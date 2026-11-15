"""Versioned file workflows and plans, isolated from business SQL and by source."""

from contextlib import contextmanager
from datetime import date, datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import uuid
import msvcrt

from data import ROOT, InvalidRequest
from easyerp import ERP
from identifiers import WORKSPACE_PREFIXES, base36, workspace_identity

LOCK = threading.RLock()
KINDS = {
    "plan": {"草稿", "已发布", "已完成", "已取消", "历史归档"},
    "workflow": {"待采纳", "待执行", "处理中", "待复核", "已完成", "已取消", "待接续", "历史归档"},
    "report": {"草稿", "已发布"},
}
TRANSITIONS = {
    "草稿": {"已发布", "已取消"},
    "已发布": {"已完成", "已取消"},
    "待采纳": {"待执行", "已取消"},
    "待执行": {"处理中", "已取消"},
    "处理中": {"待复核", "已取消"},
    "待复核": {"已完成", "处理中", "已取消"},
    "已完成": set(),
    "已取消": set(),
    "历史归档": set(),
    "待接续": {"待采纳", "待执行", "处理中", "待复核", "已完成", "已取消"},
}
FIELDS = {
    "title",
    "department",
    "owner",
    "start",
    "due",
    "description",
    "decision",
    "result",
    "evidence",
    "links",
    "plan_id",
    "month",
    "scope",
    "conclusion",
    "unresolved",
    "type",
}
DEPARTMENT_ALIASES = {
    "finance": {"finance", "财务", "财务部", "fin"},
    "legal": {"legal", "法务", "法务部", "leg"},
    "production": {"production", "生产", "生产部", "采购与库存", "生产实绩", "prd"},
    "rd": {"rd", "研发", "研发部", "r&d", "rnd"},
    "sales": {"sales", "销售", "销售部", "sal"},
    "analysis": {"analysis", "分析", "分析部", "数据分析", "分析报告", "ana"},
}
REPORT_TYPES = {"月度审计": 1, "季度审计": 3, "年度审计": 12}


def report_period(values):
    month = values.get("month", "")
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) or month.startswith("0000"):
        raise WorkspaceError("请填写有效的审计期间")
    span = REPORT_TYPES.get(values.get("type") or "月度审计")
    if span is None:
        raise WorkspaceError("请选择月度、季度或年度审计")
    first = (int(month[5:]) - 1) // span * span + 1
    return f"{month[:4]}-{first:02d}", f"{month[:4]}-{first + span - 1:02d}"


class WorkspaceError(InvalidRequest):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Workspace:
    def __init__(self, mode="live", root=None):
        if mode not in ("live", "demo"):
            raise WorkspaceError("无效数据来源")
        self.mode = mode
        self.root = Path(root) if root else ERP(mode=mode).workspace_root(mode)
        self.path = self.root / (mode + ".json")

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with LOCK, (self.root / (self.mode + ".lock")).open("a+b") as lock:
            lock.seek(0, 2)
            if not lock.tell():
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise WorkspaceError("工作流正在保存，请稍后重试。", 409)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

    def read(self):
        if not self.path.exists():
            return {"version": 1, "mode": self.mode, "items": {}, "requests": {}}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or data.get("mode") != self.mode:
            raise WorkspaceError("工作流文件版本或来源不匹配。", 503)
        return data

    def write(self, data):
        temp = self.root / (self.mode + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temp.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        finally:
            if temp.exists():
                temp.unlink()

    @staticmethod
    def public_item(item):
        value = copy.deepcopy(item)
        for key in ("long_id", "sha256", "issued_on"):
            value.pop(key, None)
        return value

    @classmethod
    def public_result(cls, result):
        return {**result, "item": cls.public_item(result["item"])}

    def identity(self, value, kind=None):
        with self.locked():
            data = self.read()
        short = data.get("id_aliases", {}).get(value, value)
        return [
            {
                "object": "workspace." + item["kind"],
                "short_id": item["id"],
                "long_id": item["long_id"],
                "sha256": item["sha256"],
                "issued_on": item["issued_on"],
            }
            for item in data["items"].values()
            if item.get("long_id")
            and (not kind or item["kind"] == kind)
            and (item["id"] == short or item["long_id"] == value or item["sha256"] == value)
        ]

    def listing(self, params):
        kind = params.get("kind", "workflow")
        if kind not in KINDS:
            raise WorkspaceError("未知工作空间类型")
        for field in ("start", "end"):
            if params.get(field):
                try:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", params[field]):
                        raise ValueError()
                    date.fromisoformat(params[field])
                except ValueError:
                    raise WorkspaceError("请选择有效的起止日期")
        if params.get("start") and params.get("end") and params["start"] > params["end"]:
            raise WorkspaceError("请选择有效的起止日期")
        search = params.get("search", "").strip().casefold()
        department = params.get("department", "")
        if department and department not in DEPARTMENT_ALIASES:
            raise WorkspaceError("未知部门")
        with self.locked():
            items = copy.deepcopy(list(self.read()["items"].values()))
        rows = []
        for item in items:
            if item["kind"] != kind:
                continue
            if kind == "report" and department and item["values"].get("department", "").strip().casefold() not in DEPARTMENT_ALIASES[department]:
                continue
            if search and search not in json.dumps(item["values"], ensure_ascii=False).casefold():
                continue
            if params.get("status") and item["status"] != params["status"]:
                continue
            # Undated plans/tasks remain visible rather than acquiring invented dates.
            day = item["values"].get("start") or item["values"].get("due")
            if kind == "report":
                first, last = report_period(item["values"])
                if params.get("start") and last < params["start"][:7]:
                    continue
                if params.get("end") and first > params["end"][:7]:
                    continue
                rows.append(item)
                continue
            if (
                day
                and params.get("start")
                and day < (params["start"][:7] if kind == "report" else params["start"])
            ):
                continue
            if (
                day
                and params.get("end")
                and day > (params["end"][:7] if kind == "report" else params["end"])
            ):
                continue
            rows.append(item)
        rows.sort(key=lambda x: x["updated_at"], reverse=True)
        return {"rows": [self.public_item(item) for item in rows], "mode": self.mode}

    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) - {
            "request_id",
            "id",
            "version",
            "kind",
            "values",
            "status",
            "note",
        }:
            raise WorkspaceError("工作空间提交格式无效")
        request = payload.get("request_id", "")
        if not isinstance(request, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request):
            raise WorkspaceError("缺少保存请求标识")
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()
        with self.locked():
            data = self.read()
            previous = data["requests"].get(request)
            if previous:
                if previous["hash"] != digest:
                    raise WorkspaceError("请求标识已用于不同内容。", 409)
                result = copy.deepcopy(previous["result"])
                result["item"]["id"] = data.get("id_aliases", {}).get(
                    result["item"]["id"], result["item"]["id"]
                )
                return self.public_result(result)
            key = payload.get("id")
            if isinstance(key, str):
                key = data.get("id_aliases", {}).get(key, key)
            if key is not None and (not isinstance(key, str) or not 1 <= len(key) <= 100):
                raise WorkspaceError("事项编号无效")
            old = data["items"].get(key) if key else None
            if key and not old:
                raise WorkspaceError("事项不存在", 404)
            if old and type(payload.get("version")) is not int:
                raise WorkspaceError("事项版本无效", 409)
            if old and payload.get("version") != old["version"]:
                raise WorkspaceError("事项已更新，请重新打开后修改。", 409)
            kind = old["kind"] if old else payload.get("kind")
            if not isinstance(kind, str) or kind not in KINDS:
                raise WorkspaceError("未知工作空间类型")
            incoming = payload.get("values", {})
            if not isinstance(incoming, dict) or set(incoming) - FIELDS:
                raise WorkspaceError("包含不支持的事项字段")
            if any(
                not isinstance(v, str) or len(v) > 20000 or "\x00" in v for v in incoming.values()
            ):
                raise WorkspaceError("事项字段必须是有效文本")
            values = {**(old["values"] if old else {}), **incoming}
            if not values.get("title", "").strip():
                raise WorkspaceError("请填写标题")
            if len(values["title"]) > 200:
                raise WorkspaceError("标题最多 200 字")
            for field in ("start", "due"):
                if values.get(field):
                    try:
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", values[field]):
                            raise ValueError()
                        date.fromisoformat(values[field])
                    except ValueError:
                        raise WorkspaceError("请填写有效日期")
            if values.get("start") and values.get("due") and values["start"] > values["due"]:
                raise WorkspaceError("截止日期不能早于开始日期")
            if kind == "report":
                values["month"], _ = report_period(values)
            if values.get("plan_id"):
                values["plan_id"] = data.get("id_aliases", {}).get(
                    values["plan_id"], values["plan_id"]
                )
                plan = data["items"].get(values["plan_id"])
                if not plan or plan["kind"] != "plan":
                    raise WorkspaceError("关联计划不存在于当前数据源")
            status = payload.get(
                "status", old["status"] if old else ("待采纳" if kind == "workflow" else "草稿")
            )
            if not isinstance(status, str) or status not in KINDS[kind]:
                raise WorkspaceError("事项状态无效")
            if old and status != old["status"] and status not in TRANSITIONS[old["status"]]:
                raise WorkspaceError("该状态不能直接跳转，请按流程推进。", 409)
            if not old and status not in (
                {"草稿", "已发布"}
                if kind == "report"
                else {"草稿"}
                if kind == "plan"
                else {"待采纳", "待执行"}
            ):
                raise WorkspaceError("新事项须从初始状态开始")
            if old and old["status"] in {"已完成", "已取消", "历史归档"}:
                raise WorkspaceError("已结束事项保留历史；请新建后续事项。", 409)
            if old and kind == "report" and old["status"] == "已发布":
                raise WorkspaceError("已发布报告不可改写，请新建修订版本。", 409)
            if (
                kind == "report"
                and status == "已发布"
                and not all(values.get(x, "").strip() for x in ("scope", "conclusion", "owner"))
            ):
                raise WorkspaceError("发布报告前请填写核定范围、结论和复核人")
            if (
                kind == "workflow"
                and status == "已完成"
                and not all(values.get(x, "").strip() for x in ("result", "evidence"))
            ):
                raise WorkspaceError("完成事项前请填写实际结果和证据")
            now = datetime.now(timezone.utc).isoformat()
            if not key:
                prefix = WORKSPACE_PREFIXES[kind]
                counters = data.setdefault("id_counters", {})
                number = (
                    max(
                        [
                            int(k[len(prefix) :], 36)
                            for k in data["items"]
                            if re.fullmatch(prefix + r"[0-9A-Z]{3,10}", k)
                        ]
                        + [counters.get(kind, 0)]
                    )
                    + 1
                )
                key = prefix + base36(number)
                counters[kind] = number
            item = {
                "id": key,
                "kind": kind,
                "values": values,
                "status": status,
                "version": old["version"] + 1 if old else 1,
                "created_at": old["created_at"] if old else now,
                "updated_at": now,
                "history": copy.deepcopy(old["history"]) if old else [],
            }
            identity = (
                {k: old[k] for k in ("long_id", "sha256", "issued_on")}
                if old and old.get("long_id")
                else {
                    k: v
                    for k, v in workspace_identity(kind, key, values.get("department", "")).items()
                    if k != "short_id"
                }
            )
            item.update(identity)
            note = payload.get("note", "")
            if not isinstance(note, str) or len(note) > 20000:
                raise WorkspaceError("处理说明无效")
            item["history"].append(
                {
                    "at": now,
                    "from": old["status"] if old else None,
                    "to": status,
                    "note": note,
                    "before": old["values"] if old else None,
                    "after": copy.deepcopy(values),
                }
            )
            data["items"][key] = item
            result = {"item": copy.deepcopy(item), "mode": self.mode}
            data["requests"][request] = {"hash": digest, "result": result}
            self.write(data)
            return self.public_result(result)
