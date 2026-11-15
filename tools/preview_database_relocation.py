"""Read-only relocation inventory. This command cannot migrate, stop or delete anything."""
from pathlib import Path
from contextlib import closing
import argparse
import hashlib
import json
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT/'tools')]
from database_manager import DatabaseManager
from easyerp import ERP


def inspect():
    result=DatabaseManager().migration_preview()
    result['config_sha256']=hashlib.sha256((ROOT/'config.json').read_bytes()).hexdigest()
    result['template']=DatabaseManager().template()
    erp=ERP()
    result['installed_versions']={}
    manifest,build=erp.verify_files()
    for mode in ('live','demo'):
        source=ERP(mode=mode)
        installed=source.sql("BEGIN READ ONLY; SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0'; COMMIT;",db=source.c['database'],role='easyerp_admin').stdout.strip()
        result['installed_versions'][mode]={'installed':installed,'matches_current_build':source.version_matches(installed,manifest,build)}
    result['databases']=json.loads(erp.sql("BEGIN READ ONLY; SELECT json_agg(row_to_json(q)) FROM (SELECT datname,pg_database_size(oid) bytes,pg_get_userbyid(datdba) owner FROM pg_database WHERE NOT datistemplate ORDER BY datname) q; COMMIT;",db='postgres',role='easyerp_admin').stdout)
    result['external_files']=[]
    live=erp.c['database'];demo=ERP(mode='demo').c['database']
    def classification(path):
        if path==ROOT/'var/workspace/live.json': return 'live'
        if path==ROOT/'var/workspace/demo.json': return 'demo'
        meta=None
        if path.is_relative_to(ROOT/'backups'):
            meta=path if path.suffix=='.json' else path.with_suffix('.json')
        elif path.is_relative_to(ROOT/'exports'):
            if path.suffix=='.zip': meta=path.with_suffix('')/'manifest.json'
            else:
                for parent in (path.parent,*path.parents):
                    if not parent.is_relative_to(ROOT/'exports'): break
                    if (parent/'manifest.json').is_file(): meta=parent/'manifest.json';break
        if meta and meta.is_file():
            try:
                metadata=json.loads(meta.read_text(encoding='utf-8'))
                database=metadata.get('database') if isinstance(metadata,dict) else None
            except (ValueError,OSError): return 'review-required'
            if database==live:return 'live'
            if database==demo:return 'demo'
            if isinstance(database,str) and any(part in database for part in ('_test_','_restore_','_inline_test_')):return 'isolated-test'
        return 'review-required'
    for folder in ('var/workspace','backups','exports','import/batches','import/inbox'):
        for path in sorted((ROOT/folder).rglob('*')):
            if not path.is_file() or path.name.endswith('.lock') or path.name=='.gitkeep':
                continue
            result['external_files'].append({'path':str(path),'relative':path.relative_to(ROOT).as_posix(),
                'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'classification':classification(path)})
    history=ROOT/'var/import-interface.sqlite3'
    if history.exists():
        with closing(sqlite3.connect(history.as_uri()+'?mode=ro',uri=True)) as connection:
            result['import_history']={'path':str(history),'checks_by_mode':dict(connection.execute('SELECT mode,count(*) FROM checks GROUP BY mode')),
                                      'settings':connection.execute('SELECT count(*) FROM settings').fetchone()[0],
                                      'events':connection.execute('SELECT count(*) FROM events').fetchone()[0]}
    result['credentials']={'source_directory':str(erp.private),'action':'保留演示凭据，目标集群生成独立凭据；恢复角色名不复制密码到报告',
                           'files':[p.name for p in erp.private.iterdir() if p.is_file()]}
    result['unexecuted']=True
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    result=inspect()
    content=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(content,encoding='utf-8')
        print(json.dumps({'status':'preview-only','path':str(args.out),'files':len(result['external_files']),'executed':False},ensure_ascii=False))
    else:
        print(content)


if __name__=='__main__':main()
