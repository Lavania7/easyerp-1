"""Verify unit migration, rollback and entry/import contracts in disposable databases."""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'app')]
from easyerp import ERP, ident as I, literal as L
from migrate_unit_profile import migrate, columns, FIELDS, OLD_FIELDS, KEY, snapshot_query
from entry import ManualEntry, EntryError, _CACHE
from standard_templates import StandardTemplates
from standard_import import StandardImport



def restore_legacy_unit_fixture(erp, db):
    """Reconstruct old columns only in disposable restored fixtures; keep ID/FK identity."""
    if not db.startswith(('easyerp_unit_test_', 'easyerp_supplier_test_')):
        raise RuntimeError('Legacy fixture reconstruction is restricted to disposable test databases')
    if [c['name'] for c in columns(erp, db)] == OLD_FIELDS:
        return
    if [c['name'] for c in columns(erp, db)] != FIELDS:
        raise RuntimeError('Unexpected fixture shape')
    manifest, _ = erp.verify_files()
    prior = manifest['unit_profile_upgrade_from']
    digest = hashlib.sha256(json.dumps(prior['sql_files'], sort_keys=True).encode()).hexdigest()
    erp.sql(f"""BEGIN;
CREATE TEMP TABLE unit_fixture_values ON COMMIT DROP AS
  SELECT u."单位ID",u."单位名称",coalesce(a.unit_code,u."单位ID") AS code,
    coalesce(a.measurement_dimension,'测试维度') AS dimension
  FROM rd."计量单位表" u LEFT JOIN erp_ops.unit_profile_retired_fields a
    ON a.unit_id=u."单位ID" AND a.upgrade_id='009_unit_profile';
ALTER TABLE rd."计量单位表" RENAME COLUMN "单位名称" TO "单位代码";
ALTER TABLE rd."计量单位表" RENAME COLUMN "备注" TO "单位名称";
ALTER TABLE rd."计量单位表" ADD COLUMN "计量维度" text;
UPDATE rd."计量单位表" u SET "单位代码"=v.code,"单位名称"=v."单位名称","计量维度"=v.dimension
  FROM unit_fixture_values v WHERE u."单位ID"=v."单位ID";
ALTER TABLE rd."计量单位表" ALTER COLUMN "单位代码" SET NOT NULL,
  ALTER COLUMN "计量维度" SET NOT NULL,ADD UNIQUE ("单位代码");
DROP TABLE erp_ops.unit_profile_retired_fields;
DELETE FROM erp_ops.schema_upgrade_log WHERE upgrade_id='009_unit_profile';
UPDATE erp_ops.schema_version SET source_sha256={L(prior['source_sha256s'][0])},build_sha256={L(digest)} WHERE version='0.2.0';
COMMIT;""", db=db, role='easyerp_admin')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--source-backup', type=Path, help='Retained pre-upgrade demo dump for reruns')
    args = parser.parse_args()
    erp = ERP()
    db = 'easyerp_unit_test_' + uuid.uuid4().hex[:12]
    fresh = db + '_fresh'
    source = erp.c['database'] + '_ui_demo'
    checks = []
    def check(label, condition):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
        print('PASS ' + label, flush=True)
    def sql(text, role='easyerp_read', target=None):
        return erp.sql(text, db=target or db, role=role).stdout.strip()
    def signature(target):
        _, query = snapshot_query(erp, target)
        query = query.replace("to_jsonb(t)-ARRAY['单位代码','计量维度','备注']", 'to_jsonb(t)')
        return sql(query, target=target)
    before = {target: signature(target) for target in (erp.c['database'], source)}
    backup = args.source_backup or erp.backup(db=source)
    try:
        erp.run('createdb', ['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','-T','template0',db])
        erp.run('pg_restore', ['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','--exit-on-error','--single-transaction','-d',db,backup])
        restore_legacy_unit_fixture(erp, db)
        check('restored pre-upgrade unit shape', [c['name'] for c in columns(erp, db)] == OLD_FIELDS)
        sql('''INSERT INTO rd."计量单位表"("单位ID","单位代码","单位名称","计量维度")
            VALUES ('UZZZ','000-CODE','迁移验收单位','数量');
            CREATE VIEW rd.unit_dependency_test AS SELECT "单位代码" FROM rd."计量单位表";''', 'easyerp_admin')
        try:
            migrate(erp, db, True)
        except RuntimeError as error:
            check('dependent view blocks migration', 'depend' in str(error).lower() or '依赖' in str(error))
        else:
            raise AssertionError('Dependent view unexpectedly removed')
        check('blocked migration rolls back DDL', [c['name'] for c in columns(erp, db)] == OLD_FIELDS)
        sql('DROP VIEW rd.unit_dependency_test', 'easyerp_admin')
        check('preview does not migrate', migrate(erp, db)['status'] == 'preview' and [c['name'] for c in columns(erp, db)] == OLD_FIELDS)
        result = erp.migrate(db)
        check('generic migration succeeds with fact and FK comparisons', result['status'] == 'PASS' and result['business_facts_preserved'] and result['references_preserved'])
        check('exact new ordered fields', [c['name'] for c in columns(erp, db)] == FIELDS)
        check('retired code and dimension archived exactly', sql("SELECT unit_code||'|'||measurement_dimension FROM erp_ops.unit_profile_retired_fields WHERE unit_id='UZZZ'", 'easyerp_admin') == '000-CODE|数量')
        check('archive is inaccessible to app and query roles', sql("SELECT NOT has_table_privilege('easyerp_read','erp_ops.unit_profile_retired_fields','SELECT') AND NOT has_table_privilege('easyerp_app','erp_ops.unit_profile_retired_fields','SELECT')") == 't')
        check('existing IDs names preserved with NULL notes', sql('SELECT "单位名称"=\'迁移验收单位\' AND "备注" IS NULL FROM rd."计量单位表" WHERE "单位ID"=\'UZZZ\'') == 't')
        check('migration is idempotent', migrate(erp, db, True)['status'] == 'already applied')
        erp.ensure_database(db)
        check('startup accepts migrated build', True)
        _CACHE.clear()
        entry = ManualEntry({'mode':'demo'})
        entry.db = db
        entry.data.db = db
        obj = entry.object(KEY)
        check('metadata has only name and optional notes beyond ID', [c['name'] for c in obj['columns']] == FIELDS and not next(c for c in obj['columns'] if c['name']=='备注')['required'])
        note = '备注保留 001、引号 " 和换行\n第二行'
        saved = entry.save({'request_id':uuid.uuid4().hex, 'object':KEY, 'values':{'单位名称':'新增验收单位','备注':note}})['records'][0]
        record = entry.record(KEY, saved['id'])
        check('create generates ID and saves exact name and notes', saved['id'].startswith('U') and record['values']['备注'] == note and record['values']['单位名称']=='新增验收单位')
        entry.save({'request_id':uuid.uuid4().hex, 'object':KEY, 'operation':'update', 'id':saved['id'], 'version':record['version'], 'values':{'备注':'修改备注'}})
        check('update keeps unit name and ID', entry.record(KEY,saved['id'])['values']['备注']=='修改备注')
        minimal = entry.save({'request_id':uuid.uuid4().hex,'object':KEY,'values':{'单位名称':'仅名称验收'}})['records'][0]
        check('notes can be omitted', entry.record(KEY,minimal['id'])['values']['备注'] is None)
        templates = StandardTemplates({'mode':'demo'})
        templates.entry = entry
        body, _ = templates.download(KEY)
        check('CSV template has exact current fields', list(csv.reader(io.StringIO(body.decode('utf-8-sig')))) == [FIELDS])
        imports = StandardImport('demo')
        imports.entry = entry
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        writer.writerow(['UZZY','CSV验收单位',note])
        plan = imports.plan(KEY+'.csv', stream.getvalue().encode('utf-8-sig'))
        check('CSV parser accepts simplified fields', not plan['errors'])
        imports.write(plan,check_id=uuid.uuid4().hex)
        check('CSV transaction saves name and notes exactly', entry.record(KEY,'UZZY')['values']['备注'] == note)
        try:
            imports.plan(KEY+'.csv', '单位ID,单位代码,单位名称,计量维度\r\nUZZX,EA,旧模板,数量\r\n'.encode('utf-8-sig'))
        except Exception as error:
            check('old CSV explicitly asks for a new template', '重新下载模板' in str(error))
        else:
            raise AssertionError('Old CSV accepted')
        try:
            entry.save({'request_id':uuid.uuid4().hex,'object':KEY,'values':{'单位名称':'旧字段','单位代码':'OLD'}})
        except EntryError:
            check('old entry fields rejected', True)
        else:
            raise AssertionError('Old entry fields accepted')
        refs = entry.data.rows("""SELECT n.nspname||'.'||t.relname AS object,a.attname AS field
          FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
          JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
          WHERE c.confrelid='rd."计量单位表"'::regclass AND c.contype='f'""")
        check('all 26 foreign keys retain name choices', len(refs)==26 and all(any(row['value']=='UZZZ' and row['label']=='迁移验收单位' for row in entry.options(r['object'],r['field'],selected='UZZZ')['rows']) for r in refs))
        erp.ensure_database(fresh)
        check('fresh installation has simplified fields', [c['name'] for c in columns(erp, fresh)] == FIELDS)
        erp.sql(file=ROOT/'tests/structure.sql',db=fresh,role='easyerp_admin')
        from business_queries import expand_queries
        erp.sql(expand_queries((ROOT/'tests/business.sql').read_text(encoding='utf-8')),db=fresh,role='easyerp_admin')
        check('fresh schema and business SQL tests pass', True)
        check('live and demo business data untouched', all(before[target] == signature(target) for target in before))
        report = {'passed':len(checks), 'checks':checks, 'source_backup':str(backup), 'migration':result}
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'passed':len(checks),'temporary_databases_removed':[db,fresh]}))
    finally:
        for target in (db,fresh):
            if target.startswith('easyerp_unit_test_'):
                erp.sql(f'DROP DATABASE IF EXISTS {I(target)} WITH (FORCE)',db='postgres',role='easyerp_admin')


if __name__ == '__main__':
    main()
