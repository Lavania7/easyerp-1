-- One inventory count now carries its optional balance evidence. No baseline required.
-- Existing records and all historical foreign keys are preserved.
ALTER TABLE production."库存盘点表"
  ADD COLUMN IF NOT EXISTS "期初数量" numeric(20,6),
  ADD COLUMN IF NOT EXISTS "收入数量" numeric(20,6),
  ADD COLUMN IF NOT EXISTS "发出数量" numeric(20,6),
  ADD COLUMN IF NOT EXISTS "账面数量" numeric(20,6),
  ADD COLUMN IF NOT EXISTS "余额说明" text;
CREATE TABLE IF NOT EXISTS erp_ops.frontend_workspace_migration (
  version text PRIMARY KEY,
  sql_sha256 char(64) NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  backup_file text NOT NULL
);
REVOKE ALL ON erp_ops.frontend_workspace_migration FROM PUBLIC;
GRANT SELECT ON erp_ops.frontend_workspace_migration TO easyerp_read;
