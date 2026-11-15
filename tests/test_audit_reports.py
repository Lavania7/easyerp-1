"""Audit periods and department isolation; fixtures live only in a temporary directory."""
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from workspace import Workspace, WorkspaceError


class AuditReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Workspace("demo", self.temp.name)

    def report(self, **values):
        return self.ws.save({
            "request_id": uuid.uuid4().hex, "kind": "report",
            "values": {"title": "审计测试", "month": "2026-11", **values},
        })["item"]

    def test_department_filter_retains_unassigned_reports_only_in_all(self):
        finance = self.report(department="FIN")
        rd = self.report(department="研发部", type="季度审计")
        unassigned = self.report()
        self.assertEqual({r["id"] for r in self.ws.listing({"kind": "report"})["rows"]},
                         {finance["id"], rd["id"], unassigned["id"]})
        for department, expected in (("finance", finance), ("rd", rd)):
            self.assertEqual([r["id"] for r in self.ws.listing({
                "kind": "report", "department": department,
            })["rows"]], [expected["id"]])
        self.assertEqual(self.ws.listing({"kind": "report", "department": "sales"})["rows"], [])
        with self.assertRaises(WorkspaceError):
            self.ws.listing({"kind": "report", "department": "unknown"})

    def test_period_overlap_and_normalization(self):
        monthly = self.report()
        quarterly = self.report(type="季度审计")
        annual = self.report(type="年度审计")
        self.assertEqual(quarterly["values"]["month"], "2026-10")
        self.assertEqual(annual["values"]["month"], "2026-01")
        for start, end, expected in (
            ("2026-11-14", "2026-11-15", {monthly["id"], quarterly["id"], annual["id"]}),
            ("2026-12-01", "2026-12-31", {quarterly["id"], annual["id"]}),
            ("2026-09-01", "2026-09-30", {annual["id"]}),
            ("2027-01-01", "2027-12-31", set()),
        ):
            rows = self.ws.listing({"kind": "report", "start": start, "end": end})["rows"]
            self.assertEqual({r["id"] for r in rows}, expected)

    def test_reading_legacy_monthly_reports_does_not_rewrite_them(self):
        legacy = self.report()
        self.assertNotIn("type", legacy["values"])
        original = self.ws.path.read_bytes()
        self.assertEqual(len(self.ws.listing({"kind": "report", "start": "2026-11-30"})["rows"]), 1)
        self.assertEqual(self.ws.path.read_bytes(), original)
        self.assertEqual(Workspace("live", self.temp.name).listing({"kind": "report"})["rows"], [])

    def test_invalid_periods_and_published_report_protection(self):
        for values in ({"month": "2026-13"}, {"month": "0000-01"}, {"type": "unknown"}):
            with self.assertRaises(WorkspaceError):
                self.report(**values)
        report = self.report(type="季度审计", department="生产", owner="复核人",
                             scope="季度审计范围", conclusion="待补业务证据")
        published = self.ws.save({"request_id": uuid.uuid4().hex, "id": report["id"],
                                  "version": report["version"], "status": "已发布"})["item"]
        with self.assertRaises(WorkspaceError):
            self.ws.save({"request_id": uuid.uuid4().hex, "id": report["id"],
                          "version": published["version"], "values": {"month": "2026-02"}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
