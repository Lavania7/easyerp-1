"""Real HTTP/SQL/browser date-range checks. Synthetic rows only enter demo."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from datetime import datetime,timezone
import argparse,csv,io,json,os,subprocess,sys,uuid

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8092')
parser.add_argument('--screenshot-dir',type=Path)
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from easyerp import ERP,literal as L,ident as I
erp=ERP();demo=erp.c['database']+'_ui_demo';run='qa_date_'+uuid.uuid4().hex[:12]
created=[];passed=[];token='';counter=0
before=erp.data_signature(erp.c['database'])
base={'mode':'demo','start':'2026-10-10','end':'2026-10-10','tz':'Asia/Shanghai','currency':'CNY'}
report=ROOT/'reports/date-query-tests.json'

def check(label,condition=True):
    if not condition:raise AssertionError(label)
    passed.append(label);print('PASS: '+label,flush=True)

def get(path,**params):
    with urlopen(args.url+'/api/'+path+'?'+urlencode({**base,**params}),timeout=30) as response:return json.load(response)

def save(obj,values,children=None):
    global counter
    counter+=1
    payload={'request_id':run+'_'+str(counter),'object':obj,'values':values}
    if children:payload['children']=children
    request=Request(args.url+'/api/entry/save?mode=demo',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','X-EasyERP-Token':token})
    with urlopen(request,timeout=30) as response:result=json.load(response)
    created.extend((row['object'],row['id']) for row in result['records'])
    return result

try:
    metadata=get('entry/meta');token=metadata['token'];pk={o['key']:o['pk'] for o in metadata['objects']}
    times=['2026-10-09T15:59:59.999999Z','2026-10-09T16:00:00Z','2026-10-10T15:59:59.999999Z','2026-10-10T16:00:00Z']
    for n,time in enumerate(times):save('finance.资金流水表',{'资金记录ID':run+'_cash_'+str(n),'账户ID':'account','发生时间':time,'金额':'12.3400','收支方向':'收入','交易摘要':run})
    for n in [0,1]:save('finance.资金用途核定表',{'用途核定ID':run+'_purpose_'+str(n),'资金记录ID':run+'_cash_'+str(n),'状态':'待核定'})
    for n,day in enumerate(['2026-10-09','2026-10-10','2026-10-10','2026-10-11']):save('analysis.分析报告登记表',{'报告ID':run+'_report_'+str(n),'分析问题':run,'生成日期':day})
    for n,day in enumerate(['2026-10-09','2026-10-10']):
        save('sales.销售订单登记表',{'订单ID':run+'_order_'+str(n),'渠道ID':'channel','平台订单号':run+'_'+str(n),'客户ID':'customer','创建时间':day+'T12:00:00+08:00','币种':'CNY','状态':'待确认'},[{'object':'sales.销售订单行表','values':{'销售订单行ID':run+'_line_'+str(n),'行号':'1','原商品信息':run,'产品版本ID':'pv','数量':'1','单位ID':'unit','单价':'10','折扣金额':'0','商品实付':'10','运费分摊':'0','取消数量':'0','状态':'待履约','收货信息':'日期验收演示地址'}}])
        save('production.生产工单表',{'工单号':run+'_work_'+str(n),'发布批次ID':'release','计划数量':'1','单位ID':'unit','计划开始日期':day,'下达依据':run,'状态':'已下达','取消数量':'0'})
    save('finance.收入成本确认表',{'确认ID':run+'_rec','所属月份':'2026-10-01','销售订单行ID':run+'_line_1','确认批次':run,'行号':'1','确认数量':'1','确认收入':'10','税额':'0','结转成本':'5','币种':'CNY','政策ID':'policy','确认依据':run,'状态':'已核定'})
    for n,foundation in enumerate([None,'2026-10-10']):save('legal.公司主体档案表',{'主体ID':run+'_company_'+str(n),'公司名称':'日期筛选验收公司（演示）','统一社会信用代码':run+'_company_'+str(n),'注册地址':'日期验收演示地址','有效状态':'有效','成立日期':foundation})
    expected={run+'_cash_1',run+'_cash_2'}
    for kind in ['list','explore']:
        result=get(kind,search=run,**({'kind':'funds'} if kind=='list' else {'object':'finance.资金流水表'}))
        check(kind+' keeps both Beijing date boundaries', {row['资金记录ID'] for row in result['rows']}==expected and int(result['total'][0]['count'])==2)
    check('master-record date filtering matches the source table',{row['资金记录ID'] for row in get('explore',object='finance.资金流水表',search=run)['rows']}==expected)
    reports=get('explore',object='analysis.分析报告登记表',search=run,limit=1,offset=1)
    check('date rows, counts and pagination agree',int(reports['total'][0]['count'])==2 and len(reports['rows'])==1 and reports['date_field']=='生成日期')
    with urlopen(args.url+'/api/export?'+urlencode({**base,'object':'finance.资金流水表','search':run})) as response:export=list(csv.DictReader(io.StringIO(response.read().decode('utf-8-sig'))))
    check('CSV export uses the same date predicate',{row['资金记录ID'] for row in export}==expected)
    check('pending orders apply the start boundary',[row['订单ID'] for row in get('list',kind='orders',scope='pending',search=run)['rows']]==[run+'_order_1'])
    check('pending work orders apply the start boundary',[row['工单号'] for row in get('list',kind='workorders',scope='pending',search=run)['rows']]==[run+'_work_1'])
    check('My Work applies both dates',{row['编号'] for row in get('tasks',search=run)['rows']}=={run+'_purpose_1',run+'_work_1'})
    check('month fields use actual stored dates rather than expand a month',int(get('explore',object='finance.收入成本确认表',scope='confirmed',search=run)['total'][0]['count'])==0 and int(get('explore',object='finance.收入成本确认表',scope='confirmed',search=run,start='2026-10-01',end='2026-10-01')['total'][0]['count'])==1)
    companies=get('explore',object='legal.公司主体档案表',search=run)
    check('NULL dates are not invented into the selected range',[row['主体ID'] for row in companies['rows']]==[run+'_company_1'])
    check('company lookup can explicitly bypass list date filtering',int(get('explore',object='legal.公司主体档案表',search=run,date_filter=0)['total'][0]['count'])==2)
    units=get('explore',object='rd.计量单位表',start='2099-01-01',end='2099-01-01')
    check('undated tables stay usable without fabricated dates',units['date_field'] is None and not units['date_filter_applied'] and any(row['单位ID']=='unit' for row in units['rows']))
    catalog=get('meta')['objects']
    check('all catalog date fields refer to real date columns',all(o['date_field'] is None or any(c['name']==o['date_field'] and (c['type']=='date' or c['type'].startswith('timestamp')) for c in o['columns']) for o in catalog))
    try:get('explore',object='finance.资金流水表',start='2026-10-11',end='2026-10-10');raise AssertionError('reversed range accepted')
    except HTTPError as error:check('backend rejects reversed date ranges',error.code==400)
    screenshots={}
    if args.screenshot_dir:
        args.screenshot_dir.mkdir(parents=True,exist_ok=True);screenshots={'desktopScreenshot':str((args.screenshot_dir/'date-query-desktop.png').resolve()),'mobileScreenshot':str((args.screenshot_dir/'date-query-mobile.png').resolve())}
    fixture={'url':args.url,'run':run,'company':run+'_company_0','order':run+'_order_1','result':str(report),**screenshots}
    subprocess.run(['node',str(ROOT/'tests/test_date_query.cjs')],env={**os.environ,'EASYERP_DATE_FIXTURE':json.dumps(fixture,ensure_ascii=False)},check=True,timeout=180)
    check('unknown company date remains NULL in SQL',erp.sql(f'SELECT "成立日期" IS NULL FROM legal."公司主体档案表" WHERE "主体ID"={L(run+"_company_0")}',db=demo,role='easyerp_read').stdout.strip()=='t')
finally:
    cleanup=[]
    for obj,row_id in reversed(created):
        schema,table=obj.split('.',1);cleanup.append(f'DELETE FROM {I(schema)}.{I(table)} WHERE {I(pk[obj])}={L(row_id)};')
    cleanup.append(f'DELETE FROM erp_ops.frontend_entry_audit WHERE left(request_id,{len(run)})={L(run)};')
    erp.sql('BEGIN;\n'+'\n'.join(cleanup)+'\nCOMMIT;',db=demo,role='easyerp_admin')
    after=erp.data_signature(erp.c['database']);assert before==after,'Formal business data changed'
result=json.loads(report.read_text(encoding='utf-8'));result['passed']=passed+result['passed'];result['checks']=len(result['passed'])
result.update(at_utc=datetime.now(timezone.utc).isoformat(),direct_sql_verified=True,test_rows_removed=True,formal_signature_before=before,formal_signature_after=after)
report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('SQL/HTTP/browser date checks, cleanup and formal signature: PASS')
