"""Enable the narrowly scoped, audited CSV missing-value support in existing databases."""

from pathlib import Path
from easyerp import ERP

if __name__ == "__main__":
    e = ERP()
    e.verify_files()
    if (
        Path(e.sql("SELECT current_setting('data_directory')").stdout.strip()).resolve()
        != e.data.resolve()
    ):
        raise RuntimeError("Unexpected PostgreSQL cluster")
    source = Path(__file__).resolve().parents[1] / "db/app/csv_import_schema.sql"
    for database in (e.c["database"], e.c["database"] + "_ui_demo"):
        e.sql("BEGIN;\n" + source.read_text(encoding="utf-8") + "\nCOMMIT;", db=database)
        print("CSV missing-value support ready: " + database)
