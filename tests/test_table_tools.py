"""Table tools checks. --integration uses disposable restored clones only."""

from pathlib import Path
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
import argparse
import csv
import io
import json
import os
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "app"), str(ROOT / "tools")]
from data import Data, InvalidRequest, I, L
from entry import ManualEntry, EntryError
from table_tools import TableData, BulkEntry, protected_fields

passed = []


def check(name, condition=True):
    assert condition, name
    passed.append(name)
    print("PASS:", name, flush=True)


def rejects(name, callback, status=None):
    try:
        callback()
    except InvalidRequest as error:
        check(name, status is None or getattr(error, "status", 400) == status)
    else:
        raise AssertionError(name)


def unit():
    query = TableData.__new__(TableData)
    columns = {"金额": "numeric(20,4)", "名称": "text", "日期": "date", "可选": "boolean"}
    query.p = {"table_filters": json.dumps([{"field": "金额", "op": "gte", "value": "9999999999999999.9999"}, {"field": "名称", "op": "contains", "value": "%'\\\n;DROP"}]), "table_sort": '{"field":"金额","direction":"desc"}'}
    where, order = query.controls(columns)
    check("numeric comparison and sorting cast to numeric", '"金额"::numeric' in where and '"金额"::numeric DESC NULLS LAST' in order)
    check("substring filters encode values as data and preserve literal wildcards", "strpos" in where and "DROP" not in where and "decode(" in where)
    for name, payload in (
        ("unknown filter fields rejected", [{"field": "secret", "op": "eq", "value": "x"}]),
        ("numeric floats rejected", [{"field": "金额", "op": "eq", "value": 0.1}]),
        ("invalid date rejected", [{"field": "日期", "op": "eq", "value": "2026-02-30"}]),
        ("boolean substring rejected", [{"field": "可选", "op": "contains", "value": "true"}]),
        ("filter count bounded", [{"field": "名称", "op": "is_null"}] * 9),
    ):
        query.p = {"table_filters": json.dumps(payload)}
        rejects(name, lambda: query.controls(columns))
    query.p = {"table_sort": '{"field":"金额","direction":"asc; DROP"}'}
    rejects("sort SQL fragments rejected", lambda: query.controls(columns))
    check("system-bound detail parent fields are protected", "订单ID" in protected_fields({"key": "sales.销售订单行表", "pk": "销售订单行ID", "columns": []}))
    from unittest.mock import patch
    query.p = {}
    query.limit, query.offset = 30, 0
    query._table_context = ({"schema": "sales", "name": "客户档案表", "pk": "客户ID", "columns": [{"name": "客户ID", "type": "text"}]}, {"客户ID": "text"}, True)
    with patch.object(Data, "bundle", return_value={"rows": [], "total": [{"count": 10001}]}):
        rejects("export refuses silent truncation above ten thousand matches", lambda: query.bundle({"rows": 'SELECT "客户ID" FROM sales."客户档案表" ORDER BY "客户ID" LIMIT 10000 OFFSET 0'}))


def integration(output, browser):
    from easyerp import ERP
    import server
    erp = ERP()
    run = "table_tools_" + uuid.uuid4().hex[:10]
    output.mkdir(parents=True, exist_ok=True)
    clones = {}
    http = None
    original_init = Data.__init__

    def signature(db):
        from migrate_finance_profiles import snapshot_query
        _, sql = snapshot_query(erp, db, omit_changed=True)
        return erp.sql("SELECT json_agg(x ORDER BY object) FROM (" + sql + ") x", db=db, role="easyerp_read").stdout.strip()

    originals = {mode: erp.c["database"] + ("_ui_demo" if mode == "demo" else "") for mode in ("live", "demo")}
    before = {mode: signature(db) for mode, db in originals.items()}
    try:
        dump = output / "demo-source.dump"
        erp.run("pg_dump", ["-h", "127.0.0.1", "-p", erp.c["port"], "-U", "easyerp_admin", "-w", "-Fc", "-f", dump, originals["demo"]])
        for mode in ("live", "demo"):
            clone = "easyerp_table_test_" + uuid.uuid4().hex[:12]
            clones[mode] = clone
            erp.run("createdb", ["-h", "127.0.0.1", "-p", erp.c["port"], "-U", "easyerp_admin", "-w", "-T", "template0", clone])
            erp.run("pg_restore", ["-h", "127.0.0.1", "-p", erp.c["port"], "-U", "easyerp_admin", "-w", "--exit-on-error", "--single-transaction", "-d", clone, dump])

        def isolated_init(self, params=None):
            original_init(self, params)
            self.db = clones[self.mode]
        Data.__init__ = isolated_init
        class Quiet(server.Handler):
            def log_message(self, *_):
                pass
        http = server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{http.server_port}"

        def call(path, extra=None, payload=None, expected=200, mode="demo", token=None):
            request = Request(base + "/api/" + path + "?" + urlencode({"mode": mode, "start": "2026-01-01", "end": "2026-12-31", "tz": "Asia/Shanghai", **(extra or {})}), data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(), headers={"Content-Type": "application/json", "X-EasyERP-Token": server.WRITE_TOKEN if token is None else token})
            try:
                with urlopen(request, timeout=25) as response:
                    code, body = response.status, response.read()
            except HTTPError as error:
                code, body = error.code, error.read()
            assert code == expected, (path, expected, code, body.decode())
            return body if path == "export" and code == 200 else json.loads(body)

        entry = ManualEntry({"mode": "demo"})
        person_key = "finance.资金流水表"
        ids = entry.ids.allocate(person_key, [run + str(i) for i in range(35)])
        account_id = entry.data.rows('SELECT "账户ID" FROM finance."资金账户档案表" WHERE "币种"=\'CNY\' LIMIT 1')[0]['账户ID']
        amounts = ["2.0000", "10.0000", "9999999999999999.9999", "0.0000", "3.0000"] + ["3.0000"] * 30
        values = [f"({L(key)},{L(account_id)},'2026-11-15T12:00:00+08:00',{L(amount)},'收入',{L(run + '-' + str(i).zfill(2))},{'NULL' if i == 4 else L('0')})" for i, (key, amount) in enumerate(zip(ids, amounts))]
        erp.sql('INSERT INTO finance."资金流水表" ("资金记录ID","账户ID","发生时间","金额","收支方向","交易摘要","平台交易号") VALUES ' + ",".join(values), db=clones["demo"], role="easyerp_app")
        common = {"object": person_key, "search": run, "date_filter": "0", "limit": "2"}
        query = {**common, "table_sort": json.dumps({"field": "金额", "direction": "asc"})}
        result = call("explore", query)
        check("whole-result numeric order precedes pagination", [row["金额"] for row in result["rows"]] == ["0.0000", "2.0000"] and result["total"][0]["count"] == 35)
        check("each selectable row has a snapshot version", all(row["_table_version"].isdigit() for row in result["rows"]))
        query["table_filters"] = json.dumps([{"field": "金额", "op": "gte", "value": "10.0000"}])
        result = call("explore", query)
        check("field filter and count cover records outside the first page", result["total"][0]["count"] == 2 and result["rows"][1]["金额"] == "9999999999999999.9999")
        exported = list(csv.DictReader(io.StringIO(call("export", query).decode("utf-8-sig"))))
        check("CSV matches full filtered count and order with exact decimals", len(exported) == 2 and [row["资金记录ID"] for row in exported] == [row["资金记录ID"] for row in result["rows"]] and exported[1]["金额"] == "9999999999999999.9999" and not any(key.startswith("_") for key in exported[0]))
        nulls = call("explore", {**common, "table_filters": '[{"field":"平台交易号","op":"is_null"}]'})
        check("NULL is filtered separately from exact zero", nulls["total"][0]["count"] == 1 and nulls["rows"][0]["资金记录ID"] == ids[4])
        rows = call("explore", {**common, "limit": "100"})["rows"]
        records = [{"id": row["资金记录ID"], "version": row["_table_version"]} for row in rows[:2]]
        payload = {"request_id": run + "_bulk", "object": person_key, "field": "金额", "value": "1234567890123456.1234", "records": records}
        result = call("entry/bulk", payload=payload)
        check("batch commits exact decimals and reports atomic result", result["count"] == 2 and result["atomic"] and all(row["values"]["金额"] == "1234567890123456.1234" for row in result["records"]))
        check("replaying a committed request returns the original batch", call("entry/bulk", payload=payload) == result)
        call("entry/bulk", payload={**payload, "value": "1"}, expected=409)
        check("idempotency key cannot be reused with changed content")
        def batch_targets():
            return [{"id": key, "version": entry.record(person_key, key, include_children=False)["version"]} for key in ids[:2]]
        targets = batch_targets()
        entry.save({"request_id": run + "_concurrent", "object": person_key, "operation": "update", "id": ids[1], "version": targets[1]["version"], "values": {"平台交易号": "concurrent"}})
        old = entry.record(person_key, ids[0])["values"]["交易摘要"]
        failure = {"request_id": run + "_conflict", "object": person_key, "field": "交易摘要", "value": "不能部分保存", "records": targets}
        error = call("entry/bulk", payload=failure, expected=409)
        check("a stale row rolls back every earlier row and has clear failure", entry.record(person_key, ids[0])["values"]["交易摘要"] == old and "整批未保存" in error["error"])
        invalid = {**failure, "request_id": run + "_constraint", "field": "金额", "value": "-1", "records": batch_targets()}
        call("entry/bulk", payload=invalid, expected=400)
        check("SQL constraints roll back the entire batch", entry.record(person_key, ids[0])["values"]["金额"] == "1234567890123456.1234")
        call("entry/bulk", payload={**invalid, "request_id": run + "_scale", "value": "1.00001"}, expected=400)
        call("entry/bulk", payload={**invalid, "request_id": run + "_pk", "field": "资金记录ID", "value": "X001"}, expected=400)
        call("entry/bulk", payload={**invalid, "request_id": run + "_size", "records": batch_targets() * 51}, expected=400)
        call("entry/bulk", payload={**invalid, "request_id": run + "_duplicate", "records": [batch_targets()[0]] * 2}, expected=400)
        call("entry/bulk", payload={**invalid, "request_id": run + "_token"}, expected=403, token="wrong")
        check("precision, PK, batch size, duplicates and write token are protected")
        concurrent = {**failure, "request_id": run + "_parallel", "records": batch_targets(), "value": run + "并发幂等验收"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda _: call("entry/bulk", payload=concurrent), range(2)))
        count = erp.sql("SELECT count(*) FROM erp_ops.frontend_entry_audit WHERE request_id=" + L(concurrent["request_id"]), db=clones["demo"], role="easyerp_read").stdout.strip()
        check("concurrent identical requests produce one audit and one result", replies[0] == replies[1] and count == "1")
        blank = {**failure, "request_id": run + "_empty", "records": batch_targets(), "field": "平台交易号", "value": ""}
        result = call("entry/bulk", payload=blank)
        check("explicit empty optional text stays empty text", all(row["values"]["平台交易号"] == "" for row in result["records"]))
        result = call("entry/bulk", payload={**blank, "request_id": run + "_null", "records": batch_targets(), "value": None})
        check("explicit NULL stays NULL without schema changes", all(row["values"]["平台交易号"] is None for row in result["records"]))
        call("entry/bulk", payload={**blank, "request_id": run + "_required", "field": "金额", "value": None, "records": batch_targets()}, expected=400)
        call("entry/bulk", payload={**blank, "request_id": run + "_reference", "field": "账户ID", "value": "ACCZZZZZZ", "records": batch_targets()}, expected=400)
        missing = batch_targets()
        missing[1] = {"id": "FZZZZZZZZ", "version": "1"}
        call("entry/bulk", payload={**blank, "request_id": run + "_missing", "records": missing, "value": "uncommitted"}, expected=409)
        check("required NULL, invalid foreign keys and missing records fail atomically", entry.record(person_key, ids[0])["values"]["平台交易号"] is None)
        check("live and demo requests stay in separate clones", call("explore", common, mode="live")["total"][0]["count"] == 0)
        for kind in ("orders", "workorders", "funds"):
            listing = call("list", {"kind": kind})
            check(kind + " business list returns whole-result query metadata", listing["_table_tools"]["scope"] == "all_matches")
            empty_csv = list(csv.reader(io.StringIO(call("export", {"kind": kind, "search": run + "_no_matches"}).decode("utf-8-sig"))))
            check(kind + " empty CSV retains complete query headers", len(empty_csv) == 1 and empty_csv[0] == [col["name"] for col in listing["_table_tools"]["columns"]])
        for key in ("production.库存盘点表", "production.采购订单表", "production.仓库档案表"):
            call("explore", {"object": key, "date_filter": "0"})
            check(key + " derived display projection executes")
        def create(key, values, children=None):
            data = {"request_id": uuid.uuid4().hex, "object": key, "values": values}
            if children is not None:
                data["children"] = children
            return entry.save(data)["records"]
        subject = create("legal.公司主体档案表", {"公司名称": run, "统一社会信用代码": run, "注册地址": "隔离测试", "有效状态": "有效"})[0]["id"]
        policy = create("finance.会计政策表", {"政策名称": run, "政策版本": "1", "适用准则": "隔离测试", "生效日期": "2026-01-01"})[0]["id"]
        account = create("finance.会计科目表", {"主体ID": subject, "科目代码": run, "科目名称": run, "分类": "测试"})[0]["id"]
        person = create("finance.人员档案表", {"姓名": run, "部门": "财务"})[0]["id"]
        voucher = create("finance.会计凭证表", {"主体ID": subject, "凭证日期": "2026-11-15", "所属月份": "2026-11-01", "凭证号": run, "摘要": run, "状态": "草稿", "政策ID": policy, "确认人ID": person}, [{"object": "finance.会计分录表", "values": {"行号": str(i+1), "科目ID": account, "借方金额": "1" if i == 0 else "0", "贷方金额": "0" if i == 0 else "1", "币种": "CNY"}} for i in range(2)])[0]
        entry.save({"request_id": run + "_post", "object": "finance.会计凭证表", "operation": "update", "id": voucher["id"], "version": voucher["version"], "values": {"状态": "已过账"}})
        posted = entry.record("finance.会计凭证表", voucher["id"], include_children=False)
        call("entry/bulk", payload={"request_id": run + "_posted", "object": "finance.会计凭证表", "field": "摘要", "value": "不能覆盖", "records": [{"id": voucher["id"], "version": posted["version"]}]}, expected=400)
        check("posted voucher protection survives batch editing", entry.record("finance.会计凭证表", voucher["id"])["values"]["摘要"] == run)
        if browser:
            env = dict(os.environ, EASYERP_URL=base, EASYERP_TABLE_OUTPUT=str(output), EASYERP_TABLE_RUN=run, EASYERP_TABLE_IDS=json.dumps(ids))
            subprocess.run(["node", str(ROOT / "tests/test_table_tools.cjs")], cwd=ROOT, env=env, check=True)
    finally:
        if http:
            http.shutdown()
            http.server_close()
        Data.__init__ = original_init
        for clone in clones.values():
            if not clone.startswith("easyerp_table_test_") or len(clone) != len("easyerp_table_test_") + 12:
                raise RuntimeError("Unsafe cleanup target")
            erp.run("dropdb", ["-h", "127.0.0.1", "-p", erp.c["port"], "-U", "easyerp_admin", "-w", "--if-exists", "--force", clone])
        after = {mode: signature(db) for mode, db in originals.items()}
        check("original live and demo business signatures are unchanged", before == after)
        (output / "backend-results.json").write_text(json.dumps({"checks": passed, "source_databases_unchanged": before == after, "clones": clones, "cleanup": "only exact random clones dropped", "complete": sys.exc_info()[0] is None}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration", action="store_true")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    unit()
    if args.integration:
        if args.out is None:
            parser.error("--integration requires --out")
        integration(args.out.resolve(), args.browser)
