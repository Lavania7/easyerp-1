"""End-to-end checks for the actual legacy import, without changing source data."""
from pathlib import Path
from decimal import Decimal
from urllib.request import urlopen
from urllib.parse import urlencode
import argparse
import hashlib
import json
import sys

def main():
    p=argparse.ArgumentParser(); p.add_argument('--project-root',type=Path,required=True); p.add_argument('--report',type=Path,required=True); p.add_argument('--url',default='http://127.0.0.1:8092'); a=p.parse_args()
    report=json.loads(a.report.read_text(encoding='utf-8')); checks=[]
    sys.path.insert(0,str(a.project_root/'tools')); from easyerp import ERP,ident
    sys.path.insert(0,str(a.project_root/'app')); from data import Data
    e=ERP()
    def check(label,ok):
        checks.append({'check':label,'passed':bool(ok)})
        if not ok: raise AssertionError(label)
    def rows(query): return [json.loads(v,parse_float=Decimal) for v in e.sql('SELECT row_to_json(x) FROM ('+query+') x;').stdout.splitlines() if v]
    for table,count in report['table_counts'].items():
        schema,name=table.split('.',1); actual=int(e.sql('SELECT count(*) FROM '+ident(schema)+'.'+ident(name)).stdout.strip())
        check(table+' exact row count',actual==count)
    counts=rows('''SELECT (SELECT count(*) FROM erp_ops.source_import_file) AS files,
    (SELECT count(*) FROM erp_ops.source_import_row) AS raw_rows,
    (SELECT count(*) FROM erp_ops.source_import_run) AS batches,
    (SELECT count(*) FROM erp_ops.source_import_nullability WHERE was_required) AS nullable_changes,
    (SELECT count(*) FROM legal."公司主体档案表") AS companies,
    (SELECT count(*) FROM sales."客户档案表") AS customers,
    (SELECT count(*) FROM finance."会计凭证表") AS vouchers''')[0]
    check('37 files and all original rows preserved',counts['files']==len(report['files']) and counts['raw_rows']==report['raw_rows'])
    check('one committed import batch',counts['batches']==1)
    check('only 14 required-field flags relaxed',counts['nullable_changes']==14)
    check('no invented companies, customers or vouchers',counts['companies']==counts['customers']==counts['vouchers']==0)
    blanks=rows('''SELECT count(*) FILTER(WHERE "数量" IS NULL) AS unknown_quantities,
    count(*) FILTER(WHERE "单位ID" IS NULL AND "单价" IS NULL AND "折扣金额" IS NULL AND "取消数量" IS NULL AND "产品版本ID" IS NULL) AS missing_facts,
    count(*) FILTER(WHERE "商品实付" IS NULL) AS unknown_paid
    FROM sales."销售订单行表"''')[0]
    check('18 multigood line quantities remain NULL',blanks['unknown_quantities']==18)
    check('all missing line facts remain NULL',blanks['missing_facts']==192)
    check('incomplete paid allocation remains NULL',blanks['unknown_paid']>=18)
    totals=rows('''SELECT a."账户名" AS account,count(*) AS rows,
    sum(f."金额") FILTER(WHERE f."收支方向"='收入') AS income,
    sum(f."金额") FILTER(WHERE f."收支方向"='支出') AS expense
    FROM finance."资金流水表" f JOIN finance."资金账户档案表" a USING("账户ID") GROUP BY 1''')
    expected={'企业网银账户':('142','44166.53','44920.30'),'企业聚合结算账户':('157','5531.34','5581.15'),'企业支付宝账户':('1370','38722.90','38430.57'),'保证金账户':('29','209.30','209.30')}
    for t in totals:
        n,i,o=expected[t['account']]
        check(t['account']+' independent source totals',t['rows']==int(n) and t['income']==Decimal(i) and t['expense']==Decimal(o))
    check('nine source summary/detail reconciliations',len(report['alipay_reconciliation'])==9 and all(r['passed'] for r in report['alipay_reconciliation']))
    check('all source bytes unchanged',all(hashlib.sha256((Path(report['source_root'])/f['relative_path']).read_bytes()).hexdigest()==f['sha256'] for f in report['files']))
    params={'mode':'live','start':'2026-01-01','end':'2026-09-30','currency':'ALL','tz':'Asia/Shanghai','limit':'200'}
    data=Data(params)
    for kind,expected_count in [('orders',192),('funds',1698)]:
        listing=data.listing(kind)
        check(kind+' backend includes unknown references and currencies',listing['total'][0]['count']==expected_count)
    overview=data.overview(); check('overview tracks incomplete sales sum',overview['sales'][0]['实付已填数']<overview['sales'][0]['记录数'])
    check('missing order quantities never become completed quantity',overview['pending_orders'][0]['待核订单行']==192)
    catalog=data.catalog(); check('currency options contain no null entry',all(c['币种'] is not None for c in catalog['currencies']))
    def api(path,extra=None):
        with urlopen(a.url+'/api/'+path+'?'+urlencode({**params,**(extra or {})}),timeout=30) as response: return json.loads(response.read())
    health=api('health');check('running frontend points to the formal database',health['ok'] and health['status'][0]['database']=='easyerp_v02')
    for kind,count in [('orders',192),('funds',1698)]:
        listing=api('list',{'kind':kind});check(kind+' HTTP listing count',listing['total'][0]['count']==count)
        first=listing['rows'][0]; key=first['订单ID'] if kind=='orders' else first['资金记录ID']; detail=api('detail',{'kind':'order' if kind=='orders' else 'fund','id':key})
        check(kind+' HTTP details and provenance',bool(detail['basic']) and bool(detail['source_files'] if kind=='orders' else detail['sources']))
    meta=api('meta'); check('import exception view visible in application',any(o['name']=='导入待补事项' for o in meta['objects']))
    overview=api('overview'); check('HTTP incomplete-sales count present',overview['sales'][0]['实付已填数']<overview['sales'][0]['记录数'])
    out={'passed':all(c['passed'] for c in checks),'checks':checks,'account_totals':totals,'preserved_nulls':blanks,'database_counts':counts}
    a.report.with_name('verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'passed':out['passed'],'checks':len(checks),'database_counts':counts,'preserved_nulls':blanks},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
