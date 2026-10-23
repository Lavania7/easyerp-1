"""Local query and manual-entry application. No framework or remote services."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from decimal import Decimal
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import io
import json
import logging
import mimetypes
import os
import sys
import threading
import secrets
import hmac
import sqlite3

from data import Data, InvalidRequest, ROOT
from entry import ManualEntry, EntryError, PREFERRED
from imports import Imports, ImportError as FormatError, MAX_FILE
from standard_templates import StandardTemplates

WEB=Path(__file__).resolve().parent/'web'
CATALOG={}
LOCK=threading.Lock()
WRITE_TOKEN=secrets.token_urlsafe(32)
MAX_BODY=1024*1024
IMPORTS=None
IMPORT_LOCK=threading.Lock()


def import_service():
    global IMPORTS
    with IMPORT_LOCK:
        if IMPORTS is None: IMPORTS=Imports()
        return IMPORTS


def strict_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('重复字段')
        result[key]=value
    return result


def encode(value):
    return json.dumps(value,ensure_ascii=False,default=lambda x:str(x) if isinstance(x,Decimal) else None).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    server_version='easyERP/0.2'
    def log_message(self, fmt,*args): logging.info('%s %s',self.address_string(),fmt%args)

    def send(self,status,body,content_type='application/json; charset=utf-8',extra=None):
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers()
        if self.command!='HEAD': self.wfile.write(body)

    def local_request(self):
        allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if len(self.headers.get_all('Host',[]))!=1 or self.headers.get('Host','') not in allowed:
            self.send(403,encode({'error':'只接受本机访问'})); return False
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+host for host in allowed}:
            self.send(403,encode({'error':'来源不受支持'})); return False
        if self.headers.get('Sec-Fetch-Site')=='cross-site':
            self.send(403,encode({'error':'不接受跨站请求'})); return False
        return True

    def do_POST(self):
        if not self.local_request(): return
        parsed=urlsplit(self.path)
        if parsed.path not in ('/api/entry/save','/api/import/check','/api/import/settings','/api/import/execute'):
            return self.send(405,encode({'error':'该接口不接受写入'}))
        if not hmac.compare_digest(self.headers.get('X-EasyERP-Token',''),WRITE_TOKEN):
            return self.send(403,encode({'error':'保存会话已失效，请刷新页面后重试。'}))
        is_file=parsed.path in ('/api/import/check','/api/import/execute')
        if self.headers.get_content_type()!=('application/octet-stream' if is_file else 'application/json'):
            return self.send(415,encode({'error':'文件检查需要原始文件内容。' if is_file else '保存需要 JSON 格式'}))
        try:
            if self.headers.get('Transfer-Encoding'): raise ValueError()
            length=int(self.headers.get('Content-Length','-1'))
            if length<0: raise ValueError()
        except ValueError:
            return self.send(400,encode({'error':'请求长度无效'}))
        if length>(MAX_FILE if is_file else MAX_BODY):
            return self.send(413,encode({'error':'单个文件不能超过 16 MB。' if is_file else '一次内容过多，请分次保存。'}))
        params={k:v[-1] for k,v in parse_qs(parsed.query,keep_blank_values=True).items()}
        if is_file:
            try:
                service=import_service()
                raw=self.rfile.read(length)
                if parsed.path=='/api/import/execute':
                    result=service.execute(params.get('check_id',''),params.get('filename',''),raw,params.get('mode','live'),
                                           allow_incomplete=params.get('allow_incomplete'),merge=params.get('merge'))
                else:
                    result=service.check(params.get('filename',''),raw,params.get('mode','live'))
                return self.send(200,encode(result))
            except FormatError as exc:
                return self.send(exc.status,encode({'error':str(exc)}))
            except Exception:
                logging.exception('Import format check failed')
                return self.send(503,encode({'error':'暂时无法完成检查，请保留原文件后重试。'}))
        try:
            payload=json.loads(self.rfile.read(length).decode('utf-8'),parse_float=Decimal,
                object_pairs_hook=strict_object,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except (ValueError,UnicodeError,RecursionError):
            return self.send(400,encode({'error':'保存内容不是有效 JSON'}))
        params={k:v[-1] for k,v in parse_qs(parsed.query,keep_blank_values=True).items()}
        try:
            if parsed.path=='/api/import/settings':
                result=import_service().configure(payload,params.get('mode','live'))
                result['token']=WRITE_TOKEN
                return self.send(200,encode(result))
            result=ManualEntry(params).save(payload)
            return self.send(200,encode(result))
        except FormatError as exc:
            return self.send(exc.status,encode({'error':str(exc)}))
        except InvalidRequest as exc:
            return self.send(getattr(exc,'status',400),encode({'error':str(exc),'fields':getattr(exc,'fields',[])}))
        except (RuntimeError,OSError,ValueError,KeyError,sqlite3.Error):
            logging.exception('Manual save failed')
            return self.send(503,encode({'error':'暂时无法保存，请检查本机数据库服务或前端日志。'}))

    def unsupported_write(self):
        if self.local_request(): self.send(405,encode({'error':'该接口不接受此操作'}))
    do_PUT=unsupported_write
    do_DELETE=unsupported_write
    do_PATCH=unsupported_write

    def do_HEAD(self): self.do_GET()

    def do_GET(self):
        global CATALOG
        if not self.local_request(): return
        parsed=urlsplit(self.path)
        path=parsed.path
        if not path.startswith('/api/'):
            files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css','/favicon.svg':'favicon.svg','/manual.js':'manual.js','/manual.css':'manual.css','/import.js':'import.js','/import.css':'import.css','/templates.js':'templates.js','/templates.css':'templates.css','/preferences.js':'preferences.js','/preferences.css':'preferences.css','/dark.css':'dark.css','/locales.js':'locales.js','/i18n.js':'i18n.js'}
            if path not in files: return self.send(404,encode({'error':'页面不存在'}))
            file=WEB/files[path]
            return self.send(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        params={k:v[-1] for k,v in parse_qs(parsed.query,keep_blank_values=True).items()}
        try:
            if path.startswith('/api/templates/'):
                templates=StandardTemplates(params)
                if path=='/api/templates/meta': return self.send(200,encode(templates.metadata()))
                if path=='/api/templates/download':
                    body,headers=templates.download(params.get('object',''))
                    return self.send(200,body,'text/csv; charset=utf-8',headers)
                return self.send(404,encode({'error':'模板接口不存在'}))
            if path.startswith('/api/import/'):
                service=import_service()
                if path=='/api/import/meta': return self.send(200,encode({**service.metadata(params.get('mode','live')),'token':WRITE_TOKEN}))
                if path=='/api/import/history': return self.send(200,encode(service.history(params.get('mode','live'),params.get('offset',0))))
                if path=='/api/import/events': return self.send(200,encode(service.events()))
                return self.send(404,encode({'error':'导入接口不存在；业务数据导入尚未开放。'}))
            data=Data(params)
            if path=='/api/health':
                status=data.rows('SELECT current_database() AS database,current_user AS role')
                return self.send(200,encode({'ok':True,'mode':data.mode,'read_only':False,'query_read_only':True,'manual_entry':True,'import_interface':True,'status':status}))
            if path.startswith('/api/entry/'):
                entry=ManualEntry(params)
                if path=='/api/entry/meta':
                    return self.send(200,encode({'objects':list(entry.catalog().values()),'preferred':PREFERRED,'token':WRITE_TOKEN,'mode':entry.mode}))
                if path=='/api/entry/options':
                    return self.send(200,encode(entry.options(params.get('object',''),params.get('field',''),params.get('q',''),params.get('selected',''),params.get('offset',0))))
                if path=='/api/entry/record':
                    return self.send(200,encode(entry.record(params.get('object',''),params.get('id',''))))
                return self.send(404,encode({'error':'录入接口不存在'}))
            with LOCK:
                if data.mode not in CATALOG or path=='/api/meta': CATALOG[data.mode]=data.catalog()
                catalog=CATALOG[data.mode]
            if path=='/api/meta':
                result={**catalog,'read_only':False,'query_read_only':True,'manual_entry':True,'mode':data.mode,'query_timezone':data.tz,
                        'today':datetime.now(timezone.utc).date().isoformat()}
            elif path=='/api/overview': result=data.overview()
            elif path=='/api/tasks': result={'rows':data.tasks()}
            elif path=='/api/search': result={'rows':data.search_all()}
            elif path=='/api/list': result=data.listing(params.get('kind','orders'))
            elif path=='/api/detail': result=data.detail(params.get('kind','order'),params.get('id',''))
            elif path=='/api/explore': result=data.explore(params.get('object',''),catalog)
            elif path=='/api/record': result=data.record(params.get('object',''),params.get('id',''),catalog)
            elif path=='/api/export':
                result=data.explore(params['object'],catalog,True) if params.get('object') else data.listing(params.get('kind','orders'),True)
                rows=result['rows']
                fields=list(dict.fromkeys(k for row in rows for k in row))
                if not fields and params.get('object'): fields=[c['name'] for c in data.object(params['object'],catalog)['columns']]
                if not fields:
                    source={'orders':'sales.订单与履约交付表','workorders':'production.生产执行交付表','funds':'finance.账户流水标准化表'}[params.get('kind','orders')]
                    fields=[c['name'] for c in data.object(source,catalog)['columns']]
                if not fields: fields=['说明']
                stream=io.StringIO(newline='')
                writer=csv.writer(stream); writer.writerow(fields)
                def cell(value):
                    if value is None: return '\\N'
                    text=str(value)
                    if text and text[0] in '=+-@' and not __import__('re').fullmatch(r'-?\d+(\.\d+)?',text): return "'"+text
                    return text
                for row in rows: writer.writerow([cell(row.get(k)) for k in fields])
                return self.send(200,stream.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8',
                    {'Content-Disposition':'attachment; filename="easyerp-records.csv"','X-Total-Rows':str(result['total'][0]['count']),'X-Exported-Rows':str(len(rows))})
            else: return self.send(404,encode({'error':'接口不存在'}))
            result['queried_at']=datetime.now(timezone.utc).isoformat()
            return self.send(200,encode(result))
        except FormatError as exc:
            return self.send(exc.status,encode({'error':str(exc)}))
        except EntryError as exc:
            return self.send(exc.status,encode({'error':str(exc),'fields':exc.fields}))
        except InvalidRequest as exc:
            return self.send(400,encode({'error':str(exc)}))
        except (RuntimeError,OSError,ValueError,KeyError,sqlite3.Error) as exc:
            logging.exception('Query failed: %s',path)
            return self.send(503,encode({'error':'暂时无法读取数据，请检查本机数据库是否运行，或查看前端日志。','mode':params.get('mode','live')}))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',type=int,default=8092)
    args=p.parse_args()
    logs=ROOT/'var'/'log'
    logs.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=logs/'frontend.log',level=logging.INFO,encoding='utf-8',format='%(asctime)s %(message)s')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    # A verifiable instance record for lifecycle helpers; no credentials stored.
    (ROOT/'var'/'frontend.json').write_bytes(encode({'pid':os.getpid(),'port':args.port,'url':f'http://127.0.0.1:{args.port}','started_at':datetime.now(timezone.utc).isoformat()}))
    print(f'easyERP front end: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__=='__main__': main()
