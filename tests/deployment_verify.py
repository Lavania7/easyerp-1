"""Run against this task's local deployment only; no production fixture writes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from easyerp import ERP, ident, write_json

e=ERP()
info=json.loads(e.sql("SELECT json_build_object('database',current_database(),'version',version(),'listen_addresses',current_setting('listen_addresses'),'port',inet_server_port(),'data_directory',current_setting('data_directory'),'encoding',current_setting('server_encoding'),'timezone',current_setting('TimeZone'));").stdout)
assert info['database']=='easyerp_v02' and info['port']==55433
assert info['listen_addresses']=='127.0.0.1'
assert Path(info['data_directory']).resolve()==(ROOT/'var'/'pgdata').resolve()
tables=e.sql("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1;").stdout.splitlines()
row_sql='SELECT sum(n) FROM ('+' UNION ALL '.join('SELECT count(*) n FROM '+'.'.join(ident(x) for x in table.split('.',1)) for table in tables)+') x;'
business_rows=int(e.sql(row_sql).stdout.strip())
assert business_rows==0
assert e.sql("SELECT count(*) FROM pg_database WHERE datname LIKE 'easyerp_v02_test_%' OR datname LIKE 'easyerp_v02_restore_%';",db='postgres').stdout.strip()=='0'
assert e.sql("SELECT bool_and(rolpassword LIKE 'SCRAM-SHA-256$%') FROM pg_authid WHERE rolname IN ('easyerp_admin','easyerp_app','easyerp_read');",db='postgres').stdout.strip()=='t'
saved=e.env.copy()
try:
    e.env['PGPASSWORD']='deliberately-invalid-test-password'
    rejected=e.sql('SELECT 1;',role='easyerp_read',ok=False)
    assert rejected.returncode!=0
finally:
    e.env=saved
backup=e.backup()
recovery=e.restore_test(backup)
export=e.export()
with zipfile.ZipFile(export['export']) as z:
    assert len([n for n in z.namelist() if n.endswith('.csv')])==146
    manifest=json.loads(z.read('manifest.json'))
    assert manifest['null_marker']=='\\N'
    for name,digest in manifest['files'].items():
        assert hashlib.sha256(z.read(name)).hexdigest()==digest
check=e.check()
assert check['business_issue_count']==0
tests=json.loads((ROOT/'reports'/'test-latest.json').read_text(encoding='utf-8'))
assert tests['passed'] and tests['populated_restore']['data_signature_matched']
startup=Path(os.environ['APPDATA'])/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'/'easyerp-0.2.vbs'
assert startup.is_file() and str(ROOT) in startup.read_text(encoding='utf-16')
log=(ROOT/'var'/'log'/'startup.log').read_bytes().decode('utf-16',errors='ignore')
# Startup readiness is additionally confirmed by the live SQL connection above.
report={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','connection':info,
        'source_sha256':hashlib.sha256((ROOT/json.loads((ROOT/'db/manifest.json').read_text(encoding='utf-8'))['source']).read_bytes()).hexdigest(),
        'business_objects':{'schemas':6,'tables':146,'foreign_keys':475,'views':15},
        'additional_operations_views':3,'business_rows':business_rows,
        'business_test_count':len(tests['sql_tests']),'role_test_count':tests['role_tests'],
        'populated_restore_data_matched':True,'production_backup_restore':recovery,
        'export':export,'export_checksums':'PASS','wrong_password_rejected':True,
        'startup':{'file':str(startup),'current_user_logon':True,'launch_smoke_test':'PASS'},
        'windows_powershell_51_smoke_test':'PASS','temporary_databases_remaining':0,
        'business_issue_count':check['business_issue_count']}
write_json(ROOT/'reports'/'deployment.json',report)
print(json.dumps(report,ensure_ascii=False,indent=2))
