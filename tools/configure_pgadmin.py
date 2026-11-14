"""Runs in the installed pgAdmin Python, never the project Python."""
from pathlib import Path
import json
import os
import runpy
import sys

ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
web=Path(config['postgres_bin']).parent/'pgAdmin 4'/'web'
sys.path.insert(0,str(web))
namespace=runpy.run_path(str(web/'pgAdmin4.py'),run_name='easyerp_pgadmin_configure')
app=namespace['app']
import config as pgconfig
from pgadmin.model import Server,db,User
from pgadmin.utils import load_database_servers
profiles=[]
with app.test_request_context():
    for label,database in [('easyERP 0.2 正式库',config['database']),('easyERP 0.2 演示库',config['database']+'_ui_demo')]:
        existing=Server.query.filter_by(name=label).first()
        if existing is None:
            profile={'Servers':{'1':{'Name':label,'Group':'easyERP 本机数据库','Host':'127.0.0.1',
              'Port':config['port'],'MaintenanceDB':database,'Username':'easyerp_app',
              'ConnectionParameters':{'passfile':str(ROOT/'.secrets'/'pgpass.conf'),'sslmode':'prefer','connect_timeout':10},
              'Comment':'本项目本机数据库；使用已有录入角色，不是超级管理员。'}}}
            path=ROOT/'var'/'pgadmin'/'server-import.json'
            path.write_text(json.dumps(profile,ensure_ascii=True),encoding='utf-8')
            load_database_servers(str(path),None,pgconfig.DESKTOP_USER,True)
            existing=Server.query.filter_by(name=label).first()
        if existing is None or existing.host!='127.0.0.1' or existing.port!=config['port'] or existing.maintenance_db!=database:
            raise RuntimeError('pgAdmin profile does not match the project connection')
        if existing.username!='easyerp_app' or existing.password:
            raise RuntimeError('Expected existing app role with pgpass, no stored password')
        profiles.append({'name':label,'server_id':existing.id,'group_id':existing.servergroup_id,'database':database,'role':existing.username})
    # Set Chinese only on first configuration; preserve later user preferences.
    marker=ROOT/'var'/'pgadmin'/'easyerp-configured.json'
    first=not marker.exists()
    marker.write_text(json.dumps({'profiles':profiles,'pgadmin_version':pgconfig.APP_VERSION},ensure_ascii=False,indent=2),encoding='utf-8')
    if first:
        from pgadmin.preferences import Preferences
        from flask_login import login_user
        user=User.query.filter_by(email=pgconfig.DESKTOP_USER).first()
        login_user(user)
        pref=Preferences.module('misc').preference('user_language')
        if pref is not None:
            pref.set('zh_Hans_CN')
            db.session.commit()
print('Project SQL profiles prepared; passwords are read from the existing protected pgpass file.')
