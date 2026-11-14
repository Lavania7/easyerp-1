"""Read-only SELECT templates composed as subqueries, without database views."""
import re

QUERIES = {
    'finance."账户流水标准化表"': """
SELECT f.*, a."币种" FROM finance."资金流水表" f JOIN finance."资金账户档案表" a USING ("账户ID")
""",
    'finance."往来未结查询"': """
SELECT r.*, r."原金额" - r."已结金额" AS "未结金额" FROM finance."往来未结明细表" r
""",
    'finance."账户核对与差异表"': """
SELECT c.*, b."账户ID", b."期间开始", b."期间结束", b."期末余额" AS "原始余额", b."期末余额" - c."滚动余额" AS "差额" FROM finance."账户核对表" c JOIN finance."账户期间余额表" b USING ("余额记录ID")
""",
    'finance."分账表"': """
SELECT l.*, v."主体ID", v."凭证日期", v."所属月份", v."凭证号" FROM finance."会计分录表" l JOIN finance."会计凭证表" v USING ("凭证ID") WHERE v."状态" = '已过账'
""",
    'production."验收交付表"': """
SELECT a.*, r."采购订单行ID", r."到货时间" FROM production."验收记录表" a JOIN production."到货记录表" r USING ("到货ID")
""",
    'production."库存收发明细表"': """
SELECT * FROM production."库存变动表"
""",
    'production."生产执行交付表"': """
SELECT w.*,
 (SELECT count(*) FROM production."生产领退料表" x WHERE x."工单号"=w."工单号") AS "领退料事件数",
 (SELECT sum(x."有效工时") FROM production."生产工时表" x WHERE x."工单号"=w."工单号" AND x."人员ID" IS NOT NULL) AS "人员有效工时",
 (SELECT sum(x."合格数量") FROM production."完工记录表" x WHERE x."工单号"=w."工单号") AS "累计合格数量"
FROM production."生产工单表" w
""",
    'production."发货履约与质量反馈表"': """
SELECT f.*, l."订单ID", coalesce(c."产品版本ID", l."产品版本ID") AS "产品版本ID", l."收货信息" FROM production."发货记录表" f JOIN sales."销售订单行表" l USING ("销售订单行ID") LEFT JOIN sales."订单组合明细表" x ON x."订单组合明细ID"=f."订单组合明细ID" LEFT JOIN sales."组合商品明细表" c ON c."组合明细ID"=x."组合明细ID"
""",
    'rd."已核定BOM明细表"': """
SELECT l.*, v."MID" FROM rd."BOM明细表" l JOIN rd."物料版本表" v USING ("物料版本ID")
""",
    'rd."研发验证及变更结论"': """
SELECT * FROM rd."设计变更与验证表"
""",
    'rd."研发实际投入说明"': """
SELECT * FROM rd."研发投入归属表"
""",
    'sales."订单与履约交付表"': """
SELECT l.*, o."客户ID", o."渠道ID" FROM sales."销售订单行表" l JOIN sales."销售订单登记表" o USING ("订单ID")
""",
    'sales."售后反馈表"': """
SELECT * FROM sales."售后事件表"
""",
    'sales."需求反馈表"': """
SELECT * FROM sales."客户需求表"
""",
    'legal."合规事项与整改跟踪表"': """
SELECT r.*, c."规则ID" FROM legal."整改跟踪表" r JOIN legal."合规自查表" c USING ("自查ID")
""",
    'erp_ops."业务核对问题"': """
SELECT '资金用途超额'::text AS "规则", f."资金记录ID" AS "记录ID", '已核定用途合计超过流水金额'::text AS "说明"
FROM finance."资金流水表" f JOIN finance."资金用途核定表" u USING ("资金记录ID")
WHERE u."状态"='已核定' GROUP BY f."资金记录ID",f."金额" HAVING sum(u."核定金额")>f."金额"
UNION ALL
SELECT '用途待补',"用途核定ID",'已核定用途缺少金额、确认人或确认时间'
FROM finance."资金用途核定表" WHERE "状态"='已核定' AND
 ("核定金额" IS NULL OR "确认人ID" IS NULL OR "确认时间" IS NULL)
UNION ALL
SELECT '分摊超额',u."用途核定ID",'结算分摊合计超过核定金额'
FROM finance."资金用途核定表" u JOIN finance."结算分摊表" a USING ("用途核定ID")
WHERE u."状态"='已核定' GROUP BY u."用途核定ID",u."核定金额" HAVING sum(a."分摊金额")>u."核定金额"
UNION ALL
SELECT '分摊未核定',a."分摊ID",'结算分摊引用尚未核定用途'
FROM finance."结算分摊表" a JOIN finance."资金用途核定表" u USING ("用途核定ID") WHERE u."状态"<>'已核定'
UNION ALL
SELECT '结算币种不一致',a."分摊ID",'资金账户币种与所引用销售或采购订单币种不一致'
FROM finance."结算分摊表" a JOIN finance."资金用途核定表" u USING ("用途核定ID")
JOIN finance."资金流水表" f USING ("资金记录ID") JOIN finance."资金账户档案表" ac USING ("账户ID")
LEFT JOIN sales."销售订单行表" sl ON sl."销售订单行ID"=a."销售订单行ID"
LEFT JOIN sales."销售订单登记表" so ON so."订单ID"=sl."订单ID"
LEFT JOIN production."采购订单行表" pl ON pl."采购订单行ID"=a."采购订单行ID"
LEFT JOIN production."采购订单表" po ON po."采购单ID"=pl."采购单ID"
WHERE ac."币种"<>coalesce(so."币种",po."币种")
UNION ALL
SELECT '内部划转方向',t."划转对应ID",'划转转出必须为支出、转入必须为收入'
FROM finance."内部划转对应表" t
JOIN finance."资金流水表" o ON o."资金记录ID"=t."转出资金记录ID"
JOIN finance."资金流水表" i ON i."资金记录ID"=t."转入资金记录ID"
WHERE t."状态"='已核定' AND (o."收支方向"<>'支出' OR i."收支方向"<>'收入')
UNION ALL
SELECT '发票分摊差异',i."票据ID",'已有分摊的金额或税额合计与发票不同；部分分摊需继续处理'
FROM finance."发票登记表" i JOIN finance."发票分摊表" a USING ("票据ID")
GROUP BY i."票据ID",i."价税合计",i."税额"
HAVING sum(a."分摊金额")<>i."价税合计" OR sum(a."分摊税额")<>i."税额"
UNION ALL
SELECT '工时计价超量',h."工时ID",'已核定计价工时合计超过实际研发工时'
FROM rd."研发工时表" h JOIN finance."工时计价表" p ON p."研发工时ID"=h."工时ID"
WHERE p."状态"='已核定' GROUP BY h."工时ID",h."实际工时" HAVING sum(p."计价工时")>h."实际工时"
UNION ALL
SELECT '工时计价超量',h."工时ID",'已核定计价工时合计超过生产有效工时'
FROM production."生产工时表" h JOIN finance."工时计价表" p ON p."生产工时ID"=h."工时ID"
WHERE p."状态"='已核定' GROUP BY h."工时ID",h."有效工时" HAVING sum(p."计价工时")>h."有效工时"
UNION ALL
SELECT '投入比例超额',coalesce("费用ID","计价ID"),'同一来源研发投入归属比例合计超过1'
FROM rd."研发投入归属表" GROUP BY "费用ID","计价ID" HAVING sum("归属比例")>1
UNION ALL
SELECT '发布文件不匹配',f."发布文件明细ID",'文件项目或产品与发布批次BOM产品不一致'
FROM rd."发布文件明细表" f JOIN rd."发布批次表" r USING ("发布批次ID")
JOIN rd."BOM登记表" b USING ("BOM登记ID") JOIN rd."产品版本表" p USING ("产品版本ID")
JOIN rd."项目文件登记表" d USING ("文件ID")
WHERE d."项目ID"<>p."项目ID" OR (d."PID" IS NOT NULL AND d."PID"<>p."PID")
UNION ALL
SELECT '工单未发布',w."工单号",'工单引用尚未发布的发布批次'
FROM production."生产工单表" w JOIN rd."发布批次表" r USING ("发布批次ID")
WHERE r."状态"<>'已发布'
UNION ALL
SELECT '到货超量',p."采购订单行ID",'同单位累计到货超过采购数量减取消数量'
FROM production."采购订单行表" p JOIN production."到货记录表" r USING ("采购订单行ID")
WHERE r."单位ID"=p."单位ID" GROUP BY p."采购订单行ID",p."数量",p."取消数量"
HAVING sum(r."数量")>p."数量"-p."取消数量"
UNION ALL
SELECT '到货单位待核',r."到货ID",'到货与采购行单位不同，需按适用换算另核对'
FROM production."到货记录表" r JOIN production."采购订单行表" p USING ("采购订单行ID")
WHERE r."单位ID"<>p."单位ID"
UNION ALL
SELECT '验收超量',r."到货ID",'同单位累计验收数量超过到货数量'
FROM production."到货记录表" r JOIN production."验收记录表" a USING ("到货ID")
WHERE r."单位ID"=a."单位ID" GROUP BY r."到货ID",r."数量" HAVING sum(a."验收数量")>r."数量"
UNION ALL
SELECT '发货超量',l."销售订单行ID",'普通商品同单位累计发货超过订单数量减取消数量'
FROM sales."销售订单行表" l JOIN production."发货记录表" f USING ("销售订单行ID")
WHERE f."订单组合明细ID" IS NULL AND l."产品版本ID" IS NOT NULL AND f."单位ID"=l."单位ID"
GROUP BY l."销售订单行ID",l."数量",l."取消数量" HAVING sum(f."数量")>l."数量"-l."取消数量"
UNION ALL
SELECT '组合发货归属',f."发货事件ID",'组合明细不属于该订单行'
FROM production."发货记录表" f JOIN sales."订单组合明细表" c USING ("订单组合明细ID")
WHERE c."销售订单行ID"<>f."销售订单行ID"
UNION ALL
SELECT '组合发货超量',x."订单组合明细ID",'同单位组合明细累计发货超过应履约数量'
FROM sales."订单组合明细表" x JOIN sales."组合商品明细表" c USING ("组合明细ID")
JOIN production."发货记录表" f USING ("订单组合明细ID")
WHERE f."单位ID"=c."单位ID" GROUP BY x."订单组合明细ID",x."应履约数量"
HAVING sum(f."数量")>x."应履约数量"
""",
    'erp_ops."资金核对"': """
WITH u AS (SELECT "资金记录ID",sum("核定金额") AS total FROM finance."资金用途核定表" WHERE "状态"='已核定' GROUP BY 1),
a AS (SELECT u."资金记录ID",sum(a."分摊金额") AS total FROM finance."结算分摊表" a
      JOIN finance."资金用途核定表" u USING ("用途核定ID") WHERE u."状态"='已核定' GROUP BY 1)
SELECT f."资金记录ID",f."金额",u.total AS "已核定用途金额",a.total AS "已核定分摊金额",
f."金额"-u.total AS "用途差额",f."金额"-a.total AS "分摊差额",
EXISTS(SELECT 1 FROM finance."重复记录对应表" d WHERE d."重复资金记录ID"=f."资金记录ID" AND d."状态"='已核定') AS "已确认重复",
EXISTS(SELECT 1 FROM finance."内部划转对应表" t WHERE (t."转出资金记录ID"=f."资金记录ID" OR t."转入资金记录ID"=f."资金记录ID") AND t."状态"='已核定') AS "已确认内部划转"
FROM finance."资金流水表" f LEFT JOIN u USING ("资金记录ID") LEFT JOIN a USING ("资金记录ID")
""",
    'erp_ops."数量版本核对问题"': """
SELECT '验收单位待核'::text AS "规则",a."验收ID" AS "记录ID",'验收与到货单位不同，需按适用换算另核对'::text AS "说明"
FROM production."验收记录表" a JOIN production."到货记录表" r USING ("到货ID") WHERE a."单位ID"<>r."单位ID"
UNION ALL
SELECT '发货单位待核',f."发货事件ID",'发货单位与订单履约单位不一致，需按适用换算另核对'
FROM production."发货记录表" f JOIN sales."销售订单行表" l USING ("销售订单行ID")
LEFT JOIN sales."订单组合明细表" x USING ("订单组合明细ID")
LEFT JOIN sales."组合商品明细表" c USING ("组合明细ID")
WHERE f."单位ID"<>coalesce(c."单位ID",l."单位ID")
UNION ALL
SELECT '工单产品不匹配',x."工单订单关联ID",'工单BOM产品与订单履约产品不一致或尚未映射'
FROM production."工单订单对应表" x JOIN production."生产工单表" w USING ("工单号")
JOIN rd."发布批次表" r USING ("发布批次ID") JOIN rd."BOM登记表" b USING ("BOM登记ID")
JOIN sales."销售订单行表" l USING ("销售订单行ID")
LEFT JOIN sales."订单组合明细表" oc USING ("订单组合明细ID")
LEFT JOIN sales."组合商品明细表" c USING ("组合明细ID")
WHERE b."产品版本ID" IS DISTINCT FROM coalesce(c."产品版本ID",l."产品版本ID")
 OR (oc."订单组合明细ID" IS NOT NULL AND oc."销售订单行ID"<>l."销售订单行ID")
""",
}

STRICT_BOM = """
SELECT l.*,v."MID" FROM rd."BOM明细表" l
JOIN rd."物料版本表" v USING("物料版本ID")
JOIN rd."BOM登记表" b USING("BOM登记ID")
JOIN rd."产品版本表" pv USING("产品版本ID")
WHERE b."BOM版本" IS NOT NULL AND b."确认依据" IS NOT NULL
 AND pv."版本名称" IS NOT NULL AND pv."确认依据" IS NOT NULL
 AND v."版本名称" IS NOT NULL AND v."确认依据" IS NOT NULL
 AND l."单位ID" IS NOT NULL AND l."确认依据" IS NOT NULL
"""

def expand_queries(sql, *, strict_bom=False):
    """Compose trusted SELECT templates without replacing SQL string literals."""
    queries = QUERIES
    if strict_bom:
        queries = {**queries, 'rd."已核定BOM明细表"': STRICT_BOM}
    keys = '|'.join(re.escape(key) for key in queries)
    pattern = re.compile(r"'(?:''|[^'])*'|--[^\n]*|/\*.*?\*/|(?P<query>" + keys + r")", re.S)
    # Templates read base tables only; PostgreSQL permits unaliased subqueries.
    return pattern.sub(lambda match: '(' + queries[match.group('query')] + ')'
                       if match.group('query') else match.group(), sql)
