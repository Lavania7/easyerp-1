"""Versioned format recognition and local registration history; no business SQL writes."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from contextlib import contextmanager
import csv
import hashlib
import io
import json
import sqlite3
import zipfile
import xml.etree.ElementTree as ET

MAX_FILE = 16 * 1024 * 1024
MAX_EXPANDED = 96 * 1024 * 1024
MAX_ROWS = 100000
MAX_CELLS = 2000000
BASE = Path(__file__).resolve().parent


class ImportError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def stamp():
    return datetime.now(timezone.utc).isoformat()


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def trimmed(row):
    row = [str(v or '').strip().removeprefix('\ufeff') for v in row]
    while row and not row[-1]:
        row.pop()
    return row


def xml(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ImportError('文件包含不支持的 XML 定义。')
    return ET.fromstring(raw)


def xlsx(raw):
    """Inspect actual worksheet XML, ignoring often incorrect exported dimensions."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
        with archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(infos) > 2000 or len(names) != len(set(names)):
                raise ImportError('工作簿结构过于复杂或包含重复文件。')
            if sum(i.file_size for i in infos) > MAX_EXPANDED:
                raise ImportError('工作簿展开后过大，请拆分后检查。', 413)
            if any(i.flag_bits & 1 for i in infos):
                raise ImportError('请先在本机另存为未加密的 XLSX 文件。')
            if any('vbaproject' in n.lower() for n in names):
                raise ImportError('当前格式目录仅支持不含宏的 XLSX 文件。')
            shared = []
            if 'xl/sharedStrings.xml' in names:
                shared = [''.join(e.itertext()) for e in xml(archive.read('xl/sharedStrings.xml'))]
            book = xml(archive.read('xl/workbook.xml'))
            rels = {r.get('Id'): r for r in xml(archive.read('xl/_rels/workbook.xml.rels'))}
            sheets = []
            for sheet in book.findall('./{*}sheets/{*}sheet'):
                rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                rel = rels.get(rid)
                if rel is None or rel.get('TargetMode') == 'External':
                    raise ImportError('工作表引用无效。')
                target = rel.get('Target', '')
                path = str(PurePosixPath(target.lstrip('/'))) if target.startswith('/') else str(PurePosixPath('xl') / target)
                if '..' in PurePosixPath(path).parts or '\\' in path or not path.startswith('xl/'):
                    raise ImportError('工作表路径无效。')
                content = archive.read(path)
                xml(content)  # reject declarations and malformed XML before streaming rows
                top = {}
                row_count = cell_count = max_columns = 0
                last_row = 0
                for event, elem in ET.iterparse(io.BytesIO(content), events=('end',)):
                    if elem.tag.rsplit('}', 1)[-1] != 'row':
                        continue
                    row_count += 1
                    row_index = int(elem.get('r', row_count))
                    if row_index <= last_row or row_index > MAX_ROWS or row_count > MAX_ROWS:
                        raise ImportError('工作表行号重复、无效或超过 100,000 行。')
                    last_row = row_index
                    cells = {}
                    for cell in elem:
                        if cell.tag.rsplit('}', 1)[-1] != 'c':
                            continue
                        cell_count += 1
                        ref = cell.get('r', '')
                        letters = ''.join(c for c in ref if 'A' <= c <= 'Z')
                        col = 0
                        for letter in letters:
                            col = col * 26 + ord(letter) - 64
                        if not col or col > 256 or col in cells or cell_count > MAX_CELLS:
                            raise ImportError('工作表列号无效或内容超出检查范围。')
                        if cell.find('{*}v') is not None or cell.find('{*}is') is not None or cell.find('{*}f') is not None:
                            max_columns = max(max_columns, col)
                        if row_index <= 20:
                            value = cell.find('{*}v')
                            text = value.text or '' if value is not None else ''
                            kind = cell.get('t')
                            if kind == 's':
                                text = shared[int(text)]
                            elif kind == 'inlineStr':
                                text = ''.join(t.text or '' for t in cell.findall('.//{*}t'))
                            if cell.find('{*}f') is not None:
                                text = '[公式表头不支持]'
                            cells[col] = text
                        else:
                            cells[col] = None
                    if row_index <= 20:
                        top[row_index] = trimmed([cells.get(c, '') for c in range(1, max(cells, default=0) + 1)])
                    elem.clear()
                sheets.append({'name': sheet.get('name', ''), 'top': top, 'rows': row_count, 'max_columns': max_columns})
                if len(sheets) > 20:
                    raise ImportError('一次最多检查 20 张工作表。')
            if not sheets:
                raise ImportError('工作簿中没有工作表。')
            return {'container': 'xlsx', 'encoding': None, 'sheets': sheets}
    except ImportError:
        raise
    except (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError, IndexError, OSError, RuntimeError, NotImplementedError) as exc:
        raise ImportError('无法读取此 XLSX，请确认文件完整且未加密。') from exc


def text_table(raw):
    text = None
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            pass
    if text is None or '\x00' in text:
        raise ImportError('无法读取文本编码；支持 UTF-8 和 GB18030。')
    try:
        rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    except csv.Error as exc:
        raise ImportError('CSV 分隔符或引号不完整。') from exc
    if len(rows) > MAX_ROWS or sum(map(len, rows)) > MAX_CELLS or any(len(r) > 256 for r in rows):
        raise ImportError('文本内容超出检查范围，请拆分后检查。', 413)
    if not rows or not any(trimmed(r) for r in rows):
        raise ImportError('文件为空。')
    return {'container': 'csv', 'encoding': encoding,
            'sheets': [{'name': '', 'rows': len(rows), 'max_columns': max(len(trimmed(r)) for r in rows),
                        'top': {i: trimmed(r) for i, r in enumerate(rows[:20], 1)}}]}


class Imports:
    def __init__(self, root=None, catalog=None):
        self.root = Path(root) if root else BASE.parent
        self.path = self.root / 'var' / 'import-interface.sqlite3'
        self.catalog = json.loads((Path(catalog) if catalog else BASE / 'import_formats.json').read_text(encoding='utf-8'))
        self.types = {t['id']: t for t in self.catalog['types']}
        if len(self.types) != len(self.catalog['types']):
            raise RuntimeError('Duplicate import type')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (
                    type_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL,
                    version INTEGER NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, type_id TEXT NOT NULL,
                    enabled INTEGER NOT NULL, version INTEGER NOT NULL, recorded_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT NOT NULL,
                    filename TEXT NOT NULL, sha256 TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, result TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def metadata(self):
        with self.connect() as db:
            settings = {r['type_id']: dict(r) for r in db.execute('SELECT * FROM settings')}
        types = []
        for key, kind in self.types.items():
            state = settings.get(key, {'enabled': 1, 'version': 0, 'updated_at': None})
            types.append({**kind, **state, 'enabled': bool(state['enabled']), 'registered_at': self.catalog['registered_at']})
        return {'types': types, 'catalog_version': self.catalog['version'], 'execution_available': False,
                'scope': 'workspace', 'max_file_bytes': MAX_FILE, 'extensions': ['.xlsx', '.csv', '.txt']}

    def configure(self, body):
        if not isinstance(body, dict) or set(body) != {'type_id', 'enabled', 'version'}:
            raise ImportError('请提供类型、启用状态和当前版本。')
        key = body['type_id']
        if not isinstance(key, str) or key not in self.types:
            raise ImportError('此表格类型未登记，需要开发新增支持。', 404)
        if type(body['enabled']) is not bool or type(body['version']) is not int:
            raise ImportError('启用状态或版本无效。')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM settings WHERE type_id=?', (key,)).fetchone()
            version = row['version'] if row else 0
            enabled = bool(row['enabled']) if row else True
            if body['version'] != version:
                raise ImportError('此类型已在其他页面修改，请刷新后重试。', 409)
            if body['enabled'] != enabled:
                now = stamp()
                db.execute('INSERT OR REPLACE INTO settings VALUES(?,?,?,?)', (key, int(body['enabled']), version + 1, now))
                db.execute('INSERT INTO events(type_id,enabled,version,recorded_at) VALUES(?,?,?,?)',
                           (key, int(body['enabled']), version + 1, now))
        return self.metadata()

    @staticmethod
    def mode(mode):
        if mode not in ('live', 'demo'):
            raise ImportError('无效数据来源。')
        return mode

    def check(self, filename, raw, mode='live'):
        mode = self.mode(mode)
        if not isinstance(filename, str) or not filename or len(filename) > 240 or any(ord(c) < 32 or c in '/\\' for c in filename):
            raise ImportError('文件名无效，请重新选择文件。')
        if not raw:
            raise ImportError('文件为空。')
        if len(raw) > MAX_FILE:
            raise ImportError('单个文件不能超过 16 MB。', 413)
        extension = Path(filename).suffix.lower()
        if extension not in ('.xlsx', '.csv', '.txt'):
            raise ImportError('当前仅检查 XLSX、CSV 和 TXT 文件；其他格式需要新增支持。', 415)
        try:
            shape = xlsx(raw) if extension == '.xlsx' else text_table(raw)
            matches = []
            for kind in self.catalog['types']:
                for profile in kind['profiles']:
                    if profile['container'] != shape['container'] or len(shape['sheets']) != 1:
                        continue
                    sheet = shape['sheets'][0]
                    if profile.get('sheet') is not None and profile['sheet'] != sheet['name']:
                        continue
                    if sheet['top'].get(profile['header_row']) != profile['columns']:
                        continue
                    if sheet['max_columns'] > len(profile['columns']):
                        continue
                    if any(sheet['top'].get(int(n)) != v for n, v in profile.get('markers', {}).items()):
                        continue
                    matches.append({'type_id': kind['id'], 'type_name': kind['name'], 'profile': profile['id'],
                                    'profile_name': profile['name'], 'sheet': sheet['name'],
                                    'header_row': profile['header_row'], 'columns': profile['columns']})
            result = {'status': 'recognized' if len(matches) == 1 else 'unknown', 'match': matches[0] if len(matches) == 1 else None,
                      'encoding': shape['encoding'], 'sheets': [{'name': s['name'], 'physical_rows': s['rows']} for s in shape['sheets']],
                      'reason': '格式已登记。' if len(matches) == 1 else '此文件结构尚未支持，需要增加或更新格式识别规则。'}
        except ImportError as exc:
            result = {'status': 'invalid', 'match': None, 'sheets': [], 'encoding': None, 'reason': str(exc)}
        result.update({'filename': filename, 'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                       'recorded_at': stamp(), 'catalog_version': self.catalog['version'], 'execution_available': False})
        # Persist eligibility and settings version from the same serialized transaction.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if result['match']:
                row = db.execute('SELECT enabled,version FROM settings WHERE type_id=?', (result['match']['type_id'],)).fetchone()
                result['enabled_at_check'] = bool(row['enabled']) if row else True
                result['settings_version'] = row['version'] if row else 0
            else:
                result['enabled_at_check'] = False
            db.execute('INSERT INTO checks(mode,filename,sha256,recorded_at,result) VALUES(?,?,?,?,?)',
                       (mode, filename, result['sha256'], result['recorded_at'], packed(result)))
            result['id'] = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        return self.current(result)

    def current(self, result, states=None):
        states = states if states is not None else {t['id']: t for t in self.metadata()['types']}
        match = result.get('match')
        current = states.get(match['type_id']) if match else None
        result['currently_enabled'] = bool(current and current['enabled'])
        result['requires_recheck'] = bool(match and (result['catalog_version'] != self.catalog['version'] or
                                                    not current or match['profile'] not in {p['id'] for p in current['profiles']}))
        result['format_eligible'] = bool(result['status'] == 'recognized' and current and current['enabled'] and not result['requires_recheck'])
        result['can_execute'] = False
        result['label'] = ('已停用 · 不可导入' if not result['currently_enabled'] else '规则已更新 · 请重新检查' if result['requires_recheck'] else '已登记 · 可用于导入') if match else ('无法检查' if result['status'] == 'invalid' else '需要新增支持')
        return result

    def history(self, mode='live', offset=0):
        mode = self.mode(mode)
        try:
            offset = int(offset)
        except (ValueError, TypeError):
            raise ImportError('分页参数无效。')
        if not 0 <= offset <= 1000000:
            raise ImportError('分页参数超出范围。')
        states = {t['id']: t for t in self.metadata()['types']}
        with self.connect() as db:
            rows = db.execute('SELECT id,result FROM checks WHERE mode=? ORDER BY id DESC LIMIT 20 OFFSET ?', (mode, offset)).fetchall()
            total = db.execute('SELECT count(*) FROM checks WHERE mode=?', (mode,)).fetchone()[0]
        return {'rows': [self.current({**json.loads(r['result']), 'id': r['id']}, states) for r in rows], 'total': total, 'offset': offset, 'limit': 20}

    def events(self):
        with self.connect() as db:
            return {'rows': [dict(r) for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 50')]}
