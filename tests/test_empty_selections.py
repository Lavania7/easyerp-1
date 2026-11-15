"""Save unknown selectors only in disposable restored databases; verify source data unchanged."""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import sys
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--source', type=Path)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
root, source = args.root.resolve(), (args.source or args.root).resolve()
sys.path[:0] = [str(source / 'app'), str(root / 'app'), str(root / 'tools')]
from easyerp import ERP, ident as I, literal as L
from entry import ManualEntry, EntryError, _CACHE
from identifiers import RULES

erp = ERP(); clones = []; passed = []; backups = []
args.out.mkdir(parents=True, exist_ok=True)
def check(name, value=True):
    assert value, name
    passed.append(name); print('PASS:', name, flush=True)
def rows(sql, db):
    return json.loads(erp.sql("SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM (" + sql + ') x;', db=db, role='easyerp_read').stdout)
def signature(db):
    queries = ["SELECT " + L(key) + " AS object,count(*) AS n,md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) AS hash FROM " + '.'.join(I(x) for x in key.split('.')) + ' t' for key in RULES]
    return rows(' UNION ALL '.join(queries), db)
def schema(db):
    return rows("SELECT n.nspname||'.'||c.relname AS object,p.conname,pg_get_constraintdef(p.oid) AS definition FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('sales','production','finance','rd','legal','analysis') AND p.contype IN ('f','p','u') ORDER BY 1,2", db)
def warehouse_schema(db):
    return rows("SELECT a.attname,a.attnotnull FROM pg_attribute a WHERE a.attrelid='production.\"仓库档案表\"'::regclass AND a.attnum>0 ORDER BY a.attnum", db)
def entry_at(db, mode):
    entry = ManualEntry({'mode': mode}); entry.db = db; entry.data.db = db
    return entry
def save(entry, values, request=None, **extra):
    return entry.save({'request_id': request or uuid.uuid4().hex, 'object': 'production.仓库档案表', 'values': values, **extra})
sql_source = (source / 'db/app/csv_import_schema.sql').read_text(encoding='utf-8')
sql = sql_source[sql_source.index('CREATE OR REPLACE FUNCTION erp_ops.csv_allow_missing_fields('):sql_source.index('\n-- Incomplete vouchers')]
before = {mode: signature(erp.c['database'] + ('_ui_demo' if mode == 'demo' else '')) for mode in ('live', 'demo')}
try:
    for mode in ('live', 'demo'):
        original = erp.c['database'] + ('_ui_demo' if mode == 'demo' else '')
        backup = erp.backup(original); backups.append(str(backup))
        clone = 'easyerp_empty_test_' + uuid.uuid4().hex[:12]; clones.append(clone)
        erp.run('createdb', ['-h', '127.0.0.1', '-p', erp.c['port'], '-U', 'easyerp_admin', '-w', '-T', 'template0', clone])
        erp.run('pg_restore', ['-h', '127.0.0.1', '-p', erp.c['port'], '-U', 'easyerp_admin', '-w', '--exit-on-error', '--single-transaction', '-d', clone, backup])
        erp.sql('BEGIN;\n' + sql + '\nCOMMIT;', db=clone, role='easyerp_admin')
        entry = entry_at(clone, mode); obj = entry.object('production.仓库档案表')
        expected = ['保管方ID', '主体ID', '启用状态']
        check(mode + ' selectors allow unknown without changing text required flags', all(next(c for c in obj['columns'] if c['name'] == name)['allow_empty_selection'] for name in expected) and not next(c for c in obj['columns'] if c['name'] == '地点')['allow_empty_selection'])
        protected = schema(clone); empty_schema = warehouse_schema(clone); count = rows('SELECT count(*) AS n FROM production."仓库档案表"', clone)[0]['n']
        bad_keeper = RULES['production.保管方档案表']['prefix'] + 'ZZZZZZZZ'
        try: save(entry, {'地点': '隔离无效关联检查', '保管方ID': bad_keeper, '主体ID': None, '启用状态': None})
        except EntryError: pass
        else: raise AssertionError('Invalid foreign key was accepted')
        check(mode + ' failed save rolls back data and constraint changes', rows('SELECT count(*) AS n FROM production."仓库档案表"', clone)[0]['n'] == count and warehouse_schema(clone) == empty_schema)
        erp.sql('ALTER TABLE production."仓库档案表" ALTER COLUMN "启用状态" SET DEFAULT \'启用\';', db=clone, role='easyerp_admin')
        _CACHE.pop(clone, None)
        request = uuid.uuid4().hex
        first = save(entry, {'地点': '隔离空值选择检查'}, request)['records'][0]
        check(mode + ' omitted selectors persist SQL NULL', all(first['values'][name] is None for name in expected))
        check(mode + ' empty selector does not silently adopt its SQL default', bool(next(c for c in entry.object('production.仓库档案表')['columns'] if c['name'] == '启用状态')['default']) and first['values']['启用状态'] is None)
        second = save(entry, {'地点': '隔离空值选择检查'}, request)['records'][0]
        check(mode + ' retries preserve record identity', first['id'] == second['id'])
        audit = rows("SELECT * FROM erp_ops.frontend_csv_nullability WHERE request_id LIKE 'entry2-%' AND schema_name='production' AND table_name='仓库档案表'", clone)
        check(mode + ' only missing selector constraints are relaxed and audited', bool(audit) and all(item['column_name'] in expected for item in audit) and next(r for r in warehouse_schema(clone) if r['attname'] == '地点')['attnotnull'])
        try: save(entry, {'地点': ''})
        except EntryError: check(mode + ' blank required text still rejected')
        else: raise AssertionError('Blank required text accepted')
        try: save(entry, {'地点': '非法枚举', '启用状态': 'N/A'})
        except EntryError: check(mode + ' literal N/A is never stored as an enum value')
        else: raise AssertionError('Literal N/A accepted')
        updated = save(entry, {'启用状态': '启用'}, operation='update', id=first['id'], version=first['version'])['records'][0]
        cleared = save(entry, {'启用状态': None}, operation='update', id=updated['id'], version=updated['version'])['records'][0]
        check(mode + ' editing can clear an existing selection', cleared['values']['启用状态'] is None)
        check(mode + ' PK unique and foreign-key constraints remain intact', schema(clone) == protected)
        check(mode + ' request and constraint audit are linked by payload hash', rows('SELECT count(*) AS n FROM erp_ops.frontend_entry_audit a JOIN erp_ops.frontend_csv_nullability b ON b.request_id=\'entry2-\'||a.payload_hash WHERE a.request_id=' + L(request), clone)[0]['n'] > 0)
    bool_col = {'name': '布尔选择', 'type': 'boolean', 'required': True, 'default': None, 'automatic': False, 'allow_empty_selection': True, 'options': []}
    check('false stays false and unknown stays NULL', ManualEntry.value(bool_col, False) == 'false' and ManualEntry.value(bool_col, None) is None)
    check('source business data unchanged in both modes', all(signature(erp.c['database'] + ('_ui_demo' if mode == 'demo' else '')) == before[mode] for mode in before))
    (args.out / 'database-validation.json').write_text(json.dumps({'status': 'PASS', 'checks': len(passed), 'passed': passed, 'backups': backups, 'isolated_databases': clones}, ensure_ascii=False, indent=2), encoding='utf-8')
finally:
    for clone in clones:
        if not clone.startswith('easyerp_empty_test_'): raise RuntimeError('Unexpected cleanup target')
        erp.run('dropdb', ['-h', '127.0.0.1', '-p', erp.c['port'], '-U', 'easyerp_admin', '-w', '--if-exists', '--force', clone])
