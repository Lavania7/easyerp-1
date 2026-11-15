需求10：正式数据库分离审批材料
================================

当前状态与审批范围
------------------

本文件是待审批执行方案。未迁移、未停机、未创建 D:\database，未切换 config.json，未删除源正式库或任何业务外部文件。当前自动审批拒绝正式库迁移和搬移；本组不执行下述命令，也不以其他脚本或工具绕过拒绝。实际执行必须由主控在原对话取得人类对本材料具体动作的批准。

2026-11-15 只读核对：

- PostgreSQL 18.4，程序 E:\PostgreSQL18\bin，PID 2324，本机 55433。
- 集群 D:\projx\release\easyerp-1\var\pgdata；正式 easyerp_v02，约34.97 MB；演示 easyerp_v02_ui_demo，约23.58 MB。两者共用集群，不能移动整个 pgdata 达到“项目仅留演示库”。
- 正式和演示均146张业务表。主控获人类批准后已完成010字段升级；最终只读预览确认两库安装摘要均与当前构建匹配（build_sha256=3d4cb250a6193c414512a9905b2238cc97644e59e7518673f403cdd7a503f652）。需求10搬移仍未获本组执行授权，不能把010批准扩展为搬移批准。
- 工作台 8092，PID 20072，启动源码为本项目 app/server.py；8093当前无监听。这些PID仅为快照，执行前重新核对，不能直接据此停止进程。
- 正式工作空间 var\workspace\live.json（8999字节），演示 demo.json（163字节）；dump 不包含这些文件。
- easyerp_admin 为集群管理员；easyerp_app/easyerp_read 没有超级用户、建库、建角色权限。目标生成独立三角色密码；密码不进入报告或前端。

精确目标与配置
----------------

- 新正式实例根 D:\database\easyerp-live，data_directory D:\database\easyerp-live\pgdata，端口55434，库名仍为 easyerp_v02。
- 目标凭据 D:\database\easyerp-live\.secrets，工作空间 D:\database\easyerp-live\workspace\live.json，导入历史 D:\database\easyerp-live\var\import-interface.sqlite3。
- 备份及恢复验证 D:\database\easyerp-live\backups；迁移证据及只读源快照放 D:\database\easyerp-live\migration\时间戳。目标目录若存在或55434占用，则停止计划、重新核对，绝不覆盖或自动换端口。
- 演示仍用原集群55433、easyerp_v02_ui_demo、原 .secrets 和 var\workspace\demo.json。
- config.json 旧 database/port 字段保留兼容，新增 database_sources.live/demo 显式 database、port、runtime_root、data_directory、private_directory、workspace_directory；候选由只读预览JSON提供，当前文件没有应用。
- 新数据库管理目录下的新建实例是独立空库，验证后停止；当前只提供候选配置，尚无前端激活/切换使用接口。不能把此状态说成需求10已经全完成。

执行前重新生成材料
------------------

以下命令只读，输出应位于主控工作目录：

::

   Set-Location -LiteralPath 'D:\projx\release\easyerp-1'
   $erpPython = (Get-Content -LiteralPath config.json -Raw -Encoding UTF8 | ConvertFrom-Json).python
   & $erpPython tools\preview_database_relocation.py --out 'D:\codex\temp\2026-11-15\woxu\work\database-relocation-preview.json'

输出包含实际集群、库大小、模板指纹、config.json SHA256、工作空间SHA256、全部 backups/exports/import 文件逐项路径及SHA256、导入历史按来源计数；不包含凭据内容。

获批后实施顺序（本组未执行）
------------------------------

1. 010字段迁移已由主控独立获批并完成；执行前仍重新核对安装摘要和结构验证。前端新源码不在当前8092热加载；迁移前不重启新版前端来掩盖版本差异。执行目录/端口/数据规模重新核对，记录临时目录和所有进程归属。建议预留15–30分钟维护窗口，其中数据库逻辑备份/恢复本身预计数分钟；尚未测量正式全量恢复耗时，外部文件核对或失败会延长。

2. 暂停业务输入、导入任务及Agent；停止核实为本项目的8092前端进程，防止迁移期间写入。此时仍不停止原PostgreSQL集群，因此演示库物理集群保留。记录全部数据库连接并确保没有其他写入者；对源库执行一致性快照签名，重复读取验证暂停后无变化。

3. 在新建的受限目标根目录中保存 config.json 原字节副本、旧源信息、批准编号和预览JSON。使用 easyerp_admin 的现有受限PGPASSFILE对 easyerp_v02 执行 pg_dump -Fc；保存 SHA256 和所有业务/erp_ops表逐表行数与排序全行内容摘要，另存schema-only结构/约束/函数/权限快照。dump保留原数据库角色名，目标建立同名三角色，目标密码独立生成。不得把密码打印到命令行或保存到普通报告。

4. 目标55434建立独立集群（仅127.0.0.1，scram-sha-256，新的 .secrets ACL）。从template0创建 easyerp_v02，将源dump用 pg_restore --exit-on-error --single-transaction 恢复到新集群。不得使用演示业务数据、pgdata目录拷贝或覆盖原库。恢复测试另建随机库，恢复同一dump并比对完整摘要后只删除该随机库。失败只保留新目标供检查，源库不动。

5. 在暂停写入期间复制 live.json 原字节到目标workspace，校验SHA256一致；目标不复制demo.json。SQLite使用SQLite备份接口取得一致性副本，目标删除checks中的demo记录、保留原检查ID/settings/events；项目副本此时保留以便回滚。新API按runtime_root隔离历史，因此后续正式检查不会写回项目SQLite。

6. 外部业务原件、import/batches、backups、exports不能凭目录或相似名称猜来源。逐项使用预览JSON清单和dump旁的数据库元数据分类；确认正式的派生备份/导出先复制到目标legacy-artifacts保持相对路径并比对SHA256。原始来源文件继续保留原路径，不能移动或改写来满足“仅留演示”表面要求。若实际原件位于项目内，先列出准确路径向用户明确这一冲突，再按用户决定复制归档或改引用。未分类文件默认保留，不能静默删除；清理前需将最终精确清单加入审批材料。

7. 比较源与目标所有6业务schema及erp_ops表的逐表行数/全行摘要，核对外键定义与有效性、序列值、函数和触发器、三标识/别名/审计/已过账保护、schema_version与模板/安装摘要。验证read只读、app可正常业务保存却无DDL/建库权，admin仅在受限运维使用。角色负面测试在隔离恢复库中执行并回滚。验证工作空间字节、SQLite正式检查ID及业务原件清单。

8. 将候选database_sources写入config.json（先保留原字节备份），重启已核实的工作台。验证 /api/health?mode=live 指向55434的正式库、demo仍指向55433演示库；列表/详情/录入/CSV/导入/工作空间分别用各自来源。实际冒烟写入仅演示或隔离库。旧源正式库仍保留用于回滚，此时尚未达到“项目仅留演示数据”。

9. 完成来源隔离验收后按本次批准范围执行第二阶段清理：再次停止写入并增量备份目标，确认恢复测试有效，再从原55433集群仅 DROP DATABASE easyerp_v02；保留 easyerp_v02_ui_demo、postgres、整个var/pgdata、原角色及.secrets。只清除源live.json及live.lock，以及SQLite中mode=live的checks；settings/events共享信息保留，SQLite清理后VACUUM去除旧页中的正式记录。正式备份/导出仅按已批准的逐文件清单在目标哈希复核后移除原副本；不自动删除共享目录、日志、旧报告或未分类文件。原始来源文件不删除。本次审批可以一次覆盖A/B及精确清单，B须等待A全部校验和使用验收成功后执行；若批准范围未含B，则不得从“切换成功”推断清理授权。

具体命令格式与限制
------------------

tools/preview_database_relocation.py 专用于只读清单；tools/relocate_database.py 默认同样仅预览，只有同时给出 --apply 与明确阶段才执行。当前没有运行任何 --apply 阶段。执行器不会自行停止8092，发现8092仍在运行或源正式库有应用/管理员连接就拒绝；获批后由主控重新核对归属并暂停全部写入方。

::

   # 默认仅预览，当前已实际执行
   & $erpPython tools\relocate_database.py --out 'D:\codex\temp\2026-11-15\woxu\work\database-relocation-preview.json'

   # A1：获批并暂停写入后，恢复到独立55434实例；不改配置，不删除源库
   & $erpPython tools\relocate_database.py --apply --phase restore --plan 'D:\codex\temp\2026-11-15\woxu\work\database-relocation-preview.json'

   # A2：全表/结构/工作空间/导入历史验证通过后切换config.json；源正式库保留
   & $erpPython tools\relocate_database.py --apply --phase cutover
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File bin\start-frontend.ps1

   # B：来源隔离验收成功，且本次批准包含精确源清理后，重新暂停写入再执行
   & $erpPython tools\relocate_database.py --apply --phase finalize
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File bin\start-frontend.ps1

   # 尚未finalize、且源目标数据库/工作空间/导入历史均无新增变化时可回滚配置
   & $erpPython tools\relocate_database.py --apply --phase rollback
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File bin\start-frontend.ps1

每阶段的恢复证据保存于 D:\database\easyerp-live\migration\restored.json。restore会检查原配置SHA256、实际源集群、目标目录全部子路径、55434空闲、当前安装版本和逐文件哈希；目标已存在则拒绝覆盖。失败时保留新目标并停止本次新实例。cutover复查全表数据/结构、live工作空间和SQLite逻辑摘要，防止恢复后变化被忽略。finalize先对目标最新数据备份及隔离恢复验证并保全最新外部工作空间/历史，再清理精确旧源。rollback发现任一来源出现新事实、工作空间或导入历史变化就拒绝直接切回，避免丢失新记录。

最终清单和删除范围
------------------

最终预览共430个外部文件：正式197、演示71、隔离测试62、待核对100；其中正式197包含live.json，其他196为有数据库元数据证据的正式备份/导出。导入历史有live 3条、demo 113条检查，settings 1条、events 6条。import/batches及inbox当前无需要复制的业务文件。完整逐文件路径、大小、SHA256、分类在预览JSON；单独生成 database-relocation-cleanup-list.rst 便于审阅，不凭文件名猜清理。

- A复制所有backups/exports/import清单文件到目标legacy-artifacts并核对SHA256，保留原文件；复制独立正式工作空间，SQLite目标只保留live检查及共享settings/events。
- B仅从原55433集群DROP DATABASE easyerp_v02；保留easyerp_v02_ui_demo、postgres/template、整个原pgdata和演示所需角色/凭据。成功后重新查询原实例所有非系统库，报告only_demo_business_database是否为真。
- B删除源var/workspace/live.json和live.lock，源SQLite仅删除mode=live的3条检查后VACUUM；保留demo检查、settings/events。
- B仅删除清单分类为live的196个backups/exports文件，且逐个确认目标归档哈希仍一致。保留demo 71、隔离测试62、待核对100个文件，保留原始来源文件。历史文件保留与“仅剩演示运行库”分别报告，不互相混淆。
- 不停止原PostgreSQL实例，不移动整个pgdata，不删除共享.secrets、整个backups/exports/import目录、日志或旧报告，不改业务原件引用。pgAdmin旧连接档案在切换后应按显式来源重新核对，当前执行器不自动更新pgAdmin内部档案；8093当前无监听，正式迁移验收应包括此限制。

本次实际验证及限制
------------------

- tests/test_database_manager.py：13项通过，含真实HTTP边界、目录票据、幂等/失败保留、模板与逻辑关联、正式演示来源隔离。
- tests/test_database_manager_integration.py：临时全新PostgreSQL实例、空业务表、角色权限、备份恢复通过；43.07秒；源两库/工作空间/config签名相同，测试实例停止且清理。
- tests/test_database_manager_ui.cjs：真实8092 Edge 16项通过，三语/深色/窄屏/图谱/真实迁移预览；folder和preview使用拦截响应，未实际操作Windows目录选择对话框，0业务写入/0脚本错误。
- tests/test_database_relocation.py：5项无apply安全测试通过，覆盖默认预览路由、显式阶段/计划必需、路径越界拒绝及SQLite按来源复制且保留检查ID/源文件不变。
- 9个Python实现文件AST、数据库管理JS语法和本组tracked文件diff空白检查通过；默认relocate_database.py --out已真实运行，为只读清单。
- **尚未执行或验证正式restore/cutover/finalize/rollback全流程。** 真实新建功能验证不能冒充正式迁移已验证。执行器是待审阅代码；正式执行仍受人类审批及当前权限控制。


回滚
----

- 切换前失败：新目标标记失败并保留；原配置/源库/工作空间和SQLite未改变。清理新目录也应先核对随机/指定目录归属，不能递归删整个D:\database。
- 切换后、源库清理前：先暂停写入；若目标已产生新正式记录，先备份并评估回灌，不能直接切回丢失新记录。无新增记录时恢复config.json原字节、旧live工作空间/SQLite一致副本，重启已核实的前端并验证正式/演示指向。目标保留用于调查。
- 源库清理后：从已验证dump恢复为新名称到原集群或独立恢复集群，恢复角色/外部文件/SQLite，完成比较后切换。此阶段不再具有即时回滚能力，故源清理应晚于验收和保留期。

可一次明确批准A（目标创建/正式复制恢复/短暂停写/配置切换）及在A验收成功后执行B（精确源库、源正式工作空间/SQLite正式行及196个派生文件清理）。当前A/B都未执行；本组不另行向用户发起重复确认。
