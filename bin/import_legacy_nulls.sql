-- Preserve absent legacy facts as NULL without fake entities or zero amounts.
-- The source schema files and their checksums remain intact. This migration
-- records every changed NOT NULL flag and preserves all keys and constraints.
CREATE TABLE IF NOT EXISTS erp_ops.source_import_nullability (
 schema_name text NOT NULL, table_name text NOT NULL, column_name text NOT NULL,
 was_required boolean NOT NULL, changed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(schema_name,table_name,column_name)
);
DO $nulls$
DECLARE r record; was_required boolean;
BEGIN
 FOR r IN SELECT * FROM (VALUES
 ('finance','资金账户档案表','主体ID'),
 ('finance','资金账户档案表','币种'),
 ('finance','流水文件登记表','导出时间'),
 ('sales','渠道档案表','平台名称'),
 ('sales','渠道档案表','店铺标识'),
 ('sales','平台文件登记表','导出时间'),
 ('sales','销售订单登记表','币种'),
 ('sales','销售订单行表','数量'),
 ('sales','销售订单行表','单位ID'),
 ('sales','销售订单行表','单价'),
 ('sales','销售订单行表','折扣金额'),
 ('sales','销售订单行表','商品实付'),
 ('sales','销售订单行表','运费分摊'),
 ('sales','销售订单行表','取消数量')
 ) AS fields(schema_name,table_name,column_name)
 LOOP
  SELECT a.attnotnull INTO STRICT was_required FROM pg_attribute a
  WHERE a.attrelid=format('%I.%I',r.schema_name,r.table_name)::regclass
  AND a.attname=r.column_name AND NOT a.attisdropped;
  INSERT INTO erp_ops.source_import_nullability(schema_name,table_name,column_name,was_required)
  VALUES(r.schema_name,r.table_name,r.column_name,was_required) ON CONFLICT DO NOTHING;
  EXECUTE format('ALTER TABLE %I.%I ALTER COLUMN %I DROP NOT NULL',r.schema_name,r.table_name,r.column_name);
 END LOOP;
END $nulls$;

CREATE TABLE IF NOT EXISTS erp_ops.source_import_file (
 file_id text PRIMARY KEY, source_root text NOT NULL, relative_path text NOT NULL,
 file_sha256 text NOT NULL, size_bytes bigint NOT NULL, format_id text NOT NULL,
 header jsonb, metadata jsonb NOT NULL, imported_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_root,relative_path,file_sha256)
);
CREATE TABLE IF NOT EXISTS erp_ops.source_import_row (
 row_id text PRIMARY KEY, file_id text NOT NULL REFERENCES erp_ops.source_import_file,
 sheet_name text NOT NULL, row_no integer NOT NULL CHECK(row_no>0), record_type text NOT NULL,
 raw_values jsonb NOT NULL, mapped_ids jsonb NOT NULL,
 UNIQUE(file_id,sheet_name,row_no)
);
CREATE TABLE IF NOT EXISTS erp_ops.source_import_exception (
 exception_id text PRIMARY KEY, file_id text REFERENCES erp_ops.source_import_file,
 row_no integer, order_id text REFERENCES sales."销售订单登记表"("订单ID"),
 reason_code text NOT NULL, details text NOT NULL
);
CREATE TABLE IF NOT EXISTS erp_ops.source_import_run (
 run_id text PRIMARY KEY, importer_version text NOT NULL, manifest_sha256 text NOT NULL,
 source_manifest jsonb NOT NULL, report jsonb NOT NULL,
 committed_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE VIEW erp_ops."导入待补事项" AS
SELECT e.exception_id AS "事项ID",e.reason_code AS "原因",e.details AS "说明",
 f.relative_path AS "来源文件",e.row_no AS "来源行号",o."平台订单号"
FROM erp_ops.source_import_exception e
LEFT JOIN erp_ops.source_import_file f USING(file_id)
LEFT JOIN sales."销售订单登记表" o ON o."订单ID"=e.order_id;
GRANT SELECT ON erp_ops.source_import_file,erp_ops.source_import_row,
 erp_ops.source_import_exception,erp_ops.source_import_run,
 erp_ops.source_import_nullability,erp_ops."导入待补事项"
TO easyerp_app,easyerp_read;
