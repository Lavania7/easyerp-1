"""Preview or apply the finance profile upgrade with backups and fact comparisons."""
from pathlib import Path
import argparse
import hashlib
import json

from easyerp import ERP, ident as I, literal as L

ROOT = Path(__file__).resolve().parents[1]
VERSION = '010_finance_profiles'
PEOPLE = 'finance.人员档案表'
ACCOUNTS = 'finance.资金账户档案表'
OLD_PEOPLE = ['人员ID', '姓名', '部门', '任职开始日期', '任职结束日期']
NEW_FIELDS = ['基准工资', '工资账户开户行', '工资账户ID']
OLD_ACCOUNTS = ['账户ID', '账户名', '主体ID', '平台', '币种', '账户性质', '启用日期', '停用日期', '余额来源']


def columns(erp, db, key):
    schema, name = key.split('.', 1)
    return json.loads(erp.sql(f"""SELECT json_agg(json_build_object('name',attname,
      'type',format_type(atttypid,atttypmod),'required',attnotnull,
      'default',pg_get_expr(d.adbin,d.adrelid)) ORDER BY attnum)
      FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
      WHERE a.attrelid={L(I(schema)+'.'+I(name))}::regclass
        AND attnum>0 AND NOT attisdropped""", db=db, role='easyerp_read').stdout)


def snapshot_query(erp, db, omit_changed=True):
    tables = erp.sql("""SELECT schemaname||'.'||tablename FROM pg_tables
      WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1""",
      db=db, role='easyerp_read').stdout.splitlines()
    queries = []
    for key in tables:
        schema, name = key.split('.', 1)
        value = 'to_jsonb(t)'
        if omit_changed and key == PEOPLE:
            value += "-ARRAY['基准工资','工资账户开户行','工资账户ID']"
        if omit_changed and key == ACCOUNTS:
            value += "-'余额来源'"
        queries.append(f"SELECT {L(key)} AS object,count(*) AS rows,md5(coalesce(string_agg(({value})::text,E'\\n' ORDER BY ({value})::text),'')) AS hash FROM {I(schema)}.{I(name)} t")
    return tables, ' UNION ALL '.join(queries)


def dependencies(erp, db):
    return json.loads(erp.sql("""SELECT coalesce(json_agg(json_build_object(
      'type',d.deptype,'dependent',pg_describe_object(d.classid,d.objid,d.objsubid))),'[]')
      FROM pg_depend d JOIN pg_attribute a ON a.attrelid=d.refobjid AND a.attnum=d.refobjsubid
      WHERE d.refclassid='pg_class'::regclass AND a.attrelid='finance."资金账户档案表"'::regclass
        AND a.attname='余额来源' AND NOT a.attisdropped""", db=db, role='easyerp_read').stdout)


def prior_versions(manifest):
    prior = manifest['finance_profile_upgrade_from']
    digest = hashlib.sha256(json.dumps(prior['sql_files'], sort_keys=True).encode()).hexdigest()
    return {source + '|' + digest for source in prior['source_sha256s']}


def verify_shape(erp, db, upgraded):
    people = columns(erp, db, PEOPLE)
    accounts = columns(erp, db, ACCOUNTS)
    if [c['name'] for c in people] != OLD_PEOPLE + (NEW_FIELDS if upgraded else []):
        raise RuntimeError('Unexpected personnel columns')
    if [c['name'] for c in accounts] != OLD_ACCOUNTS[:8 if upgraded else 9]:
        raise RuntimeError('Unexpected account columns')
    if [c['type'] for c in people] != ['text','text','text','date','date'] + (['numeric(20,4)','text','text'] if upgraded else []):
        raise RuntimeError('Unexpected personnel field types')
    if [c['type'] for c in accounts] != ['text','text','text','text','character(3)','text','date','date'] + ([] if upgraded else ['text']):
        raise RuntimeError('Unexpected account field types')
    if upgraded and any(c['required'] or c['default'] is not None for c in people[-3:]):
        raise RuntimeError('Payroll fields must remain optional without defaults')


def migrate(erp, db, apply=False):
    actual = erp.sql('SHOW data_directory', db=db, role='easyerp_admin').stdout.strip()
    if Path(actual).resolve() != erp.data.resolve():
        raise RuntimeError('PostgreSQL cluster does not belong to this project')
    manifest, digest = erp.verify_files()
    installed = erp.sql("SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0'",
                        db=db, role='easyerp_admin').stdout.strip()
    if erp.version_matches(installed, manifest, digest):
        verify_shape(erp, db, True)
        return {'database': db, 'migration': VERSION, 'status': 'already applied'}
    if installed not in prior_versions(manifest):
        raise RuntimeError('Unexpected installed version; apply reviewed earlier upgrades first')
    verify_shape(erp, db, False)
    refs = dependencies(erp, db)
    if refs:
        raise RuntimeError('Balance source has database dependencies; review before removal: '+json.dumps(refs,ensure_ascii=False))
    paths = json.loads(erp.sql('SELECT json_build_object(\'rows\',count(*),\'non_null\',count("余额来源")) FROM finance."资金账户档案表"',db=db,role='easyerp_read').stdout)
    result = {'database': db, 'migration': VERSION, 'status': 'preview',
              'retired_values': paths, 'dependencies': refs, 'new_nullable_fields': NEW_FIELDS}
    if not apply:
        return result
    backup = erp.backup(db=db, verify_data=True)
    tables, snapshot = snapshot_query(erp, db)
    locks = ','.join('.'.join(I(p) for p in key.split('.', 1)) for key in tables)
    references = """SELECT conrelid,confrelid,conname,pg_get_constraintdef(oid) AS definition,convalidated
      FROM pg_constraint WHERE contype='f'"""
    sql = f"""BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
LOCK TABLE erp_ops.schema_version IN EXCLUSIVE MODE;
DO $$ BEGIN IF (SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0') IS DISTINCT FROM {L(installed)} THEN RAISE EXCEPTION 'Installed version changed'; END IF; END $$;
LOCK TABLE {locks} IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE finance."资金账户档案表",finance."人员档案表" IN ACCESS EXCLUSIVE MODE;
CREATE TEMP TABLE finance_profiles_before ON COMMIT DROP AS {snapshot};
CREATE TEMP TABLE finance_references_before ON COMMIT DROP AS {references};
CREATE TEMP TABLE balance_sources_before ON COMMIT DROP AS SELECT "账户ID" AS account_id,"余额来源" AS balance_source FROM finance."资金账户档案表";
"""
    sql += (ROOT/'db/010_finance_profiles.sql').read_text(encoding='utf-8')
    sql += f"""
CREATE TEMP TABLE finance_profiles_after ON COMMIT DROP AS {snapshot};
CREATE TEMP TABLE finance_references_after ON COMMIT DROP AS {references};
DO $$ BEGIN
 IF EXISTS ((TABLE finance_profiles_before EXCEPT TABLE finance_profiles_after) UNION ALL (TABLE finance_profiles_after EXCEPT TABLE finance_profiles_before)) THEN RAISE EXCEPTION 'Existing business facts changed'; END IF;
 IF EXISTS ((TABLE finance_references_before EXCEPT TABLE finance_references_after) UNION ALL (TABLE finance_references_after EXCEPT TABLE finance_references_before)) THEN RAISE EXCEPTION 'Foreign key references changed'; END IF;
 IF EXISTS (SELECT 1 FROM balance_sources_before b LEFT JOIN erp_ops.account_profile_retired_fields a ON a.upgrade_id='{VERSION}' AND a.account_id=b.account_id WHERE a.account_id IS NULL OR a.balance_source IS DISTINCT FROM b.balance_source OR a.source_database<>current_database()) THEN RAISE EXCEPTION 'Retired sources were not archived exactly'; END IF;
 IF EXISTS (SELECT 1 FROM finance."人员档案表" WHERE "基准工资" IS NOT NULL OR "工资账户开户行" IS NOT NULL OR "工资账户ID" IS NOT NULL) THEN RAISE EXCEPTION 'New payroll fields must remain unknown'; END IF;
END $$;
INSERT INTO erp_ops.schema_upgrade_log(upgrade_id,from_build,to_build,source_sha256)
 VALUES ('{VERSION}',{L(installed.split('|')[1])},{L(digest)},{L(manifest['source_sha256'])});
UPDATE erp_ops.schema_version SET source_sha256={L(manifest['source_sha256'])},build_sha256={L(digest)} WHERE version='0.2.0';
COMMIT;
"""
    erp.sql(sql, db=db, role='easyerp_admin')
    verify_shape(erp, db, True)
    result.update(status='PASS', backup=str(backup), business_facts_preserved=True,
                  references_preserved=True, retired_values_archived=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--database')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    erp = ERP()
    databases = [args.database] if args.database else [erp.c['database'],erp.c['database']+'_ui_demo']
    results = []
    for db in databases:
        if erp.sql(f'SELECT 1 FROM pg_database WHERE datname={L(db)}',db='postgres',role='easyerp_admin').stdout.strip() != '1':
            raise RuntimeError('Database does not exist: '+db)
        results.append(migrate(erp, db, args.apply))
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
