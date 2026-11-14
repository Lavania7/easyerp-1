bin/ — 启动入口
======================================================================

职责与当前情况
----------------------------

保留两个 EXE、start-frontend.ps1、start-backend.ps1、start-hidden.ps1。launcher-src/ 并入 bin/launcher/，icons/ 并入 bin/icons/；数据库、导入和系统维护工具移到 tools/。

修改与维护方式
----------------------------

启动脚本调用 tools/ 下的工具。两个 EXE 的父目录仍为项目根目录，不需要因本次移动重编译；启动器源码与构建流程在 launcher/，独立图标在 icons/。

`返回目录结构总览 <../structure.rst>`__。
