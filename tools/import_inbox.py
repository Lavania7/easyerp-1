"""Agent inbox adapter. Business validation and writes use the frontend service."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from imports import Imports, ImportError as ServiceError, MAX_FILE


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    within(path, ROOT / 'import' / 'batches')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def within(path, parent):
    resolved = path.resolve()
    if not resolved.is_relative_to(parent.resolve()):
        raise ValueError('路径不在规定目录内：' + str(path))
    return resolved


def scan():
    inbox = ROOT / 'import' / 'inbox'
    result = []
    kinds = {'.csv': 'table', '.tsv': 'table', '.xlsx': 'workbook', '.xls': 'needs-conversion',
             '.txt': 'text', '.md': 'text', '.pdf': 'document', '.docx': 'document'}
    for path in sorted(inbox.rglob('*')):
        if not path.is_file() or path.name.startswith(('.', '~$')):
            continue
        within(path, inbox)
        result.append({'file': path.relative_to(ROOT / 'import').as_posix(),
                       'size_bytes': path.stat().st_size, 'sha256': sha(path),
                       'kind': kinds.get(path.suffix.lower(), 'reference-only')})
    return {'files': result, 'count': len(result), 'database_accessed': False}


def bundle(file):
    batches = ROOT / 'import' / 'batches'
    path = within(Path(file) if Path(file).is_absolute() else ROOT / file, batches)
    relative = path.relative_to(batches.resolve())
    if len(relative.parts) < 3 or relative.parts[1] != 'prepared' or path.suffix.lower() != '.csv':
        raise ValueError('请选择 import/batches/批次/prepared/ 下的标准CSV')
    batch = batches / relative.parts[0]
    if path.stat().st_size > MAX_FILE:
        raise ValueError('标准CSV超过前端单文件大小限制')
    raw = path.read_bytes()
    evidence_path = within(path.with_name(path.name + '.sources.json'), batch)
    evidence_bytes = evidence_path.read_bytes()
    evidence = json.loads(evidence_bytes.decode('utf-8-sig'))
    sources = {}
    for item in evidence['sources']:
        if item['id'] in sources:
            raise ValueError('来源ID重复')
        source = within(batch / item['file'], batch / 'sources')
        if sha(source) != item['sha256']:
            raise ValueError('来源副本校验失败：' + item['file'])
        sources[item['id']] = item
    if not sources:
        raise ValueError('必须登记原始来源副本')
    text = None
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            pass
    if text is None:
        raise ValueError('CSV编码需与前端支持范围一致')
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    headers = next(reader, [])
    if (not headers or not isinstance(evidence['fields'], dict) or
            set(evidence['fields']) != set(headers) or
            any(not str(value).strip() for value in evidence['fields'].values())):
        raise ValueError('字段映射必须逐列覆盖CSV表头，未知值注明未提供')
    lines, last_line = set(), reader.line_num
    for values in reader:
        start, last_line = last_line + 1, reader.line_num
        if any(value.strip() for value in values):
            lines.add(start)
    mapped = set()
    for row in evidence['rows']:
        line = row['csv_line']
        if type(line) is not int or line in mapped or not row['sources']:
            raise ValueError('源行对应重复或为空')
        mapped.add(line)
        for reference in row['sources']:
            if reference['id'] not in sources or not str(reference['location']).strip():
                raise ValueError('源行对应必须提供已登记来源和工作表/行/段落位置')
    if mapped != lines:
        raise ValueError('每条非空CSV记录必须且只能有一条源行对应')
    return path, batch, raw, evidence, hashlib.sha256(evidence_bytes).hexdigest(), evidence_bytes


def check(file, mode, recheck=False):
    path, batch, raw, evidence, evidence_hash, evidence_bytes = bundle(file)
    state_path = within(path.with_name(path.name + '.check.json'), batch)
    file_hash = hashlib.sha256(raw).hexdigest()
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if recheck and state.get('attempt', {}).get('outcome') == 'unknown':
            raise ValueError('上次执行结果待核对；先用原文件和原选择重试apply，勿新建检查')
        if not recheck:
            if (state['mode'], state['sha256'], state['evidence_sha256']) != (mode, file_hash, evidence_hash):
                raise ValueError('文件、来源或模式已变化；核对后使用 --recheck')
            return {**state, 'cached_check': True,
                    'receipt_exists': (batch / 'receipts' / (str(state['check']['id']) + '.json')).is_file()}
    result = Imports().check(path.name, raw, mode)
    if result.get('sha256') != file_hash or result.get('mode') != mode:
        raise ValueError('前端检查返回了不匹配的文件或数据来源')
    state = {'mode': mode, 'file': path.relative_to(batch).as_posix(), 'sha256': file_hash,
             'evidence_sha256': evidence_hash, 'check': result}
    archive = within(batch / 'checks' / str(result['id']), batch)
    archive.mkdir(parents=True, exist_ok=True)
    within(archive / path.name, batch).write_bytes(raw)
    within(archive / 'sources.json', batch).write_bytes(evidence_bytes)
    save(archive / 'result.json', state)
    save(state_path, state)
    return state


def apply(file, mode, allow_incomplete=None, merge=None):
    path, batch, raw, evidence, evidence_hash, evidence_bytes = bundle(file)
    state_path = within(path.with_name(path.name + '.check.json'), batch)
    state = json.loads(state_path.read_text(encoding='utf-8'))
    if (state['mode'], state['sha256'], state['evidence_sha256']) != (
            mode, hashlib.sha256(raw).hexdigest(), evidence_hash):
        raise ValueError('检查后的文件、来源映射或数据来源已变化，请重新检查')
    checked = state['check']
    archive = within(batch / 'checks' / str(checked['id']), batch)
    if sha(within(archive / path.name, batch)) != state['sha256'] or sha(
            within(archive / 'sources.json', batch)) != evidence_hash:
        raise ValueError('检查归档已变化，请核对本次检查和来源')
    previous_attempt = state.get('attempt', {})
    if previous_attempt.get('outcome') == 'unknown' and (
            previous_attempt.get('allow_incomplete'), previous_attempt.get('merge')) != (allow_incomplete, merge):
        raise ValueError('上次结果待核对，必须使用原空缺和合并选择重试')
    if not checked.get('validated') or not checked.get('row_count') or (checked.get('match') or {}).get('type_id') != 'standard-master':
        raise ValueError('仅允许通过前端业务校验的标准主录CSV执行入库')
    # The backup belongs to this project and the selected database. No import SQL is duplicated here.
    from easyerp import ERP
    erp = ERP()
    erp.verify_files()
    database = erp.c['database'] + ('_ui_demo' if mode == 'demo' else '')
    actual = Path(erp.sql("SELECT current_setting('data_directory')", db=database).stdout.strip())
    if actual.resolve() != erp.data.resolve():
        raise ValueError('连接的数据库集群不是当前项目')
    backup = erp.backup(database)
    state['attempt'] = {'allow_incomplete': allow_incomplete, 'merge': merge,
                        'backup': str(backup), 'outcome': 'unknown'}
    save(state_path, state)
    try:
        result = Imports().execute(checked['id'], path.name, raw, mode,
                                   allow_incomplete=allow_incomplete, merge=merge)
    except ServiceError:
        state['attempt']['outcome'] = 'rejected'
        save(state_path, state)
        raise
    receipt = {'at_utc': datetime.now(timezone.utc).isoformat(), 'mode': mode,
               'file': state['file'], 'sha256': state['sha256'],
               'evidence_sha256': evidence_hash, 'sources': evidence['sources'],
               'check_archive': 'checks/' + str(checked['id']),
               'check_id': checked['id'], 'allow_incomplete': allow_incomplete,
               'merge': merge, 'backup': str(backup), 'execution': result}
    save(batch / 'receipts' / (str(checked['id']) + '.json'), receipt)
    state['attempt']['outcome'] = 'committed'
    save(state_path, state)
    return receipt


def main():
    parser = argparse.ArgumentParser(description='导入箱盘点；通过前端同一服务检查/导入已映射标准CSV')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('scan', help='只读列出inbox原文件，不连接数据库')
    for command in ('check', 'apply'):
        item = commands.add_parser(command)
        item.add_argument('--file', required=True, help='项目相对路径或完整路径')
        item.add_argument('--mode', choices=('live', 'demo'), required=True)
        if command == 'check':
            item.add_argument('--recheck', action='store_true', help='明确开启新的前端检查批次')
        else:
            item.add_argument('--allow-incomplete', choices=('true', 'false'))
            item.add_argument('--merge', choices=('latest', 'fill_empty'))
    args = parser.parse_args()
    if args.command == 'scan':
        result = scan()
    elif args.command == 'check':
        result = check(args.file, args.mode, args.recheck)
    else:
        result = apply(args.file, args.mode, args.allow_incomplete, args.merge)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ServiceError, csv.Error, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
