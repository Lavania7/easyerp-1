"""Prepared relocation phases. Default is read-only preview; --apply is never implicit."""
from pathlib import Path
from contextlib import closing
import argparse
import hashlib
import json
import shutil
import socket
import sqlite3
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT/'tools')]
from easyerp import ERP, ident, literal
from database_manager import atomic_json
from preview_database_relocation import inspect

TARGET=Path('D:/database/easyerp-live')
RECORD=TARGET/'migration/restored.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_file(file):
    relative=Path(file['relative'])
    require(not relative.is_absolute() and '..' not in relative.parts,'清单相对路径无效。')
    path=Path(file['path']).resolve()
    require(path.is_relative_to(ROOT.resolve()) and path==(ROOT/relative).resolve(),'清单文件超出项目范围。')
    return path


def require(condition, message):
    if not condition: raise RuntimeError(message)


def writers_stopped(erp):
    with socket.socket() as sock:
        require(sock.connect_ex(('127.0.0.1',8092))!=0,'8092仍在运行；先暂停写入并核实归属后停止前端。')
    connections=erp.sql("BEGIN READ ONLY; SELECT count(*) FROM pg_stat_activity WHERE datname="+literal(erp.c['database'])+" AND pid<>pg_backend_pid() AND usename IN ('easyerp_app','easyerp_admin'); COMMIT;",db=erp.c['database'],role='easyerp_admin').stdout.strip()
    require(connections=='0','仍有正式库应用/管理连接，拒绝执行迁移阶段。')


def verify_cluster(erp):
    actual=json.loads(erp.sql("BEGIN READ ONLY; SELECT json_build_object('directory',current_setting('data_directory'),'port',inet_server_port()); COMMIT;",db='postgres',role='easyerp_admin').stdout)
    require(Path(actual['directory']).resolve()==erp.data.resolve() and actual['port']==erp.c['port'],'实际集群不匹配。')


def snapshot(erp):
    database=erp.c['database']
    tables=erp.sql("BEGIN READ ONLY; SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis','erp_ops') ORDER BY 1; COMMIT;",db=database,role='easyerp_admin').stdout.splitlines()
    union=' UNION ALL '.join('SELECT '+literal(key)+" AS object,count(*) AS rows,md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) AS hash FROM "+'.'.join(ident(p) for p in key.split('.',1))+' t' for key in tables)
    rows=json.loads(erp.sql('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT json_agg(row_to_json(q) ORDER BY object) FROM ('+union+') q; COMMIT;',db=database,role='easyerp_admin').stdout)
    schema=erp.run('pg_dump',['-h','127.0.0.1','-p',erp.c['port'],'-U','easyerp_admin','-w','--schema-only',database]).stdout
    schema='\n'.join(line for line in schema.splitlines() if not line.startswith(('\\restrict ','\\unrestrict ')))
    return {'tables':rows,'schema_sha256':hashlib.sha256(schema.encode()).hexdigest()}


def source_from_record(record):
    return ERP(config=record['source_config'],runtime_root=ROOT)


def destination(record):
    return ERP(config=record['target_config'],runtime_root=TARGET)


def copy_history(source, destination_path, mode):
    destination_path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as original, closing(sqlite3.connect(destination_path)) as copied:
        original.backup(copied)
        copied.execute('DELETE FROM checks WHERE mode<>?',(mode,))
        copied.commit()
        copied.execute('VACUUM')


def history_signature(path, mode):
    if not path.is_file():return None
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as connection:
        rows={'checks':connection.execute('SELECT * FROM checks WHERE mode=? ORDER BY id',(mode,)).fetchall(),
              'settings':connection.execute('SELECT * FROM settings ORDER BY type_id').fetchall(),
              'events':connection.execute('SELECT * FROM events ORDER BY id').fetchall()}
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def _restore(plan):
    require(digest(ROOT/'config.json')==plan['config_sha256'],'配置已改变，请重新生成并审阅预览。')
    require(plan['source']['database']=='easyerp_v02' and plan['source']['port']==55433,'源库或端口偏离本审批方案。')
    require(Path(plan['source']['directory']).resolve()==(ROOT/'var/pgdata').resolve(),'源集群偏离本审批方案。')
    require(Path(plan['target']['runtime_root']).resolve()==TARGET.resolve() and plan['target']['port']==55434,'目标偏离本审批方案。')
    require(plan['target']['database']=='easyerp_v02','目标库名偏离审批范围。')
    for key,name in (('data_directory','pgdata'),('private_directory','.secrets'),('workspace_directory','workspace')):
        require(Path(plan['target'][key]).resolve()==(TARGET/name).resolve(),'目标子目录偏离审批范围。')
    require(not TARGET.exists(),'目标已存在，拒绝覆盖或续用。')
    for parent in TARGET.parents:
        require(not parent.is_symlink() and not parent.is_junction(),'目标祖先目录含链接/联接。')
    with socket.socket() as sock:
        require(sock.connect_ex(('127.0.0.1',55434))!=0,'55434已被占用。')
    source=ERP();verify_cluster(source);writers_stopped(source)
    manifest,build=source.verify_files()
    installed=source.sql("BEGIN READ ONLY; SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0'; COMMIT;",db=source.c['database'],role='easyerp_admin').stdout.strip()
    require(source.version_matches(installed,manifest,build),'先单独批准并完成010字段升级；迁移执行器不执行隐式结构迁移。')
    require(plan['template']['build_sha256']==build,'模板已改变，请重新生成预览。')
    for file in plan['external_files']:
        path=source_file(file)
        require(path.is_relative_to(ROOT) and path.is_file() and digest(path)==file['sha256'],'外部文件清单已改变，请重新预览。')
    TARGET.mkdir(parents=True,exist_ok=False)
    source.private_dir(TARGET)
    evidence=TARGET/'migration';source.private_dir(evidence)
    (evidence/'config.before.json').write_bytes((ROOT/'config.json').read_bytes())
    atomic_json(evidence/'approved-preview.json',plan)
    source_config=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
    config={key:source.c[key] for key in ('postgres_bin','python')}
    config.update(plan['target'])
    target=ERP(config=config,runtime_root=TARGET)
    atomic_json(TARGET/'config.candidate.json',config)
    before=snapshot(source)
    backup=TARGET/'backups/easyerp_v02-relocation.dump';source.private_dir(backup.parent)
    source.run('pg_dump',['-h','127.0.0.1','-p',source.c['port'],'-U','easyerp_admin','-w','-Fc','-f',backup,source.c['database']])
    target.init(ensure_database=False)
    target.run('createdb',['-h','127.0.0.1','-p',55434,'-U','easyerp_admin','-w','--template=template0','--encoding=UTF8',config['database']])
    target.run('pg_restore',['-h','127.0.0.1','-p',55434,'-U','easyerp_admin','-w','--exit-on-error','--single-transaction','-d',config['database'],backup])
    require(snapshot(target)==before and snapshot(source)==before,'源/目标全表数据或结构不一致，未切换配置。')
    workspace=source.workspace_root('live')/'live.json'
    if workspace.exists():
        destination_path=target.workspace_root('live')/'live.json'
        destination_path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(workspace,destination_path)
        require(digest(workspace)==digest(destination_path),'工作空间哈希不一致。')
    history=ROOT/'var/import-interface.sqlite3'
    if history.exists():
        with closing(sqlite3.connect(history.as_uri()+'?mode=ro',uri=True)) as original,closing(sqlite3.connect(evidence/'import-interface.before.sqlite3')) as copied:
            original.backup(copied)
        copy_history(history,TARGET/'var/import-interface.sqlite3','live')
    for file in plan['external_files']:
        if file['relative'].startswith(('backups/','exports/','import/')):
            copied=TARGET/'legacy-artifacts'/file['relative'];copied.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(file['path'],copied)
            require(digest(copied)==file['sha256'],'外部派生文件复制哈希不一致。')
    record={'source_config':source_config,'target_config':config,'snapshot':before,'backup':str(backup),
            'backup_sha256':digest(backup),'workspace_sha256':digest(workspace) if workspace.exists() else None,
            'history_signature':history_signature(history,'live'),
            'plan':plan,'state':'restored','at_utc':datetime.now(timezone.utc).isoformat()}
    atomic_json(backup.with_suffix('.json'),{'database':config['database'],'sha256':digest(backup),'file':backup.name,'data_signature':target.data_signature(config['database'])})
    record['restore_test']=target.restore_test(backup)
    require(record['restore_test']['passed'],'隔离恢复验证失败，未切换配置。')
    atomic_json(RECORD,record)
    return {'state':'restored','record':str(RECORD),'config_switched':False,'source_deleted':False}


def restore(plan):
    existed=TARGET.exists()
    try:return _restore(plan)
    except Exception:
        candidate=TARGET/'config.candidate.json'
        if not existed and candidate.is_file():
            config=json.loads(candidate.read_text(encoding='utf-8'))
            erp=ERP(config=config,runtime_root=TARGET)
            if erp.data.resolve()==(TARGET/'pgdata').resolve() and erp.run('pg_ctl',['-D',erp.data,'status'],ok=False).returncode==0:
                erp.run('pg_ctl',['-D',erp.data,'-w','-t','45','stop','-m','fast'])
        raise


def cutover(record):
    source=source_from_record(record);target=destination(record)
    verify_cluster(source);verify_cluster(target);writers_stopped(source)
    require(record['state']=='restored','阶段不匹配。')
    require(digest(ROOT/'config.json')==record['plan']['config_sha256'],'项目配置已改变。')
    require(snapshot(source)==record['snapshot'] and snapshot(target)==record['snapshot'],'恢复后产生数据变化，请重新评估迁移。')
    require(history_signature(ROOT/'var/import-interface.sqlite3','live')==record['history_signature'] and history_signature(TARGET/'var/import-interface.sqlite3','live')==record['history_signature'],'导入检查或共享格式设置发生变化，拒绝切换。')
    if record['workspace_sha256']:
        require(digest(source.workspace_root('live')/'live.json')==record['workspace_sha256'] and digest(target.workspace_root('live')/'live.json')==record['workspace_sha256'],'工作空间已改变。')
    candidate={**record['source_config'],'database_sources':{'live':record['target_config'],
               'demo':record['plan']['candidate']['database_sources']['demo']}}
    atomic_json(ROOT/'config.json',candidate)
    record.update(state='cutover',config_after_sha256=digest(ROOT/'config.json'))
    atomic_json(RECORD,record)
    return {'state':'cutover','source_deleted':False,'next':'由主控启动工作台并验收来源隔离；finalize另行审批'}


def finalize(record):
    require(record['state']=='cutover','尚未完成切换。')
    require(digest(ROOT/'config.json')==record['config_after_sha256'],'切换后配置又已改变。')
    source=source_from_record(record);target=destination(record)
    verify_cluster(source);verify_cluster(target);writers_stopped(source);writers_stopped(target)
    require(snapshot(source)==record['snapshot'],'旧源库产生变化，拒绝删除。')
    backup=target.backup(verify_data=True)
    require(target.restore_test(backup)['passed'],'目标最新备份恢复验证失败。')
    external=TARGET/'migration/finalize-external';target.private_dir(external)
    latest_workspace=target.workspace_root('live')/'live.json'
    if latest_workspace.is_file():shutil.copyfile(latest_workspace,external/'live.json')
    latest_history=TARGET/'var/import-interface.sqlite3'
    if latest_history.is_file():
        with closing(sqlite3.connect(latest_history.as_uri()+'?mode=ro',uri=True)) as original,closing(sqlite3.connect(external/'import-interface.sqlite3')) as copied:original.backup(copied)
    require(source.c['database']=='easyerp_v02' and source.c['port']==55433 and source.data.resolve()==(ROOT/'var/pgdata').resolve(),'源库清理范围不匹配。')
    workspace=source.workspace_root('live')/'live.json'
    if record['workspace_sha256']:
        require(digest(workspace)==record['workspace_sha256'],'源工作空间已变化。')
    for file in record['plan']['external_files']:
        if file['classification']=='live' and file['relative'].startswith(('backups/','exports/')):
            require(digest(Path(file['path']))==file['sha256'] and digest(TARGET/'legacy-artifacts'/file['relative'])==file['sha256'],'待清理文件与已验证目标不一致。')
    source.sql('DROP DATABASE '+ident(source.c['database'])+';',db='postgres',role='easyerp_admin')
    if workspace.exists(): workspace.unlink()
    workspace.with_suffix('.lock').unlink(missing_ok=True)
    history=ROOT/'var/import-interface.sqlite3'
    if history.exists():
        with closing(sqlite3.connect(history)) as connection:
            connection.execute("DELETE FROM checks WHERE mode='live'");connection.commit();connection.execute('VACUUM')
    removed=[]
    for file in record['plan']['external_files']:
        if file['classification']=='live' and file['relative'].startswith(('backups/','exports/')):
            path=Path(file['path']);require(path.is_relative_to(ROOT),'清理文件不在项目内。');path.unlink();removed.append(str(path))
    record.update(state='finalized',latest_target_backup=str(backup),removed_files=removed)
    remaining=source.sql("BEGIN READ ONLY; SELECT datname FROM pg_database WHERE NOT datistemplate AND datname<>'postgres' ORDER BY datname; COMMIT;",db='postgres',role='easyerp_admin').stdout.splitlines()
    record['source_business_databases']=remaining
    atomic_json(RECORD,record)
    return {'state':'finalized','removed_files':removed,'unclassified_preserved':True,'original_sources_preserved':True,
            'remaining_review_required':[file['path'] for file in record['plan']['external_files'] if file['classification']=='review-required'],
            'source_business_databases':remaining,
            'only_demo_business_database':remaining==[record['plan']['candidate']['database_sources']['demo']['database']]}


def rollback(record):
    require(record['state']=='cutover','只支持源库尚保留时回滚配置。')
    source=source_from_record(record);target=destination(record)
    verify_cluster(source);verify_cluster(target);writers_stopped(source);writers_stopped(target)
    require(snapshot(source)==record['snapshot'] and snapshot(target)==record['snapshot'],'已出现新正式记录，拒绝直接切回造成丢失。')
    require(history_signature(ROOT/'var/import-interface.sqlite3','live')==record['history_signature'] and history_signature(TARGET/'var/import-interface.sqlite3','live')==record['history_signature'],'导入历史或格式设置已变化，拒绝直接回滚。')
    if record['workspace_sha256']:
        require(digest(source.workspace_root('live')/'live.json')==record['workspace_sha256'] and digest(target.workspace_root('live')/'live.json')==record['workspace_sha256'],'工作空间已变化，拒绝直接回滚。')
    (ROOT/'config.json').write_bytes((TARGET/'migration/config.before.json').read_bytes())
    record['state']='rolled-back';atomic_json(RECORD,record)
    return {'state':'rolled-back','target_preserved':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--phase',choices=('restore','cutover','finalize','rollback'))
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if not args.apply:
        require(args.phase is None,'执行阶段必须显式--apply；省略则仅预览。')
        result=inspect()
        if args.out: atomic_json(args.out,result)
        else: print(json.dumps(result,ensure_ascii=False,indent=2))
        return
    require(args.phase is not None,'--apply必须指定阶段。')
    if args.phase=='restore':
        require(args.plan is not None,'restore需要已审阅的--plan文件。')
        result=restore(json.loads(args.plan.read_text(encoding='utf-8')))
    else:
        record=json.loads(RECORD.read_text(encoding='utf-8'))
        result={'cutover':cutover,'finalize':finalize,'rollback':rollback}[args.phase](record)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
