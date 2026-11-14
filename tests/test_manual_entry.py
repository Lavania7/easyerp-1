"""Real HTTP/SQL manual-entry tests. Synthetic rows are confined to the demo DB."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8092')
parser.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[1])
args=parser.parse_args()
ROOT=args.project_root
sys.path.insert(0,str(ROOT/'tools'))
from easyerp import ERP, literal as L, ident as I
e=ERP();demo=e.c['database']+'_ui_demo'
run='qa_'+uuid.uuid4().hex[:14]
created=[];passed=[];counter=0;token=''


def check(label,condition):
    if not condition:raise AssertionError(label)
    passed.append(label)


def call(path,params=None,payload=None,headers=None,method=None,expected=200):
    qs=urlencode({'mode':'demo',**(params or {})})
    data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode('utf-8')
    request=Request(args.url+'/api/'+path+'?'+qs,data=data,method=method,
                    headers={'Content-Type':'application/json','X-EasyERP-Token':token,**(headers or {})})
    try:
        with urlopen(request,timeout=20) as response:code=response.status;body=json.load(response)
    except HTTPError as error:
        code=error.code;body=json.load(error)
    if code!=expected:raise AssertionError(f'{path}: expected {expected}, got {code}: {body}')
    return body


def save(key,values,children=None,**extra):
    global counter
    counter+=1
    payload={'object':key,'values':values,'request_id':f'{run}_{counter}',**extra}
    if children is not None:payload['children']=children
    result=call('entry/save',payload=payload)
    for row in result['records']:
        item=(row['object'],row['id'])
        if item not in created:created.append(item)
    return result,payload


def signature(db):
    tables=e.sql("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1",db=db).stdout.splitlines()
    queries=[]
    for table in tables:
        schema,name=table.split('.',1)
        queries.append(f"SELECT {L(table)} AS object,count(*) n,md5(coalesce(string_agg(row_to_json(t)::text,E'\\n' ORDER BY row_to_json(t)::text),'')) signature FROM {I(schema)}.{I(name)} t")
    raw=e.sql("SELECT json_agg(t) FROM ("+' UNION ALL '.join(queries)+")t",db=db).stdout
    ordered=sorted(json.loads(raw),key=lambda row:row['object'])
    return hashlib.sha256(json.dumps(ordered,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


before=signature(e.c['database'])
metadata=call('entry/meta');token=metadata['token'];objects={o['key']:o for o in metadata['objects']}
check('all 146 business tables have entry metadata',len(objects)==146)
check('all existing modules have common entry choices',set(metadata['preferred'])=={'sales','inventory','production','finance','rd','legal','analysis'})
check('views and operational tables are excluded',all(o['schema'] in ('sales','production','finance','rd','legal','analysis') for o in objects.values()))
check('status choices come from SQL constraints',next(c for c in objects['sales.销售订单登记表']['columns'] if c['name']=='状态')['options']==['待确认','已确认','已关闭','已取消'])
pk={key:o['pk'] for key,o in objects.items()}
try:
    customer,_=save('sales.客户档案表',{'客户ID':run+'_customer','客户来源标识':run,'客户名称':"演示验收 ' \\! <img src=x onerror=alert(1)>"})
    check('Chinese quotes and injection-looking text are stored as data',customer['records'][0]['values']['客户名称'].startswith('演示验收'))
    unit=call('entry/options',{'object':'sales.销售订单行表','field':'单位ID','q':'unit'})
    check('foreign key picker returns readable authoritative choices',any(r['value']=='unit' for r in unit['rows']))
    order_values={'订单ID':run+'_order','渠道ID':'channel','平台订单号':run,'客户ID':run+'_customer','创建时间':'2026-10-22T10:00:00+02:00','币种':'CNY','状态':'待确认'}
    line={'行号':'1','原商品信息':'手工录入测试商品','产品版本ID':'pv','数量':'2.500000','单位ID':'unit','单价':'10.0000','折扣金额':'0','商品实付':'25','运费分摊':'0','收货信息':'独立演示收货信息','取消数量':'0','状态':'待履约'}
    order,order_payload=save('sales.销售订单登记表',order_values,[{'object':'sales.销售订单行表','values':{**line,'销售订单行ID':run+'_line'}}])
    check('order and its line commit together',len(order['records'])==2 and order['records'][1]['values']['订单ID']==run+'_order')
    replay=call('entry/save',payload=order_payload)
    check('identical repeated save does not duplicate rows',replay['records'][0]['id']==run+'_order' and e.sql(f"SELECT count(*) FROM erp_ops.frontend_entry_audit WHERE request_id={L(order_payload['request_id'])}",db=demo).stdout.strip()=='1')
    call('entry/save',payload={**order_payload,'values':{**order_values,'平台订单号':run+'_changed'}},expected=409)
    check('request ID cannot be reused with different contents',True)
    detail=call('detail',{'kind':'order','id':run+'_order','start':'2026-10-01','end':'2026-10-22'})
    check('new order is visible through the existing frontend view',detail['lines'][0]['商品实付']=='25.0000' and detail['lines'][0]['数量']=='2.500000')
    count=e.sql(f'SELECT count(*) FROM sales."销售订单行表" WHERE "订单ID"={L(run+"_order")}',db=demo).stdout.strip()
    check('same order is present in backend SQL',count=='1')
    broken={**order_values,'订单ID':run+'_rollback','平台订单号':run+'_rollback'}
    call('entry/save',payload={'request_id':run+'_rollback','object':'sales.销售订单登记表','values':broken,'children':[{'object':'sales.销售订单行表','values':{**line,'产品版本ID':'missing_version'}}]},expected=400)
    check('a bad child rolls back the entire order',e.sql(f'SELECT count(*) FROM sales."销售订单登记表" WHERE "订单ID"={L(run+"_rollback")}',db=demo).stdout.strip()=='0')
    check('a rolled back save leaves no success audit',e.sql(f'SELECT count(*) FROM erp_ops.frontend_entry_audit WHERE request_id={L(run+"_rollback")}',db=demo).stdout.strip()=='0')
    call('entry/save',payload={'request_id':run+'_missing','object':'sales.客户档案表','values':{}},expected=400)
    call('entry/save',payload={'request_id':run+'_scale','object':'sales.销售订单行表','values':{**line,'订单ID':run+'_order','数量':'0.0000001'}},expected=400)
    call('entry/save',payload={'request_id':run+'_negative','object':'sales.销售订单行表','values':{**line,'订单ID':run+'_order','行号':'2','数量':'-1'}},expected=400)
    call('entry/save',payload={'request_id':run+'_unknown','object':'sales.客户档案表','values':{'客户来源标识':'test','unknown':'x'}},expected=400)
    call('entry/save',payload={'request_id':run+'_view','object':'sales.订单与履约交付表','values':{}},expected=400)
    check('required fields, scale, quantity, unknown fields and views are validated',True)
    current=call('entry/record',{'object':'sales.客户档案表','id':run+'_customer'})
    updated,_=save('sales.客户档案表',{'客户名称':'已更正的演示客户'},operation='update',id=run+'_customer',version=current['version'])
    check('manual correction updates the authoritative record',updated['records'][0]['values']['客户名称']=='已更正的演示客户')
    call('entry/save',payload={'request_id':run+'_conflict','object':'sales.客户档案表','operation':'update','id':run+'_customer','version':current['version'],'values':{'客户名称':'过时内容'}},expected=409)
    check('stale forms cannot overwrite a newer record',True)
    current=call('entry/record',{'object':'sales.客户档案表','id':run+'_customer'})
    e.sql(f'UPDATE sales."客户档案表" SET "产业分类"=\'SQL 侧更正\' WHERE "客户ID"={L(run+"_customer")}',db=demo)
    call('entry/save',payload={'request_id':run+'_sqlconflict','object':'sales.客户档案表','operation':'update','id':run+'_customer','version':current['version'],'values':{'客户名称':'再次过时'}},expected=409)
    check('SQL-side edits are detected before frontend overwrite',call('entry/record',{'object':'sales.客户档案表','id':run+'_customer'})['values']['产业分类']=='SQL 侧更正')
    cash,_=save('finance.资金流水表',{'资金记录ID':run+'_cash','账户ID':'account','发生时间':'2026-10-22T10:00:00+02:00','金额':'9007199254740993.1234','收支方向':'收入','交易摘要':'精确数值演示验收'})
    check('large financial decimals retain all digits',cash['records'][0]['values']['金额']=='9007199254740993.1234')
    purpose,_=save('finance.资金用途核定表',{'用途核定ID':run+'_purpose','资金记录ID':run+'_cash','状态':'待核定','核定金额':None})
    check('unknown optional amounts remain NULL',purpose['records'][0]['values']['核定金额'] is None)
    fund=call('detail',{'kind':'fund','id':run+'_cash'})
    check('manual funds appear in standard SQL-backed detail',fund['basic'][0]['金额']=='9007199254740993.1234' and fund['basic'][0]['已核定分摊金额'] is None)
    po,_=save('production.采购订单表',{'采购单ID':run+'_po','供应商ID':'supplier','创建日期':'2026-10-22','状态':'草稿','币种':'CNY'},[{'object':'production.采购订单行表','values':{'采购订单行ID':run+'_pol','行号':'1','数量':'3','单位ID':'unit','单价':'5.1234','取消数量':'0','产品版本ID':'pv'}}])
    check('purchase header and item commit atomically',len(po['records'])==2 and po['records'][1]['values']['采购单ID']==run+'_po')
    arrival,_=save('production.到货记录表',{'到货ID':run+'_arrival','采购订单行ID':run+'_pol','到货时间':'2026-10-22T11:00:00+02:00','数量':'1','单位ID':'unit'})
    check('inventory module supports manual arrival records',arrival['records'][0]['values']['数量']=='1.000000')
    work,_=save('production.生产工单表',{'工单号':run+'_work','发布批次ID':'release','计划数量':'2','单位ID':'unit','计划开始日期':'2026-10-22','下达依据':'演示库隔离验收','状态':'已下达','取消数量':'0'})
    work_view=call('detail',{'kind':'workorder','id':run+'_work'})
    check('work order entry does not invent actual completion',work_view['basic'][0]['截至合格数量'] is None)
    project,_=save('rd.项目登记表',{'项目ID':run+'_project','项目名称':'手工录入研发演示','确认依据':'隔离验收'})
    check('R&D module writes its authoritative project table',project['records'][0]['values']['开始日期'] is None)
    material,_=save('rd.物料主数据表',{'MID':run+'_mid','名称':'BOM 演示物料','规格':'隔离验收','单位ID':'unit','类别':'物料'})
    material_version,_=save('rd.物料版本表',{'物料版本ID':run+'_mv','MID':run+'_mid','版本名称':'1','确认依据':'隔离验收'})
    source_file,_=save('rd.项目文件登记表',{'文件ID':run+'_file','项目ID':run+'_project','文件类型':'BOM','文件名':'演示记录','相对路径':'demo-only','SHA256':'0'*64,'正式版本':'1'})
    bom,_=save('rd.BOM登记表',{'BOM登记ID':run+'_bom','产品版本ID':'pv','BOM版本':run,'确认依据':'隔离验收'},[{'object':'rd.BOM明细表','values':{'BOM明细ID':run+'_bomline','行号':'1','物料版本ID':run+'_mv','单件用量':'0.125000','单位ID':'unit','来源文件ID':run+'_file','确认依据':'隔离验收'}}])
    check('BOM header and material line commit together',len(bom['records'])==2 and bom['records'][1]['values']['BOM登记ID']==run+'_bom')
    voucher_values={'凭证ID':run+'_voucher','主体ID':'co','凭证日期':'2026-10-22','所属月份':'2026-10-01','凭证号':run,'摘要':'隔离验收','状态':'草稿','政策ID':'policy'}
    entries=[{'object':'finance.会计分录表','values':{'分录ID':run+'_debit','行号':'1','科目ID':'debit','借方金额':'10.1234','贷方金额':'0','币种':'CNY'}},{'object':'finance.会计分录表','values':{'分录ID':run+'_credit','行号':'2','科目ID':'credit','借方金额':'0','贷方金额':'10.1234','币种':'CNY'}}]
    voucher,_=save('finance.会计凭证表',voucher_values,entries)
    check('voucher and both accounting entries save atomically',len(voucher['records'])==3 and all(r['values']['凭证ID']==run+'_voucher' for r in voucher['records'][1:]))
    bad_entries=[{**entries[0],'values':{**entries[0]['values'],'分录ID':run+'_baddebit'}},{**entries[1],'values':{**entries[1]['values'],'分录ID':run+'_badcredit','贷方金额':'9'}}]
    call('entry/save',payload={'request_id':run+'_badposted','object':'finance.会计凭证表','values':{**voucher_values,'凭证ID':run+'_badposted','凭证号':run+'_badposted','状态':'已过账'},'children':bad_entries},expected=400)
    check('unbalanced posting is rejected by existing SQL guards',e.sql(f'SELECT count(*) FROM finance."会计凭证表" WHERE "凭证ID"={L(run+"_badposted")}',db=demo).stdout.strip()=='0')
    company,_=save('legal.公司主体档案表',{'主体ID':run+'_company','公司名称':'手工录入法务演示','统一社会信用代码':run,'注册地址':'独立演示地址','有效状态':'有效'})
    check('legal module supports authoritative master records',company['records'][0]['values']['公司名称']=='手工录入法务演示')
    report,_=save('analysis.分析报告登记表',{'报告ID':run+'_report','分析问题':'手工录入分析演示','生成日期':'2026-10-22'})
    check('analysis module keeps unknown conclusions blank',report['records'][0]['values']['关键结论'] is None)
    model,_=save('analysis.数学模型库',{'模型ID':run+'_model','模型名称':run,'版本':'1','用途':'隔离验收','输入定义':'示例','方法':'人工登记','参数':'{"large":9007199254740993.1234}','适用条件':'仅独立演示验收'})
    check('JSON input is validated and exact values preserved',str(model['records'][0]['values']['参数']['large'])=='9007199254740993.1234')
    model_record=call('entry/record',{'object':'analysis.数学模型库','id':run+'_model'})
    exact_json=model_record['values']['参数']
    check('JSON editor receives exact JSON text with numeric types',json.loads(exact_json,parse_float=Decimal)['large']==Decimal('9007199254740993.1234'))
    save('analysis.数学模型库',{'参数':exact_json[:-1]+',"extra":2}'},operation='update',id=run+'_model',version=model_record['version'])
    check('editing JSON retains the original numeric type and digits',e.sql(f'SELECT jsonb_typeof("参数"->\'large\')||\'|\'||("参数"->\'large\')::text FROM analysis."数学模型库" WHERE "模型ID"={L(run+"_model")}',db=demo).stdout.strip()=='number|9007199254740993.1234')
    save('analysis.指标定义表',{'指标ID':run+'_metric','指标名称':run,'版本':'1','公式':'人工输入','单位':'件','适用条件':'隔离验收'})
    save('analysis.数据引用登记表',{'数据集ID':run+'_dataset','数据集名称':run,'版本':'1','期间开始':'2026-10-01','期间结束':'2026-10-22','数据截止时间':'2026-10-22T10:00:00Z','生成时间':'2026-10-22T10:00:00Z'})
    calculation,_=save('analysis.指标计算表',{'计算记录ID':run+'_calc','指标ID':run+'_metric','数据集ID':run+'_dataset','期间开始':'2026-10-01','期间结束':'2026-10-22','计算时间':'2026-10-22T10:00:00Z','结果值':'9007199254740993','状态':'待复核'})
    calculated=call('entry/record',{'object':'analysis.指标计算表','id':run+'_calc'})
    explored=call('explore',{'object':'analysis.指标计算表','search':run+'_calc'})
    check('scale-free NUMERIC integers stay exact in save, editor and list',calculation['records'][0]['values']['结果值']==calculated['values']['结果值']==explored['rows'][0]['结果值']=='9007199254740993')
    simultaneous={'request_id':run+'_parallel','object':'sales.客户档案表','values':{'客户来源标识':run+'_parallel'}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent=list(pool.map(lambda _:call('entry/save',payload=simultaneous),range(2)))
    for row in concurrent[0]['records']:created.append((row['object'],row['id']))
    check('simultaneous retries create exactly one record',concurrent[0]['records'][0]['id']==concurrent[1]['records'][0]['id'])
    for headers in [{'X-EasyERP-Token':''},{'Origin':'https://example.invalid'},{'Sec-Fetch-Site':'cross-site'}]:
        call('entry/save',payload=order_payload,headers=headers,expected=403)
    call('entry/save',payload=order_payload,params={'mode':'wrong'},expected=400)
    call('entry/save',payload=order_payload,headers={'Content-Type':'text/plain'},expected=415)
    call('entry/save',payload=order_payload,method='DELETE',expected=405)
    check('write token, origin, source and method boundaries enforced',True)
    role=e.sql(f'SELECT database_role FROM erp_ops.frontend_entry_audit WHERE request_id={L(order_payload["request_id"])}',db=demo).stdout.strip()
    check('business saves use the existing app role',role=='easyerp_app')
    check('query requests retain the read-only role',call('health')['status'][0]['role']=='easyerp_read')
    privileges=e.sql("SELECT has_table_privilege('easyerp_app','erp_ops.frontend_entry_audit','SELECT') AND has_table_privilege('easyerp_app','erp_ops.frontend_entry_audit','INSERT') AND NOT has_table_privilege('easyerp_app','erp_ops.frontend_entry_audit','UPDATE') AND NOT has_table_privilege('easyerp_app','erp_ops.frontend_entry_audit','DELETE') AND has_table_privilege('easyerp_read','erp_ops.frontend_entry_audit','SELECT') AND NOT has_table_privilege('easyerp_read','erp_ops.frontend_entry_audit','INSERT')",db=demo).stdout.strip()
    check('audit permissions match the explicitly approved scope',privileges=='t')
    posted=call('entry/record',{'object':'finance.会计凭证表','id':'voucher'})
    call('entry/save',payload={'request_id':run+'_postedguard','object':'finance.会计凭证表','operation':'update','id':'voucher','version':posted['version'],'values':{'摘要':'不应保存的测试更正'}},expected=400)
    check('frontend cannot bypass posted-voucher SQL protection',call('entry/record',{'object':'finance.会计凭证表','id':'voucher'})['values']==posted['values'])
finally:
    if created:
        cleanup=[]
        for key,row_id in reversed(created):
            schema,table=key.split('.',1)
            cleanup.append(f'DELETE FROM {I(schema)}.{I(table)} WHERE {I(pk[key])}={L(row_id)};')
        cleanup.append(f'DELETE FROM erp_ops.frontend_entry_audit WHERE left(request_id,{len(run)})={L(run)};')
        e.sql('BEGIN;\n'+'\n'.join(cleanup)+'\nCOMMIT;',db=demo)
    after=signature(e.c['database'])
    if after!=before:raise AssertionError('Formal business records changed')
check('formal business data signature unchanged',after==before)
result={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','checks':len(passed),'passed':passed,'test_rows_removed':True,'formal_signature_before':before,'formal_signature_after':after}
out=Path(__file__).resolve().parents[1]/'reports/manual-entry-tests.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
