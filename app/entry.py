"""Validated manual entry into authoritative SQL tables, with atomic audit records."""

from datetime import date, datetime
from decimal import Decimal, localcontext
import hashlib
import json
import re
import threading
import time
import uuid

from data import Data, InvalidRequest, L, I
from workspace_rules import annotate
from identifiers import Identifiers, RULES, valid as valid_id

SCHEMAS = ("sales", "production", "finance", "rd", "legal", "analysis")
CHILDREN = {
    "sales.销售订单登记表": ("sales.销售订单行表", "订单ID", "商品明细", 1),
    "production.采购订单表": ("production.采购订单行表", "采购单ID", "采购明细", 0),
    "production.仓库档案表": ("production.库位档案表", "仓库ID", "地点标识", 0),
    "rd.BOM登记表": ("rd.BOM明细表", "BOM登记ID", "BOM 明细", 1),
    "finance.会计凭证表": ("finance.会计分录表", "凭证ID", "会计分录", 2),
}
PREFERRED = {
    "sales": [
        "销售订单登记表",
        "客户档案表",
        "渠道档案表",
        "售后事件表",
        "客户需求表",
        "商品对应表",
        "销售合同表",
    ],
    "inventory": [
        "采购订单表",
        "供应商档案表",
        "到货记录表",
        "验收记录表",
        "库存变动表",
        "仓库档案表",
        "库位档案表",
        "库存基准核定表",
        "库存盘点表",
    ],
    "production": [
        "生产工单表",
        "工单草稿表",
        "工单订单对应表",
        "生产领退料表",
        "生产工时表",
        "完工记录表",
        "报废记录表",
        "质量检验表",
        "设备档案表",
        "委外物料流转表",
    ],
    "finance": [
        "资金流水表",
        "资金用途核定表",
        "费用归属表",
        "发票登记表",
        "会计凭证表",
        "资金账户档案表",
        "人员档案表",
        "会计科目表",
        "会计政策表",
        "账户期间余额表",
    ],
    "rd": [
        "项目登记表",
        "产品主数据表",
        "产品版本表",
        "物料主数据表",
        "物料版本表",
        "计量单位表",
        "BOM登记表",
        "项目文件登记表",
        "发布批次表",
        "设计变更与验证表",
    ],
    "legal": [
        "公司主体档案表",
        "法规登记表",
        "法律文件登记表",
        "合同审阅表",
        "履约提示表",
        "合规自查表",
        "整改跟踪表",
        "证据对应表",
    ],
    "analysis": [
        "分析报告登记表",
        "数学模型库",
        "指标定义表",
        "指标计算表",
        "数据引用登记表",
        "意见与规划总表",
        "意见复盘表",
    ],
}
_CACHE = {}
_LOCK = threading.Lock()


class EntryError(InvalidRequest):
    def __init__(self, message, status=400, fields=None):
        super().__init__(message)
        self.status = status
        self.fields = fields or []


def text_sql(value):
    # Hex-encoded UTF-8 is a data literal even for newlines or psql metacharacters.
    return "convert_from(decode('" + value.encode("utf-8").hex() + "','hex'),'UTF8')"


def qualified(obj):
    return I(obj["schema"]) + "." + I(obj["name"])


class ManualEntry:
    def __init__(self, params=None):
        self.data = Data(params)
        self.mode = self.data.mode
        self.db = self.data.db
        self.cache_key = (str(self.data.erp.data.resolve()), self.data.erp.c["port"], self.db)
        self.ids = Identifiers(self.data)

    def catalog(self):
        with _LOCK:
            cached = _CACHE.get(self.cache_key)
            if cached and time.monotonic() - cached[0] < 60:
                return cached[1]
        result = self.data.bundle(
            {
                "tables": """SELECT n.nspname AS schema,c.relname AS name,
            (SELECT a.attname FROM pg_constraint p JOIN pg_attribute a ON a.attrelid=p.conrelid AND a.attnum=p.conkey[1]
             WHERE p.conrelid=c.oid AND p.contype='p' AND cardinality(p.conkey)=1) AS pk,
            (SELECT json_agg(json_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
             'required',a.attnotnull,'automatic',a.attidentity<>'' OR a.attgenerated<>'',
             'default',pg_get_expr(d.adbin,d.adrelid)) ORDER BY a.attnum)
             FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
             WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS columns,
            (SELECT coalesce(json_agg(json_build_object('name',p.conname,'expression',pg_get_constraintdef(p.oid))),'[]'::json)
             FROM pg_constraint p WHERE p.conrelid=c.oid AND p.contype='c') AS checks
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('sales','production','finance','rd','legal','analysis') AND c.relkind='r'
            ORDER BY n.nspname,c.relname""",
                "references": """SELECT ns.nspname AS schema,t.relname AS name,a.attname AS field,
            tn.nspname||'.'||tt.relname AS target,ta.attname AS target_field
            FROM pg_constraint p JOIN pg_class t ON t.oid=p.conrelid JOIN pg_namespace ns ON ns.oid=t.relnamespace
            JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=p.conkey[1]
            JOIN pg_class tt ON tt.oid=p.confrelid JOIN pg_namespace tn ON tn.oid=tt.relnamespace
            JOIN pg_attribute ta ON ta.attrelid=tt.oid AND ta.attnum=p.confkey[1]
            WHERE p.contype='f' AND ns.nspname IN ('sales','production','finance','rd','legal','analysis')""",
            }
        )
        references = {}
        for reference in result["references"]:
            references.setdefault(
                (reference["schema"], reference["name"], reference["field"]), reference
            )
        objects = {}
        for obj in result["tables"]:
            if not obj["pk"]:
                continue
            obj["key"] = obj["schema"] + "." + obj["name"]
            annotate(obj)
            obj["id_prefix"] = RULES[obj["key"]]["prefix"]
            obj["one_of"] = []
            for check in obj["checks"]:
                match = re.search(r"num_nonnulls\((.*?)\)\s*=\s*1", check["expression"])
                if match:
                    obj["one_of"].append(re.findall(r'"([^"]+)"', match[1]))
            obj["children"] = None
            if obj["key"] in CHILDREN:
                child, field, label, minimum = CHILDREN[obj["key"]]
                obj["children"] = {
                    "object": child,
                    "parent_field": field,
                    "label": label,
                    "minimum": minimum,
                }
            for col in obj["columns"]:
                col["reference"] = references.get((obj["schema"], obj["name"], col["name"]))
                col["options"] = []
                for check in obj["checks"]:
                    pattern = r'"' + re.escape(col["name"]) + r'"\s*=\s*ANY\s*\(\s*ARRAY\[(.*?)\]'
                    match = re.search(pattern, check["expression"], re.S)
                    if match:
                        col["options"] = [
                            v.replace("''", "'") for v in re.findall(r"'((?:''|[^'])*)'", match[1])
                        ]
                col["allow_empty_selection"] = bool(
                    col["name"] != obj["pk"]
                    and not col["automatic"]
                    and (col["reference"] or col["options"] or col["type"] == "boolean")
                )
            obj["rules"] = self.rules(obj)
            objects[obj["key"]] = obj
        for obj in objects.values():
            for col in obj["columns"]:
                reference = col.get("reference")
                col["retired_reference"] = bool(
                    reference and objects.get(reference["target"], {}).get("retired")
                )
        with _LOCK:
            _CACHE[self.cache_key] = (time.monotonic(), objects)
        return objects

    @staticmethod
    def rules(obj):
        rules = []
        for check in obj["checks"]:
            expr = check["expression"]
            match = re.search(r"num_nonnulls\((.*?)\)\s*([<=]+)\s*([0-9]+)", expr)
            if match:
                names = re.findall(r'"([^"]+)"', match[1])
                if match[3] == "1":
                    rules.append(
                        "、".join(names)
                        + ("：必须且只能填写一项。" if match[2] == "=" else "：最多填写一项。")
                    )
            elif "ANY" not in expr:
                clean = expr.replace("CHECK ", "").replace('"', "")
                clean = re.sub(r"::[a-z]+", "", clean)
                rules.append(clean)
        return rules

    def object(self, key):
        if not isinstance(key, str):
            raise EntryError("该对象不是可录入的业务主录。")
        catalog = self.catalog()
        if key not in catalog:
            raise EntryError("该对象不是可录入的业务主录。")
        return catalog[key]

    def label_expression(self, obj, alias="t", depth=0, path=()):
        names = [
            "名称",
            "客户名称",
            "公司名称",
            "姓名",
            "单位名称",
            "账户名",
            "渠道名称",
            "项目名称",
            "版本名称",
            "报告名称",
            "数据集名称",
            "指标名称",
            "科目名称",
            "文件名",
            "地点",
            "库位代码",
            "商品标题",
            "分析问题",
            "主题",
            "原商品信息",
            "交易摘要",
            "版本号",
        ]
        available = {
            c["name"] for c in obj["columns"] if c["name"] != obj["pk"] and not c["reference"]
        }
        parts = [f"nullif({alias}.{I(n)}::text,'')" for n in names if n in available][:2]
        if depth < 2 and len(parts) < 2:
            for index, col in enumerate(obj["columns"]):
                ref = col["reference"]
                if not ref or ref["target"] in path or col.get("retired_reference"):
                    continue
                target = self.object(ref["target"])
                child = "n" + str(depth) + "_" + str(index)
                label = self.label_expression(target, child, depth + 1, (*path, obj["key"]))
                parts.append(
                    f"(SELECT {label} FROM {qualified(target)} {child} WHERE {child}.{I(target['pk'])}={alias}.{I(col['name'])})"
                )
                if len(parts) >= 2:
                    break
        for col in obj["columns"]:
            if len(parts) >= 3:
                break
            if col["type"] in ("date", "timestamp with time zone"):
                parts.append(f"{alias}.{I(col['name'])}::text")
        body = "concat_ws(' · '," + ",".join(parts) + ")" if parts else "''"
        return f"coalesce(nullif({body},''),{L('未命名的' + obj.get('label', obj['name']))})"

    def choices(self, key, search="", selected="", offset=0):
        obj = self.object(key)
        try:
            offset = int(offset)
        except (ValueError, TypeError):
            raise EntryError("无效页码。")
        if not 0 <= offset <= 100000:
            raise EntryError("无效页码。")
        selected = self.ids.resolve(key, selected)
        expression = self.label_expression(obj)
        cte = f"WITH named AS (SELECT t.{I(obj['pk'])} AS value,left({expression},220) AS name FROM {qualified(obj)} t), labeled AS (SELECT value,name,count(*) OVER(PARTITION BY name) AS n,row_number() OVER(PARTITION BY name ORDER BY value) AS position FROM named) "
        projection = (
            "value,name||CASE WHEN n>1 THEN '（第'||position::text||'项）' ELSE '' END AS label"
        )
        search = str(search).strip()[:150]
        where = (
            "TRUE"
            if not search
            else f"strpos(lower(name),lower({L(search)}))>0 OR strpos(lower(value),lower({L(search)}))>0"
        )
        result = self.data.rows(
            cte
            + f"SELECT {projection} FROM labeled WHERE {where} ORDER BY value LIMIT 50 OFFSET {offset}"
        )
        more = len(result) >= 50
        if selected and not any(r["value"] == selected for r in result):
            result += self.data.rows(
                cte + f"SELECT {projection} FROM labeled WHERE value={L(selected)}"
            )
        return {"rows": result, "target": key, "more": more}

    def options(self, key, field, search="", selected="", offset=0):
        obj = self.object(key)
        col = next((c for c in obj["columns"] if c["name"] == field), None)
        if not col or not col["reference"]:
            raise EntryError("该字段没有可选择的关联主录。")
        return self.choices(col["reference"]["target"], search, selected, offset)

    def record(self, key, value, include_children=True):
        obj = self.object(key)
        value = self.ids.resolve(key, value)
        if not isinstance(value, str) or len(value) > 300:
            raise EntryError("无效记录编号。")
        expression = "to_jsonb(t)"
        for col in obj["columns"]:
            if col["type"] == "jsonb":
                field = "t." + I(col["name"])
                expression += f" || jsonb_build_object({L(col['name'])},CASE WHEN {field} IS NULL THEN NULL ELSE to_jsonb({field}::text) END)"
        rows = self.data.rows(
            f"SELECT ({expression}) AS values,xmin::text AS version FROM {qualified(obj)} t WHERE {I(obj['pk'])}={L(value)}"
        )
        if not rows:
            raise EntryError("记录不存在或已被其他操作移除。", 404)
        self.string_numbers(obj, rows[0]["values"])
        if include_children and obj["children"]:
            spec = obj["children"]
            child = self.object(spec["object"])
            ids = self.data.rows(
                f"SELECT {I(child['pk'])} AS id FROM {qualified(child)} WHERE {I(spec['parent_field'])}={L(value)} ORDER BY {I(child['pk'])}"
            )
            rows[0]["children"] = [
                {"object": child["key"], "id": r["id"], **self.record(child["key"], r["id"])}
                for r in ids
            ]
        return rows[0]

    @staticmethod
    def string_numbers(obj, values):
        for col in obj["columns"]:
            if col["type"].startswith("numeric") and values.get(col["name"]) is not None:
                values[col["name"]] = str(values[col["name"]])

    @staticmethod
    def value(col, raw):
        name, kind = col["name"], col["type"]
        if raw is None or raw == "":
            if col["required"] and not col["default"] and not col["automatic"] and not col.get("allow_empty_selection"):
                raise EntryError(f"请填写「{name}」。", fields=[name])
            return None
        if col["automatic"]:
            raise EntryError(f"「{name}」由数据库生成，不能手工填写。", fields=[name])
        if kind.startswith("numeric"):
            if (
                isinstance(raw, bool)
                or not isinstance(raw, (str, int, Decimal))
                or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", str(raw))
                or len(str(raw)) > 150
            ):
                raise EntryError(f"「{name}」请填写有效十进制数。", fields=[name])
            value = Decimal(str(raw))
            shape = re.fullmatch(r"numeric\((\d+),(\d+)\)", kind)
            if shape:
                precision, scale = map(int, shape.groups())
                with localcontext() as ctx:
                    ctx.prec = 180
                    if value != value.quantize(Decimal(1).scaleb(-scale)) or (
                        value != 0 and value.adjusted() + 1 > precision - scale
                    ):
                        raise EntryError(
                            f"「{name}」最多 {precision - scale} 位整数、{scale} 位小数，不会自动四舍五入。",
                            fields=[name],
                        )
            return str(value)
        if kind == "integer":
            if (
                isinstance(raw, bool)
                or not re.fullmatch(r"-?\d+", str(raw))
                or len(str(raw)) > 12
                or not -(2**31) <= int(raw) < 2**31
            ):
                raise EntryError(f"「{name}」请填写有效整数。", fields=[name])
            return str(int(raw))
        if kind == "boolean":
            if isinstance(raw, bool):
                return "true" if raw else "false"
            if isinstance(raw, str) and raw in ("true", "false"):
                return raw
            raise EntryError(f"「{name}」请选择是或否。", fields=[name])
        if not isinstance(raw, str) or "\x00" in raw or len(raw) > 20000:
            raise EntryError(f"「{name}」内容无效或过长。", fields=[name])
        if col["required"] and not raw.strip():
            raise EntryError(f"请填写「{name}」。", fields=[name])
        if kind == "date":
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                    raise ValueError()
                date.fromisoformat(raw)
            except ValueError:
                raise EntryError(f"「{name}」请填写有效日期。", fields=[name])
        elif kind == "timestamp with time zone":
            try:
                if datetime.fromisoformat(raw.replace("Z", "+00:00")).utcoffset() is None:
                    raise ValueError()
            except ValueError:
                raise EntryError(f"「{name}」需要有效时间及时区。", fields=[name])
        elif kind.startswith("character("):
            maximum = int(re.search(r"\d+", kind)[0])
            if len(raw) > maximum:
                raise EntryError(f"「{name}」最多 {maximum} 个字符。", fields=[name])
        elif kind == "jsonb":
            try:
                json.loads(
                    raw,
                    parse_float=Decimal,
                    parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
                )
            except (ValueError, TypeError, RecursionError):
                raise EntryError(f"「{name}」需要有效 JSON 文本。", fields=[name])
        if name == "币种" and not re.fullmatch("[A-Z]{3}", raw):
            raise EntryError("币种请使用三个大写字母，例如 CNY。", fields=[name])
        if col["options"] and raw not in col["options"]:
            raise EntryError(f"「{name}」请选择列表中的值。", fields=[name])
        return raw

    def prepare(self, obj, values, create, parent=None, allocation_key=None):
        if not isinstance(values, dict):
            raise EntryError("录入内容格式无效。")
        columns = {c["name"]: c for c in obj["columns"]}
        if set(values) - set(columns):
            raise EntryError("提交内容包含不支持的字段。")
        values = self.ids.values(obj, values)
        if any(
            c.get("retired_reference") and values.get(c["name"]) not in (None, "")
            for c in obj["columns"]
        ):
            raise EntryError("交付与业务引用请使用当前有效主录；旧流程引用仅保留历史追溯。")
        if parent:
            field, key = parent
            if values.get(field) not in (None, "", key):
                raise EntryError("明细的上级记录编号不一致。", fields=[field])
            values[field] = key
        if create and not values.get(obj["pk"]):
            values[obj["pk"]] = self.ids.allocate(obj["key"], [allocation_key or uuid.uuid4().hex])[
                0
            ]
        if create:
            # An omitted selector means unknown; non-selector SQL defaults remain unchanged.
            for col in obj["columns"]:
                if col.get("allow_empty_selection"):
                    values.setdefault(col["name"], None)
            missing = [
                c["name"]
                for c in obj["columns"]
                if c["required"]
                and not c.get("allow_empty_selection")
                and not c["automatic"]
                and not c["default"]
                and c["name"] not in values
            ]
            if missing:
                raise EntryError("请填写必填项：" + "、".join(missing), fields=missing)
        result = {name: self.value(columns[name], raw) for name, raw in values.items()}
        if create and not valid_id(obj["key"], result[obj["pk"]]):
            raise EntryError(
                "记录编号须为 " + RULES[obj["key"]]["prefix"] + " 加至少三位大写36进制流水。",
                fields=[obj["pk"]],
            )
        return result

    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) - {
            "request_id",
            "object",
            "operation",
            "values",
            "id",
            "version",
            "children",
        }:
            raise EntryError("提交格式无效。")
        request = payload.get("request_id", "")
        if not isinstance(request, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request):
            raise EntryError("保存请求标识无效，请重新打开表单。")
        obj = self.object(payload.get("object"))
        if obj.get("retired"):
            raise EntryError(
                "该记录已退出业务录入，请使用企业计划、工作流或审计月报；历史记录仍可追溯。"
            )
        operation = payload.get("operation", "create")
        if operation not in ("create", "update"):
            raise EntryError("只支持新建和修改业务记录。")
        create = operation == "create"
        incoming = payload.get("values")
        if not isinstance(incoming, dict):
            raise EntryError("录入内容格式无效。")
        if not create and (
            not isinstance(payload.get("id"), str)
            or len(payload["id"]) > 300
            or not re.fullmatch(r"\d+", str(payload.get("version", "")))
        ):
            raise EntryError("缺少当前记录版本，请重新读取后修改。", 409)
        if not create and obj["pk"] in incoming:
            raise EntryError("记录编号不能修改。", fields=[obj["pk"]])
        children = payload.get("children", [])
        if not isinstance(children, list) or len(children) > 100:
            raise EntryError("一次最多录入 100 条明细。")
        if create and obj["key"] == "production.仓库档案表" and not children:
            children = [{"object": "production.库位档案表", "values": {"库位代码": "默认"}}]
        spec = obj["children"]
        if (children and not spec) or (create and spec and len(children) < spec["minimum"]):
            raise EntryError("明细类型或明细数量不符合要求。")
        record_id = self.ids.resolve(obj["key"], payload.get("id"))
        values = self.prepare(obj, incoming, create, allocation_key=request + ":parent")
        if not create and not values and not payload.get("children"):
            raise EntryError("尚未修改任何字段。")
        operations = [(obj, values, create, record_id, payload.get("version"))]
        if children:
            child_obj = self.object(spec["object"])
            for child_index, child in enumerate(children):
                if (
                    not isinstance(child, dict)
                    or set(child) - {"object", "values", "operation", "id", "version"}
                    or child.get("object") != spec["object"]
                ):
                    raise EntryError("该业务不接受此类明细。")
                if not isinstance(child.get("values"), dict):
                    raise EntryError("明细录入内容格式无效。")
                child_create = child.get("operation", "create") == "create"
                if child.get("operation", "create") not in ("create", "update") or (
                    create and not child_create
                ):
                    raise EntryError("新主录只接受新建明细。")
                if not child_create and (
                    not isinstance(child.get("id"), str)
                    or len(child["id"]) > 300
                    or not re.fullmatch(r"\d+", str(child.get("version", "")))
                    or child_obj["pk"] in child.get("values", {})
                ):
                    raise EntryError("明细缺少有效版本或包含不可修改的编号。", 409)
                child_values = self.prepare(
                    child_obj,
                    child.get("values"),
                    child_create,
                    (spec["parent_field"], values[obj["pk"]] if create else record_id),
                    allocation_key=request + ":child:" + str(child_index),
                )
                operations.append(
                    (
                        child_obj,
                        child_values,
                        child_create,
                        self.ids.resolve(child_obj["key"], child.get("id")),
                        child.get("version"),
                    )
                )
        digest = hashlib.sha256(
            json.dumps(
                {"mode": self.mode, "payload": payload},
                ensure_ascii=False,
                sort_keys=True,
                default=str,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        sql = [
            "BEGIN; SET LOCAL statement_timeout='12s'; SET LOCAL lock_timeout='4s'; SET LOCAL standard_conforming_strings=on;",
            "DO $manual$ DECLARE old jsonb; saved jsonb; row_version text; existing_hash text; response jsonb; rows jsonb := '[]'::jsonb; changes jsonb := '[]'::jsonb; BEGIN",
            f"PERFORM pg_advisory_xact_lock(hashtextextended({L('manual-entry:' + request)},0));",
            f"SELECT payload_hash,result INTO existing_hash,response FROM erp_ops.frontend_entry_audit WHERE request_id={L(request)};",
            f"IF FOUND THEN IF existing_hash<>{L(digest)} THEN RAISE EXCEPTION 'request_reused' USING ERRCODE='22023'; END IF; RETURN; END IF;",
        ]
        for target, vals, insert, key, version in operations:
            sql.append("old := NULL;")
            if not insert:
                sql += [
                    f"SELECT to_jsonb(t),xmin::text INTO old,row_version FROM {qualified(target)} t WHERE {I(target['pk'])}={text_sql(key)} FOR UPDATE;",
                    "IF NOT FOUND THEN RAISE EXCEPTION 'record_missing' USING ERRCODE='P0002'; END IF;",
                    f"IF row_version<>{L(str(version))} THEN RAISE EXCEPTION 'record_changed' USING ERRCODE='40001'; END IF;",
                ]
                if target["key"] != obj["key"]:
                    sql.append(
                        f"IF old->>{L(obj['children']['parent_field'])} IS DISTINCT FROM {L(record_id)} THEN RAISE EXCEPTION 'child_parent_mismatch' USING ERRCODE='23514'; END IF;"
                    )
            expressions = {
                name: "NULL"
                if raw is None
                else "("
                + text_sql(raw)
                + ")::"
                + next(c["type"] for c in target["columns"] if c["name"] == name)
                for name, raw in vals.items()
            }
            null_selections = [
                c["name"] for c in target["columns"]
                if c.get("allow_empty_selection") and c["name"] in vals and vals[c["name"]] is None
            ]
            if null_selections and (
                any(c["required"] and c["name"] in null_selections for c in target["columns"])
                or any(set(group) <= set(null_selections) for group in target["one_of"])
            ):
                # The existing narrowly scoped nullability helper changes only these fields,
                # atomically with the record and audit. PKs and nonblank-value checks stay intact.
                sql.append(
                    "PERFORM erp_ops.csv_allow_missing_fields("
                    + L(qualified(target)) + "::regclass,ARRAY["
                    + ",".join(L(name) for name in null_selections)
                    + "]::text[]," + L("entry2-" + digest) + ");"
                )
            if insert:
                query = (
                    f"INSERT INTO {qualified(target)} AS t ("
                    + ",".join(I(n) for n in vals)
                    + ") VALUES ("
                    + ",".join(expressions.values())
                    + ")"
                )
            elif expressions:
                query = (
                    f"UPDATE {qualified(target)} AS t SET "
                    + ",".join(I(n) + "=" + v for n, v in expressions.items())
                    + f" WHERE {I(target['pk'])}={text_sql(key)}"
                )
            else:
                sql += [
                    "saved := old;",
                    f"rows := rows || jsonb_build_array(jsonb_build_object('object',{L(target['key'])},'id',saved->{L(target['pk'])},'values',saved,'version',row_version));",
                ]
                continue
            sql += [
                query + " RETURNING to_jsonb(t),t.xmin::text INTO saved,row_version;",
                f"rows := rows || jsonb_build_array(jsonb_build_object('object',{L(target['key'])},'id',saved->{L(target['pk'])},'values',saved,'version',row_version));",
                f"changes := changes || jsonb_build_array(jsonb_build_object('object',{L(target['key'])},'operation',{L('create' if insert else 'update')},'before',old,'after',saved));",
            ]
        sql += [
            f"response := jsonb_build_object('request_id',{L(request)},'records',rows,'mode',{L(self.mode)});",
            f"INSERT INTO erp_ops.frontend_entry_audit(request_id,payload_hash,changes,result) VALUES ({L(request)},{L(digest)},changes,response);",
            "END $manual$;",
            f"SELECT result FROM erp_ops.frontend_entry_audit WHERE request_id={L(request)}; COMMIT;",
        ]
        result = self.data.erp.sql(
            "\\set VERBOSITY verbose\n" + "\n".join(sql), db=self.db, role="easyerp_app", ok=False
        )
        if result.returncode:
            self.db_error(result.stderr)
        response = json.loads(result.stdout.strip(), parse_float=Decimal)
        for row in response["records"]:
            row["id"] = self.ids.resolve(row["object"], row["id"])
            row["values"] = self.ids.values(self.object(row["object"]), row["values"])
            self.string_numbers(self.object(row["object"]), row["values"])
        return response

    def db_error(self, error):
        if "40001" in error:
            raise EntryError(
                "这条记录已被 SQL 或其他页面修改，请重新读取后再保存。你的输入仍保留在表单中。", 409
            )
        if "P0002" in error:
            raise EntryError("记录已不存在，请重新读取。", 409)
        if "request_reused" in error:
            raise EntryError("同一次保存标识对应的内容发生了变化，请重新提交。", 409)
        if "23505" in error:
            raise EntryError("该编号或业务组合已存在，请检查重复记录后修改。", 409)
        if "23503" in error:
            raise EntryError("关联记录不存在或已被移除，请先新建关联资料，或重新选择。")
        if "23502" in error:
            raise EntryError("仍有数据库必填项未填写，请检查主录和明细。")
        if "23514" in error:
            raise EntryError(
                "保存未完成：数量、金额、状态或会计凭证不符合业务约束，请核对表单中的填写规则。"
            )
        if any(code in error for code in ("22001", "22003", "22P02", "22007", "22008")):
            raise EntryError("字段格式、数值精度或日期超出数据库允许范围。")
        raise EntryError("暂时无法保存，请检查本机数据库服务或日志后重试；本次没有部分写入。", 503)
