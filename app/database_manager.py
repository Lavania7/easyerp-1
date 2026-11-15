"""Local database catalog, empty-instance creation and read-only relocation preview."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import threading
import time
import uuid

from data import ROOT, InvalidRequest
from easyerp import ERP, SCHEMAS, ident, literal

LOCK = threading.RLock()
PICKER_LOCK = threading.Lock()
TICKETS = {}
PLANS = {}
APP_SQL = ("entry_schema.sql", "csv_import_schema.sql", "company_schema.sql",
           "workspace_schema.sql", "purchase_intake_schema.sql", "business_ids.sql")


class DatabaseError(InvalidRequest):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def folder_path(value, project=ROOT):
    if not isinstance(value, str) or not value or value.startswith(("\\\\", "//")):
        raise DatabaseError("请选择本机文件夹。")
    path = Path(value)
    if not path.is_absolute() or not path.is_dir():
        raise DatabaseError("所选文件夹不存在。")
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise DatabaseError("请选择普通本机目录，不支持链接或目录联接。")
    path = path.resolve()
    if path.is_relative_to(Path(project).resolve()):
        raise DatabaseError("请选择项目目录以外的位置，以隔离业务数据。")
    return path


def pick_folder():
    if os.name != "nt":
        raise DatabaseError("原生目录选择需要 Windows。", 503)
    if not PICKER_LOCK.acquire(blocking=False):
        raise DatabaseError("已有文件夹选择窗口，请先完成或取消。", 409)
    script = """Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择新数据库存放目录'
$dialog.ShowNewFolderButton = $true
try {
  if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    [Console]::Write($dialog.SelectedPath)
  }
} finally { $dialog.Dispose() }
"""
    try:
        process = subprocess.run(
            [str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
             "-NoProfile", "-STA", "-NonInteractive", "-Command", script],
            capture_output=True, encoding="utf-8", timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if process.returncode:
            raise DatabaseError("无法打开 Windows 文件夹选择面板。", 503)
        return process.stdout.strip() or None
    except subprocess.TimeoutExpired:
        raise DatabaseError("目录选择已超时，请重新打开。", 408)
    finally:
        PICKER_LOCK.release()


class DatabaseManager:
    def __init__(self, root=ROOT, erp_factory=ERP, picker=pick_folder):
        self.root = Path(root)
        self.registry = self.root / "var/database-manager/registry.json"
        self.erp_factory = erp_factory
        self.picker = picker

    @contextmanager
    def locked(self):
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        with LOCK, self.registry.with_suffix(".lock").open("a+b") as stream:
            if stream.seek(0, 2) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise DatabaseError("数据库管理正在处理其他操作，请稍后重试。", 409)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def read(self):
        if not self.registry.exists():
            return {"version": 1, "nodes": []}
        result = json.loads(self.registry.read_text(encoding="utf-8"))
        if result.get("version") != 1 or not isinstance(result.get("nodes"), list):
            raise DatabaseError("数据库注册表格式不受支持。", 503)
        return result

    def template(self):
        erp = self.erp_factory()
        manifest, build = erp.verify_files()
        files = {"db/" + key: value for key, value in manifest["sql_files"].items()}
        for name in APP_SQL:
            files["db/app/" + name] = hashlib.sha256((self.root / "db/app" / name).read_bytes()).hexdigest()
        files["app/id_rules.json"] = hashlib.sha256((self.root / "app/id_rules.json").read_bytes()).hexdigest()
        digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        return {"id": "template-" + digest[:16], "label": "当前空白结构模板",
                "kind": "template", "build_sha256": build, "template_sha256": digest,
                "schema_version": manifest["version"], "files": files}

    def migration_record(self):
        erp = self.erp_factory(mode="live")
        path = erp.root / "migration/restored.json"
        if not path.is_file():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("state") != "cutover":
            return None
        target = record.get("target_config", {})
        if (target.get("database") != erp.c["database"]
                or target.get("port") != erp.c["port"]
                or Path(target.get("data_directory", "")).resolve() != erp.data.resolve()
                or not re.fullmatch(r"[a-f0-9]{64}", record.get("backup_sha256", ""))):
            raise DatabaseError("迁移记录与当前正式连接不匹配，请核对来源配置。", 503)
        return record

    def retained_source(self, record):
        original = record["source_config"]
        config = {**original, **original.get("database_sources", {}).get("live", {})}
        runtime = Path(config.get("runtime_root", self.root))
        return {"id": "retained-source-" + record["backup_sha256"][:16],
                "label": "保留的旧正式库", "kind": "retained-source", "status": "retained",
                "database": config["database"], "port": config["port"],
                "directory": str(config.get("data_directory", runtime / "var/pgdata")),
                "workspace": str(config.get("workspace_directory", runtime / "var/workspace")),
                "active": False, "parent_id": None, "relation": "unknown"}

    def listing(self):
        template = self.template()
        nodes = [template]
        record = self.migration_record()
        source = self.retained_source(record) if record else None
        if source:
            nodes.append(source)
        for mode, label in (("live", "当前正式数据库"), ("demo", "项目演示数据库")):
            erp = self.erp_factory(mode=mode)
            nodes.append({"id": "active-" + mode, "label": label, "kind": mode,
                          "database": erp.c["database"], "port": erp.c["port"],
                          "directory": str(erp.data), "workspace": str(erp.workspace_root(mode)),
                          "status": "configured", "parent_id": None,
                          "relation": "unknown", "active": True})
            if mode == "live" and source:
                nodes[-1].update(parent_id=source["id"], relation="restored-copy",
                                 backup_sha256=record["backup_sha256"], source_retained=True)
        known = {node["id"] for node in nodes}
        nodes += [node for node in self.read()["nodes"] if node["id"] not in known]
        return {"nodes": nodes, "creation": "empty-schema", "activation_available": False,
                "migration": "cutover" if record else "preview-only",
                "source_retained": bool(source)}

    def select_folder(self, payload):
        if payload != {}:
            raise DatabaseError("目录选择不接受路径参数。")
        chosen = self.picker()
        if chosen is None:
            return {"cancelled": True}
        path = folder_path(chosen, self.root)
        ticket = secrets.token_urlsafe(32)
        with LOCK:
            self.expire()
            TICKETS[ticket] = (str(path), time.monotonic() + 600)
        return {"cancelled": False, "folder": str(path), "folder_ticket": ticket}

    @staticmethod
    def expire():
        for cache in (TICKETS, PLANS):
            for key, value in list(cache.items()):
                if value[1] < time.monotonic():
                    del cache[key]

    def preview(self, payload):
        if not isinstance(payload, dict) or set(payload) - {"folder_ticket", "label", "parent_id"}:
            raise DatabaseError("新建参数无效。")
        label = payload.get("label")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80 or any(ord(c) < 32 for c in label):
            raise DatabaseError("请填写1至80字数据库名称。")
        with LOCK:
            self.expire()
            ticket = TICKETS.get(str(payload.get("folder_ticket", "")))
            if not ticket:
                raise DatabaseError("请重新选择文件夹。", 409)
            directory = folder_path(ticket[0], self.root)
            template = self.template()
            nodes = self.listing()["nodes"]
            parent = payload.get("parent_id", template["id"])
            if parent not in {node["id"] for node in nodes if node.get("status") not in ("creating", "failed")}:
                raise DatabaseError("父版本不存在或尚未完成。")
            key = uuid.uuid4().hex
            port = self.available_port()
            target = directory / ("easyerp-" + key[:12])
            plan = {"id": key, "label": label.strip(), "parent_id": template["id"],
                    "logical_parent_id": parent if parent != template["id"] else None,
                    "relation": "empty-schema", "template": template,
                    "directory": str(target), "database": "easyerp_" + key[:12],
                    "port": port, "created_at": now()}
            PLANS[key] = (plan, time.monotonic() + 600)
        return {"plan_id": key, "label": plan["label"], "directory": str(target),
                "database": plan["database"], "port": port, "parent_id": template["id"],
                "logical_parent_id": plan["logical_parent_id"],
                "template_sha256": template["template_sha256"],
                "effects": ["新建独立目录、集群及三类独立角色凭据", "按已校验SQL建立空结构，业务记录数为0",
                            "新建独立空工作空间；不复制父版本的记录或工作空间", "验证后停止本次新实例；当前正式/演示配置不切换"]}

    def available_port(self):
        reserved = {node.get("port") for node in self.read()["nodes"]}
        reserved.update(self.erp_factory(mode=mode).c["port"] for mode in ("live", "demo"))
        for port in range(55434, 55535):
            if port in reserved:
                continue
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise DatabaseError("没有可用的本机数据库端口。", 409)

    def create(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"plan_id"} or not isinstance(payload["plan_id"], str):
            raise DatabaseError("请先预览新建数据库。")
        key = payload["plan_id"]
        with self.locked():
            registry = self.read()
            for node in registry["nodes"]:
                if node["id"] == key:
                    if node["status"] == "ready":
                        return {"node": node, "replayed": True}
                    raise DatabaseError("该创建任务未完成，已保留目录和记录供检查；不会重复创建。", 409)
            with LOCK:
                self.expire()
                entry = PLANS.get(key)
                if not entry:
                    raise DatabaseError("新建预览已过期，请重新预览。", 409)
                plan = entry[0]
            target = Path(plan["directory"])
            folder_path(str(target.parent), self.root)
            if target.exists():
                raise DatabaseError("目标目录已存在，拒绝覆盖。", 409)
            if self.template() != plan["template"]:
                raise DatabaseError("SQL模板已改变，请重新预览。", 409)
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", plan["port"]))
                except OSError:
                    raise DatabaseError("预览端口已被占用，请重新预览。", 409)
            node = {k: value for k, value in plan.items() if k != "template"}
            node.update(kind="database", status="creating", active=False,
                        template_sha256=plan["template"]["template_sha256"],
                        build_sha256=plan["template"]["build_sha256"])
            if not any(item["id"] == plan["template"]["id"] for item in registry["nodes"]):
                registry["nodes"].append({**plan["template"], "label": "空白结构模板 · " + plan["template"]["template_sha256"][:8]})
            registry["nodes"].append(node)
            atomic_json(self.registry, registry)
            try:
                self.initialize(plan)
                node.update(status="ready", verified_at=now(), business_rows=0,
                            workspace=str(target / "workspace"), stopped=True)
            except Exception:
                node.update(status="failed", failed_at=now())
                atomic_json(self.registry, registry)
                raise DatabaseError("新建未完成，已保留独立目录和失败记录。当前数据库不受影响，请查看本机日志。", 503)
            atomic_json(self.registry, registry)
            return {"node": node, "replayed": False}

    def initialize(self, plan):
        target = Path(plan["directory"])
        target.mkdir(exist_ok=False)
        base = self.erp_factory().c
        config = {key: base[key] for key in ("postgres_bin", "python")}
        config.update(database=plan["database"], port=plan["port"],
                      data_directory=str(target / "pgdata"), private_directory=str(target / ".secrets"),
                      workspace_directory=str(target / "workspace"), runtime_root=str(target))
        erp = self.erp_factory(config=config, runtime_root=target)
        erp.private_dir(target)
        atomic_json(target / "instance.json", {"id": plan["id"], "config": config,
                    "template": plan["template"], "created_at": now()})
        started = False
        try:
            erp.init()
            started = True
            actual = erp.sql("BEGIN READ ONLY; SELECT current_setting('data_directory'); COMMIT;",
                             db=config["database"], role="easyerp_admin").stdout.strip()
            if Path(actual).resolve() != erp.data.resolve():
                raise RuntimeError("Unexpected new cluster")
            sql = "BEGIN;\n" + "\n".join((self.root / "db/app" / name).read_text(encoding="utf-8") for name in APP_SQL)
            rules = json.loads((self.root / "app/id_rules.json").read_text(encoding="utf-8"))
            for key, rule in rules.items():
                sql += "\nINSERT INTO erp_ops.business_id_rules(table_key,pk_column,prefix,department) VALUES (" + ",".join(map(literal, [key, rule["pk"], rule["prefix"], rule["department"]])) + ");"
                schema, table = key.split(".", 1)
                sql += "\nCREATE TRIGGER easyerp_business_identity BEFORE INSERT OR UPDATE ON " + ident(schema) + "." + ident(table) + " FOR EACH ROW EXECUTE FUNCTION erp_ops.check_business_id();"
            erp.sql(sql + "\nCOMMIT;", db=config["database"], role="easyerp_admin")
            counts = " UNION ALL ".join("SELECT count(*) AS n FROM " + ident(key.split(".", 1)[0]) + "." + ident(key.split(".", 1)[1]) for key in rules)
            result = erp.sql("BEGIN READ ONLY; SELECT sum(n) FROM (" + counts + ") q; COMMIT;",
                             db=config["database"], role="easyerp_read").stdout.strip()
            if result != "0":
                raise RuntimeError("New business database is not empty")
            atomic_json(target / "workspace/live.json", {"version": 1, "mode": "live", "items": {}, "requests": {}})
            atomic_json(target / "config.candidate.json", {"database_sources": {"live": config},
                        "notice": "候选配置，未应用到当前项目"})
        finally:
            status = erp.run("pg_ctl", ["-D", erp.data, "status"], ok=False)
            if started or status.returncode == 0:
                erp.run("pg_ctl", ["-D", erp.data, "-w", "-t", "45", "stop", "-m", "fast"])

    def migration_preview(self):
        record = self.migration_record()
        if record:
            source = self.retained_source(record)
            return {"status": "cutover", "executed": True, "source_deleted": False,
                    "source": {"directory": source["directory"], "port": source["port"],
                               "database": source["database"]},
                    "target": record["target_config"], "source_retained": True,
                    "requires_separate_approval": [],
                    "steps": ["正式数据库已恢复并切换，旧源完整保留。",
                              "已核对全部业务及运维表、结构、工作空间和正式导入历史。",
                              "备份恢复验证通过，未执行旧源清理。"]}
        erp = self.erp_factory(mode="live")
        actual = json.loads(erp.sql("BEGIN READ ONLY; SELECT json_build_object('directory',current_setting('data_directory'),'port',inet_server_port(),'database',current_database(),'bytes',pg_database_size(current_database())); COMMIT;",
                                    db=erp.c["database"], role="easyerp_admin").stdout)
        if Path(actual["directory"]).resolve() != erp.data.resolve() or actual["port"] != erp.c["port"]:
            raise DatabaseError("实际集群与配置不一致，停止生成迁移方案。", 409)
        target = Path("D:/database/easyerp-live")
        files = []
        for mode in ("live", "demo"):
            source = self.erp_factory(mode=mode).workspace_root(mode) / (mode + ".json")
            files.append({"mode": mode, "path": str(source), "exists": source.is_file(),
                          "sha256": hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None})
        config = {"database": erp.c["database"], "port": 55434, "runtime_root": str(target),
                  "data_directory": str(target / "pgdata"), "private_directory": str(target / ".secrets"),
                  "workspace_directory": str(target / "workspace")}
        demo = self.erp_factory(mode="demo")
        return {"status": "preview-only", "executed": False, "source": actual,
                "target": config, "target_exists": target.exists(), "workspace_files": files,
                "candidate": {"database_sources": {"live": config, "demo": {
                    "database": demo.c["database"], "port": demo.c["port"],
                    "data_directory": str(demo.data), "private_directory": str(demo.private),
                    "workspace_directory": str(demo.workspace_root("demo")), "runtime_root": str(demo.root)}}},
                "requires_separate_approval": ["正式库备份恢复与数据复制", "暂停写入及连接切换", "从项目集群删除正式库及正式外部数据"],
                "steps": ["批准后暂停工作台及所有写入方，记录源签名及外部文件哈希",
                          "完整备份正式库、角色恢复材料和live工作空间；在目标目录恢复独立集群",
                          "逐表比较全数据与约束、审计/编号/角色权限和工作空间，验证备份恢复",
                          "切换候选配置并重启已核实的工作台，验证正式与演示隔离",
                          "保留源库用于回滚；人类验收后单独批准清除项目中的正式数据"]}
