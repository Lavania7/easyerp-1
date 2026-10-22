-- easyERP 常用查询。以下语句均为只读，可逐段选中后按 F5 执行。
-- 在 pgAdmin 中选择 easyerp_v02 数据库，打开“查询工具 / Query Tool”。

-- 1. 当前连接信息
SELECT current_database() AS 数据库, current_user AS 账户, inet_server_port() AS 端口;

-- 2. 业务表与标准视图
SELECT table_schema AS 部门, table_name AS 名称, table_type AS 类型
FROM information_schema.tables
WHERE table_schema IN ('finance','legal','production','rd','sales','analysis')
ORDER BY table_schema, table_type, table_name;

-- 3. 销售订单及履约
SELECT * FROM sales."订单与履约交付表" LIMIT 200;

-- 4. 生产执行
SELECT * FROM production."生产执行交付表" LIMIT 200;

-- 5. 实际资金流水
SELECT * FROM finance."账户流水标准化表" ORDER BY "发生时间" DESC LIMIT 200;

-- 6. 资金核对与跨记录问题
SELECT * FROM erp_ops."资金核对" LIMIT 200;
SELECT * FROM erp_ops."业务核对问题" LIMIT 200;

-- 7. 查看一个标准视图的 SQL 定义
SELECT pg_get_viewdef('sales."订单与履约交付表"'::regclass, true) AS 视图SQL;
