-- Supplier collection details; never infer a reference to the company's accounts.
CREATE TABLE IF NOT EXISTS erp_ops.supplier_profile_retired_fields (
  upgrade_id text NOT NULL,
  supplier_id text NOT NULL,
  file_path text NOT NULL,
  archived_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (upgrade_id,supplier_id)
);
REVOKE ALL ON erp_ops.supplier_profile_retired_fields FROM PUBLIC,easyerp_app,easyerp_read;

ALTER TABLE production."供应商档案表"
  ADD COLUMN IF NOT EXISTS "统一社会信用代码" text,
  ADD COLUMN IF NOT EXISTS "户名" text,
  ADD COLUMN IF NOT EXISTS "账户ID" text,
  ADD COLUMN IF NOT EXISTS "开户行" text;
COMMENT ON COLUMN production."供应商档案表"."账户ID" IS '供应商收款账户标识或账号，按文本保存；不是本公司资金账户档案表的外键。';

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_attribute
      WHERE attrelid='production."供应商档案表"'::regclass
      AND attname='相关文件路径' AND NOT attisdropped) THEN
    INSERT INTO erp_ops.supplier_profile_retired_fields(upgrade_id,supplier_id,file_path)
      SELECT '008_supplier_profile',"供应商ID","相关文件路径"
      FROM production."供应商档案表" WHERE "相关文件路径" IS NOT NULL;
    -- RESTRICT refuses unknown dependencies instead of deleting them.
    ALTER TABLE production."供应商档案表" DROP COLUMN "相关文件路径" RESTRICT;
  END IF;
END $$;
