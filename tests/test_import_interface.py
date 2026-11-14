"""Import interface acceptance: real samples, denied layouts, persistence, HTTP controls."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
import argparse
import hashlib
import io
import json
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

p=argparse.ArgumentParser()
p.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[1])
p.add_argument('--url',default='http://127.0.0.1:8094')
p.add_argument('--sample-root',type=Path,default=Path(r'D:\projx\demo\easyerp-old2'))
args=p.parse_args()
ROOT=args.project_root
sys.path.insert(0,str(ROOT/'app'))
from imports import Imports, ImportError as FormatError, MAX_FILE
passed=[]
def check(label,condition):
 if not condition:raise AssertionError(label)
 passed.append(label)

def changed_book(raw,part,transform):
 output=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(raw)) as source,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as dest:
  for name in source.namelist():
   value=source.read(name)
   if name==part:value=transform(value)
   dest.writestr(name,value)
 return output.getvalue()

def header_change(content):
 root=ET.fromstring(content)
 first=root.find('.//{*}t')
 first.text='未登记的新字段'
 return ET.tostring(root,encoding='utf-8')

def call(path,payload=None,raw=None,params=None,headers=None,method=None,expected=200):
 options={'Content-Type':'application/octet-stream' if raw is not None else 'application/json','X-EasyERP-Token':token,**(headers or {})}
 data=raw if raw is not None else json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
 req=Request(args.url+'/api/import/'+path+'?'+urlencode({'mode':'demo',**(params or {})}),data=data,headers=options,method=method)
 try:
  with urlopen(req,timeout=30) as response:code=response.status;body=json.load(response)
 except HTTPError as err:code=err.code;body=json.load(err)
 check(f'HTTP {path} {expected}',code==expected)
 return body

manifest=json.loads((ROOT/'reports/import-sample-manifest.json').read_text(encoding='utf-8'))
sales=args.sample_root/'sales/ExportOrderList-2026-Q3.xlsx';sales_raw=sales.read_bytes()
sample_results=[]
with tempfile.TemporaryDirectory(prefix='easyerp-import-test-') as temp:
 svc=Imports(temp,ROOT/'app/import_formats.json')
 check('six registered types / seven explicit profiles',len(svc.types)==6 and sum(len(t['profiles']) for t in svc.types.values())==7)
 check('standard CSV execution available in catalog',svc.metadata()['execution_available'] is True)
 for item in manifest['files']:
  source=args.sample_root/item['path'];raw=source.read_bytes()
  check('sample source unchanged: '+item['path'],hashlib.sha256(raw).hexdigest()==item['sha256'])
  r=svc.check(source.name,raw,'demo')
  check('sample recognition: '+item['path'],(r['match'] or {}).get('type_id')==item['type_id'])
  check('no sample can execute',r['can_execute'] is False)
  sample_results.append({'path':item['path'],'status':r['status'],'type_id':(r['match'] or {}).get('type_id'),'label':r['label']})
 check('35 known and 1 unsupported explanatory text',sum(bool(r['type_id']) for r in sample_results)==35 and len(sample_results)==36)
 r=svc.check('renamed-new-month.xlsx',sales_raw)
 check('recognition independent of filename',r['format_eligible'])
 r=svc.check(sales.name,b'new,unseen\na,b\n')
 check('familiar filename does not authorize different content',r['status']=='invalid' and not r['format_eligible'])
 original=svc.check(sales.name,sales_raw)
 row=next(t for t in svc.metadata()['types'] if t['id']=='sales-orders')
 svc.configure({'type_id':row['id'],'enabled':False,'version':row['version']})
 check('disabled type rejects recognized file',not svc.check(sales.name,sales_raw)['format_eligible'])
 old=next(r for r in svc.history('live')['rows'] if r['id']==original['id'])
 check('history re-evaluates current disable status',old['enabled_at_check'] and not old['currently_enabled'] and not old['format_eligible'])
 restart=Imports(temp,ROOT/'app/import_formats.json')
 check('disabled setting survives new service instance',not next(t for t in restart.metadata()['types'] if t['id']==row['id'])['enabled'])
 check('type setting shared across modes',not restart.check(sales.name,sales_raw,'demo')['format_eligible'])
 try:svc.configure({'type_id':row['id'],'enabled':True,'version':0});check('stale version rejected',False)
 except FormatError as error:check('stale version rejected',error.status==409)
 def restore(_):
  try:svc.configure({'type_id':row['id'],'enabled':True,'version':1});return 200
  except FormatError as error:return error.status
 with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(restore,range(2)))
 check('concurrent setting changes serialize',sorted(outcomes)==[200,409])
 check('restored type accepts both versions',svc.check(sales.name,sales_raw)['format_eligible'] and svc.check('older.xlsx',(args.sample_root/'sales/ExportOrderList-2026-Q2.xlsx').read_bytes())['format_eligible'])
 check('settings events persist without deleting checks',len(svc.events()['rows'])==2 and svc.history('demo')['total']>=36)
 for bad in [{'type_id':'new-type','enabled':True,'version':0},{'type_id':'sales-orders','enabled':'false','version':2},{'type_id':'sales-orders','enabled':True,'version':2,'columns':[]},{'type_id':[],'enabled':True,'version':2}]:
  try:svc.configure(bad);check('cannot self-register unknown format',False)
  except FormatError:check('invalid type management rejected',True)
 # Change actual inline header, worksheet name, header order, and add a new sheet.
 raw=changed_book(sales_raw,'xl/worksheets/sheet1.xml',header_change)
 check('changed header rejected',svc.check(sales.name,raw)['status']=='unknown')
 raw=changed_book(sales_raw,'xl/workbook.xml',lambda b:b.replace(b'name="export"',b'name="new-sheet"'))
 check('unreviewed sheet name rejected',svc.check(sales.name,raw)['status']=='unknown')
 def duplicate_sheet(b):
  x=ET.fromstring(b);s=x.find('{*}sheets');child=ET.fromstring(ET.tostring(s[0]));child.set('name','extra');s.append(child);return ET.tostring(x)
 raw=changed_book(sales_raw,'xl/workbook.xml',duplicate_sheet)
 check('extra worksheet not silently ignored',svc.check(sales.name,raw)['status']=='unknown')
 def extra_column(b):
  x=ET.fromstring(b);row=x.findall('.//{*}row')[1];ns=row.tag.split('}')[0]+'}';c=ET.SubElement(row,ns+'c',{'r':'AD2','t':'inlineStr'});ET.SubElement(ET.SubElement(c,ns+'is'),ns+'t').text='new';return ET.tostring(x)
 raw=changed_book(sales_raw,'xl/worksheets/sheet1.xml',extra_column)
 check('extra body column not silently ignored',svc.check(sales.name,raw)['status']=='unknown')
 deposit=next(args.sample_root.joinpath('finance/保证金流水2026').glob('*.csv')).read_bytes().decode('utf-8-sig')
 head,rest=deposit.split('\n',1);cols=head.rstrip('\r').split(',');cols[0],cols[1]=cols[1],cols[0]
 check('column reorder requires explicit new profile',svc.check('reordered.csv',(','.join(cols)+'\n'+rest).encode())['status']=='unknown')
 check('extra header requires explicit new profile',svc.check('extra.csv',(head+',新增列\n'+rest).encode())['status']=='unknown')
 check('wrong delimiter remains unsupported',svc.check('tabbed.csv',deposit.replace(',','\t').encode())['status']=='unknown')
 check('UTF8 transcoding preserves known CSV',svc.check('utf8.csv',deposit.encode('utf-8-sig'))['format_eligible'])
 check('malformed CSV safely recorded',svc.check('bad.csv',b'a,"unterminated')['status']=='invalid')
 for name,raw,status in [('empty.csv',b'',400),('../escape.csv',b'a,b',400),('unknown.xls',b'a,b',415),('large.csv',b'x'*(MAX_FILE+1),413)]:
  try:svc.check(name,raw);check('bad upload rejected',False)
  except FormatError as error:check('bad upload rejected: '+name,error.status==status)
 with svc.connect() as db:
  stored='\n'.join(r[0] for r in db.execute('SELECT result FROM checks'))
 check('no sales data rows stored in check history','5127801157177250623' not in stored)
 check('file SHA256 retained',original['sha256']==hashlib.sha256(sales_raw).hexdigest())
 check('history pagination bounded',len(svc.history('demo')['rows'])==20 and svc.history('demo',20)['offset']==20)
 svc.catalog['version']='next-version'
 check('updated registration rules require recheck',svc.current(original)['requires_recheck'] and not svc.current(original)['format_eligible'])

token=''
meta=call('meta');token=meta['token']
check('HTTP standard execution contract',meta['execution_available'] is True and any(t.get('immutable') and t['id']=='standard-master' for t in meta['types']))
for item in manifest['files']:
 source=args.sample_root/item['path'];r=call('check',raw=source.read_bytes(),params={'filename':source.name})
 check('HTTP sample result '+item['path'],(r['match'] or {}).get('type_id')==item['type_id'] and not r['can_execute'])
call('check',raw=sales_raw,params={'filename':sales.name},headers={'X-EasyERP-Token':''},expected=403)
call('settings',payload={'type_id':'sales-orders','enabled':False,'version':0},headers={'Origin':'http://foreign.invalid'},expected=403)
call('check',raw=sales_raw,params={'filename':sales.name},headers={'Host':'foreign.invalid:8094'},expected=403)
call('check',raw=sales_raw,params={'filename':sales.name},headers={'Content-Type':'text/plain'},expected=415)
call('check',raw=sales_raw,params={'filename':sales.name,'mode':'invalid'},expected=400)
call('settings',payload={'type_id':'new-format','enabled':True,'version':0},expected=404)
call('settings',payload={'type_id':'sales-orders','enabled':'yes','version':0},expected=400)
call('execute',payload={},expected=415)
checked_sales=call('check',raw=sales_raw,params={'filename':sales.name})
call('execute',raw=sales_raw,params={'filename':sales.name,'check_id':checked_sales['id']},expected=415)
call('settings',payload={},method='DELETE',expected=405)
call('history',params={'offset':-1},expected=400)
meta=call('meta');row=next(t for t in meta['types'] if t['id']=='sales-orders')
try:
 updated=call('settings',payload={'type_id':row['id'],'enabled':False,'version':row['version']})
 r=call('check',raw=sales_raw,params={'filename':sales.name})
 check('HTTP disabled state applied',not r['format_eligible'] and '已停用' in r['label'])
 h=call('history');check('HTTP history reflects disable',not next(r for r in h['rows'] if r['match'] and r['match']['type_id']==row['id'])['currently_enabled'])
 call('settings',payload={'type_id':row['id'],'enabled':True,'version':row['version']},expected=409)
finally:
 current=next(t for t in call('meta')['types'] if t['id']==row['id'])
 if current['enabled']!=row['enabled']:call('settings',payload={'type_id':row['id'],'enabled':row['enabled'],'version':current['version']})
call('events')
check('all source hashes unchanged after tests',all(hashlib.sha256((args.sample_root/f['path']).read_bytes()).hexdigest()==f['sha256'] for f in manifest['files']))
report={'status':'PASS','checks':len(passed),'passed':passed,'sample_results':sample_results,'business_sql_writes':False}
(ROOT/'reports/import-interface-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','checks':len(passed),'samples':len(sample_results)},ensure_ascii=False))
