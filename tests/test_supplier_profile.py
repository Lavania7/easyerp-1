"""Exercise the supplier upgrade and new fields in a restored disposable database."""
from pathlib import Path
import csv
import io
import json
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'app')]
from easyerp import ERP,ident as I
from migrate_supplier_profile import migrate,columns,FIELDS,OLD_FIELDS,KEY,snapshot_query
from entry import ManualEntry,EntryError,_CACHE
from standard_templates import StandardTemplates
from standard_import import StandardImport


def main():
    erp=ERP()
    db='easyerp_supplier_test_'+uuid.uuid4().hex[:12]
    source=erp.c['database']+'_ui_demo'
    checks=[]
    def check(label,condition):
        if not condition:raise AssertionError(label)
        checks.append(label)
        print('PASS '+label,flush=True)
    def sql(text,role='easyerp_read'):
        return erp.sql(text,db=db,role=role).stdout.strip()
    def original_signature(target):
        _,query=snapshot_query(erp,target)
        query=query.replace("to_jsonb(t)-ARRAY['相关文件路径','统一社会信用代码','户名','账户ID','开户行']",'to_jsonb(t)')
        return erp.sql(query,db=target,role='easyerp_read').stdout
    before={target:original_signature(target) for target in (erp.c['database'],source)}
    backup=erp.backup(db=source)
    try:
        erp.run('createdb',['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','-T','template0',db])
        erp.run('pg_restore',['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','--exit-on-error','--single-transaction','-d',db,backup])
        from test_unit_profile import restore_legacy_unit_fixture
        restore_legacy_unit_fixture(erp,db)
        # The same test works before and after deploying the upgrade.
        current=columns(erp,db)
        if [c['name'] for c in current]==FIELDS:
            manifest,_=erp.verify_files()
            prior=manifest['supplier_profile_upgrade_from']
            import hashlib
            digest=hashlib.sha256(json.dumps(prior['sql_files'],sort_keys=True).encode()).hexdigest()
            sql('''ALTER TABLE production."供应商档案表"
              DROP COLUMN "统一社会信用代码",DROP COLUMN "户名",DROP COLUMN "账户ID",DROP COLUMN "开户行",
              ADD COLUMN "相关文件路径" text;
              DELETE FROM erp_ops.schema_upgrade_log WHERE upgrade_id='008_supplier_profile';
              DROP TABLE erp_ops.supplier_profile_retired_fields;''','easyerp_admin')
            from easyerp import literal as L
            sql(f"UPDATE erp_ops.schema_version SET source_sha256={L(prior['source_sha256s'][0])},build_sha256={L(digest)} WHERE version='0.2.0'",'easyerp_admin')
        check('legacy supplier structure restored',[c['name'] for c in columns(erp,db)]==OLD_FIELDS)
        sql('''INSERT INTO production."供应商档案表"("供应商ID","名称","联系方式","相关文件路径")
          VALUES ('SUPTEST','升级测试供应商','电话与邮箱','原始资料/合同.pdf');
          INSERT INTO production."采购合同表"("采购合同ID","供应商ID","合同文件路径","状态")
          VALUES ('PCTEST','SUPTEST','合同.pdf','草稿');
          INSERT INTO production."采购订单表"("采购单ID","供应商ID","创建日期","状态","币种")
          VALUES ('POTEST','SUPTEST','2026-11-15','草稿','CNY');
          CREATE VIEW production.supplier_path_dependency_test AS SELECT "相关文件路径" FROM production."供应商档案表";''','easyerp_admin')
        try:
            migrate(erp,db,True)
            raise AssertionError('dependent view must refuse column removal')
        except RuntimeError as error:
            check('unknown dependency refuses migration','depend' in str(error).lower() or '依赖' in str(error))
        check('failed migration rolls back all added columns',[c['name'] for c in columns(erp,db)]==OLD_FIELDS)
        sql('DROP VIEW production.supplier_path_dependency_test','easyerp_admin')
        result=erp.migrate(db)
        check('generic migrate applies the reviewed upgrade',result['status']=='PASS')
        check('upgrade preserves existing names contacts and linked orders',sql('''SELECT s."名称"='升级测试供应商' AND s."联系方式"='电话与邮箱'
          AND c."供应商ID"=s."供应商ID" AND p."供应商ID"=s."供应商ID"
          FROM production."供应商档案表" s JOIN production."采购合同表" c ON c."采购合同ID"='PCTEST'
          JOIN production."采购订单表" p ON p."采购单ID"='POTEST' WHERE s."供应商ID"='SUPTEST' ''')=='t')
        check('retired nonempty path archived exactly',sql("SELECT file_path FROM erp_ops.supplier_profile_retired_fields WHERE supplier_id='SUPTEST'",'easyerp_admin')=='原始资料/合同.pdf')
        check('new field order is exact',[c['name'] for c in columns(erp,db)]==FIELDS)
        check('migration is idempotent',migrate(erp,db,True)['status']=='already applied')
        erp.ensure_database(db)
        check('startup recognizes upgraded build',True)
        _CACHE.clear()
        entry=ManualEntry({'mode':'demo'});entry.db=db;entry.data.db=db
        obj=entry.object(KEY)
        account=next(c for c in obj['columns'] if c['name']=='账户ID')
        check('supplier account is plain text without company-account foreign key',account['type']=='text' and not account['reference'])
        values={'名称':'六字段验收供应商','联系方式':'010-12345678','统一社会信用代码':'001234567890123456','户名':'收款户名','账户ID':'000012345678901234567890','开户行':'测试银行分行'}
        saved=entry.save({'request_id':uuid.uuid4().hex,'object':KEY,'values':values})['records'][0]
        record=entry.record(KEY,saved['id'])
        check('manual create retains all six fields and leading zeroes',all(record['values'][k]==v for k,v in values.items()))
        saved=entry.save({'request_id':uuid.uuid4().hex,'object':KEY,'operation':'update','id':saved['id'],'version':record['version'],'values':{'开户行':'更新分行'}})['records'][0]
        check('manual update preserves account text',entry.record(KEY,saved['id'])['values']['账户ID']==values['账户ID'])
        templates=StandardTemplates({'mode':'demo'});templates.entry=entry
        body,_=templates.download(KEY)
        check('CSV template contains only new ordered fields',list(csv.reader(io.StringIO(body.decode('utf-8-sig'))))==[FIELDS])
        imports=StandardImport('demo');imports.entry=entry
        stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(FIELDS)
        writer.writerow(['SUPCSV','导入测试','',values['统一社会信用代码'],values['户名'],values['账户ID'],values['开户行']])
        plan=imports.plan(KEY+'.csv',stream.getvalue().encode('utf-8-sig'))
        check('standard CSV parser retains all account and credit-code digits',not plan['errors'] and plan['rows'][0]['values']['账户ID']==values['账户ID'] and plan['rows'][0]['values']['统一社会信用代码']==values['统一社会信用代码'])
        imports.write(plan,check_id=uuid.uuid4().hex,allow_incomplete=True)
        check('standard CSV transaction saves new account fields exactly',entry.record(KEY,'SUPCSV')['values']['账户ID']==values['账户ID'] and entry.record(KEY,'SUPCSV')['values']['统一社会信用代码']==values['统一社会信用代码'])
        try:
            imports.plan(KEY+'.csv',('供应商ID,名称,联系方式,相关文件路径\r\nSUPCSV,旧模板,,a.pdf\r\n').encode('utf-8-sig'))
            raise AssertionError('old CSV header accepted')
        except Exception as error:
            check('retired CSV header produces explicit re-download error','重新下载模板' in str(error))
        try:
            entry.save({'request_id':uuid.uuid4().hex,'object':KEY,'values':{'名称':'旧字段测试','相关文件路径':'a.pdf'}})
            raise AssertionError('retired entry field accepted')
        except EntryError:
            check('retired field cannot be silently saved',True)
        refs=entry.data.rows("""SELECT n.nspname||'.'||t.relname AS object,a.attname AS field
          FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
          JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
          WHERE c.confrelid='production."供应商档案表"'::regclass AND c.contype='f' """)
        check('all five inbound references still expose supplier name choices',len(refs)==5 and all(any(row['value']=='SUPTEST' and '升级测试供应商' in row['label'] for row in entry.options(r['object'],r['field'],selected='SUPTEST')['rows']) for r in refs))
        check('live and demo source facts unchanged',all(before[target]==original_signature(target) for target in before))
        report={'passed':len(checks),'checks':checks,'source_backup':str(backup),'migration':result}
        (ROOT/'reports/supplier-profile-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'passed':len(checks),'isolated_database_removed':db},ensure_ascii=False))
    finally:
        if db.startswith('easyerp_supplier_test_'):
            erp.sql(f'DROP DATABASE IF EXISTS {I(db)} WITH (FORCE)',db='postgres',role='easyerp_admin')


if __name__=='__main__':
    main()
