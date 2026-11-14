\set ON_ERROR_STOP on
CREATE FUNCTION pg_temp.assert_ok(label text, actual boolean) RETURNS text LANGUAGE plpgsql AS $$
BEGIN
 IF actual IS DISTINCT FROM TRUE THEN RAISE EXCEPTION 'FAIL %',label; END IF;
 RETURN 'PASS '||label;
END $$;
CREATE FUNCTION pg_temp.expect_error(label text, statement text, expected text) RETURNS text LANGUAGE plpgsql AS $$
DECLARE caught text;
BEGIN
 BEGIN EXECUTE statement;
 EXCEPTION WHEN OTHERS THEN GET STACKED DIAGNOSTICS caught=RETURNED_SQLSTATE;
 END;
 IF caught IS DISTINCT FROM expected THEN RAISE EXCEPTION 'FAIL %: expected %, got %',label,expected,caught; END IF;
 RETURN 'PASS '||label;
END $$;

BEGIN;
INSERT INTO legal."公司主体档案表" VALUES ('co','测试公司','TEST-0001','测试地址',NULL,NULL,NULL,'有效');
INSERT INTO legal."公司主体档案表" VALUES ('other','另一主体','TEST-0002','测试地址',NULL,NULL,NULL,'有效');
INSERT INTO finance."人员档案表" VALUES ('person','测试审核员','财务',NULL,NULL);
INSERT INTO rd."计量单位表" VALUES ('unit','EA','件','数量');
INSERT INTO rd."项目登记表"("项目ID","项目名称","确认依据") VALUES ('project','测试项目','仅隔离测试');
INSERT INTO rd."产品主数据表" VALUES ('pid','测试产品','中文规格','unit','成品');
INSERT INTO rd."产品版本表" VALUES ('pv','project','pid','v1','2026-01-01','测试核定');
INSERT INTO rd."BOM登记表" VALUES ('bom','pv','v1','测试BOM');
INSERT INTO rd."发布批次表" VALUES ('release','bom','person','2026-01-01','测试',NULL,'已发布');
INSERT INTO production."生产工单表"("工单号","发布批次ID","计划数量","单位ID","计划开始日期","下达依据","状态","取消数量")
VALUES ('work','release',10,'unit','2026-10-01','测试','已下达',0);
SELECT pg_temp.assert_ok('no actual hours stays NULL',
 (SELECT "人员有效工时" IS NULL AND "累计合格数量" IS NULL FROM (SELECT w.*,
 (SELECT count(*) FROM production."生产领退料表" x WHERE x."工单号"=w."工单号") AS "领退料事件数",
 (SELECT sum(x."有效工时") FROM production."生产工时表" x WHERE x."工单号"=w."工单号" AND x."人员ID" IS NOT NULL) AS "人员有效工时",
 (SELECT sum(x."合格数量") FROM production."完工记录表" x WHERE x."工单号"=w."工单号") AS "累计合格数量"
FROM production."生产工单表" w) WHERE "工单号"='work'));
INSERT INTO sales."渠道档案表" VALUES ('channel','测试渠道','测试平台','test');
INSERT INTO sales."销售订单登记表"("订单ID","渠道ID","平台订单号","创建时间","币种","状态")
VALUES ('order','channel','O-001','2026-10-01T10:00:00+02:00','CNY','已确认');
INSERT INTO sales."销售订单行表"("销售订单行ID","订单ID","行号","原商品信息","产品版本ID","数量","单位ID","单价","折扣金额","商品实付","运费分摊","收货信息","取消数量","状态")
VALUES ('line','order',1,'产品中文原文','pv',10,'unit',10,0,100,0,'测试地址',0,'待履约');
INSERT INTO production."供应商档案表" VALUES ('supplier','测试供应商',NULL,NULL);
INSERT INTO production."采购订单表" VALUES ('po',NULL,'supplier','2026-10-01','已下单','CNY');
INSERT INTO production."采购订单行表"("采购订单行ID","采购单ID","行号","数量","单位ID","单价","取消数量","产品版本ID")
VALUES ('pol','po',1,10,'unit',5,0,'pv');
INSERT INTO production."到货记录表" VALUES ('arrive','pol','2026-10-02T10:00:00+02:00',10,'unit',NULL);
INSERT INTO production."验收记录表" VALUES ('accept','arrive','2026-10-02T11:00:00+02:00',10,10,0,0,'unit',NULL,NULL);
INSERT INTO production."保管方档案表" VALUES ('keeper','本公司','co');
INSERT INTO production."仓库档案表" VALUES ('warehouse','测试仓','keeper','co','启用');
INSERT INTO production."库位档案表" VALUES ('location','warehouse','A-01');
INSERT INTO production."库存变动表"("库存事件ID","发生时间","数量变化","单位ID","库位ID","批次","所有权主体ID","业务类型","验收ID","产品版本ID")
VALUES ('stock-in','2026-10-02T11:30:00+02:00',10,'unit','location','batch','co','采购入库','accept','pv');
INSERT INTO production."发货记录表"("发货事件ID","销售订单行ID","数量","单位ID","发货时间")
VALUES ('ship','line',3,'unit','2026-10-03T10:00:00+02:00');
INSERT INTO production."库存变动表"("库存事件ID","发生时间","数量变化","单位ID","库位ID","批次","所有权主体ID","业务类型","发货事件ID","产品版本ID")
VALUES ('stock-out','2026-10-03T10:00:00+02:00',-3,'unit','location','batch','co','销售出库','ship','pv');
SELECT pg_temp.assert_ok('procurement acceptance and inventory net',
 (SELECT sum("数量变化")=7 FROM (SELECT * FROM production."库存变动表")));
SELECT pg_temp.assert_ok('shipment preserves order and version',
 (SELECT "订单ID"='order' AND "产品版本ID"='pv' FROM (SELECT f.*, l."订单ID", coalesce(c."产品版本ID", l."产品版本ID") AS "产品版本ID", l."收货信息" FROM production."发货记录表" f JOIN sales."销售订单行表" l USING ("销售订单行ID") LEFT JOIN sales."订单组合明细表" x ON x."订单组合明细ID"=f."订单组合明细ID" LEFT JOIN sales."组合商品明细表" c ON c."组合明细ID"=x."组合明细ID") WHERE "发货事件ID"='ship'));
SELECT pg_temp.assert_ok('UTF8 Chinese roundtrip',(SELECT "名称"='测试产品' FROM rd."产品主数据表" WHERE "PID"='pid'));
SELECT pg_temp.assert_ok('timestamp offset roundtrip',
 (SELECT "发货时间"='2026-10-03T08:00:00Z'::timestamptz FROM production."发货记录表" WHERE "发货事件ID"='ship'));

SELECT pg_temp.expect_error('foreign key rejects missing owner',
 $q$INSERT INTO finance."资金账户档案表"("账户ID","账户名","主体ID","平台","币种","账户性质") VALUES ('bad','错误账户','missing','bank','CNY','银行')$q$,'23503');
SELECT pg_temp.expect_error('duplicate primary key',
 $q$INSERT INTO finance."人员档案表" VALUES ('person','重复','财务',NULL,NULL)$q$,'23505');
SELECT pg_temp.expect_error('status enumeration',
 $q$UPDATE sales."销售订单登记表" SET "状态"='随意完成' WHERE "订单ID"='order'$q$,'23514');
SELECT pg_temp.expect_error('required field',
 $q$INSERT INTO rd."计量单位表" VALUES ('bad',NULL,'错误','数量')$q$,'23502');
SELECT pg_temp.expect_error('one reference only',
 $q$INSERT INTO finance."发票分摊表" VALUES ('bad','missing',NULL,NULL,1,0)$q$,'23514');
SELECT pg_temp.expect_error('quantity must be positive',
 $q$INSERT INTO production."到货记录表" VALUES ('bad','pol',now(),-1,'unit',NULL)$q$,'23514');

INSERT INTO finance."资金账户档案表"("账户ID","账户名","主体ID","平台","币种","账户性质") VALUES ('account','测试银行','co','bank','CNY','银行');
INSERT INTO finance."资金流水表" VALUES ('cash','account','2026-10-01T10:00:00Z',100,'收入','P-001','测试');
SELECT pg_temp.assert_ok('missing allocations stay NULL',
 (SELECT "已核定用途金额" IS NULL AND "用途差额" IS NULL FROM (WITH u AS (SELECT "资金记录ID",sum("核定金额") AS total FROM finance."资金用途核定表" WHERE "状态"='已核定' GROUP BY 1),
a AS (SELECT u."资金记录ID",sum(a."分摊金额") AS total FROM finance."结算分摊表" a
      JOIN finance."资金用途核定表" u USING ("用途核定ID") WHERE u."状态"='已核定' GROUP BY 1)
SELECT f."资金记录ID",f."金额",u.total AS "已核定用途金额",a.total AS "已核定分摊金额",
f."金额"-u.total AS "用途差额",f."金额"-a.total AS "分摊差额",
EXISTS(SELECT 1 FROM finance."重复记录对应表" d WHERE d."重复资金记录ID"=f."资金记录ID" AND d."状态"='已核定') AS "已确认重复",
EXISTS(SELECT 1 FROM finance."内部划转对应表" t WHERE (t."转出资金记录ID"=f."资金记录ID" OR t."转入资金记录ID"=f."资金记录ID") AND t."状态"='已核定') AS "已确认内部划转"
FROM finance."资金流水表" f LEFT JOIN u USING ("资金记录ID") LEFT JOIN a USING ("资金记录ID")) WHERE "资金记录ID"='cash'));
INSERT INTO finance."资金用途核定表"("用途核定ID","资金记录ID","核定金额","状态","确认人ID","确认时间","销售订单行ID")
VALUES ('purpose','cash',100,'已核定','person',now(),'line');
INSERT INTO finance."结算分摊表"("分摊ID","用途核定ID","分摊金额","方向","销售订单行ID")
VALUES ('allocation1','purpose',40,'收入','line'),('allocation2','purpose',60,'收入','line');
SELECT pg_temp.assert_ok('independent aggregations do not multiply amounts',
 (SELECT "已核定用途金额"=100 AND "已核定分摊金额"=100 AND "分摊差额"=0 FROM (WITH u AS (SELECT "资金记录ID",sum("核定金额") AS total FROM finance."资金用途核定表" WHERE "状态"='已核定' GROUP BY 1),
a AS (SELECT u."资金记录ID",sum(a."分摊金额") AS total FROM finance."结算分摊表" a
      JOIN finance."资金用途核定表" u USING ("用途核定ID") WHERE u."状态"='已核定' GROUP BY 1)
SELECT f."资金记录ID",f."金额",u.total AS "已核定用途金额",a.total AS "已核定分摊金额",
f."金额"-u.total AS "用途差额",f."金额"-a.total AS "分摊差额",
EXISTS(SELECT 1 FROM finance."重复记录对应表" d WHERE d."重复资金记录ID"=f."资金记录ID" AND d."状态"='已核定') AS "已确认重复",
EXISTS(SELECT 1 FROM finance."内部划转对应表" t WHERE (t."转出资金记录ID"=f."资金记录ID" OR t."转入资金记录ID"=f."资金记录ID") AND t."状态"='已核定') AS "已确认内部划转"
FROM finance."资金流水表" f LEFT JOIN u USING ("资金记录ID") LEFT JOIN a USING ("资金记录ID")) WHERE "资金记录ID"='cash'));
INSERT INTO finance."收入成本确认表"("确认ID","所属月份","销售订单行ID","确认批次","行号","确认数量","币种","政策ID","确认依据","状态")
-- Policy is inserted below before this source-dependent example.
SELECT 'unused','2026-10-01'::date,'line','test',1,1,'CNY','none','待补','待核定' WHERE false;

INSERT INTO finance."会计政策表"("政策ID","政策名称","政策版本","适用准则","生效日期") VALUES ('policy','测试政策','1','仅测试','2026-01-01');
INSERT INTO finance."收入成本确认表"("确认ID","所属月份","销售订单行ID","确认批次","行号","确认数量","币种","政策ID","确认依据","状态")
VALUES ('recognition','2026-10-01','line','test',1,1,'CNY','policy','待补','待核定');
SELECT pg_temp.assert_ok('unknown income and cost stay NULL',
 (SELECT "确认收入" IS NULL AND "税额" IS NULL AND "结转成本" IS NULL FROM finance."收入成本确认表" WHERE "确认ID"='recognition'));
INSERT INTO finance."会计科目表"("科目ID","主体ID","科目代码","科目名称","分类") VALUES
 ('debit','co','1001','现金','资产'),('credit','co','6001','收入','损益'),('wrong','other','1001','其他主体现金','资产');
INSERT INTO finance."会计凭证表"("凭证ID","主体ID","凭证日期","所属月份","凭证号","摘要","状态","政策ID","确认人ID")
VALUES ('voucher','co','2026-10-01','2026-10-01','V-001','测试凭证','草稿','policy','person');
INSERT INTO finance."会计分录表"("分录ID","凭证ID","行号","科目ID","借方金额","贷方金额","币种")
VALUES ('d','voucher',1,'debit',100,0,'CNY'),('c','voucher',2,'credit',0,100,'CNY');
SET CONSTRAINTS ALL IMMEDIATE;
SELECT pg_temp.assert_ok('draft excluded from ledger',(SELECT count(*)=0 FROM (SELECT l.*, v."主体ID", v."凭证日期", v."所属月份", v."凭证号" FROM finance."会计分录表" l JOIN finance."会计凭证表" v USING ("凭证ID") WHERE v."状态" = '已过账')));
UPDATE finance."会计凭证表" SET "状态"='已过账' WHERE "凭证ID"='voucher';
SELECT pg_temp.assert_ok('balanced voucher posted',(SELECT count(*)=2 FROM (SELECT l.*, v."主体ID", v."凭证日期", v."所属月份", v."凭证号" FROM finance."会计分录表" l JOIN finance."会计凭证表" v USING ("凭证ID") WHERE v."状态" = '已过账')));
SELECT pg_temp.expect_error('posted lines immutable',$q$UPDATE finance."会计分录表" SET "借方金额"=101 WHERE "分录ID"='d'$q$,'23514');
SELECT pg_temp.expect_error('posted header immutable',$q$UPDATE finance."会计凭证表" SET "状态"='草稿' WHERE "凭证ID"='voucher'$q$,'23514');
SELECT pg_temp.expect_error('posted account owner immutable',$q$UPDATE finance."会计科目表" SET "主体ID"='other' WHERE "科目ID"='debit'$q$,'23514');

INSERT INTO finance."会计凭证表"("凭证ID","主体ID","凭证日期","所属月份","凭证号","摘要","状态","政策ID","确认人ID")
VALUES ('bad-v','co','2026-10-01','2026-10-01','V-002','未平凭证','草稿','policy','person');
INSERT INTO finance."会计分录表"("分录ID","凭证ID","行号","科目ID","借方金额","贷方金额","币种")
VALUES ('bad-d','bad-v',1,'debit',10,0,'CNY');
SELECT pg_temp.expect_error('unbalanced voucher rejected',$q$UPDATE finance."会计凭证表" SET "状态"='已过账' WHERE "凭证ID"='bad-v'$q$,'23514');
INSERT INTO finance."会计分录表"("分录ID","凭证ID","行号","科目ID","借方金额","贷方金额","币种")
VALUES ('bad-c','bad-v',2,'credit',0,10,'USD');
SELECT pg_temp.expect_error('cross currency balancing rejected',$q$UPDATE finance."会计凭证表" SET "状态"='已过账' WHERE "凭证ID"='bad-v'$q$,'23514');
UPDATE finance."会计分录表" SET "币种"='CNY',"科目ID"='wrong' WHERE "分录ID"='bad-c';
SELECT pg_temp.expect_error('wrong subject rejected',$q$UPDATE finance."会计凭证表" SET "状态"='已过账' WHERE "凭证ID"='bad-v'$q$,'23514');
UPDATE finance."会计分录表" SET "科目ID"='credit' WHERE "分录ID"='bad-c';
UPDATE finance."会计凭证表" SET "所属月份"='2026-09-01' WHERE "凭证ID"='bad-v';
SELECT pg_temp.expect_error('wrong accounting month rejected',$q$UPDATE finance."会计凭证表" SET "状态"='已过账' WHERE "凭证ID"='bad-v'$q$,'23514');
DELETE FROM finance."会计分录表" WHERE "凭证ID"='bad-v';
DELETE FROM finance."会计凭证表" WHERE "凭证ID"='bad-v';

INSERT INTO finance."交付记录表"("交付ID","交付名称","交付版本","数据截止时间","交付时间","确认人ID")
VALUES ('delivery','测试交付','v1',now(),now(),'person');
INSERT INTO finance."交付明细表"("交付明细ID","交付ID","会计凭证表引用") VALUES ('delivery-row','delivery','voucher');
INSERT INTO analysis."数据引用登记表" VALUES ('dataset','测试数据集','1','2026-10-01','2026-10-31',now(),now(),'测试接收');
INSERT INTO analysis."数据集输入来源表"("输入来源ID","数据集ID","接收时间","finance交付ID") VALUES ('input','dataset',now(),'delivery');
SELECT pg_temp.assert_ok('analysis traces source delivery and voucher',
 (SELECT count(*)=1 FROM analysis."数据集输入来源表" s JOIN finance."交付明细表" d ON d."交付ID"=s."finance交付ID" WHERE d."会计凭证表引用"='voucher'));
SELECT pg_temp.assert_ok('valid baseline no diagnostic issues',(SELECT count(*)=0 FROM (SELECT '资金用途超额'::text AS "规则", f."资金记录ID" AS "记录ID", '已核定用途合计超过流水金额'::text AS "说明"
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
HAVING sum(f."数量")>x."应履约数量")));
UPDATE finance."资金用途核定表" SET "核定金额"=101 WHERE "用途核定ID"='purpose';
SELECT pg_temp.assert_ok('diagnostics detect excess fund purpose',EXISTS(SELECT 1 FROM (SELECT '资金用途超额'::text AS "规则", f."资金记录ID" AS "记录ID", '已核定用途合计超过流水金额'::text AS "说明"
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
HAVING sum(f."数量")>x."应履约数量") WHERE "规则"='资金用途超额'));
UPDATE finance."资金用途核定表" SET "核定金额"=100 WHERE "用途核定ID"='purpose';
INSERT INTO finance."发票登记表" VALUES ('invoice','I001','蓝字','2026-10-01','co',NULL,100,10,'CNY','test.pdf');
INSERT INTO finance."发票分摊表" VALUES ('invalloc','invoice','line',NULL,99,10);
SELECT pg_temp.assert_ok('diagnostics detect invoice mismatch',EXISTS(SELECT 1 FROM (SELECT '资金用途超额'::text AS "规则", f."资金记录ID" AS "记录ID", '已核定用途合计超过流水金额'::text AS "说明"
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
HAVING sum(f."数量")>x."应履约数量") WHERE "规则"='发票分摊差异'));
UPDATE finance."发票分摊表" SET "分摊金额"=100 WHERE "发票分摊ID"='invalloc';
INSERT INTO rd."研发工时表" VALUES ('rh','project','person','2026-10-01',2,'测试开发',NULL);
INSERT INTO finance."工时计价表" VALUES ('price',NULL,'rh','2026-10-01','test',3,'人工确认',30,'CNY','person','已核定');
SELECT pg_temp.assert_ok('diagnostics detect repeated priced hours',EXISTS(SELECT 1 FROM (SELECT '资金用途超额'::text AS "规则", f."资金记录ID" AS "记录ID", '已核定用途合计超过流水金额'::text AS "说明"
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
HAVING sum(f."数量")>x."应履约数量") WHERE "规则"='工时计价超量'));
UPDATE finance."工时计价表" SET "计价工时"=2 WHERE "计价ID"='price';
INSERT INTO rd."研发投入归属表" VALUES ('input1','project',NULL,'price',0.6,'测试','person'),('input2','project',NULL,'price',0.6,'测试','person');
SELECT pg_temp.assert_ok('diagnostics detect allocation above 100 percent',EXISTS(SELECT 1 FROM (SELECT '资金用途超额'::text AS "规则", f."资金记录ID" AS "记录ID", '已核定用途合计超过流水金额'::text AS "说明"
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
HAVING sum(f."数量")>x."应履约数量") WHERE "规则"='投入比例超额'));
UPDATE rd."研发投入归属表" SET "归属比例"=0.4 WHERE "投入登记ID"='input2';
UPDATE production."到货记录表" SET "数量"=11 WHERE "到货ID"='arrive';
SELECT pg_temp.assert_ok('diagnostics detect excess arrivals',EXISTS(SELECT 1 FROM (SELECT '资金用途超额'::text AS "规则", f."资金记录ID" AS "记录ID", '已核定用途合计超过流水金额'::text AS "说明"
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
HAVING sum(f."数量")>x."应履约数量") WHERE "规则"='到货超量'));
UPDATE production."到货记录表" SET "数量"=10 WHERE "到货ID"='arrive';
SELECT pg_temp.assert_ok('resolved diagnostics clear',(SELECT count(*)=0 FROM (SELECT '资金用途超额'::text AS "规则", f."资金记录ID" AS "记录ID", '已核定用途合计超过流水金额'::text AS "说明"
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
HAVING sum(f."数量")>x."应履约数量")));
SELECT pg_temp.assert_ok('quantity version baseline clean',(SELECT count(*)=0 FROM (SELECT '验收单位待核'::text AS "规则",a."验收ID" AS "记录ID",'验收与到货单位不同，需按适用换算另核对'::text AS "说明"
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
 OR (oc."订单组合明细ID" IS NOT NULL AND oc."销售订单行ID"<>l."销售订单行ID"))));
INSERT INTO rd."计量单位表" VALUES ('box','BOX','箱','数量');
UPDATE production."发货记录表" SET "单位ID"='box' WHERE "发货事件ID"='ship';
SELECT pg_temp.assert_ok('different units require review',EXISTS(SELECT 1 FROM (SELECT '验收单位待核'::text AS "规则",a."验收ID" AS "记录ID",'验收与到货单位不同，需按适用换算另核对'::text AS "说明"
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
 OR (oc."订单组合明细ID" IS NOT NULL AND oc."销售订单行ID"<>l."销售订单行ID")) WHERE "规则"='发货单位待核'));
UPDATE production."发货记录表" SET "单位ID"='unit' WHERE "发货事件ID"='ship';
INSERT INTO production."工单订单对应表" VALUES ('link','work','line',3,'unit',NULL);
SELECT pg_temp.assert_ok('work order product matches',(SELECT count(*)=0 FROM (SELECT '验收单位待核'::text AS "规则",a."验收ID" AS "记录ID",'验收与到货单位不同，需按适用换算另核对'::text AS "说明"
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
 OR (oc."订单组合明细ID" IS NOT NULL AND oc."销售订单行ID"<>l."销售订单行ID"))));
INSERT INTO rd."产品版本表" VALUES ('pv2','project','pid','v2','2026-10-01','测试版本');
UPDATE sales."销售订单行表" SET "产品版本ID"='pv2' WHERE "销售订单行ID"='line';
SELECT pg_temp.assert_ok('wrong work order product detected',EXISTS(SELECT 1 FROM (SELECT '验收单位待核'::text AS "规则",a."验收ID" AS "记录ID",'验收与到货单位不同，需按适用换算另核对'::text AS "说明"
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
 OR (oc."订单组合明细ID" IS NOT NULL AND oc."销售订单行ID"<>l."销售订单行ID")) WHERE "规则"='工单产品不匹配'));
UPDATE sales."销售订单行表" SET "产品版本ID"='pv' WHERE "销售订单行ID"='line';
COMMIT;
