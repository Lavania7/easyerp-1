db/app/ — 应用扩展 SQL
======================================================================

职责与当前情况
----------------------------

接收原 frontend/ 的 entry_schema.sql、csv_import_schema.sql、company_schema.sql、workspace_schema.sql、purchase_intake_schema.sql；SQL 字节保持原样。

修改与维护方式
----------------------------

在对应 `tools/enable-*.py` 中执行明确的升级流程；脚本路径引用已更新。不要仅因文件移动再次执行已安装升级。

`返回目录结构总览 <../../structure.rst>`__。
