逐文件位置变更清单
======================================================================

清单以当前工作区为基线，保留此前未提交的修改。未列出的运行数据、来源、历史报告和根文件不移动。

.. list-table:: 文件迁移
   :header-rows: 1
   :widths: 50 50

   * - 原路径
     - 新路径
   * - ``bin/backend.py``
     - ``tools/backend.py``
   * - ``bin/build_schema.py``
     - ``tools/build_schema.py``
   * - ``bin/business_queries.py``
     - ``tools/business_queries.py``
   * - ``bin/configure_pgadmin.py``
     - ``tools/configure_pgadmin.py``
   * - ``bin/create-shortcuts.ps1``
     - ``tools/create-shortcuts.ps1``
   * - ``bin/easyerp-db.ps1``
     - ``tools/easyerp-db.ps1``
   * - ``bin/easyerp.py``
     - ``tools/easyerp.py``
   * - ``bin/enable-company-profile.py``
     - ``tools/enable-company-profile.py``
   * - ``bin/enable-csv-import.py``
     - ``tools/enable-csv-import.py``
   * - ``bin/enable-manual-entry.py``
     - ``tools/enable-manual-entry.py``
   * - ``bin/enable-purchase-intake.py``
     - ``tools/enable-purchase-intake.py``
   * - ``bin/enable-workspace.py``
     - ``tools/enable-workspace.py``
   * - ``bin/import_inbox.py``
     - ``tools/import_inbox.py``
   * - ``bin/import_legacy_data.py``
     - ``tools/import_legacy_data.py``
   * - ``bin/import_legacy_nulls.sql``
     - ``db/imports/import_legacy_nulls.sql``
   * - ``bin/import_release2.py``
     - ``tools/import_release2.py``
   * - ``bin/import_release2.sql``
     - ``db/imports/import_release2.sql``
   * - ``bin/inspect_release2.py``
     - ``tools/inspect_release2.py``
   * - ``bin/pgadmin_config.py``
     - ``tools/pgadmin_config.py``
   * - ``bin/refresh-icons.ps1``
     - ``tools/refresh-icons.ps1``
   * - ``frontend/COMPANY_PROFILE.md``
     - ``doc/app/company-profile.rst``
   * - ``frontend/DATE_QUERY.md``
     - ``doc/app/date-query.rst``
   * - ``frontend/IMPORT_INTERFACE.md``
     - ``doc/app/import-interface.rst``
   * - ``frontend/MANUAL_ENTRY.md``
     - ``doc/app/manual-entry.rst``
   * - ``frontend/PREFERENCES_AND_STANDARD_IMPORT.md``
     - ``doc/app/preferences-and-standard-import.rst``
   * - ``frontend/README.md``
     - ``doc/app/overview.rst``
   * - ``frontend/STANDARD_TEMPLATES.md``
     - ``doc/app/standard-templates.rst``
   * - ``frontend/company_schema.sql``
     - ``db/app/company_schema.sql``
   * - ``frontend/csv_import_schema.sql``
     - ``db/app/csv_import_schema.sql``
   * - ``frontend/data.py``
     - ``app/data.py``
   * - ``frontend/entry.py``
     - ``app/entry.py``
   * - ``frontend/entry_schema.sql``
     - ``db/app/entry_schema.sql``
   * - ``frontend/import_formats.json``
     - ``app/import_formats.json``
   * - ``frontend/imports.py``
     - ``app/imports.py``
   * - ``frontend/purchase_intake_schema.sql``
     - ``db/app/purchase_intake_schema.sql``
   * - ``frontend/server.py``
     - ``app/server.py``
   * - ``frontend/setup_demo.py``
     - ``app/setup_demo.py``
   * - ``frontend/standard_import.py``
     - ``app/standard_import.py``
   * - ``frontend/standard_templates.py``
     - ``app/standard_templates.py``
   * - ``frontend/web/app.js``
     - ``app/web/app.js``
   * - ``frontend/web/company.css``
     - ``app/web/company.css``
   * - ``frontend/web/company.js``
     - ``app/web/company.js``
   * - ``frontend/web/dark.css``
     - ``app/web/dark.css``
   * - ``frontend/web/favicon.svg``
     - ``app/web/favicon.svg``
   * - ``frontend/web/fonts/LICENSE.txt``
     - ``app/web/fonts/LICENSE.txt``
   * - ``frontend/web/fonts/SourceHanSansCN-VF.ttf.woff2``
     - ``app/web/fonts/SourceHanSansCN-VF.ttf.woff2``
   * - ``frontend/web/fonts/source.json``
     - ``app/web/fonts/source.json``
   * - ``frontend/web/i18n.js``
     - ``app/web/i18n.js``
   * - ``frontend/web/import.css``
     - ``app/web/import.css``
   * - ``frontend/web/import.js``
     - ``app/web/import.js``
   * - ``frontend/web/index.html``
     - ``app/web/index.html``
   * - ``frontend/web/locales.js``
     - ``app/web/locales.js``
   * - ``frontend/web/manual.css``
     - ``app/web/manual.css``
   * - ``frontend/web/manual.js``
     - ``app/web/manual.js``
   * - ``frontend/web/preferences.css``
     - ``app/web/preferences.css``
   * - ``frontend/web/preferences.js``
     - ``app/web/preferences.js``
   * - ``frontend/web/style.css``
     - ``app/web/style.css``
   * - ``frontend/web/table-edit.css``
     - ``app/web/table-edit.css``
   * - ``frontend/web/table-edit.js``
     - ``app/web/table-edit.js``
   * - ``frontend/web/templates.css``
     - ``app/web/templates.css``
   * - ``frontend/web/templates.js``
     - ``app/web/templates.js``
   * - ``frontend/web/workspace.css``
     - ``app/web/workspace.css``
   * - ``frontend/web/workspace.js``
     - ``app/web/workspace.js``
   * - ``frontend/workspace.py``
     - ``app/workspace.py``
   * - ``frontend/workspace_rules.py``
     - ``app/workspace_rules.py``
   * - ``frontend/workspace_schema.sql``
     - ``db/app/workspace_schema.sql``
   * - ``icons/dashboard.ico``
     - ``bin/icons/dashboard.ico``
   * - ``icons/dashboard.png``
     - ``bin/icons/dashboard.png``
   * - ``icons/preview.png``
     - ``bin/icons/preview.png``
   * - ``icons/sqlview.ico``
     - ``bin/icons/sqlview.ico``
   * - ``icons/sqlview.png``
     - ``bin/icons/sqlview.png``
   * - ``import/README.md``
     - ``doc/import/overview.rst``
   * - ``launcher-src/IconBuilder.cs``
     - ``bin/launcher/IconBuilder.cs``
   * - ``launcher-src/Launcher.cs``
     - ``bin/launcher/Launcher.cs``
   * - ``launcher-src/README.md``
     - ``doc/bin/launcher/overview.rst``
   * - ``launcher-src/backend.ico``
     - ``bin/launcher/backend.ico``
   * - ``launcher-src/build.ps1``
     - ``bin/launcher/build.ps1``
   * - ``launcher-src/dashboard.png``
     - ``bin/launcher/dashboard.png``
   * - ``launcher-src/frontend.ico``
     - ``bin/launcher/frontend.ico``
   * - ``launcher-src/icon-preview.png``
     - ``bin/launcher/icon-preview.png``
   * - ``launcher-src/sqlview.png``
     - ``bin/launcher/sqlview.png``
   * - ``launcher-src/verify-icons.py``
     - ``bin/launcher/verify-icons.py``
   * - ``sql/常用查询.sql``
     - ``db/queries/常用查询.sql``

调整方式
--------------------------------------------------

普通源码与资源移动后同步路径引用；Markdown 工程说明转换为 RST 的标题、列表、表格和代码块，内部链接按新位置重算。SQL、规范源、manifest.json、两个 EXE、字体和图标保持字节。旧 launcher-src/、icons/、frontend/、sql/ 只在迁移完成且为空时移除；历史报告及批次中的同名目录不处理。
