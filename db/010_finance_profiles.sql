CREATE TABLE IF NOT EXISTS erp_ops.account_profile_retired_fields (
  upgrade_id text NOT NULL,
  account_id text NOT NULL,
  balance_source text,
  source_database text NOT NULL DEFAULT current_database(),
  source_table text NOT NULL DEFAULT 'finance.资金账户档案表',
  source_field text NOT NULL DEFAULT '余额来源',
  archived_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (upgrade_id, account_id)
);
REVOKE ALL ON erp_ops.account_profile_retired_fields FROM PUBLIC,easyerp_app,easyerp_read;

ALTER TABLE finance."人员档案表"
  ADD COLUMN IF NOT EXISTS "基准工资" numeric(20,4),
  ADD COLUMN IF NOT EXISTS "工资账户开户行" text,
  ADD COLUMN IF NOT EXISTS "工资账户ID" text;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='finance."人员档案表"'::regclass
      AND conname='finance_people_base_salary_nonnegative') THEN
    ALTER TABLE finance."人员档案表" ADD CONSTRAINT finance_people_base_salary_nonnegative CHECK ("基准工资" >= 0);
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='finance."资金账户档案表"'::regclass
      AND attname='余额来源' AND NOT attisdropped) THEN
    IF EXISTS (SELECT 1 FROM pg_depend d JOIN pg_attribute a
        ON a.attrelid=d.refobjid AND a.attnum=d.refobjsubid
        WHERE d.refclassid='pg_class'::regclass AND a.attrelid='finance."资金账户档案表"'::regclass
          AND a.attname='余额来源' AND NOT a.attisdropped) THEN
      RAISE EXCEPTION 'Balance source has database dependencies; review before removal';
    END IF;
    INSERT INTO erp_ops.account_profile_retired_fields(upgrade_id,account_id,balance_source)
      SELECT '010_finance_profiles',"账户ID","余额来源" FROM finance."资金账户档案表";
    ALTER TABLE finance."资金账户档案表" DROP COLUMN "余额来源" RESTRICT;
  END IF;
END $$;

COMMENT ON COLUMN finance."人员档案表"."基准工资" IS '基准工资金额，numeric(20,4)；未知为NULL，真实零保留；不是实际发薪、付款或费用事实。';
COMMENT ON COLUMN finance."人员档案表"."工资账户开户行" IS '工资收款账户开户行；未知为NULL。';
COMMENT ON COLUMN finance."人员档案表"."工资账户ID" IS '工资收款账号或账户标识，按文本保留前导零；不是本公司资金账户档案表的外键。';
