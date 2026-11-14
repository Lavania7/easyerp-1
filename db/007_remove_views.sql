-- Remove project views without cascading to tables, functions or other objects.
DO $$
DECLARE targets text;
BEGIN
 SELECT string_agg(format('%I.%I',n.nspname,c.relname),', ' ORDER BY n.nspname,c.relname)
 INTO targets FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname IN ('finance','legal','production','rd','sales','analysis','erp_ops') AND c.relkind='v';
 IF targets IS NOT NULL THEN EXECUTE 'DROP VIEW '||targets||' RESTRICT'; END IF;
 SELECT string_agg(format('%I.%I',n.nspname,c.relname),', ' ORDER BY n.nspname,c.relname)
 INTO targets FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname IN ('finance','legal','production','rd','sales','analysis','erp_ops') AND c.relkind='m';
 IF targets IS NOT NULL THEN EXECUTE 'DROP MATERIALIZED VIEW '||targets||' RESTRICT'; END IF;
END $$;
