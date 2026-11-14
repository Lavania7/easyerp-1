"""Short business identifiers; transport request IDs remain opaque and unchanged."""

from pathlib import Path
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from hashlib import sha256
from easyerp import literal as L

RULES = json.loads(Path(__file__).with_name("id_rules.json").read_text(encoding="utf-8"))
WORKSPACE_PREFIXES = {"plan": "PLN", "workflow": "WF", "report": "AUD"}
DEPARTMENTS = {
    "analysis": "ANA",
    "finance": "FIN",
    "legal": "LEG",
    "production": "PRD",
    "rd": "RND",
    "sales": "SAL",
    "分析": "ANA",
    "财务": "FIN",
    "法务": "LEG",
    "生产": "PRD",
    "采购与生产": "PRD",
    "研发": "RND",
    "销售": "SAL",
}


def base36(number):
    result = ""
    while number:
        number, digit = divmod(number, 36)
        result = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[digit] + result
    return (result or "0").zfill(3)


def issued_date():
    try:
        zone = ZoneInfo("Europe/Berlin")
    except ZoneInfoNotFoundError:
        from easyerp import CONFIG

        config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
        path = Path(config["postgres_bin"]).parent / "share/timezone/Europe/Berlin"
        with path.open("rb") as handle:
            zone = ZoneInfo.from_file(handle, key="Europe/Berlin")
    return datetime.now(timezone.utc).astimezone(zone).date().isoformat()


def identity(department, prefix, short_id, day=None):
    day = day or issued_date()
    number = int(short_id[len(prefix) :], 36)
    long_id = department + "-" + prefix + "-" + day.replace("-", "") + "-" + str(number).zfill(3)
    return {
        "short_id": short_id,
        "long_id": long_id,
        "sha256": sha256(long_id.encode("utf-8")).hexdigest(),
        "issued_on": day,
    }


def workspace_identity(kind, short_id, department="", day=None):
    # WS is the workspace namespace when no owning business department is recorded.
    return identity(DEPARTMENTS.get(department, "WS"), WORKSPACE_PREFIXES[kind], short_id, day)


def valid(key, value):
    prefix = RULES[key]["prefix"]
    if not isinstance(value, str) or not re.fullmatch(prefix + r"[0-9A-Z]{3,10}", value):
        return False
    number = int(value[len(prefix) :], 36)
    return 0 < number < 10**15 and value == prefix + base36(number)


class Identifiers:
    def __init__(self, data):
        self.data = data
        self.aliases = {}

    def resolve(self, key, value):
        if not isinstance(value, str) or key not in RULES:
            return value
        if key not in self.aliases:
            rows = self.data.rows(
                "SELECT old_id,new_id FROM erp_ops.business_id_aliases WHERE table_key=" + L(key)
            )
            self.aliases[key] = {r["old_id"]: r["new_id"] for r in rows}
        return self.aliases[key].get(value, value)

    def values(self, obj, values):
        result = dict(values)
        for col in obj["columns"]:
            if col["name"] not in result or not result[col["name"]]:
                continue
            target = (
                obj["key"]
                if col["name"] == obj["pk"]
                else (col.get("reference") or {}).get("target")
            )
            if target:
                result[col["name"]] = self.resolve(target, result[col["name"]])
        return result

    def allocate(self, key, allocation_keys):
        if not allocation_keys:
            return []
        sql = (
            "SELECT erp_ops.allocate_business_ids("
            + L(key)
            + ",ARRAY["
            + ",".join(L(k) for k in allocation_keys)
            + "]::text[]);"
        )
        result = self.data.erp.sql(sql, db=self.data.db, role="easyerp_app")
        return json.loads(result.stdout.strip())

    def identity(self, key, value):
        value = self.resolve(key, value) if key else value
        where = " AND i.table_key=" + L(key) if key else ""
        found = self.data.rows(
            "SELECT i.table_key AS object,i.short_id,i.long_id,i.sha256,i.issued_on FROM erp_ops.business_record_ids i WHERE (i.short_id="
            + L(value)
            + " OR i.long_id="
            + L(value)
            + " OR i.sha256="
            + L(value)
            + ")"
            + where
        )
        result = []
        for row in found:
            rule = RULES[row["object"]]
            schema, name = row["object"].split(".", 1)
            from easyerp import ident as I

            exists = self.data.rows(
                "SELECT 1 AS found FROM "
                + I(schema)
                + "."
                + I(name)
                + " WHERE "
                + I(rule["pk"])
                + "="
                + L(row["short_id"])
            )
            if exists:
                result.append(row)
        return result
