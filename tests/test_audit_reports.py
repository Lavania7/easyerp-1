"""Release-1.3 date bounds and legacy evidence; temporary workspace only."""
from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT / 'tools'))
from workspace import Workspace, WorkspaceError
from migrate_supplier_items import migrate_workspace


class AuditReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Workspace('demo', self.temp.name)

    def report(self, **values):
        return self.ws.save({'request_id': uuid.uuid4().hex, 'kind': 'report',
            'values': {'title': '日期边界测试', 'start': '2026-11-14', 'due': '2026-11-15', **values}})['item']

    def test_exact_date_intersection_and_quarter_year_bounds(self):
        narrow = self.report()
        quarter = self.report(start='2026-10-01', due='2026-12-31')
        annual = self.report(start='2026-01-01', due='2026-12-31')
        for start, end, expected in [
            ('2026-11-14', '2026-11-15', {narrow['id'], quarter['id'], annual['id']}),
            ('2026-11-16', '2026-11-16', {quarter['id'], annual['id']}),
            ('2026-09-30', '2026-09-30', {annual['id']}),
            ('2027-01-01', '2027-12-31', set()),
        ]:
            self.assertEqual({row['id'] for row in self.ws.listing({'kind': 'report', 'start': start, 'end': end})['rows']}, expected)

    def test_department_and_source_isolation(self):
        finance = self.report(department='FIN')
        self.report(department='研发部')
        self.report()
        self.assertEqual([r['id'] for r in self.ws.listing({'kind': 'report', 'department': 'finance'})['rows']], [finance['id']])
        self.assertEqual(len(self.ws.listing({'kind': 'report'})['rows']), 3)
        self.assertEqual(Workspace('live', self.temp.name).listing({'kind': 'report'})['rows'], [])

    def test_reject_old_fields_invalid_dates_and_published_rewrite(self):
        for values in [{'type': '年度审计'}, {'month': '2026-11'}, {'start': '2026-02-30'}, {'due': '2026-11-13'}, {'start': ''}]:
            with self.assertRaises(WorkspaceError):
                self.report(**values)
        report = self.report(owner='复核人', scope='指定日期', conclusion='仅测试不作业务核定')
        item = self.ws.save({'request_id': uuid.uuid4().hex, 'id': report['id'], 'version': report['version'], 'status': '已发布'})['item']
        with self.assertRaises(WorkspaceError):
            self.ws.save({'request_id': uuid.uuid4().hex, 'id': item['id'], 'version': item['version'], 'values': {'title': '改写'}})

    def test_undated_legacy_evidence_remains_visible_without_invented_dates(self):
        report = self.report()
        data = self.ws.read()
        data['items'][report['id']]['values'] = {'title': '缺少期间的旧证据', 'type': '未知旧分类'}
        self.ws.write(data)
        rows = self.ws.listing({'kind': 'report', 'start': '2027-01-01', 'end': '2027-01-31'})['rows']
        self.assertEqual(len(rows), 1)
        self.assertNotIn('start', rows[0]['values'])
        self.assertEqual(rows[0]['legacy']['retired_report_fields']['type'], '未知旧分类')

    def test_legacy_read_and_controlled_migration_keep_exact_source(self):
        report = self.report()
        data = self.ws.read()
        legacy = {'title': '历史证据', 'month': '2024-02', 'type': '季度审计', 'evidence': 'original.pdf'}
        data['items'][report['id']]['values'] = copy.deepcopy(legacy)
        old_history = copy.deepcopy(data['items'][report['id']]['history'])
        self.ws.write(data)
        original = self.ws.path.read_bytes()
        rows = self.ws.listing({'kind': 'report', 'start': '2024-03-31', 'end': '2024-03-31'})['rows']
        self.assertEqual(rows[0]['values']['start'], '2024-01-01')
        self.assertEqual(rows[0]['values']['due'], '2024-03-31')
        self.assertNotIn('type', rows[0]['values'])
        self.assertEqual(self.ws.path.read_bytes(), original)
        preview = migrate_workspace('demo', root=self.temp.name)
        self.assertEqual(preview['changed'], 1)
        self.assertEqual(self.ws.path.read_bytes(), original)
        result = migrate_workspace('demo', apply=True, root=self.temp.name)
        self.assertEqual(Path(result['backup']).read_bytes(), original)
        migrated = self.ws.read()['items'][report['id']]
        self.assertEqual(migrated['legacy']['retired_report_fields'], legacy)
        self.assertEqual(migrated['history'], old_history)
        self.assertEqual(migrated['version'], report['version'])
        self.assertEqual(migrate_workspace('demo', apply=True, root=self.temp.name)['status'], 'already applied')


if __name__ == '__main__':
    unittest.main(verbosity=2)
