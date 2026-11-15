"""Preview or apply the reviewed supplier upgrade, preserving IDs and all references."""
from pathlib import Path
import argparse
import hashlib
import json

from easyerp import ERP, ident as I, literal as L

ROOT = Path(__file__).resolve().parents[1]
VERSION = '008_supplier_profile'
KEY = 'production.供应商档案表'
FIELDS = ['供应商ID','名称','联系方式','统一社会信用代码','户名','账户ID','开户行']
OLD_FIELDS = ['供应商ID','名称','联系方式','相关文件路径']


def columns(erp, db):
    return json.loads(erp.sql("""SELECT json_agg(json_build_object('name',attname,
      'type',format_type(atttypid,atttypmod)) ORDER BY attnum)
      FROM pg_attribute WHERE attrelid='production."供应商档案表"'::regclass
      AND attnum>0 AND NOT attisdropped""",db=db,role='easyerp_read').stdout)


def snapshot_query(erp, db):
    tables=erp.sql("""SELECT schemaname||'.'||tablename FROM pg_tables
      WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1""",
      db=db,role='easyerp_read').stdout.splitlines()
    queries=[]
    for key in tables:
        schema,name=key.split('.',1)
        value='to_jsonb(t)'
        if key==KEY:
            value="to_jsonb(t)-ARRAY['相关文件路径','统一社会信用代码','户名','账户ID','开户行']"
        queries.append(f"SELECT {L(key)} AS object,count(*) AS rows,md5(coalesce(string_agg(({value})::text,E'\\n' ORDER BY ({value})::text),'')) AS hash FROM {I(schema)}.{I(name)} t")
    return tables,' UNION ALL '.join(queries)


def migrate(erp, db, apply=False):
    actual=erp.sql('SHOW data_directory',db=db,role='easyerp_admin').stdout.strip()
    if Path(actual).resolve()!=erp.data.resolve():
        raise RuntimeError('PostgreSQL cluster does not belong to this project')
    manifest,digest=erp.verify_files()
    installed=erp.sql("SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0'",
                      db=db,role='easyerp_admin').stdout.strip()
    shape=columns(erp,db)
    if erp.version_matches(installed,manifest,digest):
        if [c['name'] for c in shape]!=FIELDS or any(c['type']!='text' for c in shape):
            raise RuntimeError('Supplier structure differs from the installed version')
        return {'database':db,'migration':VERSION,'status':'already applied'}
    # Older installs first reach the reviewed supplier build, then the unit upgrade.
    unit_prior=manifest.get('unit_profile_upgrade_from')
    if unit_prior:
        manifest={**manifest,'source_sha256':unit_prior['source_sha256s'][0],
                  'compatible_sources':[],'sql_files':unit_prior['sql_files']}
        digest=hashlib.sha256(json.dumps(unit_prior['sql_files'],sort_keys=True).encode()).hexdigest()
        if installed in {s+'|'+digest for s in unit_prior['source_sha256s']}:
            if [c['name'] for c in shape]!=FIELDS or any(c['type']!='text' for c in shape):
                raise RuntimeError('Supplier structure differs from the installed version')
            return {'database':db,'migration':VERSION,'status':'already applied'}
    prior=manifest['supplier_profile_upgrade_from']
    old_build=hashlib.sha256(json.dumps(prior['sql_files'],sort_keys=True).encode()).hexdigest()
    allowed={s+'|'+old_build for s in prior['source_sha256s']}
    legacy=manifest['migration_from']
    legacy_version=legacy['source_sha256']+'|'+legacy['build_sha256']
    remove_views=installed==legacy_version
    if installed not in allowed and not remove_views:
        raise RuntimeError('Unexpected installed version; review differences before migration')
    if [c['name'] for c in shape]!=OLD_FIELDS or any(c['type']!='text' for c in shape):
        raise RuntimeError('Unexpected pre-upgrade supplier structure')
    paths=int(erp.sql('SELECT count(*) FROM production."供应商档案表" WHERE "相关文件路径" IS NOT NULL',db=db,role='easyerp_read').stdout)
    result={'database':db,'migration':VERSION,'status':'preview','retired_paths':paths,'columns':FIELDS}
    if not apply:
        return result
    backup=erp.backup(db=db)
    tables,snapshot=snapshot_query(erp,db)
    lock_tables=','.join('.'.join(I(p) for p in key.split('.',1)) for key in tables)
    references="""SELECT conrelid,confrelid,conname,pg_get_constraintdef(oid) AS definition,convalidated
      FROM pg_constraint WHERE confrelid='production."供应商档案表"'::regclass"""
    # Compare under locks and before COMMIT; an invariant failure rolls back the DDL too.
    sql=f"""BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
LOCK TABLE erp_ops.schema_version IN EXCLUSIVE MODE;
DO $$ BEGIN IF (SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0') IS DISTINCT FROM {L(installed)} THEN RAISE EXCEPTION 'Installed version changed'; END IF; END $$;
LOCK TABLE {lock_tables} IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE production."供应商档案表" IN ACCESS EXCLUSIVE MODE;
CREATE TEMP TABLE supplier_before ON COMMIT DROP AS {snapshot};
CREATE TEMP TABLE supplier_references_before ON COMMIT DROP AS {references};
CREATE TEMP TABLE supplier_paths_before ON COMMIT DROP AS SELECT "供应商ID" AS supplier_id,"相关文件路径" AS file_path FROM production."供应商档案表" WHERE "相关文件路径" IS NOT NULL;
"""
    if remove_views:
        sql+=(ROOT/'db/007_remove_views.sql').read_text(encoding='utf-8')+'\n'
    sql+=(ROOT/'db/008_supplier_profile.sql').read_text(encoding='utf-8')
    sql+=f"""
CREATE TEMP TABLE supplier_after ON COMMIT DROP AS {snapshot};
CREATE TEMP TABLE supplier_references_after ON COMMIT DROP AS {references};
DO $$ BEGIN
 IF EXISTS ((TABLE supplier_before EXCEPT TABLE supplier_after) UNION ALL (TABLE supplier_after EXCEPT TABLE supplier_before)) THEN RAISE EXCEPTION 'Existing business facts changed'; END IF;
 IF EXISTS ((TABLE supplier_references_before EXCEPT TABLE supplier_references_after) UNION ALL (TABLE supplier_references_after EXCEPT TABLE supplier_references_before)) THEN RAISE EXCEPTION 'Supplier references changed'; END IF;
 IF EXISTS (SELECT 1 FROM supplier_paths_before b LEFT JOIN erp_ops.supplier_profile_retired_fields a ON a.upgrade_id='{VERSION}' AND a.supplier_id=b.supplier_id AND a.file_path=b.file_path WHERE a.supplier_id IS NULL) THEN RAISE EXCEPTION 'Retired paths were not archived'; END IF;
 IF EXISTS (SELECT 1 FROM production."供应商档案表" WHERE "统一社会信用代码" IS NOT NULL OR "户名" IS NOT NULL OR "账户ID" IS NOT NULL OR "开户行" IS NOT NULL) THEN RAISE EXCEPTION 'New supplier fields must remain unknown'; END IF;
END $$;
INSERT INTO erp_ops.schema_upgrade_log(upgrade_id,from_build,to_build,source_sha256)
 VALUES ('{VERSION}',{L(installed.split('|')[1])},{L(digest)},{L(manifest['source_sha256'])});
UPDATE erp_ops.schema_version SET source_sha256={L(manifest['source_sha256'])},build_sha256={L(digest)} WHERE version='0.2.0';
COMMIT;
"""
    erp.sql(sql,db=db,role='easyerp_admin')
    result.update(status='PASS',backup=str(backup),business_facts_preserved=True,references_preserved=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--database',help='One database; defaults to existing live and demo databases')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    erp=ERP()
    databases=[args.database] if args.database else [erp.c['database'],erp.c['database']+'_ui_demo']
    results=[]
    for db in databases:
        if erp.sql(f'SELECT 1 FROM pg_database WHERE datname={L(db)}',db='postgres',role='easyerp_admin').stdout.strip()=='1':
            results.append(migrate(erp,db,args.apply))
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
