-- Add source snapshots without interpreting them as operational postings.
CREATE TABLE IF NOT EXISTS erp_ops.source_workbook_record (
 record_id text PRIMARY KEY, file_id text NOT NULL REFERENCES erp_ops.source_import_file,
 sheet_name text NOT NULL, row_no integer NOT NULL CHECK(row_no>0),
 record_kind text NOT NULL, source_key text NOT NULL, source_data jsonb NOT NULL,
 derived_data jsonb NOT NULL, mapped_ids jsonb NOT NULL,
 UNIQUE(file_id,sheet_name,row_no)
);
CREATE TABLE IF NOT EXISTS erp_ops.source_import_definition (
 change_id text PRIMARY KEY, object_name text NOT NULL,
 previous_definition text NOT NULL, changed_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO erp_ops.source_import_definition(change_id,object_name,previous_definition)
SELECT 'release2-approved-bom-null-guard','rd.已核定BOM明细表',
 pg_get_viewdef('rd."已核定BOM明细表"'::regclass,true) ON CONFLICT DO NOTHING;

-- Missing version, unit or confirmation evidence must not enter the approved view.
CREATE OR REPLACE VIEW rd."已核定BOM明细表" AS
SELECT l.*,v."MID" FROM rd."BOM明细表" l
JOIN rd."物料版本表" v USING("物料版本ID")
JOIN rd."BOM登记表" b USING("BOM登记ID")
JOIN rd."产品版本表" pv USING("产品版本ID")
WHERE b."BOM版本" IS NOT NULL AND b."确认依据" IS NOT NULL
 AND pv."版本名称" IS NOT NULL AND pv."确认依据" IS NOT NULL
 AND v."版本名称" IS NOT NULL AND v."确认依据" IS NOT NULL
 AND l."单位ID" IS NOT NULL AND l."确认依据" IS NOT NULL;

CREATE OR REPLACE VIEW erp_ops."导入产品库存与报价" AS
SELECT r.record_id AS "来源记录ID",r.source_key AS "PID",r.source_data->>'名称' AS "产品名称",
 (r.source_data->>'现有库存')::numeric AS "原表库存",NULL::date AS "盘点日期",NULL::text AS "单位",
 (r.source_data->>'售价')::numeric AS "原表售价",NULL::text AS "币种",
 (r.source_data->>'附加成本')::numeric AS "原表附加成本",
 (r.source_data->>'原料成本')::numeric AS "原表原料成本",
 (r.derived_data->>'完整原料成本')::numeric AS "独立算得原料成本",
 (r.source_data->>'总成本')::numeric AS "原表总成本",
 r.source_data->>'总成本原文' AS "原表成本说明",
 (r.derived_data->>'未对应BOM行数')::integer AS "未对应BOM行数",
 '来源快照，库存日期、版本及成本归属未核定'::text AS "核定状态",
 r.file_id AS "来源文件ID",r.sheet_name AS "来源工作表",r.row_no AS "来源行号"
FROM erp_ops.source_workbook_record r WHERE r.record_kind='product';

CREATE OR REPLACE VIEW erp_ops."导入物料库存与单价" AS
SELECT r.record_id AS "来源记录ID",r.source_key AS "MID",r.source_data->>'名称' AS "物料名称",
 r.source_data->>'供应商料号' AS "供应商料号",r.source_data->>'类型' AS "类别",
 (r.source_data->>'现有库存')::numeric AS "原表库存",NULL::date AS "盘点日期",NULL::text AS "单位",
 (r.source_data->>'采购单价')::numeric AS "原表采购单价",NULL::text AS "币种",
 (r.source_data->>'原表货存总价')::numeric AS "原表货存总价",
 '来源快照，日期与计价依据未核定'::text AS "核定状态",
 r.file_id AS "来源文件ID",r.sheet_name AS "来源工作表",r.row_no AS "来源行号"
FROM erp_ops.source_workbook_record r WHERE r.record_kind='material';

CREATE OR REPLACE VIEW erp_ops."导入BOM与物料对应" AS
SELECT l."BOM明细ID",pv."PID",p."名称" AS "产品名称",b."BOM版本",l."行号",v."MID",
 l."单件用量",l."单位ID",l."原始器件描述",l."位号",l."封装",l."厂家料号",l."供应商料号",
 CASE WHEN l."物料版本ID" IS NULL THEN '待登记物料' ELSE '原文名称已对应，版本与单位待核' END AS "对应状态",
 '未核定BOM'::text AS "核定状态",l."来源文件ID",'BOM总表'::text AS "来源工作表",l."来源行号"
FROM rd."BOM明细表" l JOIN rd."BOM登记表" b USING("BOM登记ID")
JOIN rd."产品版本表" pv USING("产品版本ID") JOIN rd."产品主数据表" p USING("PID")
LEFT JOIN rd."物料版本表" v USING("物料版本ID")
JOIN erp_ops.source_import_file f ON f.file_id=l."来源文件ID" AND f.format_id='release2-workbook-v1';

CREATE OR REPLACE VIEW erp_ops."导入生产计划" AS
SELECT r.record_id AS "来源记录ID",r.source_key AS "PID",r.source_data->>'产品名称' AS "产品名称",
 (r.source_data->>'计划立即生产')::numeric AS "计划立即生产",
 (r.source_data->>'计划预备生产')::numeric AS "计划预备生产",
 (r.derived_data->>'计划合计')::numeric AS "计划生产合计",NULL::date AS "计划日期",
 r.mapped_ids->>'草稿登记ID' AS "草稿登记ID",'来源计划，未下达且未实际生产'::text AS "状态",
 r.file_id AS "来源文件ID",r.sheet_name AS "来源工作表",r.row_no AS "来源行号"
FROM erp_ops.source_workbook_record r WHERE r.record_kind='plan';

CREATE OR REPLACE VIEW erp_ops."导入物料需求" AS
SELECT r.record_id AS "来源记录ID",r.source_key AS "MID",r.source_data->>'名称' AS "物料名称",
 (r.source_data->>'原表毛需求')::numeric AS "原表毛需求",
 (r.source_data->>'原表建议采购量')::numeric AS "原表建议采购量",
 (r.source_data->>'原表预计采购花销')::numeric AS "原表预计采购花销",
 r.source_data->>'原表状态' AS "原表状态",NULL::numeric AS "完整需求",NULL::numeric AS "完整建议采购量",
 (r.derived_data->>'未对应BOM行数')::integer AS "未对应BOM行数",
 'BOM未完整对应，原表库存充足不代表完整需求已满足'::text AS "核对说明",
 r.file_id AS "来源文件ID",r.sheet_name AS "来源工作表",r.row_no AS "来源行号"
FROM erp_ops.source_workbook_record r WHERE r.record_kind='demand';

CREATE OR REPLACE VIEW erp_ops."导入其他物品" AS
SELECT r.record_id AS "来源记录ID",r.source_key AS "IID",r.source_data->>'名称' AS "登记名称",
 (r.source_data->>'数量')::numeric AS "原表数量",NULL::text AS "单位",NULL::date AS "盘点日期",
 (r.source_data->>'单价')::numeric AS "原表单价",(r.source_data->>'原表总金额')::numeric AS "原表总金额",
 NULL::text AS "币种",'来源快照，未作为库存基准或MID登记'::text AS "核定状态",
 r.file_id AS "来源文件ID",r.sheet_name AS "来源工作表",r.row_no AS "来源行号"
FROM erp_ops.source_workbook_record r WHERE r.record_kind='other';

CREATE OR REPLACE VIEW erp_ops."导入资产快照" AS
SELECT r.record_id AS "来源记录ID",r.source_key AS "资产项目",
 r.source_data->>'原表显示值' AS "原表显示值",(r.source_data->>'原表数值')::numeric AS "原表数值",
 NULL::numeric AS "已确认金额",NULL::date AS "基准日期",r.source_data->>'说明' AS "原表说明",
 '原表缓存或手填快照，未核定为资产余额'::text AS "核定状态",
 r.file_id AS "来源文件ID",r.sheet_name AS "来源工作表",r.row_no AS "来源行号"
FROM erp_ops.source_workbook_record r WHERE r.record_kind='asset';

GRANT SELECT ON erp_ops.source_workbook_record,erp_ops.source_import_definition,
 erp_ops."导入产品库存与报价",erp_ops."导入物料库存与单价",erp_ops."导入BOM与物料对应",
 erp_ops."导入生产计划",erp_ops."导入物料需求",erp_ops."导入其他物品",erp_ops."导入资产快照"
TO easyerp_read,easyerp_app;
