"""No-apply routing and temporary SQLite split; no PostgreSQL operations."""
from pathlib import Path
from contextlib import closing
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from unittest.mock import patch
import json
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'app')]
import relocate_database as relocation


class RelocationSafety(TestCase):
    def test_default_only_calls_preview(self):
        with TemporaryDirectory() as folder:
            output=Path(folder)/'plan.json'
            with patch.object(sys,'argv',['relocate_database.py','--out',str(output)]),patch.object(relocation,'inspect',return_value={'executed':False}),patch.object(relocation,'restore') as restore,patch.object(relocation,'cutover') as cutover,patch.object(relocation,'finalize') as finalize:
                relocation.main()
                self.assertEqual(json.loads(output.read_text())['executed'],False)
                restore.assert_not_called();cutover.assert_not_called();finalize.assert_not_called()
    def test_phase_without_apply_refused(self):
        with patch.object(sys,'argv',['relocate_database.py','--phase','restore']),patch.object(relocation,'inspect') as inspect:
            with self.assertRaises(RuntimeError):relocation.main()
            inspect.assert_not_called()
    def test_apply_requires_explicit_phase_and_plan(self):
        for arguments in (['--apply'],['--apply','--phase','restore']):
            with patch.object(sys,'argv',['relocate_database.py',*arguments]),patch.object(relocation,'restore') as restore:
                with self.assertRaises(RuntimeError):relocation.main()
                restore.assert_not_called()
    def test_cleanup_manifest_cannot_escape_project(self):
        for entry in ({'path':str(ROOT.parent/'other'),'relative':'../other'},{'path':str(ROOT/'config.json'),'relative':'tools/other.json'}):
            with self.assertRaises(RuntimeError):relocation.source_file(entry)
    def test_history_split_preserves_ids_and_source(self):
        with TemporaryDirectory() as folder:
            original=Path(folder)/'source.sqlite3';target=Path(folder)/'copy.sqlite3'
            with closing(sqlite3.connect(original)) as connection:
                connection.executescript("CREATE TABLE checks(id INTEGER PRIMARY KEY,mode TEXT,result TEXT);CREATE TABLE settings(type_id TEXT PRIMARY KEY,version INT);CREATE TABLE events(id INTEGER PRIMARY KEY,version INT);INSERT INTO checks VALUES(1,'live','正式'),(2,'demo','演示'),(5,'live','');INSERT INTO settings VALUES('x',2);INSERT INTO events VALUES(8,2);")
            before=relocation.digest(original)
            expected=relocation.history_signature(original,'live')
            relocation.copy_history(original,target,'live')
            with closing(sqlite3.connect(target)) as connection:
                self.assertEqual(connection.execute('SELECT id FROM checks ORDER BY id').fetchall(),[(1,),(5,)])
            self.assertEqual(relocation.digest(original),before)
            self.assertEqual(relocation.history_signature(target,'live'),expected)


if __name__=='__main__':main(verbosity=2)
