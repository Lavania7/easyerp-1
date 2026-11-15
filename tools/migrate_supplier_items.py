"""Preview or apply release-1.3 supplier references without inventing associations."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import sys

from easyerp import ERP, ROOT, ident as I, literal as L, stamp

KEY = 'production.供应物品明细表'
VERSION = '011_supplier_items'


def prior_versions(manifest):
    prior = manifest['supplier_items_upgrade_from']
    digest = hashlib.sha256(json.dumps(prior['sql_files'], sort_keys=True).encode()).hexdigest()
    return {source + '|' + digest for source in prior['source_sha256s']}


def upgrade_sql():
    tables = (ROOT / 'db/002_tables.sql').read_text(encoding='utf-8')
    start = tables.index('CREATE TABLE production."供应物品明细表"')
    table = tables[start:tables.index(';', start) + 1]
    keys = '\n'.join(line for line in (ROOT / 'db/003_foreign_keys.sql').read_text(encoding='utf-8').splitlines()
                     if line.startswith('ALTER TABLE production."供应物品明细表"'))
    return table + '\n' + keys + '\n' + (ROOT / 'db/011_supplier_items.sql').read_text(encoding='utf-8')


def snapshot_sql(tables):
    return ' UNION ALL '.join(
        f"SELECT {L(key)} AS object,count(*) AS rows,md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) AS hash FROM "
        + '.'.join(I(part) for part in key.split('.', 1)) + ' t' for key in tables
    )


def migrate(erp, db, apply=False):
    actual = erp.sql('SHOW data_directory', db=db, role='easyerp_admin').stdout.strip()
    if Path(actual).resolve() != erp.data.resolve() or db != erp.c['database']:
        raise RuntimeError('Target database or cluster does not match the selected source')
    manifest, digest = erp.verify_files()
    installed = erp.sql("SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0'", db=db, role='easyerp_admin').stdout.strip()
    present = erp.sql("SELECT to_regclass('production.\"供应物品明细表\"') IS NOT NULL", db=db, role='easyerp_read').stdout.strip() == 't'
    if erp.version_matches(installed, manifest, digest):
        if not present:
            raise RuntimeError('Installed version claims supplier items but table is absent')
        return {'database': db, 'migration': VERSION, 'status': 'already applied'}
    if installed not in prior_versions(manifest) or present:
        raise RuntimeError('Unexpected installed version or pre-existing target table; review first')
    tables = erp.sql("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1", db=db, role='easyerp_read').stdout.splitlines()
    result = {'database': db, 'port': erp.c['port'], 'data_directory': str(erp.data), 'migration': VERSION,
              'status': 'preview', 'new_table': KEY, 'relationships_to_create': 0,
              'from_version': installed, 'to_version': manifest['source_sha256'] + '|' + digest}
    if not apply:
        return result
    backup = erp.backup(db=db, verify_data=True)
    snapshot = snapshot_sql(tables)
    locks = ','.join('.'.join(I(part) for part in key.split('.', 1)) for key in tables)
    refs = "SELECT conrelid,confrelid,conname,pg_get_constraintdef(oid) AS definition,convalidated FROM pg_constraint WHERE contype='f' AND conrelid<>'production.\"供应物品明细表\"'::regclass"
    before_refs = "SELECT conrelid,confrelid,conname,pg_get_constraintdef(oid) AS definition,convalidated FROM pg_constraint WHERE contype='f'"
    sql = f'''BEGIN;
SET LOCAL lock_timeout='10s'; SET LOCAL statement_timeout='120s';
LOCK TABLE erp_ops.schema_version IN EXCLUSIVE MODE;
DO $$ BEGIN IF (SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0') IS DISTINCT FROM {L(installed)} THEN RAISE EXCEPTION 'Installed version changed'; END IF; END $$;
LOCK TABLE {locks} IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE facts_before ON COMMIT DROP AS {snapshot};
CREATE TEMP TABLE refs_before ON COMMIT DROP AS {before_refs};
{upgrade_sql()}
GRANT SELECT ON production."供应物品明细表" TO easyerp_read,easyerp_app;
GRANT INSERT,UPDATE,DELETE ON production."供应物品明细表" TO easyerp_app;
CREATE TEMP TABLE facts_after ON COMMIT DROP AS {snapshot};
CREATE TEMP TABLE refs_after ON COMMIT DROP AS {refs};
DO $$ BEGIN
 IF EXISTS ((TABLE facts_before EXCEPT TABLE facts_after) UNION ALL (TABLE facts_after EXCEPT TABLE facts_before)) THEN RAISE EXCEPTION 'Existing business facts changed'; END IF;
 IF EXISTS ((TABLE refs_before EXCEPT TABLE refs_after) UNION ALL (TABLE refs_after EXCEPT TABLE refs_before)) THEN RAISE EXCEPTION 'Existing foreign keys changed'; END IF;
 IF EXISTS (SELECT 1 FROM production."供应物品明细表") THEN RAISE EXCEPTION 'Migration must not invent supplier relationships'; END IF;
END $$;
INSERT INTO erp_ops.schema_upgrade_log(upgrade_id,from_build,to_build,source_sha256) VALUES ({L(VERSION)},{L(installed.split('|')[1])},{L(digest)},{L(manifest['source_sha256'])});
UPDATE erp_ops.schema_version SET source_sha256={L(manifest['source_sha256'])},build_sha256={L(digest)} WHERE version='0.2.0';
COMMIT;'''
    erp.sql(sql, db=db, role='easyerp_admin')
    result.update(status='PASS', backup=str(backup), business_facts_preserved=True, existing_references_preserved=True)
    return result


def migrate_workspace(mode, apply=False, root=None):
    sys.path.insert(0, str(ROOT / 'app'))
    from workspace import Workspace, legacy_report_values

    workspace = Workspace(mode, root=root)
    if not workspace.path.exists():
        return {'mode': mode, 'status': 'absent', 'changed': 0}
    with workspace.locked():
        original = workspace.path.read_bytes()
        source_hash = hashlib.sha256(original).hexdigest()
        data = workspace.read()
        changed = []
        def convert(item):
            if item.get('kind') != 'report' or not {'type', 'month'}.intersection(item['values']):
                return False
            before = copy.deepcopy(item['values'])
            item['values'] = legacy_report_values(before)
            item.setdefault('legacy', {})['retired_report_fields'] = before
            return True
        for item in data['items'].values():
            if convert(item):
                changed.append(item['id'])
        for request in data.get('requests', {}).values():
            if request.get('result', {}).get('item'):
                convert(request['result']['item'])
        result = {'mode': mode, 'path': str(workspace.path), 'sha256': source_hash,
                  'status': 'preview', 'changed': len(changed), 'items': changed}
        if apply and changed:
            folder = workspace.root / 'release-1.3-backups' / stamp()
            folder.mkdir(parents=True, exist_ok=False)
            backup = folder / workspace.path.name
            backup.write_bytes(original)
            if hashlib.sha256(backup.read_bytes()).hexdigest() != source_hash or workspace.path.read_bytes() != original:
                raise RuntimeError('Workspace source changed or backup verification failed')
            workspace.write(data)
            result.update(status='PASS', backup=str(backup), after_sha256=hashlib.sha256(workspace.path.read_bytes()).hexdigest())
        elif not changed:
            result['status'] = 'already applied'
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['live', 'demo', 'both'], default='both')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--workspace-only', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    results = []
    def receipt():
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    for mode in (['live', 'demo'] if args.mode == 'both' else [args.mode]):
        try:
            erp = ERP(mode=mode)
            if not args.workspace_only:
                results.append(migrate(erp, erp.c['database'], args.apply))
                receipt()
            results.append(migrate_workspace(mode, args.apply))
            receipt()
        except Exception:
            results.append({'mode': mode, 'status': 'FAILED', 'review': 'Inspect the preceding receipts and database version before retrying'})
            receipt()
            raise
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
