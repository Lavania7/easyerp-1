"""Real HTTP/SQL tests; synthetic rows and constraint changes are confined to demo."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import csv,io,json,sqlite3,sys,uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from data import Data,I,L
from standard_import import StandardImport
BASE='http://127.0.0.1:8092';prefix='qa_csv_'+uuid.uuid4().hex[:14]
checks=[];check_ids=[];request_ids=[];owned={};token=''
data=Data({'mode':'demo'});erp=data.erp;demo=data.db
def check(label,condition):
    if not condition:raise AssertionError(label)
    checks.append(label)
def api(path,query=None,body=None,expected=200,headers=None,auth=None):
    options={'Content-Type':'application/octet-stream' if isinstance(body,bytes) else 'application/json','X-EasyERP-Token':token if auth is None else auth,**(headers or {})}
    raw=body if isinstance(body,bytes) or body is None else json.dumps(body,ensure_ascii=False).encode()
    req=Request(BASE+'/api/'+path+'?'+urlencode({'mode':'demo',**(query or {})}),data=raw,headers=options)
    try:response=urlopen(req,timeout=60)
    except HTTPError as exc:response=exc
    with response:status=response.status;result=json.load(response)
    if status!=expected:raise AssertionError((path,status,expected,result))
    return result
def table(key):return '.'.join(I(x) for x in key.split('.'))
def snapshot(mode):
    source=Data({'mode':mode})
    names=source.rows("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('sales','finance','production','rd','legal','analysis') ORDER BY 1,2")
    queries=["SELECT "+L(r['schemaname']+'.'+r['tablename'])+" AS key,count(*) AS n,md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) AS hash FROM "+I(r['schemaname'])+'.'+I(r['tablename'])+' t' for r in names]
    return {r['key']:(r['n'],r['hash']) for r in source.rows(' UNION ALL '.join(queries))}
SCHEMA_SQL="""SELECT n.nspname||'.'||c.relname AS key,
 (SELECT jsonb_agg(jsonb_build_array(a.attname,a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS columns,
 (SELECT jsonb_agg(jsonb_build_array(p.conname,pg_get_constraintdef(p.oid)) ORDER BY p.conname) FROM pg_constraint p WHERE p.conrelid=c.oid) AS constraints
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname IN ('sales','finance','production','rd','legal','analysis') ORDER BY 1"""
def schema(mode):return Data({'mode':mode}).rows(SCHEMA_SQL)
def own(key,ident):owned.setdefault(key,set()).add(ident);return ident
def records(key,ident):return data.rows('SELECT * FROM '+table(key)+' WHERE '+I(objects[key]['pk'])+'='+L(ident))
def file(key,rows):
    columns=[c['name'] for c in objects[key]['columns']];stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\r\n');writer.writerow(columns)
    for row in rows:writer.writerow([row.get(name,'') for name in columns])
    return stream.getvalue().encode('utf-8-sig')
def inspect(key,raw,filename=None):
    result=api('import/check',{'filename':filename or key+'.csv'},raw);check_ids.append(result['id']);return result
def execute(result,raw,expected=200,mode='demo',allow='true',merge=None):
    query={'mode':mode,'filename':result['filename'],'check_id':result['id']}
    if allow is not None:query['allow_incomplete']=allow
    if merge is not None:query['merge']=merge
    response=api('import/execute',query,raw,expected)
    if expected==200:request_ids.append(response['request_id'])
    return response
def load(key,rows,merge=None):
    raw=file(key,rows);result=inspect(key,raw);check('valid trial '+key,result['validated'] and result['can_execute'])
    return result,raw,execute(result,raw,merge=merge)
before_live=snapshot('live');before_demo=snapshot('demo');schema_live=schema('live');schema_demo=schema('demo')
metadata=api('import/meta');token=metadata['token'];objects={o['key']:o for o in api('entry/meta')['objects']}
standard=next(t for t in metadata['types'] if t['id']=='standard-master');key='finance.人员档案表'
try:
    check('146 fixed standard profiles',standard['enabled'] and standard['immutable'] and len(standard['profiles'])==146)
    api('import/settings',body={'type_id':'standard-master','enabled':False,'version':0},expected=400)
    for profile in standard['profiles']:
        result=inspect(profile['id'],file(profile['id'],[]))
        check('empty template '+profile['id'],result['match']['profile']==profile['id'] and result['validated'] and not result['can_execute'])
    raw=file(key,[{'人员ID':own(key,prefix+'_gap'),'部门':'\u3000\t'}])+b',,,,\r\n\r\n';result=inspect(key,raw)
    check('warn gaps, ignore whole blank rows',result['validated'] and result['can_execute'] and result['row_count']==1 and result['blank_cells']==4 and result['skipped_empty_rows']==2)
    check('trial rolls back business rows and constraints',not records(key,prefix+'_gap') and schema_demo==schema('demo'))
    execute(result,raw,409,allow=None);execute(result,raw,409,allow='false')
    check('no affirmative confirmation means no write',not records(key,prefix+'_gap') and schema_demo==schema('demo'))
    receipt=execute(result,raw)
    check('confirmed required gaps persist NULL',receipt['created']==1 and records(key,prefix+'_gap')[0]['姓名'] is None and records(key,prefix+'_gap')[0]['部门'] is None)
    changes=data.rows('SELECT column_name FROM erp_ops.frontend_csv_nullability WHERE request_id='+L(receipt['request_id']))
    check('NOT NULL relaxation audited',set(r['column_name'] for r in changes)=={'姓名','部门'})
    auto_raw=file(key,[{'姓名':'Generated','部门':'QA'}]);auto=inspect(key,auto_raw)
    check('generated ID preview and gap confirmation',auto['generated_id_count']==1 and auto['preview'][0]['generated_id'].startswith('CSV-'))
    own(key,auto['preview'][0]['generated_id']);a=execute(auto,auto_raw);b=execute(inspect(key,auto_raw),auto_raw,merge='fill_empty')
    check('blank ID file identity stable across checks',a['records'][0]['id']==b['records'][0]['id'] and b['created']==0 and b['unchanged']==1)
    check('invalid dates rejected',not inspect(key,file(key,[{'人员ID':prefix+'_date','姓名':'A','任职开始日期':'2026-02-30'}]))['validated'])
    check('duplicate CSV IDs rejected',not inspect(key,file(key,[{'人员ID':prefix+'_dup','姓名':'A'},{'人员ID':prefix+'_dup','姓名':'B'}]))['validated'])
    check('extra nonblank columns rejected',not inspect(key,file(key,[{'人员ID':prefix+'_extra'}]).rstrip(b'\r\n')+b',extra\r\n')['validated'])
    short=file(key,[])+(prefix+'_short,Short\r\n').encode();own(key,prefix+'_short');r=inspect(key,short)
    check('omitted trailing cells are gaps',r['validated'] and r['blank_cells']==3);execute(r,short)
    check('changed header rejected',inspect(key,file(key,[]).replace('人员ID'.encode(),b'wrong',1))['status']=='invalid')
    check('ambiguous header needs filename',inspect('analysis.交付记录表',file('analysis.交付记录表',[]),'renamed.csv')['status']=='invalid')
    check('precision enforced',bool(StandardImport('demo').plan('production.库存基准核定表.csv',file('production.库存基准核定表',[{'基准ID':prefix+'_p','数量':'1.0000001'}]))['errors']))
    order={'订单ID':prefix+'_order','渠道ID':'missing-'+prefix,'平台订单号':prefix,'创建时间':'2026-10-23T10:00:00+08:00','币种':'CNY','状态':'待确认'}
    r=inspect('sales.销售订单登记表',file('sales.销售订单登记表',[order]));check('filled FK must exist',not r['validated'] and '关联记录' in r['reason'])
    order['状态']='invented';check('enum enforced',not inspect('sales.销售订单登记表',file('sales.销售订单登记表',[order]))['validated'])
    special="中文 ' \\! =SUM(1,2) <img src=x onerror=alert(1)>\nsecond line";person=own(key,prefix+'_one')
    raw=file(key,[{'人员ID':person,'姓名':special,'部门':'QA'},{'人员ID':own(key,prefix+'_two'),'姓名':'Second','部门':'QA','任职开始日期':'2026-10-23'}]);result=inspect(key,raw)
    check('valid trial no persistence',result['validated'] and not records(key,person))
    api('import/execute',{'filename':key+'.csv','check_id':result['id']},raw,expected=403,auth='')
    api('import/execute',{'filename':key+'.csv','check_id':result['id']},raw,expected=403,headers={'Origin':'https://example.com'})
    execute(result,raw,409,mode='live');execute(result,raw+b'\r\n',409)
    with ThreadPoolExecutor(max_workers=2) as pool:receipts=list(pool.map(lambda _:execute(result,raw),range(2)))
    check('concurrent check retries import once',receipts[0]['request_id']==receipts[1]['request_id'] and receipts[0]['created']==2)
    audit=data.rows('SELECT changes FROM erp_ops.frontend_entry_audit WHERE request_id='+L(receipts[0]['request_id']))
    check('one audit has before/after/source lines',len(audit)==1 and audit[0]['changes'][0]['before'] is None and audit[0]['changes'][0]['after']['姓名']==special and audit[0]['changes'][1]['line']==4)
    check('text verbatim and optional NULL',records(key,person)[0]['姓名']==special and records(key,person)[0]['任职开始日期'] is None)
    execute(result,raw,409,merge='latest');fresh=inspect(key,raw)
    check('fresh check permits same-file operation',fresh['can_execute'] and fresh['existing_count']==2 and not fresh['execution']);execute(fresh,raw,409)
    latest=file(key,[{'人员ID':person,'姓名':'Newest','部门':' \u3000','任职开始日期':'2026-10-24'}]);r=inspect(key,latest);execute(r,latest,merge='latest');row=records(key,person)[0]
    check('latest overwrites nonblank and never clears',row['姓名']=='Newest' and row['部门']=='QA' and row['任职开始日期']=='2026-10-24')
    fill=file(key,[{'人员ID':person,'姓名':'Ignored','部门':'Ignored','任职开始日期':'2020-01-01','任职结束日期':'2026-10-25'}]);r=inspect(key,fill);receipt=execute(r,fill,merge='fill_empty');row=records(key,person)[0]
    check('fill preserves nonblank and fills NULL',row['姓名']=='Newest' and row['部门']=='QA' and row['任职开始日期']=='2026-10-24' and row['任职结束日期']=='2026-10-25' and receipt['updated']==1)
    execute(inspect(key,raw),raw,merge='latest');check('original file may reapply latest',records(key,person)[0]['姓名']==special and records(key,person)[0]['任职结束日期']=='2026-10-25')
    with sqlite3.connect(ROOT/'var/import-interface.sqlite3') as db:saved=json.loads(db.execute('SELECT result FROM checks WHERE id=?',(r['id'],)).fetchone()[0])
    check('history keeps merge choice and receipt',saved['execution']['sha256']==sha256(fill).hexdigest() and saved['execution']['merge']=='fill_empty')
    funds='finance.资金流水表';fund=own(funds,prefix+'_fund');load(funds,[{'资金记录ID':fund,'金额':'0','平台交易号':'0'}])
    erp.sql('UPDATE '+table(funds)+' SET "交易摘要"='+L(' \u3000\t')+' WHERE "资金记录ID"='+L(fund),db=demo)
    load(funds,[{'资金记录ID':fund,'金额':'12','平台交易号':'replaced','交易摘要':'Filled'}],merge='fill_empty');row=records(funds,fund)[0]
    check('fill preserves numeric/text zero and fills Unicode whitespace',str(row['金额']) in ('0','0.0','0.0000') and row['平台交易号']=='0' and row['交易摘要']=='Filled')
    load(funds,[{'资金记录ID':fund,'金额':'7','交易摘要':'\t'}],merge='latest');row=records(funds,fund)[0]
    check('latest blank preserves text',str(row['金额']) in ('7','7.0000') and row['交易摘要']=='Filled')
    check('negative value CHECK retained',not inspect(funds,file(funds,[{'资金记录ID':prefix+'_negative','金额':'-1'}]))['validated'])
    stock='production.库存基准核定表';stockid=own(stock,prefix+'_stock');baseline=schema('demo');raw=file(stock,[{'基准ID':stockid}]);r=inspect(stock,raw)
    check('missing link trial rolls back presence rule',r['validated'] and schema('demo')==baseline);receipt=execute(r,raw)
    check('presence relaxation audited',bool(data.rows('SELECT * FROM erp_ops.frontend_csv_presence_checks WHERE request_id='+L(receipt['request_id']))))
    check('two exclusive links rejected',not inspect(stock,file(stock,[{'基准ID':prefix+'_double','产品版本ID':'a','物料版本ID':'b'}]))['validated'])
    voucher='finance.会计凭证表';vid=own(voucher,prefix+'_voucher');load(voucher,[{'凭证ID':vid}])
    check('missing voucher status stays NULL, unposted',records(voucher,vid)[0]['状态'] is None)
    r=inspect(voucher,file(voucher,[{'凭证ID':vid,'状态':'已过账'}]));check('incomplete voucher cannot post',not r['validated'] and records(voucher,vid)[0]['状态'] is None)
    posted=data.rows('SELECT "凭证ID" FROM finance."会计凭证表" WHERE "状态"=\'已过账\' LIMIT 1')
    if posted:
        raw=file(voucher,[{'凭证ID':posted[0]['凭证ID'],'摘要':'Forbidden change'}]);r=inspect(voucher,raw)
        check('posted edit blocked, unchanged fill allowed',r['validated'] and bool(r['merge_validation']['latest']) and not r['merge_validation']['fill_empty'])
        execute(r,raw,400,merge='latest');receipt=execute(r,raw,merge='fill_empty');check('posted unchanged avoids mutation',receipt['unchanged']==1)
    race_raw=file(key,[{'人员ID':own(key,prefix+'_race1'),'姓名':'First','部门':'QA'},{'人员ID':own(key,prefix+'_race2'),'姓名':'Second','部门':'QA'}]);race=inspect(key,race_raw)
    erp.sql('INSERT INTO '+table(key)+'("人员ID","姓名","部门") VALUES('+','.join(map(L,[prefix+'_race2','Existing','QA']))+')',db=demo);execute(race,race_raw,409)
    check('late overlap rolls back batch',not records(key,prefix+'_race1') and records(key,prefix+'_race2')[0]['姓名']=='Existing')
    request='csv2-'+'a'*64
    for target,fields in [('erp_ops.frontend_entry_audit',['source']),('finance.人员档案表',['人员ID']),('finance.人员档案表',['unknown'])]:
        response=erp.sql('BEGIN; SELECT erp_ops.csv_allow_missing_fields('+L(table(target))+'::regclass,ARRAY['+','.join(map(L,fields))+']::text[],'+L(request)+'); ROLLBACK;',db=demo,role='easyerp_app',ok=False)
        check('helper rejects '+target+':'+fields[0],response.returncode!=0)
    response=erp.sql('SELECT erp_ops.csv_allow_missing_fields('+L(table(key))+'::regclass,ARRAY[]::text[],'+L(request)+')',db=demo,role='easyerp_read',ok=False)
    check('read role cannot relax constraints',response.returncode!=0)
finally:
    statements=['BEGIN;']
    for obj,ids in reversed(list(owned.items())):statements.append('DELETE FROM '+table(obj)+' WHERE '+I(objects[obj]['pk'])+' IN ('+','.join(map(L,ids))+');')
    if request_ids:
        requests=','.join(map(L,set(request_ids)))
        nulls=data.rows('SELECT * FROM erp_ops.frontend_csv_nullability WHERE request_id IN ('+requests+')');presence=data.rows('SELECT * FROM erp_ops.frontend_csv_presence_checks WHERE request_id IN ('+requests+')')
        for rule in presence:
            target=I(rule['schema_name'])+'.'+I(rule['table_name']);statements+=['ALTER TABLE '+target+' DROP CONSTRAINT '+I(rule['constraint_name'])+';','ALTER TABLE '+target+' ADD CONSTRAINT '+I(rule['constraint_name'])+' '+rule['old_definition']+';']
        for column in nulls:statements.append('ALTER TABLE '+I(column['schema_name'])+'.'+I(column['table_name'])+' ALTER COLUMN '+I(column['column_name'])+' SET NOT NULL;')
        for name in ('frontend_csv_presence_checks','frontend_csv_nullability','frontend_entry_audit'):statements.append('DELETE FROM erp_ops.'+name+' WHERE request_id IN ('+requests+');')
    erp.sql('\n'.join(statements+['COMMIT;']),db=demo)
    if check_ids:
        with sqlite3.connect(ROOT/'var/import-interface.sqlite3') as db:db.execute('DELETE FROM checks WHERE id IN ('+','.join('?' for _ in check_ids)+') AND mode=?',(*check_ids,'demo'))
check('formal business data unchanged',before_live==snapshot('live'));check('demo business data restored',before_demo==snapshot('demo'))
check('formal constraints unchanged',schema_live==schema('live'));check('demo constraints restored',schema_demo==schema('demo'))
report={'status':'PASS','checks':checks,'live_business_data_unchanged':True,'demo_restored':True,'business_constraints_restored':True}
(ROOT/'reports/standard-import-tests-20261023.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':'PASS','checks':len(checks),'live_business_data_unchanged':True,'demo_restored':True}))
