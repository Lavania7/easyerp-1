# easyERP 0.2 数据库使用说明

工作目录：`D:\projx\demo\easyerp-0.2`。本机部署日期：2026-10-22。

## 1. 已上线内容与范围

数据库名称 `easyerp_v02`，地址 `127.0.0.1:55433`，PostgreSQL 18.4，UTF-8。
独立数据目录 `var\pgdata`，与本机原有 5432 实例分开。
仅接受本机连接；本次没有指定远程服务器，因此上线范围是当前 Windows 电脑。

依据本目录 readme.md，原样建立 6 个业务 schema、146 张业务表、475 个外键、15 个规范视图。
业务字段、中文对象名、精度、枚举、可空性均沿用原文；readme.md 未修改。
附加 `erp_ops` schema 保存版本与迁移历史，并提供 3 个运维核对视图及凭证过账保护。
这些附加对象不作为第二套业务主录。

正式库初始不含业务数据。测试样本只存在于临时测试库及其备份中，测试库完成后删除。
数据库配有轻量查询前端（见第 8 节）；录入仍通过数据库工具进行，Excel 同步和银行/平台自动采集接口尚未实现。

## 2. 开始使用

在 PowerShell 中执行：

```powershell
Set-Location 'D:\projx\demo\easyerp-0.2'
.\bin\easyerp-db.ps1 status
.\bin\easyerp-db.ps1 check
.\bin\easyerp-db.ps1 shell
```

如果 PowerShell 阻止脚本，可对本次调用使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\bin\easyerp-db.ps1 start
```

进入 SQL 命令行后，例如：

```sql
SELECT * FROM sales."订单与履约交付表" LIMIT 20;
SELECT * FROM finance."账户核对与差异表";
SELECT * FROM erp_ops."业务核对问题";
SELECT * FROM erp_ops."数量版本核对问题";
```

`\q` 退出；`\dn` 查看 schema；`\dt finance.*` 查看财务表；`\d finance."资金流水表"` 查看字段。
退出 SQL 命令行不会停止数据库。

| 操作 | 命令 |
|---|---|
| 首次初始化，或启动现有库 | `.\bin\easyerp-db.ps1 start` |
| 查看运行信息 | `.\bin\easyerp-db.ps1 status` |
| 结构检查及业务问题列表 | `.\bin\easyerp-db.ps1 check` |
| 隔离集成测试及样本恢复测试 | `.\bin\easyerp-db.ps1 test` |
| SQL 命令行，默认录入账户 | `.\bin\easyerp-db.ps1 shell` |
| 只读 SQL 命令行 | `.\bin\easyerp-db.ps1 shell -Role easyerp_read` |
| 导入 SQL 文件 | `.\bin\easyerp-db.ps1 import-sql 'D:\data\approved.sql'` |
| 生成正式库备份 | `.\bin\easyerp-db.ps1 backup` |
| 将备份恢复到临时库验证 | `.\bin\easyerp-db.ps1 restore-test 'D:\完整路径\文件.dump'` |
| 导出全库业务表 CSV 和 ZIP | `.\bin\easyerp-db.ps1 export` |
| 停止本项目实例 | `.\bin\easyerp-db.ps1 stop` |
| 安装当前用户登录启动 | `.\bin\easyerp-db.ps1 install-startup` |
| 取消当前用户登录启动 | `.\bin\easyerp-db.ps1 remove-startup` |

`init` 与 `start` 均可重复执行，不删除已有记录。不提供清空或 reset 命令。
`check` 报告 `structure: PASS` 只说明结构检查通过；必须同时查看 `business_issue_count` 和问题明细。
空库问题数为零，不代表真实业务已经核实或业务流程已经验收。

也可以直接执行一次查询，中文和字段双引号在 Windows PowerShell 5.1 中可用：

```powershell
$sql = @'
SELECT "资金记录ID", "金额", "用途差额", "分摊差额"
FROM erp_ops."资金核对";
'@
.\bin\easyerp-db.ps1 query $sql -Role easyerp_read
```

## 3. 登录账户与连接工具

| 用途 | 用户 | 权限 |
|---|---|---|
| 日常录入 | `easyerp_app` | 六部门业务表查询、增改删；不能建表、TRUNCATE 或修改运维版本表 |
| 查询与导出 | `easyerp_read` | 业务表、业务视图和核对视图只读 |
| 运维 | `easyerp_admin` | 本独立集群管理员，用于建库、测试和备份 |

三个账户均使用随机密码和 SCRAM-SHA-256 认证。脚本自动读取本目录 `.secrets\pgpass.conf`，不需要在命令行填写密码。
如使用 DBeaver、pgAdmin 等工具，填写上述地址、端口、库名和相应用户，密码由当前 Windows 用户在 `.secrets\credentials.json` 内查看。
不要将该文件、密码或整个 `.secrets` 文件夹发给其他人或提交到版本控制。
凭据、数据目录、日志、备份与导出目录均限制为当前 Windows 用户和 SYSTEM 访问。

当前录入账户具有六部门权限，尚未按具体人员和部门分配账户；多人使用前应单独设计授权。
数据库默认时区为 UTC，带时区事件保留实际时刻。
readme.md 所说的“主体约定时区”须由业务确认，并在库存截止、报表期间等业务查询中明确转换。
本次没有替主体推定业务时区。

## 4. 日常录入顺序与数据规则

先建立实际存在的主体、人员、计量单位、产品/物料主数据和版本，再录入交易和事件。
销售通常按渠道、客户、订单、订单行、发货事件依次建立；采购通常按供应商、采购行、到货、验收、库存事件依次建立。
后续业务尚未发生时保留可空引用，事件发生后再补充；不能为了满足外键虚构业务记录。
所有外键即时检查，中文名称必须用双引号，跨部门名称始终带 schema。

ID 为文本并在各自表内唯一；由录入/导入程序生成，数据库不会自动编造业务编号。
月份采用当月第一天；期间开始、结束均包含当天；有效期的失效日不含当天。
资金金额为非负数，收支方向独立保存。红字发票及收入成本调整的符号按已核定口径填写。
金额与数量采用精确 numeric，计算和导入时避免先转换为二进制浮点数。
未知金额、成本、库存基准和换算保留 NULL/待补；不得以 0 代替未知值。

`import-sql` 默认以录入账户执行，并在一个事务中提交，失败回滚。
文件应为可信的 UTF-8 SQL 语句，不含 `BEGIN/COMMIT/ROLLBACK`、psql 元命令或自行改变事务边界的内容。
CSV 可在 SQL 命令行中使用 `\copy`，务必列出目标列、核对来源与编码；本次没有预设各平台 CSV 字段映射。
原文件路径、来源行号、文件校验值等应按对应登记表留存。

凭证录入应先保存草稿，在同一事务中录入完整分录，最后修改为“已过账”并提交。
提交时核对：分录非空、每个币种借贷平衡、科目主体一致、所属月份与凭证日期一致，以及确认人已填写。
已过账凭证与分录不可直接覆盖或删除，科目所属主体也不能被改写；差错通过新调整凭证处理。
这项技术过账检查不代替会计人员确认收入、税额、成本及政策适用性。

## 5. 已实现的核对及使用边界

`erp_ops."资金核对"` 分别预聚合用途与结算，防止多组一对多关联放大金额；没有来源记录时保留 NULL。
视图标示“已确认重复”和“已确认内部划转”，做业务汇总时需按核定含义处理，不能把所有流水直接视为收入或费用。

`erp_ops."业务核对问题"` 提示：用途超额或核定信息缺失、分摊超额及未核定用途、销售/采购结算币种不一致、
划转收支方向、发票金额及税额分摊差异、计价工时超量、投入归属比例超额、发布文件项目/产品不匹配、
工单引用未发布批次、同单位到货/验收/普通及组合发货超量，以及组合发货归属错误。
`erp_ops."数量版本核对问题"` 提示验收/发货单位不一致和工单产品版本不匹配。
这些是查询时生成的核对问题，不会把候选自动改成“已核定”，也不会阻止所有相关写入。
部分分摊可能暂时有差额，需要继续处理；工时未超量也不证明不存在语义上的重复计价。

readme.md 未明确的政策和完整业务实现仍需后续确认，包括：

- 财务三表归集、结账、税务、汇兑、成本与客户分类统计的核定规则和生成程序。
- 依主体业务时区、唯一库存基准和有效单位换算生成库存结存；基准或换算缺失时不得给出确定结存。
- 全部库存来源事件之间的数量/物品一致性，以及领退料、委外保管与实际耗用的完整业务核对。
- 除已过账凭证保护外的版本和已发布业务记录冻结、交付前所有来源状态审核、红字票据适用性审核。
- PDF/说明书内容生成、研发发布包业务装配、原文件路径存在性和登记 SHA256 与实际文件的一致性校验。

`export` 输出一次数据库一致性快照：146 个业务表 CSV、逐文件 SHA256 清单和 ZIP。
CSV 为 UTF-8、带列名，NULL 标记为 `\N`，与空字符串、数字 0 区分；Excel 中请按 UTF-8 导入，并按文本处理 ID。
为兼容 Windows PostgreSQL 的本地文件名处理，CSV 使用 `schema.编号.csv`，`manifest.json` 的 `tables` 项对应完整中文表名。
保留 `INCOMPLETE.txt` 的目录表示导出未完成，不能当作成功交付使用。
导出文件保留当时值，但不会自动登记某个部门的业务交付、批准发布或冻结数据库里的来源行。
正式交付应登记交付ID、版本、截止时间、文件路径及未核事项；修订另建新交付并保留旧文件。

## 6. 备份、恢复与启动维护

每次正式导入或重要修改前运行 `backup`。输出为 `backups\库名-UTC时间.dump` 和同名 JSON 校验信息。
采用 pg_dump 自定义格式；`restore-test` 先核对备份 SHA256，再恢复到随机命名的临时库，运行结构检查后删除临时库。
它不会覆盖正式库。测试样本恢复另外比较全部 146 张业务表的数据签名，结果写入测试报告。

常规 `backup` 不保证覆盖之后新增的数据，也没有自动定时备份或异机副本。
请把需要保留的备份复制到另一受控位置；本地备份不提供整机损坏或时间点恢复保障。
`pg_dump` 不包含数据库角色密码和外部文件；请另行妥善保管角色恢复所需凭据及原始业务文件。

实际故障恢复时先停写并保留原库，恢复到一个新的数据库名称再核对。
以下是管理员手工恢复的示例，替换备份实际路径，不使用 `--clean`：

```powershell
$env:PGPASSFILE = 'D:\projx\demo\easyerp-0.2\.secrets\pgpass.conf'
$env:PGCLIENTENCODING = 'UTF8'
& 'E:\PostgreSQL18\bin\createdb.exe' -h 127.0.0.1 -p 55433 -U easyerp_admin -w -T template0 easyerp_recovered
& 'E:\PostgreSQL18\bin\pg_restore.exe' -h 127.0.0.1 -p 55433 -U easyerp_admin -w --exit-on-error --single-transaction -d easyerp_recovered 'D:\实际备份路径.dump'
```

新名称恢复后应重新检查数据库级 CONNECT 权限、角色授权、数据、外部文件及应用连接；确认后再切换使用。
不要直接替换或删除 `var\pgdata`。

本次配置了当前用户登录后自动启动，启动入口是 Windows 启动文件夹中的 `easyerp-0.2.vbs`。
该入口以隐藏窗口调用 `bin\start-hidden.ps1`，日志在 `var\log\startup.log`。
这是用户登录启动，不是 Windows 系统服务；电脑重启但尚未登录该用户时不保证运行。
手动 `stop` 后会保持停止，直至再次 `start` 或下次登录。

原生 PostgreSQL 启动日志位于 `var\log\时间.log`。端口被其他实例占用时脚本报错，不连接或修改其他实例。
PostgreSQL 路径可通过 `config.json` 或 `EASYERP_PG_BIN` 指定；Python 路径见 `config.json`。
集群建立后不要直接更改端口、库名或目录位置；此类调整应同步服务器配置、凭据匹配规则和启动入口。

## 7. 构建、版本与验证证据

| 路径 | 内容 |
|---|---|
| `readme.md` | 只读建模依据 |
| `bin\build_schema.py` | 按 Markdown SQL 块提取规范 DDL，记录来源行号 |
| `db\001_schemas.sql` 至 `004_views.sql` | 从原文提取的 schema、表、外键与视图 |
| `db\005_operations.sql` | 索引、运维核对、凭证保护 |
| `db\006_quantity_checks.sql` | 单位/版本补充检查与升级审计表 |
| `db\manifest.json` | 原文和 SQL 文件 SHA256、对象数量和来源块索引 |
| `bin\easyerp-db.ps1` | PowerShell 操作入口 |
| `bin\easyerp.py` | 数据库管理工具，无第三方 Python 库依赖 |
| `tests\structure.sql`、`business.sql` | 实际数据库结构及业务集成测试 |
| `reports\test-latest.json` | 最新业务、权限及样本备份恢复结果 |
| `reports\check-latest.json` | 最新正式库结构与业务问题结果 |
| `reports\restore-latest.json` | 最新恢复检查结果 |
| `reports\deployment.json` | 本次上线验证汇总 |

原文 SHA256：`0cb98ec46569d2ee9b746873d495b2b3c251e44077d38954c206ac49544fe0a4`。
`start` 检查构建与已安装版本；不匹配时拒绝静默覆盖。
`build_schema.py` 仅重新生成文件，不会迁移已存在的数据库；更改规范必须先审核并制作迁移。
`migrate` 当前只支持本次明确编写的 006 追加迁移，验证原版本并记录升级历史；不是通用差异自动迁移工具。

本次验证结果以 `reports\deployment.json` 为准，包含实际对象数量、正式库业务行数、启动复验、导出及备份恢复结果。
已验证约束和测试流程不等同于真实企业数据、会计政策或全部业务规则已经验收。

实现参考：[PostgreSQL 18 触发器](https://www.postgresql.org/docs/18/sql-createtrigger.html)、
[SQL 备份与恢复](https://www.postgresql.org/docs/18/backup-dump.html)、
[SCRAM 密码认证](https://www.postgresql.org/docs/18/auth-password.html)。


## 8. 轻量查询前端（2026-10-22）

访问 [经营工作台](http://127.0.0.1:8092/)，详细操作见 [前端说明](frontend/README.md)。
本轮按 dashboard.md 的首版范围完成经营总览、我的工作、订单详情、工单详情和资金结算详情，并接入标准 SQL 视图。
支持查询、期间/币种/文字等筛选、跨部门主录追溯、CSV 导出；不提供录入与修改。

初次进入为正式库；右上角可切换清楚标注的独立演示库。演示数据不写入正式业务库。
正式库未登记的金额、成本及库存继续保留未登记或待核定；毛利口径未确认时不直接显示收入减成本。

前端已在本机启动，端口 8092；未修改数据库端口与登录启动配置。双击入口见第 9 节。
维护重启入口为 `bin\start-frontend.ps1`，可加 `-OpenBrowser` 打开浏览器。
测试报告为 `reports\frontend-tests.json`，页面与 SQL 来源映射、限制及导出规则见前端说明。


## 9. 双击启动入口

项目目录提供 `启动前端.exe` 和 `启动后端SQL.exe`；桌面快捷方式分别为 `easyERP-前端工作台` 和 `easyERP-后端SQL`。
前者自动启动所需服务并打开经营工作台；后者自动启动数据库和 pgAdmin SQL 可视化界面，不需要输入启动命令。

详细步骤见 [启动说明](启动说明.md)。后端可查看表、视图、SQL 定义和查询结果，常用只读 SQL 在 `sql\常用查询.sql`。
后端预设正式库和独立演示库连接，使用已有 `easyerp_app` 账户；SQL 允许修改业务数据，练习请选择演示库。
SQL 管理页面端口为本机 8093，配置保存在本项目 `var\pgadmin`；保留 .exe 与项目目录结构。
启动器冷启动及重复启动测试结果在 `reports\launcher-tests.json`，SQL 查询工具实测结果在 `reports\sql-interface-tests.json`。
