"""Install additive manual-entry audit support in the two existing local databases."""

from pathlib import Path
from easyerp import ERP

if __name__ == "__main__":
    e = ERP()
    source = Path(__file__).resolve().parents[1] / "db" / "app" / "entry_schema.sql"
    for db in [e.c["database"], e.c["database"] + "_ui_demo"]:
        e.sql("BEGIN;\n" + source.read_text(encoding="utf-8") + "\nCOMMIT;", db=db)
        print("Manual-entry support ready: " + db)
