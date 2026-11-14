"""Start the installed pgAdmin locally using a separate project profile."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen
import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from easyerp import ERP,write_json

PORT=8093
URL=f'http://127.0.0.1:{PORT}'


def alive(key):
    try:
        with urlopen(URL+'/misc/ping?key='+key,timeout=2) as response:
            return response.read()==b'PING'
    except Exception:
        return False


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--open-browser',action='store_true')
    args=parser.parse_args()
    erp=ERP()
    erp.init()
    pgadmin=Path(erp.c['postgres_bin']).parent/'pgAdmin 4'
    python=pgadmin/'python'/'python.exe'
    entry=pgadmin/'web'/'pgAdmin4.py'
    if not python.is_file() or not entry.is_file():
        raise RuntimeError('未找到 PostgreSQL 安装附带的 pgAdmin 4，请检查安装目录')
    private=ROOT/'var'/'pgadmin'
    erp.private_dir(private)
    state_file=ROOT/'.secrets'/'pgadmin-runtime.json'
    state=json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {}
    key=state.get('key','')
    if not key or not alive(key):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',PORT))==0:
                raise RuntimeError('8093 端口被其他进程占用，拒绝连接到其他服务')
        env={k:v for k,v in os.environ.items() if k not in ('PYTHONHOME','PYTHONPATH') and not k.startswith('PG')}
        key=secrets.token_urlsafe(32)
        env.update(CONFIG_DISTRO_FILE_PATH=str(ROOT/'tools'/'pgadmin_config.py'),
          PGADMIN_SERVER_MODE='OFF',PGADMIN_INT_PORT=str(PORT),PGADMIN_INT_KEY=key,
          PGADMIN_CONFIG_DEFAULT_SERVER='127.0.0.1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8',
          PYTHONDONTWRITEBYTECODE='1',PGPASSFILE=str(ROOT/'.secrets'/'pgpass.conf'),PGCLIENTENCODING='UTF8')
        env['PATH']=str(pgadmin/'runtime')+os.pathsep+env.get('PATH','')
        hidden=getattr(subprocess,'CREATE_NO_WINDOW',0)
        with (private/'setup.log').open('a',encoding='utf-8') as log:
            setup=subprocess.run([str(python),'-s',str(ROOT/'tools'/'configure_pgadmin.py')],
                                env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90,creationflags=hidden)
        if setup.returncode:
            raise RuntimeError('SQL 界面配置失败，请查看 var\\pgadmin\\setup.log')
        with (private/'console.log').open('a',encoding='utf-8') as log:
            proc=subprocess.Popen([str(python),'-s',str(entry)],env=env,
               stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=hidden,
               cwd=str(pgadmin/'web'))
        state={'pid':proc.pid,'key':key,'port':PORT,'url':URL,'started_at':datetime.now(timezone.utc).isoformat()}
        write_json(state_file,state)
        for attempt in range(90):
            if alive(key): break
            if proc.poll() is not None: raise RuntimeError('SQL 界面进程提前退出，请查看 var\\pgadmin\\console.log')
            time.sleep(.5)
        else: raise RuntimeError('SQL 界面启动超时，请查看 var\\pgadmin\\console.log')
    # Desktop key is ephemeral. Keep it in the protected project profile, never in EXEs/log output.
    launch_url=URL+'/?key='+key
    if args.open_browser:
        # Same HTTP desktop launch mechanism used by the installed pgAdmin runtime.
        os.startfile(launch_url)
    write_json(ROOT/'reports'/'backend-start.json',{'status':'READY','url':URL,'port':PORT,
        'profile_directory':str(private),'existing_credentials':True,'database':erp.c['database'],
        'at_utc':datetime.now(timezone.utc).isoformat()})
    print('easyERP SQL 界面已就绪：'+URL)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        sys.exit(1)
