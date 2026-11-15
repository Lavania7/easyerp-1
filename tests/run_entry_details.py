"""Serve the real application on a disposable port with every database query bound to a restored clone."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import threading
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--script', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args(); root = args.root.resolve()
sys.path[:0] = [str(root / 'app'), str(root / 'tools')]
from easyerp import ERP
from data import Data
import server

erp = ERP(); backup = erp.backup(erp.c['database'] + '_ui_demo')
clone = 'easyerp_inline_test_' + uuid.uuid4().hex[:12]
http = None
try:
    erp.run('createdb', ['-h', '127.0.0.1', '-p', erp.c['port'], '-U', 'easyerp_admin', '-w', '-T', 'template0', clone])
    erp.run('pg_restore', ['-h', '127.0.0.1', '-p', erp.c['port'], '-U', 'easyerp_admin', '-w', '--exit-on-error', '--single-transaction', '-d', clone, backup])
    sql = (root / 'db/app/csv_import_schema.sql').read_text(encoding='utf-8')
    erp.sql('BEGIN;\n' + sql[sql.index('CREATE OR REPLACE FUNCTION erp_ops.csv_allow_missing_fields('):sql.index('\n-- Incomplete vouchers')] + '\nCOMMIT;', db=clone, role='easyerp_admin')
    original_init = Data.__init__
    def isolated_init(self, params=None):
        original_init(self, params); self.db = clone
    Data.__init__ = isolated_init
    class QuietHandler(server.Handler):
        def log_message(self, *_): pass
    http = server.ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    env = dict(os.environ, EASYERP_URL=f'http://127.0.0.1:{http.server_port}', EASYERP_DETAIL_OUTPUT=str(args.out))
    result = subprocess.run(['node', str(args.script.resolve())], env=env, cwd=root)
    if result.returncode: raise SystemExit(result.returncode)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'isolation.json').write_text(json.dumps({'database': clone, 'original_databases_used_for_fixture_writes': False, 'restored_from': str(backup), 'cleanup': 'drop disposable clone in finally'}, indent=2), encoding='utf-8')
finally:
    if http:
        http.shutdown(); http.server_close()
    if not clone.startswith('easyerp_inline_test_'): raise RuntimeError('Unsafe cleanup target')
    erp.run('dropdb', ['-h', '127.0.0.1', '-p', erp.c['port'], '-U', 'easyerp_admin', '-w', '--if-exists', '--force', clone])
