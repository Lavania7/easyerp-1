tools/ — 维护及导入工具
======================================================================

职责与当前情况
----------------------------

原 bin/ 中 Python 工具、easyerp-db.ps1、create-shortcuts.ps1 和 refresh-icons.ps1 迁入；脚本仍位于根目录下一层，Python 根目录定位逻辑保持有效。

修改与维护方式
----------------------------

数据库入口为 tools/easyerp-db.ps1；导入箱入口为 tools/import_inbox.py。历史专用导入器保留供追溯，普通导入沿用标准检查与执行服务。build_schema.py 保留生成 SQL 的历史注释，以保持既有 SQL 哈希。

`返回目录结构总览 <../structure.rst>`__。
