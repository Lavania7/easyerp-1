"""Small local read-only web application. No framework or third-party services."""
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

from data import Data, InvalidRequest, ROOT

WEB=Path(__file__).resolve().parent/'web'
CATALOG={}
LOCK=threading.Lock()


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

    def do_POST(self): self.send(405,encode({'error':'首版为查询模式，不接受写入'}))
    do_PUT=do_POST
    do_DELETE=do_POST
    do_PATCH=do_POST

    def do_HEAD(self): self.do_GET()

    def do_GET(self):
        global CATALOG
        allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if self.headers.get('Host','') not in allowed:
            return self.send(403,encode({'error':'只接受本机访问'}))
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+host for host in allowed}:
            return self.send(403,encode({'error':'来源不受支持'}))
        parsed=urlsplit(self.path)
        path=parsed.path
        if not path.startswith('/api/'):
            files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css','/favicon.svg':'favicon.svg'}
            if path not in files: return self.send(404,encode({'error':'页面不存在'}))
            file=WEB/files[path]
            return self.send(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        params={k:v[-1] for k,v in parse_qs(parsed.query,keep_blank_values=True).items()}
        try:
            data=Data(params)
            if path=='/api/health':
                status=data.rows('SELECT current_database() AS database,current_user AS role')
                return self.send(200,encode({'ok':True,'mode':data.mode,'read_only':True,'status':status}))
            with LOCK:
                if data.mode not in CATALOG or path=='/api/meta': CATALOG[data.mode]=data.catalog()
                catalog=CATALOG[data.mode]
            if path=='/api/meta':
                result={**catalog,'read_only':True,'mode':data.mode,'query_timezone':data.tz,
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
        except InvalidRequest as exc:
            return self.send(400,encode({'error':str(exc)}))
        except (RuntimeError,OSError,ValueError,KeyError) as exc:
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
