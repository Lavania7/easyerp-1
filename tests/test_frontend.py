"""HTTP and real PostgreSQL integration tests; never writes to the live database."""
from pathlib import Path
from urllib.request import urlopen,Request
from urllib.parse import urlencode
from urllib.error import HTTPError
from datetime import datetime, timezone
import csv
import io
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
from easyerp import ERP,write_json
e=ERP(); demo=e.c['database']+'_ui_demo'; passed=[]
base={'mode':'demo','start':'2026-10-01','end':'2026-10-22','currency':'CNY','tz':'UTC'}


def get(path,**params):
    with urlopen('http://127.0.0.1:8092/api/'+path+'?'+urlencode({**base,**params}),timeout=15) as r:
        return json.load(r)


def check(name,value):
    if not value: raise AssertionError(name)
    passed.append(name)


def status(path,code,**params):
    try: get(path,**params)
    except HTTPError as ex: return ex.code==code
    return code==200


def live_count():
    return e.sql("SELECT sum(n) FROM ("+' UNION ALL '.join(
        f'SELECT count(*) n FROM "{s}"."{t}"' for s,t in [v.split('|') for v in e.sql("SELECT schemaname||'|'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis');").stdout.splitlines()])+') x;').stdout.strip()


before=live_count()
try:
    check('live empty state preserves unknown amounts',get('overview',mode='live')['sales']==[])
    with urlopen('http://127.0.0.1:8092/api/export?'+urlencode({**base,'mode':'live','kind':'orders'})) as r:
        header=next(csv.reader(io.StringIO(r.read().decode('utf-8-sig'))))
    check('empty export preserves source field names','销售订单行ID' in header and '商品实付' in header)
    check('HTTP uses read-only DB role',get('health')['status'][0]['role']=='easyerp_read')
    meta=get('meta')
    check('all 15 standard views plus 3 operations views exposed',sum(x['kind']=='v' for x in meta['objects'])==18)
    for obj in meta['objects']:
        if obj['kind']=='v':
            get('explore',object=obj['schema']+'.'+obj['name'])
            check('standard view '+obj['schema']+'.'+obj['name'],True)
    orders=get('list',kind='orders')
    check('order business names resolved',orders['rows'][0]['产品名称']=='工业控制板')
    check('customer sourced from customer record',orders['rows'][0]['客户名称']=='青禾设备（演示）')
    check('shipment and remaining quantities independent',orders['rows'][0]['已登记发货数量']=='3.000000' and orders['rows'][0]['待履约数量']=='7.000000')
    check('date filtering excludes earlier orders',get('list',kind='orders',start='2026-10-05')['total'][0]['count']==0)
    check('pending metric drilldown keeps older unfinished orders',get('list',kind='orders',start='2026-10-05',scope='pending')['total'][0]['count']==1)
    check('literal search prevents SQL injection',get('list',kind='orders',search="' OR 1=1 --")['total'][0]['count']==0)
    check('order detail shipment history',len(get('detail',kind='order',id='order')['shipments'])==1)
    check('order detail finance tracing',len(get('detail',kind='order',id='order')['settlements'])==2)
    work=get('detail',kind='workorder',id='work')
    check('fixed BOM release and output traced',work['basic'][0]['BOM登记ID']=='bom' and work['basic'][0]['截至合格数量']=='4.000000')
    check('work actual hours traced',len(work['hours'])==1)
    fund=get('detail',kind='fund',id='cash')
    check('settlement not multiplied by joins',fund['basic'][0]['已核定分摊金额']=='100.0000')
    check('missing allocation stays NULL',get('detail',kind='fund',id='pending-cash')['basic'][0]['分摊差额'] is None)
    check('global search reaches customer names',any(r['业务']=='客户' for r in get('search',search='青禾')['rows']))
    check('master record and references retrievable',get('record',object='rd.产品版本表',id='pv')['basic'][0]['PID']=='pid')
    check('invalid date rejected',status('overview',400,start='bad'))
    check('invalid timezone rejected',status('overview',400,tz='invalid'))
    check('internal metadata excluded',status('explore',400,object='erp_ops.schema_version'))
    check('arbitrary SQL object excluded',status('explore',400,object='pg_catalog.pg_authid'))
    try: urlopen(Request('http://127.0.0.1:8092/api/overview',method='POST'))
    except HTTPError as ex: check('HTTP writes rejected',ex.code==405)
    try: urlopen(Request('http://127.0.0.1:8092/api/health',headers={'Host':'evil.invalid'}))
    except HTTPError as ex: check('unexpected host rejected',ex.code==403)
    try: urlopen(Request('http://127.0.0.1:8092/api/health',headers={'Origin':'https://evil.invalid'}))
    except HTTPError as ex: check('cross-origin requests rejected',ex.code==403)
    e.sql('''BEGIN;
INSERT INTO finance."资金账户档案表"("账户ID","账户名","主体ID","平台","币种","账户性质") VALUES
('__ui_qa_usd','QA美元','co','QA','USD','银行'),('__ui_qa_cny','QA人民币','co','QA','CNY','银行');
INSERT INTO finance."资金流水表" VALUES
('__ui_qa_usdflow','__ui_qa_usd','2026-10-10T12:00:00Z',12.34,'收入',NULL,'QA'),
('__ui_qa_out','account','2026-10-10T12:00:00Z',50,'支出',NULL,'QA'),
('__ui_qa_in','__ui_qa_cny','2026-10-10T12:00:00Z',50,'收入',NULL,'QA'),
('__ui_qa_dup','account','2026-10-10T12:00:00Z',100,'收入',NULL,'QA'),
('__ui_qa_precision','account','2026-09-30T23:30:00Z',9007199254740993.1234,'收入','','=SUM(1,1)');
INSERT INTO finance."内部划转对应表"("划转对应ID","转出资金记录ID","转入资金记录ID","划转金额","状态") VALUES ('__ui_qa_transfer','__ui_qa_out','__ui_qa_in',50,'已核定');
INSERT INTO finance."重复记录对应表"("重复对应ID","原资金记录ID","重复资金记录ID","状态") VALUES ('__ui_qa_duplicate','cash','__ui_qa_dup','已核定');
COMMIT;''',db=demo)
    ov=get('overview',currency='ALL')
    incomes={r['币种']:r['外部金额'] for r in ov['cash'] if r['收支方向']=='收入'}
    check('currencies never summed together',incomes['USD']=='12.3400' and incomes['CNY']=='100.0000')
    check('confirmed internal transfers shown separately',any(r['内部划转金额']=='50.0000' for r in ov['cash']))
    check('confirmed duplicates excluded',any(r['重复记录数']==1 for r in ov['cash']))
    check('cash metric drilldown excludes transfers and duplicates',get('list',kind='funds',scope='cash-income')['total'][0]['count']==1)
    precision=get('list',kind='funds',search='__ui_qa_precision',start='2026-09-30')['rows'][0]
    check('decimal amount survives JSON without float loss',precision['金额']=='9007199254740993.1234')
    check('UTC business date excludes previous evening',get('list',kind='funds',search='__ui_qa_precision')['total'][0]['count']==0)
    check('selected timezone controls day boundary',get('list',kind='funds',search='__ui_qa_precision',tz='Asia/Shanghai')['total'][0]['count']==1)
    with urlopen('http://127.0.0.1:8092/api/export?'+urlencode({**base,'kind':'funds','search':'__ui_qa_precision','start':'2026-09-30'})) as r:
        rows=list(csv.DictReader(io.StringIO(r.read().decode('utf-8-sig'))))
    check('CSV preserves exact amount',rows[0]['金额']=='9007199254740993.1234')
    check('CSV escapes formula-looking text',rows[0]['交易摘要']=="'=SUM(1,1)")
    check('CSV distinguishes empty string from NULL',rows[0]['平台交易号']=='')
    page=get('list',kind='funds',limit='1')
    check('pagination returns bounded rows and full total',len(page['rows'])==1 and page['total'][0]['count']>1)
finally:
    e.sql('''BEGIN;DELETE FROM finance."内部划转对应表" WHERE "划转对应ID"='__ui_qa_transfer'; DELETE FROM finance."重复记录对应表" WHERE "重复对应ID"='__ui_qa_duplicate'; DELETE FROM finance."资金流水表" WHERE left("资金记录ID",8)='__ui_qa_'; DELETE FROM finance."资金账户档案表" WHERE left("账户ID",8)='__ui_qa_'; COMMIT;''',db=demo)
check('live business row count unchanged',live_count()==before)
report={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','checks':len(passed),'passed':passed,
        'live_rows_before':int(before),'live_rows_after':int(live_count()),'qa_rows_removed':True}
write_json(ROOT/'reports'/'frontend-tests.json',report)
print(json.dumps(report,ensure_ascii=False,indent=2))
