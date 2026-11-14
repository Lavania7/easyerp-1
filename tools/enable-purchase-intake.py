"""Add optional original-order fields after backup; preserve every existing fact."""

from pathlib import Path
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from easyerp import ERP, literal as L

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "workspace_upgrade", ROOT / "tools/enable-workspace.py"
)
upgrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrade)

if __name__ == "__main__":
    erp = ERP()
    actual = erp.sql("SHOW data_directory", db="postgres", role="easyerp_admin").stdout.strip()
    if Path(actual).resolve() != (ROOT / "var/pgdata").resolve():
        raise RuntimeError("Unexpected PostgreSQL cluster")
    source = (ROOT / "db/app/purchase_intake_schema.sql").read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode()).hexdigest()
    version = "purchase-intake-v1"
    results = []
    for mode in ("live", "demo"):
        db = erp.c["database"] + ("_ui_demo" if mode == "demo" else "")
        previous = erp.sql(
            f"SELECT sql_sha256 FROM erp_ops.frontend_workspace_migration WHERE version={L(version)}",
            db=db,
            role="easyerp_read",
        ).stdout.strip()
        if previous and previous != digest:
            raise RuntimeError("Purchase migration differs from installed source")
        if previous:
            results.append({"database": db, "status": "already installed"})
            continue
        before = upgrade.signature(erp, db)
        backup = erp.backup(db=db)
        erp.sql(
            "BEGIN;\n"
            + source
            + f"\nINSERT INTO erp_ops.frontend_workspace_migration(version,sql_sha256,backup_file) VALUES ({L(version)},{L(digest)},{L(str(backup))});\nCOMMIT;",
            db=db,
            role="easyerp_admin",
        )
        if upgrade.signature(erp, db) != before:
            raise RuntimeError("Existing business facts changed")
        results.append({"database": db, "backup": str(backup), "business_facts_unchanged": True})
    report = {
        "version": version,
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    (ROOT / "reports/purchase-intake-migration.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
