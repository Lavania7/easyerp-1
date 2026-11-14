> 2026-11-14 更新：已按 `prompt.rst` 批注调整为企业计划、工作流、数据中心、档案馆，并增加审计月报。旧流程及工时表退出录入；采购、仓储和库存入口合并。详见 [实施说明](doc/workspace-revision.rst)。下文历史范围与当前界面不一致时，以该说明及当前代码为准。

# easyERP 本机经营工作台

easyERP 把财务、销售、采购与生产、研发、法务和分析的主录放在同一本机数据库中。业务事实只录一次，页面、核对和交付通过ID关联生成。未知资料保留空缺，不用0代替，也不把资金记录自动当作收入、成本或收货。

## 第一次使用

1. 在 `bin` 目录双击 `dashboard.exe` 打开经营工作台；双击 `sqlview.exe` 打开SQL管理界面。依赖本机已有的Python、PostgreSQL和pgAdmin，并非独立安装包。
2. 确认页面当前是正式数据还是演示数据。正式库用于真实业务，演示库用于练习，两者分开。
3. 日常可以查询、追溯、导出、手工录入，或下载空白主录模板后填写CSV再导入。涉及业务核定的内容仍需有依据的人确认。

默认本机地址：工作台 `http://127.0.0.1:8092/`，SQL管理界面 `http://127.0.0.1:8093/`；数据库名称和端口以 `config.json` 为准。启动器会启动或复用本项目服务，关闭浏览器不会停止数据库。

## 把文件交给Agent导入

将XLSX、CSV或文本文档等原文件放入 [import/inbox](import/inbox/)。可按财务、销售、采购生产等目录分类；不知道归属时放 `unclassified` 或直接放inbox。保留原文件名，无需先自己调整成数据库表。

然后告诉Agent：**“处理 import/inbox，更新正式库，按前端导入规则确认空缺和已有记录。”**

Agent先盘点与保留来源，解释文件并整理字段和ID，再转成标准主录CSV，使用前端同一套服务检查、备份和入库。有空缺或相同编号时沿用本批已明确的选择，缺少选择时先展示检查结果再询问。仅放文件不会自动写库。

每批的来源副本、字段及源行对应、标准CSV、检查和入库回执保存在 `import/batches/`。一个工作簿可以部分完成；未能确定的字段或关联会列为待确认。详见[导入箱说明](doc/import/overview.rst)和[文件导入流程](doc/import-workflow.rst)。

## 交接时读什么

| 需要了解 | 文件 |
| --- | --- |
| 全项目共同的主录、ID、人工/自动、数据关系和交付规则 | [全局业务与数据规则](doc/global-rules.rst) |
| 文件如何分类、转换、确认、入库和追溯 | [文件导入流程](doc/import-workflow.rst) |
| 页面功能、数据口径和运行方式 | [经营工作台](doc/app/overview.rst) |
| 手工新建、修改、主明细和冲突处理 | [手工录入](doc/app/manual-entry.rst) |
| 标准CSV、空缺和同号记录合并 | [前端导入规则](doc/app/preferences-and-standard-import.rst) |
| 文件识别、接口和实际限制 | [前端导入接口](doc/app/import-interface.rst) |
| 空白标准主录表怎么下载和填写 | [模板说明](doc/app/standard-templates.rst) |
| 启动、端口、日志、数据库命令、备份恢复与远程部署 | [运行与维护](doc/operations.rst) |
| 全部文档与许可证说明 | [文档目录](doc/index.rst)；[许可证说明](doc/licensing.rst) |
| 每张表的完整字段、SQL、关系和原始业务说明 | [SQL与逐表规范](doc/sql-specification.rst) |

## 项目文件怎么分

| 位置 | 保存内容 |
| --- | --- |
| `bin/` | EXE 与启动脚本，`launcher/` 放启动器源码，`icons/` 放图标 |
| `tools/` | 数据库、导入和系统维护工具 |
| `app/` | Python 服务、业务逻辑和 `web/` 页面 |
| `db/` | 基础 SQL、应用扩展、历史导入 SQL 和查询示例 |
| `tests/` | 测试脚本 |
| `doc/` | RST 文档，按对应文件夹分组 |
| `import/inbox/`、`import/batches/` | 原始业务文件及每批来源、映射和回执 |
| `reports/` | 按时间保留的验证证据 |
| `.secrets/`、`var/` | 凭据、数据库集群与运行状态 |
| `backups/`、`exports/` | 备份与导出 |

目录职责、原结构、修改方式及维护入口见[分文件夹说明](doc/structure.rst)，逐文件对应见[位置变更清单](doc/relocations.rst)。业务输入、批次、凭据和运行数据不提交 Git；代理约定仍保存在本机 `AGENTS.md` 与 `.agents/`。

## 维护时保留的边界

正式结构修改或入库前先备份，核对目标库与本项目集群。不要删除 `var/pgdata` 或重建正式库来消除错误；查询、写入、审计和已过账保护继续分工。

SQL规范现统一为 `doc/sql-specification.rst`。构建器读取RST中的SQL块并保留历史来源行号；全部生成SQL字节和构建摘要保持不变，严格验证当前RST全文和SQL哈希。只有SQL完全相同时兼容旧规范的安装标记，因此文档转换无需修改已安装数据库。

历史报告只证明当时执行过的检查。具体运行状态以当前配置、实际数据和本次检查为准；SQL通过不代表会计政策、库存结存或全部业务流程已经核定。


## 许可证

项目完整授权见 [LICENSE](LICENSE)，项目及第三方声明见 [NOTICE](NOTICE) 和 [许可证说明](doc/licensing.rst)。
