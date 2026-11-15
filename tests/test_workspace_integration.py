"""HTTP and SQL checks; all synthetic business rows stay in the demo database."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import json
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from easyerp import ERP,literal as L
sys.path.insert(0,str(ROOT/'app'))
from workspace import Workspace

BASE='http://127.0.0.1:8092'
erp=ERP();demo=erp.c['database']+'_ui_demo';run='qa_ws_'+uuid.uuid4().hex[:10]
token='';passed=[]

def call(path,body=None,mode='demo',status=200):
    request=Request(BASE+path+('&' if '?' in path else '?')+'mode='+mode,
      data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),
      headers={'Content-Type':'application/json','X-EasyERP-Token':token})
    try:
        with urlopen(request,timeout=30) as response: actual=response.status;result=json.load(response)
    except HTTPError as error:actual=error.code;result=json.load(error)
    assert actual==status,(path,actual,result)
    return result

def save(key,values,**kw):
    return call('/api/entry/save',{'request_id':run+'_'+uuid.uuid4().hex,'object':key,'values':values,**kw})

before=erp.data_signature(erp.c['database']);ids=[];file_ids=[]
try:
    metadata=call('/api/entry/meta');token=metadata['token'];objects={x['key']:x for x in metadata['objects']}
    assert objects['production.生产工时表']['retired']
    assert objects['finance.会计政策表']['area']=='archive'
    assert objects['finance.资金用途核定表']['area']=='audit'
    passed.append('Catalog ownership and retired flags')
    templates=call('/api/templates/meta');assert all(not objects[x['key']]['retired'] and objects[x['key']]['standalone'] for x in templates['objects'])
    call('/api/entry/save',{'request_id':run+'_retired','object':'production.生产工时表','values':{}},status=400)
    passed.append('Retired entry and template boundaries')
    # Pick only actual demo reference IDs. No business relation is guessed by name.
    def first(key):
        obj=objects[key];rows=call('/api/explore?object='+__import__('urllib.parse',fromlist=['quote']).quote(key)+'&date_filter=0&limit=1')['rows'];assert rows,key;return rows[0][obj['pk']]
    supplier=first('production.供应商档案表')
    unit=run+'_unit';mid=run+'_mid';material=run+'_material'
    save('rd.计量单位表',{'单位ID':unit,'单位名称':'验收单位','备注':'隔离验收'})
    ids.insert(0,('rd.计量单位表','单位ID',unit))
    save('rd.物料主数据表',{'MID':mid,'名称':'隔离验收物料','规格':'仅用于测试','单位ID':unit,'类别':'验收样例'})
    ids.insert(0,('rd.物料主数据表','MID',mid))
    save('rd.物料版本表',{'物料版本ID':material,'MID':mid,'版本名称':'验收版','确认依据':'仅隔离验收'})
    ids.insert(0,('rd.物料版本表','物料版本ID',material))
    purchase=run+'_purchase';line=run+'_line'
    result=save('production.采购订单表',{'采购单ID':purchase,'供应商ID':supplier,'创建日期':'2026-11-14','状态':'草稿','币种':'CNY'},children=[{'object':'production.采购订单行表','values':{'采购订单行ID':line,'行号':'1','数量':'2.000001','单位ID':unit,'单价':'9007199254740993.1234','取消数量':'0','物料版本ID':material}}])
    ids[0:0]=[('production.采购订单行表','采购订单行ID',line),('production.采购订单表','采购单ID',purchase)]
    record=call('/api/entry/record?object=production.%E9%87%87%E8%B4%AD%E8%AE%A2%E5%8D%95%E8%A1%A8&id='+purchase)
    child=record['children'][0];assert child['values']['单价']=='9007199254740993.1234'
    result=save('production.采购订单表',{},operation='update',id=purchase,version=record['version'],children=[{'object':child['object'],'operation':'update','id':line,'version':child['version'],'values':{'数量':'3.123456'}}])
    actual=erp.sql(f'SELECT "数量"::text FROM production."采购订单行表" WHERE "采购订单行ID"={L(line)}',db=demo,role='easyerp_read').stdout.strip();assert actual=='3.123456'
    record=call('/api/entry/record?object=production.%E9%87%87%E8%B4%AD%E8%AE%A2%E5%8D%95%E8%A1%A8&id='+purchase)
    call('/api/entry/save',{'request_id':run+'_rollback','object':'production.采购订单表','operation':'update','id':purchase,'version':record['version'],'values':{'状态':'已下单'},'children':[{'object':child['object'],'operation':'update','id':line,'version':child['version'],'values':{'数量':'5'}}]},status=409)
    actual=erp.sql(f'SELECT "状态" FROM production."采购订单表" WHERE "采购单ID"={L(purchase)}',db=demo,role='easyerp_read').stdout.strip();assert actual=='草稿'
    passed.append('Atomic purchase edit, exact decimals, stale child rollback')
    simple=run+'_simple'
    save('production.采购订单表',{'采购单ID':simple,'供应商ID':supplier,'创建日期':'2026-11-14','状态':'草稿','币种':'CNY','采购说明':'按原订单登记，不要求逐项编码','订单金额':'123.4567','订单文件路径':'验收原单.pdf'})
    ids.insert(0,('production.采购订单表','采购单ID',simple))
    record=call('/api/entry/record?object=production.%E9%87%87%E8%B4%AD%E8%AE%A2%E5%8D%95%E8%A1%A8&id='+simple)
    assert not record['children'] and record['values']['订单金额']=='123.4567'
    rows=call('/api/explore?object=production.%E9%87%87%E8%B4%AD%E8%AE%A2%E5%8D%95%E8%A1%A8&date_filter=0&search='+simple)['rows']
    assert rows[0]['采购内容']=='按原订单登记，不要求逐项编码'
    passed.append('Original-order purchase registration without detailed item coding')
    custody=first('production.保管方档案表');subject=first('legal.公司主体档案表')
    warehouse=run+'_warehouse';location=run+'_location'
    result=save('production.仓库档案表',{'仓库ID':warehouse,'地点':'隔离验收地点','保管方ID':custody,'主体ID':subject,'启用状态':'启用'})
    location=result['records'][1]['id'];assert result['records'][1]['values']['库位代码']=='默认'
    ids[0:0]=[('production.库位档案表','库位ID',location),('production.仓库档案表','仓库ID',warehouse)]
    stock=run+'_stock'
    save('production.库存盘点表',{'盘点ID':stock,'盘点日期':'2026-11-14','库位ID':location,'批次':run,'所有权主体ID':subject,'单位ID':unit,'实盘数量':'90071992547409.123456','账面数量':'90071992547409.000001','依据':'隔离验收','物料版本ID':material})
    ids.insert(0,('production.库存盘点表','盘点ID',stock))
    rows=call('/api/explore?object=production.%E5%BA%93%E5%AD%98%E7%9B%98%E7%82%B9%E8%A1%A8&date_filter=0&search='+run)['rows']
    assert rows[0]['盘点差异']=='0.123455' and rows[0]['期初数量'] is None
    passed.append('Combined warehouse and stock, nullable balances, exact difference')
    item=call('/api/workspace/save',{'request_id':run+'_file','kind':'workflow','values':{'title':run}})['item'];file_ids.append(item['id'])
    retry=call('/api/workspace/save',{'request_id':run+'_file','kind':'workflow','values':{'title':run}})['item'];assert retry==item
    live=call('/api/workspace?kind=workflow&search='+run,mode='live');assert not live['rows']
    call('/api/workspace/save',{'request_id':run+'_conflict','id':item['id'],'version':0,'values':{'title':'conflict'}},status=409)
    passed.append('Protected HTTP file workflow, retry and source isolation')
    print(json.dumps({'passed':passed},ensure_ascii=False,indent=2))
finally:
    for key,pk,value in ids:
        schema,name=key.split('.',1)
        erp.sql(f'DELETE FROM {schema}."{name}" WHERE "{pk}"={L(value)}',db=demo,role='easyerp_admin')
    erp.sql(f'DELETE FROM erp_ops.frontend_entry_audit WHERE left(request_id,{len(run)})={L(run)}',db=demo,role='easyerp_admin')
    ws=Workspace('demo')
    with ws.locked():
        state=ws.read()
        for key in file_ids:state['items'].pop(key,None)
        state['requests']={k:v for k,v in state['requests'].items() if not k.startswith(run)}
        ws.write(state)
    after=erp.data_signature(erp.c['database']);assert before==after,'Formal business data changed'
report={'passed':passed,'formal_business_unchanged':before==after,'test_rows_removed':True}
(ROOT/'reports/workspace-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
