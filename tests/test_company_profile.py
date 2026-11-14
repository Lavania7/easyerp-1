"""Company profile UI and PostgreSQL integration. All fixtures stay in demo."""
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

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8092')
parser.add_argument('--node', default='node')
parser.add_argument('--screenshot', type=Path)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from easyerp import ERP, literal as L
erp = ERP()
demo = erp.c['database']+'_ui_demo'
run = 'qa_company_'+uuid.uuid4().hex[:12]
first, second = run+'_first', run+'_second'
before = erp.data_signature(erp.c['database'])
report = ROOT/'reports/company-profile-tests.json'
token = ''


def call(path, payload=None):
    request = Request(args.url+'/api/entry/'+path+'?'+urlencode({'mode':'demo'}),
                      data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode(),
                      headers={'Content-Type':'application/json','X-EasyERP-Token':token})
    with urlopen(request,timeout=30) as response:
        return json.load(response)


try:
    metadata = call('meta')
    assert metadata['mode'] == 'demo'
    token = metadata['token']
    for row_id, suffix, label in ((first,'A','甲'), (second,'B','乙')):
        call('save', {'request_id':run+'_create_'+suffix, 'object':'legal.公司主体档案表', 'values':{
            '主体ID':row_id, '公司名称':'公司资料验收'+label+'有限公司', '公司简称':'公司验收'+label,
            '公司英文名':'Company Profile QA '+suffix, '统一社会信用代码':run+'_'+suffix,
            '注册地址':'验收注册地址', '办公地址':'验收办公地址',
            '联系电话':'+86 010 12345678', '有效状态':'有效', '成立日期':'2026-10-30'}})
    fixture = {'url':args.url, 'run':run, 'token':token, 'first':first,'second':second,
               'result':str(report),'screenshot':str(args.screenshot.resolve()) if args.screenshot else None}
    env = {**os.environ,'EASYERP_COMPANY_FIXTURE':json.dumps(fixture,ensure_ascii=False)}
    subprocess.run([args.node,str(ROOT/'tests/test_company_profile.cjs')],env=env,check=True,timeout=180)
    row = json.loads(erp.sql(f'SELECT row_to_json(t) FROM legal."公司主体档案表" t WHERE "主体ID"={L(first)}', db=demo,role='easyerp_read').stdout)
    assert row['公司英文名'] == 'Company Profile QA Updated' and row['联系电话'] == '其他页面更新的电话'
    assert row['公司名称'] == '来自表格的公司完整名称有限公司' and row['公司简称'] == '公司验收已更新' and row['备注'] == '<script>保留为原文</script>'
    assert row['法定代表人'] is None
    grants = erp.sql("SELECT has_column_privilege('easyerp_app','legal.公司主体档案表','公司英文名','UPDATE') AND NOT has_column_privilege('easyerp_read','legal.公司主体档案表','公司英文名','UPDATE')", db=demo,role='easyerp_read').stdout.strip()
    assert grants == 't'
finally:
    # Cleanup only exact fixture IDs/credit codes. Business foreign keys still protect dependencies.
    erp.sql(f'''BEGIN;
      DELETE FROM erp_ops.frontend_entry_audit a WHERE left(request_id,{len(run)})={L(run)}
        OR a.changes @> jsonb_build_array(jsonb_build_object('after',jsonb_build_object('主体ID',{L(first)})))
        OR a.changes @> jsonb_build_array(jsonb_build_object('after',jsonb_build_object('主体ID',{L(second)})))
        OR a.changes @> jsonb_build_array(jsonb_build_object('after',jsonb_build_object('统一社会信用代码',{L(run+'_NEW')})));
      DELETE FROM legal."公司主体档案表" WHERE "主体ID" IN ({L(first)},{L(second)}) OR "统一社会信用代码"={L(run+'_NEW')};
      COMMIT;''',db=demo,role='easyerp_admin')
    after = erp.data_signature(erp.c['database'])
    assert after == before, 'Formal business data changed'

result = json.loads(report.read_text(encoding='utf-8'))
result.update(at_utc=datetime.now(timezone.utc).isoformat(),direct_sql_verified=True,
              role_permissions_verified=True,test_rows_removed=True,
              formal_signature_before=before,formal_signature_after=after)
report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Direct SQL, permissions, fixture cleanup and formal data signature: PASS')
