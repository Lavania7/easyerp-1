"""Install nullable company profile fields, backing up each existing database first."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
from easyerp import ERP, literal as L

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {'公司英文名': 'text', '公司简称': 'text', '联系电话': 'text', '联系邮箱': 'text',
          '办公地址': 'text', '官方网站': 'text', '联系人': 'text', '法定代表人': 'text',
          '成立日期': 'date', '经营范围': 'text', '备注': 'text'}
VERSION = 'company-profile-v1'


def fingerprint(erp, db):
    return erp.sql('''SELECT md5(coalesce(string_agg(jsonb_strip_nulls(to_jsonb(t))::text,
      E'\\n' ORDER BY "主体ID"),'')) FROM legal."公司主体档案表" t''',
                   db=db, role='easyerp_read').stdout.strip()


def install():
    erp = ERP()
    actual = erp.sql('SHOW data_directory', db='postgres', role='easyerp_admin').stdout.strip()
    if Path(actual).resolve() != (ROOT/'var/pgdata').resolve():
        raise RuntimeError('PostgreSQL cluster does not belong to this project')
    source = (ROOT/'db/app/company_schema.sql').read_text(encoding='utf-8')
    digest = hashlib.sha256(source.encode()).hexdigest()
    results = []
    for db in (erp.c['database'], erp.c['database']+'_ui_demo'):
        exists = erp.sql(f'SELECT 1 FROM pg_database WHERE datname={L(db)}', db='postgres', role='easyerp_admin').stdout.strip()
        if exists != '1':
            results.append({'database': db, 'status': 'not created'}); continue
        columns = json.loads(erp.sql('''SELECT coalesce(json_object_agg(column_name,data_type),'{}')
          FROM information_schema.columns WHERE table_schema='legal' AND table_name='公司主体档案表' ''',
                                    db=db, role='easyerp_read').stdout)
        if any(name in columns and columns[name] != kind for name, kind in FIELDS.items()):
            raise RuntimeError('Existing company profile column has an unexpected type: '+db)
        installed = erp.sql("SELECT to_regclass('erp_ops.frontend_company_profile_migration') IS NOT NULL", db=db, role='easyerp_admin').stdout.strip() == 't'
        previous = erp.sql(f'SELECT sql_sha256 FROM erp_ops.frontend_company_profile_migration WHERE version={L(VERSION)}', db=db, role='easyerp_admin').stdout.strip() if installed else ''
        if previous and previous != digest:
            raise RuntimeError('Installed company migration differs from the SQL file: '+db)
        if previous and all(name in columns for name in FIELDS):
            backup = erp.sql(f'SELECT backup_file FROM erp_ops.frontend_company_profile_migration WHERE version={L(VERSION)}', db=db, role='easyerp_read').stdout.strip()
            results.append({'database': db, 'status': 'already installed', 'backup': backup}); continue
        before = fingerprint(erp, db)
        backup = erp.backup(db=db)
        erp.sql('BEGIN;\n'+source+f'''\nINSERT INTO erp_ops.frontend_company_profile_migration(version,sql_sha256,backup_file)
          VALUES ({L(VERSION)},{L(digest)},{L(str(backup))}) ON CONFLICT (version) DO NOTHING;\nCOMMIT;''', db=db, role='easyerp_admin')
        after = fingerprint(erp, db)
        if before != after:
            raise RuntimeError('Company records changed during migration: '+db)
        results.append({'database': db, 'status': 'PASS', 'backup': str(backup), 'company_data_unchanged': True})
    report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'version': VERSION,
              'sql_sha256': digest, 'results': results}
    (ROOT/'reports/company-profile-migration.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    install()
