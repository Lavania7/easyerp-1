# easyERP 启动器图标

Dashboard 由三根绿色递增柱形组成，D 直接绘制在前景柱形上；SQLview 由三层蓝紫色圆柱数据层组成，S 直接绘制在圆柱正面。参考桌面 Power BI 图标由业务符号构成外轮廓的方式，保留柔和渐变与叠层。

- `frontend.ico`、`backend.ico`：透明背景，32 位色深，含 16、20、24、32、40、48、64、96、128、256 像素十个尺寸。16–24 像素简化细边高光。
- 项目根目录 `icons/dashboard.ico`、`icons/sqlview.ico`：便于复用的独立图标；同目录保存透明 PNG 和 `preview.png` 预览。构建时同步生成。
- `dashboard.png`、`sqlview.png`：512 像素透明原图。
- `icon-preview.png`：浅色和深色背景的预览。
- `IconBuilder.cs`：可重复生成全部图标资源，不依赖额外绘图软件。
- `Launcher.cs`：静默启动，就绪后直接打开浏览器；失败时显示错误提示，并保留日志。

在项目根目录运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\launcher-src\build.ps1`，重建 `dashboard.exe` 和 `sqlview.exe`。需要现有 Windows .NET Framework 编译器。

运行 `python .\launcher-src\verify-icons.py` 检查两个 exe 的所有内嵌图标尺寸、色深、透明通道和资源内容是否与 ico 一致。启动检查可分别使用 `dashboard.exe --check` 和 `sqlview.exe --check`；会启动或复用本项目服务，不自动打开浏览器。

重建后可运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\bin\refresh-icons.ps1`，备份并更新桌面两个 easyERP 快捷方式的图标，通知资源管理器刷新。加上 `-UseCurrentProject` 可同时将两个快捷方式的目标和工作目录设为当前项目；本次已按用户确认改为 easyerp-1。
