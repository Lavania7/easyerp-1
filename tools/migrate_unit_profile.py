"""Preview or apply unit simplification, preserving IDs, references and retired values."""
from pathlib import Path
import argparse
import hashlib
import json

from easyerp import ERP, ident as I, literal as L

ROOT = Path(__file__).resolve().parents[1]
VERSION = '009_unit_profile'
KEY = 'rd.计量单位表'
FIELDS = ['单位ID', '单位名称', '备注']
OLD_FIELDS = ['单位ID', '单位代码', '单位名称', '计量维度']


def columns(erp, db):
    return json.loads(erp.sql("""SELECT json_agg(json_build_object('name',attname,
      'type',format_type(atttypid,atttypmod)) ORDER BY attnum)
      FROM pg_attribute WHERE attrelid='rd."计量单位表"'::regclass
      AND attnum>0 AND NOT attisdropped""", db=db, role='easyerp_read').stdout)


def snapshot_query(erp, db):
    tables = erp.sql("""SELECT schemaname||'.'||tablename FROM pg_tables
      WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1""",
      db=db, role='easyerp_read').stdout.splitlines()
    queries = []
    for key in tables:
        schema, name = key.split('.', 1)
        value = "to_jsonb(t)-ARRAY['单位代码','计量维度','备注']" if key == KEY else 'to_jsonb(t)'
        queries.append(f"SELECT {L(key)} AS object,count(*) AS rows,md5(coalesce(string_agg(({value})::text,E'\\n' ORDER BY ({value})::text),'')) AS hash FROM {I(schema)}.{I(name)} t")
    return tables, ' UNION ALL '.join(queries)


def prior_versions(manifest):
    prior = manifest['unit_profile_upgrade_from']
    digest = hashlib.sha256(json.dumps(prior['sql_files'], sort_keys=True).encode()).hexdigest()
    return {source + '|' + digest for source in prior['source_sha256s']}


def migrate(erp, db, apply=False):
    actual = erp.sql('SHOW data_directory', db=db, role='easyerp_admin').stdout.strip()
    if Path(actual).resolve() != erp.data.resolve():
        raise RuntimeError('PostgreSQL cluster does not belong to this project')
    manifest, digest = erp.verify_files()
    installed = erp.sql("SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0'",
                        db=db, role='easyerp_admin').stdout.strip()
    shape = columns(erp, db)
    if erp.version_matches(installed, manifest, digest):
        if [c['name'] for c in shape] != FIELDS or any(c['type'] != 'text' for c in shape):
            raise RuntimeError('Unit structure differs from the installed version')
        return {'database': db, 'migration': VERSION, 'status': 'already applied'}
    if installed not in prior_versions(manifest):
        raise RuntimeError('Unexpected installed version; apply reviewed earlier upgrades first')
    if [c['name'] for c in shape] != OLD_FIELDS or any(c['type'] != 'text' for c in shape):
        raise RuntimeError('Unexpected pre-upgrade unit structure')
    count = int(erp.sql('SELECT count(*) FROM rd."计量单位表"', db=db, role='easyerp_read').stdout)
    result = {'database': db, 'migration': VERSION, 'status': 'preview', 'archived_units': count, 'columns': FIELDS}
    if not apply:
        return result
    backup = erp.backup(db=db)
    tables, snapshot = snapshot_query(erp, db)
    locks = ','.join('.'.join(I(p) for p in key.split('.', 1)) for key in tables)
    references = """SELECT conrelid,confrelid,conname,pg_get_constraintdef(oid) AS definition,convalidated
      FROM pg_constraint WHERE confrelid='rd."计量单位表"'::regclass"""
    sql = f"""BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
LOCK TABLE erp_ops.schema_version IN EXCLUSIVE MODE;
DO $$ BEGIN IF (SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0') IS DISTINCT FROM {L(installed)} THEN RAISE EXCEPTION 'Installed version changed'; END IF; END $$;
LOCK TABLE {locks} IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE rd."计量单位表" IN ACCESS EXCLUSIVE MODE;
CREATE TEMP TABLE units_before ON COMMIT DROP AS {snapshot};
CREATE TEMP TABLE unit_references_before ON COMMIT DROP AS {references};
CREATE TEMP TABLE unit_fields_before ON COMMIT DROP AS SELECT "单位ID" AS unit_id,"单位代码" AS unit_code,"计量维度" AS measurement_dimension FROM rd."计量单位表";
"""
    sql += (ROOT / 'db/009_unit_profile.sql').read_text(encoding='utf-8')
    sql += f"""
CREATE TEMP TABLE units_after ON COMMIT DROP AS {snapshot};
CREATE TEMP TABLE unit_references_after ON COMMIT DROP AS {references};
DO $$ BEGIN
 IF EXISTS ((TABLE units_before EXCEPT TABLE units_after) UNION ALL (TABLE units_after EXCEPT TABLE units_before)) THEN RAISE EXCEPTION 'Existing business facts changed'; END IF;
 IF EXISTS ((TABLE unit_references_before EXCEPT TABLE unit_references_after) UNION ALL (TABLE unit_references_after EXCEPT TABLE unit_references_before)) THEN RAISE EXCEPTION 'Unit references changed'; END IF;
 IF EXISTS (SELECT 1 FROM unit_fields_before b LEFT JOIN erp_ops.unit_profile_retired_fields a ON a.upgrade_id='{VERSION}' AND a.unit_id=b.unit_id WHERE a.unit_id IS NULL OR a.unit_code IS DISTINCT FROM b.unit_code OR a.measurement_dimension IS DISTINCT FROM b.measurement_dimension) THEN RAISE EXCEPTION 'Retired unit values were not archived'; END IF;
 IF EXISTS (SELECT 1 FROM rd."计量单位表" WHERE "备注" IS NOT NULL) THEN RAISE EXCEPTION 'New notes must remain unknown'; END IF;
END $$;
INSERT INTO erp_ops.schema_upgrade_log(upgrade_id,from_build,to_build,source_sha256)
 VALUES ('{VERSION}',{L(installed.split('|')[1])},{L(digest)},{L(manifest['source_sha256'])});
UPDATE erp_ops.schema_version SET source_sha256={L(manifest['source_sha256'])},build_sha256={L(digest)} WHERE version='0.2.0';
COMMIT;
"""
    erp.sql(sql, db=db, role='easyerp_admin')
    result.update(status='PASS', backup=str(backup), business_facts_preserved=True, references_preserved=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--database', help='One database; defaults to existing live and demo databases')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    erp = ERP()
    databases = [args.database] if args.database else [erp.c['database'], erp.c['database'] + '_ui_demo']
    results = []
    for db in databases:
        if erp.sql(f'SELECT 1 FROM pg_database WHERE datname={L(db)}', db='postgres', role='easyerp_admin').stdout.strip() == '1':
            results.append(migrate(erp, db, args.apply))
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
