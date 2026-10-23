"""Verify the actual release2 import and preserve the earlier financial/sales batch."""
from pathlib import Path
from decimal import Decimal
from urllib.request import urlopen
from urllib.parse import urlencode
import argparse
import hashlib
import json
import sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--url',default='http://127.0.0.1:8092');a=p.parse_args()
    sys.path.insert(0,str(a.project_root/'bin'));from easyerp import ERP;from import_release2 import signature,qualified,sqlval;from inspect_release2 import inspect
    e=ERP();report=json.loads(a.report.read_text(encoding='utf-8'));fid=report['file_id'];checks=[]
    def check(label,passed):
        checks.append({'check':label,'passed':bool(passed)})
        if not passed:raise AssertionError(label)
    def rows(query):return [json.loads(v,parse_float=Decimal) for v in e.sql('SELECT row_to_json(x) FROM ('+query+') x').stdout.splitlines() if v]
    def count(table,where='TRUE'):return int(e.sql('SELECT count(*) FROM '+qualified(table)+' WHERE '+where).stdout.strip())
    for table,n in report['table_counts'].items():check(table+' complete row count',count(table)==n)
    before=json.loads(a.report.with_name('business-before.json').read_text(encoding='utf-8'));after=signature(e);touched={t.replace('.','|') for t in report['table_counts']}
    check('all 138 unrelated business tables unchanged',all(before[t]==after[t] for t in before if t not in touched) and len(before)-len(touched)==138)
    check('prior financial and sales counts unchanged',count('finance.资金流水表')==1698 and count('sales.销售订单登记表')==183 and count('sales.销售订单行表')==192)
    check('prior source records unchanged in count',count('erp_ops.source_import_file',"file_id LIKE 'old2-%'")==37 and count('erp_ops.source_import_row',"file_id LIKE 'old2-%'")==2100)
    check('exactly two independent import batches',count('erp_ops.source_import_run')==2)
    check('release2 source registration preserved',count('erp_ops.source_import_file','file_id='+sqlval(fid))==1)
    book=inspect(Path(report['source']));check('source SHA256 unchanged',book['sha256']==report['source_sha256'] and report['source_unchanged'])
    expected={(s['name'],r['row_no']):r['cells'] for s in book['sheets'] for r in s['rows']}
    actual=rows('SELECT sheet_name,row_no,raw_values FROM erp_ops.source_import_row WHERE file_id='+sqlval(fid))
    check('every original cell/formula/cache/style preserved',len(actual)==1334 and all(expected[(r['sheet_name'],r['row_no'])]==r['raw_values'] for r in actual))
    preserved_formulas=sum(c['formula_meta'] is not None for r in actual for c in r['raw_values'].values())
    check('all 6619 formula records retained without recalculation',preserved_formulas==6619)
    kinds=rows('SELECT record_kind,count(*) AS n FROM erp_ops.source_workbook_record WHERE file_id='+sqlval(fid)+' GROUP BY 1')
    check('all 80 meaningful source rows typed',dict((r['record_kind'],r['n']) for r in kinds)==report['business_record_counts'])
    missing=rows('''SELECT count(*) FILTER(WHERE "物料版本ID" IS NULL) AS unmatched,
     count(*) FILTER(WHERE "物料版本ID" IS NOT NULL) AS matched,
     count(*) FILTER(WHERE "单位ID" IS NULL AND "确认依据" IS NULL) AS incomplete,
     count(*) FILTER(WHERE "来源文件ID" IS NOT NULL AND "来源行号" IS NOT NULL) AS provenance
     FROM rd."BOM明细表"''')[0]
    check('17 unresolved BOM links remain NULL',missing['unmatched']==17 and missing['matched']==18)
    check('all BOM units/confirmation evidence stay NULL',missing['incomplete']==35)
    check('all BOM original row locations linked',missing['provenance']==35)
    check('unverified BOM not labelled approved',count('rd.已核定BOM明细表')==0)
    aliases=rows('''SELECT "原始器件描述","物料版本ID" FROM rd."BOM明细表"
      WHERE "原始器件描述" IN ('CuLine30x5.5x1','SMCJ36CA','SS-12D10L5')''')
    check('similar but different material names not merged',len(aliases)==4 and all(r['物料版本ID'] is None for r in aliases))
    check('missing product fields remain NULL',count('rd.产品主数据表','"规格" IS NULL AND "单位ID" IS NULL AND "类别" IS NULL')==4)
    check('missing material units and specifications remain NULL',count('rd.物料主数据表','"规格" IS NULL AND "单位ID" IS NULL')==15)
    check('missing material categories stay blank',count('rd.物料主数据表','"类别" IS NULL')==2)
    check('no fictional version names or project links',count('rd.产品版本表','"版本名称" IS NULL AND "项目ID" IS NULL AND "确认依据" IS NULL')==4 and count('rd.物料版本表','"版本名称" IS NULL AND "确认依据" IS NULL')==15)
    check('BOM versions and confirmation evidence absent',count('rd.BOM登记表','"BOM版本" IS NULL AND "确认依据" IS NULL')==4)
    check('workbook file not called approved',count('rd.项目文件登记表','"项目ID" IS NULL AND "正式版本" IS NULL AND "批准人ID" IS NULL')==1)
    check('two drafts retain missing time and owner',count('production.工单草稿表','"状态"=\'待下达\' AND "登记时间" IS NULL AND "负责人ID" IS NULL')==2)
    for table in ['production.生产工单表','production.完工记录表','production.库存基准核定表','production.库存变动表','production.到货记录表','production.采购订单表','finance.会计凭证表','finance.收入成本确认表','rd.项目登记表','rd.计量单位表']:
        check('no unsupported actual record in '+table,count(table)==0)
    nullable=rows('SELECT schema_name,table_name,column_name FROM erp_ops.source_import_nullability WHERE was_required')
    check('19 new nullable-field changes logged',set(map(tuple,report['nullable_fields'])).issubset({(r['schema_name'],r['table_name'],r['column_name']) for r in nullable}))
    params={'mode':'live','start':'2026-01-01','end':'2026-12-31','currency':'ALL','tz':'Asia/Shanghai','limit':'200'}
    def api(path,extra=None):
        with urlopen(a.url+'/api/'+path+'?'+urlencode({**params,**(extra or {})}),timeout=30) as response:return json.loads(response.read())
    meta=api('meta');expected_views={'导入产品库存与报价':4,'导入物料库存与单价':15,'导入BOM与物料对应':35,'导入生产计划':4,'导入物料需求':15,'导入其他物品':2,'导入资产快照':5}
    available={o['name'] for o in meta['objects'] if o['schema']=='erp_ops'}
    check('all seven workbook projections available in UI',set(expected_views).issubset(available))
    values={}
    for name,n in expected_views.items():
        listing=api('explore',{'object':'erp_ops.'+name});check(name+' HTTP count',listing['total'][0]['count']==n);values[name]=listing['rows']
    products={v['PID']:v for v in values['导入产品库存与报价']}
    check('product quantities preserved as undated snapshots',{k:v['原表库存'] for k,v in products.items()}=={'P001':'83','P002':'114','P003':'5','P004':'9'} and all(v['盘点日期'] is None for v in products.values()))
    check('incomplete product costs remain NULL',products['P003']['独立算得原料成本'] is None and products['P004']['独立算得原料成本'] is None)
    check('two complete BOM material-cost sums tie to source',Decimal(products['P001']['独立算得原料成本'])==Decimal('11.84') and Decimal(products['P002']['独立算得原料成本'])==Decimal('6.38'))
    materials={v['MID']:v for v in values['导入物料库存与单价']}
    check('explicit zero inventory preserved',materials['M010']['原表库存']=='0' and materials['M011']['原表库存']=='0')
    check('source price precision preserved',materials['M008']['原表采购单价']=='1.1200000000000001')
    plans={v['PID']:v for v in values['导入生产计划']}
    check('plans retain zero, 50 and 30 without actual production',{k:v['计划生产合计'] for k,v in plans.items()}=={'P001':'0','P002':'0','P003':'50','P004':'30'})
    check('incomplete full material demand stays NULL',all(v['完整需求'] is None and v['完整建议采购量'] is None and v['未对应BOM行数']==17 for v in values['导入物料需求']))
    assets=values['导入资产快照'];check('no asset confirmation or date invented',all(v['已确认金额'] is None and v['基准日期'] is None for v in assets))
    check('missing working capital not changed to zero',next(v for v in assets if v['资产项目']=='流动资金')['原表数值'] is None)
    for kind,n in [('funds',1698),('orders',192)]:check('prior '+kind+' still visible over HTTP',api('list',{'kind':kind})['total'][0]['count']==n)
    health=api('health');check('formal frontend remains healthy',health['ok'] and health['status'][0]['database']=='easyerp_v02')
    e.sql((a.project_root/'tests/structure.sql').read_text(encoding='utf-8'));check('structure and all validated constraints pass',True)
    saved={'passed':all(c['passed'] for c in checks),'checks':checks,'source_check_count':len(report['checks']),'source_sha256':book['sha256'],'raw_rows':len(actual),'formula_records':preserved_formulas,'missing_bom':missing}
    a.report.with_name('verification.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':saved['passed'],'checks':len(checks),'source_checks':len(report['checks']),'missing_bom':missing},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
