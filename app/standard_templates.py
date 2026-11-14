"""Blank CSV master-table templates from the existing business SQL catalog."""

from hashlib import sha256
import csv
import io
import json
from urllib.parse import quote

from data import DEPARTMENTS, InvalidRequest
from entry import ManualEntry

FORMAT_VERSION = "easyerp-master-csv-v1"
ORDER = ("sales", "production", "rd", "finance", "legal", "analysis")


class StandardTemplates:
    def __init__(self, params=None):
        # The entry catalog reads pg_catalog with the existing read-only role.
        # It contains no business records and excludes views and erp_ops tables.
        self.entry = ManualEntry({"mode": (params or {}).get("mode", "live")})

    def catalog(self):
        return self.entry.catalog()

    @staticmethod
    def describe(obj):
        columns = []
        for source in obj["columns"]:
            reference = source.get("reference")
            columns.append(
                {
                    "name": source["name"],
                    "type": source["type"],
                    "required": source["required"],
                    "primary": source["name"] == obj["pk"],
                    "automatic": source.get("automatic", False),
                    "options": source.get("options", []),
                    "reference": {"table": reference["target"], "field": reference["target_field"]}
                    if reference
                    else None,
                }
            )
        signature = sha256(
            json.dumps(columns, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "key": obj["key"],
            "schema": obj["schema"],
            "name": obj["name"],
            "department": DEPARTMENTS[obj["schema"]],
            "pk": obj["pk"],
            "columns": columns,
            "rules": obj.get("rules", []),
            "filename": obj["key"] + ".csv",
            "signature": signature,
        }

    def metadata(self):
        objects = [
            self.describe(obj)
            for obj in self.catalog().values()
            if obj["schema"] in DEPARTMENTS
            and not obj.get("retired")
            and obj.get("standalone", True)
        ]
        objects.sort(key=lambda obj: (ORDER.index(obj["schema"]), obj["name"]))
        return {
            "mode": self.entry.mode,
            "format": FORMAT_VERSION,
            "encoding": "UTF-8 with BOM",
            "delimiter": ",",
            "departments": [
                {
                    "id": key,
                    "name": DEPARTMENTS[key],
                    "count": sum(obj["schema"] == key for obj in objects),
                }
                for key in ORDER
            ],
            "objects": objects,
        }

    def download(self, key):
        if not isinstance(key, str) or key not in self.catalog():
            raise InvalidRequest("请选择现有的业务主录表。")
        obj = self.catalog()[key]
        if (
            obj["schema"] not in DEPARTMENTS
            or obj.get("retired")
            or not obj.get("standalone", True)
        ):
            raise InvalidRequest("请选择现有的业务主录表。")
        description = self.describe(obj)
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        # No notes, annotations, sample data or filler rows enter the CSV.
        writer.writerow([column["name"] for column in obj["columns"]])
        body = stream.getvalue().encode("utf-8-sig")
        return body, {
            "Content-Disposition": 'attachment; filename="'
            + obj["schema"]
            + "-master.csv\"; filename*=UTF-8''"
            + quote(description["filename"], safe=""),
            "X-Template-Format": FORMAT_VERSION,
            "X-Template-Signature": description["signature"],
            "X-Template-Column-Count": str(len(obj["columns"])),
        }
