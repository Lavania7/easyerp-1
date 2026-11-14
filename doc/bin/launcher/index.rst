bin/launcher/ — Windows 启动器源码与构建
======================================================================

职责与当前情况
----------------------------

原 launcher-src/ 整体并入本目录；README.md 转为 doc/bin/launcher/overview.rst。构建器与图标校验器按两级父目录定位根目录。

修改与维护方式
----------------------------

在项目根运行 ``powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\bin\launcher\build.ps1``；校验命令为配置中的 Python 执行 bin/launcher/verify-icons.py。构建产物仍写 bin/，图标同步到 bin/icons/。

`原有功能说明 <overview.rst>`__。

`返回目录结构总览 <../../structure.rst>`__。
