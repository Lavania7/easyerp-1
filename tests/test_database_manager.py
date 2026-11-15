"""Registry and real HTTP boundaries; no connection to a business database."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
import copy
from http.client import HTTPConnection
import json
import shutil
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'app'), str(ROOT/'tools')]
from easyerp import ERP
import database_manager as dm
import server
from data import Data
from entry import ManualEntry
from workspace import Workspace


class FakeERP:
    generation = 'a'
    def __init__(self, mode='live', **kwargs):
        self.c = {'database': 'fixture_' + mode, 'port': 55433,
                  'postgres_bin': 'unused', 'python': sys.executable}
        self.root = ROOT
        self.data = ROOT/'var/pgdata'
        self.private = ROOT/'.secrets'
    def workspace_root(self, mode='live'):
        return ROOT/'var/workspace'
    def verify_files(self):
        return {'version':'fixture', 'sql_files':{'001.sql':self.generation}}, self.generation * 64


class RegistryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='easyerp-manager-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'project'
        self.folder = Path(self.temp.name)/'selected'
        self.folder.mkdir()
        for relative in [*[f'db/app/{name}' for name in dm.APP_SQL], 'app/id_rules.json']:
            dest = self.root/relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/relative, dest)
        self.manager = dm.DatabaseManager(self.root, FakeERP, lambda:str(self.folder))
        FakeERP.generation = 'a'
    def preview(self):
        ticket = self.manager.select_folder({})['folder_ticket']
        return self.manager.preview({'label':'独立空库', 'folder_ticket':ticket})
    def test_listing_is_read_only_and_lineage_unknown(self):
        result = self.manager.listing()
        self.assertEqual(len(result['nodes']), 3)
        self.assertEqual(result['nodes'][1]['relation'], 'unknown')
        self.assertFalse(self.manager.registry.exists())
    def test_native_selection_cancel_and_reject_supplied_path(self):
        self.manager.picker = lambda:None
        self.assertTrue(self.manager.select_folder({})['cancelled'])
        with self.assertRaises(dm.DatabaseError): self.manager.select_folder({'path':str(self.folder)})
    def test_arbitrary_create_path_and_plan_forbidden(self):
        with self.assertRaises(dm.DatabaseError): self.manager.preview({'label':'x', 'folder':str(self.folder)})
        with self.assertRaises(dm.DatabaseError): self.manager.create({'plan_id':'untrusted', 'directory':str(self.folder)})
        with self.assertRaises(dm.DatabaseError): self.manager.create({'plan_id':'untrusted'})
    def test_invalid_ticket_parent_label_and_project_directory(self):
        with self.assertRaises(dm.DatabaseError): self.manager.preview({'label':'x','folder_ticket':'untrusted'})
        ticket = self.manager.select_folder({})['folder_ticket']
        for bad in ({'parent_id':'unknown'}, {'label':''}, {'label':'bad\nname'}):
            with self.assertRaises(dm.DatabaseError): self.manager.preview({'label':'x','folder_ticket':ticket,**bad})
        with self.assertRaises(dm.DatabaseError): dm.folder_path(str(self.root), self.root)
    def test_create_idempotency_and_parent_relation(self):
        result = self.preview()
        calls = []
        self.manager.initialize = lambda plan:calls.append(plan['id'])
        first = self.manager.create({'plan_id':result['plan_id']})
        second = self.manager.create({'plan_id':result['plan_id']})
        self.assertFalse(first['replayed'])
        self.assertTrue(second['replayed'])
        self.assertEqual(len(calls),1)
        self.assertEqual(first['node']['business_rows'],0)
        self.assertTrue(first['node']['stopped'])
        self.assertEqual(first['node']['relation'],'empty-schema')
    def test_plan_rejects_template_drift_and_existing_target(self):
        plan = self.preview()
        FakeERP.generation = 'b'
        with self.assertRaises(dm.DatabaseError): self.manager.create({'plan_id':plan['plan_id']})
        FakeERP.generation = 'a'
        Path(plan['directory']).mkdir()
        with self.assertRaises(dm.DatabaseError): self.manager.create({'plan_id':plan['plan_id']})
    def test_actual_template_and_logical_relation_are_distinct(self):
        ticket=self.manager.select_folder({})['folder_ticket']
        preview=self.manager.preview({'label':'x','folder_ticket':ticket,'parent_id':'active-live'})
        self.assertTrue(preview['parent_id'].startswith('template-'))
        self.assertEqual(preview['logical_parent_id'],'active-live')
        self.manager.initialize=lambda _:None
        created=self.manager.create({'plan_id':preview['plan_id']})['node']
        self.assertNotEqual(created['parent_id'],created['logical_parent_id'])
        FakeERP.generation='b'
        self.assertIn(created['parent_id'],{node['id'] for node in self.manager.listing()['nodes']})
    def test_failed_creation_preserves_record_and_no_retry(self):
        plan = self.preview()
        def failed(value):
            Path(value['directory']).mkdir()
            raise RuntimeError('private internal details')
        self.manager.initialize = failed
        with self.assertRaises(dm.DatabaseError) as error: self.manager.create({'plan_id':plan['plan_id']})
        self.assertNotIn('private internal details',str(error.exception))
        self.assertEqual(next(node for node in self.manager.read()['nodes'] if node['kind']=='database')['status'],'failed')
        self.assertTrue(Path(plan['directory']).exists())
        with self.assertRaises(dm.DatabaseError): self.manager.create({'plan_id':plan['plan_id']})
    def test_expired_ticket(self):
        result = self.manager.select_folder({})
        path,_ = dm.TICKETS[result['folder_ticket']]
        dm.TICKETS[result['folder_ticket']] = (path, time.monotonic()-1)
        with self.assertRaises(dm.DatabaseError): self.manager.preview({'label':'x','folder_ticket':result['folder_ticket']})
    def test_retained_source_is_derived_from_matching_cutover_record(self):
        target=Path(self.temp.name)/'migrated'
        def factory(mode='live',**_):
            instance=FakeERP(mode)
            instance.root=target if mode=='live' else self.root
            if mode=='live':
                instance.data=target/'pgdata'
                instance.c['port']=55434
            return instance
        self.manager.erp_factory=factory
        record={'state':'cutover','backup_sha256':'a'*64,
                'target_config':{'database':'fixture_live','port':55434,'data_directory':str(target/'pgdata')},
                'source_config':{'database':'old_live','port':55433,'data_directory':str(self.root/'var/pgdata')}}
        dm.atomic_json(target/'migration/restored.json',record)
        catalog=self.manager.listing()
        old=next(node for node in catalog['nodes'] if node['kind']=='retained-source')
        active=next(node for node in catalog['nodes'] if node['id']=='active-live')
        self.assertEqual(active['parent_id'],old['id'])
        self.assertEqual(active['relation'],'restored-copy')
        self.assertEqual(old['port'],55433)
        self.assertTrue(catalog['source_retained'])
        self.assertTrue(self.manager.migration_preview()['executed'])
        record['target_config']['port']=55435
        dm.atomic_json(target/'migration/restored.json',record)
        with self.assertRaises(dm.DatabaseError):self.manager.listing()
    def test_http_boundaries_and_static_resources(self):
        class Quiet(server.Handler):
            def log_message(self,*_): pass
        with patch.object(server,'DATABASES',self.manager):
            http = server.ThreadingHTTPServer(('127.0.0.1',0),Quiet)
            thread = threading.Thread(target=http.serve_forever,daemon=True)
            thread.start()
            try:
                def call(method,path,body=None,headers=None):
                    connection = HTTPConnection('127.0.0.1',http.server_port)
                    connection.request(method,path,body=body,headers=headers or {})
                    response=connection.getresponse(); status=response.status; raw=response.read(); connection.close()
                    return status,raw
                status,body=call('GET','/api/databases')
                self.assertEqual(status,200)
                token=json.loads(body)['token']
                for resource in ('database-manager.js','database-manager.css'):
                    self.assertEqual(call('GET','/'+resource)[0],200)
                self.assertEqual(call('POST','/api/databases/folder','{}',{'Content-Type':'application/json'})[0],403)
                headers={'Content-Type':'application/json','X-EasyERP-Token':token}
                self.assertEqual(call('POST','/api/databases/folder','{}',{**headers,'Origin':'http://evil.invalid'})[0],403)
                self.assertEqual(call('POST','/api/databases/folder','{}',{**headers,'Host':'evil.invalid'})[0],403)
                self.assertEqual(call('POST','/api/databases/folder','{"x":1,"x":2}',headers)[0],400)
                self.assertEqual(call('POST','/api/databases/folder','{}',{**headers,'Content-Type':'text/plain'})[0],415)
                self.assertEqual(call('POST','/api/databases/migrate','{}',headers)[0],405)
                self.assertEqual(call('POST','/api/databases/delete','{}',headers)[0],405)
                self.assertEqual(call('POST','/api/databases/folder','{}',headers)[0],200)
            finally:
                http.shutdown();http.server_close();thread.join()


class SourceTests(TestCase):
    def test_explicit_sources_propagate(self):
        base=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
        with TemporaryDirectory(prefix='easyerp-sources-') as directory:
            root=Path(directory)
            config={**base,'database_sources':{mode:{'database':'same_name','port':55434+index,
                'runtime_root':str(root/mode),'data_directory':str(root/mode/'pgdata'),
                'private_directory':str(root/mode/'private'),'workspace_directory':str(root/mode/'workspace')}
                for index,mode in enumerate(('live','demo'))}}
            config_path=root/'candidate.json';config_path.write_text(json.dumps(config),encoding='utf-8')
            with patch('easyerp.CONFIG',config_path):
                live=Data({'mode':'live'});demo=Data({'mode':'demo'})
                self.assertEqual(live.db,'same_name');self.assertEqual(demo.db,'same_name')
                self.assertEqual(live.erp.c['port'],55434);self.assertEqual(demo.erp.c['port'],55435)
                self.assertNotEqual(ManualEntry({'mode':'live'}).cache_key,ManualEntry({'mode':'demo'}).cache_key)
                self.assertEqual(Workspace('live').root,root/'live/workspace')
                self.assertEqual(Workspace('demo').root,root/'demo/workspace')
                with patch.object(server,'IMPORTS',{}):
                    self.assertNotEqual(server.import_service('live').path,server.import_service('demo').path)
    def test_legacy_config_is_compatible(self):
        config=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
        config.pop('database_sources',None)
        live=ERP(config=config);demo=ERP(mode='demo',config=config)
        self.assertEqual(demo.c['database'],live.c['database']+'_ui_demo')
        self.assertEqual(live.data,demo.data)
        self.assertEqual(live.c['port'],demo.c['port'])
    def test_invalid_remote_and_port(self):
        config=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
        config.pop('database_sources',None)
        for changes in ({'port':True},{'port':0},{'host':'remote.invalid'}):
            with self.assertRaises(ValueError): ERP(config={**config,**changes})
            with self.assertRaises(ValueError): ERP(config={**config,'database_sources':{'live':changes}})


if __name__=='__main__': main(verbosity=2)
