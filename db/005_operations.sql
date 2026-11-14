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


-- These two checks deliberately distinguish NULL (not yet established) from zero.
