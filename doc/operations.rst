easyERP 运行与维护
==========================


本文合并原根目录 ``launch.md``、``help.md`` 和 ``server.md``，集中说明启动、数据库操作、备份恢复、远程部署与连接监控。当前配置以项目根目录 ``config.json`` 为准；历史验收报告只说明对应时间执行过的检查。


当前正式／演示拓扑（2026-11-15）
--------------------------------

用户已批准并完成阶段A：正式 ``easyerp_v02`` 当前使用 ``127.0.0.1:55434``，集群目录 ``D:\database\easyerp-live\pgdata``；运行根目录 ``D:\database\easyerp-live``，凭据在该目录的 ``.secrets``，正式工作空间为 ``workspace\live.json``，正式导入历史为 ``var\import-interface.sqlite3``。

演示 ``easyerp_v02_ui_demo`` 仍使用 ``127.0.0.1:55433``、项目 ``var\pgdata``、原 ``.secrets`` 和 ``var\workspace\demo.json``。用户仅批准A并要求保留旧源，因此原55433集群中的旧 ``easyerp_v02`` 只作为回滚来源保留；当前正式界面、录入和导入不连接该旧源。未执行阶段B：旧正式库、旧live工作空间、旧SQLite正式检查及旧正式备份/导出文件均保留。

``config.json.database_sources.live``／``demo`` 中的 ``database``、``port``、``data_directory``、``private_directory``、``workspace_directory`` 和 ``runtime_root`` 分别覆盖对应来源的旧顶层默认值。显式配置的演示库名直接使用，不再额外拼接 ``_ui_demo``；缺少来源配置时才沿用旧的共用集群及演示库后缀规则。顶层 ``database=easyerp_v02``／``port=55433`` 当前仅保留兼容，不能据此把55433认作当前正式连接。

数据库工具默认指向配置后的正式来源；``start`` 会启动/核对显式配置的两种来源。SQLview下次配置时分别使用 ``ERP(mode="live")`` 和 ``ERP(mode="demo")`` 的库、端口和受限pgpass路径更新项目连接档案，仍使用 ``easyerp_app``，不保存密码或公开临时会话。本次未启动8093，已运行的旧pgAdmin会话需要重新加载正确档案后使用。

下文旧默认端口、``D:\projx\demo\easyerp-1`` 路径及远程部署片段属于命令示例和历史环境；实际本项目在 ``D:\projx\release\easyerp-1``，连接前以来源配置和实际 ``data_directory`` 核对，不把这些示例当作当前正式连接。阶段A证据在目标 ``migration\restored.json``，状态为 ``cutover``；来源关系图显示保留旧源到当前正式库的真实恢复边。


日常启动
--------


在项目的 ``bin`` 目录双击 ``dashboard.exe`` 打开经营工作台，或双击 ``sqlview.exe`` 打开 pgAdmin SQL 管理界面。启动器根据自身所在的 ``bin`` 定位上一级项目根目录；从其他工作目录启动也使用同一份项目配置。


.. list-table::
   :header-rows: 1
   :widths: auto

   * - 入口
     - 作用
   * - ``bin/dashboard.exe``
     - 启动或复用本项目数据库及网页服务，再打开经营工作台
   * - ``bin/sqlview.exe``
     - 启动或复用本项目数据库及 pgAdmin，再打开 SQL 管理界面
   * - ``bin/start-frontend.ps1 -OpenBrowser``
     - 对应工作台的脚本入口
   * - ``bin/start-backend.ps1 -OpenBrowser``
     - 对应 SQL 管理界面的脚本入口
   * - ``tools/easyerp-db.ps1``
     - 数据库启动、检查、查询、备份及维护


启动过程使用隐藏窗口，失败时显示错误提示。再次双击会复用已就绪服务。关闭浏览器不会停止数据库；需要停止整个实例时使用数据库维护命令。

EXE 依赖本机 Windows .NET Framework、Python、PostgreSQL 和 pgAdmin，并非自带数据库的安装包。保留完整项目目录结构，在桌面使用快捷方式，不单独复制 EXE。启动器源码、图标与构建说明见 `doc/bin/launcher/overview.rst <bin/launcher/overview.rst>`__。


工作台与 SQL 管理
~~~~~~~~~~~~~~~~~~~~~~


工作台默认使用正式数据，左下角数据源菜单可切换清楚标注的独立演示库。企业计划、工作流、数据中心、档案馆及审计入口见 `功能实施说明 <workspace-revision.rst>`__。查询、手工保存和标准 CSV 导入使用同一业务主录；金额、成本、分类、数量及关联未知时保持空缺，不自动认定核定完成。

数据源菜单中的“数据库管理”为独立管理入口。管理窗标注当前“正在使用”的版本，点击其他已就绪数据库后可选择“切换到此数据库”。切换会按需启动所选现有集群，核对实际目录、端口、库名及读取权限，再刷新当前页面；不会初始化、复制或替换原数据库。空白结构模板、创建中及创建失败的版本不能切换。

所选数据库通过页面地址中的 ``db`` 版本标识保留，刷新或重启网页服务后沿用该地址即可继续使用；不同浏览器窗口可选择不同版本。查询、录入、详情、导出、模板、导入历史及计划／审计工作空间均按每次请求的数据库隔离。正式／演示默认配置与迁移记录保持原值，切换保留旧正式库属于查看和使用该旧版本，并不撤销已完成的迁移。关闭旧数据库进程后，可从管理窗再次切换以启动它。切换会刷新页面，尚未保存的输入应先完成保存。

打开 SQLview 后，在 pgAdmin 中选择项目服务器及目标数据库，展开六个业务 schema 查看表；右键数据库打开查询工具，可打开 ``db/queries/常用查询.sql`` 执行只读示例。连接显示名称可能沿用历史版本，以实际库名识别正式库与演示库。预设业务连接使用 ``easyerp_app``，可以修改业务数据；练习使用演示库，正式修改前先备份。


.. list-table::
   :header-rows: 1
   :widths: auto

   * - 服务
     - 当前默认
   * - 工作台
     - ``http://127.0.0.1:8092/``
   * - pgAdmin
     - 本机 ``8093``，通过 SQLview 获取当前会话
   * - 当前正式PostgreSQL
     - ``127.0.0.1:55434``，``easyerp_v02``
   * - 当前演示PostgreSQL
     - ``127.0.0.1:55433``，``easyerp_v02_ui_demo``
   * - 正式数据目录
     - ``D:\database\easyerp-live\pgdata``
   * - 演示数据目录
     - 项目 ``var/pgdata``（同时保留旧正式库供回滚）


两个网页服务仅绑定本机，前端保留 Host、Origin 和保存令牌检查。pgAdmin 的临时会话信息保存在 ``.secrets/pgadmin-runtime.json``，不要公开完整会话地址。日志在 ``var/log/launcher-frontend.log``、``launcher-backend.log``、``frontend.log``、``frontend-error.log``；pgAdmin 使用 ``var/pgadmin`` 独立配置。


数据库命令与权限
----------------


从项目根目录运行，实际项目路径可自行替换：

.. code-block:: powershell

   Set-Location -LiteralPath 'D:\projx\demo\easyerp-1'
   .\tools\easyerp-db.ps1 status
   .\tools\easyerp-db.ps1 check
   .\tools\easyerp-db.ps1 shell -Role easyerp_read


.. list-table::
   :header-rows: 1
   :widths: auto

   * - 操作
     - 命令
   * - 初始化或启动现有实例
     - ``.\tools\easyerp-db.ps1 start``
   * - 查看运行信息
     - ``.\tools\easyerp-db.ps1 status``
   * - 结构与业务核对
     - ``.\tools\easyerp-db.ps1 check``
   * - 隔离集成及恢复测试
     - ``.\tools\easyerp-db.ps1 test``
   * - 业务 SQL 命令行
     - ``.\tools\easyerp-db.ps1 shell -Role easyerp_app``
   * - 只读 SQL 命令行
     - ``.\tools\easyerp-db.ps1 shell -Role easyerp_read``
   * - 已审核 SQL 文件
     - ``.\tools\easyerp-db.ps1 import-sql 'D:\data\approved.sql'``
   * - 备份正式库
     - ``.\tools\easyerp-db.ps1 backup``
   * - 备份隔离恢复验证
     - ``.\tools\easyerp-db.ps1 restore-test 'D:\实际路径\备份.dump'``
   * - 一致性 CSV 导出
     - ``.\tools\easyerp-db.ps1 export``
   * - 停止本项目实例
     - ``.\tools\easyerp-db.ps1 stop``
   * - 安装／取消登录启动
     - ``.\tools\easyerp-db.ps1 install-startup`` / ``remove-startup``


``start`` 和 ``init`` 可重复执行，不清除记录；未提供 reset。它们会检查凭据、角色和安装版本，必要时初始化尚不存在的实例。严格只启动已有集群时，使用后文的原生 ``pg_ctl`` 示例。退出 SQL 命令行用 ``\q``；``\dn`` 查看 schema，``\dt finance.*`` 查看表，``\d finance."资金流水表"`` 查看结构。


.. list-table::
   :header-rows: 1
   :widths: auto

   * - 用途
     - 角色
     - 范围
   * - 查询与导出
     - ``easyerp_read``
     - 业务查询使用只读事务
   * - 业务保存
     - ``easyerp_app``
     - 已授权业务表写入及同事务审计，保留约束与过账保护
   * - 运维
     - ``easyerp_admin``
     - 本独立集群管理、备份、受控迁移


密码由受保护的 ``.secrets`` 文件及 ``PGPASSFILE`` 在服务端读取；不要写入 EXE、命令行、浏览器代码或版本控制。当前工具为本机单用户工作台，尚无按个人分派的登录与分级审批。配置中的 Python、PostgreSQL 路径及 ``EASYERP_PG_BIN`` 覆盖规则见实际脚本。

中文只读查询可使用 PowerShell here-string，避免双引号被命令行破坏：

.. code-block:: powershell

   $erpSql = @'
   SELECT "资金记录ID", "金额", "发生时间"
   FROM finance."资金流水表" LIMIT 20;
   '@
   .\tools\easyerp-db.ps1 query $erpSql -Role easyerp_read


普通业务文件先保留原件，按 `文件导入流程 <import-workflow.rst>`__ 转成标准主录 CSV，再通过共用检查／执行入口；不以直接 SQL 绕过审核、空缺和合并规则。``import-sql`` 留作明确审核过的维护脚本，采用一个事务，文件不另带事务控制或 psql 元命令。


数据语义、核对与导出
--------------------


先登记实际存在的主体、人员、单位、产品物料和版本，再按真实事件引用 ID。付款、到货、验收、库存变动、发票、退款与实物退回各自记录；不凭相似名称猜关联。完整规则见 `全局规则 <global-rules.rst>`__ 和 `SQL 规范 <sql-specification.rst>`__。

金额、数量使用 PostgreSQL numeric 和精确十进制字符串；真实 0、空字符串和 NULL 按接口合同区分。业务事件保存时区，当前工作台按北京时间划分业务日期；所属月份为月首日期，期间开始与结束均包含当天。已过账凭证须满足分录非空、逐币种借贷平衡、主体与期间一致、确认人齐全等约束；差错以新调整记录处理。

``check`` 的结构 PASS 和问题数 0 不等于业务已审核。核对涵盖用途、分摊、币种、重复、划转、凭证、数量、单位和发布版本等关系；缺少核定、成本、完整库存基准或适用换算时保留待核。税务、报表口径、成本政策、完整实物核对及报告结论仍需明确业务依据。

``export`` 导出一次一致性快照，包括业务表 CSV、SHA256 清单及 ZIP。CSV 保留 NULL 的 ``\N``、空字符串和 0，按 UTF-8 导入，编号按文本处理；中文表名与 ASCII 文件名在导出 ``manifest.json`` 中对应。保留 ``INCOMPLETE.txt`` 的目录表示未完成。导出不会自动批准发布、登记业务交付或冻结来源记录。


备份与恢复
----------


正式导入或重要修改前运行 ``backup``，输出 ``backups/库名-UTC时间.dump`` 及同名 JSON 校验信息。它使用 pg_dump 自定义格式；``restore-test`` 核对摘要后恢复到随机临时库验证，不覆盖正式库。数据库备份之外，另行妥善备份 ``var/workspace/`` 中的文件工作流、原始业务文件、导入批次和角色恢复所需凭据。

数据库 dump 不包含角色密码和外部文件。当前工具未实现定时备份或异机副本；按实际留存要求保留受控副本。故障时先停写、保留原库，恢复到新库名核对，不删除或替换 ``var/pgdata``。

以下为管理员手工恢复示例，先核对项目、程序路径和实际备份：

.. code-block:: powershell

   $erpRoot = 'D:\projx\demo\easyerp-1'
   $erpConfig = Get-Content -LiteralPath (Join-Path $erpRoot 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
   $env:PGPASSFILE = Join-Path $erpRoot '.secrets\pgpass.conf'
   $env:PGCLIENTENCODING = 'UTF8'
   & (Join-Path $erpConfig.postgres_bin 'createdb.exe') -h 127.0.0.1 -p $erpConfig.port -U easyerp_admin -w -T template0 easyerp_recovered
   & (Join-Path $erpConfig.postgres_bin 'pg_restore.exe') -h 127.0.0.1 -p $erpConfig.port -U easyerp_admin -w --exit-on-error --single-transaction -d easyerp_recovered 'D:\实际备份路径.dump'


恢复后核对 CONNECT 权限、角色、数据、外部文件与应用连接，再决定切换。当前用户登录启动调用 ``bin/start-hidden.ps1``，记录 ``var/log/startup.log``；这与 Windows 系统服务不同，不保证未登录时运行。


构建、布局与验证
----------------


``tools/build_schema.py`` 从 ``doc/sql-specification.rst`` 提取基础 DDL。RST 中的 ``sql-source-line`` 注释保留历史 SQL 行号，生成文件中的 ``readme.md:行号`` 继续作为原来源标记；清单同时记录当前 RST 行号。规范全文和 SQL 文件都保持严格哈希检查。

只有全部 SQL 文件的哈希完全一致，构建器才记录旧规范哈希与同一构建摘要的兼容关系。文档换格式不改写正式库版本行、不迁移业务结构；真实 SQL 差异仍走受控迁移。``build_schema.py`` 仅生成文件，不升级现有数据库。原有视图删除迁移保留，应用查询通过 ``tools/business_queries.py`` 直接读取主录。

供应商字段升级使用 ``tools/migrate_supplier_profile.py``，默认预览，``--apply`` 才逐库备份并迁移正式库和已有演示库；``--database`` 可指定单库。通用 ``easyerp-db.ps1 migrate`` 也支持此升级。迁移严格验证旧构建、目标集群和旧列结构，在同一事务内锁定主录、保留供应商ID及全部外键，并逐表核对原有业务事实。旧相关文件路径保存在迁移前dump及仅管理员可读的 ``erp_ops.supplier_profile_retired_fields``，不再出现在表单或CSV中。新增字段保持NULL；账户ID为供应商收款账号文本。执行后刷新页面，动态元数据缓存最长60秒更新。

计量单位字段简化使用 ``tools/migrate_unit_profile.py``，默认预览，``--apply`` 才逐库备份并迁移正式库和已有演示库；``--database`` 可指定单库。通用 ``easyerp-db.ps1 migrate`` 也支持此升级，并为旧安装先执行已审核的供应商升级。新建、编辑及CSV只需维护“单位名称”和可选“备注”；单位ID保留并自动生成，25张表的26处单位ID外键和单位换算关系保持不变。旧单位代码和计量维度原值归档到仅管理员可读的 ``erp_ops.unit_profile_retired_fields``，同时保留迁移前dump；备注初始为NULL。迁移在同一事务锁定、逐表对比原有事实和外键，遇到未知依赖整体回滚，不级联删除。执行后刷新页面，动态元数据缓存最长60秒更新。

重建启动器：

.. code-block:: powershell

   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\bin\launcher\build.ps1


构建产物为 ``bin/dashboard.exe`` 与 ``bin/sqlview.exe``；图标资源仍在 ``bin/icons/``。图标校验运行 ``python .\bin\launcher\verify-icons.py``。``bin/*.exe --check`` 启动或复用服务但不打开浏览器；``tests/test_launchers.ps1`` 默认不停止既有服务，只有显式 ``-ColdStart`` 才做冷启动。源码重建不会自动改写桌面快捷方式。

创建入口使用 ``tools/create-shortcuts.ps1``；已有快捷方式迁移／刷新使用 ``tools/refresh-icons.ps1 -UseCurrentProject``，操作前核对目标属于本项目，保留原快捷方式备份。启动报错先查日志和进程归属，不停止其他项目实例。


远程部署与连接监控
------------------


以下内容由原 ``server.md`` 合并，保留远程配置示例和回退步骤。原 2026-10-24 的进程状态和环境检查为历史快照；不代表当前实例状态。本次目录整理没有执行远程账号、网络监听、防火墙或系统服务配置，也没有进行跨机连接验收。


1. 仅启动数据库服务器
~~~~~~~~~~~~~~~~~~~~~~~~


在服务器电脑、拥有本项目数据目录权限的 Windows 用户下打开 PowerShell。以下代码只控制这个已有集群，不初始化数据库，也不启动工作台或 pgAdmin：

.. code-block:: powershell

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
   .\tools\easyerp-db.ps1 status


最后的状态输出应指向本项目 ``var\pgdata``、正式库及 ``55433``；若不相符，先查清实例归属。端口被其他实例占用时不要停止其他实例，也不要更换到其他数据库继续配置。

首次按当前配置启动仍然仅允许本机连接。完成下一节配置并重启后，同一启动命令才会同时接受指定远程地址的连接。关闭 PowerShell 或客户端不会自动停止数据库。

项目原有 ``.\tools\easyerp-db.ps1 start`` 也只启动数据库相关功能，但会额外检查凭据、角色和库的安装状态，必要时初始化或安装；严格只启动已有集群时采用上面的原生命令。


2. 首次启用远程连接
~~~~~~~~~~~~~~~~~~~~~~


下例采用**两台电脑已接入同一加密 VPN**的方式。先确认真实网络，再替换所有示例地址：服务器 VPN 地址 ``10.66.0.1``、张三电脑 VPN 地址 ``10.66.0.20``、个人账号 ``erp_remote_zhang``。这些不是本机实查地址。VPN 的建立及路由需先完成；服务器的该地址应固定且启动时已存在。

现有 ``ssl=off``，SCRAM 认证并不加密后续业务数据。因此此例依靠 VPN 加密传输。若采用无 VPN 的直接网络连接，应另行配置 PostgreSQL TLS、证书及 ``hostssl``，客户端使用 ``sslmode=verify-full``；不能只将此例端口映射到公网就视为完成部署。参见 `PostgreSQL TLS <https://www.postgresql.org/docs/18/ssl-tcp.html>`__。


2.1 核对、备份
~~~~~~~~~~~~~~~~~~


先按第 1 节启动现有实例，然后：

.. code-block:: powershell

   .\tools\easyerp-db.ps1 backup
   if ($LASTEXITCODE -ne 0) { throw '备份失败，停止后续配置。' }
   $serverBackup = Join-Path $erpRoot ('backups\server-config-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
   New-Item -ItemType Directory -Path $serverBackup | Out-Null
   foreach ($name in @('postgresql.conf','postgresql.auto.conf','pg_hba.conf')) {
       Copy-Item -LiteralPath (Join-Path $pgData $name) -Destination (Join-Path $serverBackup $name)
   }
   .\tools\easyerp-db.ps1 shell -Role easyerp_admin


最后一条打开本机管理员 ``psql``；密码由现有受保护文件读取。在这个窗口中先确认：

.. code-block:: sql

   SELECT current_database(), current_user, current_setting('data_directory');
   SHOW port;
   SHOW listen_addresses;


应为 ``easyerp_v02``、``easyerp_admin`` 和本项目数据目录。备份命令保存数据库；配置另由上述复制保留。数据库转储不包含新建角色及其密码，之后新增的角色需单独记录受保护的授权与恢复方案。保留现有 ``.secrets``，不要将其发给远程用户。


2.2 每人建立独立账号，先开放只读
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


仍在管理员 ``psql`` 中，逐条执行：

.. code-block:: sql

   CREATE ROLE erp_remote_zhang LOGIN INHERIT
       NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
       CONNECTION LIMIT 5;
   GRANT easyerp_read TO erp_remote_zhang WITH INHERIT TRUE;
   ALTER ROLE erp_remote_zhang IN DATABASE easyerp_v02
       SET default_transaction_read_only = on;


然后在同一 ``psql`` 窗口设置该人的密码，交互输入两次，不把密码写进 SQL 文件、命令参数或日志：

.. code-block:: text

   \password erp_remote_zhang


这是首次建号示例，账号已存在时先核对原权限，不重复 ``CREATE ROLE``。其他人使用各自账号及密码，逐人增加 HBA 和防火墙允许地址。

此方案复用项目代码为 ``easyerp_read`` 定义的对象授权；启用时须核对实际权限。``default_transaction_read_only`` 是辅助默认值，不能代替权限隔离。该组的权限设计覆盖六部门业务数据，**不等于按部门或按人员隔离数据**。需要更小范围时应另建权限组并逐对象授权。不要向外分发 ``easyerp_admin``、``easyerp_app`` 或现有共享密码。

当前配置的 50 个连接是整个实例的上限，正式库、演示库、网页服务和监控共同占用；一个人可能打开多条连接，不能据此认定支持 50 人同时使用。上线人数需结合连接池、查询负载和备份维护实测。

若将来需要远程业务录入，须明确写入权限及审计路径。直接 SQL 写表不会经过 ``app/entry.py`` 的保存服务，因而不能自动获得该服务的全部幂等、冲突检测和业务审计；本说明采用只读接入。


2.3 配置监听、认证与防火墙
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


仍在管理员 ``psql`` 中，单独执行以下语句，不放入事务：

.. code-block:: sql

   ALTER SYSTEM SET listen_addresses = '127.0.0.1,10.66.0.1';


本项目的 ``postgresql.auto.conf`` 已设置本机监听，且其优先级高于 ``postgresql.conf``，所以只修改后者可能不生效。上面的 ``ALTER SYSTEM`` 会更新自动配置；现有项目启动代码仅在新集群初始化时写入初始配置。参见 `参数配置与覆盖规则 <https://www.postgresql.org/docs/18/config-setting.html>`__。

用编辑器在 ``var\pgdata\pg_hba.conf`` 保留原行，再追加第二行；不要将文件替换成只有远程规则的版本：

.. code-block:: text

   host all         all               127.0.0.1/32   scram-sha-256
   host easyerp_v02 erp_remote_zhang  10.66.0.20/32  scram-sha-256


只允许指定数据库、个人账号、客户端地址。未匹配的远程连接会被拒绝。规则按首次匹配处理；Windows 上 HBA 更改会影响后续新连接，因此先备份、保留原本机规则。参见 `HBA 规则 <https://www.postgresql.org/docs/18/auth-pg-hba-conf.html>`__。

在本机管理员 ``psql`` 中检查文件解析结果，结果应为空：

.. code-block:: sql

   SELECT sourcefile, sourceline, name, error
   FROM pg_file_settings WHERE error IS NOT NULL;
   SELECT line_number, error
   FROM pg_hba_file_rules WHERE error IS NOT NULL;


在**管理员权限的 PowerShell** 中，针对实际 VPN 地址设置 Windows 入站规则；这一步无需停库：

.. code-block:: powershell

   New-NetFirewallRule -Name 'EasyERP-PG-Remote-Zhang' -DisplayName 'easyERP PostgreSQL Zhang VPN' `
       -Direction Inbound -Action Allow -Protocol TCP -LocalPort 55433 `
       -LocalAddress '10.66.0.1' -RemoteAddress '10.66.0.20' -Profile Any


规则只覆盖此服务器地址、客户端地址和数据库端口；如已有同名规则先核对，不重复添加。云主机还需检查安全组及 VPN 路由。数据库连接不需要共享项目目录或启动 8092/8093。

退出管理员 ``psql``（输入 ``\q``），回到第 1 节的 PowerShell。监听地址变更需要重启，安排所有用户停止操作后执行；``fast`` 会断开现有连接并回滚未提交事务：

.. code-block:: powershell

   & $pgCtl -D $pgData -l $pgLog -m fast -w -t 45 restart
   if ($LASTEXITCODE -ne 0) { throw "数据库重启失败，请检查 $pgLog" }
   .\tools\easyerp-db.ps1 status
   Get-NetTCPConnection -State Listen -LocalPort 55433 |
       Select-Object LocalAddress,LocalPort,OwningProcess


确认包含 ``127.0.0.1`` 与实际 VPN 地址。PostgreSQL 在部分地址绑定失败时仍可能启动成功，因此不能只看“启动成功”。仅新增 HBA 规则不要求重启；监听地址则必须重启。参见 `监听设置 <https://www.postgresql.org/docs/18/runtime-config-connection.html>`__ 和 `pg_ctl <https://www.postgresql.org/docs/18/app-pg-ctl.html>`__。


3. 其他电脑如何连接
~~~~~~~~~~~~~~~~~~~~~~


远程用户连接 VPN 后，用自己电脑上的 PostgreSQL 客户端、pgAdmin 或其他支持 PostgreSQL 的工具填写：


.. list-table::
   :header-rows: 1
   :widths: auto

   * - 参数
     - 本例
   * - Host
     - 服务器实际 VPN 地址，本例 ``10.66.0.1``；不是 ``127.0.0.1``
   * - Port
     - ``55433``
   * - Database
     - ``easyerp_v02``
   * - Username
     - 分配给本人的账号，本例 ``erp_remote_zhang``
   * - Password
     - 本人的独立密码
   * - application_name
     - 可选标识，如 ``zhang-laptop``；辅助识别，不能代替账号身份


例如在客户端电脑的 PowerShell 中执行，``psql.exe`` 按客户端实际安装路径调用：

.. code-block:: powershell

   Test-NetConnection -ComputerName '10.66.0.1' -Port 55433
   psql.exe -X -W -P pager=off -d 'host=10.66.0.1 port=55433 dbname=easyerp_v02 user=erp_remote_zhang application_name=zhang-laptop connect_timeout=5'


连接后核对目标及自身身份：

.. code-block:: sql

   SELECT current_database(), session_user, current_user,
          inet_server_addr(), inet_server_port(), inet_client_addr();
   SHOW transaction_read_only;


``Test-NetConnection`` 成功只说明 TCP 可达；实际登录、目标库、账号权限仍需用后面的连接确认。继续执行项目 ``db\queries\常用查询.sql`` 中的只读业务查询，核对可见范围，不要在正式库用写入业务数据来测试。


4. 显示谁在连接 SQL 服务器
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


自动刷新的原生监控窗口
~~~~~~~~~~~~~~~~~~~~~~


在服务器项目目录打开另一个 PowerShell，执行：

.. code-block:: powershell

   .\tools\easyerp-db.ps1 shell -Role easyerp_admin


在该管理员 ``psql`` 窗口粘贴以下查询，并在最后输入 ``\watch 3``。它每 3 秒重新查询，Ctrl+C 停止刷新，``\q`` 退出：

.. code-block:: text

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


这里查看该实例的所有客户端，包括正式库、演示库和其他管理连接；不显示查询文本。``active`` 是正在执行命令，``idle`` 是保持连接但当前没有执行命令，``idle in transaction`` 是事务仍未结束。VPN 例中的“数据库TLS”可能为 false，它仅表示数据库协议是否使用 TLS，不表示 VPN 是否加密。

``pg_stat_activity`` 是当前会话快照；断开后该行消失，轮询也可能看不到很短的连接。客户端程序名由客户端提供，IP 可能是 VPN、代理或 NAT 地址；**独立登录账号与人员的对应表才是识别人员的基础**。网页服务或连接池使用共享账号时，数据库只能显示服务账号，不能据此识别每位网页访问者。参见 `PostgreSQL 会话统计 <https://www.postgresql.org/docs/18/monitoring-stats.html>`__ 与 `psql 自动刷新 <https://www.postgresql.org/docs/18/app-psql.html>`__。

管理员可看到完整会话详情；普通账号对其他角色的许多会话字段无权查看。确需独立监控人员时，另建个人监控账号并授予 ``pg_read_all_stats``，同时配置其登录权限和允许来源；此权限会暴露其他会话的查询等敏感信息，不分配给普通远程只读用户。


使用已有 pgAdmin 图形界面
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


本机双击 ``bin/sqlview.exe``，在左侧选中服务器或数据库，再打开 Dashboard（仪表盘）的 Server activity / Sessions（会话）。界面名称随版本和语言变化。若希望保留“只启动数据库”的运行方式，使用上一段 ``psql`` 即可。

项目预设 pgAdmin 连接使用 ``easyerp_app``，对其他角色的详情有权限限制。完整监控优先用本机管理员 ``psql``，或由运维在本机 pgAdmin 单独注册合适的监控连接；不要把现有预设业务连接改成超级管理员。此图形入口已通过已安装源码确认存在，本次未作页面操作验证。


需要连接历史时
~~~~~~~~~~~~~~


当前配置未启用成功连接/断开日志。若需要历史记录，在本机管理员 ``psql`` 单独执行以下管理语句：

.. code-block:: sql

   ALTER SYSTEM SET log_connections = 'authorization';
   ALTER SYSTEM SET log_disconnections = on;
   ALTER SYSTEM SET log_line_prefix = '%m [%p] user=%u db=%d app=%a client=%r ';
   SELECT pg_reload_conf();


``log_min_messages`` 保持现有 ``warning`` 即可，服务端这个级别包含 LOG 消息。上述设置用于之后的新连接，不会补回过去记录。当前 ``logging_collector=off``，按第 1 节启动时日志输出到传给 ``-l`` 的实际文件；项目启动脚本另用时间戳日志。应安排日志轮转、留存和访问权限。连接历史不等于每条业务修改的审计记录。参见 `PostgreSQL 连接日志 <https://www.postgresql.org/docs/18/runtime-config-logging.html>`__。


5. 验收、退出与回退
~~~~~~~~~~~~~~~~~~~~~~


启用配置后，从另一台电脑验收：允许的个人账号能登录并查询授权数据；错误密码、未授权来源、未允许的数据库均被拒绝；服务器监控窗口能看到该账号、来源地址，断开后记录消失；原本机工作台及 SQL 界面仍能连接。**这些跨机验收本次均未执行。**

常见排查：TCP 不通时看 VPN 路由、监听和防火墙；出现 ``no pg_hba.conf entry`` 时核对服务器实际看到的来源 IP、库名和账号；密码失败时检查个人账号及密码，不改成 ``trust``；登录后无权查询时核对对象授权，不直接授予管理员。

撤回远程开放时：

#. 本机管理员执行 ``ALTER ROLE erp_remote_zhang NOLOGIN;`` 阻止其新登录；必要时按监控列表准确确认会话 PID，再执行 ``SELECT pg_terminate_backend(实际PID);``。NOLOGIN 不会自行断开现有会话。
#. 移除本次新增 HBA 行，在管理员 PowerShell 执行 ``Remove-NetFirewallRule -Name 'EasyERP-PG-Remote-Zhang'``；保留原本机 HBA 行。
#. 本机管理员单独执行 ``ALTER SYSTEM SET listen_addresses = '127.0.0.1';``，安排重启并核对监听。账号及历史记录可保留，不必删库或重建集群。

若远程配置后启动失败，在确认该集群已停止时，用第 2.1 节留存的配置副本恢复本次变更，再按第 1 节启动；先排查日志，不删除 ``var\pgdata``。配置备份只恢复到对应文件，不覆盖业务数据或凭据。

停止整个本项目数据库可执行 ``.\tools\easyerp-db.ps1 stop``，它会影响本机工作台、演示库和全部远程连接，不是只关闭某一个人的远程访问。

如果以后需要开机后台运行，PostgreSQL 原生 ``pg_ctl register`` 可注册 Windows 服务，但需要安排专用服务身份、数据目录权限及与现有启动方式的协调，本次未注册系统服务。另建远程主机部署时，还需安装匹配版本、备份恢复正式数据及角色并重新配置网络；不是只复制某个 exe 即可运行。


业务短编号维护
--------------

内部业务编号使用 ``app/id_rules.json`` 的表级固定前缀与至少三位36进制流水，ZZZ 之后增加流水位数继续递增。工作空间计划、事项、审计月报分别使用 PLN、WF、AUD。外部平台订单号、税号、文件哈希和请求幂等标识保留其原有含义。

``tools/migrate_business_ids.py --mode live --out reports/本次目录`` 默认只生成预览；追加 ``--apply`` 会先核对集群并备份，再在一个 SQL 事务中改主键及全部外键，校验逆向映射后的完整记录等同迁移前，恢复原外键时机和过账触发器。文件工作空间另存备份后更新当前编号和引用，原始历史快照保留。迁移结果、SQL、备份路径和旧新编号表保存在本次目录及 erp_ops 迁移登记中。

操作期间应停止核对归属后的本项目网页服务，迁移两种来源后再启动，避免内存草稿与元数据沿用旧编号。SQL 已提交而文件阶段中断时，保留 SQL_COMMITTED 回执，重跑同源迁移完成文件恢复；不得回滚别名或重新创建业务记录。

自动分配在独立元数据表中预留号码；校验失败、取消和回滚检查允许产生空号，同一请求或同一 CSV 文件行重试复用原号。输入旧 CSV 编号时通过别名找回当前记录，原始文件字节、导入回执和审计不改写。


三个业务标识：短 ID 为表级前缀加至少三位大写36进制流水（例如 PO00M）；长 ID 为部门简写-主录简写-编号生成年月日-流水的十进制值（例如 PRD-PO-20261114-022）；SHA-256 是对 UTF-8 长 ID 的稳定摘要。历史记录采用迁移的编号生成日，不改业务日期。SQL 元数据在 erp_ops.business_record_ids；工作空间也保存同样三个标识。前端普通表格保留短 ID 字段，编辑与选择只露出名称；长 ID 和 SHA-256 均不展示，Agent 使用只读 /api/identity?mode=live&object=production.采购订单表&id=短ID、长ID或SHA256 查询。无部门的文件工作空间使用 WS 命名空间，不推定业务部门。


编号生成日期使用 Europe/Berlin 本地日历；事件录入和业务日期沿用既有口径。首次迁移的日期时区校正记录保存在同次迁移目录的 date-correction.json，既有数据备份和迁移原回执均保留。

量化计算备份
----------------

所选来源workspace_directory/calculations目录保存独立计算条目、计算台、版本与历史。备份workspace时包含整个目录；旧live.json/demo.json和数据库备份仍保留。Agent操作说明见项目.agents/skills/easyerp-calculations/SKILL.md。
