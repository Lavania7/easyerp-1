"""Validate finance profile upgrades only in disposable restored databases."""
from pathlib import Path
import argparse
import csv
import io
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'),str(ROOT/'app')]
from easyerp import ERP,ident as I,literal as L
from migrate_finance_profiles import migrate,columns,snapshot_query,PEOPLE,ACCOUNTS,NEW_FIELDS,OLD_PEOPLE,OLD_ACCOUNTS
from entry import ManualEntry,EntryError,_CACHE
from standard_templates import StandardTemplates
from standard_import import StandardImport


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    erp=ERP()
    db='easyerp_finance_profile_test_'+uuid.uuid4().hex[:12]
    fresh=db+'_fresh'
    originals=[erp.c['database'],erp.c['database']+'_ui_demo']
    checks=[]
    def check(label,condition):
        if not condition: raise AssertionError(label)
        checks.append(label)
        print('PASS '+label,flush=True)
    def sql(query,role='easyerp_read',target=None):
        return erp.sql(query,db=target or db,role=role).stdout.strip()
    def signature(target):
        _,query=snapshot_query(erp,target,False)
        return sql(query,target=target)
    before={target:signature(target) for target in originals}
    backup=erp.backup(db=originals[1],verify_data=True)
    try:
        erp.run('createdb',['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','-T','template0',db])
        erp.run('pg_restore',['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','--exit-on-error','--single-transaction','-d',db,backup])
        check('restored pre-upgrade personnel shape',[c['name'] for c in columns(erp,db,PEOPLE)]==OLD_PEOPLE)
        check('restored pre-upgrade account shape',[c['name'] for c in columns(erp,db,ACCOUNTS)]==OLD_ACCOUNTS)
        source='C:\\来源\\账户 "001"\\资金\n原始目录'
        sql(f'''UPDATE finance."资金账户档案表" SET "余额来源"={L(source)};
            CREATE VIEW finance.finance_profile_dependency AS SELECT "余额来源" FROM finance."资金账户档案表";''','easyerp_admin')
        try:
            migrate(erp,db,True)
        except RuntimeError as error:
            check('database dependency blocks removal','dependencies' in str(error))
        else: raise AssertionError('Dependent view was removed')
        check('blocked migration preserves old shape',[c['name'] for c in columns(erp,db,PEOPLE)]==OLD_PEOPLE)
        sql('DROP VIEW finance.finance_profile_dependency','easyerp_admin')
        check('preview does not change schema',migrate(erp,db)['status']=='preview' and [c['name'] for c in columns(erp,db,ACCOUNTS)]==OLD_ACCOUNTS)
        sql('''CREATE TABLE erp_ops.account_profile_retired_fields (
          upgrade_id text NOT NULL,account_id text NOT NULL,balance_source text,
          source_database text NOT NULL DEFAULT current_database(),source_table text NOT NULL DEFAULT 'finance.资金账户档案表',
          source_field text NOT NULL DEFAULT '余额来源',archived_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(upgrade_id,account_id));
          CREATE FUNCTION erp_ops.finance_profile_test_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'fixture archive failure'; END $$;
          CREATE TRIGGER finance_profile_test_fail BEFORE INSERT ON erp_ops.account_profile_retired_fields FOR EACH ROW EXECUTE FUNCTION erp_ops.finance_profile_test_fail();''','easyerp_admin')
        try:
            migrate(erp,db,True)
        except RuntimeError as error:
            check('archive failure aborts transaction','fixture archive failure' in str(error))
        else: raise AssertionError('Archive error ignored')
        check('DDL and archive roll back together',[c['name'] for c in columns(erp,db,PEOPLE)]==OLD_PEOPLE and sql('SELECT count(*) FROM erp_ops.account_profile_retired_fields','easyerp_admin')=='0')
        sql('DROP TRIGGER finance_profile_test_fail ON erp_ops.account_profile_retired_fields; DROP FUNCTION erp_ops.finance_profile_test_fail();','easyerp_admin')
        result=migrate(erp,db,True)
        check('migration preserves business facts and all foreign keys',result['status']=='PASS' and result['business_facts_preserved'] and result['references_preserved'])
        check('retired path and provenance preserved exactly',sql(f"SELECT bool_and(balance_source={L(source)} AND source_database=current_database() AND source_table='finance.资金账户档案表' AND source_field='余额来源') FROM erp_ops.account_profile_retired_fields",'easyerp_admin')=='t')
        check('archive unavailable to read and app roles',sql("SELECT NOT has_table_privilege('easyerp_read','erp_ops.account_profile_retired_fields','SELECT') AND NOT has_table_privilege('easyerp_app','erp_ops.account_profile_retired_fields','SELECT')")=='t')
        check('payroll fields are nullable and without defaults',all(not c['required'] and c['default'] is None for c in columns(erp,db,PEOPLE)[-3:]))
        check('migration repeat is idempotent',migrate(erp,db,True)['status']=='already applied')
        erp.ensure_database(db)
        check('startup accepts upgraded schema',True)
        _CACHE.clear()
        entry=ManualEntry({'mode':'demo'})
        entry.db=db
        entry.data.db=db
        obj=entry.object(PEOPLE)
        check('metadata includes exact payroll types',[c['type'] for c in obj['columns'][-3:]]==['numeric(20,4)','text','text'])
        check('payroll account is external text without foreign key',not obj['columns'][-1].get('reference'))
        value='9999999999999999.1234'
        saved=entry.save({'request_id':uuid.uuid4().hex,'object':PEOPLE,'values':{'姓名':'迁移专项验收','部门':'财务','基准工资':value,'工资账户开户行':'工资账户银行','工资账户ID':'000012345678901234567890'}})['records'][0]
        record=entry.record(PEOPLE,saved['id'])
        check('entry preserves 20 digit salary and leading zero account',record['values']['基准工资']==value and record['values']['工资账户ID']=='000012345678901234567890')
        minimal=entry.save({'request_id':uuid.uuid4().hex,'object':PEOPLE,'values':{'姓名':'未知工资验收','部门':'财务'}})['records'][0]
        check('omitted payroll values remain NULL',all(entry.record(PEOPLE,minimal['id'])['values'][k] is None for k in NEW_FIELDS))
        entry.save({'request_id':uuid.uuid4().hex,'object':PEOPLE,'operation':'update','id':minimal['id'],'version':entry.record(PEOPLE,minimal['id'])['version'],'values':{'基准工资':'0'}})
        check('real zero salary differs from unknown',entry.record(PEOPLE,minimal['id'])['values']['基准工资']=='0.0000')
        try:
            entry.save({'request_id':uuid.uuid4().hex,'object':PEOPLE,'values':{'姓名':'负数验收','部门':'财务','基准工资':'-1'}})
        except (EntryError,RuntimeError): check('negative salary rejected',True)
        else: raise AssertionError('Negative salary accepted')
        templates=StandardTemplates({'mode':'demo'})
        templates.entry=entry
        body,_=templates.download(PEOPLE)
        check('personnel CSV template lists new fields',list(csv.reader(io.StringIO(body.decode('utf-8-sig'))))==[OLD_PEOPLE+NEW_FIELDS])
        body,_=templates.download(ACCOUNTS)
        check('account CSV template omits retired field',list(csv.reader(io.StringIO(body.decode('utf-8-sig'))))==[OLD_ACCOUNTS[:-1]])
        imports=StandardImport('demo')
        imports.entry=entry
        stream=io.StringIO(newline='')
        writer=csv.writer(stream)
        writer.writerow(OLD_PEOPLE+NEW_FIELDS)
        writer.writerow(['','CSV工资验收','财务','','',value,'CSV银行','000000987654321'])
        plan=imports.plan(PEOPLE+'.csv',stream.getvalue().encode('utf-8-sig'))
        check('CSV accepts new payroll fields',not plan['errors'])
        imports.write(plan,check_id=uuid.uuid4().hex,allow_incomplete=True)
        check('CSV salary and account remain exact',sql('''SELECT "基准工资"::text||'|'||"工资账户ID" FROM finance."人员档案表" WHERE "姓名"='CSV工资验收' ''')==value+'|000000987654321')
        erp.ensure_database(fresh)
        check('fresh install contains new personnel schema',[c['name'] for c in columns(erp,fresh,PEOPLE)]==OLD_PEOPLE+NEW_FIELDS)
        check('fresh install omits old balance source',[c['name'] for c in columns(erp,fresh,ACCOUNTS)]==OLD_ACCOUNTS[:-1])
        erp.sql(file=ROOT/'tests/structure.sql',db=fresh,role='easyerp_admin')
        from business_queries import expand_queries
        erp.sql(expand_queries((ROOT/'tests/business.sql').read_text(encoding='utf-8')),db=fresh,role='easyerp_admin')
        check('fresh structure and business SQL pass',True)
        check('original live and demo facts untouched',all(before[target]==signature(target) for target in originals))
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({'passed':len(checks),'checks':checks,'source_backup':str(backup),'migration':result,'temporary_databases':[db,fresh]},ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        for target in (db,fresh):
            if not target.startswith('easyerp_finance_profile_test_'): raise RuntimeError('Unsafe cleanup target')
            erp.sql(f'DROP DATABASE IF EXISTS {I(target)} WITH (FORCE)',db='postgres',role='easyerp_admin')


if __name__=='__main__':
    main()
