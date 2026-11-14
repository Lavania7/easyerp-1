目录结构与维护索引
======================================================================

本次整理日期：2026-11-14。项目为本机部署，不引入打包框架；按启动、工具、应用、SQL、文档、证据和运行数据划分职责。

.. code-block:: text

   .
   ├── bin/                 启动入口
   │   ├── launcher/        C# 源码、构建与图标校验
   │   └── icons/           可复用图标
   ├── tools/               数据库、导入与系统维护工具
   ├── app/                 Python 应用与浏览器资源
   │   └── web/fonts/       页面与字体授权
   ├── db/                  基础 SQL 与构建清单
   │   ├── app/             应用扩展 SQL
   │   ├── imports/         历史导入 SQL
   │   └── queries/         查询示例
   ├── tests/               离线、HTTP、数据库及浏览器检查
   ├── doc/                 RST 文档，按文件夹分组
   ├── import/              原始来源与导入证据（原位保留）
   ├── reports/             历史验证证据（原位保留）
   ├── var/                 数据库集群及运行状态（原位保留）
   ├── .secrets/            本机私密配置（原位保留）
   ├── backups/             备份（原位保留）
   └── exports/             导出（原位保留）

逐文件迁移见 `位置变更清单 <relocations.rst>`__。所有命令从项目根目录执行，Python 使用 config.json 中的解释器。

按文件夹查看
--------------------------------------------------

- `app/：应用代码 <app/index.rst>`__
- `app/web/：浏览器静态资源 <app/web/index.rst>`__
- `app/web/fonts/：字体与第三方声明 <app/web/fonts/index.rst>`__
- `bin/：启动入口 <bin/index.rst>`__
- `bin/launcher/：Windows 启动器源码与构建 <bin/launcher/index.rst>`__
- `bin/icons/：启动器图标 <bin/icons/index.rst>`__
- `tools/：维护及导入工具 <tools/index.rst>`__
- `db/：SQL 与结构清单 <db/index.rst>`__
- `db/app/：应用扩展 SQL <db/app/index.rst>`__
- `db/imports/：历史导入 SQL <db/imports/index.rst>`__
- `db/queries/：只读查询示例 <db/queries/index.rst>`__
- `tests/：测试脚本 <tests/index.rst>`__
- `doc/：工程与业务文档 <doc/index.rst>`__
- `import/：业务导入工作区 <import/index.rst>`__
- `import/inbox/：待处理原件 <import/inbox/index.rst>`__
- `import/batches/：导入批次证据 <import/batches/index.rst>`__
- `reports/：历史验证与交付证据 <reports/index.rst>`__
- `var/：运行状态与数据库集群 <var/index.rst>`__
- `.secrets/：本机凭据 <.secrets/index.rst>`__
- `backups/：数据库和系统集成备份 <backups/index.rst>`__
- `exports/：业务导出 <exports/index.rst>`__
- `.agents/：本机代理技能 <.agents/index.rst>`__
- `.git/：版本管理元数据 <.git/index.rst>`__
- `import/inbox/analysis/：原件分类：analysis <import/inbox/analysis/index.rst>`__
- `import/inbox/finance/：原件分类：finance <import/inbox/finance/index.rst>`__
- `import/inbox/legal/：原件分类：legal <import/inbox/legal/index.rst>`__
- `import/inbox/production/：原件分类：production <import/inbox/production/index.rst>`__
- `import/inbox/rd/：原件分类：rd <import/inbox/rd/index.rst>`__
- `import/inbox/sales/：原件分类：sales <import/inbox/sales/index.rst>`__
- `import/inbox/unclassified/：原件分类：unclassified <import/inbox/unclassified/index.rst>`__

根文件
--------------------------------------------------

readme.md 为使用首页，config.json 为本机配置，LICENSE 与 NOTICE 为授权说明，.gitignore 管理忽略边界；这些位置保持不变。AGENTS.md 为忽略提交的本机代理入口，路径说明已同步。

验证范围
--------------------------------------------------

本次执行静态语法、路径及链接检查、离线回归、SQL 与资源哈希比较和图标资源检查。详细实际结果见 reports/directory-structure-20261114.json。本次不执行数据库迁移、正式导入或桌面快捷方式写入；数据库、HTTP 和浏览器行为的验证范围以该报告为准。

已有图标快捷方式
--------------------------------------------------

两个 EXE 位置保持 bin/ 不变。若本机快捷方式单独引用旧 icons/，在核对本项目目标后运行 tools/refresh-icons.ps1 恢复图标；本次没有改写桌面。原 frontend/ 路径上的服务若正在运行，应按运维说明在适当时机重启为 app/server.py，服务状态和数据库数据目录不变。
