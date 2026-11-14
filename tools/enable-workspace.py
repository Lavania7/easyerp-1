"""Backed-up additive upgrade and provenance-preserving legacy workflow handoff."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

from easyerp import ERP, literal as L, ident as I

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from workspace import Workspace
from data import Data
from identifiers import Identifiers, WORKSPACE_PREFIXES, base36, workspace_identity

VERSION = "workspace-v1"


def signature(erp, db):
    # New nullable columns do not alter any existing business fact.
    tables = json.loads(
        erp.sql(
            """SELECT json_agg(n.nspname||'.'||c.relname ORDER BY 1)
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname IN ('finance','legal','production','rd','sales','analysis') AND c.relkind='r'""",
            db=db,
            role="easyerp_read",
        ).stdout
    )
    result = {}
    for key in tables:
        schema, name = key.split(".", 1)
        result[key] = erp.sql(
            f"SELECT count(*)||':'||md5(coalesce(string_agg(v,E'\\n' ORDER BY v),'')) FROM (SELECT jsonb_strip_nulls(to_jsonb(t))::text AS v FROM {I(schema)}.{I(name)} t) x",
            db=db,
            role="easyerp_read",
        ).stdout.strip()
    return result


def handoff(mode):
    source = Data({"mode": mode})
    catalog = source.catalog()
    tables = {(o["schema"], o["name"]): o for o in catalog["objects"]}
    now = datetime.now(timezone.utc).isoformat()
    converted = []
    for schema in ("finance", "legal", "production", "rd", "sales", "analysis"):
        for name in (
            "工单草稿表",
            "意见与规划总表",
            "意见采纳表",
            "意见执行表",
            "整改跟踪表",
            "履约提示表",
            "合规自查表",
            "整改处理表",
        ):
            obj = tables.get((schema, name))
            if not obj:
                continue
            # Each adoption owns its executions, rather than becoming two editable events.
            if name == "整改处理表":
                # A correction with a legal tracking row is attached there below.
                rows = source.rows(
                    f'SELECT * FROM {I(schema)}.{I(name)} r WHERE NOT EXISTS (SELECT 1 FROM legal."整改跟踪表" t WHERE t."整改事项ID"=r."整改事项ID")'
                )
            elif name == "意见执行表":
                rows = source.rows(
                    f'SELECT * FROM {I(schema)}.{I(name)} r WHERE NOT EXISTS (SELECT 1 FROM {I(schema)}."意见采纳表" t WHERE t."采纳记录ID"=r."采纳记录ID")'
                )
            else:
                rows = source.rows(f"SELECT * FROM {I(schema)}.{I(name)}")
            for row in rows:
                related = []
                if name == "意见采纳表" and (schema, "意见执行表") in tables:
                    related = source.rows(
                        f'SELECT * FROM {I(schema)}."意见执行表" WHERE "采纳记录ID"={L(row[obj["pk"]])}'
                    )
                if name == "整改跟踪表":
                    for dept in ("finance", "legal", "production", "rd", "sales", "analysis"):
                        if (dept, "整改处理表") in tables:
                            related += source.rows(
                                f'SELECT {L(dept + ".整改处理表")} AS "来源表",r.* FROM {I(dept)}."整改处理表" r WHERE "整改事项ID"={L(row[obj["pk"]])}'
                            )
                kind = "plan" if name in ("工单草稿表", "意见与规划总表") else "workflow"
                key = (
                    "legacy_"
                    + hashlib.sha256(
                        (schema + "." + name + ":" + row[obj["pk"]]).encode()
                    ).hexdigest()[:24]
                )
                title = next(
                    (
                        row.get(field)
                        for field in (
                            "计划说明",
                            "问题",
                            "整改意见",
                            "履约节点",
                            "主题",
                            "处理内容",
                        )
                        if row.get(field)
                    ),
                    name + " " + row[obj["pk"]],
                )
                # Legacy states stay verbatim as evidence; migration grants no approval.
                values = {
                    "title": str(title)[:200],
                    "department": row.get("责任部门") or schema,
                    "owner": row.get("负责人ID") or row.get("责任人ID") or "",
                    "description": "历史记录接续；原状态及字段见来源快照。",
                    "links": schema + "." + name + ":" + row[obj["pk"]],
                    "type": name.removesuffix("表"),
                }
                if row.get("期限"):
                    values["due"] = row["期限"]
                legacy_status = row.get("状态") or row.get("关闭状态") or ""
                status = "待接续"
                if legacy_status in {"已关闭", "已取消", "已履约", "已确认", "已复盘"}:
                    status = "历史归档"
                elif name == "工单草稿表":
                    status = "已发布" if legacy_status == "已下达" else "草稿"
                elif kind == "plan":
                    status = "草稿" if legacy_status == "待决定" else "已发布"
                values["description"] += " 原状态：" + (legacy_status or "来源未规定统一状态")
                item = {
                    "id": key,
                    "kind": kind,
                    "values": values,
                    "status": status,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                    "history": [
                        {
                            "at": now,
                            "from": None,
                            "to": status,
                            "note": "历史记录接续，未自动认定审核或完成。",
                            "before": None,
                            "after": values.copy(),
                        }
                    ],
                    "legacy": {
                        "object": schema + "." + name,
                        "id": row[obj["pk"]],
                        "values": row,
                        "related": related,
                    },
                }
                converted.append(item)
    ws = Workspace(mode)
    with ws.locked():
        data = ws.read()
        added = 0
        ids = Identifiers(source)
        existing = {
            (i["legacy"]["object"], ids.resolve(i["legacy"]["object"], i["legacy"]["id"]))
            for i in data["items"].values()
            if i.get("legacy")
        }
        for item in converted:
            origin = (item["legacy"]["object"], item["legacy"]["id"])
            if origin in existing:
                continue
            kind = item["kind"]
            prefix = WORKSPACE_PREFIXES[kind]
            counters = data.setdefault("id_counters", {})
            number = (
                max(
                    [
                        int(k[len(prefix) :], 36)
                        for k in data["items"]
                        if k.startswith(prefix)
                        and all(
                            c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in k[len(prefix) :]
                        )
                    ]
                    + [counters.get(kind, 0)]
                )
                + 1
            )
            item["id"] = prefix + base36(number)
            counters[kind] = number
            item.update(
                {
                    k: v
                    for k, v in workspace_identity(
                        kind, item["id"], item["values"].get("department", "")
                    ).items()
                    if k != "short_id"
                }
            )
            data["items"][item["id"]] = item
            existing.add(origin)
            added += 1
        if added:
            ws.write(data)
    return {"legacy_records": len(converted), "new_handoffs": added}


def install():
    erp = ERP()
    actual = erp.sql("SHOW data_directory", db="postgres", role="easyerp_admin").stdout.strip()
    if Path(actual).resolve() != (ROOT / "var/pgdata").resolve():
        raise RuntimeError("Unexpected PostgreSQL cluster")
    sql = (ROOT / "db/app/workspace_schema.sql").read_text(encoding="utf-8")
    digest = hashlib.sha256(sql.encode()).hexdigest()
    results = []
    for mode in ("live", "demo"):
        db = erp.c["database"] + ("_ui_demo" if mode == "demo" else "")
        exists = erp.sql(
            f"SELECT 1 FROM pg_database WHERE datname={L(db)}", db="postgres", role="easyerp_admin"
        ).stdout.strip()
        if exists != "1":
            continue
        installed = (
            erp.sql(
                "SELECT to_regclass('erp_ops.frontend_workspace_migration') IS NOT NULL",
                db=db,
                role="easyerp_read",
            ).stdout.strip()
            == "t"
        )
        previous = (
            erp.sql(
                f"SELECT sql_sha256 FROM erp_ops.frontend_workspace_migration WHERE version={L(VERSION)}",
                db=db,
                role="easyerp_read",
            ).stdout.strip()
            if installed
            else ""
        )
        if previous and previous != digest:
            raise RuntimeError("Installed workspace migration differs from source")
        before = signature(erp, db)
        if not previous:
            backup = erp.backup(db=db)
            erp.sql(
                "BEGIN;\n"
                + sql
                + f"\nINSERT INTO erp_ops.frontend_workspace_migration(version,sql_sha256,backup_file) VALUES ({L(VERSION)},{L(digest)},{L(str(backup))});\nCOMMIT;",
                db=db,
                role="easyerp_admin",
            )
        else:
            backup = erp.sql(
                f"SELECT backup_file FROM erp_ops.frontend_workspace_migration WHERE version={L(VERSION)}",
                db=db,
                role="easyerp_read",
            ).stdout.strip()
        if signature(erp, db) != before:
            raise RuntimeError("Existing business facts changed during upgrade")
        results.append(
            {
                "mode": mode,
                "database": db,
                "backup": str(backup),
                "business_facts_unchanged": True,
                **handoff(mode),
            }
        )
    report = {
        "version": VERSION,
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    (ROOT / "reports/workspace-migration.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    install()
