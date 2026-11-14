"""Three identifiers, restored-data migration and concurrency in disposable databases."""
from pathlib import Path
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
import argparse
import csv
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import uuid

parser=argparse.ArgumentParser()
parser.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--source-root',type=Path)
parser.add_argument('--out',type=Path)
args=parser.parse_args()
root=args.project_root.resolve();source=(args.source_root or root).resolve()
sys.path.insert(0,str(root/'tools'))
from easyerp import ERP,literal as L,ident as I
sys.path[:0]=[str(source/'app'),str(root/'app')]
from identifiers import RULES,base36,identity,valid
from entry import ManualEntry,EntryError
from standard_import import StandardImport
from workspace import Workspace
spec=importlib.util.spec_from_file_location('id_migration',source/'tools/migrate_business_ids.py')
migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
erp=ERP();run='id_test_'+uuid.uuid4().hex[:12]
out=(args.out/run) if args.out else root/'reports'/run;out.mkdir(parents=True,exist_ok=True)
passed=[];clones=[]
def check(name,condition=True):
    assert condition,name
    passed.append(name);print('PASS:',name,flush=True)
def rows(sql,db):
    return json.loads(erp.sql("SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM ("+sql+") x;",db=db,role='easyerp_read').stdout)
def signature(db):
    parts=[]
    for key,rule in RULES.items():
        s,n=key.split('.',1)
        parts.append('SELECT '+L(key)+" AS object,count(*) AS n,md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) AS hash FROM "+I(s)+'.'+I(n)+' t')
    return rows(' UNION ALL '.join(parts),db)
def make_entry(db,mode):
    entry=ManualEntry({'mode':mode});entry.db=db;entry.data.db=db;return entry
def save(entry,key,values,request=None,**extra):
    return entry.save({'request_id':request or uuid.uuid4().hex,'object':key,'values':values,**extra})
def csv_bytes(obj,values):
    stream=io.StringIO(newline='');writer=csv.writer(stream)
    writer.writerow([c['name'] for c in obj['columns']]);writer.writerow([values.get(c['name'],'') for c in obj['columns']])
    return stream.getvalue().encode('utf-8-sig')

check('base36 boundaries and long-ID decimal suffix',base36(9)=='009' and base36(10)=='00A' and base36(35)=='00Z' and base36(36)=='010' and identity('PRD','PO','PO00M','2026-11-14')['long_id']=='PRD-PO-20261114-022')
before={mode:signature(erp.c['database']+('_ui_demo' if mode=='demo' else '')) for mode in ('live','demo')}
try:
    for mode in ('live','demo'):
        original=erp.c['database']+('_ui_demo' if mode=='demo' else '')
        backup=erp.backup(original)
        clone='easyerp_ids_test_'+uuid.uuid4().hex[:12];clones.append(clone)
        erp.run('createdb',['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','-T','template0',clone])
        erp.run('pg_restore',['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','--exit-on-error','--single-transaction','-d',clone,backup])
        workspace=out/mode/'workspace';workspace.mkdir(parents=True)
        live_workspace=root/'var/workspace'/(mode+'.json')
        if live_workspace.exists():shutil.copyfile(live_workspace,workspace/(mode+'.json'))
        fk_before=rows("SELECT c.conrelid::regclass::text AS source,c.conname,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE c.contype='f' AND n.nspname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1,2",clone)
        enabled=rows("SELECT to_regclass('erp_ops.business_record_ids') IS NOT NULL AS enabled",clone)[0]['enabled']
        existing_identities=rows('SELECT * FROM erp_ops.business_record_ids',clone) if enabled else []
        result=migration.run(erp,root,clone,mode,out/mode,True,workspace)
        check(mode+' restored-data migration preserves all original records',result['status']=='PASS' and result['canonical_records_unchanged'])
        fk_after=rows("SELECT c.conrelid::regclass::text AS source,c.conname,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE c.contype='f' AND n.nspname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1,2",clone)
        check(mode+' foreign keys and their timing are restored',fk_before==fk_after)
        ids=rows('SELECT * FROM erp_ops.business_record_ids',clone)
        check(mode+' each migrated row has exactly three stable identifiers',len(ids)==result['rows'] and all(valid(r['table_key'],r['short_id']) and sha256(r['long_id'].encode()).hexdigest()==r['sha256'] for r in ids))
        prior={(r['table_key'],r['short_id']):r for r in existing_identities}
        check(mode+' existing identities stay stable and new dates use issuance day',all(r==prior[(r['table_key'],r['short_id'])] if (r['table_key'],r['short_id']) in prior else r['issued_on']==result['issued_on'] for r in ids))
        entry=make_entry(clone,mode)
        if result['mapping']:
            alias=result['mapping'][0]
            check(mode+' old IDs resolve to the current short ID',entry.ids.resolve(alias['object'],alias['old'])==alias['new'])
        if mode=='live':
            unit_ws=Workspace(mode,workspace)
            for item in unit_ws.read()['items'].values():
                check('workspace three IDs are stable and hidden from public results',bool(re.fullmatch(r'PLN[0-9A-Z]{3,}',item['id'])) and sha256(item['long_id'].encode()).hexdigest()==item['sha256'] and 'long_id' not in unit_ws.public_item(item) and 'sha256' not in unit_ws.public_item(item))
            continue
        key='sales.客户档案表';obj=entry.object(key)
        payload={'客户名称':'同名验收客户','客户来源标识':run}
        request=uuid.uuid4().hex
        first=save(entry,key,payload,request)['records'][0]
        retried=save(entry,key,payload,request)['records'][0]
        check('manual create retries reuse the same short ID',first['id']==retried['id'] and valid(key,first['id']))
        second=save(entry,key,payload)['records'][0]
        choices=entry.choices(key,search='同名验收客户')['rows']
        check('duplicate names remain selectable without IDs',len(choices)==2 and len({r['label'] for r in choices})==2 and all(r['value'] not in r['label'] for r in choices))
        identity_before=entry.ids.identity(key,first['id'])[0]
        current=entry.record(key,first['id'])
        save(entry,key,{'客户名称':'更新后的验收客户'},operation='update',id=first['id'],version=current['version'])
        check('long ID and SHA-256 remain unchanged after edits',entry.ids.identity(key,first['id'])[0]==identity_before)
        check('Agent lookup accepts both SHA-256 and long ID',entry.ids.identity(key,identity_before['sha256'])[0]==identity_before and entry.ids.identity(key,identity_before['long_id'])[0]==identity_before)
        try:save(entry,key,{**payload,'客户ID':'ME-unreadable-identifier'})
        except EntryError:check('manual create rejects long legacy IDs for new rows')
        else:raise AssertionError('Legacy new ID accepted')
        # Reserve across 00Z -> 010 under concurrent allocation.
        erp.sql("UPDATE erp_ops.business_id_counters SET last_number=34 WHERE table_key="+L(key),db=clone,role='easyerp_admin')
        check('SQL allocation crosses the alphabet boundary',entry.ids.allocate(key,[run+':z',run+':10'])==['C00Z','C010'])
        def allocate(index):return make_entry(clone,mode).ids.allocate(key,[run+':parallel:'+str(index)])[0]
        with ThreadPoolExecutor(max_workers=6) as pool:allocated=list(pool.map(allocate,range(12)))
        check('concurrent allocation is unique and canonical',len(set(allocated))==12 and all(valid(key,value) for value in allocated))
        importer=StandardImport(mode);importer.entry=entry
        content=csv_bytes(obj,{'客户名称':'CSV验收客户','客户来源标识':run+'_csv'})
        plan=importer.plan(key+'.csv',content);repeat=importer.plan(key+'.csv',content)
        check('CSV blank IDs reserve stable base36 identifiers',not plan['errors'] and plan['rows'][0]['values'][obj['pk']]==repeat['rows'][0]['values'][obj['pk']] and valid(key,plan['rows'][0]['values'][obj['pk']]))
        importer.write(plan,run+'_check',merge='fill_empty',allow_incomplete=True)
        old_csv=csv_bytes(obj,{'客户ID':'customer','客户名称':'历史客户','客户来源标识':'source'})
        old_plan=importer.plan(key+'.csv',old_csv)
        check('legacy CSV IDs map to existing records',old_plan['rows'][0]['values']['客户ID']==entry.ids.resolve(key,'customer'))
        # Use a real related record, including its legacy reference, in one atomic parent/child save.
        po=entry.record('production.采购订单表','po')['values'];po.pop('采购单ID')
        line=entry.record('production.采购订单行表','pol')['values'];line.pop('采购订单行ID');line.pop('采购单ID')
        po['供应商ID']='supplier'
        purchase=save(entry,'production.采购订单表',po,children=[{'object':'production.采购订单行表','values':line}])
        check('parent and child get independent short IDs with intact linkage',len(purchase['records'])==2 and purchase['records'][1]['values']['采购单ID']==purchase['records'][0]['id'])
        options=entry.options('production.采购订单表','供应商ID',selected='supplier')['rows']
        check('reference options show names and resolve legacy values',any(r['value']==entry.ids.resolve('production.供应商档案表','supplier') for r in options) and all(r['value'] not in r['label'] for r in options))
        ws=Workspace('demo',out/'isolated-workspace')
        plan_item=ws.save({'request_id':uuid.uuid4().hex,'kind':'plan','values':{'title':'计划验收','department':'production'}})['item']
        check('workspace exposes only the short ID to its UI',plan_item['id']=='PLN001' and 'long_id' not in plan_item and 'sha256' not in plan_item)
        saved=ws.read()['items'][plan_item['id']]
        check('workspace Agent lookup resolves SHA-256',ws.identity(saved['sha256'])[0]['short_id']==plan_item['id'])
        ws.save({'request_id':uuid.uuid4().hex,'id':plan_item['id'],'version':1,'values':{'title':'改名后的计划'}})
        check('workspace edits preserve long ID and SHA-256',ws.read()['items'][plan_item['id']]['long_id']==saved['long_id'] and ws.read()['items'][plan_item['id']]['sha256']==saved['sha256'])
finally:
    for clone in clones:
        assert re.fullmatch(r'easyerp_ids_test_[0-9a-f]{12}',clone)
        erp.sql('DROP DATABASE IF EXISTS '+I(clone)+' WITH (FORCE)',db='postgres',role='easyerp_admin')
    for mode in ('live','demo'):
        db=erp.c['database']+('_ui_demo' if mode=='demo' else '')
        assert signature(db)==before[mode],mode+' original data changed during isolated testing'
check('both original databases remain unchanged and test databases are removed')
(out/'tests.json').write_text(json.dumps({'status':'PASS','checks':len(passed),'passed':passed,'temporary_databases_removed':True},ensure_ascii=False,indent=2),encoding='utf-8')
