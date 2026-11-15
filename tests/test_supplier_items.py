"""Narrow supplier migration/FK/template test in one random isolated database."""
from pathlib import Path
import csv
import io
import json
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'app'))
from easyerp import ERP, DATABASE_CONTEXT, ident as I, literal as L
from migrate_supplier_items import migrate, prior_versions
from entry import ManualEntry
from standard_templates import StandardTemplates
from identifiers import RULES


def main():
    original = ERP(mode='demo')
    name = 'easyerp_v02_test_supplier_' + uuid.uuid4().hex[:12]
    assert name.startswith('easyerp_v02_test_supplier_')
    config = {**original.c, 'database_sources': {'demo': {**original.c, 'database': name}}}
    with tempfile.TemporaryDirectory() as folder:
        erp = ERP(mode='demo', config=config, runtime_root=folder)
        created = False
        try:
            original.sql('CREATE DATABASE ' + I(name) + ' TEMPLATE template0 ENCODING \'UTF8\'', db='postgres', role='easyerp_admin')
            created = True
            manifest, digest = erp.verify_files()
            prior = sorted(prior_versions(manifest))[0].split('|')
            sql = '''CREATE SCHEMA production; CREATE SCHEMA rd; CREATE SCHEMA erp_ops;
CREATE TABLE production."供应商档案表" ("供应商ID" text PRIMARY KEY,"名称" text NOT NULL);
CREATE TABLE rd."物料主数据表" ("MID" text PRIMARY KEY,"名称" text NOT NULL);
CREATE TABLE erp_ops.schema_version (version text PRIMARY KEY,source_sha256 text,build_sha256 text);
CREATE TABLE erp_ops.schema_upgrade_log (upgrade_id text,from_build text,to_build text,source_sha256 text);
INSERT INTO production."供应商档案表" VALUES ('SUP001','真实ID夹具供应商甲'),('SUP002','真实ID夹具供应商乙');
INSERT INTO rd."物料主数据表" VALUES ('M001','物料甲'),('M002','物料乙');
'''
            sql += f"INSERT INTO erp_ops.schema_version VALUES ('0.2.0',{L(prior[0])},{L(prior[1])});\n"
            sql += (ROOT / 'db/app/business_ids.sql').read_text(encoding='utf-8')
            sql += (ROOT / 'db/app/entry_schema.sql').read_text(encoding='utf-8')
            for key in ['production.供应商档案表', 'rd.物料主数据表']:
                rule = RULES[key]
                sql += 'INSERT INTO erp_ops.business_id_rules(table_key,pk_column,prefix,department) VALUES (' + ','.join(L(value) for value in [key, rule['pk'], rule['prefix'], rule['department']]) + ');\n'
            sql += 'GRANT USAGE ON SCHEMA production,rd,erp_ops TO easyerp_app,easyerp_read; GRANT SELECT ON ALL TABLES IN SCHEMA production,rd TO easyerp_app,easyerp_read; GRANT INSERT,UPDATE ON ALL TABLES IN SCHEMA production,rd TO easyerp_app;'
            erp.sql(sql, db=name, role='easyerp_admin')
            assert migrate(erp, name)['status'] == 'preview'
            result = migrate(erp, name, apply=True)
            assert result['business_facts_preserved'] and result['existing_references_preserved']
            assert migrate(erp, name)['status'] == 'already applied'
            context = DATABASE_CONTEXT.set({'mode': 'demo', 'config': config})
            try:
                entry = ManualEntry({'mode': 'demo'})
                catalog = entry.catalog()
                child = catalog['production.供应物品明细表']
                assert catalog['production.供应商档案表']['children']['object'] == child['key']
                assert next(c for c in child['columns'] if c['name'] == 'MID')['reference']['target'] == 'rd.物料主数据表'
                choices = entry.options(child['key'], 'MID')['rows']
                assert {r['value'] for r in choices} == {'M001', 'M002'}
                assert all(r['label'].startswith('物料') for r in choices)
                for supplier, material in [('SUP001', 'M001'), ('SUP001', 'M002'), ('SUP002', 'M001')]:
                    entry.save({'request_id': uuid.uuid4().hex, 'object': child['key'], 'values': {'供应商ID': supplier, 'MID': material}})
                parent = entry.save({'request_id': uuid.uuid4().hex, 'object': 'production.供应商档案表', 'values': {'名称': '主明细夹具'}, 'children': [
                    {'object': child['key'], 'values': {'MID': 'M001'}}, {'object': child['key'], 'values': {'MID': 'M002'}}]})
                assert len(parent['records']) == 3
                from data import Data
                summary = Data({'mode': 'demo'}).explore('production.供应商档案表', {'objects': list(catalog.values())})
                summary_row = next(row for row in summary['rows'] if row['供应商ID'] == 'SUP001')
                assert {row['id'] for row in summary_row['_供应物品']} == {'M001', 'M002'}
                assert summary_row['供应的物品'] == '物料甲、物料乙'
                record = entry.record('production.供应商档案表', 'SUP001')
                assert len(record['children']) == 2
                assert all(r['id'].startswith('SPM') for r in record['children'])
                for supplier, material in [('SUP001', 'M001'), ('SUP001', 'M999'), ('SUP999', 'M001')]:
                    failed = erp.sql(f'INSERT INTO production."供应物品明细表" VALUES (\'SPMZZZ\',{L(supplier)},{L(material)})', db=name, role='easyerp_app', ok=False)
                    assert failed.returncode != 0
                assert int(erp.sql('SELECT count(*) FROM production."供应物品明细表"', db=name, role='easyerp_read').stdout.strip()) == 5
                template, _ = StandardTemplates({'mode': 'demo'}).download(child['key'])
                assert list(csv.reader(io.StringIO(template.decode('utf-8-sig')))) == [['供应关系ID', '供应商ID', 'MID']]
            finally:
                DATABASE_CONTEXT.reset(context)
            print(json.dumps({'status': 'PASS', 'database': name, 'migration': True, 'many_to_many': True, 'invalid_duplicate_rejected': True, 'options_details_template': True}, ensure_ascii=False))
        finally:
            if created:
                original.sql('DROP DATABASE ' + I(name) + ' WITH (FORCE)', db='postgres', role='easyerp_admin')


if __name__ == '__main__':
    main()
