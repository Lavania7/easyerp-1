"""Offline adapter tests. No connection to a business database."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import csv
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'bin'))
spec = importlib.util.spec_from_file_location('import_inbox', PROJECT / 'bin/import_inbox.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
import easyerp


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.batch = self.root / 'import/batches/test'
        (self.batch / 'sources').mkdir(parents=True)
        (self.batch / 'prepared').mkdir()
        self.source = self.batch / 'sources/source.txt'
        self.source.write_text('编号A，姓名原值', encoding='utf-8')
        self.file = self.batch / 'prepared/finance.人员档案表.csv'
        self.mapping = self.file.with_name(self.file.name + '.sources.json')
        self.write_csv([['A', '原值']])
        self.write_mapping([2])
        self.check_calls, self.execute_calls, self.backups = [], [], []
        self.uncertain = False
        case = self

        class Service:
            def check(self, filename, raw, mode):
                case.check_calls.append((filename, raw, mode))
                return {'id': len(case.check_calls), 'mode': mode, 'sha256': hashlib.sha256(raw).hexdigest(),
                        'validated': True, 'row_count': 1, 'match': {'type_id': 'standard-master'}}

            def execute(self, *args, **kwargs):
                case.execute_calls.append((args, kwargs))
                if case.uncertain:
                    raise RuntimeError('Unknown commit outcome')
                return {'request_id': 'request-' + str(args[0]), 'inserted': 1}

        class Database:
            c = {'database': 'local'}
            data = case.root / 'var/pgdata'

            def verify_files(self):
                return None

            def sql(self, query, db):
                return SimpleNamespace(stdout=str(self.data))

            def backup(self, db):
                case.backups.append(db)
                return case.root / 'backup.dump'

        self.patches = [patch.object(adapter, 'ROOT', self.root), patch.object(adapter, 'Imports', Service),
                        patch.object(easyerp, 'ERP', Database)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def write_csv(self, rows):
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator='\r\n')
        writer.writerow(['人员ID', '姓名'])
        writer.writerows(rows)
        self.file.write_bytes(stream.getvalue().encode('utf-8-sig'))

    def write_mapping(self, lines):
        self.evidence = {'sources': [{'id': 's1', 'file': 'sources/source.txt', 'sha256': adapter.sha(self.source)}],
                         'fields': {'人员ID': '原文编号', '姓名': '原文姓名'},
                         'rows': [{'csv_line': line, 'sources': [{'id': 's1', 'location': '第1段'}]} for line in lines]}
        self.mapping.write_text(json.dumps(self.evidence, ensure_ascii=False), encoding='utf-8')

    def test_scan_is_offline_and_skips_office_temporary_files(self):
        inbox = self.root / 'import/inbox/finance'
        inbox.mkdir(parents=True)
        (inbox / 'sample.txt').write_bytes(b'source')
        (inbox / '~$sample.xlsx').write_bytes(b'temporary')
        result = adapter.scan()
        self.assertEqual(result['count'], 1)
        self.assertFalse(result['database_accessed'])
        self.assertEqual(result['files'][0]['sha256'], hashlib.sha256(b'source').hexdigest())
        self.assertFalse(self.check_calls)

    def test_check_caches_original_identity_and_archives_exact_bytes(self):
        checked = adapter.check(self.file, 'demo')
        again = adapter.check(self.file, 'demo')
        self.assertTrue(again['cached_check'])
        self.assertEqual(len(self.check_calls), 1)
        self.assertEqual(checked['check']['id'], again['check']['id'])
        self.assertEqual((self.batch / 'checks/1' / self.file.name).read_bytes(), self.file.read_bytes())
        self.assertEqual((self.batch / 'checks/1/sources.json').read_bytes(), self.mapping.read_bytes())

    def test_apply_passes_frontend_choices_and_backs_up_selected_database(self):
        adapter.check(self.file, 'demo')
        receipt = adapter.apply(self.file, 'demo', 'true', 'fill_empty')
        self.assertEqual(self.backups, ['local_ui_demo'])
        args, options = self.execute_calls[0]
        self.assertEqual(args, (1, self.file.name, self.file.read_bytes(), 'demo'))
        self.assertEqual(options, {'allow_incomplete': 'true', 'merge': 'fill_empty'})
        self.assertEqual(receipt['check_id'], 1)
        self.assertTrue((self.batch / 'receipts/1.json').is_file())

    def test_file_or_mapping_or_source_change_blocks_write(self):
        adapter.check(self.file, 'demo')
        original = self.file.read_bytes()
        self.file.write_bytes(original + b'\r\n')
        with self.assertRaisesRegex(ValueError, '已变化'):
            adapter.apply(self.file, 'demo')
        self.file.write_bytes(original)
        self.evidence['fields']['姓名'] = '不同对应'
        self.mapping.write_text(json.dumps(self.evidence), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '已变化'):
            adapter.apply(self.file, 'demo')
        self.write_mapping([2])
        self.source.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError, '来源副本校验失败'):
            adapter.apply(self.file, 'demo')
        self.assertFalse(self.backups)
        self.assertFalse(self.execute_calls)

    def test_mode_change_and_outside_paths_are_rejected(self):
        adapter.check(self.file, 'demo')
        with self.assertRaisesRegex(ValueError, '已变化'):
            adapter.apply(self.file, 'live')
        with self.assertRaisesRegex(ValueError, '规定目录'):
            adapter.check(self.root / 'elsewhere.csv', 'demo')
        self.evidence['sources'][0]['file'] = '../../escape.txt'
        self.mapping.write_text(json.dumps(self.evidence), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '规定目录'):
            adapter.bundle(self.file)

    def test_multiline_csv_uses_frontend_physical_line_numbers(self):
        self.write_csv([['A', '第一行\n第二行'], ['B', '姓名B']])
        self.write_mapping([2, 4])
        adapter.bundle(self.file)
        self.write_mapping([2, 3])
        with self.assertRaisesRegex(ValueError, '源行对应'):
            adapter.bundle(self.file)

    def test_explicit_recheck_creates_new_identity_and_preserves_old_receipt(self):
        adapter.check(self.file, 'demo')
        adapter.apply(self.file, 'demo')
        second = adapter.check(self.file, 'demo', recheck=True)
        self.assertEqual(second['check']['id'], 2)
        self.assertTrue((self.batch / 'receipts/1.json').is_file())
        self.assertTrue((self.batch / 'checks/1/sources.json').is_file())
        self.assertTrue((self.batch / 'checks/2/sources.json').is_file())

    def test_uncertain_commit_requires_same_identity_and_choices(self):
        adapter.check(self.file, 'demo')
        self.uncertain = True
        with self.assertRaises(RuntimeError):
            adapter.apply(self.file, 'demo', 'true', 'latest')
        with self.assertRaisesRegex(ValueError, '上次执行结果'):
            adapter.check(self.file, 'demo', recheck=True)
        with self.assertRaisesRegex(ValueError, '原空缺和合并选择'):
            adapter.apply(self.file, 'demo', 'true', 'fill_empty')
        self.uncertain = False
        receipt = adapter.apply(self.file, 'demo', 'true', 'latest')
        self.assertEqual(receipt['check_id'], 1)


if __name__ == '__main__':
    unittest.main()
