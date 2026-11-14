from decimal import Decimal
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import io
from pathlib import Path
import socket
import sys
import threading
from types import SimpleNamespace
import unittest
import zipfile
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from entry import EntryError, ManualEntry
import imports
import server
from standard_import import StandardImport


def column(name, kind="text", required=False):
    return {
        "name": name,
        "type": kind,
        "required": required,
        "default": None,
        "automatic": False,
        "options": [],
        "reference": None,
    }


class EntryValidationTests(unittest.TestCase):
    def setUp(self):
        self.entry = object.__new__(ManualEntry)
        self.entry.mode = "demo"
        self.entry.db = "isolated"
        self.entry.ids = Mock()
        self.entry.ids.resolve.side_effect = lambda key, value: value
        self.entry.ids.values.side_effect = lambda obj, values: dict(values)
        self.entry.data = Mock()
        self.obj = {
            "key": "sales.销售订单登记表",
            "pk": "订单ID",
            "columns": [column("订单ID"), column("状态")],
            "children": {
                "object": "sales.销售订单行表",
                "parent_field": "订单ID",
                "minimum": 1,
            },
        }
        self.child = {
            "key": "sales.销售订单行表",
            "pk": "销售订单行ID",
            "columns": [column("销售订单行ID"), column("订单ID")],
            "children": None,
        }
        self.entry.catalog = Mock(
            return_value={self.obj["key"]: self.obj, self.child["key"]: self.child}
        )
        self.payload = {
            "request_id": "validation_request",
            "object": self.obj["key"],
            "operation": "update",
            "id": "SO001",
            "version": "1",
            "values": {"状态": "草稿"},
        }

    def test_invalid_parent_values_are_rejected_before_database_access(self):
        for values in (None, [], 1, "invalid"):
            with self.subTest(values=values), self.assertRaises(EntryError):
                self.entry.save({**self.payload, "values": values})
        self.entry.data.erp.sql.assert_not_called()

    def test_invalid_child_values_are_rejected_before_database_access(self):
        for values in (None, [], 1, "invalid"):
            child = {
                "object": self.child["key"],
                "operation": "update",
                "id": "SOL001",
                "version": "1",
                "values": values,
            }
            with self.subTest(values=values), self.assertRaises(EntryError):
                self.entry.save({**self.payload, "children": [child]})
        self.entry.data.erp.sql.assert_not_called()

    def test_required_children_cannot_be_omitted_or_empty(self):
        for extra in ({}, {"children": []}):
            payload = {**self.payload, "operation": "create", **extra}
            with self.subTest(extra=extra), self.assertRaises(EntryError):
                self.entry.save(payload)
        self.entry.ids.allocate.assert_not_called()
        self.entry.data.erp.sql.assert_not_called()

    def test_boolean_json_and_form_values(self):
        col = column("有效", "boolean")
        for raw, expected in (
            (True, "true"),
            (False, "false"),
            ("true", "true"),
            ("false", "false"),
        ):
            self.assertEqual(ManualEntry.value(col, raw), expected)
        for raw in (0, 1, "yes", [], {}):
            with self.subTest(raw=raw), self.assertRaises(EntryError):
                ManualEntry.value(col, raw)
        self.assertIsNone(ManualEntry.value(col, None))

    def test_exact_decimal_and_excess_precision(self):
        col = column("金额", "numeric(20,4)")
        value = "9007199254740993.1234"
        self.assertEqual(ManualEntry.value(col, Decimal(value)), value)
        self.assertEqual(ManualEntry.value(col, "0"), "0")
        for raw in ("1.00001", "10000000000000000", 0.1, True):
            with self.subTest(raw=raw), self.assertRaises(EntryError):
                ManualEntry.value(col, raw)

    def test_deep_json_has_a_validation_error(self):
        with patch("entry.json.loads", side_effect=RecursionError), self.assertRaises(EntryError):
            ManualEntry.value(column("内容", "jsonb"), "{}")

    def test_catalog_is_read_once_per_object_lookup(self):
        self.assertIs(self.entry.object(self.obj["key"]), self.obj)
        self.entry.catalog.assert_called_once()


class ImportParsingTests(unittest.TestCase):
    @staticmethod
    def workbook(sheet):
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "xl/workbook.xml",
                '<workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="来源表" r:id="rId1"/></sheets></workbook>',
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
            )
            archive.writestr("xl/worksheets/sheet1.xml", sheet)
        return content.getvalue()

    def test_xlsx_preview_retains_physical_rows_and_values(self):
        raw = self.workbook(
            '<worksheet><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>名称</t></is></c></row>'
            '<row r="3"><c r="B3"><v>0</v></c></row></sheetData></worksheet>'
        )
        sheet = imports.xlsx(raw)["sheets"][0]
        self.assertEqual(sheet["rows"], 2)
        self.assertEqual(sheet["max_columns"], 2)
        self.assertEqual(sheet["top"], {1: ["名称"], 3: ["", "0"]})

    def test_xlsx_rejects_xml_definitions_and_incomplete_xml(self):
        for sheet in (
            '<!DOCTYPE worksheet [<!ENTITY item "value">]><worksheet/>',
            '<worksheet><sheetData><row r="1"></row>',
        ):
            with self.subTest(sheet=sheet), self.assertRaises(imports.ImportError):
                imports.xlsx(self.workbook(sheet))

    def test_csv_preview_counts_rows_columns_and_multiline_cells(self):
        result = imports.text_table(
            '名称,内容,\r\n甲,"第一行\n第二行",\r\n,,\r\n'.encode("utf-8-sig")
        )
        sheet = result["sheets"][0]
        self.assertEqual(sheet["rows"], 3)
        self.assertEqual(sheet["max_columns"], 2)
        self.assertEqual(sheet["top"][2], ["甲", "第一行\n第二行"])
        self.assertEqual(sheet["top"][3], [])

    def test_csv_only_retains_the_first_twenty_rows(self):
        sheet = imports.text_table(("a,b\n" * 50).encode())["sheets"][0]
        self.assertEqual(sheet["rows"], 50)
        self.assertEqual(len(sheet["top"]), 20)

    def test_csv_limits_are_checked_before_reading_the_rest(self):
        def rows(*args, **kwargs):
            yield ["a"]
            yield ["b"]
            yield ["c"]
            raise AssertionError("reader consumed data beyond the row limit")

        with patch.object(imports, "MAX_ROWS", 2), patch.object(imports.csv, "reader", rows):
            with self.assertRaises(imports.ImportError) as caught:
                imports.text_table(b"a\nb\nc\n")
        self.assertEqual(caught.exception.status, 413)

    def test_csv_rejects_invalid_and_empty_input(self):
        for raw in (b'"unterminated', b" \n,\n", b"a\x00b"):
            with self.subTest(raw=raw), self.assertRaises(imports.ImportError):
                imports.text_table(raw)
        with patch.object(imports, "MAX_CELLS", 2), self.assertRaises(imports.ImportError):
            imports.text_table(b"a,b\nc\n")
        with self.assertRaises(imports.ImportError):
            imports.text_table(("," * 256).encode())

    def test_automatic_ids_are_not_missing_business_values(self):
        obj = {
            "key": "sales.客户档案表",
            "name": "客户档案表",
            "pk": "客户ID",
            "columns": [column("客户ID", required=True), column("客户名称", required=True)],
        }
        importer = object.__new__(StandardImport)
        importer.entry = Mock(mode="demo")
        importer.entry.catalog.return_value = {obj["key"]: obj}
        importer.entry.ids.allocate.return_value = ["C001"]
        importer.entry.ids.values.side_effect = lambda obj, values: dict(values)
        importer.entry.value.side_effect = ManualEntry.value
        plan = importer.plan(
            obj["key"] + ".csv", "客户ID,客户名称\r\n,客户\r\n".encode("utf-8-sig")
        )
        self.assertEqual(plan["errors"], [])
        self.assertEqual(plan["generated_id_count"], 1)
        self.assertEqual(plan["blank_cells"], 0)
        self.assertEqual(plan["missing"], [])


class HTTPBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def call(self, body=b"{}", headers=None, path="/api/entry/save", method="POST"):
        connection = HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        self.addCleanup(connection.close)
        defaults = {"Content-Type": "application/json", "X-EasyERP-Token": server.WRITE_TOKEN}
        connection.request(method, path, body=body, headers={**defaults, **(headers or {})})
        response = connection.getresponse()
        return response.status, response.read()

    def test_valid_json_preserves_decimal_precision(self):
        service = SimpleNamespace(save=lambda payload: payload)
        with patch.object(server, "ManualEntry", return_value=service):
            status, raw = self.call(b'{"amount":9007199254740993.1234,"zero":0}')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), {"amount": "9007199254740993.1234", "zero": 0})

    def test_duplicate_and_nonfinite_json_are_rejected(self):
        for body in (b'{"a":1,"a":2}', b'{"amount":NaN}', b"[" * 2000 + b"0" + b"]" * 2000):
            with self.subTest(body=body[:30]):
                self.assertEqual(self.call(body)[0], 400)

    def test_local_origin_and_token_boundaries(self):
        for headers in (
            {"Host": "example.com"},
            {"Origin": "https://example.com"},
            {"Sec-Fetch-Site": "cross-site"},
            {"X-EasyERP-Token": "caf\xe9"},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.call(body=b"", headers=headers)[0], 403)

    def test_invalid_length_and_oversize_requests(self):
        for value, expected in (("-1", 400), ("+2", 400), (str(server.MAX_BODY + 1), 413)):
            with self.subTest(value=value):
                self.assertEqual(
                    self.call(body=b"", headers={"Content-Length": value})[0], expected
                )
        self.assertEqual(self.call(body=b"", headers={"Transfer-Encoding": "chunked"})[0], 400)

    def test_duplicate_lengths_and_truncated_files(self):
        port = self.httpd.server_port
        for lengths, body in (
            ("Content-Length: 2\r\nContent-Length: 2", b""),
            ("Content-Length: 5", b"a"),
        ):
            with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
                header = (
                    f"POST /api/import/check?filename=a.csv HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\n"
                    f"Content-Type: application/octet-stream\r\nX-EasyERP-Token: {server.WRITE_TOKEN}\r\n"
                    f"{lengths}\r\n\r\n"
                ).encode()
                with patch.object(server, "import_service") as service:
                    connection.sendall(header + body)
                    connection.shutdown(socket.SHUT_WR)
                    response = connection.makefile("rb").read()
                    self.assertIn(b" 400 ", response.split(b"\r\n", 1)[0])
                    service.assert_not_called()

    def test_csv_cells_preserve_null_zero_and_protect_formulas(self):
        self.assertEqual(server.csv_cell(None), "\\N")
        self.assertEqual(server.csv_cell(""), "")
        self.assertEqual(server.csv_cell(0), "0")
        self.assertEqual(server.csv_cell(Decimal("-1.2300")), "-1.2300")
        for value in ("=1+1", " \t=1+1", "\r@SUM(A1)", "+cmd", "-cmd"):
            self.assertEqual(server.csv_cell(value), "'" + value)

    def test_head_has_no_body_and_keeps_security_headers(self):
        connection = HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        self.addCleanup(connection.close)
        connection.request("HEAD", "/")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.read(), b"")
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
        self.assertIn("frame-ancestors 'none'", response.getheader("Content-Security-Policy"))
        self.assertGreater(int(response.getheader("Content-Length")), 0)


if __name__ == "__main__":
    unittest.main()
