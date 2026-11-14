"""Backed-up, reversible identity migration; never rewrites source/audit snapshots."""

from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import json
import re
import sys


def run(erp, root, db, mode, destination, apply=False, workspace_root=None):
    from easyerp import literal as L, ident as I

    assets = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(assets / "app"))
    from identifiers import base36, valid, issued_date, workspace_identity

    day = issued_date()
    rules = json.loads((assets / "app/id_rules.json").read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)

    def rows(sql):
        return json.loads(
            erp.sql(
                "BEGIN READ ONLY; SELECT coalesce(json_agg(row_to_json(q)),'[]'::json) FROM ("
                + sql
                + ") q; COMMIT;",
                db=db,
                role="easyerp_admin",
            ).stdout
        )

    assert (
        Path(rows("SELECT current_setting('data_directory') AS path")[0]["path"]).resolve()
        == (root / "var/pgdata").resolve()
    ), "Unexpected cluster"
    tables = rows(
        """SELECT n.nspname AS schema,c.relname AS name,a.attname AS pk FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=p.conkey[1] WHERE p.contype='p' AND cardinality(p.conkey)=1 AND n.nspname IN ('sales','production','rd','finance','legal','analysis') ORDER BY 1,2"""
    )
    for t in tables:
        t["key"] = t["schema"] + "." + t["name"]
        t["sql"] = I(t["schema"]) + "." + I(t["name"])
    assert {t["key"] for t in tables} == set(rules), "Registry must cover every business table"
    fks = rows(
        """SELECT p.conname,p.conrelid::regclass::text AS source,p.confrelid::regclass::text AS target,p.condeferrable,p.condeferred,pg_get_constraintdef(p.oid) AS definition,a.attname AS field,ta.attname AS target_field FROM pg_constraint p JOIN pg_namespace n ON n.oid=p.connamespace JOIN pg_class tc ON tc.oid=p.confrelid JOIN pg_namespace tn ON tn.oid=tc.relnamespace JOIN pg_attribute a ON a.attrelid=p.conrelid AND a.attnum=p.conkey[1] JOIN pg_attribute ta ON ta.attrelid=p.confrelid AND ta.attnum=p.confkey[1] WHERE p.contype='f' AND (n.nspname IN ('sales','production','rd','finance','legal','analysis') OR tn.nspname IN ('sales','production','rd','finance','legal','analysis')) AND cardinality(p.conkey)=1 ORDER BY 2,1"""
    )
    operational = {}
    for fk in fks:
        if fk["source"].replace('"', "") not in rules and fk["target"].replace('"', "") in rules:
            operational.setdefault(fk["source"], {})[fk["field"]] = fk["target"].replace('"', "")
    identifiers = rows(
        " UNION ALL ".join(
            "SELECT " + L(t["key"]) + " AS object," + I(t["pk"]) + " AS id FROM " + t["sql"]
            for t in tables
        )
    )
    mapping = []
    maximum = {}
    for t in tables:
        prefix = rules[t["key"]]["prefix"]
        ids = sorted(r["id"] for r in identifiers if r["object"] == t["key"])
        good = lambda x: valid(t["key"], x)
        number = max([int(x[len(prefix) :], 36) for x in ids if good(x)] + [0])
        for old in ids:
            if good(old):
                continue
            number += 1
            mapping.append({"object": t["key"], "old": old, "new": prefix + base36(number)})
        maximum[t["key"]] = number
    report = {
        "database": db,
        "mode": mode,
        "migration_id": "ids-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"),
        "issued_on": day,
        "short_id_scheme": "prefix-base36-min3",
        "rows": len(identifiers),
        "renamed": len(mapping),
        "foreign_keys": len(fks),
        "mapping": mapping,
        "status": "PREVIEW",
    }

    def save_report():
        (destination / "migration.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    save_report()
    if not apply:
        return report
    report["backup"] = str(erp.backup(db))
    workspace_root = workspace_root or root / "var/workspace"
    workspace_path = workspace_root / (mode + ".json")
    workspace_before = workspace_path.read_bytes() if workspace_path.exists() else None
    if workspace_before is not None:
        (destination / "workspace-before.json").write_bytes(workspace_before)
    save_report()
    batch = report["migration_id"]
    sql = [
        "BEGIN; SET LOCAL lock_timeout='8s'; SET LOCAL statement_timeout='300s';",
        (assets / "db/app/business_ids.sql").read_text(encoding="utf-8"),
    ]
    for key, rule in rules.items():
        sql.append(
            "INSERT INTO erp_ops.business_id_rules(table_key,pk_column,prefix,department) VALUES("
            + ",".join(map(L, [key, rule["pk"], rule["prefix"], rule["department"]]))
            + ") ON CONFLICT(table_key) DO UPDATE SET pk_column=excluded.pk_column,prefix=excluded.prefix,department=excluded.department;"
        )
    sql.append(
        "LOCK TABLE "
        + ",".join([t["sql"] for t in tables] + list(operational))
        + " IN ACCESS EXCLUSIVE MODE;"
    )
    # All assertions are inside the same transaction as the identifier rewrite.
    sql += [
        "CREATE TEMP TABLE id_map(object text,old_id text,new_id text,PRIMARY KEY(object,old_id),UNIQUE(object,new_id)) ON COMMIT DROP;",
        "CREATE TEMP TABLE id_before(object text,id text,data jsonb,PRIMARY KEY(object,id)) ON COMMIT DROP;",
        "CREATE TEMP TABLE id_ops_before(object text,data jsonb) ON COMMIT DROP;",
    ]
    if mapping:
        sql.append(
            "INSERT INTO id_map VALUES "
            + ",".join(
                "(" + ",".join(map(L, [r["object"], r["old"], r["new"]])) + ")" for r in mapping
            )
            + ";"
        )
    for t in tables:
        sql.append(
            "INSERT INTO id_before SELECT "
            + L(t["key"])
            + ","
            + I(t["pk"])
            + ",to_jsonb(t) FROM "
            + t["sql"]
            + " t;"
        )
    for source in operational:
        sql.append(
            "INSERT INTO id_ops_before SELECT " + L(source) + ",to_jsonb(t) FROM " + source + " t;"
        )
    # Defer only FK checks; restore the original timing after they validate.
    for fk in fks:
        sql.append(
            "ALTER TABLE "
            + fk["source"]
            + " ALTER CONSTRAINT "
            + I(fk["conname"])
            + " DEFERRABLE INITIALLY DEFERRED;"
        )
    guards = rows(
        """SELECT t.tgname,t.tgrelid::regclass::text AS object,t.tgenabled FROM pg_trigger t WHERE NOT t.tgisinternal AND t.tgname IN ('freeze_posted','guard_voucher_lines','guard_posted_account','business_id_format')"""
    )
    for g in guards:
        sql.append("ALTER TABLE " + g["object"] + " DISABLE TRIGGER " + I(g["tgname"]) + ";")
    reverse_expressions = {}
    for t in tables:
        fields = {t["pk"]: t["key"]}
        fields.update(
            {
                f["field"]: f["target"].replace('"', "")
                for f in fks
                if f["source"].replace('"', "") == t["key"]
                and f["target"].replace('"', "") in rules
            }
        )
        assignments = []
        conditions = []
        reverse = []
        for col, target in fields.items():
            source = "t." + I(col)
            lookup = "SELECT new_id FROM id_map WHERE object=" + L(target) + " AND old_id=" + source
            assignments.append(I(col) + "=coalesce((" + lookup + ")," + source + ")")
            conditions.append("EXISTS(" + lookup + ")")
            reverse.extend(
                [
                    L(col),
                    "coalesce((SELECT old_id FROM id_map WHERE object="
                    + L(target)
                    + " AND new_id="
                    + source
                    + "),"
                    + source
                    + ")",
                ]
            )
        sql.append(
            "UPDATE "
            + t["sql"]
            + " t SET "
            + ",".join(assignments)
            + " WHERE "
            + " OR ".join(conditions)
            + ";"
        )
        reverse_expressions[t["key"]] = "to_jsonb(t)||jsonb_build_object(" + ",".join(reverse) + ")"
    for source, fields in operational.items():
        assignments = []
        conditions = []
        reverse = []
        for col, target in fields.items():
            column = "t." + I(col)
            lookup = "SELECT new_id FROM id_map WHERE object=" + L(target) + " AND old_id=" + column
            assignments.append(I(col) + "=coalesce((" + lookup + ")," + column + ")")
            conditions.append("EXISTS(" + lookup + ")")
            reverse.extend(
                [
                    L(col),
                    "coalesce((SELECT old_id FROM id_map WHERE object="
                    + L(target)
                    + " AND new_id="
                    + column
                    + "),"
                    + column
                    + ")",
                ]
            )
        sql.append(
            "UPDATE "
            + source
            + " t SET "
            + ",".join(assignments)
            + " WHERE "
            + " OR ".join(conditions)
            + ";"
        )
        restored = (
            "SELECT to_jsonb(t)||jsonb_build_object("
            + ",".join(reverse)
            + ") AS data FROM "
            + source
            + " t"
        )
        original = "SELECT data FROM id_ops_before WHERE object=" + L(source)
        sql.append(
            "DO $$ BEGIN IF EXISTS(("
            + original
            + " EXCEPT ALL "
            + restored
            + ") UNION ALL ("
            + restored
            + " EXCEPT ALL "
            + original
            + ")) THEN RAISE EXCEPTION 'Operational source references changed beyond identifier mapping';END IF;END $$;"
        )
    sql.append("SET CONSTRAINTS ALL IMMEDIATE;")
    for t in tables:
        pattern = "^" + rules[t["key"]]["prefix"] + "[0-9A-Z]{3,10}$"
        sql.append(
            "DO $$ BEGIN IF EXISTS(SELECT 1 FROM "
            + t["sql"]
            + " WHERE "
            + I(t["pk"])
            + " !~ "
            + L(pattern)
            + ") THEN RAISE EXCEPTION 'Invalid business ID after migration'; END IF; END $$;"
        )
        original = (
            "coalesce((SELECT old_id FROM id_map WHERE object="
            + L(t["key"])
            + " AND new_id=t."
            + I(t["pk"])
            + "),t."
            + I(t["pk"])
            + ")"
        )
        sql.append(
            "DO $$ BEGIN IF EXISTS(SELECT 1 FROM "
            + t["sql"]
            + " t FULL JOIN (SELECT * FROM id_before WHERE object="
            + L(t["key"])
            + ") b ON b.id="
            + original
            + " WHERE b.data IS DISTINCT FROM ("
            + reverse_expressions[t["key"]]
            + ")) THEN RAISE EXCEPTION 'Identity migration changed record content: %',"
            + L(t["key"])
            + "; END IF; END $$;"
        )
    for fk in fks:
        timing = (
            ("DEFERRABLE INITIALLY " + ("DEFERRED" if fk["condeferred"] else "IMMEDIATE"))
            if fk["condeferrable"]
            else "NOT DEFERRABLE"
        )
        sql.append(
            "ALTER TABLE "
            + fk["source"]
            + " ALTER CONSTRAINT "
            + I(fk["conname"])
            + " "
            + timing
            + ";"
        )
    for g in guards:
        action = {"O": "ENABLE", "D": "DISABLE", "A": "ENABLE ALWAYS", "R": "ENABLE REPLICA"}[
            g["tgenabled"]
        ]
        sql.append("ALTER TABLE " + g["object"] + " " + action + " TRIGGER " + I(g["tgname"]) + ";")
    for t in tables:
        sql.append(
            "SELECT erp_ops.ensure_business_identity("
            + L(t["key"])
            + ","
            + I(t["pk"])
            + ","
            + L(day)
            + "::date) FROM "
            + t["sql"]
            + ";"
        )
        sql.append(
            "DROP TRIGGER IF EXISTS business_id_format ON "
            + t["sql"]
            + "; CREATE TRIGGER business_id_format BEFORE INSERT OR UPDATE OF "
            + I(t["pk"])
            + " ON "
            + t["sql"]
            + " FOR EACH ROW EXECUTE FUNCTION erp_ops.check_business_id();"
        )
        sql.append(
            "INSERT INTO erp_ops.business_id_counters(table_key,last_number) VALUES("
            + L(t["key"])
            + ","
            + str(maximum[t["key"]])
            + ") ON CONFLICT(table_key) DO UPDATE SET last_number=greatest(erp_ops.business_id_counters.last_number,excluded.last_number);"
        )
    sql.append(
        "INSERT INTO erp_ops.business_id_aliases(table_key,old_id,new_id,migration_id) SELECT object,old_id,new_id,"
        + L(batch)
        + " FROM id_map;"
    )
    summary = {k: v for k, v in report.items() if k not in ("mapping", "backup")}
    summary.update(status="PASS", canonical_records_unchanged=True)
    sql.append(
        "INSERT INTO erp_ops.business_id_migrations(migration_id,result) VALUES("
        + L(batch)
        + ","
        + L(json.dumps(summary, ensure_ascii=False))
        + "::jsonb); COMMIT;"
    )
    (destination / "migration.sql").write_text("\n".join(sql), encoding="utf-8")
    erp.sql("\n".join(sql), db=db, role="easyerp_admin")
    report.update(status="SQL_COMMITTED", canonical_records_unchanged=True)
    save_report()
    # Current workspace references change; immutable legacy/history snapshots stay original.
    aliases = rows("SELECT table_key,old_id,new_id FROM erp_ops.business_id_aliases")
    business_map = {(r["table_key"], r["old_id"]): r["new_id"] for r in aliases}
    workspace_count = 0
    if workspace_before is not None:
        assert workspace_path.read_bytes() == workspace_before, (
            "Workspace changed during migration; SQL committed, resume from receipt"
        )
        data = json.loads(workspace_before)
        old_data = copy.deepcopy(data)
        ws_aliases = data.setdefault("id_aliases", {})
        counters = data.setdefault("id_counters", {})
        for kind, prefix in {"plan": "PLN", "workflow": "WF", "report": "AUD"}.items():
            current = [i["id"] for i in data["items"].values() if i["kind"] == kind]
            number = max(
                [
                    int(i[len(prefix) :], 36)
                    for i in current
                    if re.fullmatch(prefix + r"[0-9A-Z]{3,10}", i)
                ]
                + [counters.get(kind, 0)]
            )
            for key in sorted(current):
                if re.fullmatch(prefix + r"[0-9A-Z]{3,10}", key):
                    continue
                number += 1
                ws_aliases[key] = prefix + base36(number)
                workspace_count += 1
            counters[kind] = number
        new_items = {}
        for old_id, item in data["items"].items():
            new_id = ws_aliases.get(old_id, old_id)
            values = item["values"]
            old_values = copy.deepcopy(values)
            if values.get("plan_id"):
                values["plan_id"] = ws_aliases.get(values["plan_id"], values["plan_id"])

            def link(match):
                obj, key = match.group(1), match.group(2)
                return obj + ":" + business_map.get((obj, key), key)

            if values.get("links"):
                values["links"] = re.sub(
                    r"((?:sales|production|finance|rd|legal|analysis)\.[^:\s]+):([^\s,;，；]+)",
                    link,
                    values["links"],
                )
            item["id"] = new_id
            if new_id != old_id or not item.get("long_id"):
                identity = workspace_identity(
                    item["kind"], new_id, values.get("department", ""), day
                )
                item.update({k: v for k, v in identity.items() if k != "short_id"})
            if new_id != old_id or old_values != values:
                item["version"] += 1
                item["history"].append(
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "from": item["status"],
                        "to": item["status"],
                        "note": "统一短编号；原始来源和既有处理历史保留。",
                        "before": old_values,
                        "after": copy.deepcopy(values),
                    }
                )
            new_items[new_id] = item
        data["items"] = new_items
        assert len(data["items"]) == len(old_data["items"])
        temp = workspace_path.with_suffix(".ids.tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(workspace_path)
    report.update(status="PASS", workspace_renamed=workspace_count)
    save_report()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mode", choices=["live", "demo"], required=True)
    parser.add_argument("--database")
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    sys.path.insert(0, str(root / "tools"))
    from easyerp import ERP

    erp = ERP()
    db = args.database or erp.c["database"] + ("_ui_demo" if args.mode == "demo" else "")
    result = run(erp, root, db, args.mode, args.out, args.apply, args.workspace_root)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "mapping"}, ensure_ascii=False, indent=2
        )
    )
