"""My Work editing and full-width header integration. Fixtures only enter demo."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from datetime import datetime, timezone
import argparse
import json
import os
import subprocess
import sys
import uuid

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8092')
parser.add_argument('--node',default='node')
parser.add_argument('--screenshot-dir',type=Path)
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from easyerp import ERP,literal as L
erp=ERP();demo=erp.c['database']+'_ui_demo'
run='qa_tasks_'+uuid.uuid4().hex[:12]
cash,purpose,company=run+'_cash',run+'_purpose',run+'_company'
company_name='公司全称完整显示与自动换行验收技术研发及生产服务有限公司'
report=ROOT/'reports/tasks-header-tests.json'
before=erp.data_signature(erp.c['database']);token=''


def call(path,payload=None):
    req=Request(args.url+'/api/entry/'+path+'?'+urlencode({'mode':'demo'}),
                data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode(),
                headers={'Content-Type':'application/json','X-EasyERP-Token':token})
    with urlopen(req,timeout=30) as response:return json.load(response)


try:
    token=call('meta')['token']
    for suffix,obj,values in [
        ('cash','finance.资金流水表',{'资金记录ID':cash,'账户ID':'account','发生时间':'2026-10-30T04:00:00+00:00','金额':'12.3400','收支方向':'收入','交易摘要':'待办编辑隔离样例'}),
        ('purpose','finance.资金用途核定表',{'用途核定ID':purpose,'资金记录ID':cash,'状态':'待核定'}),
        ('company','legal.公司主体档案表',{'主体ID':company,'公司名称':company_name,'公司简称':'不显示这个简称','统一社会信用代码':run,'注册地址':'顶栏验收地址','有效状态':'有效'})]:
        call('save',{'request_id':run+'_create_'+suffix,'object':obj,'values':values})
    screenshots={}
    if args.screenshot_dir:
        args.screenshot_dir.mkdir(parents=True,exist_ok=True)
        screenshots={'desktopScreenshot':str((args.screenshot_dir/'tasks-header-desktop.png').resolve()),'mobileScreenshot':str((args.screenshot_dir/'tasks-header-mobile.png').resolve())}
    fixture={'url':args.url,'cash':cash,'purpose':purpose,'company':company,'companyName':company_name,'result':str(report),**screenshots}
    subprocess.run([args.node,str(ROOT/'tests/test_tasks_header.cjs')],env={**os.environ,'EASYERP_TASKS_FIXTURE':json.dumps(fixture,ensure_ascii=False)},check=True,timeout=180)
    actual=erp.sql(f'SELECT "状态"||\'|\'||"依据" FROM finance."资金用途核定表" WHERE "用途核定ID"={L(purpose)}',db=demo,role='easyerp_read').stdout.strip()
    assert actual=='已撤销|我的工作编辑保存验收',actual
    assert erp.sql(f'SELECT "金额" FROM finance."资金流水表" WHERE "资金记录ID"={L(cash)}',db=demo,role='easyerp_read').stdout.strip()=='12.3400'
finally:
    erp.sql(f'''BEGIN;
      DELETE FROM finance."资金用途核定表" WHERE "用途核定ID"={L(purpose)};
      DELETE FROM finance."资金流水表" WHERE "资金记录ID"={L(cash)};
      DELETE FROM legal."公司主体档案表" WHERE "主体ID"={L(company)};
      DELETE FROM erp_ops.frontend_entry_audit a WHERE left(request_id,{len(run)})={L(run)}
       OR a.changes @> jsonb_build_array(jsonb_build_object('after',jsonb_build_object('用途核定ID',{L(purpose)})));
      COMMIT;''',db=demo,role='easyerp_admin')
    after=erp.data_signature(erp.c['database'])
    assert before==after,'Formal business records changed'
result=json.loads(report.read_text(encoding='utf-8'))
result.update(at_utc=datetime.now(timezone.utc).isoformat(),direct_sql_verified=True,parent_fund_unchanged=True,test_rows_removed=True,formal_signature_before=before,formal_signature_after=after)
report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Direct SQL, parent fund preservation, cleanup and formal data signature: PASS')
