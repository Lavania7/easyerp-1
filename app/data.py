"""Read-only queries over authoritative business tables."""

from pathlib import Path
from datetime import date
from decimal import Decimal
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from easyerp import ERP, literal as L, ident as I
from business_queries import expand_queries
from workspace_rules import annotate

DEPARTMENTS = {
    "finance": "财务",
    "legal": "法务",
    "production": "采购与生产",
    "rd": "研发",
    "sales": "销售",
    "analysis": "分析",
}
DATE_FIELDS = {"sales": "订单创建日期", "production": "计划开始日期", "finance": "资金发生日期"}

# One actual date column per object, in documented business-date priority order.
# No NULL substitution and no dates inferred from filenames or unrelated records.
DATE_PRIORITY = (
    "发生时间",
    "发生日期",
    "日期",
    "创建时间",
    "创建日期",
    "验收时间",
    "到货时间",
    "发货时间",
    "执行时间",
    "处理时间",
    "交付时间",
    "计算时间",
    "生成时间",
    "生成日期",
    "登记时间",
    "登记日期",
    "复盘日期",
    "决定日期",
    "审阅日期",
    "检查日期",
    "提供时间",
    "接收时间",
    "缴退日期",
    "申报日期",
    "盘点日期",
    "基准日期",
    "购置日期",
    "导出时间",
    "付款时间",
    "到账时间",
    "凭证日期",
    "确认日期",
    "确认时间",
    "计划开始日期",
    "开始日期",
    "开始时间",
    "截止时间",
    "生效日期",
    "启用日期",
    "任职开始日期",
    "成立日期",
    "签署日期",
    "期限",
    "交期",
    "预计交期",
    "所属月份",
    "期间结束",
    "期间开始",
    "覆盖开始日期",
    "覆盖结束日期",
    "金额截至日期",
    "到期日",
    "有效期至",
    "检索日期",
    "复核日期",
    "失效日期",
    "停用日期",
    "计划结束日期",
    "结束时间",
    "结束日期",
    "任职结束日期",
    "处置日期",
)


class InvalidRequest(ValueError):
    pass


class Data:
    def __init__(self, params=None):
        self.p = params or {}
        self.mode = self.p.get("mode", "live")
        if self.mode not in ("live", "demo"):
            raise InvalidRequest("无效数据来源")
        self.erp = ERP(mode=self.mode)
        self.db = self.erp.c["database"]
        self.start = self.p.get("start", date.today().replace(day=1).isoformat())
        self.end = self.p.get("end", date.today().isoformat())
        try:
            if date.fromisoformat(self.start) > date.fromisoformat(self.end):
                raise ValueError()
        except ValueError:
            raise InvalidRequest("请选择有效的起止日期")
        self.tz = self.p.get("tz", "UTC")
        if self.tz not in ("UTC", "Europe/Berlin", "Asia/Shanghai"):
            raise InvalidRequest("无效查询时区")
        self.currency = self.p.get("currency", "CNY")
        if self.currency != "ALL" and not re.fullmatch("[A-Z]{3}", self.currency):
            raise InvalidRequest("无效币种")
        self.search = self.p.get("search", "").strip()[:150]
        self.offset = self.integer("offset", 0, 0, 100000)
        self.limit = self.integer("limit", 30, 1, 200)

    def integer(self, key, default, low, high):
        try:
            value = int(self.p.get(key, default))
        except ValueError:
            raise InvalidRequest("无效分页参数")
        if not low <= value <= high:
            raise InvalidRequest("分页参数超出范围")
        return value

    def expression(self, value, timestamp=False):
        return f"({value} AT TIME ZONE {L(self.tz)})::date" if timestamp else value

    def period(self, value, timestamp=False, months=False):
        value = self.expression(value, timestamp)
        start = (
            f"date_trunc('month',{L(self.start)}::date)::date"
            if months
            else f"{L(self.start)}::date"
        )
        end = f"date_trunc('month',{L(self.end)}::date)::date" if months else f"{L(self.end)}::date"
        return f"{value} BETWEEN {start} AND {end}"

    def cutoff(self, value, timestamp=False):
        return f"{self.expression(value, timestamp)}<={L(self.end)}::date"

    def money(self, value):
        return "TRUE" if self.currency == "ALL" else f"{value}={L(self.currency)}"

    def matching(self, expression):
        # strpos provides literal substring search; SQL wildcard characters stay literal.
        return (
            "TRUE" if not self.search else f"strpos(lower({expression}),lower({L(self.search)}))>0"
        )

    def sql(self, query):
        query = expand_queries(query, strict_bom=self.mode == "live")
        result = self.erp.sql(
            "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\nSET LOCAL statement_timeout='8s';\n"
            + query
            + "\nCOMMIT;",
            db=self.db,
            role="easyerp_read",
        )
        return json.loads(result.stdout.strip(), parse_float=Decimal)

    def rows(self, query):
        return self.sql(f"SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM ({query}) x;")

    def bundle(self, queries):
        values = []
        for key, query in queries.items():
            values.extend(
                [L(key), f"(SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM ({query}) x)"]
            )
        return self.sql("SELECT json_build_object(" + ",".join(values) + ");")

    def catalog(self):
        catalog = self.bundle(
            {
                "objects": """SELECT n.nspname AS schema,c.relname AS name,c.relkind AS kind,
          (SELECT json_agg(json_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),'required',a.attnotnull) ORDER BY a.attnum)
           FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS columns,
          coalesce((SELECT a.attname FROM pg_constraint p JOIN pg_attribute a ON a.attrelid=p.conrelid AND a.attnum=p.conkey[1]
           WHERE p.conrelid=c.oid AND p.contype='p'),(SELECT a.attname FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum=1)) AS pk
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE (n.nspname IN ('finance','legal','production','rd','sales','analysis') AND c.relkind='r') ORDER BY n.nspname,c.relkind DESC,c.relname""",
                "references": """SELECT s.nspname AS source_schema,t.relname AS source_table,a.attname AS source_column,
          ns.nspname AS target_schema,nt.relname AS target_table,na.attname AS target_column
          FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace s ON s.oid=t.relnamespace
          JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=c.conkey[1]
          JOIN pg_class nt ON nt.oid=c.confrelid JOIN pg_namespace ns ON ns.oid=nt.relnamespace
          JOIN pg_attribute na ON na.attrelid=nt.oid AND na.attnum=c.confkey[1]
          WHERE c.contype='f' AND s.nspname IN ('finance','legal','production','rd','sales','analysis')""",
                "subjects": 'SELECT "主体ID","公司名称" FROM legal."公司主体档案表" ORDER BY "公司名称"',
                "people": 'SELECT "人员ID","姓名" FROM finance."人员档案表" ORDER BY "姓名"',
                "units": 'SELECT "单位ID","单位名称" FROM rd."计量单位表" ORDER BY "单位名称"',
                "currencies": """SELECT DISTINCT "币种" FROM (SELECT "币种" FROM finance."资金账户档案表" UNION SELECT "币种" FROM sales."销售订单登记表" UNION SELECT "币种" FROM finance."收入成本确认表") x WHERE "币种" IS NOT NULL ORDER BY 1""",
            }
        )
        for obj in catalog["objects"]:
            annotate(obj)
            col = self.date_column(obj)
            obj["date_field"] = col["name"] if col else None
        return catalog

    @staticmethod
    def date_column(obj):
        dates = {
            c["name"]: c
            for c in obj["columns"]
            if c["type"] == "date" or c["type"].startswith("timestamp")
        }
        return next(
            (dates[name] for name in DATE_PRIORITY if name in dates),
            next(iter(dates.values()), None),
        )

    def order_query(self):
        return f'''WITH ship AS (SELECT f."销售订单行ID",f."单位ID",sum(f."数量") AS qty,count(*) AS events
        FROM production."发货履约与质量反馈表" f WHERE f."订单组合明细ID" IS NULL AND {self.cutoff('f."发货时间"', True)} GROUP BY 1,2),
        mismatch AS (SELECT DISTINCT f."销售订单行ID" FROM production."发货履约与质量反馈表" f JOIN sales."销售订单行表" l USING ("销售订单行ID")
        WHERE f."单位ID"<>l."单位ID" AND {self.cutoff('f."发货时间"', True)})
        SELECT l.*,o."创建时间",o."币种",o."平台订单号",o."状态" AS "订单状态",c."客户名称",p."名称" AS "产品名称",pv."版本名称",u."单位名称",
        s.qty AS "已登记发货数量",CASE WHEN m."销售订单行ID" IS NOT NULL OR l."产品版本ID" IS NULL OR l."数量" IS NULL OR l."取消数量" IS NULL OR l."单位ID" IS NULL THEN NULL
        ELSE greatest(l."数量"-l."取消数量"-coalesce(s.qty,0),0) END AS "待履约数量",
        CASE WHEN m."销售订单行ID" IS NOT NULL THEN '单位待核' WHEN l."产品版本ID" IS NULL THEN '组合／版本待核'
        WHEN l."单位ID" IS NULL THEN '单位待核' WHEN l."数量" IS NULL OR l."取消数量" IS NULL THEN '数量待核'
        WHEN o."状态" IN ('已取消','已关闭') OR l."状态"='已取消' THEN '已关闭／取消'
        WHEN l."状态"='已完成' THEN '已完成'
        WHEN l."数量"-l."取消数量"-coalesce(s.qty,0)<=0 THEN '登记发货已覆盖'
        WHEN s.events>0 THEN '部分发货' ELSE '待履约' END AS "履约进展"
        FROM sales."订单与履约交付表" l JOIN sales."销售订单登记表" o USING ("订单ID")
        LEFT JOIN sales."客户档案表" c ON c."客户ID"=l."客户ID" LEFT JOIN rd."产品版本表" pv USING ("产品版本ID")
        LEFT JOIN rd."产品主数据表" p USING ("PID") LEFT JOIN rd."计量单位表" u ON u."单位ID"=l."单位ID"
        LEFT JOIN ship s ON s."销售订单行ID"=l."销售订单行ID" AND s."单位ID"=l."单位ID"
        LEFT JOIN mismatch m ON m."销售订单行ID"=l."销售订单行ID"'''

    def work_query(self):
        return f'''WITH output AS (SELECT "工单号","单位ID",sum("合格数量") qty FROM production."完工记录表"
        WHERE {self.cutoff('"日期"')} GROUP BY 1,2),scrap AS (SELECT "工单号","单位ID",sum("数量") qty FROM production."报废记录表"
        WHERE {self.cutoff('"日期"')} GROUP BY 1,2)
        SELECT w.*,p."名称" AS "产品名称",pv."产品版本ID",pv."版本名称",b."BOM登记ID",b."BOM版本",pv."项目ID",
        u."单位名称",person."姓名" AS "负责人",out.qty AS "截至合格数量",s.qty AS "截至报废数量",
        CASE WHEN EXISTS(SELECT 1 FROM production."完工记录表" z WHERE z."工单号"=w."工单号" AND z."单位ID"<>w."单位ID" AND {self.cutoff('z."日期"')}) THEN NULL
        ELSE greatest(w."计划数量"-w."取消数量"-coalesce(out.qty,0),0) END AS "待完成数量"
        FROM production."生产执行交付表" w JOIN rd."发布批次表" r USING ("发布批次ID")
        JOIN rd."BOM登记表" b USING ("BOM登记ID") JOIN rd."产品版本表" pv USING ("产品版本ID")
        JOIN rd."产品主数据表" p USING ("PID") LEFT JOIN finance."人员档案表" person ON person."人员ID"=w."负责人ID"
        LEFT JOIN rd."计量单位表" u ON u."单位ID"=w."单位ID"
        LEFT JOIN output out ON out."工单号"=w."工单号" AND out."单位ID"=w."单位ID"
        LEFT JOIN scrap s ON s."工单号"=w."工单号" AND s."单位ID"=w."单位ID"'''

    def fund_query(self):
        return """SELECT f.*,a."账户名",a."主体ID",co."公司名称",q."已核定用途金额",q."已核定分摊金额",q."用途差额",q."分摊差额",q."已确认重复",q."已确认内部划转"
        FROM finance."账户流水标准化表" f JOIN finance."资金账户档案表" a USING ("账户ID")
        LEFT JOIN legal."公司主体档案表" co USING ("主体ID") JOIN erp_ops."资金核对" q USING ("资金记录ID")"""

    def filtered(self, kind):
        scope = self.p.get("scope", "")
        if kind == "orders":
            query = self.order_query()
            where = self.period('x."创建时间"', True) + " AND " + self.money('x."币种"')
            if scope == "pending":
                where += " AND x.\"待履约数量\">0 AND x.\"订单状态\" NOT IN ('已关闭','已取消') AND x.\"状态\" NOT IN ('已完成','已取消')"
            text = 'concat_ws(\' \',x."订单ID",x."平台订单号",x."客户名称",x."产品名称",x."原商品信息")'
            order = 'x."创建时间" DESC,x."销售订单行ID"'
        elif kind == "workorders":
            query = self.work_query()
            where = self.period('x."计划开始日期"')
            if scope == "pending":
                where += (
                    " AND x.\"待完成数量\">0 AND x.\"状态\" NOT IN ('已关闭','已取消','已完工')"
                )
            text = 'concat_ws(\' \',x."工单号",x."产品名称",x."负责人",x."版本名称")'
            order = 'x."计划开始日期" DESC,x."工单号"'
            person = self.p.get("person", "")
            if person:
                where += ' AND x."负责人ID"=' + L(person)
        elif kind == "funds":
            query = self.fund_query()
            where = self.period('x."发生时间"', True) + " AND " + self.money('x."币种"')
            if scope in ("cash-income", "cash-expense"):
                where += ' AND NOT x."已确认重复" AND NOT x."已确认内部划转" AND x."收支方向"=' + L(
                    "收入" if scope == "cash-income" else "支出"
                )
            text = 'concat_ws(\' \',x."资金记录ID",x."账户名",x."交易摘要",x."平台交易号")'
            order = 'x."发生时间" DESC,x."资金记录ID"'
            subject = self.p.get("subject", "")
            if subject:
                where += ' AND x."主体ID"=' + L(subject)
        else:
            raise InvalidRequest("未知业务入口")
        status = self.p.get("status", "")
        if status and kind in ("orders", "workorders"):
            where += (
                " AND " + ('x."履约进展"' if kind == "orders" else 'x."状态"') + "=" + L(status)
            )
        where += " AND " + self.matching(text)
        return query, where, order

    def listing(self, kind, export=False):
        query, where, order = self.filtered(kind)
        cap = 10000 if export else self.limit
        return self.bundle(
            {
                "rows": f"SELECT * FROM ({query}) x WHERE {where} ORDER BY {order} LIMIT {cap} OFFSET {0 if export else self.offset}",
                "total": f"SELECT count(*) AS count FROM ({query}) x WHERE {where}",
            }
        )

    def overview(self):
        # Each metric preaggregates its own events; money is always grouped by currency.
        oq = self.order_query()
        wq = self.work_query()
        fq = self.fund_query()
        rec = f"""SELECT r."币种",count(*) AS "记录数",count(r."确认收入") AS "收入已填数",count(r."结转成本") AS "成本已填数",
        sum(r."确认收入") AS "已确认收入",sum(r."结转成本") AS "已确认结转成本",
        sum(r."确认收入"-r."结转成本") FILTER(WHERE r."确认收入" IS NOT NULL AND r."结转成本" IS NOT NULL) AS "配对收入减成本",
        count(*) FILTER(WHERE r."确认收入" IS NOT NULL AND r."结转成本" IS NOT NULL) AS "配对记录数"
        FROM finance."收入成本确认表" r WHERE r."状态"='已核定' AND {self.period('r."所属月份"')} AND {self.money('r."币种"')} GROUP BY 1"""
        return self.bundle(
            {
                "sales": f'SELECT "币种",sum("商品实付") AS "金额",count(*) AS "订单行数",count(*) AS "记录数",count("商品实付") AS "实付已填数" FROM ({oq}) x WHERE {self.period('x."创建时间"', True)} AND {self.money('x."币种"')} GROUP BY 1',
                "recognition": rec,
                "cash": f"""SELECT "币种","收支方向",sum("金额") FILTER(WHERE NOT "已确认重复" AND NOT "已确认内部划转") AS "外部金额",
          sum("金额") FILTER(WHERE NOT "已确认重复" AND "已确认内部划转") AS "内部划转金额",count(*) FILTER(WHERE "已确认重复") AS "重复记录数"
          FROM ({fq}) x WHERE {self.period('x."发生时间"', True)} AND {self.money('x."币种"')} GROUP BY 1,2""",
                "fulfillment": f"""SELECT "履约进展",count(*) AS "数量" FROM ({oq}) x WHERE {self.period('x."创建时间"', True)} AND {self.money('x."币种"')} GROUP BY 1""",
                "pending_orders": f"""SELECT count(*) FILTER(WHERE "待履约数量">0 AND "订单状态" NOT IN ('已关闭','已取消') AND "状态" NOT IN ('已完成','已取消')) AS "待发货订单行",
          count(*) FILTER(WHERE "待履约数量" IS NULL) AS "待核订单行",count(*) AS "范围记录数" FROM ({oq}) x
          WHERE {self.period('x."创建时间"', True)} AND {self.money('x."币种"')}""",
                "pending_work": f"""SELECT count(*) FILTER(WHERE "待完成数量">0 AND "状态" NOT IN ('已关闭','已取消','已完工')) AS "待完成工单",
          count(*) FILTER(WHERE "待完成数量" IS NULL) AS "待核工单",count(*) AS "范围记录数" FROM ({wq}) x WHERE {self.period('x."计划开始日期"')}""",
                "trend": f"""SELECT "所属月份","币种",count(*) AS "记录数",count("确认收入") AS "收入已填数",count("结转成本") AS "成本已填数",sum("确认收入") AS "收入",sum("结转成本") AS "成本"
          FROM finance."收入成本确认表" WHERE "状态"='已核定' AND {self.period('"所属月份"')} AND {self.money('"币种"')} GROUP BY 1,2 ORDER BY 1,2""",
                "balances": f"""SELECT DISTINCT ON(c."账户ID") c.*,a."账户名",a."币种" FROM finance."账户核对与差异表" c
          JOIN finance."资金账户档案表" a USING ("账户ID") WHERE c."核定状态"='已核定' AND {self.period('c."期间结束"')} AND {self.money('a."币种"')}
          ORDER BY c."账户ID",c."期间结束" DESC,c."核对版本" DESC LIMIT 8""",
                "inventory": f"""SELECT coalesce(p."名称",m."名称") AS "物品名称",w."地点" AS "仓库",l."库位代码",e."批次",u."单位名称",e."所有权主体ID",
          sum(e."数量变化") FILTER(WHERE e."数量变化">0) AS "期间入库",sum(-e."数量变化") FILTER(WHERE e."数量变化"<0) AS "期间出库"
          FROM production."库存收发明细表" e JOIN production."库位档案表" l USING ("库位ID") JOIN production."仓库档案表" w USING ("仓库ID")
          JOIN rd."计量单位表" u ON u."单位ID"=e."单位ID" LEFT JOIN rd."产品版本表" pv USING ("产品版本ID")
          LEFT JOIN rd."产品主数据表" p USING ("PID") LEFT JOIN rd."物料版本表" mv USING ("物料版本ID") LEFT JOIN rd."物料主数据表" m USING ("MID")
          WHERE {self.period('e."发生时间"', True)} GROUP BY p."名称",m."名称",w."地点",l."库位代码",e."批次",u."单位名称",e."所有权主体ID",e."产品版本ID",e."物料版本ID" LIMIT 8""",
                "issues": """SELECT * FROM erp_ops."业务核对问题" UNION ALL SELECT * FROM erp_ops."数量版本核对问题" LIMIT 12""",
                "activity": f"""SELECT * FROM (SELECT '订单' AS "类型","订单ID" AS "编号","创建时间" AS "时间",'sales.销售订单登记表' AS "来源" FROM sales."销售订单登记表"
          UNION ALL SELECT '到货',"到货ID","到货时间",'production.到货记录表' FROM production."到货记录表"
          UNION ALL SELECT '发货',"发货事件ID","发货时间",'production.发货记录表' FROM production."发货记录表") x
          WHERE {self.period('x."时间"', True)} ORDER BY "时间" DESC LIMIT 8""",
            }
        )

    def tasks(self):
        # No implicit current-user assignment or invented deadlines.
        rows = self.rows(f"""SELECT * FROM (
        SELECT '资金用途待核定' AS "事项",u."用途核定ID" AS "编号",a."账户名" AS "内容",u."状态",NULL::date AS "期限",NULL::text AS "负责人",
        'finance.资金用途核定表' AS "来源",'fund' AS "入口",f."资金记录ID" AS "入口ID",f."发生时间" AS "时间",f."币种",f."金额"::text AS "金额"
        FROM finance."资金用途核定表" u JOIN finance."账户流水标准化表" f USING ("资金记录ID") JOIN finance."资金账户档案表" a USING ("账户ID") WHERE u."状态"='待核定'
        UNION ALL SELECT '售后待处理',"售后事件ID","原因","处理状态",NULL,NULL,'sales.售后事件表','order',l."订单ID",s."发生时间",o."币种",NULL
        FROM sales."售后反馈表" s JOIN sales."销售订单行表" l USING ("销售订单行ID") JOIN sales."销售订单登记表" o USING ("订单ID") WHERE s."处理状态" IN ('新建','处理中')
        UNION ALL SELECT '工单待登记',"工单号","下达依据","状态","计划结束日期",p."姓名",'production.生产工单表','workorder',"工单号","计划开始日期"::timestamptz,NULL,NULL
        FROM production."生产工单表" w LEFT JOIN finance."人员档案表" p ON p."人员ID"=w."负责人ID" WHERE w."状态" IN ('已下达','执行中')
        UNION ALL SELECT '履约提示',"提示ID","履约节点","状态","期限",NULL,'legal.履约提示表','record',"提示ID","期限"::timestamptz,NULL,NULL
        FROM legal."履约提示表" WHERE "状态"='待履约'
        UNION ALL SELECT '整改待复核',"整改事项ID","整改意见","关闭状态","期限",p."姓名",'legal.整改跟踪表','record',"整改事项ID",r."期限"::timestamptz,NULL,NULL
        FROM legal."整改跟踪表" r LEFT JOIN finance."人员档案表" p ON p."人员ID"=r."责任人ID" WHERE "关闭状态"='未关闭'
        UNION ALL SELECT '到货待验收',r."到货ID",sp."名称",'待验收',NULL,NULL,'production.到货记录表','record',r."到货ID",r."到货时间",po."币种",NULL
        FROM production."到货记录表" r JOIN production."采购订单行表" l USING ("采购订单行ID") JOIN production."采购订单表" po USING ("采购单ID") JOIN production."供应商档案表" sp USING ("供应商ID")
        WHERE NOT EXISTS(SELECT 1 FROM production."验收交付表" a WHERE a."到货ID"=r."到货ID")
        ) x WHERE {self.period('x."时间"', True)} AND {self.matching('concat_ws(\' \',x."事项",x."编号",x."内容",x."负责人")')}
        ORDER BY "期限" NULLS LAST,"时间" DESC NULLS LAST LIMIT 200""")
        from workspace import Workspace

        rows = [r for r in rows if r["来源"] not in {"legal.履约提示表", "legal.整改跟踪表"}]
        for item in Workspace(self.mode).listing(
            {"kind": "workflow", "start": self.start, "end": self.end, "search": self.search}
        )["rows"]:
            if item["status"] in {"已完成", "已取消", "历史归档"}:
                continue
            v = item["values"]
            rows.append(
                {
                    "事项": v.get("type") or "工作流事项",
                    "编号": item["id"],
                    "内容": v["title"],
                    "状态": item["status"],
                    "期限": v.get("due"),
                    "负责人": v.get("owner"),
                    "来源": "workspace",
                    "入口": "record",
                    "入口ID": item["id"],
                    "时间": item["updated_at"],
                    "币种": None,
                    "金额": None,
                }
            )
        return rows

    def detail(self, kind, key):
        from identifiers import Identifiers

        target = {
            "order": "sales.销售订单登记表",
            "workorder": "production.生产工单表",
            "fund": "finance.资金流水表",
        }.get(kind)
        if target:
            key = Identifiers(self).resolve(target, key)
        if len(key) > 300:
            raise InvalidRequest("编号过长")
        k = L(key)
        if kind == "order":
            line = f'SELECT "销售订单行ID" FROM sales."销售订单行表" WHERE "订单ID"={k}'
            return self.bundle(
                {
                    "basic": f"""SELECT o.*,c."客户名称",ch."渠道名称" FROM sales."销售订单登记表" o LEFT JOIN sales."客户档案表" c USING ("客户ID") JOIN sales."渠道档案表" ch USING ("渠道ID") WHERE "订单ID"={k}""",
                    "lines": f'SELECT * FROM ({self.order_query()}) x WHERE "订单ID"={k}',
                    "snapshots": f'SELECT * FROM sales."订单导出快照表" WHERE "订单ID"={k} ORDER BY "订单快照ID"',
                    "source_files": f'SELECT DISTINCT f.* FROM sales."平台文件登记表" f JOIN sales."订单导出快照表" s USING ("平台文件ID") WHERE s."订单ID"={k}',
                    "shipments": f'SELECT * FROM production."发货履约与质量反馈表" WHERE "订单ID"={k} ORDER BY "发货时间"',
                    "workorders": f'SELECT * FROM production."工单订单对应表" WHERE "销售订单行ID" IN ({line})',
                    "settlements": f"""SELECT a.*,f."币种",f."发生时间",f."资金记录ID",u."状态" AS "用途状态" FROM finance."结算分摊表" a JOIN finance."资金用途核定表" u USING ("用途核定ID") JOIN finance."账户流水标准化表" f USING ("资金记录ID") WHERE a."销售订单行ID" IN ({line})""",
                    "invoices": f'SELECT i.*,a."分摊金额",a."分摊税额" FROM finance."发票分摊表" a JOIN finance."发票登记表" i USING ("票据ID") WHERE a."销售订单行ID" IN ({line})',
                    "aftersales": f'SELECT * FROM sales."售后反馈表" WHERE "销售订单行ID" IN ({line})',
                    "demands": f'SELECT * FROM sales."需求反馈表" WHERE "订单ID"={k}',
                }
            )
        if kind == "workorder":
            return self.bundle(
                {
                    "basic": f'SELECT * FROM ({self.work_query()}) x WHERE "工单号"={k}',
                    "orders": f'SELECT * FROM production."工单订单对应表" WHERE "工单号"={k}',
                    "materials": f'SELECT m.*,p."名称" AS "物料名称",u."单位名称" FROM production."生产领退料表" m JOIN rd."物料版本表" v USING ("物料版本ID") JOIN rd."物料主数据表" p USING ("MID") JOIN rd."计量单位表" u ON u."单位ID"=m."单位ID" WHERE "工单号"={k}',
                    "completion": f'SELECT * FROM production."完工记录表" WHERE "工单号"={k}',
                    "scrap": f'SELECT * FROM production."报废记录表" WHERE "工单号"={k}',
                    "bom": f"""SELECT b.*,m."名称" AS "物料名称",u."单位名称" FROM rd."已核定BOM明细表" b JOIN rd."物料主数据表" m USING ("MID") JOIN rd."计量单位表" u ON u."单位ID"=b."单位ID"
              WHERE b."BOM登记ID"=(SELECT r."BOM登记ID" FROM production."生产工单表" w JOIN rd."发布批次表" r USING ("发布批次ID") WHERE "工单号"={k})""",
                    "files": f"""SELECT d.* FROM production."生产工单表" w JOIN rd."发布文件明细表" f USING ("发布批次ID") JOIN rd."项目文件登记表" d USING ("文件ID") WHERE "工单号"={k}""",
                }
            )
        if kind == "fund":
            return self.bundle(
                {
                    "basic": f'SELECT * FROM ({self.fund_query()}) x WHERE "资金记录ID"={k}',
                    "purposes": f'SELECT * FROM finance."资金用途核定表" WHERE "资金记录ID"={k}',
                    "allocations": f'SELECT a.*,u."状态" AS "用途状态" FROM finance."结算分摊表" a JOIN finance."资金用途核定表" u USING ("用途核定ID") WHERE u."资金记录ID"={k}',
                    "sources": f'SELECT l.*,f."文件路径",f."文件校验值" FROM finance."流水来源明细表" l JOIN finance."流水文件登记表" f USING ("流水文件ID") WHERE "资金记录ID"={k}',
                    "transfers": f'SELECT * FROM finance."内部划转对应表" WHERE "转出资金记录ID"={k} OR "转入资金记录ID"={k}',
                    "duplicates": f'SELECT * FROM finance."重复记录对应表" WHERE "原资金记录ID"={k} OR "重复资金记录ID"={k}',
                    "entries": f'SELECT * FROM finance."分账表" WHERE "资金记录ID"={k}',
                }
            )
        raise InvalidRequest("未知详情类型")

    def object(self, key, catalog):
        obj = next((o for o in catalog["objects"] if o["schema"] + "." + o["name"] == key), None)
        if not obj:
            raise InvalidRequest("该数据对象不可访问")
        return obj

    @staticmethod
    def projection(obj):
        # Even a scale-free NUMERIC integer must reach JavaScript as exact text.
        return ",".join(
            I(c["name"]) + "::text AS " + I(c["name"])
            if c["type"].startswith("numeric")
            else I(c["name"])
            for c in obj["columns"]
        )

    def explore(self, key, catalog, export=False):
        o = self.object(key, catalog)
        expr = I(o["schema"]) + "." + I(o["name"])
        columns = [x["name"] for x in o["columns"]]
        where = self.matching("concat_ws(' '," + ",".join(I(c) + "::text" for c in columns) + ")")
        date_col = self.date_column(o)
        date_filter = date_col is not None and self.p.get("date_filter", "1") != "0"
        if date_filter:
            date_expr = I(date_col["name"])
            if (
                date_col["type"].startswith("timestamp")
                and date_col["type"] != "timestamp with time zone"
            ):
                date_expr += "::date"
            where += " AND " + self.period(
                date_expr, date_col["type"] == "timestamp with time zone"
            )
        if key == "finance.收入成本确认表" and self.p.get("scope") == "confirmed":
            where += " AND \"状态\"='已核定' AND " + self.money('"币种"')
        cap = 10000 if export else self.limit
        extra = ""
        if key == "production.库存盘点表" and "账面数量" in columns:
            extra = ',("实盘数量"-"账面数量")::text AS "盘点差异"'
        elif key == "production.采购订单表":
            extra = ''',(SELECT s."名称" FROM production."供应商档案表" s WHERE s."供应商ID"=t."供应商ID") AS "供应商",coalesce(nullif(t."采购说明",''),(SELECT string_agg(concat_ws(' · ',l."物料版本ID",l."产品版本ID",l."数量"::text,u."单位名称",l."单价"::text),E'\n' ORDER BY l."行号") FROM production."采购订单行表" l LEFT JOIN rd."计量单位表" u USING ("单位ID") WHERE l."采购单ID"=t."采购单ID")) AS "采购内容"'''
        elif key == "production.供应商档案表" and any(obj["schema"] == "production" and obj["name"] == "供应物品明细表" for obj in catalog["objects"]):
            extra = ',(SELECT string_agg(coalesce(m."名称",d."MID"),\'、\' ORDER BY d."供应关系ID") FROM production."供应物品明细表" d LEFT JOIN rd."物料主数据表" m USING ("MID") WHERE d."供应商ID"=t."供应商ID") AS "供应的物品",(SELECT json_agg(json_build_object(\'id\',d."MID",\'name\',m."名称") ORDER BY d."供应关系ID") FROM production."供应物品明细表" d LEFT JOIN rd."物料主数据表" m USING ("MID") WHERE d."供应商ID"=t."供应商ID" AND d."MID" IS NOT NULL) AS "_供应物品"'
        elif key == "production.仓库档案表":
            extra = ''',(SELECT string_agg(l."库位代码",'、' ORDER BY l."库位ID") FROM production."库位档案表" l WHERE l."仓库ID"=t."仓库ID") AS "地点标识"'''
        result = self.bundle(
            {
                "rows": f"SELECT {self.projection(o)}{extra} FROM {expr} t WHERE {where} ORDER BY {I(o['pk'])} LIMIT {cap} OFFSET {0 if export else self.offset}",
                "total": f"SELECT count(*) AS count FROM {expr} WHERE {where}",
            }
        )
        result.update(
            date_field=date_col["name"] if date_col else None, date_filter_applied=date_filter
        )
        return result

    def search_all(self):
        if not self.search:
            return []
        return self.rows(f"""SELECT * FROM (
        SELECT '订单' AS "业务",o."订单ID" AS "编号",coalesce(c."客户名称",o."平台订单号") AS "名称",'sales.销售订单登记表' AS "来源",TRUE AS "_dated",{self.expression('o."创建时间"', True)} AS "_date"
        FROM sales."销售订单登记表" o LEFT JOIN sales."客户档案表" c USING ("客户ID")
        UNION ALL SELECT '工单',w."工单号",p."名称",'production.生产工单表',TRUE,w."计划开始日期" FROM production."生产工单表" w JOIN rd."发布批次表" r USING ("发布批次ID") JOIN rd."BOM登记表" b USING ("BOM登记ID") JOIN rd."产品版本表" v USING ("产品版本ID") JOIN rd."产品主数据表" p USING ("PID")
        UNION ALL SELECT '资金',"资金记录ID","交易摘要",'finance.资金流水表',TRUE,{self.expression('"发生时间"', True)} FROM finance."资金流水表"
        UNION ALL SELECT '项目',"项目ID","项目名称",'rd.项目登记表',TRUE,"开始日期" FROM rd."项目登记表"
        UNION ALL SELECT '产品',"PID","名称",'rd.产品主数据表',FALSE,NULL::date FROM rd."产品主数据表"
        UNION ALL SELECT '客户',"客户ID","客户名称",'sales.客户档案表',TRUE,"确认日期" FROM sales."客户档案表"
        UNION ALL SELECT '采购',p."采购单ID",s."名称",'production.采购订单表',TRUE,p."创建日期" FROM production."采购订单表" p JOIN production."供应商档案表" s USING ("供应商ID")
        ) x WHERE {self.matching('concat_ws(\' \',x."编号",x."名称")')} AND (NOT x."_dated" OR {self.period('x."_date"')}) LIMIT 60""")

    def record(self, key, value, catalog):
        from identifiers import Identifiers

        value = Identifiers(self).resolve(key, value)
        o = self.object(key, catalog)
        refs = [
            r
            for r in catalog["references"]
            if r["target_schema"] == o["schema"]
            and r["target_table"] == o["name"]
            and not next(
                (
                    x.get("retired")
                    for x in catalog["objects"]
                    if x["schema"] == r["source_schema"] and x["name"] == r["source_table"]
                ),
                False,
            )
        ]
        # Bounded inverse references; each references the same authoritative primary row.
        queries = {
            "basic": f"SELECT {self.projection(o)} FROM {I(o['schema'])}.{I(o['name'])} WHERE {I(o['pk'])}={L(value)} LIMIT 1"
        }
        selected = []
        for n, r in enumerate(refs[:16]):
            name = "related_" + str(n)
            queries[name] = (
                f"SELECT * FROM {I(r['source_schema'])}.{I(r['source_table'])} WHERE {I(r['source_column'])}={L(value)} LIMIT 20"
            )
            selected.append(
                {
                    "key": name,
                    "object": r["source_schema"] + "." + r["source_table"],
                    "column": r["source_column"],
                }
            )
        result = self.bundle(queries)
        result["_relations"] = selected
        result["_more_relations"] = max(len(refs) - 16, 0)
        return result
