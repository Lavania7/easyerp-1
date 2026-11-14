"""Source-faithful release2 workbook import. Read/preview is the default.

The workbook is evidence, never executable instructions. Formula text and saved
values are retained without running formulas. No inventory or financial events
are inferred from stock snapshots, quotes, costs or plans.
"""

from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import hashlib
import json
import re
import sys
from inspect_release2 import inspect

VERSION = "release2-workbook-20261023-v1"
SHEETS = {
    "产品源数据表": 5,
    "物料源数据表": 5,
    "BOM总表": 6,
    "物料需求": 8,
    "计划总览": 9,
    "其他物品数据表": 5,
    "资产表": 5,
}
NULLABLE = [
    ("rd", "产品主数据表", "规格"),
    ("rd", "产品主数据表", "单位ID"),
    ("rd", "产品主数据表", "类别"),
    ("rd", "物料主数据表", "规格"),
    ("rd", "物料主数据表", "单位ID"),
    ("rd", "物料主数据表", "类别"),
    ("rd", "产品版本表", "项目ID"),
    ("rd", "产品版本表", "版本名称"),
    ("rd", "产品版本表", "确认依据"),
    ("rd", "物料版本表", "版本名称"),
    ("rd", "物料版本表", "确认依据"),
    ("rd", "项目文件登记表", "项目ID"),
    ("rd", "项目文件登记表", "正式版本"),
    ("rd", "BOM登记表", "BOM版本"),
    ("rd", "BOM登记表", "确认依据"),
    ("rd", "BOM明细表", "物料版本ID"),
    ("rd", "BOM明细表", "单位ID"),
    ("rd", "BOM明细表", "确认依据"),
    ("production", "工单草稿表", "登记时间"),
]


def packed(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(v):
    return hashlib.sha256(v if isinstance(v, bytes) else v.encode("utf-8")).hexdigest()


def uid(kind, *values):
    return "rel2-" + kind + "-" + digest(packed(values))[:32]


def q(v):
    return '"' + v.replace('"', '""') + '"'


def qualified(v):
    return ".".join(q(x) for x in v.split("."))


def sqlval(v):
    return (
        "NULL"
        if v is None
        else "convert_from(decode('" + str(v).encode("utf-8").hex() + "','hex'),'UTF8')"
    )


def clean(v):
    return None if v is None or str(v).strip() == "" else str(v).strip()


def num(v):
    v = clean(v)
    if v is None or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", v):
        return None
    value = Decimal(v)
    return format(value, "f") if value.is_finite() else None


def val(row, col):
    return clean(row["cells"].get(col + str(row["row_no"]), {}).get("value"))


def cell(row, col):
    return row["cells"].get(col + str(row["row_no"]), {})


class Plan:
    def __init__(self, source, project):
        self.source = source.resolve()
        self.project = project.resolve()
        self.book = inspect(self.source)
        self.file_id = uid("file", str(self.source), self.book["sha256"])
        self.sheets = {s["name"]: s for s in self.book["sheets"]}
        self.tables = defaultdict(dict)
        self.records = []
        self.issues = []
        self.mapped = {}
        self.controls = []
        if set(self.sheets) != set(SHEETS):
            raise ValueError("Unreviewed worksheet set")
        self.products = {}
        self.materials = {}
        self.boms = defaultdict(list)

    def issue(self, reason, details, sheet=None, row=None):
        details = (sheet + ("!" + str(row) if row else "") + "：" if sheet else "") + details
        item = {
            "exception_id": uid("issue", self.file_id, reason, details),
            "file_id": self.file_id,
            "row_no": row,
            "order_id": None,
            "reason_code": reason,
            "details": details,
        }
        if item not in self.issues:
            self.issues.append(item)

    def add(self, table, row):
        key = next(iter(row.values()))
        if key in self.tables[table] and self.tables[table][key] != row:
            raise ValueError("Conflicting proposed row " + table + "/" + key)
        self.tables[table][key] = row
        return key

    def record(self, kind, sheet, row, key, data, derived=None, mapped=None):
        record = {
            "record_id": uid("record", self.file_id, sheet, row["row_no"]),
            "file_id": self.file_id,
            "sheet_name": sheet,
            "row_no": row["row_no"],
            "record_kind": kind,
            "source_key": key,
            "source_data": data,
            "derived_data": derived or {},
            "mapped_ids": mapped or {},
        }
        self.records.append(record)
        self.mapped[(sheet, row["row_no"])] = record["mapped_ids"]
        return record

    def input_rows(self, name, key="A"):
        return [
            r
            for r in self.sheets[name]["rows"]
            if r["row_no"] > SHEETS[name] and val(r, key) is not None
        ]

    def check(self, label, passed, details=None):
        self.controls.append({"check": label, "passed": bool(passed), "details": details})
        if not passed:
            raise ValueError(label + ": " + str(details))

    def build(self):
        for sheet in self.book["sheets"]:
            self.check(sheet["name"] + " has no saved formula errors", sheet["error_count"] == 0)
        expected_headers = {
            "产品源数据表": [
                "PID",
                "登记名称",
                "现有库存",
                "售价",
                "原料成本",
                "附加成本",
                "总成本",
                "总利润",
                "附加成本注释",
            ],
            "物料源数据表": [
                "MID",
                "物料名称",
                "供应商料号",
                "类型",
                "现有库存",
                "采购单价",
                "货存总价",
            ],
            "BOM总表": [
                "PID",
                "产品名称",
                "MID",
                "数量",
                "Comment",
                "Designator",
                "Footprint",
                "Value",
                "ManufacturerPart",
                "Manufacturer",
                "SupplierPart",
                "Supplier",
            ],
            "计划总览": [
                "PID",
                "产品名称",
                "现有库存",
                "计划立即生产",
                "计划预备生产",
                "计划生产合计",
            ],
            "物料需求": [
                "MID",
                "物料名称",
                "供应商料号",
                "类型",
                "现有库存",
                "毛需求",
                "建议采购量",
                "预计采购花销",
                "预计余量",
                "状态",
                "需求计算说明",
            ],
            "其他物品数据表": ["IID", "登记名称", "数量", "单价", "总金额"],
            "资产表": ["资产项目", "金额", "说明"],
        }
        for name, headers in expected_headers.items():
            row = next(r for r in self.sheets[name]["rows"] if r["row_no"] == SHEETS[name])
            columns = []
            for i in range(len(headers)):
                n = i + 1
                s = ""
                while n:
                    n, a = divmod(n - 1, 26)
                    s = chr(65 + a) + s
                columns.append(val(row, s))
            self.check(name + " reviewed headers", columns == headers)
        for row in self.input_rows("产品源数据表"):
            pid = val(row, "A")
            self.check("unique PID " + pid, pid not in self.products)
            name = val(row, "B")
            self.check("product name " + pid, name is not None)
            self.products[pid] = {
                "row": row,
                "name": name,
                "version_id": uid("product-version", self.file_id, pid),
            }
            self.add(
                "rd.产品主数据表",
                {"PID": pid, "名称": name, "规格": None, "单位ID": None, "类别": None},
            )
            self.add(
                "rd.产品版本表",
                {
                    "产品版本ID": self.products[pid]["version_id"],
                    "项目ID": None,
                    "PID": pid,
                    "版本名称": None,
                    "生效日期": None,
                    "确认依据": None,
                },
            )
            self.record(
                "product",
                "产品源数据表",
                row,
                pid,
                {
                    "PID": pid,
                    "名称": name,
                    "现有库存": num(val(row, "C")),
                    "售价": num(val(row, "D")),
                    "原料成本": num(val(row, "E")),
                    "原料成本原文": val(row, "E"),
                    "附加成本": num(val(row, "F")),
                    "总成本": num(val(row, "G")),
                    "总成本原文": val(row, "G"),
                    "总利润": num(val(row, "H")),
                    "总利润原文": val(row, "H"),
                    "附加成本注释": val(row, "I"),
                    "单位": None,
                    "币种": None,
                    "盘点日期": None,
                },
                mapped={"PID": pid, "产品版本ID": self.products[pid]["version_id"]},
            )
        names = defaultdict(list)
        for row in self.input_rows("物料源数据表"):
            mid = val(row, "A")
            name = val(row, "B")
            self.check("unique MID " + mid, mid not in self.materials and name is not None)
            self.materials[mid] = {
                "row": row,
                "name": name,
                "version_id": uid("material-version", self.file_id, mid),
                "price": num(val(row, "F")),
            }
            names[name].append(mid)
            self.add(
                "rd.物料主数据表",
                {"MID": mid, "名称": name, "规格": None, "单位ID": None, "类别": val(row, "D")},
            )
            self.add(
                "rd.物料版本表",
                {
                    "物料版本ID": self.materials[mid]["version_id"],
                    "MID": mid,
                    "版本名称": None,
                    "生效日期": None,
                    "确认依据": None,
                },
            )
            self.record(
                "material",
                "物料源数据表",
                row,
                mid,
                {
                    "MID": mid,
                    "名称": name,
                    "供应商料号": val(row, "C"),
                    "类型": val(row, "D"),
                    "现有库存": num(val(row, "E")),
                    "采购单价": num(val(row, "F")),
                    "原表货存总价": num(val(row, "G")),
                    "单位": None,
                    "币种": None,
                    "盘点日期": None,
                },
                mapped={"MID": mid, "物料版本ID": self.materials[mid]["version_id"]},
            )
        self.add(
            "rd.项目文件登记表",
            {
                "文件ID": self.file_id,
                "项目ID": None,
                "PID": None,
                "文件类型": "来源工作簿",
                "文件名": self.source.name,
                "相对路径": self.source.name,
                "SHA256": self.book["sha256"],
                "正式版本": None,
                "发布依据": None,
                "批准人ID": None,
                "生效日期": None,
            },
        )
        counts = Counter()
        for row in self.input_rows("BOM总表"):
            pid = val(row, "A")
            description = val(row, "E")
            qty = num(val(row, "D"))
            self.check("BOM source PID " + str(row["row_no"]), pid in self.products)
            self.check("BOM quantity " + str(row["row_no"]), qty is not None and Decimal(qty) > 0)
            candidates = names.get(description, [])
            mid = candidates[0] if len(candidates) == 1 else None
            cached = val(row, "C")
            status = val(row, "AO")
            self.check(
                "BOM name mapping agrees with saved result " + str(row["row_no"]),
                cached == mid if mid else cached in (None, "不匹配"),
            )
            counts[bool(mid)] += 1
            bid = uid("bom", self.file_id, pid)
            lineid = uid("bom-line", self.file_id, row["row_no"])
            self.add(
                "rd.BOM登记表",
                {
                    "BOM登记ID": bid,
                    "产品版本ID": self.products[pid]["version_id"],
                    "BOM版本": None,
                    "确认依据": None,
                },
            )
            self.add(
                "rd.BOM明细表",
                {
                    "BOM明细ID": lineid,
                    "BOM登记ID": bid,
                    "行号": row["row_no"] - 6,
                    "物料版本ID": self.materials[mid]["version_id"] if mid else None,
                    "单件用量": qty,
                    "单位ID": None,
                    "原始器件描述": description,
                    "位号": val(row, "F"),
                    "封装": val(row, "G"),
                    "厂家料号": val(row, "I"),
                    "供应商料号": val(row, "K"),
                    "来源文件ID": self.file_id,
                    "来源行号": row["row_no"],
                    "确认依据": None,
                    "替代适用条件": None,
                },
            )
            self.boms[pid].append({"mid": mid, "quantity": qty, "row": row["row_no"]})
            self.record(
                "bom",
                "BOM总表",
                row,
                pid + ":" + str(row["row_no"]),
                {
                    "PID": pid,
                    "原表MID": cached,
                    "单件用量": qty,
                    "Comment": description,
                    "Designator": val(row, "F"),
                    "Footprint": val(row, "G"),
                    "ManufacturerPart": val(row, "I"),
                    "SupplierPart": val(row, "K"),
                    "匹配状态": status,
                },
                derived={"MID": mid, "按原文精确匹配": mid is not None},
                mapped={"PID": pid, "MID": mid, "BOM登记ID": bid, "BOM明细ID": lineid},
            )
            if mid is None:
                self.issue(
                    "BOM物料未对应",
                    "未找到唯一同名物料，物料版本ID留空；不猜测别名或替代器件。Comment="
                    + str(description),
                    "BOM总表",
                    row["row_no"],
                )
            if val(row, "I") == "62" or val(row, "K") == "62":
                self.issue(
                    "来源料号待核",
                    "厂家或供应商料号包含“62”，照录来源，尚未核实其业务含义。",
                    "BOM总表",
                    row["row_no"],
                )
        self.check(
            "35 BOM rows, 18 exact matches and 17 unresolved",
            sum(counts.values()) == 35 and counts[True] == 18 and counts[False] == 17,
            dict(counts),
        )
        planned = {}
        plan_count = 0
        for row in self.input_rows("计划总览"):
            pid = val(row, "A")
            self.check("plan PID " + pid, pid in self.products and pid not in planned)
            immediate = num(val(row, "D"))
            reserve = num(val(row, "E"))
            total = (
                str(Decimal(immediate) + Decimal(reserve))
                if immediate is not None and reserve is not None
                else None
            )
            self.check(
                "plan saved total " + pid,
                total is None
                or num(val(row, "F")) is not None
                and Decimal(total) == Decimal(num(val(row, "F"))),
            )
            planned[pid] = total
            draft = None
            if total is not None and Decimal(total) > 0:
                draft = uid("draft", self.file_id, pid)
                plan_count += 1
                self.add(
                    "production.工单草稿表",
                    {
                        "草稿登记ID": draft,
                        "计划说明": packed(
                            {
                                "来源": str(self.source) + "#计划总览!" + str(row["row_no"]),
                                "PID": pid,
                                "产品名称": self.products[pid]["name"],
                                "计划立即生产": immediate,
                                "计划预备生产": reserve,
                                "计划合计": total,
                                "计划日期": None,
                                "说明": "源表生产意向；未下达、未完工，不作为实际产出或库存增加",
                            }
                        ),
                        "登记时间": None,
                        "负责人ID": None,
                        "状态": "待下达",
                    },
                )
            self.record(
                "plan",
                "计划总览",
                row,
                pid,
                {
                    "PID": pid,
                    "产品名称": val(row, "B"),
                    "原表库存": num(val(row, "C")),
                    "计划立即生产": immediate,
                    "计划预备生产": reserve,
                    "计划生产合计": num(val(row, "F")),
                    "计划后库存": num(val(row, "G")),
                    "计划生产成本": num(val(row, "K")),
                    "计划销售额": num(val(row, "L")),
                    "计划利润": num(val(row, "M")),
                    "计划日期": None,
                },
                derived={"计划合计": total},
                mapped={"PID": pid, "草稿登记ID": draft},
            )
        self.check(
            "four plans; 80 proposed units in two drafts",
            len(planned) == 4
            and sum(Decimal(v) for v in planned.values() if v is not None) == 80
            and plan_count == 2,
        )
        demands = {}
        for row in self.input_rows("物料需求"):
            mid = val(row, "A")
            self.check("demand MID " + mid, mid in self.materials and mid not in demands)
            expected = sum(
                Decimal(b["quantity"]) * Decimal(planned[pid])
                for pid, lines in self.boms.items()
                for b in lines
                if b["mid"] == mid and planned[pid] is not None
            )
            observed = num(val(row, "F"))
            self.check(
                "saved partial material demand " + mid,
                observed is not None and Decimal(observed) == expected,
            )
            demands[mid] = observed
            self.record(
                "demand",
                "物料需求",
                row,
                mid,
                {
                    "MID": mid,
                    "名称": val(row, "B"),
                    "现有库存": num(val(row, "E")),
                    "原表毛需求": observed,
                    "原表建议采购量": num(val(row, "G")),
                    "原表预计采购花销": num(val(row, "H")),
                    "原表预计余量": num(val(row, "I")),
                    "原表状态": val(row, "J"),
                    "需求计算说明": val(row, "K"),
                },
                derived={
                    "已对应物料的需求": str(expected),
                    "完整需求": None,
                    "完整建议采购量": None,
                    "未对应BOM行数": counts[False],
                },
                mapped={"MID": mid},
            )
        for row in self.input_rows("其他物品数据表"):
            iid = val(row, "A")
            self.record(
                "other",
                "其他物品数据表",
                row,
                iid,
                {
                    "IID": iid,
                    "名称": val(row, "B"),
                    "数量": num(val(row, "C")),
                    "单价": num(val(row, "D")),
                    "原表总金额": num(val(row, "E")),
                    "单位": None,
                    "币种": None,
                    "盘点日期": None,
                },
            )
        for row in self.input_rows("资产表"):
            label = val(row, "A")
            self.record(
                "asset",
                "资产表",
                row,
                label,
                {
                    "资产项目": label,
                    "原表数值": num(val(row, "B")),
                    "原表显示值": val(row, "B"),
                    "说明": val(row, "C"),
                    "确认金额": None,
                    "基准日期": None,
                },
            )
        for record in self.records:
            if record["record_kind"] == "product":
                pid = record["source_key"]
                lines = self.boms[pid]
                cost = None
                if lines and all(
                    b["mid"] and self.materials[b["mid"]]["price"] is not None for b in lines
                ):
                    cost = sum(
                        Decimal(b["quantity"]) * Decimal(self.materials[b["mid"]]["price"])
                        for b in lines
                    )
                observed = record["source_data"]["原料成本"]
                if cost is not None:
                    self.check(
                        "source material cost " + pid,
                        observed is not None
                        and abs(cost - Decimal(observed)) < Decimal("0.00000001"),
                    )
                else:
                    self.check(
                        "incomplete material cost remains unavailable " + pid, observed is None
                    )
                record["derived_data"].update(
                    完整原料成本=str(cost) if cost is not None else None,
                    未对应BOM行数=sum(b["mid"] is None for b in lines),
                )
        self.check("80 business source rows", len(self.records) == 80)
        self.issue(
            "版本及批准依据缺失",
            "文件名release2.0不是产品、物料或BOM的正式版本。版本、项目、批准和确认依据留空；导入记录不视为已核定BOM。",
        )
        self.issue(
            "规格单位缺失", "产品/物料规格、单位及部分类别没有独立来源字段，留空，不根据名称猜测。"
        )
        self.issue(
            "库存基准缺失",
            "库存是无盘点日期的来源快照；基准日期、仓库、库位、批次、所有权主体和单位不补造，不生成库存基准、库存变动或已核定余额。",
        )
        self.issue(
            "计划未实际执行",
            "两条正数计划仅登记为待下达草稿（50、30），不生成生产工单、完工、领料、采购或销售收入。零计划仍按来源保存为0。",
        )
        self.issue(
            "建议需求不完整",
            "物料需求仅覆盖能够匹配的18条BOM；17条未匹配时完整需求与完整采购建议留空，原表“库存充足”仅作为缓存原文。",
        )
        self.issue(
            "成本资产未核定",
            "库存价值、报价、采购单价、计划利润及资产数字均为来源/缓存快照，不写入成本、资产、收入确认或资金流水；币种和基准日期缺失保持为空。",
        )
        self.issue(
            "公式缓存边界",
            "保留全部公式和已保存值；独立复核匹配、BOM成本及计划需求，不运行Excel，也不把缓存值当作新的实时重算结果。",
        )
        return self

    def report(self):
        return {
            "version": VERSION,
            "source": str(self.source),
            "source_sha256": self.book["sha256"],
            "file_id": self.file_id,
            "sheets": [
                {k: s[k] for k in ("name", "dimension", "formula_count", "error_count")}
                for s in self.book["sheets"]
            ],
            "raw_rows": sum(len(s["rows"]) for s in self.book["sheets"]),
            "formula_count": sum(s["formula_count"] for s in self.book["sheets"]),
            "business_record_counts": dict(Counter(r["record_kind"] for r in self.records)),
            "table_counts": {t: len(rows) for t, rows in self.tables.items()},
            "nullable_fields": NULLABLE,
            "checks": self.controls,
            "exceptions": self.issues,
            "source_unchanged": digest(self.source.read_bytes()) == self.book["sha256"],
        }

    def sql(self, report, commit=False):
        statements = [
            "BEGIN;",
            "SET LOCAL lock_timeout='10s';",
            "SELECT pg_advisory_xact_lock(hashtext('easyerp-release2-import'));",
            (
                Path(__file__).resolve().parents[1] / "db" / "imports" / "import_release2.sql"
            ).read_text(encoding="utf-8"),
        ]
        for schema, table, col in NULLABLE:
            statements.append(
                "INSERT INTO erp_ops.source_import_nullability(schema_name,table_name,column_name,was_required) SELECT "
                + ",".join(sqlval(v) for v in (schema, table, col))
                + ",a.attnotnull FROM pg_attribute a WHERE a.attrelid="
                + sqlval(qualified(schema + "." + table))
                + "::regclass AND a.attname="
                + sqlval(col)
                + " AND NOT a.attisdropped ON CONFLICT DO NOTHING;"
            )
            statements.append(
                "ALTER TABLE "
                + qualified(schema + "." + table)
                + " ALTER COLUMN "
                + q(col)
                + " DROP NOT NULL;"
            )

        def insert(table, rows):
            if not rows:
                return
            cols = list(rows[0])
            pk = cols[0]
            target = qualified(table)
            for start in range(0, len(rows), 50):
                payload = sqlval(packed(rows[start : start + 50])) + "::jsonb"
                source = "jsonb_populate_recordset(NULL::" + target + "," + payload + ")"
                columns = ",".join(map(q, cols))
                statements.append(
                    "INSERT INTO "
                    + target
                    + " ("
                    + columns
                    + ") SELECT "
                    + columns
                    + " FROM "
                    + source
                    + " ON CONFLICT DO NOTHING;"
                )
                predicate = " OR ".join(
                    "t." + q(c) + " IS DISTINCT FROM x." + q(c) for c in cols if c != pk
                )
                statements.append(
                    "DO $verify$ BEGIN IF EXISTS (SELECT 1 FROM "
                    + source
                    + " x LEFT JOIN "
                    + target
                    + " t ON t."
                    + q(pk)
                    + "=x."
                    + q(pk)
                    + " WHERE t."
                    + q(pk)
                    + " IS NULL"
                    + (" OR " + predicate if predicate else "")
                    + ") THEN RAISE EXCEPTION 'Release import conflicts with existing data'; END IF; END $verify$;"
                )

        insert(
            "erp_ops.source_import_file",
            [
                {
                    "file_id": self.file_id,
                    "source_root": str(self.source.parent),
                    "relative_path": self.source.name,
                    "file_sha256": self.book["sha256"],
                    "size_bytes": self.book["size_bytes"],
                    "format_id": "release2-workbook-v1",
                    "header": {"sheet_header_rows": SHEETS},
                    "metadata": {
                        "sheets": report["sheets"],
                        "defined_names": self.book["defined_names"],
                        "note": "只读源工作簿；不执行单元格说明或公式；公式与缓存分别保留",
                    },
                }
            ],
        )
        for table in [
            "rd.产品主数据表",
            "rd.物料主数据表",
            "rd.产品版本表",
            "rd.物料版本表",
            "rd.项目文件登记表",
            "rd.BOM登记表",
            "rd.BOM明细表",
            "production.工单草稿表",
        ]:
            insert(table, list(self.tables[table].values()))
        insert("erp_ops.source_workbook_record", self.records)
        raw = []
        for sheet in self.book["sheets"]:
            for row in sheet["rows"]:
                mapped = self.mapped.get((sheet["name"], row["row_no"]), {})
                raw.append(
                    {
                        "row_id": uid("raw", self.file_id, sheet["name"], row["row_no"]),
                        "file_id": self.file_id,
                        "sheet_name": sheet["name"],
                        "row_no": row["row_no"],
                        "record_type": "detail"
                        if (sheet["name"], row["row_no"]) in self.mapped
                        else "formula_template"
                        if any(c["formula_meta"] is not None for c in row["cells"].values())
                        else "metadata",
                        "raw_values": row["cells"],
                        "mapped_ids": mapped,
                    }
                )
        insert("erp_ops.source_import_row", raw)
        insert("erp_ops.source_import_exception", self.issues)
        insert(
            "erp_ops.source_import_run",
            [
                {
                    "run_id": uid("run", VERSION, self.file_id),
                    "importer_version": VERSION,
                    "manifest_sha256": digest(
                        packed([{"source": str(self.source), "sha256": self.book["sha256"]}])
                    ),
                    "source_manifest": [
                        {"source": str(self.source), "sha256": self.book["sha256"]}
                    ],
                    "report": report,
                }
            ],
        )
        statements.append((self.project / "tests/structure.sql").read_text(encoding="utf-8"))
        statements.append("COMMIT;" if commit else "ROLLBACK;")
        return "\n".join(statements)


def signature(e):
    names = e.sql(
        "SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1,2"
    ).stdout.splitlines()
    parts = []
    for name in names:
        table = ".".join(q(x) for x in name.split("|"))
        parts.append(
            "SELECT "
            + sqlval(name)
            + " AS object,count(*) AS rows,md5(coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text)::text,'[]')) AS signature FROM "
            + table
            + " x"
        )
    rows = e.sql(
        "SELECT row_to_json(r) FROM (" + " UNION ALL ".join(parts) + ") r"
    ).stdout.splitlines()
    return {r["object"]: {k: r[k] for k in ("rows", "signature")} for r in map(json.loads, rows)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--trial", action="store_true")
    modes.add_argument("--apply", action="store_true")
    a = p.parse_args()
    plan = Plan(a.source, a.project_root).build()
    report = plan.report()
    if not report["source_unchanged"]:
        raise RuntimeError("Source changed during inspection")
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "preview.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sql = plan.sql(report, commit=a.apply)
    (a.out / ("prepared-import.sql" if a.apply else "trial-import.sql")).write_text(
        sql, encoding="utf-8"
    )
    if a.trial or a.apply:
        sys.path.insert(0, str(a.project_root / "tools"))
        from easyerp import ERP

        e = ERP()
        e.verify_files()
        if (
            Path(e.sql("SELECT current_setting('data_directory')").stdout.strip()).resolve()
            != e.data.resolve()
        ):
            raise RuntimeError("Unexpected target PostgreSQL cluster")
        before = signature(e)
        backup = e.backup(verify_data=True)
        (a.out / "business-before.json").write_text(
            json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        e.sql(sql)
        after = signature(e)
        if a.trial:
            if before != after:
                raise RuntimeError("Trial was not fully rolled back")
            report.update(trial="PASSED_AND_ROLLED_BACK", backup=str(backup))
        else:
            touched = {t.replace(".", "|") for t in plan.tables}
            unchanged = [t for t in before if t not in touched]
            if any(before[t] != after[t] for t in unchanged):
                raise RuntimeError("Pre-existing business data changed")
            report.update(
                applied_at_utc=datetime.now(timezone.utc).isoformat(),
                backup=str(backup),
                untouched_business_tables_verified=len(unchanged),
                structure=e.check(),
            )
        report["source_unchanged"] = digest(plan.source.read_bytes()) == report["source_sha256"]
        (a.out / ("result.json" if a.apply else "trial-result.json")).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "table_counts",
                    "business_record_counts",
                    "raw_rows",
                    "formula_count",
                    "source_unchanged",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("SOURCE CHECKS PASSED: " + str(len(report["checks"])))
    if a.trial:
        print("TRIAL PASSED AND ROLLED BACK")
    if a.apply:
        print("FORMALLY COMMITTED; backup=" + report["backup"])


if __name__ == "__main__":
    main()
