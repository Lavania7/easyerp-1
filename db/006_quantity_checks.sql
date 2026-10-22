CREATE TABLE erp_ops.schema_upgrade_log (
 upgrade_id text PRIMARY KEY, from_build text NOT NULL, to_build text NOT NULL,
 source_sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE VIEW erp_ops."数量版本核对问题" AS
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
 OR (oc."订单组合明细ID" IS NOT NULL AND oc."销售订单行ID"<>l."销售订单行ID");
