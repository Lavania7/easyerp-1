"""Create and restore an empty instance in a TemporaryDirectory; never write source databases."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT/'tools')]
from database_manager import DatabaseManager
from easyerp import ERP, literal, ident


def source_state():
    state={'config':hashlib.sha256((ROOT/'config.json').read_bytes()).hexdigest(),'databases':{}}
    for mode in ('live','demo'):
        erp=ERP(mode=mode);database=erp.c['database']
        tables=erp.sql("BEGIN READ ONLY; SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1; COMMIT;",db=database,role='easyerp_read').stdout.splitlines()
        sql=' UNION ALL '.join('SELECT '+literal(key)+" AS object,count(*) AS rows,md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) AS digest FROM "+'.'.join(ident(part) for part in key.split('.',1))+' t' for key in tables)
        content=erp.sql('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT json_agg(row_to_json(q) ORDER BY object) FROM ('+sql+') q; COMMIT;',db=database,role='easyerp_read').stdout
        workspace=erp.workspace_root(mode)/(mode+'.json')
        state['databases'][mode]={'database':database,'signature':hashlib.sha256(content.encode()).hexdigest(),
                                'workspace':hashlib.sha256(workspace.read_bytes()).hexdigest()}
    return state


def main():
    before=source_state();start=time.monotonic();result={'source_before':before,'passed':False}
    with TemporaryDirectory(prefix='easyerp-new-instance-') as directory:
        folder=Path(directory)
        manager=DatabaseManager(picker=lambda:str(folder))
        manager.registry=folder/'catalog/registry.json'
        ticket=manager.select_folder({})['folder_ticket']
        preview=manager.preview({'label':'隔离空库验证','folder_ticket':ticket})
        erp=None
        try:
            created=manager.create({'plan_id':preview['plan_id']})
            target=Path(created['node']['directory'])
            config=json.loads((target/'instance.json').read_text(encoding='utf-8'))['config']
            erp=ERP(config=config,runtime_root=target)
            assert erp.run('pg_ctl',['-D',erp.data,'status'],ok=False).returncode != 0
            erp.start_server()
            actual=erp.sql("BEGIN READ ONLY; SELECT current_setting('data_directory'); COMMIT;",db=config['database'],role='easyerp_admin').stdout.strip()
            assert Path(actual).resolve()==erp.data.resolve()
            result['instance']={key:preview[key] for key in ('directory','database','port')}
            result['business_rows']=created['node']['business_rows']
            result['roles']={}
            for role in ('easyerp_read','easyerp_app'):
                output=erp.sql("BEGIN READ ONLY; SELECT json_build_object('insert',has_table_privilege(current_user,'finance.\"人员档案表\"','INSERT'),'select',has_table_privilege(current_user,'finance.\"人员档案表\"','SELECT'),'create_schema',has_schema_privilege(current_user,'finance','CREATE')); COMMIT;",db=config['database'],role=role).stdout
                result['roles'][role]=json.loads(output)
                assert result['roles'][role]['select']
                assert not result['roles'][role]['create_schema']
                assert result['roles'][role]['insert']==(role=='easyerp_app')
                assert erp.sql('CREATE TABLE finance.forbidden(id int);',db=config['database'],role=role,ok=False).returncode!=0
            backup=erp.backup(verify_data=True)
            result['restore']=erp.restore_test(backup)
            assert result['restore']['passed']
            assert manager.create({'plan_id':preview['plan_id']})['replayed']
            result['passed']=True
        finally:
            if erp and erp.run('pg_ctl',['-D',erp.data,'status'],ok=False).returncode==0:
                erp.run('pg_ctl',['-D',erp.data,'-w','-t','45','stop','-m','fast'])
    after=source_state();result['source_after']=after
    assert after==before,'Source config/business/workspace changed'
    result['source_unchanged']=True;result['seconds']=round(time.monotonic()-start,2)
    report=Path(sys.argv[1]) if len(sys.argv)>1 else Path.cwd()/'database-manager-integration.json'
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'source_unchanged':True,'seconds':result['seconds'],'report':str(report)},ensure_ascii=False))


if __name__=='__main__':main()
