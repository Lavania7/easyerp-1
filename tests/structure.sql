DO $$
DECLARE n integer; r record;
BEGIN
 SELECT count(*) INTO n FROM pg_namespace WHERE nspname IN ('finance','legal','production','rd','sales','analysis');
 IF n<>6 THEN RAISE EXCEPTION 'Expected 6 schemas, got %',n; END IF;
 SELECT count(*) INTO n FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis');
 IF n<>146 THEN RAISE EXCEPTION 'Expected 146 tables, got %',n; END IF;
 SELECT count(*) INTO n FROM pg_views WHERE schemaname IN ('finance','legal','production','rd','sales','analysis','erp_ops');
 IF n<>0 THEN RAISE EXCEPTION 'Expected no views, got %',n; END IF;
 SELECT count(*) INTO n FROM pg_constraint c JOIN pg_namespace s ON s.oid=c.connamespace
 WHERE s.nspname IN ('finance','legal','production','rd','sales','analysis') AND c.contype='f' AND c.convalidated;
 IF n<>475 THEN RAISE EXCEPTION 'Expected 475 validated foreign keys, got %',n; END IF;
 SELECT count(*) INTO n FROM pg_constraint c JOIN pg_namespace s ON s.oid=c.connamespace
 JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
 WHERE s.nspname IN ('finance','legal','production','rd','sales','analysis') AND c.contype='p'
 AND cardinality(c.conkey)=1 AND a.atttypid='text'::regtype;
 IF n<>146 THEN RAISE EXCEPTION 'Expected 146 single text primary keys, got %',n; END IF;
 SELECT count(*) INTO n FROM pg_matviews WHERE schemaname IN ('finance','legal','production','rd','sales','analysis','erp_ops');
 IF n<>0 THEN RAISE EXCEPTION 'Expected no materialized views, got %',n; END IF;
 IF current_setting('server_encoding')<>'UTF8' THEN RAISE EXCEPTION 'Expected UTF8'; END IF;
 IF EXISTS(SELECT 1 FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
  WHERE n.nspname IN ('finance','legal','production','rd','sales','analysis') AND NOT c.convalidated) THEN
  RAISE EXCEPTION 'Unvalidated constraints';
 END IF;
END $$;
