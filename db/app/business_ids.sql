-- Three business identifiers: short ID, immutable long ID, SHA-256(long ID).
CREATE TABLE IF NOT EXISTS erp_ops.business_id_rules (
 table_key text PRIMARY KEY, pk_column text NOT NULL,
 prefix text NOT NULL UNIQUE CHECK (prefix ~ '^[A-Z]{1,3}$'),
 department text NOT NULL CHECK (department ~ '^[A-Z]{1,3}$')
);
CREATE TABLE IF NOT EXISTS erp_ops.business_id_counters (
 table_key text PRIMARY KEY REFERENCES erp_ops.business_id_rules(table_key),
 last_number bigint NOT NULL DEFAULT 0 CHECK (last_number>=0)
);
CREATE TABLE IF NOT EXISTS erp_ops.business_id_aliases (
 table_key text NOT NULL REFERENCES erp_ops.business_id_rules(table_key),
 old_id text NOT NULL, new_id text NOT NULL, migration_id text NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(table_key,old_id)
);
CREATE INDEX IF NOT EXISTS business_id_alias_new ON erp_ops.business_id_aliases(table_key,new_id);
CREATE TABLE IF NOT EXISTS erp_ops.business_record_ids (
 table_key text NOT NULL REFERENCES erp_ops.business_id_rules(table_key),
 short_id text NOT NULL, long_id text NOT NULL UNIQUE, sha256 char(64) NOT NULL UNIQUE,
 issued_on date NOT NULL, PRIMARY KEY(table_key,short_id),
 CHECK (sha256=encode(sha256(convert_to(long_id,'UTF8')),'hex'))
);
CREATE TABLE IF NOT EXISTS erp_ops.business_id_allocations (
 table_key text NOT NULL REFERENCES erp_ops.business_id_rules(table_key),
 allocation_key text NOT NULL, id text NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(table_key,allocation_key), UNIQUE(table_key,id)
);
CREATE TABLE IF NOT EXISTS erp_ops.business_id_migrations (
 migration_id text PRIMARY KEY, recorded_at timestamptz NOT NULL DEFAULT now(),result jsonb NOT NULL
);
REVOKE ALL ON erp_ops.business_id_rules,erp_ops.business_id_counters,erp_ops.business_id_aliases,
 erp_ops.business_record_ids,erp_ops.business_id_allocations,erp_ops.business_id_migrations FROM PUBLIC;
GRANT SELECT ON erp_ops.business_id_rules,erp_ops.business_id_aliases,erp_ops.business_record_ids,
 erp_ops.business_id_migrations TO easyerp_read,easyerp_app;

CREATE OR REPLACE FUNCTION erp_ops.id_base36(number bigint) RETURNS text
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE value text:='';digit integer; BEGIN
 IF number<0 THEN RAISE EXCEPTION 'negative identifier sequence'; END IF;
 LOOP digit:=number%36;value:=substr('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',digit+1,1)||value;
 number:=number/36;EXIT WHEN number=0;END LOOP;
 RETURN lpad(value,greatest(3,length(value)),'0');
END $$;
CREATE OR REPLACE FUNCTION erp_ops.id_number(value text) RETURNS bigint
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE number bigint:=0; digit integer; letter text; BEGIN
 IF value !~ '^[0-9A-Z]{3,10}$' THEN RAISE EXCEPTION 'invalid identifier sequence';END IF;
 FOREACH letter IN ARRAY regexp_split_to_array(value,'') LOOP
 digit:=strpos('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',letter)-1;number:=number*36+digit;
 END LOOP;
 IF number=0 OR number>=1000000000000000 OR erp_ops.id_base36(number)<>value THEN
 RAISE EXCEPTION 'noncanonical identifier sequence';END IF;RETURN number;
END $$;

CREATE OR REPLACE FUNCTION erp_ops.ensure_business_identity(target text,short text,day date DEFAULT NULL)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,erp_ops AS $$
DECLARE rule erp_ops.business_id_rules%ROWTYPE;number bigint;long text;BEGIN
 SELECT * INTO STRICT rule FROM erp_ops.business_id_rules WHERE table_key=target;
 IF left(short,length(rule.prefix))<>rule.prefix THEN RAISE EXCEPTION 'wrong identifier prefix';END IF;
 number:=erp_ops.id_number(substring(short from length(rule.prefix)+1));
 day:=coalesce(day,(clock_timestamp() AT TIME ZONE 'Europe/Berlin')::date);
 long:=rule.department||'-'||rule.prefix||'-'||to_char(day,'YYYYMMDD')||'-'||lpad(number::text,greatest(3,length(number::text)),'0');
 INSERT INTO erp_ops.business_record_ids(table_key,short_id,long_id,sha256,issued_on)
 VALUES(target,short,long,encode(sha256(convert_to(long,'UTF8')),'hex'),day)
 ON CONFLICT(table_key,short_id) DO NOTHING;
END $$;
REVOKE ALL ON FUNCTION erp_ops.ensure_business_identity(text,text,date) FROM PUBLIC;

CREATE OR REPLACE FUNCTION erp_ops.allocate_business_ids(target text,keys text[])
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,erp_ops AS $$
DECLARE rule erp_ops.business_id_rules%ROWTYPE;number bigint;observed bigint;
 allocation text;allocated text;taken boolean;result jsonb:='[]'::jsonb;
BEGIN
 SELECT * INTO STRICT rule FROM erp_ops.business_id_rules WHERE table_key=target;
 IF cardinality(keys)>5000 OR cardinality(keys)<1 THEN RAISE EXCEPTION 'invalid allocation count';END IF;
 INSERT INTO erp_ops.business_id_counters(table_key) VALUES(target) ON CONFLICT DO NOTHING;
 SELECT last_number INTO number FROM erp_ops.business_id_counters WHERE table_key=target FOR UPDATE;
 EXECUTE format('SELECT coalesce(max(erp_ops.id_number(substring(%I from %s))),0) FROM %I.%I WHERE %I ~ $1',
 rule.pk_column,length(rule.prefix)+1,split_part(target,'.',1),split_part(target,'.',2),rule.pk_column)
 INTO observed USING '^'||rule.prefix||'[0-9A-Z]{3,10}$';
 number:=greatest(number,observed);
 FOREACH allocation IN ARRAY keys LOOP
 IF allocation IS NULL OR length(allocation)>300 THEN RAISE EXCEPTION 'invalid allocation key';END IF;
 SELECT id INTO allocated FROM erp_ops.business_id_allocations WHERE table_key=target AND allocation_key=allocation;
 IF NOT FOUND THEN
 LOOP number:=number+1;IF number>=1000000000000000 THEN RAISE EXCEPTION 'identifier range exhausted';END IF;
 allocated:=rule.prefix||erp_ops.id_base36(number);
 EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I.%I WHERE %I=$1)',split_part(target,'.',1),split_part(target,'.',2),rule.pk_column)
 INTO taken USING allocated;EXIT WHEN NOT taken;END LOOP;
 INSERT INTO erp_ops.business_id_allocations(table_key,allocation_key,id) VALUES(target,allocation,allocated);
 END IF;
 PERFORM erp_ops.ensure_business_identity(target,allocated);
 result:=result||jsonb_build_array(allocated);
 END LOOP;
 UPDATE erp_ops.business_id_counters SET last_number=number WHERE table_key=target;RETURN result;
END $$;
REVOKE ALL ON FUNCTION erp_ops.allocate_business_ids(text,text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION erp_ops.allocate_business_ids(text,text[]) TO easyerp_app;

CREATE OR REPLACE FUNCTION erp_ops.check_business_id() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,erp_ops AS $$
DECLARE rule erp_ops.business_id_rules%ROWTYPE;value text;BEGIN
 SELECT * INTO STRICT rule FROM erp_ops.business_id_rules WHERE table_key=TG_TABLE_SCHEMA||'.'||TG_TABLE_NAME;
 value:=to_jsonb(NEW)->>rule.pk_column;
 IF TG_OP='UPDATE' AND value IS DISTINCT FROM (to_jsonb(OLD)->>rule.pk_column) THEN
 RAISE EXCEPTION '记录编号不可直接修改；请使用受控编号迁移' USING ERRCODE='23514';END IF;
 BEGIN PERFORM erp_ops.ensure_business_identity(rule.table_key,value);
 EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION '记录编号须为 % 加至少三位大写36进制流水',rule.prefix USING ERRCODE='23514';END;
 RETURN NEW;
END $$;
