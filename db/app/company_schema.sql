-- Additive company profile fields; the original specification remains intact.
ALTER TABLE legal."公司主体档案表"
  ADD COLUMN IF NOT EXISTS "公司英文名" text,
  ADD COLUMN IF NOT EXISTS "公司简称" text,
  ADD COLUMN IF NOT EXISTS "联系电话" text,
  ADD COLUMN IF NOT EXISTS "联系邮箱" text,
  ADD COLUMN IF NOT EXISTS "办公地址" text,
  ADD COLUMN IF NOT EXISTS "官方网站" text,
  ADD COLUMN IF NOT EXISTS "联系人" text,
  ADD COLUMN IF NOT EXISTS "法定代表人" text,
  ADD COLUMN IF NOT EXISTS "成立日期" date,
  ADD COLUMN IF NOT EXISTS "经营范围" text,
  ADD COLUMN IF NOT EXISTS "备注" text;

CREATE TABLE IF NOT EXISTS erp_ops.frontend_company_profile_migration (
  version text PRIMARY KEY,
  sql_sha256 char(64) NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  backup_file text
);
REVOKE ALL ON erp_ops.frontend_company_profile_migration FROM PUBLIC;
GRANT SELECT ON erp_ops.frontend_company_profile_migration TO easyerp_read;
