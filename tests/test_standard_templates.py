"""Read-only integration verification against the running local workbench."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--url', default='http://127.0.0.1:8092')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.project_root / 'frontend'))
    from data import Data, I, L

    checks = []
    downloads = {}

    def check(label, value):
        checks.append({'check': label, 'passed': bool(value)})
        if not value:
            raise AssertionError(label)

    def request(path, params=None, method='GET', headers=None):
        url = args.url + path + ('?' + urlencode(params) if params else '')
        req = Request(url, method=method, headers=headers or {})
        try:
            response = urlopen(req, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def json_api(path, params):
        status, _, body = request(path, params)
        check(path + ' returns 200 in ' + params['mode'], status == 200)
        return json.loads(body)

    def structure(data):
        return data.rows('''SELECT t.table_schema||'.'||t.table_name AS key,
            json_agg(json_build_object('name',c.column_name,'required',c.is_nullable='NO')
                     ORDER BY c.ordinal_position) AS columns
            FROM information_schema.tables t JOIN information_schema.columns c
              ON c.table_schema=t.table_schema AND c.table_name=t.table_name
            WHERE t.table_schema IN ('sales','production','rd','finance','legal','analysis')
              AND t.table_type='BASE TABLE'
            GROUP BY t.table_schema,t.table_name ORDER BY 1''')

    def signature(data, tables):
        # One read-only snapshot across every business table, including all NULLs.
        parts = []
        for key in tables:
            schema, name = key.split('.', 1)
            parts.append('SELECT ' + L(key) + ' AS key,count(*) AS rows,'
                         "md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) AS hash FROM "
                         + I(schema) + '.' + I(name) + ' t')
        return {row['key']: (row['rows'], row['hash']) for row in data.rows(' UNION ALL '.join(parts))}

    for mode in ('live', 'demo'):
        data = Data({'mode': mode})
        expected = {table['key']: table['columns'] for table in structure(data)}
        before = signature(data, expected)
        metadata = json_api('/api/templates/meta', {'mode': mode})
        actual = {obj['key']: obj for obj in metadata['objects']}
        check(mode + ' covers exactly all SQL business tables', actual.keys() == expected.keys() and bool(actual))
        check(mode + ' has six department counts', len(metadata['departments']) == 6 and
              sum(item['count'] for item in metadata['departments']) == len(expected) and
              all(item['count'] == sum(obj['schema'] == item['id'] for obj in actual.values()) for item in metadata['departments']))
        check(mode + ' correctly identifies data source and format', metadata['mode'] == mode and
              metadata['format'] == 'easyerp-master-csv-v1' and metadata['encoding'] == 'UTF-8 with BOM')

        def verify_download(item):
            key, obj = item
            status, headers, body = request('/api/templates/download', {'mode': mode, 'object': key})
            assert status == 200, (key, status)
            assert body.startswith(b'\xef\xbb\xbf') and body.endswith(b'\r\n'), key
            rows = list(csv.reader(io.StringIO(body.decode('utf-8-sig'), newline='')))
            assert rows == [[column['name'] for column in expected[key]]], key
            assert [{'name': col['name'], 'required': col['required']} for col in obj['columns']] == expected[key], key
            assert 'text/csv' in headers['Content-Type'] and headers['Cache-Control'] == 'no-store', key
            assert "filename*=UTF-8''" + quote(key + '.csv', safe='') in headers['Content-Disposition'], key
            assert headers['X-Template-Signature'] == obj['signature'], key
            assert headers['X-Template-Column-Count'] == str(len(expected[key])), key
            return {'object': key, 'columns': len(rows[0]), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

        with ThreadPoolExecutor(max_workers=4) as pool:
            downloads[mode] = list(pool.map(verify_download, actual.items()))
        check(mode + ' every CSV has exact SQL header order and no business/sample rows', len(downloads[mode]) == len(expected))
        account = actual['finance.资金账户档案表']
        subject = next(col for col in account['columns'] if col['name'] == '主体ID')
        check(mode + ' nullable fields follow actual SQL', subject['required'] == next(col['required'] for col in expected[account['key']] if col['name'] == '主体ID'))
        check(mode + ' field constraints provided', any(col['primary'] for col in account['columns']) and
              any(col['reference'] for col in account['columns']) and
              any(col['options'] for obj in actual.values() for col in obj['columns']) and
              any(obj['rules'] for obj in actual.values()))
        sample = next(iter(actual))
        status, headers, body = request('/api/templates/download', {'mode': mode, 'object': sample}, method='HEAD')
        check(mode + ' HEAD has accurate headers and no body', status == 200 and not body and int(headers['Content-Length']) == downloads[mode][0]['bytes'])
        for key in ('', 'erp_ops.source_import_file', 'pg_catalog.pg_class', 'sales.订单与履约交付表', "sales.x';DROP TABLE x;--"):
            status, _, body = request('/api/templates/download', {'mode': mode, 'object': key})
            check(mode + ' rejects non-table template ' + repr(key), status == 400 and 'error' in json.loads(body))
        check(mode + ' all business data unchanged', before == signature(data, expected))

    for path in ('/api/templates/meta', '/api/templates/download'):
        status, _, _ = request(path, {'mode': 'invalid'})
        check(path + ' rejects invalid source', status == 400)
        status, _, _ = request(path, method='POST')
        check(path + ' is read-only', status == 405)
        status, _, _ = request(path, headers={'Origin': 'https://example.com'})
        check(path + ' rejects cross-origin access', status == 403)
    for path in ('/', '/templates.js', '/templates.css'):
        status, _, body = request(path)
        check(path + ' served by frontend', status == 200 and bool(body))
        if path == '/':
            html = body.decode('utf-8')
            check('download button and modules wired', all(value in html for value in ('id="templates-open"', '/templates.js', '/templates.css')))
    report = {'checks': checks, 'downloads': downloads, 'business_data_unchanged': True}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': len(checks), 'templates': {mode: len(rows) for mode, rows in downloads.items()},
                      'business_data_unchanged': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
