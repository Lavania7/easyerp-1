"""Document relocation regression checks, with no database connection."""
from pathlib import Path
from unittest.mock import patch
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'tools'))
import build_schema
import easyerp


class SpecificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / 'doc').mkdir()
        (self.root / 'db').mkdir()
        shutil.copyfile(PROJECT / 'doc/sql-specification.rst', self.root / 'doc/sql-specification.rst')
        for file in (PROJECT / 'db').iterdir():
            if file.suffix in ('.sql', '.json'):
                shutil.copyfile(file, self.root / 'db' / file.name)
        self.manager = object.__new__(easyerp.ERP)
        self.patch = patch.object(easyerp, 'ROOT', self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temporary.cleanup()

    def test_user_readme_can_change_without_invalidating_database_source(self):
        before = self.manager.verify_files()[1]
        (self.root / 'readme.md').write_text('Human-facing navigation can change.', encoding='utf-8')
        self.assertEqual(self.manager.verify_files()[1], before)

    def test_technical_specification_still_has_strict_hash_protection(self):
        source = self.root / 'doc/sql-specification.rst'
        source.write_bytes(source.read_bytes() + b'changed')
        with self.assertRaisesRegex(RuntimeError, '已改变'):
            self.manager.verify_files()

    def test_regeneration_keeps_all_sql_bytes_and_installed_build_digest(self):
        manifest, digest = self.manager.verify_files()
        before = {file.name: file.read_bytes() for file in (self.root / 'db').glob('*.sql')}
        with patch.object(build_schema, 'ROOT', self.root), contextlib.redirect_stdout(io.StringIO()):
            build_schema.build()
        after_manifest, after_digest = self.manager.verify_files()
        self.assertEqual(before, {file.name: file.read_bytes() for file in (self.root / 'db').glob('*.sql')})
        self.assertEqual(digest, after_digest)
        self.assertEqual(manifest['source_sha256'], after_manifest['source_sha256'])
        self.assertEqual(after_manifest['source'], 'doc/sql-specification.rst')

    def test_format_alias_requires_identical_build(self):
        manifest,digest=self.manager.verify_files()
        self.assertTrue(manifest['compatible_sources'])
        for pair in manifest['compatible_sources']:
            self.assertTrue(self.manager.version_matches(pair['source_sha256']+'|'+digest,manifest,digest))
            self.assertFalse(self.manager.version_matches(pair['source_sha256']+'|wrong-build',manifest,digest))

    def test_regeneration_drops_aliases_after_sql_change(self):
        source=self.root/'doc/sql-specification.rst'
        text=source.read_text(encoding='utf-8')
        source.write_text(text.replace('CREATE SCHEMA finance;','CREATE SCHEMA finance; -- reviewed change',1),encoding='utf-8')
        with patch.object(build_schema,'ROOT',self.root),contextlib.redirect_stdout(io.StringIO()):
            build_schema.build()
        manifest,_=self.manager.verify_files()
        self.assertEqual(manifest['compatible_sources'],[])


if __name__ == '__main__':
    unittest.main()
