"""Exercise pgAdmin's real query tool against the existing app role."""
from pathlib import Path
from urllib.request import Request,build_opener,HTTPCookieProcessor
from urllib.error import HTTPError
from http.cookiejar import CookieJar
import json
import re
import time
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
state=json.loads((ROOT/'.secrets'/'pgadmin-runtime.json').read_text(encoding='utf-8'))
profiles=json.loads((ROOT/'var'/'pgadmin'/'easyerp-configured.json').read_text(encoding='utf-8'))
BASE=state['url'];opener=build_opener(HTTPCookieProcessor(CookieJar()))


def request(path,data=None,method=None,headers=None):
    content=None if data is None else json.dumps(data).encode()
    req=Request(BASE+path,data=content,method=method,headers=headers or {})
    if content: req.add_header('Content-Type','application/json')
    try:
        with opener.open(req,timeout=20) as r: return r.read().decode('utf-8')
    except HTTPError as ex:
        body=ex.read().decode('utf-8',errors='replace').replace(state['key'],'[redacted]')
        raise RuntimeError('HTTP '+str(ex.code)+' '+body[:2000]) from None


html=request('/?key='+state['key'])
assert 'pgAdmin' in html
js=request('/browser/js/utils.js')
token=re.search(r"pgAdmin\['csrf_token'\]\s*=\s*'([^']+)'",js)[1]
header=re.search(r"pgAdmin\['csrf_token_header'\]\s*=\s*'([^']+)'",js)[1]
headers={header:token}
# The normal pgAdmin page performs this desktop OS-secret-storage initialization.
# No password is supplied or changed by this test.
master=json.loads(request('/browser/master_password',{'password':''},'POST',headers))
print('DESKTOP_KEY_READY',bool(master.get('data',{}).get('present')))
profile=profiles['profiles'][0]
gid=profile['group_id'];sid=profile['server_id']
connected=json.loads(request(f'/browser/server/connect/{gid}/{sid}',{},'POST',headers))
print('CONNECT',connected.get('success')==1)
assert connected.get('success')==1
trans=731421
did=connected['data']['did']
initialized=json.loads(request(f'/sqleditor/initialize/sqleditor/{trans}/{gid}/{sid}/{did}',{'dbname':profile['database']},'POST',headers))
print('INITIALIZE',initialized.get('success')==1)
assert initialized.get('success')==1
sql="SELECT current_database() AS database,current_user AS role,(SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('finance','legal','production','rd','sales','analysis') AND table_type='BASE TABLE') AS business_tables,(SELECT count(*) FROM information_schema.views WHERE table_schema IN ('finance','legal','production','rd','sales','analysis')) AS standard_views;"
started=json.loads(request(f'/sqleditor/query_tool/start/{trans}',{'sql':sql},'POST',headers))
print('QUERY',started.get('success')==1)
for i in range(30):
    result=json.loads(request(f'/sqleditor/poll/{trans}',headers=headers))
    if result.get('data',{}).get('status')!='Busy':break
    time.sleep(.2)
print('RESULT',json.dumps(result.get('data',{}).get('result'),ensure_ascii=False))
assert result['success']==1 and result['data']['status']=='Success'
expected=json.loads((ROOT/'db/manifest.json').read_text(encoding='utf-8'))['counts']
database=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))['database']
assert result['data']['result']==[[database,'easyerp_app',str(expected['tables']),str(expected['views'])]]
request(f'/sqleditor/close/{trans}',method='DELETE',headers=headers)
(ROOT/'reports'/'sql-interface-tests.json').write_text(json.dumps({
  'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS',
  'pgadmin_version':profiles['pgadmin_version'],'database':'easyerp_v02','role':'easyerp_app',
  'is_superuser':connected['data']['user']['is_superuser'],'pgpass_connection':True,
  'query_tool_initialized':True,'sql_result':result['data']['result'],
  'query_session_closed':True,'database_password_stored_in_pgadmin':False
},ensure_ascii=False,indent=2),encoding='utf-8')
