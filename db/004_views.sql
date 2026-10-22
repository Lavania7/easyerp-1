-- Generated from readme.md. Run bin/build_schema.py to regenerate.
-- readme.md:3913
CREATE VIEW finance."账户流水标准化表" AS
SELECT f.*, a."币种" FROM finance."资金流水表" f JOIN finance."资金账户档案表" a USING ("账户ID");

CREATE VIEW finance."往来未结查询" AS
SELECT r.*, r."原金额" - r."已结金额" AS "未结金额" FROM finance."往来未结明细表" r;

CREATE VIEW finance."账户核对与差异表" AS
SELECT c.*, b."账户ID", b."期间开始", b."期间结束", b."期末余额" AS "原始余额", b."期末余额" - c."滚动余额" AS "差额" FROM finance."账户核对表" c JOIN finance."账户期间余额表" b USING ("余额记录ID");

CREATE VIEW finance."分账表" AS
SELECT l.*, v."主体ID", v."凭证日期", v."所属月份", v."凭证号" FROM finance."会计分录表" l JOIN finance."会计凭证表" v USING ("凭证ID") WHERE v."状态" = '已过账';

CREATE VIEW production."验收交付表" AS
SELECT a.*, r."采购订单行ID", r."到货时间" FROM production."验收记录表" a JOIN production."到货记录表" r USING ("到货ID");

CREATE VIEW production."库存收发明细表" AS
SELECT * FROM production."库存变动表";

CREATE VIEW production."生产执行交付表" AS
SELECT w.*,
 (SELECT count(*) FROM production."生产领退料表" x WHERE x."工单号"=w."工单号") AS "领退料事件数",
 (SELECT sum(x."有效工时") FROM production."生产工时表" x WHERE x."工单号"=w."工单号" AND x."人员ID" IS NOT NULL) AS "人员有效工时",
 (SELECT sum(x."合格数量") FROM production."完工记录表" x WHERE x."工单号"=w."工单号") AS "累计合格数量"
FROM production."生产工单表" w;

CREATE VIEW production."发货履约与质量反馈表" AS
SELECT f.*, l."订单ID", coalesce(c."产品版本ID", l."产品版本ID") AS "产品版本ID", l."收货信息" FROM production."发货记录表" f JOIN sales."销售订单行表" l USING ("销售订单行ID") LEFT JOIN sales."订单组合明细表" x ON x."订单组合明细ID"=f."订单组合明细ID" LEFT JOIN sales."组合商品明细表" c ON c."组合明细ID"=x."组合明细ID";

CREATE VIEW rd."已核定BOM明细表" AS
SELECT l.*, v."MID" FROM rd."BOM明细表" l JOIN rd."物料版本表" v USING ("物料版本ID");

CREATE VIEW rd."研发验证及变更结论" AS
SELECT * FROM rd."设计变更与验证表";

CREATE VIEW rd."研发实际投入说明" AS
SELECT * FROM rd."研发投入归属表";

CREATE VIEW sales."订单与履约交付表" AS
SELECT l.*, o."客户ID", o."渠道ID" FROM sales."销售订单行表" l JOIN sales."销售订单登记表" o USING ("订单ID");

CREATE VIEW sales."售后反馈表" AS
SELECT * FROM sales."售后事件表";

CREATE VIEW sales."需求反馈表" AS
SELECT * FROM sales."客户需求表";

CREATE VIEW legal."合规事项与整改跟踪表" AS
SELECT r.*, c."规则ID" FROM legal."整改跟踪表" r JOIN legal."合规自查表" c USING ("自查ID");
