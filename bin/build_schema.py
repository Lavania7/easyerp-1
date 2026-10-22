"""Extract the specification verbatim; never rewrite readme.md."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def build():
    source = ROOT / 'readme.md'
    raw = source.read_bytes()
    text = raw.decode('utf-8-sig')
    groups = [[], [], [], []]
    entries = []
    for match in re.finditer(r'\x60{3}sql\s*\n(.*?)\x60{3}', text, re.S):
        sql = match[1]
        line = text.count('\n', 0, match.start()) + 2
        group = (0 if sql.startswith('CREATE SCHEMA') else
                 1 if sql.startswith('CREATE TABLE') else
                 2 if sql.startswith('ALTER TABLE') else
                 3 if sql.startswith('CREATE VIEW') else None)
        if group is None:
            raise ValueError(f'Unknown SQL block at line {line}')
        groups[group].append(f'-- readme.md:{line}\n{sql.rstrip()}\n')
        entries.append({'line': line, 'type': ['schema','table','foreign_key','view'][group],
                        'sha256': hashlib.sha256(sql.encode()).hexdigest()})
    names = ['001_schemas.sql','002_tables.sql','003_foreign_keys.sql','004_views.sql']
    files = {}
    for name, sql in zip(names, groups):
        payload = ('-- Generated from readme.md. Run bin/build_schema.py to regenerate.\n' +
                   '\n'.join(sql)).encode('utf-8')
        (ROOT / 'db' / name).write_bytes(payload)
    all_sql = '\n'.join('\n'.join(g) for g in groups)
    counts = {'schemas': len(re.findall(r'CREATE SCHEMA ', all_sql)),
              'tables': len(re.findall(r'CREATE TABLE ', all_sql)),
              'foreign_keys': len(re.findall(r'FOREIGN KEY', all_sql)),
              'views': len(re.findall(r'CREATE VIEW ', all_sql))}
    if counts != dict(schemas=6, tables=146, foreign_keys=475, views=15):
        raise ValueError(f'Specification changed; review before deploying: {counts}')
    for file in sorted((ROOT / 'db').glob('*.sql')):
        files[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    manifest = {'version': '0.2.0', 'source': 'readme.md',
                'source_sha256': hashlib.sha256(raw).hexdigest(),
                'counts': counts, 'sql_files': files, 'blocks': entries}
    (ROOT / 'db' / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'source_sha256': manifest['source_sha256'], **counts}, ensure_ascii=False))


if __name__ == '__main__':
    build()
