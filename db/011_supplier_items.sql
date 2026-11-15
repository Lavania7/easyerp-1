DO $$ BEGIN
 IF to_regclass('erp_ops.business_id_rules') IS NOT NULL THEN
   INSERT INTO erp_ops.business_id_rules(table_key,pk_column,prefix,department)
   VALUES ('production.供应物品明细表','供应关系ID','SPM','PRD')
   ON CONFLICT(table_key) DO NOTHING;
   IF NOT EXISTS (SELECT 1 FROM erp_ops.business_id_rules WHERE table_key='production.供应物品明细表' AND pk_column='供应关系ID' AND prefix='SPM' AND department='PRD') THEN
     RAISE EXCEPTION 'Supplier item identifier rule differs';
   END IF;
   IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='production."供应物品明细表"'::regclass AND tgname='business_id_format') THEN
     CREATE TRIGGER business_id_format BEFORE INSERT OR UPDATE OF "供应关系ID" ON production."供应物品明细表"
       FOR EACH ROW EXECUTE FUNCTION erp_ops.check_business_id();
   END IF;
 END IF;
END $$;
