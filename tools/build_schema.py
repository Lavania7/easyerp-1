"""Extract RST SQL blocks; retain original SQL bytes and source-line markers."""

from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def sql_blocks(text):
    if not re.search(r"^\.\. sql-source-newline: CRLF$", text, re.M):
        raise ValueError("Missing explicit historical SQL newline format")
    pattern = r"^\.\. sql-source-line: (\d+)\n\n\.\. code-block:: sql\n\n((?:   [^\n]*\n)*)"
    matches = list(re.finditer(pattern, text, re.M))
    if len(matches) != len(re.findall(r"^\.\. code-block:: sql\s*$", text, re.M)):
        raise ValueError("Each SQL block must have a historical sql-source-line marker")
    for match in matches:
        sql = "".join(line[3:] for line in match[2].splitlines(keepends=True)).replace("\n", "\r\n")
        yield int(match[1]), text.count("\n", 0, match.start()) + 5, sql


def build():
    source = ROOT / "doc/sql-specification.rst"
    raw = source.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    manifest_path = ROOT / "db/manifest.json"
    previous = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    groups = [[], [], []]
    entries = []
    for line, rst_line, sql in sql_blocks(text):
        group = (
            0
            if sql.startswith("CREATE SCHEMA")
            else 1
            if sql.startswith("CREATE TABLE")
            else 2
            if sql.startswith("ALTER TABLE")
            else None
        )
        if group is None:
            raise ValueError(f"Unknown SQL block at RST line {rst_line}")
        groups[group].append(f"-- readme.md:{line}\n{sql.rstrip()}\n")
        entries.append(
            {
                "line": line,
                "source_line": rst_line,
                "type": ["schema", "table", "foreign_key"][group],
                "sha256": hashlib.sha256(sql.encode()).hexdigest(),
            }
        )
    all_sql = "\n".join("\n".join(group) for group in groups)
    counts = {
        "schemas": len(re.findall(r"CREATE SCHEMA ", all_sql)),
        "tables": len(re.findall(r"CREATE TABLE ", all_sql)),
        "foreign_keys": len(re.findall(r"FOREIGN KEY", all_sql)),
        "views": len(re.findall(r"CREATE VIEW ", all_sql)),
    }
    if counts != dict(schemas=6, tables=147, foreign_keys=477, views=0):
        raise ValueError(f"Specification changed; review before deploying: {counts}")
    for name, group in zip(("001_schemas.sql", "002_tables.sql", "003_foreign_keys.sql"), groups):
        payload = (
            "-- Generated from readme.md. Run bin/build_schema.py to regenerate.\n"
            + "\n".join(group)
        ).encode("utf-8")
        (ROOT / "db" / name).write_bytes(payload)
    files = {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted((ROOT / "db").glob("*.sql"))
    }
    compatible = []
    # A documentation change reuses an installed version only if ALL SQL files match.
    # SQL changes discard these aliases and still require the existing migration path.
    if previous.get("sql_files") == files:
        compatible = previous.get("compatible_sources", []) + [
            {
                "source_sha256": previous["source_sha256"],
                "build_sha256": hashlib.sha256(
                    json.dumps(files, sort_keys=True).encode()
                ).hexdigest(),
            }
        ]
    source_hash = hashlib.sha256(raw).hexdigest()
    compatible = [
        dict(pair)
        for pair in {
            tuple(sorted(item.items()))
            for item in compatible
            if item["source_sha256"] != source_hash
        }
    ]
    compatible.sort(key=lambda item: item["source_sha256"])
    manifest = {
        "version": "0.2.0",
        "source": "doc/sql-specification.rst",
        "source_format": "rst",
        "source_sql_newlines": "CRLF",
        "source_marker": "readme.md",
        "source_sha256": source_hash,
        "counts": counts,
        "sql_files": files,
        "blocks": entries,
        "compatible_sources": compatible,
        **({"supplier_profile_upgrade_from": previous["supplier_profile_upgrade_from"]}
           if "supplier_profile_upgrade_from" in previous else {}),
        **({"unit_profile_upgrade_from": previous["unit_profile_upgrade_from"]}
           if "unit_profile_upgrade_from" in previous else {}),
        "finance_profile_upgrade_from": previous.get(
            "finance_profile_upgrade_from",
            {
                "source_sha256s": sorted({previous["source_sha256"],
                    *(pair["source_sha256"] for pair in previous.get("compatible_sources", []))}),
                "sql_files": previous["sql_files"],
            },
        ),
        "supplier_items_upgrade_from": previous.get(
            "supplier_items_upgrade_from",
            {
                "source_sha256s": sorted({previous["source_sha256"],
                    *(pair["source_sha256"] for pair in previous.get("compatible_sources", []))}),
                "sql_files": previous["sql_files"],
            },
        ),
        "migration_from": previous.get(
            "migration_from",
            {
                "source_sha256": "0cb98ec46569d2ee9b746873d495b2b3c251e44077d38954c206ac49544fe0a4",
                "build_sha256": "86e2875a509f0dc0f4bd3fa8333f7df2042e7dcc838f71e5f9a792c2c99f9937",
            },
        ),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"source": manifest["source"], "source_sha256": source_hash, **counts},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    build()
