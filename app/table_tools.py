"""Whole-result table queries and atomic, versioned single-field batch changes."""

from decimal import Decimal
import hashlib
import json
import re

from data import Data, InvalidRequest, I, L
from entry import ManualEntry, EntryError, CHILDREN, qualified, text_sql

EXPORT_LIMIT = 10000
BATCH_LIMIT = 100
LIST_OBJECTS = {
    "orders": "sales.销售订单行表",
    "workorders": "production.生产工单表",
    "funds": "finance.资金流水表",
}
LIST_EXTRA = {
    "orders": {
        **dict.fromkeys(("客户ID", "渠道ID", "平台订单号", "订单状态", "客户名称", "产品名称", "版本名称", "单位名称", "履约进展"), "text"),
        "创建时间": "timestamp with time zone", "币种": "character(3)",
        **dict.fromkeys(("已登记发货数量", "待履约数量"), "numeric"),
    },
    "workorders": {
        **dict.fromkeys(("产品名称", "产品版本ID", "版本名称", "BOM登记ID", "BOM版本", "项目ID", "单位名称", "负责人"), "text"),
        **dict.fromkeys(("领退料事件数", "人员有效工时", "累计合格数量", "截至合格数量", "截至报废数量", "待完成数量"), "numeric"),
    },
    "funds": {
        **dict.fromkeys(("账户名", "主体ID", "公司名称"), "text"), "币种": "character(3)",
        **dict.fromkeys(("已核定用途金额", "已核定分摊金额", "用途差额", "分摊差额"), "numeric"),
        **dict.fromkeys(("已确认重复", "已确认内部划转"), "boolean"),
    },
}


def hidden(name):
    return name.startswith("_") or name.lower() in {"sha256", "long_id", "longid", "长id", "长编号"}


def protected_fields(obj):
    fields = {obj["pk"], "币种"}
    fields.update(c["name"] for c in obj["columns"] if c.get("automatic") or c.get("retired_reference") or hidden(c["name"]))
    fields.update(spec[1] for spec in CHILDREN.values() if spec[0] == obj["key"])
    return sorted(fields)


class TableData(Data):
    def explore(self, key, catalog, export=False):
        obj = self.object(key, catalog)
        columns = {c["name"]: c["type"] for c in obj["columns"]}
        if key == "production.库存盘点表" and "账面数量" in columns:
            columns["盘点差异"] = "numeric"
        elif key == "production.采购订单表":
            columns.update({"供应商": "text", "采购内容": "text"})
        elif key == "production.仓库档案表":
            columns["地点标识"] = "text"
        self._table_context = (obj, columns, export)
        try:
            return super().explore(key, catalog, export)
        finally:
            self._table_context = None

    def listing(self, kind, export=False):
        if kind not in LIST_OBJECTS:
            raise InvalidRequest("未知业务入口")
        catalog = self.catalog()
        obj = self.object(LIST_OBJECTS[kind], catalog)
        columns = {c["name"]: c["type"] for c in obj["columns"]}
        columns.update(LIST_EXTRA[kind])
        self._table_context = (obj, columns, export)
        try:
            return super().listing(kind, export)
        finally:
            self._table_context = None

    @staticmethod
    def operations(kind):
        common = ["eq", "ne", "is_null", "not_null"]
        if kind.startswith(("numeric", "integer", "bigint", "date", "timestamp")):
            return common + ["lt", "lte", "gt", "gte"]
        if kind == "boolean":
            return common
        return common + ["contains", "starts_with", "is_empty", "not_empty"]

    def controls(self, columns):
        try:
            raw_filters = self.p.get("table_filters", "[]")
            raw_sort = self.p.get("table_sort", "{}")
            if len(raw_filters) > 10000 or len(raw_sort) > 1000:
                raise ValueError()
            filters = json.loads(raw_filters, parse_float=Decimal)
            sort = json.loads(raw_sort)
        except (ValueError, TypeError, RecursionError):
            raise InvalidRequest("表格筛选或排序格式无效。")
        if not isinstance(filters, list) or len(filters) > 8 or not isinstance(sort, dict):
            raise InvalidRequest("最多同时使用 8 项字段筛选。")
        where = []
        for item in filters:
            if not isinstance(item, dict) or set(item) - {"field", "op", "value"}:
                raise InvalidRequest("字段筛选格式无效。")
            field, op = item.get("field"), item.get("op")
            if not isinstance(field, str) or field not in columns or hidden(field):
                raise InvalidRequest("筛选字段不可访问。")
            kind = columns[field]
            if op not in self.operations(kind):
                raise InvalidRequest("该字段不支持此筛选条件。")
            expr = "s." + I(field)
            if op in ("is_null", "not_null"):
                where.append(expr + (" IS NULL" if op == "is_null" else " IS NOT NULL"))
                continue
            if op in ("is_empty", "not_empty"):
                where.append(expr + ("::text=''" if op == "is_empty" else "::text<>''"))
                continue
            raw = item.get("value")
            if not isinstance(raw, (str, bool)) or isinstance(raw, str) and (len(raw) > 500 or "\x00" in raw):
                raise InvalidRequest("筛选值无效；金额和数量必须使用十进制文本。")
            if op in ("contains", "starts_with"):
                if not isinstance(raw, str):
                    raise InvalidRequest("文本筛选值无效。")
                find = f"strpos(lower({expr}::text),lower({text_sql(raw)}))"
                where.append(find + (">0" if op == "contains" else "=1"))
                continue
            if kind.startswith(("numeric", "integer", "bigint")):
                if not isinstance(raw, str) or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw) or len(raw) > 150:
                    raise InvalidRequest("数值筛选需要有效十进制文本。")
                expr += "::numeric"
                value = text_sql(raw) + "::numeric"
            elif kind.startswith(("date", "timestamp")) or kind == "boolean":
                col = {"name": field, "type": kind, "required": False, "automatic": False, "default": None, "options": []}
                value = ManualEntry.value(col, raw)
                if value is None:
                    raise InvalidRequest("请使用空值筛选条件。")
                value = text_sql(value) + "::" + kind
            else:
                if not isinstance(raw, str):
                    raise InvalidRequest("文本筛选值无效。")
                expr += "::text"
                value = text_sql(raw)
            where.append(expr + {"eq": "=", "ne": "<>", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}[op] + value)
        if set(sort) - {"field", "direction"}:
            raise InvalidRequest("排序格式无效。")
        order = None
        if sort:
            field, direction = sort.get("field"), sort.get("direction")
            if not isinstance(field, str) or field not in columns or hidden(field) or direction not in ("asc", "desc"):
                raise InvalidRequest("排序字段或方向无效。")
            expr = "s." + I(field)
            if columns[field].startswith(("numeric", "integer", "bigint")):
                expr += "::numeric"
            elif columns[field] == "jsonb":
                expr += "::text"
            order = expr + " " + direction.upper() + " NULLS LAST"
        return " AND ".join(where) or "TRUE", order

    def bundle(self, queries):
        context = getattr(self, "_table_context", None)
        if not context:
            return super().bundle(queries)
        obj, columns, export = context
        columns = {name: kind for name, kind in columns.items() if not hidden(name)}
        source, separator, suffix = queries["rows"].rpartition(" ORDER BY ")
        match = re.fullmatch(r"(.+) LIMIT \d+ OFFSET \d+", suffix, re.S)
        if not separator or not match:
            raise InvalidRequest("当前列表不支持全范围表格查询。")
        where, order = self.controls(columns)
        default_order = match[1].replace("x.", "s.")
        order = (order + ",s." + I(obj["pk"]) + " ASC") if order else default_order
        query = f"FROM ({source}) s WHERE {where}"
        projection = []
        for name, kind in columns.items():
            expr = "s." + I(name)
            if kind.startswith("numeric"):
                expr += "::text"
            projection.append(expr + " AS " + I(name))
        if not export:
            projection.append(f"(SELECT t.xmin::text FROM {I(obj['schema'])}.{I(obj['name'])} t WHERE t.{I(obj['pk'])}=s.{I(obj['pk'])}) AS _table_version")
        result = super().bundle({
            "rows": "SELECT " + ",".join(projection) + " " + query + f" ORDER BY {order} LIMIT {EXPORT_LIMIT + 1 if export else self.limit} OFFSET {0 if export else self.offset}",
            "total": "SELECT count(*) AS count " + query,
        })
        if export and int(result["total"][0]["count"]) > EXPORT_LIMIT:
            raise InvalidRequest("当前筛选超过 10000 条，请缩小范围后导出；未导出部分结果。")
        entry_shape = {**obj, "key": obj["schema"] + "." + obj["name"]}
        result["_table_tools"] = {
            "object": entry_shape["key"], "pk": obj["pk"], "scope": "all_matches",
            "columns": [{"name": name, "type": kind, "operations": self.operations(kind)} for name, kind in columns.items()],
            "protected_fields": protected_fields(entry_shape), "writable": not obj.get("retired", False),
            "export_limit": EXPORT_LIMIT, "batch_limit": BATCH_LIMIT,
        }
        return result


class BulkEntry(ManualEntry):
    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"request_id", "object", "field", "value", "records"}:
            raise EntryError("批量修改格式无效。")
        request = payload["request_id"]
        if not isinstance(request, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request):
            raise EntryError("保存请求标识无效。")
        obj = self.object(payload["object"])
        if obj.get("retired"):
            raise EntryError("历史主录不可批量修改。")
        field = payload["field"]
        if not isinstance(field, str) or field in protected_fields(obj):
            raise EntryError("此字段受保护，不能批量修改。")
        col = next((c for c in obj["columns"] if c["name"] == field), None)
        if col is None:
            raise EntryError("字段不可写。")
        records = payload["records"]
        if not isinstance(records, list) or not 1 <= len(records) <= BATCH_LIMIT:
            raise EntryError("一次请选择 1 至 100 条记录。")
        targets = []
        for record in records:
            if (not isinstance(record, dict) or set(record) != {"id", "version"}
                or not isinstance(record["id"], str) or not record["id"] or len(record["id"]) > 300
                or not isinstance(record["version"], str) or not re.fullmatch(r"\d{1,20}", record["version"])):
                raise EntryError("批量记录缺少原版本，请重新选择。", 409)
            targets.append((self.ids.resolve(obj["key"], record["id"]), record["version"]))
        if len({key for key, _ in targets}) != len(targets):
            raise EntryError("同一记录不能在批次中重复。")
        if col["required"] and payload["value"] in (None, ""):
            raise EntryError("该字段为必填项，批量修改不能清空或改变结构。", fields=[field])
        value = self.prepare(obj, {field: payload["value"]}, False)[field]
        if payload["value"] == "" and (col["type"] == "text" or col["type"].startswith("character")):
            value = ""
        if obj["key"] == "finance.会计凭证表" and field == "状态" and value == "已过账":
            raise EntryError("会计凭证须逐笔核对后过账，不能批量过账。")
        digest = hashlib.sha256(json.dumps({"mode": self.mode, "bulk": payload}, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        expression = "NULL" if value is None else "(" + text_sql(value) + ")::" + col["type"]
        sql = [
            "BEGIN; SET LOCAL statement_timeout='12s'; SET LOCAL lock_timeout='4s'; SET LOCAL standard_conforming_strings=on;",
            "DO $bulk$ DECLARE old jsonb; saved jsonb; row_version text; existing_hash text; response jsonb; rows jsonb := '[]'::jsonb; changes jsonb := '[]'::jsonb; BEGIN",
            f"PERFORM pg_advisory_xact_lock(hashtextextended({L('manual-entry:' + request)},0));",
            f"SELECT payload_hash,result INTO existing_hash,response FROM erp_ops.frontend_entry_audit WHERE request_id={L(request)};",
            f"IF FOUND THEN IF existing_hash<>{L(digest)} THEN RAISE EXCEPTION 'request_reused' USING ERRCODE='22023'; END IF; RETURN; END IF;",
        ]
        for key, version in sorted(targets):
            sql.extend([
                f"SELECT to_jsonb(t),xmin::text INTO old,row_version FROM {qualified(obj)} t WHERE {I(obj['pk'])}={text_sql(key)} FOR UPDATE;",
                "IF NOT FOUND THEN RAISE EXCEPTION 'record_missing' USING ERRCODE='P0002'; END IF;",
                f"IF row_version<>{L(version)} THEN RAISE EXCEPTION 'record_changed' USING ERRCODE='40001'; END IF;",
                f"UPDATE {qualified(obj)} AS t SET {I(field)}={expression} WHERE {I(obj['pk'])}={text_sql(key)} RETURNING to_jsonb(t),t.xmin::text INTO saved,row_version;",
                f"rows := rows || jsonb_build_array(jsonb_build_object('object',{L(obj['key'])},'id',saved->{L(obj['pk'])},'values',saved,'version',row_version));",
                f"changes := changes || jsonb_build_array(jsonb_build_object('object',{L(obj['key'])},'operation','update','before',old,'after',saved));",
            ])
        sql.extend([
            f"response := jsonb_build_object('request_id',{L(request)},'records',rows,'mode',{L(self.mode)},'field',{L(field)},'count',jsonb_array_length(rows),'atomic',true);",
            f"INSERT INTO erp_ops.frontend_entry_audit(request_id,payload_hash,changes,result) VALUES ({L(request)},{L(digest)},changes,response);",
            "END $bulk$;",
            f"SELECT result FROM erp_ops.frontend_entry_audit WHERE request_id={L(request)}; COMMIT;",
        ])
        result = self.data.erp.sql("\\set VERBOSITY verbose\n" + "\n".join(sql), db=self.db, role="easyerp_app", ok=False)
        if result.returncode:
            try:
                self.db_error(result.stderr)
            except EntryError as error:
                raise EntryError("整批未保存，所有修改已回滚。" + str(error), error.status, error.fields) from None
        response = json.loads(result.stdout.strip(), parse_float=Decimal)
        for row in response["records"]:
            row["id"] = self.ids.resolve(obj["key"], row["id"])
            row["values"] = self.ids.values(obj, row["values"])
            self.string_numbers(obj, row["values"])
        return response
