"""Calculation persistence and browser/service arithmetic parity; no business writes."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from http.server import ThreadingHTTPServer
import threading
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from calculation_engine import evaluate, parameters, FormulaError
from calculations import Calculations
from workspace import Workspace, WorkspaceError


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = Calculations('demo', self.temp.name)

    def save(self, **values):
        return self.service.save({'request_id': uuid.uuid4().hex, **values})['item']

    def test_independent_source_and_only_two_business_fields(self):
        item = self.save(remarks='目的说明', board={'expression': '0.1+0.2'})
        self.assertEqual(item['board']['result'], {'value': '0.3', 'exact': True})
        self.assertRegex(item['id'], r'^CAL[0-9A-Z]{3,}$')
        self.assertNotIn('long_id', item)
        self.assertNotIn('department', item)
        self.assertFalse((Path(self.temp.name) / 'demo.json').exists())
        self.assertEqual(Workspace('demo', self.temp.name).listing({'kind': 'plan'})['rows'], [])
        self.assertEqual(Calculations('live', self.temp.name).listing({})['rows'], [])
        self.assertEqual(self.service.listing({'department': 'finance', 'start': '2099-01-01'})['rows'][0]['id'], item['id'])
        self.assertEqual(self.service.listing({'search': item['id']})['rows'][0]['remarks'], '目的说明')

    def test_recompute_result_notes_and_retry(self):
        request = {'request_id': 'stable_retry_id', 'remarks': '保留原备注', 'board': {'expression': r'T=\frac{Q_{plan}\times t_u}{n\times\eta}', 'parameters': {'Q_plan': '50', 't_u': '2', 'n': '4', 'eta': '0.8'}}, 'write_result': True}
        first = self.service.save(request)
        self.assertEqual(first, self.service.save(request))
        item = first['item']
        self.assertEqual(item['board']['result']['value'], '31.25')
        self.assertTrue(item['remarks'].startswith('保留原备注\n\n'))
        self.assertIn('结果：31.25', item['remarks'])
        self.assertEqual(item['version'], 1)
        with self.assertRaises(WorkspaceError):
            self.service.save({**request, 'remarks': 'different'})
        item = self.save(id=item['id'], version=1, board={'expression': '1/3'}, write_result=True)
        self.assertIn('≈ 0.33333333333333333333', item['remarks'])
        with self.assertRaises(WorkspaceError) as error:
            self.save(id=item['id'], version=1, remarks='stale')
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(len(item['history']), 2)

    def test_drafts_failures_and_no_forged_results(self):
        item = self.save(board={'expression': 'a/0', 'parameters': {'a': ''}})
        self.assertIsNone(item['board']['result'])
        with self.assertRaises(WorkspaceError):
            self.save(id=item['id'], version=1, write_result=True)
        self.assertEqual(self.service.listing({})['rows'][0]['version'], 1)
        for board in ({'expression': '1', 'result': {'value': '99'}}, {'expression': 'a', 'parameters': {'a': 1.2}}):
            with self.assertRaises(WorkspaceError):
                self.save(board=board)
        with self.assertRaises(WorkspaceError):
            self.save(department='production')

    def test_concurrent_updates_and_ids(self):
        def create(_):
            return self.save()['id']
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(create, range(12)))
        self.assertEqual(len(set(ids)), 12)
        def update(index):
            try:
                self.save(id=ids[0], version=1, remarks=str(index))
                return True
            except WorkspaceError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, range(2)))
        self.assertEqual(results.count(True), 1)

    def test_shared_formula_library_persistence_and_isolation(self):
        self.assertEqual(self.service.listing({})['formulas'], [])
        first = self.save(remarks='保留说明', board={'expression': ' x+1 ', 'parameters': {'x': '2'}}, save_formula=True)
        self.assertEqual(first['remarks'], '保留说明')
        self.assertEqual(first['board']['result']['value'], '3')
        self.assertEqual([f['expression'] for f in Calculations('demo', self.temp.name).listing({})['formulas']], ['x+1'])
        second = self.save(board={'expression': 'x+1'}, save_formula=True)
        self.assertEqual([f['expression'] for f in self.service.listing({})['formulas']], ['x+1'])
        self.save(id=second['id'], version=second['version'], board={'expression': 'y*2'}, save_formula=True)
        self.assertEqual([f['expression'] for f in self.service.listing({})['formulas']], ['x+1', 'y*2'])
        self.assertEqual(Calculations('live', self.temp.name).listing({})['formulas'], [])
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(Calculations('demo', other).listing({})['formulas'], [])
        for payload in ({'board': {}, 'save_formula': True}, {'save_formula': 'true'}, {'board': {'expression': '1/0'}, 'save_formula': True, 'write_result': True}):
            with self.assertRaises(WorkspaceError):
                self.save(**payload)
        self.assertEqual([f['expression'] for f in self.service.listing({})['formulas']], ['x+1', 'y*2'])
        def save_formula(index):
            return self.save(board={'expression': 'a+' + str(index % 3)}, save_formula=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(save_formula, range(12)))
        self.assertEqual({f['expression'] for f in self.service.listing({})['formulas']}, {'x+1', 'y*2', 'a+0', 'a+1', 'a+2'})

    def test_browser_service_parity(self):
        cases = [
            ('0.1+0.2', {}), ('9007199254740993+.0001', {}), ('1/3', {}), ('2/3', {}),
            ('-0.000000000000000000001', {}), ('0.999999999999999999999', {}),
            (r'Q_{\mathrm{plan}}=\max\!\left(0,\,D+S-I-W\right)', {'D': '50', 'S': '10', 'I': '100', 'W': '0'}),
            (r'M_j=Q_{plan}\times b_j', {'Q_plan': '50', 'b_j': '0.2'}),
            (r'T=\frac{Q_{plan}\times t_u}{n\times\eta}', {'Q_plan': '50', 't_u': '2', 'n': '4', 'eta': '0.8'}),
            ('max(2,min(3,4))', {}), ('a*(1+r)^n', {'a': '100', 'r': '.1', 'n': '2'}),
            ('2^-2', {}), ('2^3^2', {}), ('-2^2', {}), ('1,25*4', {}),
            ('1/0', {}), ('2^101', {}), ('2^0.5', {}), ('a+1', {}),
            (r'\sqrt{4}', {}), ('1+', {}), ('9' * 121, {}), ('9^100^2', {}),
            ('max(1)', {}), ('alert(1)', {}), ('1;process.exit()', {}),
        ]
        def run(case):
            expression, values = case
            try:
                return {'names': parameters(expression), 'result': evaluate(expression, values)}
            except FormulaError as error:
                return {'error': str(error)}
        engine = Path(__file__).resolve().parents[1] / 'app/web/calculator.js'
        script = "const e=require(process.argv[1]);let raw='';process.stdin.on('data',d=>raw+=d);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(raw).map(([x,v])=>{try{return {names:e.parameters(x),result:e.evaluate(x,v)}}catch(error){return {error:error.message}}}))));"
        result = subprocess.run(['node', '-e', script, str(engine)], input=json.dumps(cases), text=True, capture_output=True, check=True)
        self.assertEqual([run(case) for case in cases], json.loads(result.stdout))

    def test_named_formula_edits_and_legacy_library(self):
        first = self.save(remarks='独立计算记录', board={'expression': 'p*q', 'parameters': {'p': '2', 'q': '3'}, 'formula_name': '金额', 'parameter_notes': {'p': '单价', 'q': '数量', 'unused': '不保留'}}, save_formula=True)
        formula = self.service.listing({})['formulas'][0]
        self.assertEqual(first['board']['parameter_notes'], {'p': '单价', 'q': '数量'})
        self.assertEqual(formula['name'], '金额')
        revision = {'request_id': uuid.uuid4().hex, 'id': formula['id'], 'version': 1, 'name': '含运费金额', 'expression': 'p*q+s', 'parameter_notes': {'p': '单价', 'q': '数量', 's': '运费'}}
        updated = self.service.save_formula(revision)
        self.assertEqual(updated, self.service.save_formula(revision))
        self.assertEqual(updated['formula']['version'], 2)
        self.assertEqual(len(updated['formula']['history']), 2)
        self.assertEqual(self.service.listing({})['rows'][0], first)
        with self.assertRaises(WorkspaceError) as error:
            self.service.save_formula({**revision, 'request_id': uuid.uuid4().hex})
        self.assertEqual(error.exception.status, 409)
        for changes in ({'expression': ''}, {'name': 'x' * 121}, {'parameter_notes': {'p': 2}}, {'parameter_notes': {'p': 'x' * 301}}):
            with self.assertRaises(WorkspaceError):
                self.service.save_formula({**revision, 'request_id': uuid.uuid4().hex, 'version': 2, **changes})
        with self.service.locked():
            data = self.service.read()
            data['formulas'].append('a+1')
            self.service.write(data)
        legacy = self.service.listing({})['formulas'][-1]
        self.assertEqual(legacy['name'], '')
        self.assertEqual(legacy['expression'], 'a+1')
        self.assertEqual(legacy['id'], self.service.listing({})['formulas'][-1]['id'])
        self.service.save_formula({'request_id': uuid.uuid4().hex, 'id': legacy['id'], 'version': 1, 'name': '旧公式命名', 'parameter_notes': {'a': '输入'}})
        self.assertEqual(self.service.listing({})['formulas'][-1]['parameter_notes'], {'a': '输入'})

    def test_real_http_boundaries_and_decimal_parameters(self):
        import server
        service = self.service

        class Source:
            def workspace_root(self, mode):
                return service.root.parent

        with patch.object(server, 'ERP', lambda **kwargs: Source()):
            http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                base = 'http://127.0.0.1:' + str(http.server_port)
                with urlopen(base + '/api/calculations?mode=demo') as response:
                    listing = json.loads(response.read())
                token = listing['token']

                def post(payload, endpoint='/save', **headers):
                    request = Request(base + '/api/calculations' + endpoint + '?mode=demo', data=json.dumps(payload).encode(), headers={
                        'Content-Type': 'application/json', 'X-EasyERP-Token': token, **headers,
                    })
                    try:
                        with urlopen(request) as response:
                            return response.status, json.loads(response.read())
                    except HTTPError as error:
                        with error:
                            return error.code, json.loads(error.read())

                payload = {'request_id': uuid.uuid4().hex, 'board': {'expression': 'a+0.2', 'parameters': {'a': '0.1'}}, 'write_result': True, 'save_formula': True}
                status, first = post(payload)
                self.assertEqual(status, 200)
                self.assertEqual(first['item']['board']['result']['value'], '0.3')
                self.assertEqual(post(payload), (200, first))
                self.assertEqual(post(payload, **{'X-EasyERP-Token': ''})[0], 403)
                self.assertEqual(post(payload, Origin='https://outside.example')[0], 403)
                status, error = post({'request_id': uuid.uuid4().hex, 'board': {'expression': 'a', 'parameters': {'a': 0.1}}})
                self.assertEqual(status, 400)
                self.assertIn('error', error)
                status, error = post({'request_id': uuid.uuid4().hex, 'board': {'expression': '1/0'}, 'write_result': True})
                self.assertEqual(status, 400)
                self.assertEqual(len(service.listing({})['rows']), 1)
                formula = first['formulas'][0]
                revision = {'request_id': uuid.uuid4().hex, 'id': formula['id'], 'version': formula['version'], 'name': '金额', 'expression': 'p*q', 'parameter_notes': {'p': '单价', 'q': '数量'}}
                self.assertEqual(post(revision, '/formulas/save', **{'X-EasyERP-Token': ''})[0], 403)
                self.assertEqual(post(revision, '/formulas/save', Origin='https://outside.example')[0], 403)
                status, updated = post(revision, '/formulas/save')
                self.assertEqual(status, 200)
                self.assertEqual(updated['formula']['parameter_notes'], {'p': '单价', 'q': '数量'})
                self.assertEqual(post(revision, '/formulas/save'), (200, updated))
                self.assertEqual(post({**revision, 'request_id': uuid.uuid4().hex}, '/formulas/save')[0], 409)
            finally:
                http.shutdown()
                http.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
