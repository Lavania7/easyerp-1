-- Runtime additions. The 146 business tables in 001..004 remain source-faithful.
CREATE SCHEMA erp_ops;
CREATE TABLE erp_ops.schema_version (
    version text PRIMARY KEY,
    source_sha256 text NOT NULL,
    build_sha256 text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

-- Index referencing columns unless an existing index has the same leading column.
DO $$
DECLARE r record;
BEGIN
 FOR r IN
  SELECT DISTINCT c.conrelid, c.conkey[1] AS attnum, a.attname
  FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
  JOIN pg_namespace n ON n.oid=c.connamespace
  WHERE c.contype='f' AND n.nspname IN ('finance','legal','production','rd','sales','analysis')
 LOOP
  IF NOT EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid=r.conrelid
                 AND i.indkey[0]=r.attnum AND i.indpred IS NULL AND i.indisvalid) THEN
   EXECUTE format('CREATE INDEX %I ON %s (%I)',
       'fk_' || r.conrelid || '_' || r.attnum, r.conrelid::regclass, r.attname);
  END IF;
 END LOOP;
END $$;

-- Deferred check permits writing both sides of a voucher in one transaction.
-- A header lock serializes line edits and posting of the same voucher.
CREATE FUNCTION erp_ops.guard_voucher_lines() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text; s text;
BEGIN
 FOR k IN SELECT DISTINCT v FROM unnest(ARRAY[
   CASE WHEN TG_OP<>'INSERT' THEN OLD."凭证ID" END,
   CASE WHEN TG_OP<>'DELETE' THEN NEW."凭证ID" END]) v WHERE v IS NOT NULL ORDER BY v
 LOOP
  SELECT "状态" INTO s FROM finance."会计凭证表" WHERE "凭证ID"=k FOR UPDATE;
  IF s='已过账' THEN RAISE EXCEPTION '已过账凭证 % 的分录不能修改；请建立调整凭证',k USING ERRCODE='23514'; END IF;
 END LOOP;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER guard_voucher_lines BEFORE INSERT OR UPDATE OR DELETE
ON finance."会计分录表" FOR EACH ROW EXECUTE FUNCTION erp_ops.guard_voucher_lines();

CREATE FUNCTION erp_ops.freeze_posted_voucher() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD."状态"='已过账' THEN
  RAISE EXCEPTION '已过账凭证不可覆盖或删除；请建立调整凭证' USING ERRCODE='23514';
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER freeze_posted BEFORE UPDATE OR DELETE ON finance."会计凭证表"
FOR EACH ROW EXECUTE FUNCTION erp_ops.freeze_posted_voucher();

CREATE FUNCTION erp_ops.check_voucher() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v finance."会计凭证表"%ROWTYPE;
BEGIN
 SELECT * INTO v FROM finance."会计凭证表" WHERE "凭证ID"=NEW."凭证ID";
 IF NOT FOUND OR v."状态" <> '已过账' THEN RETURN NULL; END IF;
 IF v."确认人ID" IS NULL OR v."所属月份"<>date_trunc('month',v."凭证日期")::date THEN
  RAISE EXCEPTION '凭证 % 缺少确认人或所属月份不匹配',v."凭证ID" USING ERRCODE='23514';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM finance."会计分录表" WHERE "凭证ID"=v."凭证ID") OR EXISTS (
  SELECT 1 FROM finance."会计分录表" WHERE "凭证ID"=v."凭证ID"
  GROUP BY "币种" HAVING sum("借方金额")<>sum("贷方金额")
 ) THEN RAISE EXCEPTION '凭证 % 按币种借贷不平衡或没有分录',v."凭证ID" USING ERRCODE='23514'; END IF;
 IF EXISTS (SELECT 1 FROM finance."会计分录表" l JOIN finance."会计科目表" a USING ("科目ID")
            WHERE l."凭证ID"=v."凭证ID" AND a."主体ID"<>v."主体ID") THEN
  RAISE EXCEPTION '凭证 % 引用其他主体科目',v."凭证ID" USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER check_voucher AFTER INSERT OR UPDATE ON finance."会计凭证表"
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION erp_ops.check_voucher();

-- Accounting identities must not be silently changed after posting.
CREATE FUNCTION erp_ops.guard_posted_account() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW."主体ID" IS DISTINCT FROM OLD."主体ID" AND EXISTS (
  SELECT 1 FROM finance."会计分录表" l JOIN finance."会计凭证表" v USING ("凭证ID")
  WHERE l."科目ID"=OLD."科目ID" AND v."状态"='已过账') THEN
  RAISE EXCEPTION '已过账科目的主体不可改变' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_posted_account BEFORE UPDATE ON finance."会计科目表"
FOR EACH ROW EXECUTE FUNCTION erp_ops.guard_posted_account();

-- Diagnostic findings are candidates requiring review, never inferred business facts.
CREATE VIEW erp_ops."业务核对问题" AS
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
HAVING sum(f."数量")>x."应履约数量";

-- These two checks deliberately distinguish NULL (not yet established) from zero.
CREATE VIEW erp_ops."资金核对" AS
WITH u AS (SELECT "资金记录ID",sum("核定金额") AS total FROM finance."资金用途核定表" WHERE "状态"='已核定' GROUP BY 1),
a AS (SELECT u."资金记录ID",sum(a."分摊金额") AS total FROM finance."结算分摊表" a
      JOIN finance."资金用途核定表" u USING ("用途核定ID") WHERE u."状态"='已核定' GROUP BY 1)
SELECT f."资金记录ID",f."金额",u.total AS "已核定用途金额",a.total AS "已核定分摊金额",
f."金额"-u.total AS "用途差额",f."金额"-a.total AS "分摊差额",
EXISTS(SELECT 1 FROM finance."重复记录对应表" d WHERE d."重复资金记录ID"=f."资金记录ID" AND d."状态"='已核定') AS "已确认重复",
EXISTS(SELECT 1 FROM finance."内部划转对应表" t WHERE (t."转出资金记录ID"=f."资金记录ID" OR t."转入资金记录ID"=f."资金记录ID") AND t."状态"='已核定') AS "已确认内部划转"
FROM finance."资金流水表" f LEFT JOIN u USING ("资金记录ID") LEFT JOIN a USING ("资金记录ID");
