"""Independent, versioned calculation boards in the selected source workspace."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import re
import uuid

from calculation_engine import evaluate, parameters, FormulaError
from workspace import Workspace, WorkspaceError
from identifiers import base36, identity


class Calculations(Workspace):
    def __init__(self, mode="live", root=None):
        super().__init__(mode, root)
        self.root = self.root / "calculations"
        self.path = self.root / (mode + ".json")

    def listing(self, params):
        with self.locked():
            data = self.read()
            items = list(data["items"].values())
            formulas = self.formulas(data)
        search = params.get("search", "").strip().casefold()
        rows = [self.public_item(item) for item in items if
                (not params.get("id") or item["id"] == params["id"]) and
                (not search or search in (item["id"] + " " + item["remarks"]).casefold())]
        rows.sort(key=lambda item: item["updated_at"], reverse=True)
        return {"rows": rows, "mode": self.mode, "formulas": formulas}

    @staticmethod
    def board(value):
        if not isinstance(value, dict) or set(value) - {"expression", "parameters", "formula_name", "parameter_notes"}:
            raise WorkspaceError("计算台格式无效")
        expression = value.get("expression", "")
        values = value.get("parameters", {})
        if not isinstance(expression, str) or len(expression) > 512 or not isinstance(values, dict) or len(values) > 64:
            raise WorkspaceError("公式或参数格式无效")
        if any(not isinstance(k, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", k) or not isinstance(v, str) or len(v) > 123 for k, v in values.items()):
            raise WorkspaceError("参数必须使用名称和十进制文本")
        result, error = None, ""
        names = []
        if expression.strip():
            try:
                names = parameters(expression)
                result = evaluate(expression, values)
            except FormulaError as exc:
                error = str(exc)
        metadata = Calculations.formula_metadata(value.get("formula_name", ""), value.get("parameter_notes", {}), names)
        return {"expression": expression, "parameters": {k: values.get(k, "") for k in names}, "formula_name": metadata["name"], "parameter_notes": metadata["parameter_notes"], "result": result, "error": error}

    @staticmethod
    def formula_metadata(name, notes, names):
        if not isinstance(name, str) or len(name) > 120:
            raise WorkspaceError("公式名称应为不超过120字的文本")
        if not isinstance(notes, dict) or len(notes) > 64 or any(not isinstance(k, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", k) or not isinstance(v, str) or len(v) > 300 for k, v in notes.items()):
            raise WorkspaceError("参数含义应为不超过300字的文本")
        return {"name": name.strip(), "parameter_notes": {k: notes[k].strip() for k in names if notes.get(k, "").strip()}}

    @staticmethod
    def formulas(data):
        return [{"id": "formula_" + hashlib.sha256(value.encode()).hexdigest()[:32], "version": 1, "name": "", "expression": value, "parameter_notes": {}, "history": []} if isinstance(value, str) else copy.deepcopy(value) for value in data.get("formulas", [])]

    @staticmethod
    def validate_request(payload):
        request = payload.get("request_id")
        if not isinstance(request, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request):
            raise WorkspaceError("缺少保存请求标识")
        return request

    def save_formula(self, payload):
        if not isinstance(payload, dict) or set(payload) - {"request_id", "id", "version", "name", "expression", "parameter_notes"}:
            raise WorkspaceError("公式提交格式无效")
        request = self.validate_request(payload)
        try:
            digest = hashlib.sha256(json.dumps({"operation": "formula_save", "payload": payload}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        except (TypeError, ValueError):
            raise WorkspaceError("公式提交格式无效") from None
        with self.locked():
            data = self.read()
            previous = data["requests"].get(request)
            if previous:
                if previous["digest"] != digest:
                    raise WorkspaceError("请求标识已用于不同内容", 409)
                return copy.deepcopy(previous["result"])
            formulas = self.formulas(data)
            old = next((item for item in formulas if item["id"] == payload.get("id")), None)
            if old is None:
                raise WorkspaceError("已保存的公式不存在", 404)
            if type(payload.get("version")) is not int or payload["version"] != old["version"]:
                raise WorkspaceError("公式已更新，请刷新后重试", 409)
            expression = payload.get("expression", old["expression"])
            if not isinstance(expression, str) or not expression.strip() or len(expression) > 512:
                raise WorkspaceError("请输入不超过512字的LaTeX公式")
            try:
                names = parameters(expression)
            except FormulaError:
                names = []
            metadata = self.formula_metadata(payload.get("name", old["name"]), payload.get("parameter_notes", old["parameter_notes"]), names)
            old.update(**metadata, expression=expression.strip(), version=old["version"] + 1)
            old.setdefault("history", []).append({"at": datetime.now(timezone.utc).isoformat(), **{k: copy.deepcopy(old[k]) for k in ("version", "name", "expression", "parameter_notes")}})
            data["formulas"] = formulas
            result = {"formula": copy.deepcopy(old), "formulas": formulas, "mode": self.mode}
            data["requests"][request] = {"digest": digest, "result": copy.deepcopy(result)}
            self.write(data)
            return result

    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) - {"request_id", "id", "version", "remarks", "board", "write_result", "save_formula"}:
            raise WorkspaceError("量化计算提交格式无效")
        request = self.validate_request(payload)
        if "write_result" in payload and not isinstance(payload["write_result"], bool):
            raise WorkspaceError("结果写入选项无效")
        if "save_formula" in payload and not isinstance(payload["save_formula"], bool):
            raise WorkspaceError("公式保存选项无效")
        try:
            digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        except (TypeError, ValueError):
            raise WorkspaceError("量化计算提交格式无效；数字参数请使用十进制文本") from None
        with self.locked():
            data = self.read()
            previous = data["requests"].get(request)
            if previous:
                if previous["digest"] != digest:
                    raise WorkspaceError("请求标识已用于不同内容", 409)
                return self.public_result(previous["result"])
            key = payload.get("id")
            if key is not None and (not isinstance(key, str) or key not in data["items"]):
                raise WorkspaceError("量化计算记录不存在", 404)
            old = data["items"].get(key)
            if old and (type(payload.get("version")) is not int or payload["version"] != old["version"]):
                raise WorkspaceError("记录已更新，请刷新后重试", 409)
            if not old and "version" in payload:
                raise WorkspaceError("新建记录不应提交版本")
            remarks = payload.get("remarks", old["remarks"] if old else "")
            if not isinstance(remarks, str) or len(remarks) > 20000:
                raise WorkspaceError("备注应为不超过20000字的文本")
            board = self.board(payload.get("board", {k: v for k, v in old["board"].items() if k in ("expression", "parameters", "formula_name", "parameter_notes")} if old else {}))
            formulas = self.formulas(data)
            if payload.get("save_formula"):
                expression = board["expression"].strip()
                if not expression:
                    raise WorkspaceError("请输入需要保存的LaTeX公式")
                metadata = {"expression": expression, "name": board["formula_name"], "parameter_notes": board["parameter_notes"]}
                if not any(all(item.get(k) == v for k, v in metadata.items()) for item in formulas):
                    if len(formulas) >= 256:
                        raise WorkspaceError("备选公式已达256条上限")
                    formula = {"id": "formula_" + uuid.uuid4().hex, "version": 1, **metadata}
                    formula["history"] = [{"at": datetime.now(timezone.utc).isoformat(), "version": 1, **copy.deepcopy(metadata)}]
                    formulas.append(formula)
            if payload.get("write_result"):
                if board["result"] is None:
                    raise WorkspaceError("公式尚不能计算，请检查公式和参数")
                result = board["result"]
                summary = board["expression"] + "\n" + ", ".join(k + "=" + v for k, v in board["parameters"].items())
                summary += "\n结果：" + ("" if result["exact"] else "≈ ") + result["value"]
                if not result["exact"]:
                    summary += "（四舍五入至20位小数）"
                remarks = (remarks.rstrip() + "\n\n" if remarks.strip() else "") + summary
                if len(remarks) > 20000:
                    raise WorkspaceError("结果写入后备注超过20000字，请精简后重试")
            now = datetime.now(timezone.utc).isoformat()
            if not old:
                number = data.get("sequence", 0) + 1
                key = "CAL" + base36(number)
                data["sequence"] = number
                item = {"id": key, "kind": "calculation", "created_at": now, "version": 0, "history": []}
                item.update({k: v for k, v in identity("WS", "CAL", key).items() if k != "short_id"})
            else:
                item = copy.deepcopy(old)
            item.update(remarks=remarks, board=board, updated_at=now, version=item["version"] + 1)
            item["history"].append({"at": now, "version": item["version"], "remarks": remarks, "board": copy.deepcopy(board)})
            data["items"][key] = item
            data["formulas"] = formulas
            result = {"item": copy.deepcopy(item), "mode": self.mode, "formulas": list(formulas)}
            data["requests"][request] = {"digest": digest, "result": result}
            self.write(data)
            return self.public_result(result)
