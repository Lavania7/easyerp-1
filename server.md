# easyERP PostgreSQL 远程服务器说明

检查日期：2026-10-24。项目目录：`D:\projx\demo\easyerp-1`。

## 结论与本次范围

**可以让其他电脑连接现有数据库。PostgreSQL 本身就是数据库服务器，原生提供远程连接、独立用户、权限控制和当前连接监控。** 本项目的 SQL 不需要为此改写，也不需要另造 SQL 服务程序。按照“PostgreSQL 已有此功能则完成 server.md”的要求，本次仅新增本说明。

“仅启动服务器”可用已有 PostgreSQL 的 `pg_ctl.exe`；“显示谁在连接”可用 `pg_stat_activity`、`psql` 自动刷新，或已有 pgAdmin 的会话页面。`dashboard.exe` 和 `sqlview.exe` 仍用于打开本机工作台与 SQL 界面。

本次没有执行以下配置示例，没有创建远程账号、开放端口、启动或重启正式实例。远程访问尚未启用，也没有完成另一台电脑的连接验收。

## 本项目检查结果

| 项目 | 本次实查结果 |
| --- | --- |
| PostgreSQL | 已安装 18.4，程序目录 `E:\PostgreSQL18\bin` |
| 正式库 / 演示库 | 配置库名 `easyerp_v02`；代码中的演示库名为 `easyerp_v02_ui_demo`；本次未联网查询库内状态 |
| 集群目录 | `D:\projx\demo\easyerp-1\var\pgdata` |
| 数据库端口 | `55433` |
| 监听地址 | `127.0.0.1`，目前仅本机 |
| 客户端认证 | HBA 仅有 `host all all 127.0.0.1/32 scram-sha-256` |
| 连接与加密设置 | `max_connections=50`、`password_encryption=scram-sha-256`、`ssl=off` |
| 当前服务状态 | `pg_ctl status` 返回 `no server running`；检查时未发现本机 55433、8092、8093 的 TCP 监听 |
| 当前连接日志设置 | `log_connections` 为空、`log_disconnections=off`、`logging_collector=off`、`log_min_messages=warning` |
| SQL 文件校验 | 调用现有 `ERP.verify_files()`：六个 SQL 文件与规范/清单的静态哈希校验通过；本次未执行建表、迁移或业务 SQL |
| 远程能力判断 | 现有 PostgreSQL 表、视图和约束可通过同一 PostgreSQL 协议访问；远程可达性取决于监听、网络、认证和权限 |
| 网页访问边界 | `frontend/server.py`、pgAdmin 启动配置均绑定 `127.0.0.1`；工作台另有 Host、Origin、令牌校验 |
| 图形连接监控 | 已安装 pgAdmin 的 Dashboard 源码含 Sessions，会查询 `pg_stat_activity`；本次未打开浏览器验收 |

配置值由 `postgres.exe -D ... -C 参数名` 只读解析，并核对配置文件。**这是停机状态下的配置检查，不是正在运行实例的 `SHOW` 结果。** 初始 `git status --short` 为空。

## 1. 仅启动数据库服务器

在服务器电脑、拥有本项目数据目录权限的 Windows 用户下打开 PowerShell。以下代码只控制这个已有集群，不初始化数据库，也不启动工作台或 pgAdmin：

```powershell
Set-Location -LiteralPath 'D:\projx\demo\easyerp-1'
$ErrorActionPreference = 'Stop'
$erpRoot = (Get-Location).Path
$erpConfig = Get-Content -LiteralPath .\config.json -Raw -Encoding UTF8 | ConvertFrom-Json
$pgBin = $erpConfig.postgres_bin
if ($env:EASYERP_PG_BIN) { $pgBin = $env:EASYERP_PG_BIN }
$pgCtl = Join-Path $pgBin 'pg_ctl.exe'
$pgData = Join-Path $erpRoot 'var\pgdata'
$pgLog = Join-Path $erpRoot ('var\log\server-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.log')
if (-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))) {
    throw '找不到已有集群；请核对目录，不要初始化或重建正式库。'
}
& $pgCtl -D $pgData status
$pgStatus = $LASTEXITCODE
if ($pgStatus -eq 3) {
    New-Item -ItemType Directory -Path (Split-Path $pgLog -Parent) -Force | Out-Null
    & $pgCtl -D $pgData -l $pgLog -w -t 45 start
    if ($LASTEXITCODE -ne 0) { throw "数据库启动失败，请检查 $pgLog" }
} elseif ($pgStatus -ne 0) {
    throw "无法确认集群状态，pg_ctl 退出码为 $pgStatus"
}
.\bin\easyerp-db.ps1 status
```

最后的状态输出应指向本项目 `var\pgdata`、正式库及 `55433`；若不相符，先查清实例归属。端口被其他实例占用时不要停止其他实例，也不要更换到其他数据库继续配置。

首次按当前配置启动仍然仅允许本机连接。完成下一节配置并重启后，同一启动命令才会同时接受指定远程地址的连接。关闭 PowerShell 或客户端不会自动停止数据库。

项目原有 `.\bin\easyerp-db.ps1 start` 也只启动数据库相关功能，但会额外检查凭据、角色和库的安装状态，必要时初始化或安装；严格只启动已有集群时采用上面的原生命令。

## 2. 首次启用远程连接

下例采用**两台电脑已接入同一加密 VPN**的方式。先确认真实网络，再替换所有示例地址：服务器 VPN 地址 `10.66.0.1`、张三电脑 VPN 地址 `10.66.0.20`、个人账号 `erp_remote_zhang`。这些不是本机实查地址。VPN 的建立及路由需先完成；服务器的该地址应固定且启动时已存在。

现有 `ssl=off`，SCRAM 认证并不加密后续业务数据。因此此例依靠 VPN 加密传输。若采用无 VPN 的直接网络连接，应另行配置 PostgreSQL TLS、证书及 `hostssl`，客户端使用 `sslmode=verify-full`；不能只将此例端口映射到公网就视为完成部署。参见 [PostgreSQL TLS](https://www.postgresql.org/docs/18/ssl-tcp.html)。

### 2.1 核对、备份

先按第 1 节启动现有实例，然后：

```powershell
.\bin\easyerp-db.ps1 backup
if ($LASTEXITCODE -ne 0) { throw '备份失败，停止后续配置。' }
$serverBackup = Join-Path $erpRoot ('backups\server-config-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $serverBackup | Out-Null
foreach ($name in @('postgresql.conf','postgresql.auto.conf','pg_hba.conf')) {
    Copy-Item -LiteralPath (Join-Path $pgData $name) -Destination (Join-Path $serverBackup $name)
}
.\bin\easyerp-db.ps1 shell -Role easyerp_admin
```

最后一条打开本机管理员 `psql`；密码由现有受保护文件读取。在这个窗口中先确认：

```sql
SELECT current_database(), current_user, current_setting('data_directory');
SHOW port;
SHOW listen_addresses;
```

应为 `easyerp_v02`、`easyerp_admin` 和本项目数据目录。备份命令保存数据库；配置另由上述复制保留。数据库转储不包含新建角色及其密码，之后新增的角色需单独记录受保护的授权与恢复方案。保留现有 `.secrets`，不要将其发给远程用户。

### 2.2 每人建立独立账号，先开放只读

仍在管理员 `psql` 中，逐条执行：

```sql
CREATE ROLE erp_remote_zhang LOGIN INHERIT
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT 5;
GRANT easyerp_read TO erp_remote_zhang WITH INHERIT TRUE;
ALTER ROLE erp_remote_zhang IN DATABASE easyerp_v02
    SET default_transaction_read_only = on;
```

然后在同一 `psql` 窗口设置该人的密码，交互输入两次，不把密码写进 SQL 文件、命令参数或日志：

```psql
\password erp_remote_zhang
```

这是首次建号示例，账号已存在时先核对原权限，不重复 `CREATE ROLE`。其他人使用各自账号及密码，逐人增加 HBA 和防火墙允许地址。

此方案复用项目代码为 `easyerp_read` 定义的对象授权；启用时须核对实际权限。`default_transaction_read_only` 是辅助默认值，不能代替权限隔离。该组的权限设计覆盖六部门业务数据，**不等于按部门或按人员隔离数据**。需要更小范围时应另建权限组并逐对象授权。不要向外分发 `easyerp_admin`、`easyerp_app` 或现有共享密码。

当前配置的 50 个连接是整个实例的上限，正式库、演示库、网页服务和监控共同占用；一个人可能打开多条连接，不能据此认定支持 50 人同时使用。上线人数需结合连接池、查询负载和备份维护实测。

若将来需要远程业务录入，须明确写入权限及审计路径。直接 SQL 写表不会经过 `frontend/entry.py` 的保存服务，因而不能自动获得该服务的全部幂等、冲突检测和业务审计；本说明采用只读接入。

### 2.3 配置监听、认证与防火墙

仍在管理员 `psql` 中，单独执行以下语句，不放入事务：

```sql
ALTER SYSTEM SET listen_addresses = '127.0.0.1,10.66.0.1';
```

本项目的 `postgresql.auto.conf` 已设置本机监听，且其优先级高于 `postgresql.conf`，所以只修改后者可能不生效。上面的 `ALTER SYSTEM` 会更新自动配置；现有项目启动代码仅在新集群初始化时写入初始配置。参见 [参数配置与覆盖规则](https://www.postgresql.org/docs/18/config-setting.html)。

用编辑器在 `var\pgdata\pg_hba.conf` 保留原行，再追加第二行；不要将文件替换成只有远程规则的版本：

```text
host all         all               127.0.0.1/32   scram-sha-256
host easyerp_v02 erp_remote_zhang  10.66.0.20/32  scram-sha-256
```

只允许指定数据库、个人账号、客户端地址。未匹配的远程连接会被拒绝。规则按首次匹配处理；Windows 上 HBA 更改会影响后续新连接，因此先备份、保留原本机规则。参见 [HBA 规则](https://www.postgresql.org/docs/18/auth-pg-hba-conf.html)。

在本机管理员 `psql` 中检查文件解析结果，结果应为空：

```sql
SELECT sourcefile, sourceline, name, error
FROM pg_file_settings WHERE error IS NOT NULL;
SELECT line_number, error
FROM pg_hba_file_rules WHERE error IS NOT NULL;
```

在**管理员权限的 PowerShell** 中，针对实际 VPN 地址设置 Windows 入站规则；这一步无需停库：

```powershell
New-NetFirewallRule -Name 'EasyERP-PG-Remote-Zhang' -DisplayName 'easyERP PostgreSQL Zhang VPN' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 55433 `
    -LocalAddress '10.66.0.1' -RemoteAddress '10.66.0.20' -Profile Any
```

规则只覆盖此服务器地址、客户端地址和数据库端口；如已有同名规则先核对，不重复添加。云主机还需检查安全组及 VPN 路由。数据库连接不需要共享项目目录或启动 8092/8093。

退出管理员 `psql`（输入 `\q`），回到第 1 节的 PowerShell。监听地址变更需要重启，安排所有用户停止操作后执行；`fast` 会断开现有连接并回滚未提交事务：

```powershell
& $pgCtl -D $pgData -l $pgLog -m fast -w -t 45 restart
if ($LASTEXITCODE -ne 0) { throw "数据库重启失败，请检查 $pgLog" }
.\bin\easyerp-db.ps1 status
Get-NetTCPConnection -State Listen -LocalPort 55433 |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

确认包含 `127.0.0.1` 与实际 VPN 地址。PostgreSQL 在部分地址绑定失败时仍可能启动成功，因此不能只看“启动成功”。仅新增 HBA 规则不要求重启；监听地址则必须重启。参见 [监听设置](https://www.postgresql.org/docs/18/runtime-config-connection.html) 和 [pg_ctl](https://www.postgresql.org/docs/18/app-pg-ctl.html)。

## 3. 其他电脑如何连接

远程用户连接 VPN 后，用自己电脑上的 PostgreSQL 客户端、pgAdmin 或其他支持 PostgreSQL 的工具填写：

| 参数 | 本例 |
| --- | --- |
| Host | 服务器实际 VPN 地址，本例 `10.66.0.1`；不是 `127.0.0.1` |
| Port | `55433` |
| Database | `easyerp_v02` |
| Username | 分配给本人的账号，本例 `erp_remote_zhang` |
| Password | 本人的独立密码 |
| application_name | 可选标识，如 `zhang-laptop`；辅助识别，不能代替账号身份 |

例如在客户端电脑的 PowerShell 中执行，`psql.exe` 按客户端实际安装路径调用：

```powershell
Test-NetConnection -ComputerName '10.66.0.1' -Port 55433
psql.exe -X -W -P pager=off -d 'host=10.66.0.1 port=55433 dbname=easyerp_v02 user=erp_remote_zhang application_name=zhang-laptop connect_timeout=5'
```

连接后核对目标及自身身份：

```sql
SELECT current_database(), session_user, current_user,
       inet_server_addr(), inet_server_port(), inet_client_addr();
SHOW transaction_read_only;
```

`Test-NetConnection` 成功只说明 TCP 可达；实际登录、目标库、账号权限仍需用后面的连接确认。继续执行项目 `sql\常用查询.sql` 中的只读业务查询，核对可见范围，不要在正式库用写入业务数据来测试。

## 4. 显示谁在连接 SQL 服务器

### 自动刷新的原生监控窗口

在服务器项目目录打开另一个 PowerShell，执行：

```powershell
.\bin\easyerp-db.ps1 shell -Role easyerp_admin
```

在该管理员 `psql` 窗口粘贴以下查询，并在最后输入 `\watch 3`。它每 3 秒重新查询，Ctrl+C 停止刷新，`\q` 退出：

```psql
SELECT a.pid AS "连接PID", a.datname AS "数据库", a.usename AS "登录账号",
       a.client_addr AS "来源IP", a.client_port AS "来源端口",
       a.application_name AS "客户端", a.backend_start AS "连接时间",
       a.state AS "状态", a.wait_event_type AS "等待类型",
       COALESCE(s.ssl, false) AS "数据库TLS"
FROM pg_stat_activity AS a
LEFT JOIN pg_stat_ssl AS s ON s.pid = a.pid
WHERE a.backend_type = 'client backend'
  AND a.pid <> pg_backend_pid()
ORDER BY a.datname, a.usename, a.backend_start;
\watch 3
```

这里查看该实例的所有客户端，包括正式库、演示库和其他管理连接；不显示查询文本。`active` 是正在执行命令，`idle` 是保持连接但当前没有执行命令，`idle in transaction` 是事务仍未结束。VPN 例中的“数据库TLS”可能为 false，它仅表示数据库协议是否使用 TLS，不表示 VPN 是否加密。

`pg_stat_activity` 是当前会话快照；断开后该行消失，轮询也可能看不到很短的连接。客户端程序名由客户端提供，IP 可能是 VPN、代理或 NAT 地址；**独立登录账号与人员的对应表才是识别人员的基础**。网页服务或连接池使用共享账号时，数据库只能显示服务账号，不能据此识别每位网页访问者。参见 [PostgreSQL 会话统计](https://www.postgresql.org/docs/18/monitoring-stats.html) 与 [psql 自动刷新](https://www.postgresql.org/docs/18/app-psql.html)。

管理员可看到完整会话详情；普通账号对其他角色的许多会话字段无权查看。确需独立监控人员时，另建个人监控账号并授予 `pg_read_all_stats`，同时配置其登录权限和允许来源；此权限会暴露其他会话的查询等敏感信息，不分配给普通远程只读用户。

### 使用已有 pgAdmin 图形界面

本机双击 `sqlview.exe`，在左侧选中服务器或数据库，再打开 Dashboard（仪表盘）的 Server activity / Sessions（会话）。界面名称随版本和语言变化。若希望保留“只启动数据库”的运行方式，使用上一段 `psql` 即可。

项目预设 pgAdmin 连接使用 `easyerp_app`，对其他角色的详情有权限限制。完整监控优先用本机管理员 `psql`，或由运维在本机 pgAdmin 单独注册合适的监控连接；不要把现有预设业务连接改成超级管理员。此图形入口已通过已安装源码确认存在，本次未作页面操作验证。

### 需要连接历史时

当前配置未启用成功连接/断开日志。若需要历史记录，在本机管理员 `psql` 单独执行以下管理语句：

```sql
ALTER SYSTEM SET log_connections = 'authorization';
ALTER SYSTEM SET log_disconnections = on;
ALTER SYSTEM SET log_line_prefix = '%m [%p] user=%u db=%d app=%a client=%r ';
SELECT pg_reload_conf();
```

`log_min_messages` 保持现有 `warning` 即可，服务端这个级别包含 LOG 消息。上述设置用于之后的新连接，不会补回过去记录。当前 `logging_collector=off`，按第 1 节启动时日志输出到传给 `-l` 的实际文件；项目启动脚本另用时间戳日志。应安排日志轮转、留存和访问权限。连接历史不等于每条业务修改的审计记录。参见 [PostgreSQL 连接日志](https://www.postgresql.org/docs/18/runtime-config-logging.html)。

## 5. 验收、退出与回退

启用配置后，从另一台电脑验收：允许的个人账号能登录并查询授权数据；错误密码、未授权来源、未允许的数据库均被拒绝；服务器监控窗口能看到该账号、来源地址，断开后记录消失；原本机工作台及 SQL 界面仍能连接。**这些跨机验收本次均未执行。**

常见排查：TCP 不通时看 VPN 路由、监听和防火墙；出现 `no pg_hba.conf entry` 时核对服务器实际看到的来源 IP、库名和账号；密码失败时检查个人账号及密码，不改成 `trust`；登录后无权查询时核对对象授权，不直接授予管理员。

撤回远程开放时：

1. 本机管理员执行 `ALTER ROLE erp_remote_zhang NOLOGIN;` 阻止其新登录；必要时按监控列表准确确认会话 PID，再执行 `SELECT pg_terminate_backend(实际PID);`。NOLOGIN 不会自行断开现有会话。
2. 移除本次新增 HBA 行，在管理员 PowerShell 执行 `Remove-NetFirewallRule -Name 'EasyERP-PG-Remote-Zhang'`；保留原本机 HBA 行。
3. 本机管理员单独执行 `ALTER SYSTEM SET listen_addresses = '127.0.0.1';`，安排重启并核对监听。账号及历史记录可保留，不必删库或重建集群。

若远程配置后启动失败，在确认该集群已停止时，用第 2.1 节留存的配置副本恢复本次变更，再按第 1 节启动；先排查日志，不删除 `var\pgdata`。配置备份只恢复到对应文件，不覆盖业务数据或凭据。

停止整个本项目数据库可执行 `.\bin\easyerp-db.ps1 stop`，它会影响本机工作台、演示库和全部远程连接，不是只关闭某一个人的远程访问。

如果以后需要开机后台运行，PostgreSQL 原生 `pg_ctl register` 可注册 Windows 服务，但需要安排专用服务身份、数据目录权限及与现有启动方式的协调，本次未注册系统服务。另建远程主机部署时，还需安装匹配版本、备份恢复正式数据及角色并重新配置网络；不是只复制某个 exe 即可运行。
