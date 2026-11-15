"""Local PostgreSQL lifecycle; Python standard library only."""

from pathlib import Path
from contextvars import ContextVar
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import uuid
import zipfile

from business_queries import expand_queries

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ["finance", "legal", "production", "rd", "sales", "analysis"]
CONFIG = ROOT / "config.json"
DATABASE_CONTEXT = ContextVar("easyerp_database", default=None)


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def ident(value):
    return '"' + str(value).replace('"', '""') + '"'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class ERP:
    def __init__(self, *, mode="live", config=None, runtime_root=None):
        if mode not in ("live", "demo"):
            raise ValueError("无效数据来源")
        context = DATABASE_CONTEXT.get() if config is None else None
        if context and context["mode"] != mode:
            raise ValueError("数据库与数据来源不一致，请刷新后重试。")
        base = dict(config if config is not None else context["config"]) if config is not None or context else json.loads(CONFIG.read_text(encoding="utf-8-sig"))
        sources = base.get("database_sources", {})
        source = sources.get(mode, {})
        self.c = {**base, **source}
        if mode == "demo" and "database" not in source:
            self.c["database"] = base["database"] + "_ui_demo"
        port = self.c["port"]
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("本机数据库端口无效")
        if self.c.get("host", "127.0.0.1") not in ("127.0.0.1", "localhost"):
            raise ValueError("只支持本机数据库")
        self.root = Path(runtime_root or self.c.get("runtime_root", ROOT)).resolve()
        self.data = Path(self.c.get("data_directory", self.root / "var/pgdata"))
        self.private = Path(self.c.get("private_directory", self.root / ".secrets"))
        if not self.data.is_absolute() or not self.private.is_absolute():
            raise ValueError("数据库及凭据目录必须为绝对路径")
        self.pg = Path(os.environ.get("EASYERP_PG_BIN", self.c["postgres_bin"]))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
        self.env.update(
            PGCLIENTENCODING="UTF8",
            PGPASSFILE=str(self.private / "pgpass.conf"),
            PAGER="",
            PGCONNECT_TIMEOUT="5",
        )
        if not (self.pg / "psql.exe").is_file():
            raise RuntimeError(
                "找不到 PostgreSQL，请设置 EASYERP_PG_BIN 或 config.json 中 postgres_bin"
            )

    def workspace_root(self, mode="live"):
        if mode not in ("live", "demo"):
            raise ValueError("无效数据来源")
        source = self.c.get("database_sources", {}).get(mode, {})
        path = Path(source.get("workspace_directory", self.c.get("workspace_directory", ROOT / "var/workspace")))
        if not path.is_absolute():
            raise ValueError("工作空间目录必须为绝对路径")
        return path

    def run(self, exe, args, *, text=None, ok=True, timeout=120):
        # On Windows, a daemon may inherit pg_ctl's pipe handles. File handles
        # let the launcher finish without waiting for the daemon to close EOF.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            p = subprocess.run(
                [str(self.pg / (exe + ".exe")), *map(str, args)],
                input=text,
                stdout=out,
                stderr=err,
                encoding="utf-8",
                errors="replace",
                env=self.env,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            out.seek(0)
            err.seek(0)
            p.stdout = out.read().decode("utf-8", errors="replace")
            p.stderr = err.read().decode("utf-8", errors="replace")
        if ok and p.returncode:
            raise RuntimeError(
                f"{exe} 失败 ({p.returncode}): {p.stderr.strip()} {p.stdout.strip()}"
            )
        return p

    def sql(self, sql=None, *, db=None, role="easyerp_admin", file=None, ok=True):
        args = [
            "-X",
            "-w",
            "-h",
            "127.0.0.1",
            "-p",
            self.c["port"],
            "-U",
            role,
            "-d",
            db or self.c["database"],
            "-v",
            "ON_ERROR_STOP=1",
            "-P",
            "pager=off",
            "-Atq",
        ]
        args += ["-f", str(file)] if file else ["-f", "-"]
        return self.run("psql", args, text=None if file else sql, ok=ok)

    def private_dir(self, path):
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            user = subprocess.check_output(["whoami"], text=True).strip()
            p = subprocess.run(
                [
                    "icacls",
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    f"{user}:(OI)(CI)F",
                    "*S-1-5-18:(OI)(CI)F",
                ],
                capture_output=True,
            )
            if p.returncode:
                raise RuntimeError(f"无法限制目录访问权限：{path}")

    def init(self, *, ensure_database=True):
        self.private_dir(self.private)
        credential_file = self.private / "credentials.json"
        if not credential_file.exists():
            if (self.data / "PG_VERSION").exists():
                raise RuntimeError("已有数据库但缺失凭据，请先恢复 .secrets，拒绝覆盖原库")
            creds = {
                r: secrets.token_urlsafe(32)
                for r in ["easyerp_admin", "easyerp_app", "easyerp_read"]
            }
            write_json(credential_file, creds)
        creds = json.loads(credential_file.read_text(encoding="utf-8"))
        (self.private / "pgpass.conf").write_text(
            "".join(f"127.0.0.1:{self.c['port']}:*:{r}:{p}\n" for r, p in creds.items()),
            encoding="utf-8",
        )
        if not (self.data / "PG_VERSION").exists():
            if self.data.exists() and any(self.data.iterdir()):
                raise RuntimeError("数据目录非空且不是有效集群，拒绝初始化")
            self.private_dir(self.data)
            pw = self.private / "initdb-password.tmp"
            try:
                pw.write_text(creds["easyerp_admin"] + "\n", encoding="utf-8")
                self.run(
                    "initdb",
                    [
                        "-D",
                        self.data,
                        "-U",
                        "easyerp_admin",
                        "--pwfile",
                        pw,
                        "--auth-host=scram-sha-256",
                        "--auth-local=scram-sha-256",
                        "--encoding=UTF8",
                        "--locale=C",
                    ],
                )
            finally:
                pw.unlink(missing_ok=True)
            (self.data / "postgresql.auto.conf").write_text(
                "listen_addresses = '127.0.0.1'\n"
                + f"port = {self.c['port']}\n"
                + "timezone = 'UTC'\npassword_encryption = 'scram-sha-256'\n"
                + "max_connections = 50\nshared_buffers = '128MB'\n"
                + "logging_collector = off\nlog_min_messages = warning\n",
                encoding="utf-8",
            )
            (self.data / "pg_hba.conf").write_text(
                "host all all 127.0.0.1/32 scram-sha-256\n", encoding="utf-8"
            )
        self.start_server()
        for role in ["easyerp_app", "easyerp_read"]:
            found = self.sql(
                f"SELECT 1 FROM pg_roles WHERE rolname={literal(role)};", db="postgres"
            ).stdout.strip()
            if not found:
                self.sql(
                    f"CREATE ROLE {ident(role)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD {literal(creds[role])};",
                    db="postgres",
                )
        if ensure_database:
            self.ensure_database(self.c["database"])

    def start_server(self):
        status = self.run("pg_ctl", ["-D", self.data, "status"], ok=False)
        if status.returncode == 0:
            self.sql("SELECT 1;", db="postgres")
            return
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", self.c["port"])) == 0:
                raise RuntimeError("指定端口已有其他实例，拒绝连接或改动；请调整 config.json")
        logs = self.root / "var" / "log"
        self.private_dir(logs)
        self.run(
            "pg_ctl", ["-D", self.data, "-l", logs / (stamp() + ".log"), "-w", "-t", "45", "start"]
        )

    def verify_files(self):
        m = json.loads((ROOT / "db" / "manifest.json").read_text(encoding="utf-8"))
        source = (ROOT / m.get("source", "readme.md")).resolve()
        if not source.is_relative_to(ROOT.resolve()):
            raise RuntimeError("规范来源路径不在项目内")
        if hashlib.sha256(source.read_bytes()).hexdigest() != m["source_sha256"]:
            raise RuntimeError(
                f"{m.get('source', 'readme.md')} 已改变；请审查后重新构建，当前库不会被覆盖"
            )
        for name, digest in m["sql_files"].items():
            if hashlib.sha256((ROOT / "db" / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"{name} 校验失败；请审查后重新构建")
        digest = hashlib.sha256(json.dumps(m["sql_files"], sort_keys=True).encode()).hexdigest()
        return m, digest

    @staticmethod
    def version_matches(installed, manifest, digest):
        if installed == manifest["source_sha256"] + "|" + digest:
            return True
        return any(
            pair.get("build_sha256") == digest
            and installed == pair.get("source_sha256", "") + "|" + digest
            for pair in manifest.get("compatible_sources", [])
        )

    def ensure_database(self, db):
        m, digest = self.verify_files()
        exists = self.sql(
            f"SELECT 1 FROM pg_database WHERE datname={literal(db)};", db="postgres"
        ).stdout.strip()
        if not exists:
            self.run(
                "createdb",
                [
                    "-h",
                    "127.0.0.1",
                    "-p",
                    self.c["port"],
                    "-U",
                    "easyerp_admin",
                    "-w",
                    "--template=template0",
                    "--encoding=UTF8",
                    db,
                ],
            )
        installed = (
            self.sql(
                "SELECT to_regclass('erp_ops.schema_version') IS NOT NULL;", db=db
            ).stdout.strip()
            == "t"
        )
        if installed:
            old = self.sql(
                "SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0';",
                db=db,
            ).stdout.strip()
            if not self.version_matches(old, m, digest):
                raise RuntimeError("库中版本与当前构建不一致，需要单独审核迁移；拒绝自动重建")
            return
        occupied = self.sql(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','v');",
            db=db,
        ).stdout.strip()
        if occupied != "0":
            raise RuntimeError("目标库非空且没有本项目版本标记，拒绝覆盖")
        sql = "BEGIN;\n" + "".join(
            (ROOT / "db" / f).read_text(encoding="utf-8") + "\n" for f in sorted(m["sql_files"])
        )
        sql += f"INSERT INTO erp_ops.schema_version(version,source_sha256,build_sha256) VALUES ('0.2.0',{literal(m['source_sha256'])},{literal(digest)});\n"
        sql += self.permissions(db) + "\nCOMMIT;\n"
        self.sql(sql, db=db)

    def permissions(self, db):
        statements = [
            f"REVOKE ALL ON DATABASE {ident(db)} FROM PUBLIC;",
            f"GRANT CONNECT ON DATABASE {ident(db)} TO easyerp_app,easyerp_read;",
            "REVOKE CREATE ON SCHEMA public FROM PUBLIC;",
            "REVOKE ALL ON SCHEMA erp_ops FROM PUBLIC;",
            "GRANT USAGE ON SCHEMA erp_ops TO easyerp_app,easyerp_read;",
            "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA erp_ops FROM PUBLIC;",
        ]
        for schema in SCHEMAS:
            statements += [
                f"REVOKE ALL ON SCHEMA {schema} FROM PUBLIC;",
                f"GRANT USAGE ON SCHEMA {schema} TO easyerp_app,easyerp_read;",
                f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO easyerp_app,easyerp_read;",
                f"GRANT INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {schema} TO easyerp_app;",
            ]
        return "\n".join(statements)

    def migrate(self, db=None):
        db = db or self.c["database"]
        m, digest = self.verify_files()
        actual = self.sql(
            "SELECT current_setting('data_directory');", db=db, role="easyerp_admin"
        ).stdout.strip()
        if Path(actual).resolve() != self.data.resolve():
            raise RuntimeError("数据库目录不属于本项目，拒绝迁移")
        old = self.sql(
            "SELECT source_sha256||'|'||build_sha256 FROM erp_ops.schema_version WHERE version='0.2.0';",
            db=db,
            role="easyerp_admin",
        ).stdout.strip()
        if self.version_matches(old, m, digest):
            return {"database": db, "migration": "already applied"}
        if m.get("supplier_items_upgrade_from"):
            from migrate_supplier_items import migrate as migrate_supplier_items

            return migrate_supplier_items(self, db, apply=True)
        if m.get("finance_profile_upgrade_from"):
            from migrate_finance_profiles import migrate as migrate_finance, prior_versions

            if old not in prior_versions(m):
                raise RuntimeError("现有库需要先按已审核的旧版规范顺序升级，再执行010财务字段迁移；拒绝跳版标记")
            return migrate_finance(self, db, apply=True)
        if m.get("unit_profile_upgrade_from"):
            from migrate_unit_profile import migrate as migrate_unit, prior_versions

            if old not in prior_versions(m):
                from migrate_supplier_profile import migrate as migrate_supplier

                migrate_supplier(self, db, apply=True)
            return migrate_unit(self, db, apply=True)
        if m.get("supplier_profile_upgrade_from"):
            from migrate_supplier_profile import migrate as migrate_supplier

            return migrate_supplier(self, db, apply=True)
        previous = m["migration_from"]
        expected = previous["source_sha256"] + "|" + previous["build_sha256"]
        if old != expected:
            raise RuntimeError("现有版本并非预期前版，拒绝迁移；须审核差异")
        before = self.data_signature(db)
        backup = self.backup(db=db, verify_data=True)
        sql = "BEGIN;\n" + (ROOT / "db" / "007_remove_views.sql").read_text(encoding="utf-8")
        sql += f"\nINSERT INTO erp_ops.schema_upgrade_log(upgrade_id,from_build,to_build,source_sha256) VALUES ('007_remove_views',{literal(previous['build_sha256'])},{literal(digest)},{literal(m['source_sha256'])});"
        sql += f"\nUPDATE erp_ops.schema_version SET source_sha256={literal(m['source_sha256'])},build_sha256={literal(digest)} WHERE version='0.2.0';"
        self.sql(sql + "\nCOMMIT;", db=db, role="easyerp_admin")
        if self.data_signature(db) != before:
            raise RuntimeError("迁移后业务数据签名不一致")
        return {
            "database": db,
            "migration": "007_remove_views",
            "status": "PASS",
            "backup": str(backup),
            "business_data_unchanged": True,
        }

    def check(self, db=None):
        db = db or self.c["database"]
        self.verify_files()
        sql = (ROOT / "tests" / "structure.sql").read_text(encoding="utf-8")
        self.sql(sql, db=db)
        detail = self.sql(
            expand_queries(
                'SELECT row_to_json(x) FROM (SELECT * FROM erp_ops."业务核对问题" UNION ALL SELECT * FROM erp_ops."数量版本核对问题") x;'
            ),
            db=db,
            role="easyerp_read",
        ).stdout
        issues = [json.loads(x) for x in detail.splitlines() if x]
        rows = len(issues)
        result = {
            "at_utc": datetime.now(timezone.utc).isoformat(),
            "database": db,
            "structure": "PASS",
            "business_issue_count": rows,
            "business_issues": issues,
        }
        write_json(self.root / "reports" / "check-latest.json", result)
        return result

    def test(self):
        db = "easyerp_v02_test_" + uuid.uuid4().hex[:10]
        report = {"database": db, "at_utc": datetime.now(timezone.utc).isoformat(), "passed": False}
        try:
            self.ensure_database(db)
            self.check(db)
            p = self.sql(
                expand_queries((ROOT / "tests" / "business.sql").read_text(encoding="utf-8")), db=db
            )
            report["sql_tests"] = [s for s in p.stdout.splitlines() if s.startswith("PASS ")]
            # Real role tests, with rollback to avoid fixture pollution.
            for role, sql, success in [
                ("easyerp_read", 'SELECT count(*) FROM finance."人员档案表";', True),
                (
                    "easyerp_read",
                    "INSERT INTO finance.\"人员档案表\" VALUES ('deny','x','x',NULL,NULL);",
                    False,
                ),
                (
                    "easyerp_app",
                    "BEGIN; INSERT INTO finance.\"人员档案表\" VALUES ('writer','写入测试','财务',NULL,NULL); ROLLBACK;",
                    True,
                ),
                ("easyerp_app", "CREATE TABLE finance.forbidden(id int);", False),
                ("easyerp_app", 'TRUNCATE finance."会计分录表";', False),
                ("easyerp_read", "SELECT * FROM erp_ops.schema_version;", False),
            ]:
                outcome = self.sql(sql, db=db, role=role, ok=False)
                if (outcome.returncode == 0) != success:
                    raise RuntimeError("权限测试未通过: " + role)
            report["role_tests"] = 6
            # Restore a populated six-department fixture, not just an empty schema.
            sample = self.backup(db=db, verify_data=True)
            report["populated_restore"] = self.restore_test(sample)
            report["passed"] = True
        finally:
            # Only generated ephemeral databases may be removed by the test runner.
            if db.startswith("easyerp_v02_test_"):
                self.sql(f"DROP DATABASE IF EXISTS {ident(db)} WITH (FORCE);", db="postgres")
            write_json(self.root / "reports" / "test-latest.json", report)
        return report

    def data_signature(self, db):
        tables = self.sql(
            "SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1;",
            db=db,
        ).stdout.splitlines()
        chunks = []
        for table in tables:
            schema, name = table.split(".", 1)
            value = self.sql(
                f"SELECT count(*)||'|'||coalesce(md5(string_agg(row_to_json(x)::text,E'\\n' ORDER BY row_to_json(x)::text)),md5('')) FROM {ident(schema)}.{ident(name)} x;",
                db=db,
            ).stdout.strip()
            chunks.append(table + "|" + value)
        return hashlib.sha256("\n".join(chunks).encode()).hexdigest()

    def backup(self, db=None, verify_data=False):
        db = db or self.c["database"]
        folder = self.root / "backups"
        self.private_dir(folder)
        out = folder / (db + "-" + stamp() + ".dump")
        self.run(
            "pg_dump",
            [
                "-h",
                "127.0.0.1",
                "-p",
                self.c["port"],
                "-U",
                "easyerp_admin",
                "-w",
                "-Fc",
                "-f",
                out,
                db,
            ],
        )
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        write_json(
            out.with_suffix(".json"),
            {
                "database": db,
                "sha256": digest,
                "at_utc": datetime.now(timezone.utc).isoformat(),
                "file": out.name,
                "data_signature": self.data_signature(db) if verify_data else None,
            },
        )
        return out

    def restore_test(self, path):
        path = Path(path).resolve()
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise RuntimeError("备份哈希不匹配")
        db = "easyerp_v02_restore_" + uuid.uuid4().hex[:10]
        result = {"backup": str(path), "passed": False}
        try:
            self.run(
                "createdb",
                [
                    "-h",
                    "127.0.0.1",
                    "-p",
                    self.c["port"],
                    "-U",
                    "easyerp_admin",
                    "-w",
                    "-T",
                    "template0",
                    db,
                ],
            )
            self.run(
                "pg_restore",
                [
                    "-h",
                    "127.0.0.1",
                    "-p",
                    self.c["port"],
                    "-U",
                    "easyerp_admin",
                    "-w",
                    "--exit-on-error",
                    "--single-transaction",
                    "-d",
                    db,
                    path,
                ],
            )
            self.check(db)
            if meta.get("data_signature"):
                actual = self.data_signature(db)
                if actual != meta["data_signature"]:
                    raise RuntimeError("恢复后业务数据签名与备份测试样本不一致")
                result["data_signature_matched"] = True
            result["passed"] = True
        finally:
            self.sql(f"DROP DATABASE IF EXISTS {ident(db)} WITH (FORCE);", db="postgres")
            write_json(self.root / "reports" / "restore-latest.json", result)
        return result

    def startup(self, remove=False):
        # Current-user Startup folder; no system service or administrator privilege required.
        dest = (
            Path(os.environ["APPDATA"])
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / "easyerp-0.2.vbs"
        )
        if remove:
            if dest.exists() and str(ROOT) in dest.read_text(encoding="utf-16"):
                dest.unlink()
            return {"startup_removed": str(dest)}
        powershell = (
            Path(os.environ["SystemRoot"])
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        script = ROOT / "bin" / "start-hidden.ps1"
        content = f'Set sh = CreateObject("WScript.Shell")\nsh.Run """{powershell}"" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{script}""", 0, False\n'
        if dest.exists() and dest.read_text(encoding="utf-16") != content:
            raise RuntimeError("启动目录存在不同内容的同名文件，拒绝覆盖")
        dest.write_text(content, encoding="utf-16")
        return {"startup_installed": str(dest), "trigger": "current-user logon"}

    def export(self):
        # Repeatable-read export freezes actual values in files; references alone do not freeze rows.
        self.private_dir(self.root / "exports")
        folder = self.root / "exports" / stamp()
        self.private_dir(folder)
        incomplete = folder / "INCOMPLETE.txt"
        incomplete.write_text(
            "Export in progress or failed. Do not use without manifest.json.\n", encoding="utf-8"
        )
        export_sql = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n"
        tables = self.sql(
            "SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('finance','legal','production','rd','sales','analysis') ORDER BY 1;"
        ).stdout.splitlines()
        mapping = {}
        for index, table in enumerate(tables, 1):
            schema, name = table.split(".", 1)
            # Windows psql uses the active code page for local filenames.
            # Keep filenames ASCII; preserve full Unicode table identity in the manifest.
            path = folder / (schema + f".{index:03}.csv")
            mapping[path.name] = {"schema": schema, "table": name}
            export_sql += f"\\copy (SELECT * FROM {ident(schema)}.{ident(name)}) TO {literal(path.as_posix())} WITH (FORMAT CSV, HEADER TRUE, ENCODING 'UTF8', NULL '\\N')\n"
        export_sql += "COMMIT;\n"
        self.sql(export_sql, role="easyerp_read")
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("*.csv")}
        source, _ = self.verify_files()
        write_json(
            folder / "manifest.json",
            {
                "at_utc": datetime.now(timezone.utc).isoformat(),
                "source_sha256": source["source_sha256"],
                "database": self.c["database"],
                "null_marker": "\\N",
                "files": files,
                "tables": mapping,
            },
        )
        incomplete.unlink()
        archive = folder.with_suffix(".zip")
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
            for p in folder.iterdir():
                z.write(p, p.name)
        return {"export": str(archive), "tables": len(tables)}


def main():
    p = argparse.ArgumentParser(description="easyERP 0.2 本机数据库管理")
    p.add_argument(
        "command",
        choices=[
            "init",
            "start",
            "stop",
            "status",
            "shell",
            "check",
            "test",
            "backup",
            "restore-test",
            "migrate",
            "install-startup",
            "remove-startup",
            "export",
            "query",
            "databases",
            "migration-preview",
            "import-sql",
        ],
    )
    p.add_argument("value", nargs="?")
    p.add_argument(
        "--role", choices=["easyerp_app", "easyerp_read", "easyerp_admin"], default="easyerp_app"
    )
    p.add_argument("--encoded-value", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()
    if a.encoded_value and a.value is not None:
        import base64

        a.value = base64.b64decode(a.value).decode("utf-8")
    e = ERP()
    if a.command in ("init", "start"):
        if e.c.get("database_sources"):
            seen = set()
            for mode in ("live", "demo"):
                source = ERP(mode=mode)
                key = (str(source.data.resolve()), source.c["database"])
                if key not in seen:
                    source.init()
                    seen.add(key)
        else:
            e.init()
        result = {
            "database": e.c["database"],
            "host": "127.0.0.1",
            "port": e.c["port"],
            "status": "READY",
        }
    elif a.command in ("databases", "migration-preview"):
        sys.path.insert(0, str(ROOT / "app"))
        from database_manager import DatabaseManager
        manager = DatabaseManager()
        result = manager.listing() if a.command == "databases" else manager.migration_preview()
    elif a.command == "stop":
        e.run("pg_ctl", ["-D", e.data, "-w", "-t", "45", "stop", "-m", "fast"])
        result = {"status": "STOPPED"}
    elif a.command == "status":
        result = json.loads(
            e.sql(
                "SELECT json_build_object('database',current_database(),'user',current_user,'version',version(),'data_directory',current_setting('data_directory'),'port',inet_server_port(),'listen_addresses',current_setting('listen_addresses'),'timezone',current_setting('TimeZone'));"
            ).stdout
        )
    elif a.command == "shell":
        sys.exit(
            subprocess.call(
                [
                    str(e.pg / "psql.exe"),
                    "-X",
                    "-w",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(e.c["port"]),
                    "-U",
                    a.role,
                    "-d",
                    e.c["database"],
                    "-P",
                    "pager=off",
                ],
                env=e.env,
            )
        )
    elif a.command == "query":
        if not a.value:
            p.error("query 需要 SQL 参数")
        print(e.sql(a.value, role=a.role).stdout, end="")
        return
    elif a.command == "import-sql":
        if not a.value:
            p.error("import-sql 需要 SQL 文件路径")
        # Ensure import is atomic, including deferred posting checks.
        content = Path(a.value).read_text(encoding="utf-8-sig")
        if any(line.lstrip().startswith("\\") for line in content.splitlines()):
            raise RuntimeError("导入只接受 SQL，不接受 psql 元命令")
        e.sql("BEGIN;\n" + content + "\nCOMMIT;", role=a.role)
        result = {"imported": str(Path(a.value).resolve())}
    elif a.command == "check":
        result = e.check()
    elif a.command == "migrate":
        result = e.migrate()
    elif a.command == "test":
        result = e.test()
    elif a.command == "backup":
        result = {"backup": str(e.backup())}
    elif a.command == "restore-test":
        if not a.value:
            p.error("restore-test 需要备份文件路径")
        result = e.restore_test(a.value)
    elif a.command in ("install-startup", "remove-startup"):
        result = e.startup(a.command == "remove-startup")
    elif a.command == "export":
        result = e.export()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
