"""Browser/HTTP checks of human names and private identifier suppression; demo fixtures only."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import argparse
import json
import os
import subprocess
import sys
import uuid

parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8092');parser.add_argument('--screenshot',type=Path)
args=parser.parse_args();root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'));sys.path.insert(0,str(root/'app'))
from easyerp import ERP,literal as L,ident as I
from identifiers import RULES,issued_date
from hashlib import sha256
from workspace import Workspace
erp=ERP();demo=erp.c['database']+'_ui_demo';run='qa_id_ui_'+uuid.uuid4().hex[:12];token=''
def call(path,payload=None):
    request=Request(args.url+'/api/'+path+('mode=demo' if path.endswith('?') else '&mode=demo'),data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','X-EasyERP-Token':token})
    with urlopen(request,timeout=30) as response:return json.load(response)
def signature():
    queries=[]
    for key in RULES:
        s,n=key.split('.',1);queries.append('SELECT '+L(key)+" AS object,count(*) AS n,md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) AS hash FROM "+I(s)+'.'+I(n)+' t')
    return erp.sql('SELECT json_agg(x) FROM ('+' UNION ALL '.join(queries)+') x;',db=erp.c['database'],role='easyerp_read').stdout
before=signature();report=root/'reports/identifier-ui-tests.json'
try:
    token=call('entry/meta?')['token']
    customer=call('entry/save?',{'request_id':uuid.uuid4().hex,'object':'sales.客户档案表','values':{'客户名称':'界面验收客户','客户来源标识':run}})['records'][0]['id']
    identifier=call('identity?'+urlencode({'object':'sales.客户档案表','id':customer}))['records'][0]
    assert identifier['issued_on']==issued_date() and identifier['sha256']==sha256(identifier['long_id'].encode()).hexdigest()
    purchase=call('entry/record?'+urlencode({'object':'production.采购订单表','id':'po'}))['values']['采购单ID']
    supplier=call('entry/record?'+urlencode({'object':'production.供应商档案表','id':'supplier'}))['values']['供应商ID']
    plan=call('workspace/save?',{'request_id':uuid.uuid4().hex,'kind':'plan','values':{'title':run+'_plan','department':'production'}})['item']['id']
    env={**os.environ,'EASYERP_ID_UI_FIXTURE':json.dumps({'url':args.url,'run':run,'customer':customer,'purchase':purchase,'supplier':supplier,'plan':plan,'result':str(report),'screenshot':str(args.screenshot.resolve()) if args.screenshot else None},ensure_ascii=False)}
    subprocess.run(['node',str(root/'tests/test_identifier_ui.cjs')],env=env,check=True,timeout=180)
finally:
    ids=json.loads(erp.sql('SELECT coalesce(json_agg("客户ID"),\'[]\'::json) FROM sales."客户档案表" WHERE "客户来源标识"='+L(run),db=demo,role='easyerp_read').stdout)
    erp.sql('BEGIN; DELETE FROM sales."客户档案表" WHERE "客户来源标识"='+L(run)+'; DELETE FROM erp_ops.frontend_entry_audit WHERE changes @> jsonb_build_array(jsonb_build_object(\'after\',jsonb_build_object(\'客户来源标识\','+L(run)+')));'+(' DELETE FROM erp_ops.business_id_allocations WHERE table_key=\'sales.客户档案表\' AND id IN ('+','.join(map(L,ids))+'); DELETE FROM erp_ops.business_record_ids WHERE table_key=\'sales.客户档案表\' AND short_id IN ('+','.join(map(L,ids))+');' if ids else '')+' COMMIT;',db=demo,role='easyerp_admin')
    ws=Workspace('demo')
    with ws.locked():
        data=ws.read();ours={key for key,item in data['items'].items() if item['values'].get('title') in (run+'_plan',run+'_workflow')}
        for key in ours:del data['items'][key]
        data['requests']={key:value for key,value in data['requests'].items() if value['result']['item']['id'] not in ours};ws.write(data)
    assert signature()==before,'Formal business records changed during browser tests'
result=json.loads(report.read_text(encoding='utf-8'));result.update(test_rows_removed=True,formal_business_unchanged=True)
report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Demo fixtures cleaned and formal business records unchanged: PASS')
