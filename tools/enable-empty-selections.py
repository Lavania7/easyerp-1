"""Upgrade the existing audited missing-value helper; business columns change only on save."""
from pathlib import Path
import argparse
import hashlib
import json
from easyerp import ERP, stamp, ident as I, literal as L

ROOT = Path(__file__).resolve().parents[1]

def migration_sql(root=ROOT):
    source = (root / 'db/app/csv_import_schema.sql').read_text(encoding='utf-8')
    start = source.index('CREATE OR REPLACE FUNCTION erp_ops.csv_allow_missing_fields(')
    end = source.index('\n-- Incomplete vouchers', start)
    return source[start:end]

def business_signature(erp, database):
    tables = erp.sql("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1", db=database, role='easyerp_read').stdout.splitlines()
    queries = ["SELECT " + L(table) + " AS object,count(*) AS n,md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) AS hash FROM " + '.'.join(I(part) for part in table.split('.')) + ' t' for table in tables]
    return erp.sql("SELECT jsonb_agg(x ORDER BY object) FROM (" + ' UNION ALL '.join(queries) + ') x', db=database, role='easyerp_read').stdout

def upgrade(erp, databases, output):
    erp.verify_files()
    current = Path(erp.sql("SELECT current_setting('data_directory')", role='easyerp_admin').stdout.strip()).resolve()
    if current != erp.data.resolve():
        raise RuntimeError('Unexpected PostgreSQL cluster')
    output.mkdir(parents=True, exist_ok=True)
    sql = migration_sql()
    report = {'status': 'PASS', 'migration': 'empty-selections', 'databases': []}
    for database in databases:
        backup = erp.backup(database)
        old = erp.sql("SELECT pg_get_functiondef('erp_ops.csv_allow_missing_fields(regclass,text[],text)'::regprocedure)", db=database, role='easyerp_admin').stdout
        (output / (database + '-previous-function.sql')).write_text(old, encoding='utf-8')
        before = business_signature(erp, database)
        erp.sql('BEGIN;\n' + sql + '\nCOMMIT;', db=database, role='easyerp_admin')
        after = business_signature(erp, database)
        if before != after:
            raise RuntimeError('Business data changed during function upgrade')
        report['databases'].append({'database': database, 'backup': str(backup), 'backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(), 'business_data_unchanged': True})
    (output / 'migration.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    erp = ERP()
    if not args.apply:
        print('Preview: accept entry2 request IDs in the existing missing-value helper; no business columns or records changed.')
    else:
        destination = args.output or ROOT / 'reports' / ('empty-selections-' + stamp())
        result = upgrade(erp, [erp.c['database'], erp.c['database'] + '_ui_demo'], destination)
        print(json.dumps({'status': result['status'], 'report': str(destination / 'migration.json')}, ensure_ascii=False))
