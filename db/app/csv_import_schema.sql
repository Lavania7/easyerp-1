-- Optional CSV business values stay NULL after the user confirms incomplete data.
-- Only the affected NOT NULL columns are relaxed, inside the import transaction.
CREATE TABLE IF NOT EXISTS erp_ops.frontend_csv_nullability (
    schema_name text NOT NULL,
    table_name text NOT NULL,
    column_name text NOT NULL,
    request_id text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    database_role text NOT NULL DEFAULT session_user,
    PRIMARY KEY (schema_name,table_name,column_name)
);
REVOKE ALL ON erp_ops.frontend_csv_nullability FROM PUBLIC;
GRANT SELECT ON erp_ops.frontend_csv_nullability TO easyerp_app,easyerp_read;
CREATE TABLE IF NOT EXISTS erp_ops.frontend_csv_presence_checks (
    schema_name text NOT NULL, table_name text NOT NULL, constraint_name text NOT NULL,
    old_definition text NOT NULL, new_definition text NOT NULL, request_id text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (schema_name,table_name,constraint_name)
);
REVOKE ALL ON erp_ops.frontend_csv_presence_checks FROM PUBLIC;
GRANT SELECT ON erp_ops.frontend_csv_presence_checks TO easyerp_app,easyerp_read;

CREATE OR REPLACE FUNCTION erp_ops.csv_allow_missing_fields(target regclass,fields text[],import_request text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,erp_ops,pg_temp AS $csv_nulls$
DECLARE schema_value text; table_value text; kind_value "char"; field_value text; attribute_value record; rule_value record; new_expression text;
BEGIN
    SELECT n.nspname,c.relname,c.relkind INTO schema_value,table_value,kind_value
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=target;
    IF schema_value IS NULL OR schema_value NOT IN ('sales','production','finance','rd','legal','analysis') OR kind_value<>'r' THEN
        RAISE EXCEPTION 'unsupported_csv_table' USING ERRCODE='22023';
    END IF;
    IF import_request IS NULL OR import_request !~ '^csv2-[0-9a-f]{64}$' OR fields IS NULL OR
       cardinality(fields) NOT BETWEEN 1 AND 256 OR array_position(fields,NULL) IS NOT NULL THEN
        RAISE EXCEPTION 'invalid_csv_request' USING ERRCODE='22023';
    END IF;
    FOR field_value IN SELECT DISTINCT unnest(fields) ORDER BY 1 LOOP
        SELECT a.attnum,a.attnotnull,a.attidentity,a.attgenerated,a.attinhcount INTO attribute_value
          FROM pg_catalog.pg_attribute a WHERE a.attrelid=target AND a.attname=field_value AND a.attnum>0 AND NOT a.attisdropped;
        IF NOT FOUND OR attribute_value.attidentity<>'' OR attribute_value.attgenerated<>'' OR attribute_value.attinhcount<>0 OR
           EXISTS(SELECT 1 FROM pg_catalog.pg_constraint p WHERE p.conrelid=target AND p.contype='p' AND attribute_value.attnum=ANY(p.conkey)) THEN
            RAISE EXCEPTION 'unsupported_csv_column' USING ERRCODE='22023';
        END IF;
        IF attribute_value.attnotnull THEN
            EXECUTE format('ALTER TABLE %I.%I ALTER COLUMN %I DROP NOT NULL',schema_value,table_value,field_value);
            INSERT INTO erp_ops.frontend_csv_nullability(schema_name,table_name,column_name,request_id)
              VALUES(schema_value,table_value,field_value,import_request) ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;
    -- An unresolved link may be NULL, but mutually exclusive links cannot both be filled.
    -- Only pure num_nonnulls(...)=1 checks whose entire link group is missing qualify.
    FOR rule_value IN
        SELECT p.conname,pg_get_expr(p.conbin,p.conrelid) AS expression,pg_get_constraintdef(p.oid) AS definition
          FROM pg_catalog.pg_constraint p
          WHERE p.conrelid=target AND p.contype='c' AND cardinality(p.conkey)>0
            AND NOT EXISTS(SELECT 1 FROM unnest(p.conkey) k JOIN pg_catalog.pg_attribute a ON a.attrelid=target AND a.attnum=k WHERE NOT(a.attname=ANY(fields)))
    LOOP
        IF rule_value.expression ~ '^\(*num_nonnulls\([^()]*\) = 1\)*$' THEN
            new_expression=replace(rule_value.expression,' = 1',' <= 1');
            EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I',schema_value,table_value,rule_value.conname);
            EXECUTE format('ALTER TABLE %I.%I ADD CONSTRAINT %I CHECK (%s)',schema_value,table_value,rule_value.conname,new_expression);
            INSERT INTO erp_ops.frontend_csv_presence_checks(schema_name,table_name,constraint_name,old_definition,new_definition,request_id)
              VALUES(schema_value,table_value,rule_value.conname,rule_value.definition,'CHECK ('||new_expression||')',import_request) ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;
END $csv_nulls$;
REVOKE ALL ON FUNCTION erp_ops.csv_allow_missing_fields(regclass,text[],text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION erp_ops.csv_allow_missing_fields(regclass,text[],text) TO easyerp_app;

-- Incomplete vouchers are not posted. Posting still requires complete facts and balanced entries.
CREATE OR REPLACE FUNCTION erp_ops.check_voucher() RETURNS trigger LANGUAGE plpgsql AS $csv_voucher$
DECLARE v finance."会计凭证表"%ROWTYPE;
BEGIN
    SELECT * INTO v FROM finance."会计凭证表" WHERE "凭证ID"=NEW."凭证ID";
    IF NOT FOUND OR v."状态" IS DISTINCT FROM '已过账' THEN RETURN NULL; END IF;
    IF v."主体ID" IS NULL OR v."凭证日期" IS NULL OR v."所属月份" IS NULL OR v."确认人ID" IS NULL OR
       v."所属月份"<>date_trunc('month',v."凭证日期")::date THEN
        RAISE EXCEPTION '凭证 % 缺少过账事实或所属月份不匹配',v."凭证ID" USING ERRCODE='23514';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM finance."会计分录表" WHERE "凭证ID"=v."凭证ID") OR EXISTS(
        SELECT 1 FROM finance."会计分录表" l WHERE l."凭证ID"=v."凭证ID" AND
          (l."科目ID" IS NULL OR l."币种" IS NULL OR l."借方金额" IS NULL OR l."贷方金额" IS NULL)
    ) OR EXISTS(
        SELECT 1 FROM finance."会计分录表" WHERE "凭证ID"=v."凭证ID" GROUP BY "币种" HAVING sum("借方金额")<>sum("贷方金额")
    ) THEN RAISE EXCEPTION '凭证 % 分录不完整、借贷不平衡或没有分录',v."凭证ID" USING ERRCODE='23514'; END IF;
    IF EXISTS(SELECT 1 FROM finance."会计分录表" l JOIN finance."会计科目表" a USING ("科目ID")
              WHERE l."凭证ID"=v."凭证ID" AND a."主体ID" IS DISTINCT FROM v."主体ID") THEN
        RAISE EXCEPTION '凭证 % 科目主体缺失或不一致',v."凭证ID" USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END $csv_voucher$;
