.. sql-source-newline: CRLF

easyerp数据规范，业务网表和流程自动化说明
================================================


“人工”指无法被计算程序、AGENT拉取和处理，或必须人工审核、确认语义的内容；
“自动”指可以被计算程序或AGENT处理的内容。
自动生成的前提是原始数据已留存；计算程序或AGENT可以导入、查重、校验和生成候选，涉及业务性质、适用性、金额归属和发布批准的内容由人工确认。

“需要持有”指部门应该主动爬取或整理相关内容；
“默认交出”指即使没有其他部门要求，部门也应该主动完成并存档的内容。


.. note::

   数据结构规则


#. 业务动作第一次发生在哪里，哪个部门就拥有唯一主录数据
#. 一张表只代表一类主录数据，一个主录数据只有一类主录ID，表的每行对应该类ID的一条记录，每条记录拥有自己的完整字段
#. 除了部门自己的主录数据，仅引用其他部门的ID
#. 其他ID仅作引用，不在本表定义，不展开完整字段


SQL数据结构规则
------------------


本版采用PostgreSQL语法。业务章节及原说明保留，以下SQL是对原说明的具体化；原文中的“沿用、汇总、引用”按本节明确为主表、关联表、视图或输出快照。


.. list-table::
   :header-rows: 1
   :widths: auto

   * - 自然语言规则
     - SQL对应结构
   * - 首次业务发生部门拥有唯一主录
     - 用finance、legal、production、rd、sales、analysis六个schema表达业务归属，每类事实只建一张权威主表
   * - 一表一类主录，每行一条记录
     - 每表一个text类型主键；具体粒度见各表说明；业务编号组合另设UNIQUE
   * - 每条记录有完整字段
     - CREATE TABLE列出全部列、类型及是否必填；没有NOT NULL的列可为空，表示尚未发生或尚未核定
   * - 部门外只引用ID
     - 跨schema只存外键，不复制其他部门的名称、规格、金额等主录字段；前端通过关联查询显示
   * - 其他ID仅作引用
     - 每个引用落到明确表的主键；“甲ID或乙ID”拆成明确外键并用CHECK规定选择条件
   * - 同一业务发生多次
     - 每次建立独立事件ID；父记录一对多由明细外键表达；多对多建立带自身主键的关联表
   * - 默认交出数据
     - 原表查询、视图或已发布快照；相同数据不另建可独立修改的第二主录


字段类型统一采用：编号text；描述text；日期date；事件时间timestamptz；金额numeric(20,4)；数量numeric(20,6)；工时numeric(12,4)；币种char(3)。金额小数位是本版存储精度，最终舍入仍由业务口径确定。ID由录入或导入过程生成并保证所在表内唯一，不要求跨所有表使用同一种业务编号。

字段语义补充：所属月份以当月第一天表示；期间开始、期间结束均含当天；有效期采用生效日期含当天、失效日期不含当天，失效日期为空表示尚未设定结束。事件时间保存时区，按主体约定时区划分业务日期。资金金额为非负数，收支方向单列；发票及收入成本调整金额的符号按已核定口径填写，不通过缺省零表示未核定。各表状态值已列为本版默认枚举并写入CHECK；状态转移仍由实际业务动作触发。视图中“已过账”专指已完成借贷核对的会计凭证。

本版补充的归属约定：人员基础身份暂由财务维护，设备和库位由生产维护，渠道与销售组合由销售维护，单位及物品版本由研发维护；各部门的工时、交付、采纳、执行和整改处理仍由实际发生部门持有。这些是本版建模默认，组织分工确认后可整体调整归属。

产品和物料分别保留PID、MID；业务记录引用产品版本ID或物料版本ID，PID、MID由对应版本查询得到。交易单位与物品基本单位分别处理，换算必须引用适用换算记录。候选、已确认、关闭等状态按各表业务含义使用，不将所有不同状态压成一个统一“完成”。

创建顺序：先执行下面的schema块，再按文档顺序执行各部门CREATE TABLE块，最后执行外键块和视图块。所有外键集中在主表创建完成后添加，以处理部门间相互引用。建表时允许业务尚未发生的结果引用为空；不强制先填写下游结果。

.. sql-source-line: 43

.. code-block:: sql

   CREATE SCHEMA finance;
   CREATE SCHEMA legal;
   CREATE SCHEMA production;
   CREATE SCHEMA rd;
   CREATE SCHEMA sales;
   CREATE SCHEMA analysis;


各部门持有数据和交付内容说明
----------------------------


.. note::

   说明格式


<表名>:<主录ID名>,<各字段>,<需引用的ID>

<文档名>:<文档内容>

<压缩包名>:<压缩包内容>


财务：
~~~~~~


财务需要持有的是：

资金账户档案表：主录ID为账户ID；字段及引用：账户名、所属主体ID、平台、币种、账户性质、启用停用日期，人工确认。旧余额来源路径受控归档，不再作为账户业务字段。
各账户流水单：保存原始网银导出文件。
资金流水表：主录ID为资金记录ID；字段及引用：账户ID、日期、金额及原始流水来源，自动导入。
账户期间余额表：主录ID为余额记录ID；字段及引用：账户ID、统计期间、期初余额、期末余额及来源，导出及人工确认。
会计政策表：主录ID为政策ID；字段及引用：适用准则、记账方法、收入确认口径、成本核算方法，人工确认。
会计科目表：主录ID为科目ID；字段及引用：科目名称及分类，人工确认。
资金用途核定表：主录ID为用途核定ID；字段及引用：资金记录ID、关联业务ID、用途、归属部门、所属期间及依据，自动生成候选，人工核定。
结算分摊表：主录ID为分摊ID；字段及引用：用途核定ID、关联业务ID、分摊金额、方向、费用类型及依据，人工确认，自动核对。
内部划转对应表：主录ID为划转对应ID；字段及引用：转出及转入资金记录ID、划转金额、到账时间、手续费、差异原因及依据，自动匹配候选，人工确认。
重复记录对应表：主录ID为重复对应ID；字段及引用：原资金记录ID、重复资金记录ID、重复事件标识及确认依据，自动匹配候选，人工确认。
期初及结账核实表：主录ID为核实ID；字段及引用：基准日期、科目ID、金额、来源凭证、核定状态、差异及确认人，人工确认。
往来未结明细表：主录ID为未结记录ID；字段及引用：基准日期、往来类型、对方ID、业务单据ID、原金额、已结金额、未结金额、币种及到期日，自动计算，人工确认。
费用归属表：主录ID为费用ID；字段及引用：发生日期、所属期间、人员或供应商ID、费用类型、金额、部门、项目ID或工单号、资金记录ID及凭证，人工确认，自动汇总。
工时计价表：主录ID为计价ID；字段及引用：工时记录ID、计费依据、应计金额、所属期间及确认人，引用工时ID，人工核定计价。
收入成本确认表：主录ID为确认ID；字段及引用：所属月份、销售订单行ID、工单号、确认收入、税额、结转成本及确认依据，人工核定，自动汇总。
发票登记表：主录ID为票据ID；字段及引用：发票号码、日期、蓝字或红字、原票ID、价税合计、税额及文件路径，人工核验。
发票分摊表：主录ID为发票分摊ID；字段及引用：票据ID、销售或采购订单行ID、分摊金额及分摊税额，人工确认，自动核对。
资产台账：主录ID为资产ID；字段及引用：名称、所属主体ID、购置及启用日期、原值、折旧或摊销政策ID、累计折旧或摊销、处置日期及凭证，人工确认，自动计算。
纳税申报与缴款记录表：主录ID为记录ID；字段及引用：申报期间、税种、申报金额、申报及缴退日期、缴退金额、状态、资金记录ID及回执路径，人工确认，自动整理。

财务需要默认交出的是：

账户流水标准化表：按资金记录ID整理原始流水，自动。
资产负债表、现金流量表、利润表和分账表：依据已核定凭证、期初余额、会计政策及结账事项生成。
账户核对与差异表：账户核对ID、账户ID、统计月份、原始余额、滚动余额、差额、划转对应ID、重复对应ID及核定状态，自动核对，人工处理差异。
结算、计价、收入成本及纳税记录：按各表ID交付已核定结果。
财务交付说明：列明已核定部分、未核事项及期间覆盖。


SQL记录粒度与字段定义
^^^^^^^^^^^^^^^^^^^^^^^^


下列表中，ID主键标识本表主录；引用列的目标统一列在文末外键定义中。


人员档案表
""""""""""


记录粒度：一名内部人员的基础身份记录。

补充引用来源；本版暂由财务维护人员基础档案，工时仍由实际发生部门记录。基准工资使用金额类型 numeric(20,4)，未知为 NULL，真实零保留；基准工资不是实际发薪事实，不自动生成付款或费用。工资账户开户行和工资账户ID为可空文本，账号保留前导零，不引用本公司资金账户档案表。

.. sql-source-line: 105

.. code-block:: sql

   CREATE TABLE finance."人员档案表" (
     "人员ID" text PRIMARY KEY,
     "姓名" text NOT NULL,
     "部门" text NOT NULL,
     "任职开始日期" date,
     "任职结束日期" date,
     "基准工资" numeric(20,4),
     "工资账户开户行" text,
     "工资账户ID" text,
     CONSTRAINT finance_people_base_salary_nonnegative CHECK ("基准工资" >= 0)
   );


资金账户档案表
""""""""""""""


记录粒度：一个资金账户。

引用关系：主体ID → legal.公司主体档案表。

.. sql-source-line: 121

.. code-block:: sql

   CREATE TABLE finance."资金账户档案表" (
     "账户ID" text PRIMARY KEY,
     "账户名" text NOT NULL,
     "主体ID" text NOT NULL,
     "平台" text NOT NULL,
     "币种" char(3) NOT NULL,
     "账户性质" text NOT NULL,
     "启用日期" date,
     "停用日期" date
   );


流水文件登记表
""""""""""""""


记录粒度：一次网银原始文件导出。

引用关系：账户ID → finance.资金账户档案表。

.. sql-source-line: 141

.. code-block:: sql

   CREATE TABLE finance."流水文件登记表" (
     "流水文件ID" text PRIMARY KEY,
     "账户ID" text NOT NULL,
     "导出时间" timestamptz NOT NULL,
     "覆盖开始日期" date,
     "覆盖结束日期" date,
     "文件路径" text NOT NULL,
     "文件校验值" text NOT NULL
   );


资金流水表
""""""""""


记录粒度：一个平台实际资金事件。

引用关系：账户ID → finance.资金账户档案表。

.. sql-source-line: 159

.. code-block:: sql

   CREATE TABLE finance."资金流水表" (
     "资金记录ID" text PRIMARY KEY,
     "账户ID" text NOT NULL,
     "发生时间" timestamptz NOT NULL,
     "金额" numeric(20,4) NOT NULL,
     "收支方向" text NOT NULL,
     "平台交易号" text,
     "交易摘要" text,
     CHECK ("金额" >= 0),
     CHECK ("收支方向" IN ('收入','支出'))
   );


流水来源明细表
""""""""""""""


记录粒度：资金事件在一个导出文件中的一次出现。

同一事件可在多个导出快照出现，不重复建立资金主录。

引用关系：资金记录ID → finance.资金流水表；流水文件ID → finance.流水文件登记表。

.. sql-source-line: 181

.. code-block:: sql

   CREATE TABLE finance."流水来源明细表" (
     "流水来源ID" text PRIMARY KEY,
     "资金记录ID" text NOT NULL,
     "流水文件ID" text NOT NULL,
     "来源行号" integer NOT NULL,
     UNIQUE ("流水文件ID", "来源行号")
   );


账户期间余额表
""""""""""""""


记录粒度：一个账户一个期间的一版期初和期末余额。

引用关系：账户ID → finance.资金账户档案表；确认人ID → finance.人员档案表。

.. sql-source-line: 197

.. code-block:: sql

   CREATE TABLE finance."账户期间余额表" (
     "余额记录ID" text PRIMARY KEY,
     "账户ID" text NOT NULL,
     "期间开始" date NOT NULL,
     "期间结束" date NOT NULL,
     "余额版本" integer NOT NULL,
     "期初余额" numeric(20,4) NOT NULL,
     "期末余额" numeric(20,4) NOT NULL,
     "来源" text NOT NULL,
     "确认人ID" text,
     UNIQUE ("账户ID", "期间开始", "期间结束", "余额版本"),
     CHECK ("期间结束" >= "期间开始")
   );


会计政策表
""""""""""


记录粒度：一项政策的一版适用口径。

.. sql-source-line: 217

.. code-block:: sql

   CREATE TABLE finance."会计政策表" (
     "政策ID" text PRIMARY KEY,
     "政策名称" text NOT NULL,
     "政策版本" text NOT NULL,
     "适用准则" text NOT NULL,
     "记账方法" text,
     "收入确认口径" text,
     "成本核算方法" text,
     "生效日期" date NOT NULL,
     "失效日期" date,
     UNIQUE ("政策名称", "政策版本")
   );


会计科目表
""""""""""


记录粒度：一个主体科目体系中的一个科目。

引用关系：主体ID → legal.公司主体档案表；上级科目ID → finance.会计科目表。

.. sql-source-line: 238

.. code-block:: sql

   CREATE TABLE finance."会计科目表" (
     "科目ID" text PRIMARY KEY,
     "主体ID" text NOT NULL,
     "科目代码" text NOT NULL,
     "科目名称" text NOT NULL,
     "分类" text NOT NULL,
     "上级科目ID" text,
     "正常余额方向" text,
     UNIQUE ("主体ID", "科目代码")
   );


资金用途核定表
""""""""""""""


记录粒度：对一笔资金中的一部分用途的一次核定。

候选阶段允许尚未选定业务；同笔资金可形成多个用途核定。 本版状态：待核定、已核定、已撤销。

引用关系：资金记录ID → finance.资金流水表；确认人ID → finance.人员档案表；销售订单行ID → sales.销售订单行表；采购订单行ID → production.采购订单行表；工单号 → production.生产工单表；项目ID → rd.项目登记表；售后事件ID → sales.售后事件表；费用ID → finance.费用归属表。

.. sql-source-line: 259

.. code-block:: sql

   CREATE TABLE finance."资金用途核定表" (
     "用途核定ID" text PRIMARY KEY,
     "资金记录ID" text NOT NULL,
     "用途" text,
     "归属部门" text,
     "所属月份" date,
     "核定金额" numeric(20,4),
     "依据" text,
     "状态" text NOT NULL,
     "确认人ID" text,
     "确认时间" timestamptz,
     "销售订单行ID" text,
     "采购订单行ID" text,
     "工单号" text,
     "项目ID" text,
     "售后事件ID" text,
     "费用ID" text,
     CHECK (num_nonnulls("销售订单行ID", "采购订单行ID", "工单号", "项目ID", "售后事件ID", "费用ID") <= 1),
     CHECK ("状态" IN ('待核定', '已核定', '已撤销'))
   );


结算分摊表
""""""""""


记录粒度：一笔资金对一个业务对象的一条结算分摊。

资金记录、账户及币种沿用途核定查询，不另存业务名称或整笔金额。

引用关系：用途核定ID → finance.资金用途核定表；销售订单行ID → sales.销售订单行表；采购订单行ID → production.采购订单行表；工单号 → production.生产工单表；项目ID → rd.项目登记表；售后事件ID → sales.售后事件表；费用ID → finance.费用归属表。

.. sql-source-line: 290

.. code-block:: sql

   CREATE TABLE finance."结算分摊表" (
     "分摊ID" text PRIMARY KEY,
     "用途核定ID" text NOT NULL,
     "分摊金额" numeric(20,4) NOT NULL,
     "方向" text NOT NULL,
     "费用类型" text,
     "凭证路径" text,
     "销售订单行ID" text,
     "采购订单行ID" text,
     "工单号" text,
     "项目ID" text,
     "售后事件ID" text,
     "费用ID" text,
     CHECK (num_nonnulls("销售订单行ID", "采购订单行ID", "工单号", "项目ID", "售后事件ID", "费用ID") = 1),
     CHECK ("分摊金额" > 0)
   );


内部划转对应表
""""""""""""""


记录粒度：一笔转出和一笔转入之间的一条匹配。

 本版状态：待核定、已核定、已撤销。

引用关系：转出资金记录ID → finance.资金流水表；转入资金记录ID → finance.资金流水表。

.. sql-source-line: 317

.. code-block:: sql

   CREATE TABLE finance."内部划转对应表" (
     "划转对应ID" text PRIMARY KEY,
     "转出资金记录ID" text NOT NULL,
     "转入资金记录ID" text NOT NULL,
     "划转金额" numeric(20,4) NOT NULL,
     "到账时间" timestamptz,
     "手续费" numeric(20,4),
     "差异原因" text,
     "确认依据" text,
     "状态" text NOT NULL,
     UNIQUE ("转出资金记录ID", "转入资金记录ID"),
     CHECK ("转出资金记录ID" <> "转入资金记录ID"),
     CHECK ("状态" IN ('待核定', '已核定', '已撤销'))
   );


重复记录对应表
""""""""""""""


记录粒度：一个重复资金记录与其保留记录的对应。

 本版状态：待核定、已核定、已撤销。

引用关系：原资金记录ID → finance.资金流水表；重复资金记录ID → finance.资金流水表。

.. sql-source-line: 342

.. code-block:: sql

   CREATE TABLE finance."重复记录对应表" (
     "重复对应ID" text PRIMARY KEY,
     "原资金记录ID" text NOT NULL,
     "重复资金记录ID" text NOT NULL,
     "重复事件标识" text,
     "确认依据" text,
     "状态" text NOT NULL,
     UNIQUE ("重复资金记录ID"),
     CHECK ("原资金记录ID" <> "重复资金记录ID"),
     CHECK ("状态" IN ('待核定', '已核定', '已撤销'))
   );


期初及结账核实表
""""""""""""""""


记录粒度：某科目在某基准日的一次余额核定。

 本版状态：待核定、已核定、已撤销。

引用关系：科目ID → finance.会计科目表；确认人ID → finance.人员档案表。

.. sql-source-line: 364

.. code-block:: sql

   CREATE TABLE finance."期初及结账核实表" (
     "核实ID" text PRIMARY KEY,
     "科目ID" text NOT NULL,
     "基准日期" date NOT NULL,
     "核实类型" text NOT NULL,
     "金额" numeric(20,4) NOT NULL,
     "币种" char(3) NOT NULL,
     "来源凭证" text,
     "状态" text NOT NULL,
     "差异说明" text,
     "确认人ID" text,
     "核定版本" integer NOT NULL,
     UNIQUE ("科目ID", "基准日期", "核实类型", "核定版本"),
     CHECK ("状态" IN ('待核定', '已核定', '已撤销'))
   );


往来未结明细表
""""""""""""""


记录粒度：某往来业务在一个基准日的一版核定余额。

未结金额在视图中以原金额减已结金额计算；基准日余额是一项核定结果。

引用关系：客户ID → sales.客户档案表；供应商ID → production.供应商档案表；销售订单行ID → sales.销售订单行表；采购订单行ID → production.采购订单行表；工单号 → production.生产工单表；项目ID → rd.项目登记表；售后事件ID → sales.售后事件表；费用ID → finance.费用归属表。

.. sql-source-line: 390

.. code-block:: sql

   CREATE TABLE finance."往来未结明细表" (
     "未结记录ID" text PRIMARY KEY,
     "基准日期" date NOT NULL,
     "往来类型" text NOT NULL,
     "客户ID" text,
     "供应商ID" text,
     "原金额" numeric(20,4) NOT NULL,
     "已结金额" numeric(20,4) NOT NULL,
     "币种" char(3) NOT NULL,
     "到期日" date,
     "核定版本" integer NOT NULL,
     "依据" text,
     "销售订单行ID" text,
     "采购订单行ID" text,
     "工单号" text,
     "项目ID" text,
     "售后事件ID" text,
     "费用ID" text,
     CHECK (num_nonnulls("客户ID", "供应商ID") = 1),
     CHECK (num_nonnulls("销售订单行ID", "采购订单行ID", "工单号", "项目ID", "售后事件ID", "费用ID") = 1)
   );


费用归属表
""""""""""


记录粒度：一笔已划分到单一期间和对象的费用归属。

 本版状态：待核定、已核定、已撤销。

引用关系：人员ID → finance.人员档案表；供应商ID → production.供应商档案表；项目ID → rd.项目登记表；工单号 → production.生产工单表；资金记录ID → finance.资金流水表。

.. sql-source-line: 422

.. code-block:: sql

   CREATE TABLE finance."费用归属表" (
     "费用ID" text PRIMARY KEY,
     "发生日期" date NOT NULL,
     "所属月份" date NOT NULL,
     "费用类型" text NOT NULL,
     "金额" numeric(20,4) NOT NULL,
     "币种" char(3) NOT NULL,
     "部门" text NOT NULL,
     "人员ID" text,
     "供应商ID" text,
     "项目ID" text,
     "工单号" text,
     "资金记录ID" text,
     "凭证路径" text,
     "状态" text NOT NULL,
     CHECK (num_nonnulls("人员ID", "供应商ID") <= 1),
     CHECK (num_nonnulls("项目ID", "工单号") <= 1),
     CHECK ("状态" IN ('待核定', '已核定', '已撤销'))
   );


工时计价表
""""""""""


记录粒度：一条实际工时在一个计价期间的一条金额分配。

同一工时可分期或分摊计价；累计计价工时由跨行核对控制。 本版状态：待核定、已核定、已撤销。

引用关系：生产工时ID → production.生产工时表；研发工时ID → rd.研发工时表；确认人ID → finance.人员档案表。

.. sql-source-line: 452

.. code-block:: sql

   CREATE TABLE finance."工时计价表" (
     "计价ID" text PRIMARY KEY,
     "生产工时ID" text,
     "研发工时ID" text,
     "所属月份" date NOT NULL,
     "计价批次" text NOT NULL,
     "计价工时" numeric(12,4) NOT NULL,
     "计费依据" text NOT NULL,
     "应计金额" numeric(20,4) NOT NULL,
     "币种" char(3) NOT NULL,
     "确认人ID" text,
     "状态" text NOT NULL,
     CHECK (num_nonnulls("生产工时ID", "研发工时ID") = 1),
     CHECK ("计价工时" >= 0),
     CHECK ("状态" IN ('待核定', '已核定', '已撤销'))
   );


收入成本确认表
""""""""""""""


记录粒度：一个订单行某月的一条收入成本确认明细。

金额为核定结果；未核定成本允许NULL，不能默认成0。 本版状态：待核定、已核定、已撤销。

引用关系：销售订单行ID → sales.销售订单行表；工单号 → production.生产工单表；政策ID → finance.会计政策表。

.. sql-source-line: 479

.. code-block:: sql

   CREATE TABLE finance."收入成本确认表" (
     "确认ID" text PRIMARY KEY,
     "所属月份" date NOT NULL,
     "销售订单行ID" text NOT NULL,
     "工单号" text,
     "确认批次" text NOT NULL,
     "行号" integer NOT NULL,
     "确认数量" numeric(20,6) NOT NULL,
     "确认收入" numeric(20,4),
     "税额" numeric(20,4),
     "结转成本" numeric(20,4),
     "币种" char(3) NOT NULL,
     "政策ID" text NOT NULL,
     "确认依据" text NOT NULL,
     "状态" text NOT NULL,
     UNIQUE ("确认批次", "行号"),
     CHECK ("状态" IN ('待核定', '已核定', '已撤销'))
   );


发票登记表
""""""""""


记录粒度：一张蓝字或红字发票。

引用关系：开票主体ID → legal.公司主体档案表；原票ID → finance.发票登记表。

.. sql-source-line: 506

.. code-block:: sql

   CREATE TABLE finance."发票登记表" (
     "票据ID" text PRIMARY KEY,
     "发票号码" text NOT NULL,
     "发票类型" text NOT NULL,
     "日期" date NOT NULL,
     "开票主体ID" text NOT NULL,
     "原票ID" text,
     "价税合计" numeric(20,4) NOT NULL,
     "税额" numeric(20,4) NOT NULL,
     "币种" char(3) NOT NULL,
     "文件路径" text NOT NULL,
     UNIQUE ("开票主体ID", "发票号码")
   );


发票分摊表
""""""""""


记录粒度：一张发票对一个业务行的一条分摊。

引用关系：票据ID → finance.发票登记表；销售订单行ID → sales.销售订单行表；采购订单行ID → production.采购订单行表。

.. sql-source-line: 528

.. code-block:: sql

   CREATE TABLE finance."发票分摊表" (
     "发票分摊ID" text PRIMARY KEY,
     "票据ID" text NOT NULL,
     "销售订单行ID" text,
     "采购订单行ID" text,
     "分摊金额" numeric(20,4) NOT NULL,
     "分摊税额" numeric(20,4) NOT NULL,
     CHECK (num_nonnulls("销售订单行ID", "采购订单行ID") = 1)
   );


资产台账
""""""""


记录粒度：一项可独立核算的资产。

累计金额必须同时注明截至日期；具体折旧规则由引用政策确定。

引用关系：主体ID → legal.公司主体档案表；政策ID → finance.会计政策表。

.. sql-source-line: 548

.. code-block:: sql

   CREATE TABLE finance."资产台账" (
     "资产ID" text PRIMARY KEY,
     "名称" text NOT NULL,
     "主体ID" text NOT NULL,
     "购置日期" date NOT NULL,
     "启用日期" date,
     "原值" numeric(20,4) NOT NULL,
     "币种" char(3) NOT NULL,
     "政策ID" text NOT NULL,
     "累计折旧或摊销" numeric(20,4),
     "金额截至日期" date,
     "处置日期" date,
     "凭证路径" text
   );


纳税申报记录表
""""""""""""""


记录粒度：一个申报主体某期间某税种的一次申报。

原纳税申报与缴款记录拆为申报主录和缴退明细。 本版状态：草稿、已申报、已撤销。

引用关系：主体ID → legal.公司主体档案表。

.. sql-source-line: 573

.. code-block:: sql

   CREATE TABLE finance."纳税申报记录表" (
     "记录ID" text PRIMARY KEY,
     "主体ID" text NOT NULL,
     "期间开始" date NOT NULL,
     "期间结束" date NOT NULL,
     "税种" text NOT NULL,
     "申报版本" integer NOT NULL,
     "申报金额" numeric(20,4) NOT NULL,
     "币种" char(3) NOT NULL,
     "申报日期" date,
     "状态" text NOT NULL,
     "回执路径" text,
     UNIQUE ("主体ID", "期间开始", "期间结束", "税种", "申报版本"),
     CHECK ("状态" IN ('草稿', '已申报', '已撤销'))
   );


税款缴退明细表
""""""""""""""


记录粒度：一次申报对应的一次缴税或退税。

引用关系：记录ID → finance.纳税申报记录表；资金记录ID → finance.资金流水表。

.. sql-source-line: 597

.. code-block:: sql

   CREATE TABLE finance."税款缴退明细表" (
     "缴退ID" text PRIMARY KEY,
     "记录ID" text NOT NULL,
     "资金记录ID" text NOT NULL,
     "缴退日期" date NOT NULL,
     "缴退类型" text NOT NULL,
     "缴退金额" numeric(20,4) NOT NULL,
     "回执路径" text
   );


账户核对表
""""""""""


记录粒度：一个账户一版期间核对结果。

差额由期末余额减滚动余额计算；划转和重复记录从对应资金明细查询。 本版核定状态：待核对、有差异、已核定。

引用关系：余额记录ID → finance.账户期间余额表。

.. sql-source-line: 617

.. code-block:: sql

   CREATE TABLE finance."账户核对表" (
     "账户核对ID" text PRIMARY KEY,
     "余额记录ID" text NOT NULL,
     "滚动余额" numeric(20,4) NOT NULL,
     "核定状态" text NOT NULL,
     "核对说明" text,
     "核对版本" integer NOT NULL,
     UNIQUE ("余额记录ID", "核对版本"),
     CHECK ("核定状态" IN ('待核对', '有差异', '已核定'))
   );


会计凭证表
""""""""""


记录粒度：一个主体的一张会计凭证。

为原分账表和财务报表补充明确的记账来源。 本版状态：草稿、已核对、已过账、已作废。

引用关系：主体ID → legal.公司主体档案表；政策ID → finance.会计政策表；确认人ID → finance.人员档案表。

.. sql-source-line: 638

.. code-block:: sql

   CREATE TABLE finance."会计凭证表" (
     "凭证ID" text PRIMARY KEY,
     "主体ID" text NOT NULL,
     "凭证日期" date NOT NULL,
     "所属月份" date NOT NULL,
     "凭证号" text NOT NULL,
     "摘要" text NOT NULL,
     "状态" text NOT NULL,
     "政策ID" text NOT NULL,
     "确认人ID" text,
     UNIQUE ("主体ID", "所属月份", "凭证号"),
     CHECK ("状态" IN ('草稿', '已核对', '已过账', '已作废'))
   );


会计分录表
""""""""""


记录粒度：一张凭证内的一条科目分录。

引用关系：凭证ID → finance.会计凭证表；科目ID → finance.会计科目表；资金记录ID → finance.资金流水表；确认ID → finance.收入成本确认表；费用ID → finance.费用归属表；计价ID → finance.工时计价表；核实ID → finance.期初及结账核实表。

.. sql-source-line: 660

.. code-block:: sql

   CREATE TABLE finance."会计分录表" (
     "分录ID" text PRIMARY KEY,
     "凭证ID" text NOT NULL,
     "行号" integer NOT NULL,
     "科目ID" text NOT NULL,
     "借方金额" numeric(20,4) NOT NULL,
     "贷方金额" numeric(20,4) NOT NULL,
     "币种" char(3) NOT NULL,
     "资金记录ID" text,
     "确认ID" text,
     "费用ID" text,
     "计价ID" text,
     "核实ID" text,
     UNIQUE ("凭证ID", "行号"),
     CHECK ("借方金额" >= 0 AND "贷方金额" >= 0),
     CHECK (("借方金额" > 0 AND "贷方金额" = 0) OR ("贷方金额" > 0 AND "借方金额" = 0))
   );


报表批次表
""""""""""


记录粒度：某主体某期间的一版财务报表生成结果。

引用关系：主体ID → legal.公司主体档案表；政策ID → finance.会计政策表。

.. sql-source-line: 686

.. code-block:: sql

   CREATE TABLE finance."报表批次表" (
     "报表批次ID" text PRIMARY KEY,
     "主体ID" text NOT NULL,
     "期间开始" date NOT NULL,
     "期间结束" date NOT NULL,
     "报表版本" integer NOT NULL,
     "币种" char(3) NOT NULL,
     "政策ID" text NOT NULL,
     "生成时间" timestamptz NOT NULL,
     "核定范围说明" text NOT NULL,
     "未核事项" text,
     "交付说明路径" text,
     UNIQUE ("主体ID", "期间开始", "期间结束", "报表版本")
   );


资产负债表
""""""""""


记录粒度：一个报表批次中的一个报表项目。

报表输出快照，不构成新的业务发生主录。

引用关系：报表批次ID → finance.报表批次表。

.. sql-source-line: 711

.. code-block:: sql

   CREATE TABLE finance."资产负债表" (
     "资产负债行ID" text PRIMARY KEY,
     "报表批次ID" text NOT NULL,
     "项目代码" text NOT NULL,
     "项目名称" text NOT NULL,
     "显示顺序" integer NOT NULL,
     "期初金额" numeric(20,4),
     "期末金额" numeric(20,4),
     UNIQUE ("报表批次ID", "项目代码")
   );


现金流量表
""""""""""


记录粒度：一个报表批次中的一个报表项目。

报表输出快照，不构成新的业务发生主录。

引用关系：报表批次ID → finance.报表批次表。

.. sql-source-line: 732

.. code-block:: sql

   CREATE TABLE finance."现金流量表" (
     "现金流量行ID" text PRIMARY KEY,
     "报表批次ID" text NOT NULL,
     "项目代码" text NOT NULL,
     "项目名称" text NOT NULL,
     "显示顺序" integer NOT NULL,
     "本期金额" numeric(20,4),
     UNIQUE ("报表批次ID", "项目代码")
   );


利润表
""""""


记录粒度：一个报表批次中的一个报表项目。

报表输出快照，不构成新的业务发生主录。

引用关系：报表批次ID → finance.报表批次表。

.. sql-source-line: 752

.. code-block:: sql

   CREATE TABLE finance."利润表" (
     "利润行ID" text PRIMARY KEY,
     "报表批次ID" text NOT NULL,
     "项目代码" text NOT NULL,
     "项目名称" text NOT NULL,
     "显示顺序" integer NOT NULL,
     "本期金额" numeric(20,4),
     UNIQUE ("报表批次ID", "项目代码")
   );


报表项目映射表
""""""""""""""


记录粒度：一版会计政策下一个科目到某报表项目的一条映射。

引用关系：政策ID → finance.会计政策表；科目ID → finance.会计科目表。

.. sql-source-line: 770

.. code-block:: sql

   CREATE TABLE finance."报表项目映射表" (
     "项目映射ID" text PRIMARY KEY,
     "政策ID" text NOT NULL,
     "报表类型" text NOT NULL,
     "项目代码" text NOT NULL,
     "科目ID" text NOT NULL,
     "取数口径" text NOT NULL,
     "计算方向" text NOT NULL,
     "生效日期" date NOT NULL,
     "失效日期" date,
     UNIQUE ("政策ID", "报表类型", "项目代码", "科目ID", "生效日期")
   );


资产负债表来源明细表
""""""""""""""""""""


记录粒度：一个报表结果行纳入的一条分录或期初核定。

引用关系：结果行ID → finance.资产负债表；分录ID → finance.会计分录表；核实ID → finance.期初及结账核实表；项目映射ID → finance.报表项目映射表。

.. sql-source-line: 791

.. code-block:: sql

   CREATE TABLE finance."资产负债表来源明细表" (
     "资产负债来源ID" text PRIMARY KEY,
     "结果行ID" text NOT NULL,
     "分录ID" text,
     "核实ID" text,
     "归集金额" numeric(20,4) NOT NULL,
     "金额列" text NOT NULL,
     "项目映射ID" text,
     CHECK (num_nonnulls("分录ID", "核实ID") = 1)
   );


现金流量表来源明细表
""""""""""""""""""""


记录粒度：一个报表结果行纳入的一条分录或期初核定。

引用关系：结果行ID → finance.现金流量表；分录ID → finance.会计分录表；核实ID → finance.期初及结账核实表；项目映射ID → finance.报表项目映射表。

.. sql-source-line: 810

.. code-block:: sql

   CREATE TABLE finance."现金流量表来源明细表" (
     "现金流量来源ID" text PRIMARY KEY,
     "结果行ID" text NOT NULL,
     "分录ID" text,
     "核实ID" text,
     "归集金额" numeric(20,4) NOT NULL,
     "金额列" text NOT NULL,
     "项目映射ID" text,
     CHECK (num_nonnulls("分录ID", "核实ID") = 1)
   );


利润表来源明细表
""""""""""""""""


记录粒度：一个报表结果行纳入的一条分录或期初核定。

引用关系：结果行ID → finance.利润表；分录ID → finance.会计分录表；核实ID → finance.期初及结账核实表；项目映射ID → finance.报表项目映射表。

.. sql-source-line: 829

.. code-block:: sql

   CREATE TABLE finance."利润表来源明细表" (
     "利润来源ID" text PRIMARY KEY,
     "结果行ID" text NOT NULL,
     "分录ID" text,
     "核实ID" text,
     "归集金额" numeric(20,4) NOT NULL,
     "金额列" text NOT NULL,
     "项目映射ID" text,
     CHECK (num_nonnulls("分录ID", "核实ID") = 1)
   );


交付记录表
""""""""""


记录粒度：本部门发布的一版数据或文件交付。

引用关系：确认人ID → finance.人员档案表。

.. sql-source-line: 848

.. code-block:: sql

   CREATE TABLE finance."交付记录表" (
     "交付ID" text PRIMARY KEY,
     "交付名称" text NOT NULL,
     "交付版本" text NOT NULL,
     "期间开始" date,
     "期间结束" date,
     "数据截止时间" timestamptz NOT NULL,
     "交付时间" timestamptz NOT NULL,
     "文件路径" text,
     "待核事项" text,
     "确认人ID" text
   );


意见采纳表
""""""""""


记录粒度：本部门对一项分析建议的一次采纳决定。

引用关系：意见ID → analysis.意见与规划总表；负责人ID → finance.人员档案表。

.. sql-source-line: 869

.. code-block:: sql

   CREATE TABLE finance."意见采纳表" (
     "采纳记录ID" text PRIMARY KEY,
     "意见ID" text NOT NULL,
     "决定日期" date NOT NULL,
     "采纳结论" text NOT NULL,
     "目标" text,
     "负责人ID" text
   );


意见执行表
""""""""""


记录粒度：本部门对一次采纳决定的一次实际执行。

引用关系：采纳记录ID → finance.意见采纳表；负责人ID → finance.人员档案表。

.. sql-source-line: 886

.. code-block:: sql

   CREATE TABLE finance."意见执行表" (
     "执行记录ID" text PRIMARY KEY,
     "采纳记录ID" text NOT NULL,
     "执行时间" timestamptz NOT NULL,
     "执行内容" text NOT NULL,
     "实际结果" text,
     "证据路径" text,
     "负责人ID" text
   );


整改处理表
""""""""""


记录粒度：本部门对一项整改要求的一次实际处理。

引用关系：整改事项ID → legal.整改跟踪表；处理人ID → finance.人员档案表。

.. sql-source-line: 904

.. code-block:: sql

   CREATE TABLE finance."整改处理表" (
     "整改处理记录ID" text PRIMARY KEY,
     "整改事项ID" text NOT NULL,
     "处理时间" timestamptz NOT NULL,
     "处理内容" text NOT NULL,
     "结果" text,
     "证据路径" text,
     "处理人ID" text
   );


交付明细表
""""""""""


记录粒度：本部门一次交付中引用的一条本部门记录。

每行只选一个来源；一份交付可含任意多行，不复制来源记录字段。

引用关系：交付ID → finance.交付记录表；人员档案表引用 → finance.人员档案表；资金账户档案表引用 → finance.资金账户档案表；流水文件登记表引用 → finance.流水文件登记表；资金流水表引用 → finance.资金流水表；流水来源明细表引用 → finance.流水来源明细表；账户期间余额表引用 → finance.账户期间余额表；会计政策表引用 → finance.会计政策表；会计科目表引用 → finance.会计科目表；资金用途核定表引用 → finance.资金用途核定表；结算分摊表引用 → finance.结算分摊表；内部划转对应表引用 → finance.内部划转对应表；重复记录对应表引用 → finance.重复记录对应表；期初及结账核实表引用 → finance.期初及结账核实表；往来未结明细表引用 → finance.往来未结明细表；费用归属表引用 → finance.费用归属表；工时计价表引用 → finance.工时计价表；收入成本确认表引用 → finance.收入成本确认表；发票登记表引用 → finance.发票登记表；发票分摊表引用 → finance.发票分摊表；资产台账引用 → finance.资产台账；纳税申报记录表引用 → finance.纳税申报记录表；税款缴退明细表引用 → finance.税款缴退明细表；账户核对表引用 → finance.账户核对表；会计凭证表引用 → finance.会计凭证表；会计分录表引用 → finance.会计分录表；报表批次表引用 → finance.报表批次表；资产负债表引用 → finance.资产负债表；现金流量表引用 → finance.现金流量表；利润表引用 → finance.利润表；报表项目映射表引用 → finance.报表项目映射表；资产负债表来源明细表引用 → finance.资产负债表来源明细表；现金流量表来源明细表引用 → finance.现金流量表来源明细表；利润表来源明细表引用 → finance.利润表来源明细表；意见采纳表引用 → finance.意见采纳表；意见执行表引用 → finance.意见执行表；整改处理表引用 → finance.整改处理表。

.. sql-source-line: 924

.. code-block:: sql

   CREATE TABLE finance."交付明细表" (
     "交付明细ID" text PRIMARY KEY,
     "交付ID" text NOT NULL,
     "人员档案表引用" text,
     "资金账户档案表引用" text,
     "流水文件登记表引用" text,
     "资金流水表引用" text,
     "流水来源明细表引用" text,
     "账户期间余额表引用" text,
     "会计政策表引用" text,
     "会计科目表引用" text,
     "资金用途核定表引用" text,
     "结算分摊表引用" text,
     "内部划转对应表引用" text,
     "重复记录对应表引用" text,
     "期初及结账核实表引用" text,
     "往来未结明细表引用" text,
     "费用归属表引用" text,
     "工时计价表引用" text,
     "收入成本确认表引用" text,
     "发票登记表引用" text,
     "发票分摊表引用" text,
     "资产台账引用" text,
     "纳税申报记录表引用" text,
     "税款缴退明细表引用" text,
     "账户核对表引用" text,
     "会计凭证表引用" text,
     "会计分录表引用" text,
     "报表批次表引用" text,
     "资产负债表引用" text,
     "现金流量表引用" text,
     "利润表引用" text,
     "报表项目映射表引用" text,
     "资产负债表来源明细表引用" text,
     "现金流量表来源明细表引用" text,
     "利润表来源明细表引用" text,
     "意见采纳表引用" text,
     "意见执行表引用" text,
     "整改处理表引用" text,
     CHECK (num_nonnulls("人员档案表引用", "资金账户档案表引用", "流水文件登记表引用", "资金流水表引用", "流水来源明细表引用", "账户期间余额表引用", "会计政策表引用", "会计科目表引用", "资金用途核定表引用", "结算分摊表引用", "内部划转对应表引用", "重复记录对应表引用", "期初及结账核实表引用", "往来未结明细表引用", "费用归属表引用", "工时计价表引用", "收入成本确认表引用", "发票登记表引用", "发票分摊表引用", "资产台账引用", "纳税申报记录表引用", "税款缴退明细表引用", "账户核对表引用", "会计凭证表引用", "会计分录表引用", "报表批次表引用", "资产负债表引用", "现金流量表引用", "利润表引用", "报表项目映射表引用", "资产负债表来源明细表引用", "现金流量表来源明细表引用", "利润表来源明细表引用", "意见采纳表引用", "意见执行表引用", "整改处理表引用") = 1)
   );


法务
~~~~


法务需要持有的是：

公司主体档案表：主录ID为主体ID；字段及引用：公司名称、统一社会信用代码、注册地址、登记及税务资料路径、资料版本及有效状态，人工核验。
法规登记表：主录ID为法规ID；字段及引用：检索目录、法规名称、条文及原文URL、版本、生效失效日期及检索日期，自动检索候选，人工确认。
适用规则表：主录ID为规则ID；字段及引用：法规ID、适用条件及责任部门，人工确认。
法律文件登记表：主录ID为文件ID；字段及引用：文件类型、日期、有效期、文件路径及状态；业务合同仅引用销售或生产的合同ID。
合同审阅表：主录ID为审阅ID；字段及引用：合同ID、审阅事项、责任部门及审阅结论，人工确认。
履约提示表：主录ID为提示ID；字段及引用：合同ID、审阅ID、履约节点、责任部门及期限，人工确认，自动提醒。
合规自查表：主录ID为自查ID；字段及引用：规则ID、检查期间、主题、责任部门及责任人、适用性结论、检查日期及结论，人工确认。
证据对应表：主录ID为证据关联ID；字段及引用：自查ID、来源部门、业务对象ID及证据位置，自动收集引用，人工核验。
整改跟踪表：主录ID为整改事项ID；字段及引用：自查ID、规则ID、整改意见、责任人、期限、业务处理记录ID、复核结论、复核日期及关闭状态，人工核定，自动跟踪。

法务需要默认交出的是：

公司主体资料、适用法规与规则目录。
合同审阅表及履约提示表：分别沿用审阅ID、提示ID交付。
合规事项与整改跟踪表：按整改事项ID交付整改意见及复核结果。


SQL记录粒度与字段定义
^^^^^^^^^^^^^^^^^^^^^^^^


下列表中，ID主键标识本表主录；引用列的目标统一列在文末外键定义中。


公司主体档案表
""""""""""""""


记录粒度：一个公司法律主体。

.. sql-source-line: 997

.. code-block:: sql

   CREATE TABLE legal."公司主体档案表" (
     "主体ID" text PRIMARY KEY,
     "公司名称" text NOT NULL,
     "统一社会信用代码" text NOT NULL,
     "注册地址" text NOT NULL,
     "登记资料路径" text,
     "税务资料路径" text,
     "资料版本" text,
     "有效状态" text NOT NULL,
     UNIQUE ("统一社会信用代码")
   );


法规登记表
""""""""""


记录粒度：一部法规的一版原文。

.. sql-source-line: 1015

.. code-block:: sql

   CREATE TABLE legal."法规登记表" (
     "法规ID" text PRIMARY KEY,
     "法规名称" text NOT NULL,
     "检索目录" text,
     "条文" text NOT NULL,
     "原文URL" text NOT NULL,
     "版本" text NOT NULL,
     "生效日期" date,
     "失效日期" date,
     "检索日期" date NOT NULL,
     UNIQUE ("原文URL", "版本")
   );


适用规则表
""""""""""


记录粒度：一项法规条文对应的一项企业适用规则。

引用关系：法规ID → legal.法规登记表。

.. sql-source-line: 1036

.. code-block:: sql

   CREATE TABLE legal."适用规则表" (
     "规则ID" text PRIMARY KEY,
     "法规ID" text NOT NULL,
     "条文定位" text NOT NULL,
     "适用条件" text NOT NULL,
     "责任部门" text NOT NULL
   );


法律文件登记表
""""""""""""""


记录粒度：一份法务持有法律文件的一版文件记录。

销售、采购合同原文仍由其业务部门持有；本表只引用合同ID。 本版状态：草稿、有效、失效。

引用关系：销售合同ID → sales.销售合同表；采购合同ID → production.采购合同表。

.. sql-source-line: 1054

.. code-block:: sql

   CREATE TABLE legal."法律文件登记表" (
     "法律文件ID" text PRIMARY KEY,
     "文件类型" text NOT NULL,
     "日期" date,
     "有效期至" date,
     "文件路径" text NOT NULL,
     "状态" text NOT NULL,
     "销售合同ID" text,
     "采购合同ID" text,
     CHECK (num_nonnulls("销售合同ID", "采购合同ID") <= 1),
     CHECK ("状态" IN ('草稿', '有效', '失效'))
   );


合同审阅表
""""""""""


记录粒度：对一份业务合同的一次审阅。

引用关系：销售合同ID → sales.销售合同表；采购合同ID → production.采购合同表；确认人ID → finance.人员档案表。

.. sql-source-line: 1075

.. code-block:: sql

   CREATE TABLE legal."合同审阅表" (
     "审阅ID" text PRIMARY KEY,
     "销售合同ID" text,
     "采购合同ID" text,
     "审阅日期" date NOT NULL,
     "审阅事项" text NOT NULL,
     "责任部门" text NOT NULL,
     "审阅结论" text,
     "确认人ID" text,
     CHECK (num_nonnulls("销售合同ID", "采购合同ID") = 1)
   );


履约提示表
""""""""""


记录粒度：一次合同审阅中的一个履约节点。

合同沿审阅记录查询，避免重复保存不同合同引用。 本版状态：待履约、已履约、已取消。

引用关系：审阅ID → legal.合同审阅表。

.. sql-source-line: 1097

.. code-block:: sql

   CREATE TABLE legal."履约提示表" (
     "提示ID" text PRIMARY KEY,
     "审阅ID" text NOT NULL,
     "履约节点" text NOT NULL,
     "责任部门" text NOT NULL,
     "期限" date NOT NULL,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('待履约', '已履约', '已取消'))
   );


合规自查表
""""""""""


记录粒度：一项规则在一个检查范围中的一次自查。

 本版状态：待检查、检查中、已确认。

引用关系：规则ID → legal.适用规则表；责任人ID → finance.人员档案表。

.. sql-source-line: 1117

.. code-block:: sql

   CREATE TABLE legal."合规自查表" (
     "自查ID" text PRIMARY KEY,
     "规则ID" text NOT NULL,
     "期间开始" date NOT NULL,
     "期间结束" date NOT NULL,
     "主题" text NOT NULL,
     "责任部门" text NOT NULL,
     "责任人ID" text,
     "适用性结论" text,
     "检查日期" date,
     "检查结论" text,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('待检查', '检查中', '已确认'))
   );


证据对应表
""""""""""


记录粒度：一次自查中的一份来源证据对应。

一般文件由证据位置表达；已建模业务证据使用明确外键。

引用关系：自查ID → legal.合规自查表；提供人ID → finance.人员档案表；销售订单行ID → sales.销售订单行表；采购订单行ID → production.采购订单行表；工单号 → production.生产工单表；项目ID → rd.项目登记表；售后事件ID → sales.售后事件表；费用ID → finance.费用归属表。

.. sql-source-line: 1142

.. code-block:: sql

   CREATE TABLE legal."证据对应表" (
     "证据关联ID" text PRIMARY KEY,
     "自查ID" text NOT NULL,
     "证据位置" text NOT NULL,
     "提供时间" timestamptz,
     "提供人ID" text,
     "销售订单行ID" text,
     "采购订单行ID" text,
     "工单号" text,
     "项目ID" text,
     "售后事件ID" text,
     "费用ID" text,
     CHECK (num_nonnulls("销售订单行ID", "采购订单行ID", "工单号", "项目ID", "售后事件ID", "费用ID") <= 1)
   );


整改跟踪表
""""""""""


记录粒度：一次自查产生的一项整改要求。

规则沿自查查询；实际处理记录由责任部门持有并反向引用本事项。 本版关闭状态：未关闭、已关闭。

引用关系：自查ID → legal.合规自查表；责任人ID → finance.人员档案表；复核人ID → finance.人员档案表。

.. sql-source-line: 1167

.. code-block:: sql

   CREATE TABLE legal."整改跟踪表" (
     "整改事项ID" text PRIMARY KEY,
     "自查ID" text NOT NULL,
     "整改意见" text NOT NULL,
     "责任部门" text NOT NULL,
     "责任人ID" text,
     "期限" date,
     "复核结论" text,
     "复核人ID" text,
     "复核日期" date,
     "关闭状态" text NOT NULL,
     CHECK ("关闭状态" IN ('未关闭', '已关闭'))
   );


交付记录表
""""""""""


记录粒度：本部门发布的一版数据或文件交付。

引用关系：确认人ID → finance.人员档案表。

.. sql-source-line: 1189

.. code-block:: sql

   CREATE TABLE legal."交付记录表" (
     "交付ID" text PRIMARY KEY,
     "交付名称" text NOT NULL,
     "交付版本" text NOT NULL,
     "期间开始" date,
     "期间结束" date,
     "数据截止时间" timestamptz NOT NULL,
     "交付时间" timestamptz NOT NULL,
     "文件路径" text,
     "待核事项" text,
     "确认人ID" text
   );


意见采纳表
""""""""""


记录粒度：本部门对一项分析建议的一次采纳决定。

引用关系：意见ID → analysis.意见与规划总表；负责人ID → finance.人员档案表。

.. sql-source-line: 1210

.. code-block:: sql

   CREATE TABLE legal."意见采纳表" (
     "采纳记录ID" text PRIMARY KEY,
     "意见ID" text NOT NULL,
     "决定日期" date NOT NULL,
     "采纳结论" text NOT NULL,
     "目标" text,
     "负责人ID" text
   );


意见执行表
""""""""""


记录粒度：本部门对一次采纳决定的一次实际执行。

引用关系：采纳记录ID → legal.意见采纳表；负责人ID → finance.人员档案表。

.. sql-source-line: 1227

.. code-block:: sql

   CREATE TABLE legal."意见执行表" (
     "执行记录ID" text PRIMARY KEY,
     "采纳记录ID" text NOT NULL,
     "执行时间" timestamptz NOT NULL,
     "执行内容" text NOT NULL,
     "实际结果" text,
     "证据路径" text,
     "负责人ID" text
   );


整改处理表
""""""""""


记录粒度：本部门对一项整改要求的一次实际处理。

引用关系：整改事项ID → legal.整改跟踪表；处理人ID → finance.人员档案表。

.. sql-source-line: 1245

.. code-block:: sql

   CREATE TABLE legal."整改处理表" (
     "整改处理记录ID" text PRIMARY KEY,
     "整改事项ID" text NOT NULL,
     "处理时间" timestamptz NOT NULL,
     "处理内容" text NOT NULL,
     "结果" text,
     "证据路径" text,
     "处理人ID" text
   );


交付明细表
""""""""""


记录粒度：本部门一次交付中引用的一条本部门记录。

每行只选一个来源；一份交付可含任意多行，不复制来源记录字段。

引用关系：交付ID → legal.交付记录表；公司主体档案表引用 → legal.公司主体档案表；法规登记表引用 → legal.法规登记表；适用规则表引用 → legal.适用规则表；法律文件登记表引用 → legal.法律文件登记表；合同审阅表引用 → legal.合同审阅表；履约提示表引用 → legal.履约提示表；合规自查表引用 → legal.合规自查表；证据对应表引用 → legal.证据对应表；整改跟踪表引用 → legal.整改跟踪表；意见采纳表引用 → legal.意见采纳表；意见执行表引用 → legal.意见执行表；整改处理表引用 → legal.整改处理表。

.. sql-source-line: 1265

.. code-block:: sql

   CREATE TABLE legal."交付明细表" (
     "交付明细ID" text PRIMARY KEY,
     "交付ID" text NOT NULL,
     "公司主体档案表引用" text,
     "法规登记表引用" text,
     "适用规则表引用" text,
     "法律文件登记表引用" text,
     "合同审阅表引用" text,
     "履约提示表引用" text,
     "合规自查表引用" text,
     "证据对应表引用" text,
     "整改跟踪表引用" text,
     "意见采纳表引用" text,
     "意见执行表引用" text,
     "整改处理表引用" text,
     CHECK (num_nonnulls("公司主体档案表引用", "法规登记表引用", "适用规则表引用", "法律文件登记表引用", "合同审阅表引用", "履约提示表引用", "合规自查表引用", "证据对应表引用", "整改跟踪表引用", "意见采纳表引用", "意见执行表引用", "整改处理表引用") = 1)
   );


生产
~~~~


生产需要持有的是：

供应商档案表：主录ID为供应商ID；字段：名称、联系方式、统一社会信用代码、户名、账户ID、开户行，人工确认。账户ID是供应商收款账户标识或账号，按文本保留前导零，不引用本公司的资金账户档案表。
采购合同表：主录ID为采购合同ID；字段及引用：供应商ID、签署日期、合同文件路径及状态，人工确认。
采购订单表：主录ID为采购单ID；字段及引用：采购合同ID、供应商ID及状态，人工确认。
采购订单行表：主录ID为采购订单行ID；字段及引用：采购单ID、MID或PID、版本、数量、单位、单价及预计交期，人工确认。
保管方档案表：主录ID为保管方ID；字段及引用：名称及所属主体ID，人工确认。
仓库档案表：主录ID为仓库ID；字段及引用：地点、库位、保管方ID、所属主体ID及启用状态，人工确认。
库存基准核定表：主录ID为基准ID；字段及引用：基准日期、MID或PID、仓库ID、库位、批次、版本、单位、数量、所有权主体ID、盘点依据及确认人，人工确认。
到货记录表：主录ID为到货ID；字段及引用：采购订单行ID、实际到货时间、到货数量及凭证，人工确认。
验收记录表：主录ID为验收ID；字段及引用：到货ID、验收时间、验收数量、检验ID及凭证，人工确认；实际入库引用库存事件ID。
库存变动表：主录ID为库存事件ID；字段及引用：MID或PID、数量变化、单位、时间、仓库ID、库位、批次、版本、所有权主体ID及业务来源ID，人工确认，自动汇总。
生产工单表：主录ID为工单号；字段及引用：草稿登记ID、研发发布批次ID、计划数量、单位、计划日期、负责人及下达依据，人工确认。
生产领退料表：主录ID为领退料事件ID；字段及引用：工单号、MID、批次、版本、领退料类型、实际数量、单位、日期、库存事件ID及凭证，人工确认。
生产工时表：主录ID为工时ID；字段及引用：工单号、工序、人员或设备ID、开始结束时间、有效工时、产量、异常及凭证，人工确认。
完工记录表：主录ID为完工事件ID；字段及引用：工单号、PID、版本、批次、日期、合格及不良数量、单位、库存事件ID及检验ID，人工确认。
报废记录表：主录ID为报废事件ID；字段及引用：工单号、完工事件ID、PID或MID、版本、批次、日期、报废数量、单位、库存事件ID及检验ID，人工确认。
质量检验表：主录ID为检验ID；字段及引用：日期、PID或MID、版本、批次、工单号或订单行ID、检验数量、不良数量、现象、测试条件、凭证、售后事件ID及研发事项ID，人工确认。
委外物料流转表：主录ID为物料事件ID；字段及引用：日期、采购订单行ID、事件类型、MID、版本、批次、来源及去向保管方ID、数量、单位、工单号、库存事件ID及凭证，人工确认。
采购归属对应表：主录ID为采购归属ID；字段及引用：采购订单行ID、财务分摊ID、归属数量、单位及依据，生产确认采购归属。
发货记录表：主录ID为发货事件ID；字段及引用：销售订单行ID、PID、版本、数量、日期、物流、检验ID及库存事件ID，人工确认实际发货，收货信息引用销售订单。

生产需要默认交出的是：

验收交付表：沿用验收ID，交付到货与验收结果。
库存收发明细表：沿用库存事件ID，交付实际收发记录。
库存余额与差异表：库存结存ID、基准ID、截止日期、MID或PID、仓库ID、批次、版本、所有权主体ID、单位、期初、收入、发出、期末及盘点差异，自动计算，人工确认差异。
生产执行交付表：沿用工单号，引用领退料、工时、完工、报废、检验及异常记录ID，自动汇总。
发货履约与质量反馈表：沿用发货事件ID，引用销售订单行ID、检验ID及售后事件ID，自动汇总。


SQL记录粒度与字段定义
^^^^^^^^^^^^^^^^^^^^^^^^


下列表中，ID主键标识本表主录；引用列的目标统一列在文末外键定义中。


设备档案表
""""""""""


记录粒度：一台可单独登记工时的设备。

 本版启用状态：启用、停用。

.. sql-source-line: 1328

.. code-block:: sql

   CREATE TABLE production."设备档案表" (
     "设备ID" text PRIMARY KEY,
     "设备名称" text NOT NULL,
     "规格" text,
     "所在地点" text,
     "启用状态" text NOT NULL,
     CHECK ("启用状态" IN ('启用', '停用'))
   );


供应商档案表
""""""""""""


记录粒度：一个业务供应商。

.. sql-source-line: 1343

.. code-block:: sql

   CREATE TABLE production."供应商档案表" (
     "供应商ID" text PRIMARY KEY,
     "名称" text NOT NULL,
     "联系方式" text,
     "统一社会信用代码" text,
     "户名" text,
     "账户ID" text,
     "开户行" text
   );


采购合同表
""""""""""


记录粒度：一份采购合同。

 本版状态：草稿、已签署、已终止。

引用关系：供应商ID → production.供应商档案表。

.. sql-source-line: 1360

.. code-block:: sql

   CREATE TABLE production."采购合同表" (
     "采购合同ID" text PRIMARY KEY,
     "供应商ID" text NOT NULL,
     "签署日期" date,
     "合同文件路径" text NOT NULL,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('草稿', '已签署', '已终止'))
   );


采购订单表
""""""""""


记录粒度：一张采购订单。

 本版状态：草稿、已下单、部分到货、已完成、已取消。

引用关系：采购合同ID → production.采购合同表；供应商ID → production.供应商档案表。

.. sql-source-line: 1379

.. code-block:: sql

   CREATE TABLE production."采购订单表" (
     "采购单ID" text PRIMARY KEY,
     "采购合同ID" text,
     "供应商ID" text NOT NULL,
     "创建日期" date NOT NULL,
     "状态" text NOT NULL,
     "币种" char(3) NOT NULL,
     CHECK ("状态" IN ('草稿', '已下单', '部分到货', '已完成', '已取消'))
   );


采购订单行表
""""""""""""


记录粒度：一张采购单中一个物品版本的一行约定。

引用关系：采购单ID → production.采购订单表；单位ID → rd.计量单位表；产品版本ID → rd.产品版本表；物料版本ID → rd.物料版本表。

.. sql-source-line: 1397

.. code-block:: sql

   CREATE TABLE production."采购订单行表" (
     "采购订单行ID" text PRIMARY KEY,
     "采购单ID" text NOT NULL,
     "行号" integer NOT NULL,
     "数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "单价" numeric(20,4) NOT NULL,
     "预计交期" date,
     "取消数量" numeric(20,6) NOT NULL,
     "产品版本ID" text,
     "物料版本ID" text,
     UNIQUE ("采购单ID", "行号"),
     CHECK (num_nonnulls("产品版本ID", "物料版本ID") = 1),
     CHECK ("数量" > 0),
     CHECK ("取消数量" >= 0 AND "取消数量" <= "数量")
   );


保管方档案表
""""""""""""


记录粒度：一个实物保管方。

引用关系：主体ID → legal.公司主体档案表。

.. sql-source-line: 1422

.. code-block:: sql

   CREATE TABLE production."保管方档案表" (
     "保管方ID" text PRIMARY KEY,
     "名称" text NOT NULL,
     "主体ID" text
   );


仓库档案表
""""""""""


记录粒度：一个仓库。

 本版启用状态：启用、停用。

引用关系：保管方ID → production.保管方档案表；主体ID → legal.公司主体档案表。

.. sql-source-line: 1438

.. code-block:: sql

   CREATE TABLE production."仓库档案表" (
     "仓库ID" text PRIMARY KEY,
     "地点" text NOT NULL,
     "保管方ID" text NOT NULL,
     "主体ID" text NOT NULL,
     "启用状态" text NOT NULL,
     CHECK ("启用状态" IN ('启用', '停用'))
   );


库位档案表
""""""""""


记录粒度：一个仓库中的一个库位。

为原仓库中的多个库位补充明细，每个库存事件引用一个库位。

引用关系：仓库ID → production.仓库档案表。

.. sql-source-line: 1457

.. code-block:: sql

   CREATE TABLE production."库位档案表" (
     "库位ID" text PRIMARY KEY,
     "仓库ID" text NOT NULL,
     "库位代码" text NOT NULL,
     UNIQUE ("仓库ID", "库位代码")
   );


库存基准核定表
""""""""""""""


记录粒度：某物品版本在库位、批次和所有权维度的一次库存起点核定。

相同物品、库位、批次和所有权下，查询应明确选择哪个基准日期及核定版本。

引用关系：库位ID → production.库位档案表；单位ID → rd.计量单位表；所有权主体ID → legal.公司主体档案表；确认人ID → finance.人员档案表；产品版本ID → rd.产品版本表；物料版本ID → rd.物料版本表。

.. sql-source-line: 1474

.. code-block:: sql

   CREATE TABLE production."库存基准核定表" (
     "基准ID" text PRIMARY KEY,
     "基准日期" date NOT NULL,
     "库位ID" text NOT NULL,
     "批次" text NOT NULL,
     "单位ID" text NOT NULL,
     "数量" numeric(20,6) NOT NULL,
     "所有权主体ID" text NOT NULL,
     "盘点依据" text NOT NULL,
     "确认人ID" text,
     "核定版本" integer NOT NULL,
     "产品版本ID" text,
     "物料版本ID" text,
     CHECK (num_nonnulls("产品版本ID", "物料版本ID") = 1)
   );


到货记录表
""""""""""


记录粒度：采购订单行的一次实际到货。

引用关系：采购订单行ID → production.采购订单行表；单位ID → rd.计量单位表。

.. sql-source-line: 1498

.. code-block:: sql

   CREATE TABLE production."到货记录表" (
     "到货ID" text PRIMARY KEY,
     "采购订单行ID" text NOT NULL,
     "到货时间" timestamptz NOT NULL,
     "数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "凭证路径" text,
     CHECK ("数量" > 0)
   );


验收记录表
""""""""""


记录粒度：对一次到货中一部分数量的一次验收。

引用关系：到货ID → production.到货记录表；单位ID → rd.计量单位表；检验ID → production.质量检验表。

.. sql-source-line: 1516

.. code-block:: sql

   CREATE TABLE production."验收记录表" (
     "验收ID" text PRIMARY KEY,
     "到货ID" text NOT NULL,
     "验收时间" timestamptz NOT NULL,
     "验收数量" numeric(20,6) NOT NULL,
     "合格数量" numeric(20,6) NOT NULL,
     "不合格数量" numeric(20,6) NOT NULL,
     "待检数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "检验ID" text,
     "凭证路径" text,
     CHECK ("验收数量" = "合格数量" + "不合格数量" + "待检数量"),
     CHECK ("合格数量" >= 0 AND "不合格数量" >= 0 AND "待检数量" >= 0)
   );


库存变动表
""""""""""


记录粒度：一个物品版本在一个库存维度的一次实物数量增减。

一个来源事件可产生多条库存变动；调拨分别记来源库位负数与去向库位正数。

引用关系：单位ID → rd.计量单位表；库位ID → production.库位档案表；所有权主体ID → legal.公司主体档案表；验收ID → production.验收记录表；领退料事件ID → production.生产领退料表；完工事件ID → production.完工记录表；报废事件ID → production.报废记录表；发货事件ID → production.发货记录表；物料事件ID → production.委外物料流转表；售后事件ID → sales.售后事件表；产品版本ID → rd.产品版本表；物料版本ID → rd.物料版本表。

.. sql-source-line: 1541

.. code-block:: sql

   CREATE TABLE production."库存变动表" (
     "库存事件ID" text PRIMARY KEY,
     "发生时间" timestamptz NOT NULL,
     "数量变化" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "库位ID" text NOT NULL,
     "批次" text NOT NULL,
     "所有权主体ID" text NOT NULL,
     "业务类型" text NOT NULL,
     "凭证路径" text,
     "验收ID" text,
     "领退料事件ID" text,
     "完工事件ID" text,
     "报废事件ID" text,
     "发货事件ID" text,
     "物料事件ID" text,
     "售后事件ID" text,
     "产品版本ID" text,
     "物料版本ID" text,
     CHECK (num_nonnulls("产品版本ID", "物料版本ID") = 1),
     CHECK (num_nonnulls("验收ID", "领退料事件ID", "完工事件ID", "报废事件ID", "发货事件ID", "物料事件ID", "售后事件ID") <= 1),
     CHECK ("数量变化" <> 0)
   );


工单草稿表
""""""""""


记录粒度：一次尚未正式下达的生产计划。

 本版状态：待下达、已下达、已取消。

引用关系：负责人ID → finance.人员档案表。

.. sql-source-line: 1575

.. code-block:: sql

   CREATE TABLE production."工单草稿表" (
     "草稿登记ID" text PRIMARY KEY,
     "计划说明" text NOT NULL,
     "登记时间" timestamptz NOT NULL,
     "负责人ID" text,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('待下达', '已下达', '已取消'))
   );


生产工单表
""""""""""


记录粒度：一张正式下达的生产工单。

 本版状态：已下达、执行中、已完工、已关闭、已取消。

引用关系：草稿登记ID → production.工单草稿表；发布批次ID → rd.发布批次表；单位ID → rd.计量单位表；负责人ID → finance.人员档案表。

.. sql-source-line: 1594

.. code-block:: sql

   CREATE TABLE production."生产工单表" (
     "工单号" text PRIMARY KEY,
     "草稿登记ID" text,
     "发布批次ID" text NOT NULL,
     "计划数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "计划开始日期" date NOT NULL,
     "计划结束日期" date,
     "负责人ID" text,
     "下达依据" text NOT NULL,
     "状态" text NOT NULL,
     "取消数量" numeric(20,6) NOT NULL,
     CHECK ("计划数量" > 0),
     CHECK ("取消数量" >= 0 AND "取消数量" <= "计划数量"),
     CHECK ("状态" IN ('已下达', '执行中', '已完工', '已关闭', '已取消'))
   );


工单订单对应表
""""""""""""""


记录粒度：一张工单承担一个销售订单行的一部分数量。

补充工单与订单行的多对多关系。

引用关系：工单号 → production.生产工单表；销售订单行ID → sales.销售订单行表；单位ID → rd.计量单位表；订单组合明细ID → sales.订单组合明细表。

.. sql-source-line: 1621

.. code-block:: sql

   CREATE TABLE production."工单订单对应表" (
     "工单订单关联ID" text PRIMARY KEY,
     "工单号" text NOT NULL,
     "销售订单行ID" text NOT NULL,
     "对应数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "订单组合明细ID" text,
     UNIQUE ("工单号", "销售订单行ID")
   );


生产领退料表
""""""""""""


记录粒度：一张工单的一种物料版本的一次领料或退料。

引用关系：工单号 → production.生产工单表；物料版本ID → rd.物料版本表；单位ID → rd.计量单位表。

.. sql-source-line: 1639

.. code-block:: sql

   CREATE TABLE production."生产领退料表" (
     "领退料事件ID" text PRIMARY KEY,
     "工单号" text NOT NULL,
     "物料版本ID" text NOT NULL,
     "批次" text NOT NULL,
     "类型" text NOT NULL,
     "数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "日期" date NOT NULL,
     "凭证路径" text,
     CHECK ("类型" IN ('领料','退料')),
     CHECK ("数量" > 0)
   );


生产工时表
""""""""""


记录粒度：某工序的一名人员或一台设备的一段实际投入。

人工工时和设备工时分别记行，不把两个资源的投入合成一个ID。

引用关系：工单号 → production.生产工单表；人员ID → finance.人员档案表；设备ID → production.设备档案表；产量单位ID → rd.计量单位表。

.. sql-source-line: 1663

.. code-block:: sql

   CREATE TABLE production."生产工时表" (
     "工时ID" text PRIMARY KEY,
     "工单号" text NOT NULL,
     "工序" text NOT NULL,
     "人员ID" text,
     "设备ID" text,
     "开始时间" timestamptz NOT NULL,
     "结束时间" timestamptz NOT NULL,
     "有效工时" numeric(12,4) NOT NULL,
     "产量" numeric(20,6),
     "产量单位ID" text,
     "异常" text,
     "凭证路径" text,
     CHECK (num_nonnulls("人员ID", "设备ID") = 1),
     CHECK ("结束时间" >= "开始时间"),
     CHECK ("有效工时" >= 0)
   );


完工记录表
""""""""""


记录粒度：一张工单一个批次的一次完工申报。

产品版本沿工单及发布批次查询；报废记录独立，不再计入新增完工产量。

引用关系：工单号 → production.生产工单表；单位ID → rd.计量单位表；检验ID → production.质量检验表。

.. sql-source-line: 1691

.. code-block:: sql

   CREATE TABLE production."完工记录表" (
     "完工事件ID" text PRIMARY KEY,
     "工单号" text NOT NULL,
     "批次" text NOT NULL,
     "日期" date NOT NULL,
     "合格数量" numeric(20,6) NOT NULL,
     "不良数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "检验ID" text,
     CHECK ("合格数量" >= 0 AND "不良数量" >= 0)
   );


报废记录表
""""""""""


记录粒度：一个工单中一个物品版本的一次报废处置。

引用关系：工单号 → production.生产工单表；完工事件ID → production.完工记录表；单位ID → rd.计量单位表；检验ID → production.质量检验表；产品版本ID → rd.产品版本表；物料版本ID → rd.物料版本表。

.. sql-source-line: 1711

.. code-block:: sql

   CREATE TABLE production."报废记录表" (
     "报废事件ID" text PRIMARY KEY,
     "工单号" text NOT NULL,
     "完工事件ID" text,
     "日期" date NOT NULL,
     "批次" text NOT NULL,
     "数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "检验ID" text,
     "产品版本ID" text,
     "物料版本ID" text,
     CHECK (num_nonnulls("产品版本ID", "物料版本ID") = 1),
     CHECK ("数量" > 0)
   );


质量检验表
""""""""""


记录粒度：一个物品版本一个批次在一次测试条件下的一次检验。

研发事项反向引用本检验；登记检验时不要求已有研发处理结果。

引用关系：工单号 → production.生产工单表；销售订单行ID → sales.销售订单行表；单位ID → rd.计量单位表；售后事件ID → sales.售后事件表；产品版本ID → rd.产品版本表；物料版本ID → rd.物料版本表。

.. sql-source-line: 1736

.. code-block:: sql

   CREATE TABLE production."质量检验表" (
     "检验ID" text PRIMARY KEY,
     "日期" date NOT NULL,
     "批次" text NOT NULL,
     "工单号" text,
     "销售订单行ID" text,
     "检验数量" numeric(20,6) NOT NULL,
     "不良数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "现象" text,
     "测试条件" text NOT NULL,
     "凭证路径" text,
     "售后事件ID" text,
     "产品版本ID" text,
     "物料版本ID" text,
     CHECK (num_nonnulls("产品版本ID", "物料版本ID") = 1),
     CHECK ("检验数量" >= 0 AND "不良数量" >= 0 AND "不良数量" <= "检验数量")
   );


委外物料流转表
""""""""""""""


记录粒度：一种物料版本一次委外实物流转。

引用关系：采购订单行ID → production.采购订单行表；物料版本ID → rd.物料版本表；来源保管方ID → production.保管方档案表；去向保管方ID → production.保管方档案表；单位ID → rd.计量单位表；工单号 → production.生产工单表。

.. sql-source-line: 1763

.. code-block:: sql

   CREATE TABLE production."委外物料流转表" (
     "物料事件ID" text PRIMARY KEY,
     "日期" date NOT NULL,
     "采购订单行ID" text,
     "事件类型" text NOT NULL,
     "物料版本ID" text NOT NULL,
     "批次" text NOT NULL,
     "来源保管方ID" text NOT NULL,
     "去向保管方ID" text NOT NULL,
     "数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "工单号" text,
     "凭证路径" text,
     CHECK ("数量" > 0)
   );


采购归属对应表
""""""""""""""


记录粒度：一条财务分摊对应一条采购行的一次实物归属说明。

引用关系：采购订单行ID → production.采购订单行表；分摊ID → finance.结算分摊表；单位ID → rd.计量单位表。

.. sql-source-line: 1787

.. code-block:: sql

   CREATE TABLE production."采购归属对应表" (
     "采购归属ID" text PRIMARY KEY,
     "采购订单行ID" text NOT NULL,
     "分摊ID" text NOT NULL,
     "归属数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "依据" text NOT NULL,
     UNIQUE ("采购订单行ID", "分摊ID")
   );


发货记录表
""""""""""


记录粒度：一个销售订单行的一次实际发货明细。

同一物流单发多种商品时，每个订单行分别建立事件。产品和收货信息通过订单行查询。

引用关系：销售订单行ID → sales.销售订单行表；单位ID → rd.计量单位表；检验ID → production.质量检验表；订单组合明细ID → sales.订单组合明细表。

.. sql-source-line: 1807

.. code-block:: sql

   CREATE TABLE production."发货记录表" (
     "发货事件ID" text PRIMARY KEY,
     "销售订单行ID" text NOT NULL,
     "数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "发货时间" timestamptz NOT NULL,
     "物流单号" text,
     "物流说明" text,
     "检验ID" text,
     "订单组合明细ID" text,
     CHECK ("数量" > 0)
   );


库存盘点表
""""""""""


记录粒度：某库存维度在一个日期的一次实盘确认。

补充原库存差异输出所需的实际盘点事实。

引用关系：库位ID → production.库位档案表；所有权主体ID → legal.公司主体档案表；单位ID → rd.计量单位表；确认人ID → finance.人员档案表；产品版本ID → rd.产品版本表；物料版本ID → rd.物料版本表。

.. sql-source-line: 1830

.. code-block:: sql

   CREATE TABLE production."库存盘点表" (
     "盘点ID" text PRIMARY KEY,
     "盘点日期" date NOT NULL,
     "库位ID" text NOT NULL,
     "批次" text NOT NULL,
     "所有权主体ID" text NOT NULL,
     "单位ID" text NOT NULL,
     "实盘数量" numeric(20,6) NOT NULL,
     "确认人ID" text,
     "依据" text NOT NULL,
     "产品版本ID" text,
     "物料版本ID" text,
     CHECK (num_nonnulls("产品版本ID", "物料版本ID") = 1)
   );


库存余额与差异表
""""""""""""""""


记录粒度：某库存基准在一个截止时点的一版结存结果。

核定和计算结果快照；未知的基准、换算或待核事件使结果保留NULL，不默认零。

引用关系：基准ID → production.库存基准核定表；盘点ID → production.库存盘点表。

.. sql-source-line: 1855

.. code-block:: sql

   CREATE TABLE production."库存余额与差异表" (
     "库存结存ID" text PRIMARY KEY,
     "基准ID" text NOT NULL,
     "截止时间" timestamptz NOT NULL,
     "结果版本" integer NOT NULL,
     "期初数量" numeric(20,6),
     "收入数量" numeric(20,6),
     "发出数量" numeric(20,6),
     "期末数量" numeric(20,6),
     "盘点ID" text,
     "盘点差异" numeric(20,6),
     "计算说明" text,
     "生成时间" timestamptz NOT NULL,
     UNIQUE ("基准ID", "截止时间", "结果版本")
   );


库存结存来源明细表
""""""""""""""""""


记录粒度：一条库存结存结果纳入的一条库存事件。

引用关系：库存结存ID → production.库存余额与差异表；库存事件ID → production.库存变动表；换算ID → rd.单位换算表。

.. sql-source-line: 1879

.. code-block:: sql

   CREATE TABLE production."库存结存来源明细表" (
     "结存来源ID" text PRIMARY KEY,
     "库存结存ID" text NOT NULL,
     "库存事件ID" text NOT NULL,
     "统一单位数量" numeric(20,6) NOT NULL,
     "换算ID" text,
     UNIQUE ("库存结存ID", "库存事件ID")
   );


交付记录表
""""""""""


记录粒度：本部门发布的一版数据或文件交付。

引用关系：确认人ID → finance.人员档案表。

.. sql-source-line: 1896

.. code-block:: sql

   CREATE TABLE production."交付记录表" (
     "交付ID" text PRIMARY KEY,
     "交付名称" text NOT NULL,
     "交付版本" text NOT NULL,
     "期间开始" date,
     "期间结束" date,
     "数据截止时间" timestamptz NOT NULL,
     "交付时间" timestamptz NOT NULL,
     "文件路径" text,
     "待核事项" text,
     "确认人ID" text
   );


意见采纳表
""""""""""


记录粒度：本部门对一项分析建议的一次采纳决定。

引用关系：意见ID → analysis.意见与规划总表；负责人ID → finance.人员档案表。

.. sql-source-line: 1917

.. code-block:: sql

   CREATE TABLE production."意见采纳表" (
     "采纳记录ID" text PRIMARY KEY,
     "意见ID" text NOT NULL,
     "决定日期" date NOT NULL,
     "采纳结论" text NOT NULL,
     "目标" text,
     "负责人ID" text
   );


意见执行表
""""""""""


记录粒度：本部门对一次采纳决定的一次实际执行。

引用关系：采纳记录ID → production.意见采纳表；负责人ID → finance.人员档案表。

.. sql-source-line: 1934

.. code-block:: sql

   CREATE TABLE production."意见执行表" (
     "执行记录ID" text PRIMARY KEY,
     "采纳记录ID" text NOT NULL,
     "执行时间" timestamptz NOT NULL,
     "执行内容" text NOT NULL,
     "实际结果" text,
     "证据路径" text,
     "负责人ID" text
   );


整改处理表
""""""""""


记录粒度：本部门对一项整改要求的一次实际处理。

引用关系：整改事项ID → legal.整改跟踪表；处理人ID → finance.人员档案表。

.. sql-source-line: 1952

.. code-block:: sql

   CREATE TABLE production."整改处理表" (
     "整改处理记录ID" text PRIMARY KEY,
     "整改事项ID" text NOT NULL,
     "处理时间" timestamptz NOT NULL,
     "处理内容" text NOT NULL,
     "结果" text,
     "证据路径" text,
     "处理人ID" text
   );


交付明细表
""""""""""


记录粒度：本部门一次交付中引用的一条本部门记录。

每行只选一个来源；一份交付可含任意多行，不复制来源记录字段。

引用关系：交付ID → production.交付记录表；设备档案表引用 → production.设备档案表；供应商档案表引用 → production.供应商档案表；采购合同表引用 → production.采购合同表；采购订单表引用 → production.采购订单表；采购订单行表引用 → production.采购订单行表；保管方档案表引用 → production.保管方档案表；仓库档案表引用 → production.仓库档案表；库位档案表引用 → production.库位档案表；库存基准核定表引用 → production.库存基准核定表；到货记录表引用 → production.到货记录表；验收记录表引用 → production.验收记录表；库存变动表引用 → production.库存变动表；工单草稿表引用 → production.工单草稿表；生产工单表引用 → production.生产工单表；工单订单对应表引用 → production.工单订单对应表；生产领退料表引用 → production.生产领退料表；生产工时表引用 → production.生产工时表；完工记录表引用 → production.完工记录表；报废记录表引用 → production.报废记录表；质量检验表引用 → production.质量检验表；委外物料流转表引用 → production.委外物料流转表；采购归属对应表引用 → production.采购归属对应表；发货记录表引用 → production.发货记录表；库存盘点表引用 → production.库存盘点表；库存余额与差异表引用 → production.库存余额与差异表；库存结存来源明细表引用 → production.库存结存来源明细表；意见采纳表引用 → production.意见采纳表；意见执行表引用 → production.意见执行表；整改处理表引用 → production.整改处理表。

.. sql-source-line: 1972

.. code-block:: sql

   CREATE TABLE production."交付明细表" (
     "交付明细ID" text PRIMARY KEY,
     "交付ID" text NOT NULL,
     "设备档案表引用" text,
     "供应商档案表引用" text,
     "采购合同表引用" text,
     "采购订单表引用" text,
     "采购订单行表引用" text,
     "保管方档案表引用" text,
     "仓库档案表引用" text,
     "库位档案表引用" text,
     "库存基准核定表引用" text,
     "到货记录表引用" text,
     "验收记录表引用" text,
     "库存变动表引用" text,
     "工单草稿表引用" text,
     "生产工单表引用" text,
     "工单订单对应表引用" text,
     "生产领退料表引用" text,
     "生产工时表引用" text,
     "完工记录表引用" text,
     "报废记录表引用" text,
     "质量检验表引用" text,
     "委外物料流转表引用" text,
     "采购归属对应表引用" text,
     "发货记录表引用" text,
     "库存盘点表引用" text,
     "库存余额与差异表引用" text,
     "库存结存来源明细表引用" text,
     "意见采纳表引用" text,
     "意见执行表引用" text,
     "整改处理表引用" text,
     CHECK (num_nonnulls("设备档案表引用", "供应商档案表引用", "采购合同表引用", "采购订单表引用", "采购订单行表引用", "保管方档案表引用", "仓库档案表引用", "库位档案表引用", "库存基准核定表引用", "到货记录表引用", "验收记录表引用", "库存变动表引用", "工单草稿表引用", "生产工单表引用", "工单订单对应表引用", "生产领退料表引用", "生产工时表引用", "完工记录表引用", "报废记录表引用", "质量检验表引用", "委外物料流转表引用", "采购归属对应表引用", "发货记录表引用", "库存盘点表引用", "库存余额与差异表引用", "库存结存来源明细表引用", "意见采纳表引用", "意见执行表引用", "整改处理表引用") = 1)
   );


研发
~~~~


研发需要持有的是：

产品主数据表：主录ID为PID；字段及引用：名称、规格、单位及类别，人工确认，供各部门引用。
物料主数据表：主录ID为MID；字段及引用：名称、规格、单位及类别，人工确认，供各部门引用。
项目登记表：主录ID为项目ID；字段及引用：草稿登记ID、项目名称、负责人、起止日期及确认依据，人工确认。
产品版本表：主录ID为产品版本ID；字段及引用：项目ID、PID、版本名称、生效日期及确认依据，人工确认。
项目文件及登记表：主录ID为文件ID；字段及引用：项目ID、PID、文件类型、文件名、相对路径、SHA256、正式版本、发布依据、批准人及生效日期；保存设计稿、生产稿、BOM、数据手册和测试记录。
BOM登记表：主录ID为BOM登记ID；字段及引用：产品版本ID、BOM版本及确认依据，人工确认。
BOM明细表：主录ID为BOM明细ID；字段及引用：BOM登记ID、MID、单件用量、单位、原始器件描述、位号、封装、厂家料号、供应商料号、来源文件ID及行号、确认依据，自动提取，人工确认。
设计变更与验证表：主录ID为研发事项ID；字段及引用：项目ID、PID、新旧版本、变更或验证内容、日期、测试条件及结果、证据、确认人、来源检验ID及需求ID，人工确认。
产品规格表：主录ID为规格ID；字段及引用：PID、产品版本、规格内容、适用范围、限制条件、证据、批准人及生效日期，人工批准。
研发工时表：主录ID为工时ID；字段及引用：项目ID、人员ID、日期、实际工时、工作内容及凭证，人工确认。
研发投入归属表：主录ID为投入登记ID；字段及引用：项目ID、财务费用ID或计价ID、研发或生产工时ID、归属依据及确认人，人工确认研发归属。
发布批次表：主录ID为发布批次ID；字段及引用：产品版本ID、BOM登记ID、批准人、生效日期及适用范围，人工批准。
发布文件明细表：主录ID为发布文件明细ID；字段及引用：发布批次ID、文件ID，自动整理，批准后打包。

研发需要默认交出的是：

打包的项目文件：生产稿、数据手册、测试记录，按发布批次ID交付。
发布批次表及发布文件明细表：分别沿用发布批次ID、发布文件明细ID交付。
已核定的BOM明细表：沿用BOM明细ID，引用BOM登记ID及MID，交付用量及替代适用条件。
研发验证及变更结论：按研发事项ID交付结果、适用版本、整改建议及关闭依据。
研发实际投入说明：沿用投入登记ID，引用项目ID及工时ID，供财务计价及核定期间。


SQL记录粒度与字段定义
^^^^^^^^^^^^^^^^^^^^^^^^


下列表中，ID主键标识本表主录；引用列的目标统一列在文末外键定义中。


计量单位表
""""""""""


记录粒度：一种明确的计量单位。

.. sql-source-line: 2044

.. code-block:: sql

   CREATE TABLE rd."计量单位表" (
     "单位ID" text PRIMARY KEY,
     "单位名称" text NOT NULL,
     "备注" text
   );


产品主数据表
""""""""""""


记录粒度：一个产品标识。

引用关系：单位ID → rd.计量单位表。

.. sql-source-line: 2060

.. code-block:: sql

   CREATE TABLE rd."产品主数据表" (
     "PID" text PRIMARY KEY,
     "名称" text NOT NULL,
     "规格" text NOT NULL,
     "单位ID" text NOT NULL,
     "类别" text NOT NULL
   );


物料主数据表
""""""""""""


记录粒度：一个物料标识。

引用关系：单位ID → rd.计量单位表。

.. sql-source-line: 2076

.. code-block:: sql

   CREATE TABLE rd."物料主数据表" (
     "MID" text PRIMARY KEY,
     "名称" text NOT NULL,
     "规格" text NOT NULL,
     "单位ID" text NOT NULL,
     "类别" text NOT NULL
   );


项目草稿表
""""""""""


记录粒度：一个项目正式编号前的登记。

 本版状态：待确认、已立项、已取消。

.. sql-source-line: 2092

.. code-block:: sql

   CREATE TABLE rd."项目草稿表" (
     "草稿登记ID" text PRIMARY KEY,
     "项目描述" text NOT NULL,
     "登记日期" date NOT NULL,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('待确认', '已立项', '已取消'))
   );


项目登记表
""""""""""


记录粒度：一个正式研发项目。

引用关系：草稿登记ID → rd.项目草稿表；负责人ID → finance.人员档案表。

.. sql-source-line: 2108

.. code-block:: sql

   CREATE TABLE rd."项目登记表" (
     "项目ID" text PRIMARY KEY,
     "草稿登记ID" text,
     "项目名称" text NOT NULL,
     "负责人ID" text,
     "开始日期" date,
     "结束日期" date,
     "确认依据" text NOT NULL
   );


产品版本表
""""""""""


记录粒度：一个产品的一版设计定义。

引用关系：项目ID → rd.项目登记表；PID → rd.产品主数据表。

.. sql-source-line: 2126

.. code-block:: sql

   CREATE TABLE rd."产品版本表" (
     "产品版本ID" text PRIMARY KEY,
     "项目ID" text NOT NULL,
     "PID" text NOT NULL,
     "版本名称" text NOT NULL,
     "生效日期" date,
     "确认依据" text NOT NULL,
     UNIQUE ("PID", "版本名称")
   );


物料版本表
""""""""""


记录粒度：一个物料的一版采购及制造规格。

补充原库存、采购和领退料中的物料版本引用。

引用关系：MID → rd.物料主数据表。

.. sql-source-line: 2146

.. code-block:: sql

   CREATE TABLE rd."物料版本表" (
     "物料版本ID" text PRIMARY KEY,
     "MID" text NOT NULL,
     "版本名称" text NOT NULL,
     "生效日期" date,
     "确认依据" text NOT NULL,
     UNIQUE ("MID", "版本名称")
   );


单位换算表
""""""""""


记录粒度：一种物品版本一组单位之间的一版换算。

先定义1来源单位等于多少目标单位；不存在适用换算时不得直接合并数量。

引用关系：来源单位ID → rd.计量单位表；目标单位ID → rd.计量单位表；产品版本ID → rd.产品版本表；物料版本ID → rd.物料版本表。

.. sql-source-line: 2165

.. code-block:: sql

   CREATE TABLE rd."单位换算表" (
     "换算ID" text PRIMARY KEY,
     "来源单位ID" text NOT NULL,
     "目标单位ID" text NOT NULL,
     "换算系数" numeric(20,6) NOT NULL,
     "生效日期" date NOT NULL,
     "失效日期" date,
     "依据" text NOT NULL,
     "产品版本ID" text,
     "物料版本ID" text,
     CHECK (num_nonnulls("产品版本ID", "物料版本ID") = 1),
     CHECK ("换算系数" > 0),
     CHECK ("来源单位ID" <> "目标单位ID")
   );


项目文件登记表
""""""""""""""


记录粒度：一份项目文件的一版文件内容。

引用关系：项目ID → rd.项目登记表；PID → rd.产品主数据表；批准人ID → finance.人员档案表。

.. sql-source-line: 2188

.. code-block:: sql

   CREATE TABLE rd."项目文件登记表" (
     "文件ID" text PRIMARY KEY,
     "项目ID" text NOT NULL,
     "PID" text,
     "文件类型" text NOT NULL,
     "文件名" text NOT NULL,
     "相对路径" text NOT NULL,
     "SHA256" char(64) NOT NULL,
     "正式版本" text NOT NULL,
     "发布依据" text,
     "批准人ID" text,
     "生效日期" date
   );


BOM登记表
""""""""""""


记录粒度：一个产品版本的一版BOM。

引用关系：产品版本ID → rd.产品版本表。

.. sql-source-line: 2210

.. code-block:: sql

   CREATE TABLE rd."BOM登记表" (
     "BOM登记ID" text PRIMARY KEY,
     "产品版本ID" text NOT NULL,
     "BOM版本" text NOT NULL,
     "确认依据" text NOT NULL,
     UNIQUE ("产品版本ID", "BOM版本")
   );


BOM明细表
""""""""""""


记录粒度：一版BOM中一个独立装配位置或用量行。

相同物料在不同位置可多行出现；原始器件描述保留来源提取事实。

引用关系：BOM登记ID → rd.BOM登记表；物料版本ID → rd.物料版本表；单位ID → rd.计量单位表；来源文件ID → rd.项目文件登记表。

.. sql-source-line: 2228

.. code-block:: sql

   CREATE TABLE rd."BOM明细表" (
     "BOM明细ID" text PRIMARY KEY,
     "BOM登记ID" text NOT NULL,
     "行号" integer NOT NULL,
     "物料版本ID" text NOT NULL,
     "单件用量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "原始器件描述" text,
     "位号" text,
     "封装" text,
     "厂家料号" text,
     "供应商料号" text,
     "来源文件ID" text NOT NULL,
     "来源行号" integer,
     "确认依据" text NOT NULL,
     "替代适用条件" text,
     UNIQUE ("BOM登记ID", "行号"),
     CHECK ("单件用量" > 0)
   );


设计变更与验证表
""""""""""""""""


记录粒度：一次独立设计变更或验证事项。

 本版状态：待处理、验证中、已确认、已关闭。

引用关系：项目ID → rd.项目登记表；PID → rd.产品主数据表；原产品版本ID → rd.产品版本表；新产品版本ID → rd.产品版本表；确认人ID → finance.人员档案表。

.. sql-source-line: 2258

.. code-block:: sql

   CREATE TABLE rd."设计变更与验证表" (
     "研发事项ID" text PRIMARY KEY,
     "项目ID" text NOT NULL,
     "PID" text NOT NULL,
     "原产品版本ID" text,
     "新产品版本ID" text,
     "内容" text NOT NULL,
     "日期" date NOT NULL,
     "测试条件" text,
     "测试结果" text,
     "证据路径" text,
     "确认人ID" text,
     "整改建议" text,
     "关闭依据" text,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('待处理', '验证中', '已确认', '已关闭'))
   );


研发事项来源表
""""""""""""""


记录粒度：一个研发事项对应的一条客户需求或检验事实。

多项需求可进入同一研发事项，同一检验也可触发多个研发事项。

引用关系：研发事项ID → rd.设计变更与验证表；检验ID → production.质量检验表；需求ID → sales.客户需求表；售后事件ID → sales.售后事件表。

.. sql-source-line: 2286

.. code-block:: sql

   CREATE TABLE rd."研发事项来源表" (
     "来源关联ID" text PRIMARY KEY,
     "研发事项ID" text NOT NULL,
     "检验ID" text,
     "需求ID" text,
     "售后事件ID" text,
     CHECK (num_nonnulls("检验ID", "需求ID", "售后事件ID") = 1)
   );


产品规格表
""""""""""


记录粒度：一个产品版本中的一条独立规格。

引用关系：产品版本ID → rd.产品版本表；批准人ID → finance.人员档案表。

.. sql-source-line: 2303

.. code-block:: sql

   CREATE TABLE rd."产品规格表" (
     "规格ID" text PRIMARY KEY,
     "产品版本ID" text NOT NULL,
     "规格代码" text NOT NULL,
     "规格内容" text NOT NULL,
     "适用范围" text,
     "限制条件" text,
     "证据路径" text,
     "批准人ID" text,
     "生效日期" date,
     UNIQUE ("产品版本ID", "规格代码")
   );


研发工时表
""""""""""


记录粒度：一名人员在某项目某日的一条实际工作投入。

引用关系：项目ID → rd.项目登记表；人员ID → finance.人员档案表。

.. sql-source-line: 2324

.. code-block:: sql

   CREATE TABLE rd."研发工时表" (
     "工时ID" text PRIMARY KEY,
     "项目ID" text NOT NULL,
     "人员ID" text NOT NULL,
     "日期" date NOT NULL,
     "实际工时" numeric(12,4) NOT NULL,
     "工作内容" text NOT NULL,
     "凭证路径" text,
     CHECK ("实际工时" >= 0)
   );


研发投入归属表
""""""""""""""


记录粒度：一项财务费用或计价金额向一个项目的一次归属分配。

计价记录已关联实际工时，不再在本表重复登记相同工时和金额。

引用关系：项目ID → rd.项目登记表；费用ID → finance.费用归属表；计价ID → finance.工时计价表；确认人ID → finance.人员档案表。

.. sql-source-line: 2345

.. code-block:: sql

   CREATE TABLE rd."研发投入归属表" (
     "投入登记ID" text PRIMARY KEY,
     "项目ID" text NOT NULL,
     "费用ID" text,
     "计价ID" text,
     "归属比例" numeric(12,8) NOT NULL,
     "归属依据" text NOT NULL,
     "确认人ID" text,
     CHECK (num_nonnulls("费用ID", "计价ID") = 1),
     CHECK ("归属比例" > 0 AND "归属比例" <= 1)
   );


发布批次表
""""""""""


记录粒度：一版BOM连同文件的一次批准发布。

产品版本通过BOM查询，不同时保存可能矛盾的产品版本ID。 本版状态：待发布、已发布、已撤回。

引用关系：BOM登记ID → rd.BOM登记表；批准人ID → finance.人员档案表。

.. sql-source-line: 2367

.. code-block:: sql

   CREATE TABLE rd."发布批次表" (
     "发布批次ID" text PRIMARY KEY,
     "BOM登记ID" text NOT NULL,
     "批准人ID" text NOT NULL,
     "生效日期" date NOT NULL,
     "适用范围" text NOT NULL,
     "发布包路径" text,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('待发布', '已发布', '已撤回'))
   );


发布文件明细表
""""""""""""""


记录粒度：一个发布批次包含的一份文件版本。

引用关系：发布批次ID → rd.发布批次表；文件ID → rd.项目文件登记表。

.. sql-source-line: 2386

.. code-block:: sql

   CREATE TABLE rd."发布文件明细表" (
     "发布文件明细ID" text PRIMARY KEY,
     "发布批次ID" text NOT NULL,
     "文件ID" text NOT NULL,
     UNIQUE ("发布批次ID", "文件ID")
   );


交付记录表
""""""""""


记录粒度：本部门发布的一版数据或文件交付。

引用关系：确认人ID → finance.人员档案表。

.. sql-source-line: 2401

.. code-block:: sql

   CREATE TABLE rd."交付记录表" (
     "交付ID" text PRIMARY KEY,
     "交付名称" text NOT NULL,
     "交付版本" text NOT NULL,
     "期间开始" date,
     "期间结束" date,
     "数据截止时间" timestamptz NOT NULL,
     "交付时间" timestamptz NOT NULL,
     "文件路径" text,
     "待核事项" text,
     "确认人ID" text
   );


意见采纳表
""""""""""


记录粒度：本部门对一项分析建议的一次采纳决定。

引用关系：意见ID → analysis.意见与规划总表；负责人ID → finance.人员档案表。

.. sql-source-line: 2422

.. code-block:: sql

   CREATE TABLE rd."意见采纳表" (
     "采纳记录ID" text PRIMARY KEY,
     "意见ID" text NOT NULL,
     "决定日期" date NOT NULL,
     "采纳结论" text NOT NULL,
     "目标" text,
     "负责人ID" text
   );


意见执行表
""""""""""


记录粒度：本部门对一次采纳决定的一次实际执行。

引用关系：采纳记录ID → rd.意见采纳表；负责人ID → finance.人员档案表。

.. sql-source-line: 2439

.. code-block:: sql

   CREATE TABLE rd."意见执行表" (
     "执行记录ID" text PRIMARY KEY,
     "采纳记录ID" text NOT NULL,
     "执行时间" timestamptz NOT NULL,
     "执行内容" text NOT NULL,
     "实际结果" text,
     "证据路径" text,
     "负责人ID" text
   );


整改处理表
""""""""""


记录粒度：本部门对一项整改要求的一次实际处理。

引用关系：整改事项ID → legal.整改跟踪表；处理人ID → finance.人员档案表。

.. sql-source-line: 2457

.. code-block:: sql

   CREATE TABLE rd."整改处理表" (
     "整改处理记录ID" text PRIMARY KEY,
     "整改事项ID" text NOT NULL,
     "处理时间" timestamptz NOT NULL,
     "处理内容" text NOT NULL,
     "结果" text,
     "证据路径" text,
     "处理人ID" text
   );


交付明细表
""""""""""


记录粒度：本部门一次交付中引用的一条本部门记录。

每行只选一个来源；一份交付可含任意多行，不复制来源记录字段。

引用关系：交付ID → rd.交付记录表；计量单位表引用 → rd.计量单位表；产品主数据表引用 → rd.产品主数据表；物料主数据表引用 → rd.物料主数据表；项目草稿表引用 → rd.项目草稿表；项目登记表引用 → rd.项目登记表；产品版本表引用 → rd.产品版本表；物料版本表引用 → rd.物料版本表；单位换算表引用 → rd.单位换算表；项目文件登记表引用 → rd.项目文件登记表；BOM登记表引用 → rd.BOM登记表；BOM明细表引用 → rd.BOM明细表；设计变更与验证表引用 → rd.设计变更与验证表；研发事项来源表引用 → rd.研发事项来源表；产品规格表引用 → rd.产品规格表；研发工时表引用 → rd.研发工时表；研发投入归属表引用 → rd.研发投入归属表；发布批次表引用 → rd.发布批次表；发布文件明细表引用 → rd.发布文件明细表；意见采纳表引用 → rd.意见采纳表；意见执行表引用 → rd.意见执行表；整改处理表引用 → rd.整改处理表。

.. sql-source-line: 2477

.. code-block:: sql

   CREATE TABLE rd."交付明细表" (
     "交付明细ID" text PRIMARY KEY,
     "交付ID" text NOT NULL,
     "计量单位表引用" text,
     "产品主数据表引用" text,
     "物料主数据表引用" text,
     "项目草稿表引用" text,
     "项目登记表引用" text,
     "产品版本表引用" text,
     "物料版本表引用" text,
     "单位换算表引用" text,
     "项目文件登记表引用" text,
     "BOM登记表引用" text,
     "BOM明细表引用" text,
     "设计变更与验证表引用" text,
     "研发事项来源表引用" text,
     "产品规格表引用" text,
     "研发工时表引用" text,
     "研发投入归属表引用" text,
     "发布批次表引用" text,
     "发布文件明细表引用" text,
     "意见采纳表引用" text,
     "意见执行表引用" text,
     "整改处理表引用" text,
     CHECK (num_nonnulls("计量单位表引用", "产品主数据表引用", "物料主数据表引用", "项目草稿表引用", "项目登记表引用", "产品版本表引用", "物料版本表引用", "单位换算表引用", "项目文件登记表引用", "BOM登记表引用", "BOM明细表引用", "设计变更与验证表引用", "研发事项来源表引用", "产品规格表引用", "研发工时表引用", "研发投入归属表引用", "发布批次表引用", "发布文件明细表引用", "意见采纳表引用", "意见执行表引用", "整改处理表引用") = 1)
   );


销售
~~~~


销售需要持有的是：

客户档案表：主录ID为客户ID；字段及引用：客户来源标识、产业及地区分类、分类依据、确认日期及未知原因，人工确认。
平台销售流水单：保存销售平台原始导出文件。
销售订单登记表：主录ID为订单ID；字段及引用：渠道ID、客户ID、支付单号、创建及付款时间、原商品标题及属性、原始实付、累计退款、原发货和物流信息、来源文件及行号，自动导入。
销售合同表：主录ID为销售合同ID；字段及引用：客户ID、订单ID及合同文件路径，人工记录。
销售动作表：主录ID为销售动作ID；字段及引用：客户ID、订单ID、销售合同ID、发生时间及销售行为记录，人工记录。
销售订单行表：主录ID为销售订单行ID；字段及引用：订单ID、子订单号、原商品信息、PID、版本、数量、单位、单价、折扣、商品实付、运费、税额分摊、交期、收货信息及来源凭证，人工确认，引用研发PID。
商品对应表：主录ID为映射登记ID；字段及引用：原标题及属性、渠道ID、渠道SKU、PID、组合商品ID、换算数量、单位、生效失效日期及确认依据，人工确认。
售后事件表：主录ID为售后事件ID；字段及引用：类型、订单ID及行ID、发生时间、PID、数量、申请或约定退款金额、原因、退回仓库ID、资金记录ID及凭证，人工确认；实际收退款引用财务资金记录ID，实际退回引用生产库存事件ID。
客户需求表：主录ID为需求ID；字段及引用：日期、订单ID、PID、客户原话、使用场景、来源证据及研发事项ID，人工记录。

销售需要默认提供的是：

客户所在产业和地区分类统计表：分类统计ID、统计期间、分类口径、去重规则、客户数、订单数、金额口径及未分类数量，自动统计。
订单与履约交付表：沿用销售订单行ID，引用订单ID及销售合同ID，供生产履约、财务核对。
售后反馈表：沿用售后事件ID交付处理状态，供生产检验及研发评估。
需求反馈表：沿用需求ID交付处理状态，供研发评估。
销售期间覆盖与例外清单：覆盖记录ID、导出时间、筛选条件、实际覆盖期间、去重规则、退款口径及未核商品行，自动整理，人工确认。


SQL记录粒度与字段定义
^^^^^^^^^^^^^^^^^^^^^^^^


下列表中，ID主键标识本表主录；引用列的目标统一列在文末外键定义中。


渠道档案表
""""""""""


记录粒度：一个业务销售渠道。

.. sql-source-line: 2537

.. code-block:: sql

   CREATE TABLE sales."渠道档案表" (
     "渠道ID" text PRIMARY KEY,
     "渠道名称" text NOT NULL,
     "平台名称" text NOT NULL,
     "店铺标识" text NOT NULL,
     UNIQUE ("平台名称", "店铺标识")
   );


客户档案表
""""""""""


记录粒度：一个已识别的客户。

.. sql-source-line: 2551

.. code-block:: sql

   CREATE TABLE sales."客户档案表" (
     "客户ID" text PRIMARY KEY,
     "客户名称" text,
     "客户来源标识" text NOT NULL,
     "产业分类" text,
     "地区分类" text,
     "分类依据" text,
     "确认日期" date,
     "未知原因" text
   );


平台文件登记表
""""""""""""""


记录粒度：一次销售平台原始文件导出。

引用关系：渠道ID → sales.渠道档案表。

.. sql-source-line: 2570

.. code-block:: sql

   CREATE TABLE sales."平台文件登记表" (
     "平台文件ID" text PRIMARY KEY,
     "渠道ID" text NOT NULL,
     "导出时间" timestamptz NOT NULL,
     "覆盖开始日期" date,
     "覆盖结束日期" date,
     "筛选条件" text,
     "文件路径" text NOT NULL,
     "文件校验值" text NOT NULL
   );


销售订单登记表
""""""""""""""


记录粒度：一个销售渠道中的一个平台订单。

 本版状态：待确认、已确认、已关闭、已取消。

引用关系：渠道ID → sales.渠道档案表；客户ID → sales.客户档案表。

.. sql-source-line: 2591

.. code-block:: sql

   CREATE TABLE sales."销售订单登记表" (
     "订单ID" text PRIMARY KEY,
     "渠道ID" text NOT NULL,
     "平台订单号" text NOT NULL,
     "客户ID" text,
     "支付单号" text,
     "创建时间" timestamptz NOT NULL,
     "币种" char(3) NOT NULL,
     "状态" text NOT NULL,
     UNIQUE ("渠道ID", "平台订单号"),
     CHECK ("状态" IN ('待确认', '已确认', '已关闭', '已取消'))
   );


订单导出快照表
""""""""""""""


记录粒度：一个订单在一次平台导出中的原始快照。

原始累计退款、发货信息可能随导出变化，不能作为新的销售或资金发生事件。

引用关系：订单ID → sales.销售订单登记表；平台文件ID → sales.平台文件登记表。

.. sql-source-line: 2614

.. code-block:: sql

   CREATE TABLE sales."订单导出快照表" (
     "订单快照ID" text PRIMARY KEY,
     "订单ID" text NOT NULL,
     "平台文件ID" text NOT NULL,
     "来源行号" integer NOT NULL,
     "付款时间" timestamptz,
     "原商品标题" text,
     "原商品属性" text,
     "原始实付" numeric(20,4),
     "原始累计退款" numeric(20,4),
     "原发货信息" text,
     "原物流信息" text,
     UNIQUE ("平台文件ID", "来源行号")
   );


销售合同表
""""""""""


记录粒度：一份销售合同。

 本版状态：草稿、已签署、已终止。

引用关系：客户ID → sales.客户档案表。

.. sql-source-line: 2639

.. code-block:: sql

   CREATE TABLE sales."销售合同表" (
     "销售合同ID" text PRIMARY KEY,
     "客户ID" text NOT NULL,
     "签署日期" date,
     "合同文件路径" text NOT NULL,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('草稿', '已签署', '已终止'))
   );


合同订单对应表
""""""""""""""


记录粒度：一份合同与一张订单的关联。

引用关系：销售合同ID → sales.销售合同表；订单ID → sales.销售订单登记表。

.. sql-source-line: 2656

.. code-block:: sql

   CREATE TABLE sales."合同订单对应表" (
     "合同订单关联ID" text PRIMARY KEY,
     "销售合同ID" text NOT NULL,
     "订单ID" text NOT NULL,
     UNIQUE ("销售合同ID", "订单ID")
   );


销售动作表
""""""""""


记录粒度：针对客户的一次销售行为。

引用关系：客户ID → sales.客户档案表；订单ID → sales.销售订单登记表；销售合同ID → sales.销售合同表。

.. sql-source-line: 2671

.. code-block:: sql

   CREATE TABLE sales."销售动作表" (
     "销售动作ID" text PRIMARY KEY,
     "客户ID" text NOT NULL,
     "订单ID" text,
     "销售合同ID" text,
     "发生时间" timestamptz NOT NULL,
     "行为记录" text NOT NULL
   );


销售订单行表
""""""""""""


记录粒度：一张订单中的一个已确认商品行。

未确认商品映射时产品版本允许为空；已确认履约前需补齐。 本版状态：待映射、待履约、部分履约、已完成、已取消。

引用关系：订单ID → sales.销售订单登记表；产品版本ID → rd.产品版本表；单位ID → rd.计量单位表；来源订单快照ID → sales.订单导出快照表。

.. sql-source-line: 2690

.. code-block:: sql

   CREATE TABLE sales."销售订单行表" (
     "销售订单行ID" text PRIMARY KEY,
     "订单ID" text NOT NULL,
     "行号" integer NOT NULL,
     "子订单号" text,
     "原商品信息" text NOT NULL,
     "产品版本ID" text,
     "数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "单价" numeric(20,4) NOT NULL,
     "折扣金额" numeric(20,4) NOT NULL,
     "商品实付" numeric(20,4) NOT NULL,
     "运费分摊" numeric(20,4) NOT NULL,
     "税额分摊" numeric(20,4),
     "交期" date,
     "收货信息" text NOT NULL,
     "来源订单快照ID" text,
     "取消数量" numeric(20,6) NOT NULL,
     "状态" text NOT NULL,
     UNIQUE ("订单ID", "行号"),
     CHECK ("数量" > 0),
     CHECK ("取消数量" >= 0 AND "取消数量" <= "数量"),
     CHECK ("状态" IN ('待映射', '待履约', '部分履约', '已完成', '已取消'))
   );


组合商品表
""""""""""


记录粒度：一种销售组合商品。

.. sql-source-line: 2721

.. code-block:: sql

   CREATE TABLE sales."组合商品表" (
     "组合商品ID" text PRIMARY KEY,
     "组合名称" text NOT NULL,
     "定义版本" text NOT NULL,
     "生效日期" date NOT NULL,
     "失效日期" date
   );


组合商品明细表
""""""""""""""


记录粒度：一个销售组合中的一种产品版本。

引用关系：组合商品ID → sales.组合商品表；产品版本ID → rd.产品版本表；单位ID → rd.计量单位表。

.. sql-source-line: 2737

.. code-block:: sql

   CREATE TABLE sales."组合商品明细表" (
     "组合明细ID" text PRIMARY KEY,
     "组合商品ID" text NOT NULL,
     "产品版本ID" text NOT NULL,
     "换算数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     UNIQUE ("组合商品ID", "产品版本ID"),
     CHECK ("换算数量" > 0)
   );


订单组合明细表
""""""""""""""


记录粒度：一个订单行购买组合时需履约的一种产品。

组合订单履约按本明细追踪，销售订单行保留原成交金额；不得拆行后重复累计成交金额。

引用关系：销售订单行ID → sales.销售订单行表；组合明细ID → sales.组合商品明细表。

.. sql-source-line: 2757

.. code-block:: sql

   CREATE TABLE sales."订单组合明细表" (
     "订单组合明细ID" text PRIMARY KEY,
     "销售订单行ID" text NOT NULL,
     "组合明细ID" text NOT NULL,
     "应履约数量" numeric(20,6) NOT NULL,
     UNIQUE ("销售订单行ID", "组合明细ID")
   );


商品对应表
""""""""""


记录粒度：一个渠道SKU在一个有效范围内的一版商品映射。

有效期重叠校验属于发布映射时的业务核对。

引用关系：渠道ID → sales.渠道档案表；产品版本ID → rd.产品版本表；组合商品ID → sales.组合商品表；单位ID → rd.计量单位表。

.. sql-source-line: 2775

.. code-block:: sql

   CREATE TABLE sales."商品对应表" (
     "映射登记ID" text PRIMARY KEY,
     "渠道ID" text NOT NULL,
     "渠道SKU" text NOT NULL,
     "原标题" text NOT NULL,
     "原属性" text,
     "产品版本ID" text,
     "组合商品ID" text,
     "换算数量" numeric(20,6) NOT NULL,
     "单位ID" text NOT NULL,
     "生效日期" date NOT NULL,
     "失效日期" date,
     "确认依据" text NOT NULL,
     UNIQUE ("渠道ID", "渠道SKU", "生效日期"),
     CHECK (num_nonnulls("产品版本ID", "组合商品ID") = 1)
   );


售后事件表
""""""""""


记录粒度：一个订单行的一次客户售后诉求。

实际退款通过财务分摊查询；实际退回通过库存事件查询，不重复建立实际金额和实物主录。 本版处理状态：新建、处理中、已关闭、已取消。

引用关系：销售订单行ID → sales.销售订单行表；单位ID → rd.计量单位表；退回仓库ID → production.仓库档案表。

.. sql-source-line: 2802

.. code-block:: sql

   CREATE TABLE sales."售后事件表" (
     "售后事件ID" text PRIMARY KEY,
     "销售订单行ID" text NOT NULL,
     "类型" text NOT NULL,
     "发生时间" timestamptz NOT NULL,
     "数量" numeric(20,6),
     "单位ID" text,
     "申请或约定退款金额" numeric(20,4),
     "原因" text NOT NULL,
     "退回仓库ID" text,
     "凭证路径" text,
     "处理状态" text NOT NULL,
     CHECK ("处理状态" IN ('新建', '处理中', '已关闭', '已取消'))
   );


客户需求表
""""""""""


记录粒度：一次独立客户需求表达。

研发处理关联由研发事项来源表持有。 本版处理状态：新建、评估中、已采纳、未采纳、已关闭。

引用关系：订单ID → sales.销售订单登记表；产品版本ID → rd.产品版本表；客户ID → sales.客户档案表。

.. sql-source-line: 2827

.. code-block:: sql

   CREATE TABLE sales."客户需求表" (
     "需求ID" text PRIMARY KEY,
     "订单ID" text,
     "产品版本ID" text,
     "客户ID" text,
     "日期" date NOT NULL,
     "客户原话" text NOT NULL,
     "使用场景" text,
     "来源证据" text NOT NULL,
     "处理状态" text NOT NULL,
     CHECK ("处理状态" IN ('新建', '评估中', '已采纳', '未采纳', '已关闭'))
   );


销售期间覆盖表
""""""""""""""


记录粒度：一次平台导出范围与缺失情况说明。

引用关系：平台文件ID → sales.平台文件登记表；确认人ID → finance.人员档案表。

.. sql-source-line: 2848

.. code-block:: sql

   CREATE TABLE sales."销售期间覆盖表" (
     "覆盖记录ID" text PRIMARY KEY,
     "平台文件ID" text NOT NULL,
     "去重规则" text NOT NULL,
     "不可恢复记录说明" text,
     "退款口径" text NOT NULL,
     "未核商品行说明" text,
     "确认人ID" text,
     UNIQUE ("平台文件ID")
   );


客户分类统计批次表
""""""""""""""""""


记录粒度：一版客户行业及地区统计的统计范围。

来源交付外键在交付记录表生成后补齐。

引用关系：来源交付ID → sales.交付记录表。

.. sql-source-line: 2869

.. code-block:: sql

   CREATE TABLE sales."客户分类统计批次表" (
     "分类统计ID" text PRIMARY KEY,
     "期间开始" date NOT NULL,
     "期间结束" date NOT NULL,
     "分类口径" text NOT NULL,
     "去重规则" text NOT NULL,
     "金额口径" text NOT NULL,
     "生成时间" timestamptz NOT NULL,
     "来源交付ID" text
   );


客户分类统计结果表
""""""""""""""""""


记录粒度：一个统计批次中一个行业、地区及币种组合的结果。

引用关系：分类统计ID → sales.客户分类统计批次表。

.. sql-source-line: 2888

.. code-block:: sql

   CREATE TABLE sales."客户分类统计结果表" (
     "分类结果ID" text PRIMARY KEY,
     "分类统计ID" text NOT NULL,
     "产业分类" text,
     "地区分类" text,
     "币种" char(3) NOT NULL,
     "客户数" integer NOT NULL,
     "订单数" integer NOT NULL,
     "已核定金额" numeric(20,4),
     "未分类客户数" integer NOT NULL,
     UNIQUE NULLS NOT DISTINCT ("分类统计ID", "产业分类", "地区分类", "币种"),
     CHECK ("客户数" >= 0 AND "订单数" >= 0 AND "未分类客户数" >= 0)
   );


交付记录表
""""""""""


记录粒度：本部门发布的一版数据或文件交付。

引用关系：确认人ID → finance.人员档案表。

.. sql-source-line: 2910

.. code-block:: sql

   CREATE TABLE sales."交付记录表" (
     "交付ID" text PRIMARY KEY,
     "交付名称" text NOT NULL,
     "交付版本" text NOT NULL,
     "期间开始" date,
     "期间结束" date,
     "数据截止时间" timestamptz NOT NULL,
     "交付时间" timestamptz NOT NULL,
     "文件路径" text,
     "待核事项" text,
     "确认人ID" text
   );


意见采纳表
""""""""""


记录粒度：本部门对一项分析建议的一次采纳决定。

引用关系：意见ID → analysis.意见与规划总表；负责人ID → finance.人员档案表。

.. sql-source-line: 2931

.. code-block:: sql

   CREATE TABLE sales."意见采纳表" (
     "采纳记录ID" text PRIMARY KEY,
     "意见ID" text NOT NULL,
     "决定日期" date NOT NULL,
     "采纳结论" text NOT NULL,
     "目标" text,
     "负责人ID" text
   );


意见执行表
""""""""""


记录粒度：本部门对一次采纳决定的一次实际执行。

引用关系：采纳记录ID → sales.意见采纳表；负责人ID → finance.人员档案表。

.. sql-source-line: 2948

.. code-block:: sql

   CREATE TABLE sales."意见执行表" (
     "执行记录ID" text PRIMARY KEY,
     "采纳记录ID" text NOT NULL,
     "执行时间" timestamptz NOT NULL,
     "执行内容" text NOT NULL,
     "实际结果" text,
     "证据路径" text,
     "负责人ID" text
   );


整改处理表
""""""""""


记录粒度：本部门对一项整改要求的一次实际处理。

引用关系：整改事项ID → legal.整改跟踪表；处理人ID → finance.人员档案表。

.. sql-source-line: 2966

.. code-block:: sql

   CREATE TABLE sales."整改处理表" (
     "整改处理记录ID" text PRIMARY KEY,
     "整改事项ID" text NOT NULL,
     "处理时间" timestamptz NOT NULL,
     "处理内容" text NOT NULL,
     "结果" text,
     "证据路径" text,
     "处理人ID" text
   );


交付明细表
""""""""""


记录粒度：本部门一次交付中引用的一条本部门记录。

每行只选一个来源；一份交付可含任意多行，不复制来源记录字段。

引用关系：交付ID → sales.交付记录表；渠道档案表引用 → sales.渠道档案表；客户档案表引用 → sales.客户档案表；平台文件登记表引用 → sales.平台文件登记表；销售订单登记表引用 → sales.销售订单登记表；订单导出快照表引用 → sales.订单导出快照表；销售合同表引用 → sales.销售合同表；合同订单对应表引用 → sales.合同订单对应表；销售动作表引用 → sales.销售动作表；销售订单行表引用 → sales.销售订单行表；组合商品表引用 → sales.组合商品表；组合商品明细表引用 → sales.组合商品明细表；订单组合明细表引用 → sales.订单组合明细表；商品对应表引用 → sales.商品对应表；售后事件表引用 → sales.售后事件表；客户需求表引用 → sales.客户需求表；销售期间覆盖表引用 → sales.销售期间覆盖表；客户分类统计批次表引用 → sales.客户分类统计批次表；客户分类统计结果表引用 → sales.客户分类统计结果表；意见采纳表引用 → sales.意见采纳表；意见执行表引用 → sales.意见执行表；整改处理表引用 → sales.整改处理表。

.. sql-source-line: 2986

.. code-block:: sql

   CREATE TABLE sales."交付明细表" (
     "交付明细ID" text PRIMARY KEY,
     "交付ID" text NOT NULL,
     "渠道档案表引用" text,
     "客户档案表引用" text,
     "平台文件登记表引用" text,
     "销售订单登记表引用" text,
     "订单导出快照表引用" text,
     "销售合同表引用" text,
     "合同订单对应表引用" text,
     "销售动作表引用" text,
     "销售订单行表引用" text,
     "组合商品表引用" text,
     "组合商品明细表引用" text,
     "订单组合明细表引用" text,
     "商品对应表引用" text,
     "售后事件表引用" text,
     "客户需求表引用" text,
     "销售期间覆盖表引用" text,
     "客户分类统计批次表引用" text,
     "客户分类统计结果表引用" text,
     "意见采纳表引用" text,
     "意见执行表引用" text,
     "整改处理表引用" text,
     CHECK (num_nonnulls("渠道档案表引用", "客户档案表引用", "平台文件登记表引用", "销售订单登记表引用", "订单导出快照表引用", "销售合同表引用", "合同订单对应表引用", "销售动作表引用", "销售订单行表引用", "组合商品表引用", "组合商品明细表引用", "订单组合明细表引用", "商品对应表引用", "售后事件表引用", "客户需求表引用", "销售期间覆盖表引用", "客户分类统计批次表引用", "客户分类统计结果表引用", "意见采纳表引用", "意见执行表引用", "整改处理表引用") = 1)
   );


分析
~~~~


分析需要持有的是：

数学模型库：主录ID为模型ID；字段及引用：版本、用途、参考文献、输入定义、计算或推理方法、参数、适用条件、验证记录及维护人，人工确认，自动运行。
数据引用登记表：主录ID为数据集ID；字段及引用：提供部门、输入交付ID或业务记录ID、版本、统计期间、数据截止时间及接收记录，自动登记引用。
指标定义表：主录ID为指标ID；字段及引用：版本、名称、公式、输入数据ID、统计期间、单位及适用条件，人工确认。
分析报告登记表：主录ID为报告ID；字段及引用：分析问题、输入数据集ID、模型ID、指标ID、关键结论、假设、局限、生成日期及PDF路径，自动生成，人工复核。
意见与规划总表：主录ID为意见ID；字段及引用：报告ID、问题、证据及指标ID、建议、适用前提、责任部门、计划期间、预期目标、优先级、采纳记录ID、执行记录ID、实际效果及复盘日期，自动生成建议候选；采纳和执行事实由责任部门持有。

分析需要默认交出的是：

分析报告PDF及报告登记表：按报告ID交付指标口径、数据范围、模型方法、结论及局限。
意见与规划总表：按意见ID交付建议及复盘结果。


SQL记录粒度与字段定义
^^^^^^^^^^^^^^^^^^^^^^^^


下列表中，ID主键标识本表主录；引用列的目标统一列在文末外键定义中。


数学模型库
""""""""""


记录粒度：一种模型的一版方法与参数。

JSON仅保存参数值，不保存多条业务ID引用。

引用关系：维护人ID → finance.人员档案表。

.. sql-source-line: 3043

.. code-block:: sql

   CREATE TABLE analysis."数学模型库" (
     "模型ID" text PRIMARY KEY,
     "模型名称" text NOT NULL,
     "版本" text NOT NULL,
     "用途" text NOT NULL,
     "参考文献" text,
     "输入定义" text NOT NULL,
     "方法" text NOT NULL,
     "参数" jsonb,
     "适用条件" text NOT NULL,
     "验证记录" text,
     "维护人ID" text,
     UNIQUE ("模型名称", "版本")
   );


数据引用登记表
""""""""""""""


记录粒度：一次明确统计范围的数据集定义。

.. sql-source-line: 3064

.. code-block:: sql

   CREATE TABLE analysis."数据引用登记表" (
     "数据集ID" text PRIMARY KEY,
     "数据集名称" text NOT NULL,
     "版本" text NOT NULL,
     "期间开始" date NOT NULL,
     "期间结束" date NOT NULL,
     "数据截止时间" timestamptz NOT NULL,
     "生成时间" timestamptz NOT NULL,
     "接收说明" text,
     UNIQUE ("数据集名称", "版本")
   );


指标定义表
""""""""""


记录粒度：一个指标的一版计算口径。

定义不绑定单次统计期间；实际期间与输入在指标计算记录中保存。

.. sql-source-line: 3084

.. code-block:: sql

   CREATE TABLE analysis."指标定义表" (
     "指标ID" text PRIMARY KEY,
     "指标名称" text NOT NULL,
     "版本" text NOT NULL,
     "公式" text NOT NULL,
     "单位" text NOT NULL,
     "适用条件" text NOT NULL,
     UNIQUE ("指标名称", "版本")
   );


指标计算表
""""""""""


记录粒度：一个指标在某数据集与期间的一次计算。

 本版状态：待计算、已生成、待复核、已核定。

引用关系：指标ID → analysis.指标定义表；数据集ID → analysis.数据引用登记表。

.. sql-source-line: 3104

.. code-block:: sql

   CREATE TABLE analysis."指标计算表" (
     "计算记录ID" text PRIMARY KEY,
     "指标ID" text NOT NULL,
     "数据集ID" text NOT NULL,
     "期间开始" date NOT NULL,
     "期间结束" date NOT NULL,
     "计算时间" timestamptz NOT NULL,
     "结果值" numeric,
     "结果说明" text,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('待计算', '已生成', '待复核', '已核定'))
   );


分析报告登记表
""""""""""""""


记录粒度：一份报告的一次生成版本。

引用关系：复核人ID → finance.人员档案表。

.. sql-source-line: 3125

.. code-block:: sql

   CREATE TABLE analysis."分析报告登记表" (
     "报告ID" text PRIMARY KEY,
     "分析问题" text NOT NULL,
     "关键结论" text,
     "假设" text,
     "局限" text,
     "生成日期" date NOT NULL,
     "PDF路径" text,
     "复核人ID" text
   );


报告模型对应表
""""""""""""""


记录粒度：一份报告使用的一版模型。

引用关系：报告ID → analysis.分析报告登记表；模型ID → analysis.数学模型库。

.. sql-source-line: 3144

.. code-block:: sql

   CREATE TABLE analysis."报告模型对应表" (
     "报告模型关联ID" text PRIMARY KEY,
     "报告ID" text NOT NULL,
     "模型ID" text NOT NULL,
     UNIQUE ("报告ID", "模型ID")
   );


报告数据对应表
""""""""""""""


记录粒度：一份报告引用的一个数据集。

引用关系：报告ID → analysis.分析报告登记表；数据集ID → analysis.数据引用登记表。

.. sql-source-line: 3159

.. code-block:: sql

   CREATE TABLE analysis."报告数据对应表" (
     "报告数据关联ID" text PRIMARY KEY,
     "报告ID" text NOT NULL,
     "数据集ID" text NOT NULL,
     UNIQUE ("报告ID", "数据集ID")
   );


报告指标对应表
""""""""""""""


记录粒度：一份报告引用的一次指标计算。

引用关系：报告ID → analysis.分析报告登记表；计算记录ID → analysis.指标计算表。

.. sql-source-line: 3174

.. code-block:: sql

   CREATE TABLE analysis."报告指标对应表" (
     "报告指标关联ID" text PRIMARY KEY,
     "报告ID" text NOT NULL,
     "计算记录ID" text NOT NULL,
     UNIQUE ("报告ID", "计算记录ID")
   );


意见与规划总表
""""""""""""""


记录粒度：针对一个问题的一项分析建议。

采纳与执行事实在责任部门；分析复盘另记，不回填为业务原始事实。 本版状态：待决定、跟进中、已复盘、已关闭。

引用关系：报告ID → analysis.分析报告登记表。

.. sql-source-line: 3191

.. code-block:: sql

   CREATE TABLE analysis."意见与规划总表" (
     "意见ID" text PRIMARY KEY,
     "报告ID" text NOT NULL,
     "问题" text NOT NULL,
     "建议" text NOT NULL,
     "适用前提" text,
     "责任部门" text NOT NULL,
     "计划开始日期" date,
     "计划结束日期" date,
     "预期目标" text,
     "优先级" integer NOT NULL,
     "状态" text NOT NULL,
     CHECK ("状态" IN ('待决定', '跟进中', '已复盘', '已关闭'))
   );


意见指标对应表
""""""""""""""


记录粒度：一项意见使用的一条指标计算证据。

引用关系：意见ID → analysis.意见与规划总表；计算记录ID → analysis.指标计算表。

.. sql-source-line: 3214

.. code-block:: sql

   CREATE TABLE analysis."意见指标对应表" (
     "意见指标关联ID" text PRIMARY KEY,
     "意见ID" text NOT NULL,
     "计算记录ID" text NOT NULL,
     UNIQUE ("意见ID", "计算记录ID")
   );


意见复盘表
""""""""""


记录粒度：对一项意见的一次效果分析。

引用关系：意见ID → analysis.意见与规划总表；计算记录ID → analysis.指标计算表。

.. sql-source-line: 3229

.. code-block:: sql

   CREATE TABLE analysis."意见复盘表" (
     "复盘ID" text PRIMARY KEY,
     "意见ID" text NOT NULL,
     "复盘日期" date NOT NULL,
     "期间开始" date NOT NULL,
     "期间结束" date NOT NULL,
     "实际效果" text NOT NULL,
     "复盘结论" text NOT NULL,
     "计算记录ID" text
   );


交付记录表
""""""""""


记录粒度：本部门发布的一版数据或文件交付。

引用关系：确认人ID → finance.人员档案表。

.. sql-source-line: 3248

.. code-block:: sql

   CREATE TABLE analysis."交付记录表" (
     "交付ID" text PRIMARY KEY,
     "交付名称" text NOT NULL,
     "交付版本" text NOT NULL,
     "期间开始" date,
     "期间结束" date,
     "数据截止时间" timestamptz NOT NULL,
     "交付时间" timestamptz NOT NULL,
     "文件路径" text,
     "待核事项" text,
     "确认人ID" text
   );


意见采纳表
""""""""""


记录粒度：本部门对一项分析建议的一次采纳决定。

引用关系：意见ID → analysis.意见与规划总表；负责人ID → finance.人员档案表。

.. sql-source-line: 3269

.. code-block:: sql

   CREATE TABLE analysis."意见采纳表" (
     "采纳记录ID" text PRIMARY KEY,
     "意见ID" text NOT NULL,
     "决定日期" date NOT NULL,
     "采纳结论" text NOT NULL,
     "目标" text,
     "负责人ID" text
   );


意见执行表
""""""""""


记录粒度：本部门对一次采纳决定的一次实际执行。

引用关系：采纳记录ID → analysis.意见采纳表；负责人ID → finance.人员档案表。

.. sql-source-line: 3286

.. code-block:: sql

   CREATE TABLE analysis."意见执行表" (
     "执行记录ID" text PRIMARY KEY,
     "采纳记录ID" text NOT NULL,
     "执行时间" timestamptz NOT NULL,
     "执行内容" text NOT NULL,
     "实际结果" text,
     "证据路径" text,
     "负责人ID" text
   );


整改处理表
""""""""""


记录粒度：本部门对一项整改要求的一次实际处理。

引用关系：整改事项ID → legal.整改跟踪表；处理人ID → finance.人员档案表。

.. sql-source-line: 3304

.. code-block:: sql

   CREATE TABLE analysis."整改处理表" (
     "整改处理记录ID" text PRIMARY KEY,
     "整改事项ID" text NOT NULL,
     "处理时间" timestamptz NOT NULL,
     "处理内容" text NOT NULL,
     "结果" text,
     "证据路径" text,
     "处理人ID" text
   );


交付明细表
""""""""""


记录粒度：本部门一次交付中引用的一条本部门记录。

每行只选一个来源；一份交付可含任意多行，不复制来源记录字段。

引用关系：交付ID → analysis.交付记录表；数学模型库引用 → analysis.数学模型库；数据引用登记表引用 → analysis.数据引用登记表；指标定义表引用 → analysis.指标定义表；指标计算表引用 → analysis.指标计算表；分析报告登记表引用 → analysis.分析报告登记表；报告模型对应表引用 → analysis.报告模型对应表；报告数据对应表引用 → analysis.报告数据对应表；报告指标对应表引用 → analysis.报告指标对应表；意见与规划总表引用 → analysis.意见与规划总表；意见指标对应表引用 → analysis.意见指标对应表；意见复盘表引用 → analysis.意见复盘表；意见采纳表引用 → analysis.意见采纳表；意见执行表引用 → analysis.意见执行表；整改处理表引用 → analysis.整改处理表。

.. sql-source-line: 3324

.. code-block:: sql

   CREATE TABLE analysis."交付明细表" (
     "交付明细ID" text PRIMARY KEY,
     "交付ID" text NOT NULL,
     "数学模型库引用" text,
     "数据引用登记表引用" text,
     "指标定义表引用" text,
     "指标计算表引用" text,
     "分析报告登记表引用" text,
     "报告模型对应表引用" text,
     "报告数据对应表引用" text,
     "报告指标对应表引用" text,
     "意见与规划总表引用" text,
     "意见指标对应表引用" text,
     "意见复盘表引用" text,
     "意见采纳表引用" text,
     "意见执行表引用" text,
     "整改处理表引用" text,
     CHECK (num_nonnulls("数学模型库引用", "数据引用登记表引用", "指标定义表引用", "指标计算表引用", "分析报告登记表引用", "报告模型对应表引用", "报告数据对应表引用", "报告指标对应表引用", "意见与规划总表引用", "意见指标对应表引用", "意见复盘表引用", "意见采纳表引用", "意见执行表引用", "整改处理表引用") = 1)
   );


数据集输入来源表
""""""""""""""""


记录粒度：一个数据集使用的某部门一版交付。

引用关系：数据集ID → analysis.数据引用登记表；finance交付ID → finance.交付记录表；legal交付ID → legal.交付记录表；production交付ID → production.交付记录表；rd交付ID → rd.交付记录表；sales交付ID → sales.交付记录表；analysis交付ID → analysis.交付记录表。

.. sql-source-line: 3352

.. code-block:: sql

   CREATE TABLE analysis."数据集输入来源表" (
     "输入来源ID" text PRIMARY KEY,
     "数据集ID" text NOT NULL,
     "接收时间" timestamptz NOT NULL,
     "接收说明" text,
     "finance交付ID" text,
     "legal交付ID" text,
     "production交付ID" text,
     "rd交付ID" text,
     "sales交付ID" text,
     "analysis交付ID" text,
     CHECK (num_nonnulls("finance交付ID", "legal交付ID", "production交付ID", "rd交付ID", "sales交付ID", "analysis交付ID") = 1)
   );


工作流和反馈分析
----------------


财务需要法务的主体ID：对应资金账户及资产所属公司主体。
财务需要销售的客户ID、销售合同ID、订单ID、销售订单行ID、售后事件ID：对应往来、销售业务、收入及退款依据。
财务需要生产的供应商ID、采购订单行ID、工单号、工时ID、库存事件ID、完工事件ID、报废事件ID、发货事件ID：对应采购往来、实际耗用、工时、产出及履约事实。
财务需要研发的项目ID、投入登记ID、工时ID：对应研发归属及实际投入。

法务需要销售的销售合同ID、订单ID及生产的采购合同ID、采购单ID等业务对象ID：对应合同审阅、履约及合规检查事项。
法务需要各部门的业务记录ID、整改处理记录ID：对应自查证据、整改执行及复核依据。

生产需要法务的主体ID、规则ID、审阅ID、整改事项ID：对应主体归属、适用要求、合同审阅及整改要求。
生产需要研发的PID、MID、规格ID、BOM登记ID、BOM明细ID、发布批次ID、研发事项ID：对应物品定义、制造依据及变更验证结论。
生产需要销售的销售合同ID、销售订单行ID、售后事件ID：对应履约数量、交期、收货信息及售后检验需求。
生产需要财务的分摊ID、用途核定ID：对应采购结算金额及资金用途核定结果。

研发需要销售的需求ID、售后事件ID：对应客户原话、使用场景及售后反馈。
研发需要生产的检验ID、工单号、工时ID：对应质量问题、实际制造及投入事实。
研发需要财务的费用ID、计价ID：对应已核定费用及工时金额。
研发需要法务的规则ID、整改事项ID：对应适用要求及整改要求。

销售需要研发的PID、规格ID、研发事项ID：对应产品定义、适用规格及需求处理结论。
销售需要生产的发货事件ID、检验ID、库存事件ID：对应实际发货、质量结果及退回入库。
销售需要财务的资金记录ID、分摊ID、票据ID：对应实际收退款、订单结算及开票结果。
销售需要法务的主体ID、审阅ID、规则ID、整改事项ID：对应签约主体、合同审阅及合规要求。

分析需要各部门的交付ID、业务记录ID：对应报告和指标的数据来源。
各部门需要分析的报告ID、指标ID、意见ID：对应分析结论、指标口径及建议。
分析需要责任部门的采纳记录ID、执行记录ID：对应建议采纳情况、实际执行及效果复盘。


数据集和交付物格式规范
----------------------


表：csv
文本：md
报告和副本：pdf
压缩包：zip


SQL关联关系与交付实现
------------------------


主要关系的数量约定
~~~~~~~~~~~~~~~~~~


.. list-table::
   :header-rows: 1
   :widths: auto

   * - 关系
     - 数量关系及落点
   * - 销售订单 → 订单行 → 发货
     - 1:N、1:N；每次发货只记一个订单行，组合产品另引用订单组合明细
   * - 销售合同 ↔ 订单
     - M:N；合同订单对应表
   * - 订单行 ↔ 生产工单
     - M:N；工单订单对应表，保存实际分配的数量
   * - 采购订单 → 采购行 → 到货 → 验收 → 库存事件
     - 各级1:N；分批实际分别记行
   * - 工单 → 领退料、工时、完工、报废
     - 分别1:N；各事件可再关联多条库存变动
   * - 产品 → 产品版本 → BOM → BOM明细
     - 各级1:N；相同物料可在不同装配位置重复使用
   * - 发布批次 ↔ 文件版本
     - M:N；发布文件明细表
   * - 资金 → 用途核定 → 结算分摊 → 业务
     - 资金可分摊给多个业务，业务可被多笔资金结算；按分摊行关联
   * - 发票 ↔ 订单行
     - M:N；发票分摊表
   * - 检验或需求 ↔ 研发事项
     - M:N；研发事项来源表，不双向强制提前填写结果ID
   * - 报告 ↔ 模型、数据集、指标计算
     - 分别M:N；各对应表每行一个引用
   * - 分析意见 → 责任部门采纳 → 执行
     - 1:N、1:N；实际结果留在责任部门，复盘留在分析
   * - 部门交付 → 交付明细 → 部门原始记录
     - 1:N；每条交付明细只选一个已定义来源外键


同一笔分摊、同一条工时或同一条库存事件，在多个查询入口出现仍是同一条主录。汇总查询应先分别聚合发货、资金、工时等明细再关联，避免直接连接多组一对多明细导致金额或数量倍增。


外键定义
~~~~~~~~


下面所有目标表均已在前文定义。外键默认即时检查；先创建实际存在的来源记录，再补充后续业务结果。主外键只保证对象存在，业务日期、物品、单位、币种及期间匹配另按后文规则核对。

.. sql-source-line: 3431

.. code-block:: sql

   ALTER TABLE finance."资金账户档案表" ADD FOREIGN KEY ("主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE finance."流水文件登记表" ADD FOREIGN KEY ("账户ID") REFERENCES finance."资金账户档案表" ("账户ID");
   ALTER TABLE finance."资金流水表" ADD FOREIGN KEY ("账户ID") REFERENCES finance."资金账户档案表" ("账户ID");
   ALTER TABLE finance."流水来源明细表" ADD FOREIGN KEY ("资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."流水来源明细表" ADD FOREIGN KEY ("流水文件ID") REFERENCES finance."流水文件登记表" ("流水文件ID");
   ALTER TABLE finance."账户期间余额表" ADD FOREIGN KEY ("账户ID") REFERENCES finance."资金账户档案表" ("账户ID");
   ALTER TABLE finance."账户期间余额表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."会计科目表" ADD FOREIGN KEY ("主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE finance."会计科目表" ADD FOREIGN KEY ("上级科目ID") REFERENCES finance."会计科目表" ("科目ID");
   ALTER TABLE finance."资金用途核定表" ADD FOREIGN KEY ("资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."资金用途核定表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."资金用途核定表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE finance."资金用途核定表" ADD FOREIGN KEY ("采购订单行ID") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE finance."资金用途核定表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE finance."资金用途核定表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE finance."资金用途核定表" ADD FOREIGN KEY ("售后事件ID") REFERENCES sales."售后事件表" ("售后事件ID");
   ALTER TABLE finance."资金用途核定表" ADD FOREIGN KEY ("费用ID") REFERENCES finance."费用归属表" ("费用ID");
   ALTER TABLE finance."结算分摊表" ADD FOREIGN KEY ("用途核定ID") REFERENCES finance."资金用途核定表" ("用途核定ID");
   ALTER TABLE finance."结算分摊表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE finance."结算分摊表" ADD FOREIGN KEY ("采购订单行ID") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE finance."结算分摊表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE finance."结算分摊表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE finance."结算分摊表" ADD FOREIGN KEY ("售后事件ID") REFERENCES sales."售后事件表" ("售后事件ID");
   ALTER TABLE finance."结算分摊表" ADD FOREIGN KEY ("费用ID") REFERENCES finance."费用归属表" ("费用ID");
   ALTER TABLE finance."内部划转对应表" ADD FOREIGN KEY ("转出资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."内部划转对应表" ADD FOREIGN KEY ("转入资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."重复记录对应表" ADD FOREIGN KEY ("原资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."重复记录对应表" ADD FOREIGN KEY ("重复资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."期初及结账核实表" ADD FOREIGN KEY ("科目ID") REFERENCES finance."会计科目表" ("科目ID");
   ALTER TABLE finance."期初及结账核实表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."往来未结明细表" ADD FOREIGN KEY ("客户ID") REFERENCES sales."客户档案表" ("客户ID");
   ALTER TABLE finance."往来未结明细表" ADD FOREIGN KEY ("供应商ID") REFERENCES production."供应商档案表" ("供应商ID");
   ALTER TABLE finance."往来未结明细表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE finance."往来未结明细表" ADD FOREIGN KEY ("采购订单行ID") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE finance."往来未结明细表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE finance."往来未结明细表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE finance."往来未结明细表" ADD FOREIGN KEY ("售后事件ID") REFERENCES sales."售后事件表" ("售后事件ID");
   ALTER TABLE finance."往来未结明细表" ADD FOREIGN KEY ("费用ID") REFERENCES finance."费用归属表" ("费用ID");
   ALTER TABLE finance."费用归属表" ADD FOREIGN KEY ("人员ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."费用归属表" ADD FOREIGN KEY ("供应商ID") REFERENCES production."供应商档案表" ("供应商ID");
   ALTER TABLE finance."费用归属表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE finance."费用归属表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE finance."费用归属表" ADD FOREIGN KEY ("资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."工时计价表" ADD FOREIGN KEY ("生产工时ID") REFERENCES production."生产工时表" ("工时ID");
   ALTER TABLE finance."工时计价表" ADD FOREIGN KEY ("研发工时ID") REFERENCES rd."研发工时表" ("工时ID");
   ALTER TABLE finance."工时计价表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."收入成本确认表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE finance."收入成本确认表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE finance."收入成本确认表" ADD FOREIGN KEY ("政策ID") REFERENCES finance."会计政策表" ("政策ID");
   ALTER TABLE finance."发票登记表" ADD FOREIGN KEY ("开票主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE finance."发票登记表" ADD FOREIGN KEY ("原票ID") REFERENCES finance."发票登记表" ("票据ID");
   ALTER TABLE finance."发票分摊表" ADD FOREIGN KEY ("票据ID") REFERENCES finance."发票登记表" ("票据ID");
   ALTER TABLE finance."发票分摊表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE finance."发票分摊表" ADD FOREIGN KEY ("采购订单行ID") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE finance."资产台账" ADD FOREIGN KEY ("主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE finance."资产台账" ADD FOREIGN KEY ("政策ID") REFERENCES finance."会计政策表" ("政策ID");
   ALTER TABLE finance."纳税申报记录表" ADD FOREIGN KEY ("主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE finance."税款缴退明细表" ADD FOREIGN KEY ("记录ID") REFERENCES finance."纳税申报记录表" ("记录ID");
   ALTER TABLE finance."税款缴退明细表" ADD FOREIGN KEY ("资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."账户核对表" ADD FOREIGN KEY ("余额记录ID") REFERENCES finance."账户期间余额表" ("余额记录ID");
   ALTER TABLE finance."会计凭证表" ADD FOREIGN KEY ("主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE finance."会计凭证表" ADD FOREIGN KEY ("政策ID") REFERENCES finance."会计政策表" ("政策ID");
   ALTER TABLE finance."会计凭证表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."会计分录表" ADD FOREIGN KEY ("凭证ID") REFERENCES finance."会计凭证表" ("凭证ID");
   ALTER TABLE finance."会计分录表" ADD FOREIGN KEY ("科目ID") REFERENCES finance."会计科目表" ("科目ID");
   ALTER TABLE finance."会计分录表" ADD FOREIGN KEY ("资金记录ID") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."会计分录表" ADD FOREIGN KEY ("确认ID") REFERENCES finance."收入成本确认表" ("确认ID");
   ALTER TABLE finance."会计分录表" ADD FOREIGN KEY ("费用ID") REFERENCES finance."费用归属表" ("费用ID");
   ALTER TABLE finance."会计分录表" ADD FOREIGN KEY ("计价ID") REFERENCES finance."工时计价表" ("计价ID");
   ALTER TABLE finance."会计分录表" ADD FOREIGN KEY ("核实ID") REFERENCES finance."期初及结账核实表" ("核实ID");
   ALTER TABLE finance."报表批次表" ADD FOREIGN KEY ("主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE finance."报表批次表" ADD FOREIGN KEY ("政策ID") REFERENCES finance."会计政策表" ("政策ID");
   ALTER TABLE finance."资产负债表" ADD FOREIGN KEY ("报表批次ID") REFERENCES finance."报表批次表" ("报表批次ID");
   ALTER TABLE finance."现金流量表" ADD FOREIGN KEY ("报表批次ID") REFERENCES finance."报表批次表" ("报表批次ID");
   ALTER TABLE finance."利润表" ADD FOREIGN KEY ("报表批次ID") REFERENCES finance."报表批次表" ("报表批次ID");
   ALTER TABLE finance."报表项目映射表" ADD FOREIGN KEY ("政策ID") REFERENCES finance."会计政策表" ("政策ID");
   ALTER TABLE finance."报表项目映射表" ADD FOREIGN KEY ("科目ID") REFERENCES finance."会计科目表" ("科目ID");
   ALTER TABLE finance."资产负债表来源明细表" ADD FOREIGN KEY ("结果行ID") REFERENCES finance."资产负债表" ("资产负债行ID");
   ALTER TABLE finance."资产负债表来源明细表" ADD FOREIGN KEY ("分录ID") REFERENCES finance."会计分录表" ("分录ID");
   ALTER TABLE finance."资产负债表来源明细表" ADD FOREIGN KEY ("核实ID") REFERENCES finance."期初及结账核实表" ("核实ID");
   ALTER TABLE finance."资产负债表来源明细表" ADD FOREIGN KEY ("项目映射ID") REFERENCES finance."报表项目映射表" ("项目映射ID");
   ALTER TABLE finance."现金流量表来源明细表" ADD FOREIGN KEY ("结果行ID") REFERENCES finance."现金流量表" ("现金流量行ID");
   ALTER TABLE finance."现金流量表来源明细表" ADD FOREIGN KEY ("分录ID") REFERENCES finance."会计分录表" ("分录ID");
   ALTER TABLE finance."现金流量表来源明细表" ADD FOREIGN KEY ("核实ID") REFERENCES finance."期初及结账核实表" ("核实ID");
   ALTER TABLE finance."现金流量表来源明细表" ADD FOREIGN KEY ("项目映射ID") REFERENCES finance."报表项目映射表" ("项目映射ID");
   ALTER TABLE finance."利润表来源明细表" ADD FOREIGN KEY ("结果行ID") REFERENCES finance."利润表" ("利润行ID");
   ALTER TABLE finance."利润表来源明细表" ADD FOREIGN KEY ("分录ID") REFERENCES finance."会计分录表" ("分录ID");
   ALTER TABLE finance."利润表来源明细表" ADD FOREIGN KEY ("核实ID") REFERENCES finance."期初及结账核实表" ("核实ID");
   ALTER TABLE finance."利润表来源明细表" ADD FOREIGN KEY ("项目映射ID") REFERENCES finance."报表项目映射表" ("项目映射ID");
   ALTER TABLE finance."交付记录表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."意见采纳表" ADD FOREIGN KEY ("意见ID") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE finance."意见采纳表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."意见执行表" ADD FOREIGN KEY ("采纳记录ID") REFERENCES finance."意见采纳表" ("采纳记录ID");
   ALTER TABLE finance."意见执行表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."整改处理表" ADD FOREIGN KEY ("整改事项ID") REFERENCES legal."整改跟踪表" ("整改事项ID");
   ALTER TABLE finance."整改处理表" ADD FOREIGN KEY ("处理人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("交付ID") REFERENCES finance."交付记录表" ("交付ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("人员档案表引用") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("资金账户档案表引用") REFERENCES finance."资金账户档案表" ("账户ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("流水文件登记表引用") REFERENCES finance."流水文件登记表" ("流水文件ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("资金流水表引用") REFERENCES finance."资金流水表" ("资金记录ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("流水来源明细表引用") REFERENCES finance."流水来源明细表" ("流水来源ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("账户期间余额表引用") REFERENCES finance."账户期间余额表" ("余额记录ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("会计政策表引用") REFERENCES finance."会计政策表" ("政策ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("会计科目表引用") REFERENCES finance."会计科目表" ("科目ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("资金用途核定表引用") REFERENCES finance."资金用途核定表" ("用途核定ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("结算分摊表引用") REFERENCES finance."结算分摊表" ("分摊ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("内部划转对应表引用") REFERENCES finance."内部划转对应表" ("划转对应ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("重复记录对应表引用") REFERENCES finance."重复记录对应表" ("重复对应ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("期初及结账核实表引用") REFERENCES finance."期初及结账核实表" ("核实ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("往来未结明细表引用") REFERENCES finance."往来未结明细表" ("未结记录ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("费用归属表引用") REFERENCES finance."费用归属表" ("费用ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("工时计价表引用") REFERENCES finance."工时计价表" ("计价ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("收入成本确认表引用") REFERENCES finance."收入成本确认表" ("确认ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("发票登记表引用") REFERENCES finance."发票登记表" ("票据ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("发票分摊表引用") REFERENCES finance."发票分摊表" ("发票分摊ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("资产台账引用") REFERENCES finance."资产台账" ("资产ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("纳税申报记录表引用") REFERENCES finance."纳税申报记录表" ("记录ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("税款缴退明细表引用") REFERENCES finance."税款缴退明细表" ("缴退ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("账户核对表引用") REFERENCES finance."账户核对表" ("账户核对ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("会计凭证表引用") REFERENCES finance."会计凭证表" ("凭证ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("会计分录表引用") REFERENCES finance."会计分录表" ("分录ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("报表批次表引用") REFERENCES finance."报表批次表" ("报表批次ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("资产负债表引用") REFERENCES finance."资产负债表" ("资产负债行ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("现金流量表引用") REFERENCES finance."现金流量表" ("现金流量行ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("利润表引用") REFERENCES finance."利润表" ("利润行ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("报表项目映射表引用") REFERENCES finance."报表项目映射表" ("项目映射ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("资产负债表来源明细表引用") REFERENCES finance."资产负债表来源明细表" ("资产负债来源ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("现金流量表来源明细表引用") REFERENCES finance."现金流量表来源明细表" ("现金流量来源ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("利润表来源明细表引用") REFERENCES finance."利润表来源明细表" ("利润来源ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("意见采纳表引用") REFERENCES finance."意见采纳表" ("采纳记录ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("意见执行表引用") REFERENCES finance."意见执行表" ("执行记录ID");
   ALTER TABLE finance."交付明细表" ADD FOREIGN KEY ("整改处理表引用") REFERENCES finance."整改处理表" ("整改处理记录ID");
   ALTER TABLE legal."适用规则表" ADD FOREIGN KEY ("法规ID") REFERENCES legal."法规登记表" ("法规ID");
   ALTER TABLE legal."法律文件登记表" ADD FOREIGN KEY ("销售合同ID") REFERENCES sales."销售合同表" ("销售合同ID");
   ALTER TABLE legal."法律文件登记表" ADD FOREIGN KEY ("采购合同ID") REFERENCES production."采购合同表" ("采购合同ID");
   ALTER TABLE legal."合同审阅表" ADD FOREIGN KEY ("销售合同ID") REFERENCES sales."销售合同表" ("销售合同ID");
   ALTER TABLE legal."合同审阅表" ADD FOREIGN KEY ("采购合同ID") REFERENCES production."采购合同表" ("采购合同ID");
   ALTER TABLE legal."合同审阅表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."履约提示表" ADD FOREIGN KEY ("审阅ID") REFERENCES legal."合同审阅表" ("审阅ID");
   ALTER TABLE legal."合规自查表" ADD FOREIGN KEY ("规则ID") REFERENCES legal."适用规则表" ("规则ID");
   ALTER TABLE legal."合规自查表" ADD FOREIGN KEY ("责任人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."证据对应表" ADD FOREIGN KEY ("自查ID") REFERENCES legal."合规自查表" ("自查ID");
   ALTER TABLE legal."证据对应表" ADD FOREIGN KEY ("提供人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."证据对应表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE legal."证据对应表" ADD FOREIGN KEY ("采购订单行ID") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE legal."证据对应表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE legal."证据对应表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE legal."证据对应表" ADD FOREIGN KEY ("售后事件ID") REFERENCES sales."售后事件表" ("售后事件ID");
   ALTER TABLE legal."证据对应表" ADD FOREIGN KEY ("费用ID") REFERENCES finance."费用归属表" ("费用ID");
   ALTER TABLE legal."整改跟踪表" ADD FOREIGN KEY ("自查ID") REFERENCES legal."合规自查表" ("自查ID");
   ALTER TABLE legal."整改跟踪表" ADD FOREIGN KEY ("责任人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."整改跟踪表" ADD FOREIGN KEY ("复核人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."交付记录表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."意见采纳表" ADD FOREIGN KEY ("意见ID") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE legal."意见采纳表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."意见执行表" ADD FOREIGN KEY ("采纳记录ID") REFERENCES legal."意见采纳表" ("采纳记录ID");
   ALTER TABLE legal."意见执行表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."整改处理表" ADD FOREIGN KEY ("整改事项ID") REFERENCES legal."整改跟踪表" ("整改事项ID");
   ALTER TABLE legal."整改处理表" ADD FOREIGN KEY ("处理人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("交付ID") REFERENCES legal."交付记录表" ("交付ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("公司主体档案表引用") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("法规登记表引用") REFERENCES legal."法规登记表" ("法规ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("适用规则表引用") REFERENCES legal."适用规则表" ("规则ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("法律文件登记表引用") REFERENCES legal."法律文件登记表" ("法律文件ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("合同审阅表引用") REFERENCES legal."合同审阅表" ("审阅ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("履约提示表引用") REFERENCES legal."履约提示表" ("提示ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("合规自查表引用") REFERENCES legal."合规自查表" ("自查ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("证据对应表引用") REFERENCES legal."证据对应表" ("证据关联ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("整改跟踪表引用") REFERENCES legal."整改跟踪表" ("整改事项ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("意见采纳表引用") REFERENCES legal."意见采纳表" ("采纳记录ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("意见执行表引用") REFERENCES legal."意见执行表" ("执行记录ID");
   ALTER TABLE legal."交付明细表" ADD FOREIGN KEY ("整改处理表引用") REFERENCES legal."整改处理表" ("整改处理记录ID");
   ALTER TABLE production."采购合同表" ADD FOREIGN KEY ("供应商ID") REFERENCES production."供应商档案表" ("供应商ID");
   ALTER TABLE production."采购订单表" ADD FOREIGN KEY ("采购合同ID") REFERENCES production."采购合同表" ("采购合同ID");
   ALTER TABLE production."采购订单表" ADD FOREIGN KEY ("供应商ID") REFERENCES production."供应商档案表" ("供应商ID");
   ALTER TABLE production."采购订单行表" ADD FOREIGN KEY ("采购单ID") REFERENCES production."采购订单表" ("采购单ID");
   ALTER TABLE production."采购订单行表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."采购订单行表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE production."采购订单行表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE production."保管方档案表" ADD FOREIGN KEY ("主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE production."仓库档案表" ADD FOREIGN KEY ("保管方ID") REFERENCES production."保管方档案表" ("保管方ID");
   ALTER TABLE production."仓库档案表" ADD FOREIGN KEY ("主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE production."库位档案表" ADD FOREIGN KEY ("仓库ID") REFERENCES production."仓库档案表" ("仓库ID");
   ALTER TABLE production."库存基准核定表" ADD FOREIGN KEY ("库位ID") REFERENCES production."库位档案表" ("库位ID");
   ALTER TABLE production."库存基准核定表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."库存基准核定表" ADD FOREIGN KEY ("所有权主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE production."库存基准核定表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."库存基准核定表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE production."库存基准核定表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE production."到货记录表" ADD FOREIGN KEY ("采购订单行ID") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE production."到货记录表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."验收记录表" ADD FOREIGN KEY ("到货ID") REFERENCES production."到货记录表" ("到货ID");
   ALTER TABLE production."验收记录表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."验收记录表" ADD FOREIGN KEY ("检验ID") REFERENCES production."质量检验表" ("检验ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("库位ID") REFERENCES production."库位档案表" ("库位ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("所有权主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("验收ID") REFERENCES production."验收记录表" ("验收ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("领退料事件ID") REFERENCES production."生产领退料表" ("领退料事件ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("完工事件ID") REFERENCES production."完工记录表" ("完工事件ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("报废事件ID") REFERENCES production."报废记录表" ("报废事件ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("发货事件ID") REFERENCES production."发货记录表" ("发货事件ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("物料事件ID") REFERENCES production."委外物料流转表" ("物料事件ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("售后事件ID") REFERENCES sales."售后事件表" ("售后事件ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE production."库存变动表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE production."工单草稿表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."生产工单表" ADD FOREIGN KEY ("草稿登记ID") REFERENCES production."工单草稿表" ("草稿登记ID");
   ALTER TABLE production."生产工单表" ADD FOREIGN KEY ("发布批次ID") REFERENCES rd."发布批次表" ("发布批次ID");
   ALTER TABLE production."生产工单表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."生产工单表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."工单订单对应表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE production."工单订单对应表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE production."工单订单对应表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."工单订单对应表" ADD FOREIGN KEY ("订单组合明细ID") REFERENCES sales."订单组合明细表" ("订单组合明细ID");
   ALTER TABLE production."生产领退料表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE production."生产领退料表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE production."生产领退料表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."生产工时表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE production."生产工时表" ADD FOREIGN KEY ("人员ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."生产工时表" ADD FOREIGN KEY ("设备ID") REFERENCES production."设备档案表" ("设备ID");
   ALTER TABLE production."生产工时表" ADD FOREIGN KEY ("产量单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."完工记录表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE production."完工记录表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."完工记录表" ADD FOREIGN KEY ("检验ID") REFERENCES production."质量检验表" ("检验ID");
   ALTER TABLE production."报废记录表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE production."报废记录表" ADD FOREIGN KEY ("完工事件ID") REFERENCES production."完工记录表" ("完工事件ID");
   ALTER TABLE production."报废记录表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."报废记录表" ADD FOREIGN KEY ("检验ID") REFERENCES production."质量检验表" ("检验ID");
   ALTER TABLE production."报废记录表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE production."报废记录表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE production."质量检验表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE production."质量检验表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE production."质量检验表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."质量检验表" ADD FOREIGN KEY ("售后事件ID") REFERENCES sales."售后事件表" ("售后事件ID");
   ALTER TABLE production."质量检验表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE production."质量检验表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE production."委外物料流转表" ADD FOREIGN KEY ("采购订单行ID") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE production."委外物料流转表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE production."委外物料流转表" ADD FOREIGN KEY ("来源保管方ID") REFERENCES production."保管方档案表" ("保管方ID");
   ALTER TABLE production."委外物料流转表" ADD FOREIGN KEY ("去向保管方ID") REFERENCES production."保管方档案表" ("保管方ID");
   ALTER TABLE production."委外物料流转表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."委外物料流转表" ADD FOREIGN KEY ("工单号") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE production."采购归属对应表" ADD FOREIGN KEY ("采购订单行ID") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE production."采购归属对应表" ADD FOREIGN KEY ("分摊ID") REFERENCES finance."结算分摊表" ("分摊ID");
   ALTER TABLE production."采购归属对应表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."发货记录表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE production."发货记录表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."发货记录表" ADD FOREIGN KEY ("检验ID") REFERENCES production."质量检验表" ("检验ID");
   ALTER TABLE production."发货记录表" ADD FOREIGN KEY ("订单组合明细ID") REFERENCES sales."订单组合明细表" ("订单组合明细ID");
   ALTER TABLE production."库存盘点表" ADD FOREIGN KEY ("库位ID") REFERENCES production."库位档案表" ("库位ID");
   ALTER TABLE production."库存盘点表" ADD FOREIGN KEY ("所有权主体ID") REFERENCES legal."公司主体档案表" ("主体ID");
   ALTER TABLE production."库存盘点表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE production."库存盘点表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."库存盘点表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE production."库存盘点表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE production."库存余额与差异表" ADD FOREIGN KEY ("基准ID") REFERENCES production."库存基准核定表" ("基准ID");
   ALTER TABLE production."库存余额与差异表" ADD FOREIGN KEY ("盘点ID") REFERENCES production."库存盘点表" ("盘点ID");
   ALTER TABLE production."库存结存来源明细表" ADD FOREIGN KEY ("库存结存ID") REFERENCES production."库存余额与差异表" ("库存结存ID");
   ALTER TABLE production."库存结存来源明细表" ADD FOREIGN KEY ("库存事件ID") REFERENCES production."库存变动表" ("库存事件ID");
   ALTER TABLE production."库存结存来源明细表" ADD FOREIGN KEY ("换算ID") REFERENCES rd."单位换算表" ("换算ID");
   ALTER TABLE production."交付记录表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."意见采纳表" ADD FOREIGN KEY ("意见ID") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE production."意见采纳表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."意见执行表" ADD FOREIGN KEY ("采纳记录ID") REFERENCES production."意见采纳表" ("采纳记录ID");
   ALTER TABLE production."意见执行表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."整改处理表" ADD FOREIGN KEY ("整改事项ID") REFERENCES legal."整改跟踪表" ("整改事项ID");
   ALTER TABLE production."整改处理表" ADD FOREIGN KEY ("处理人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("交付ID") REFERENCES production."交付记录表" ("交付ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("设备档案表引用") REFERENCES production."设备档案表" ("设备ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("供应商档案表引用") REFERENCES production."供应商档案表" ("供应商ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("采购合同表引用") REFERENCES production."采购合同表" ("采购合同ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("采购订单表引用") REFERENCES production."采购订单表" ("采购单ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("采购订单行表引用") REFERENCES production."采购订单行表" ("采购订单行ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("保管方档案表引用") REFERENCES production."保管方档案表" ("保管方ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("仓库档案表引用") REFERENCES production."仓库档案表" ("仓库ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("库位档案表引用") REFERENCES production."库位档案表" ("库位ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("库存基准核定表引用") REFERENCES production."库存基准核定表" ("基准ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("到货记录表引用") REFERENCES production."到货记录表" ("到货ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("验收记录表引用") REFERENCES production."验收记录表" ("验收ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("库存变动表引用") REFERENCES production."库存变动表" ("库存事件ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("工单草稿表引用") REFERENCES production."工单草稿表" ("草稿登记ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("生产工单表引用") REFERENCES production."生产工单表" ("工单号");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("工单订单对应表引用") REFERENCES production."工单订单对应表" ("工单订单关联ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("生产领退料表引用") REFERENCES production."生产领退料表" ("领退料事件ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("生产工时表引用") REFERENCES production."生产工时表" ("工时ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("完工记录表引用") REFERENCES production."完工记录表" ("完工事件ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("报废记录表引用") REFERENCES production."报废记录表" ("报废事件ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("质量检验表引用") REFERENCES production."质量检验表" ("检验ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("委外物料流转表引用") REFERENCES production."委外物料流转表" ("物料事件ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("采购归属对应表引用") REFERENCES production."采购归属对应表" ("采购归属ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("发货记录表引用") REFERENCES production."发货记录表" ("发货事件ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("库存盘点表引用") REFERENCES production."库存盘点表" ("盘点ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("库存余额与差异表引用") REFERENCES production."库存余额与差异表" ("库存结存ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("库存结存来源明细表引用") REFERENCES production."库存结存来源明细表" ("结存来源ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("意见采纳表引用") REFERENCES production."意见采纳表" ("采纳记录ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("意见执行表引用") REFERENCES production."意见执行表" ("执行记录ID");
   ALTER TABLE production."交付明细表" ADD FOREIGN KEY ("整改处理表引用") REFERENCES production."整改处理表" ("整改处理记录ID");
   ALTER TABLE rd."产品主数据表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE rd."物料主数据表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE rd."项目登记表" ADD FOREIGN KEY ("草稿登记ID") REFERENCES rd."项目草稿表" ("草稿登记ID");
   ALTER TABLE rd."项目登记表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."产品版本表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE rd."产品版本表" ADD FOREIGN KEY ("PID") REFERENCES rd."产品主数据表" ("PID");
   ALTER TABLE rd."物料版本表" ADD FOREIGN KEY ("MID") REFERENCES rd."物料主数据表" ("MID");
   ALTER TABLE rd."单位换算表" ADD FOREIGN KEY ("来源单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE rd."单位换算表" ADD FOREIGN KEY ("目标单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE rd."单位换算表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE rd."单位换算表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE rd."项目文件登记表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE rd."项目文件登记表" ADD FOREIGN KEY ("PID") REFERENCES rd."产品主数据表" ("PID");
   ALTER TABLE rd."项目文件登记表" ADD FOREIGN KEY ("批准人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."BOM登记表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE rd."BOM明细表" ADD FOREIGN KEY ("BOM登记ID") REFERENCES rd."BOM登记表" ("BOM登记ID");
   ALTER TABLE rd."BOM明细表" ADD FOREIGN KEY ("物料版本ID") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE rd."BOM明细表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE rd."BOM明细表" ADD FOREIGN KEY ("来源文件ID") REFERENCES rd."项目文件登记表" ("文件ID");
   ALTER TABLE rd."设计变更与验证表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE rd."设计变更与验证表" ADD FOREIGN KEY ("PID") REFERENCES rd."产品主数据表" ("PID");
   ALTER TABLE rd."设计变更与验证表" ADD FOREIGN KEY ("原产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE rd."设计变更与验证表" ADD FOREIGN KEY ("新产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE rd."设计变更与验证表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."研发事项来源表" ADD FOREIGN KEY ("研发事项ID") REFERENCES rd."设计变更与验证表" ("研发事项ID");
   ALTER TABLE rd."研发事项来源表" ADD FOREIGN KEY ("检验ID") REFERENCES production."质量检验表" ("检验ID");
   ALTER TABLE rd."研发事项来源表" ADD FOREIGN KEY ("需求ID") REFERENCES sales."客户需求表" ("需求ID");
   ALTER TABLE rd."研发事项来源表" ADD FOREIGN KEY ("售后事件ID") REFERENCES sales."售后事件表" ("售后事件ID");
   ALTER TABLE rd."产品规格表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE rd."产品规格表" ADD FOREIGN KEY ("批准人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."研发工时表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE rd."研发工时表" ADD FOREIGN KEY ("人员ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."研发投入归属表" ADD FOREIGN KEY ("项目ID") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE rd."研发投入归属表" ADD FOREIGN KEY ("费用ID") REFERENCES finance."费用归属表" ("费用ID");
   ALTER TABLE rd."研发投入归属表" ADD FOREIGN KEY ("计价ID") REFERENCES finance."工时计价表" ("计价ID");
   ALTER TABLE rd."研发投入归属表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."发布批次表" ADD FOREIGN KEY ("BOM登记ID") REFERENCES rd."BOM登记表" ("BOM登记ID");
   ALTER TABLE rd."发布批次表" ADD FOREIGN KEY ("批准人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."发布文件明细表" ADD FOREIGN KEY ("发布批次ID") REFERENCES rd."发布批次表" ("发布批次ID");
   ALTER TABLE rd."发布文件明细表" ADD FOREIGN KEY ("文件ID") REFERENCES rd."项目文件登记表" ("文件ID");
   ALTER TABLE rd."交付记录表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."意见采纳表" ADD FOREIGN KEY ("意见ID") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE rd."意见采纳表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."意见执行表" ADD FOREIGN KEY ("采纳记录ID") REFERENCES rd."意见采纳表" ("采纳记录ID");
   ALTER TABLE rd."意见执行表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."整改处理表" ADD FOREIGN KEY ("整改事项ID") REFERENCES legal."整改跟踪表" ("整改事项ID");
   ALTER TABLE rd."整改处理表" ADD FOREIGN KEY ("处理人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("交付ID") REFERENCES rd."交付记录表" ("交付ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("计量单位表引用") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("产品主数据表引用") REFERENCES rd."产品主数据表" ("PID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("物料主数据表引用") REFERENCES rd."物料主数据表" ("MID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("项目草稿表引用") REFERENCES rd."项目草稿表" ("草稿登记ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("项目登记表引用") REFERENCES rd."项目登记表" ("项目ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("产品版本表引用") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("物料版本表引用") REFERENCES rd."物料版本表" ("物料版本ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("单位换算表引用") REFERENCES rd."单位换算表" ("换算ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("项目文件登记表引用") REFERENCES rd."项目文件登记表" ("文件ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("BOM登记表引用") REFERENCES rd."BOM登记表" ("BOM登记ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("BOM明细表引用") REFERENCES rd."BOM明细表" ("BOM明细ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("设计变更与验证表引用") REFERENCES rd."设计变更与验证表" ("研发事项ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("研发事项来源表引用") REFERENCES rd."研发事项来源表" ("来源关联ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("产品规格表引用") REFERENCES rd."产品规格表" ("规格ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("研发工时表引用") REFERENCES rd."研发工时表" ("工时ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("研发投入归属表引用") REFERENCES rd."研发投入归属表" ("投入登记ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("发布批次表引用") REFERENCES rd."发布批次表" ("发布批次ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("发布文件明细表引用") REFERENCES rd."发布文件明细表" ("发布文件明细ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("意见采纳表引用") REFERENCES rd."意见采纳表" ("采纳记录ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("意见执行表引用") REFERENCES rd."意见执行表" ("执行记录ID");
   ALTER TABLE rd."交付明细表" ADD FOREIGN KEY ("整改处理表引用") REFERENCES rd."整改处理表" ("整改处理记录ID");
   ALTER TABLE sales."平台文件登记表" ADD FOREIGN KEY ("渠道ID") REFERENCES sales."渠道档案表" ("渠道ID");
   ALTER TABLE sales."销售订单登记表" ADD FOREIGN KEY ("渠道ID") REFERENCES sales."渠道档案表" ("渠道ID");
   ALTER TABLE sales."销售订单登记表" ADD FOREIGN KEY ("客户ID") REFERENCES sales."客户档案表" ("客户ID");
   ALTER TABLE sales."订单导出快照表" ADD FOREIGN KEY ("订单ID") REFERENCES sales."销售订单登记表" ("订单ID");
   ALTER TABLE sales."订单导出快照表" ADD FOREIGN KEY ("平台文件ID") REFERENCES sales."平台文件登记表" ("平台文件ID");
   ALTER TABLE sales."销售合同表" ADD FOREIGN KEY ("客户ID") REFERENCES sales."客户档案表" ("客户ID");
   ALTER TABLE sales."合同订单对应表" ADD FOREIGN KEY ("销售合同ID") REFERENCES sales."销售合同表" ("销售合同ID");
   ALTER TABLE sales."合同订单对应表" ADD FOREIGN KEY ("订单ID") REFERENCES sales."销售订单登记表" ("订单ID");
   ALTER TABLE sales."销售动作表" ADD FOREIGN KEY ("客户ID") REFERENCES sales."客户档案表" ("客户ID");
   ALTER TABLE sales."销售动作表" ADD FOREIGN KEY ("订单ID") REFERENCES sales."销售订单登记表" ("订单ID");
   ALTER TABLE sales."销售动作表" ADD FOREIGN KEY ("销售合同ID") REFERENCES sales."销售合同表" ("销售合同ID");
   ALTER TABLE sales."销售订单行表" ADD FOREIGN KEY ("订单ID") REFERENCES sales."销售订单登记表" ("订单ID");
   ALTER TABLE sales."销售订单行表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE sales."销售订单行表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE sales."销售订单行表" ADD FOREIGN KEY ("来源订单快照ID") REFERENCES sales."订单导出快照表" ("订单快照ID");
   ALTER TABLE sales."组合商品明细表" ADD FOREIGN KEY ("组合商品ID") REFERENCES sales."组合商品表" ("组合商品ID");
   ALTER TABLE sales."组合商品明细表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE sales."组合商品明细表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE sales."订单组合明细表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE sales."订单组合明细表" ADD FOREIGN KEY ("组合明细ID") REFERENCES sales."组合商品明细表" ("组合明细ID");
   ALTER TABLE sales."商品对应表" ADD FOREIGN KEY ("渠道ID") REFERENCES sales."渠道档案表" ("渠道ID");
   ALTER TABLE sales."商品对应表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE sales."商品对应表" ADD FOREIGN KEY ("组合商品ID") REFERENCES sales."组合商品表" ("组合商品ID");
   ALTER TABLE sales."商品对应表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE sales."售后事件表" ADD FOREIGN KEY ("销售订单行ID") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE sales."售后事件表" ADD FOREIGN KEY ("单位ID") REFERENCES rd."计量单位表" ("单位ID");
   ALTER TABLE sales."售后事件表" ADD FOREIGN KEY ("退回仓库ID") REFERENCES production."仓库档案表" ("仓库ID");
   ALTER TABLE sales."客户需求表" ADD FOREIGN KEY ("订单ID") REFERENCES sales."销售订单登记表" ("订单ID");
   ALTER TABLE sales."客户需求表" ADD FOREIGN KEY ("产品版本ID") REFERENCES rd."产品版本表" ("产品版本ID");
   ALTER TABLE sales."客户需求表" ADD FOREIGN KEY ("客户ID") REFERENCES sales."客户档案表" ("客户ID");
   ALTER TABLE sales."销售期间覆盖表" ADD FOREIGN KEY ("平台文件ID") REFERENCES sales."平台文件登记表" ("平台文件ID");
   ALTER TABLE sales."销售期间覆盖表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE sales."客户分类统计批次表" ADD FOREIGN KEY ("来源交付ID") REFERENCES sales."交付记录表" ("交付ID");
   ALTER TABLE sales."客户分类统计结果表" ADD FOREIGN KEY ("分类统计ID") REFERENCES sales."客户分类统计批次表" ("分类统计ID");
   ALTER TABLE sales."交付记录表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE sales."意见采纳表" ADD FOREIGN KEY ("意见ID") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE sales."意见采纳表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE sales."意见执行表" ADD FOREIGN KEY ("采纳记录ID") REFERENCES sales."意见采纳表" ("采纳记录ID");
   ALTER TABLE sales."意见执行表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE sales."整改处理表" ADD FOREIGN KEY ("整改事项ID") REFERENCES legal."整改跟踪表" ("整改事项ID");
   ALTER TABLE sales."整改处理表" ADD FOREIGN KEY ("处理人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("交付ID") REFERENCES sales."交付记录表" ("交付ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("渠道档案表引用") REFERENCES sales."渠道档案表" ("渠道ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("客户档案表引用") REFERENCES sales."客户档案表" ("客户ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("平台文件登记表引用") REFERENCES sales."平台文件登记表" ("平台文件ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("销售订单登记表引用") REFERENCES sales."销售订单登记表" ("订单ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("订单导出快照表引用") REFERENCES sales."订单导出快照表" ("订单快照ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("销售合同表引用") REFERENCES sales."销售合同表" ("销售合同ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("合同订单对应表引用") REFERENCES sales."合同订单对应表" ("合同订单关联ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("销售动作表引用") REFERENCES sales."销售动作表" ("销售动作ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("销售订单行表引用") REFERENCES sales."销售订单行表" ("销售订单行ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("组合商品表引用") REFERENCES sales."组合商品表" ("组合商品ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("组合商品明细表引用") REFERENCES sales."组合商品明细表" ("组合明细ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("订单组合明细表引用") REFERENCES sales."订单组合明细表" ("订单组合明细ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("商品对应表引用") REFERENCES sales."商品对应表" ("映射登记ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("售后事件表引用") REFERENCES sales."售后事件表" ("售后事件ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("客户需求表引用") REFERENCES sales."客户需求表" ("需求ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("销售期间覆盖表引用") REFERENCES sales."销售期间覆盖表" ("覆盖记录ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("客户分类统计批次表引用") REFERENCES sales."客户分类统计批次表" ("分类统计ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("客户分类统计结果表引用") REFERENCES sales."客户分类统计结果表" ("分类结果ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("意见采纳表引用") REFERENCES sales."意见采纳表" ("采纳记录ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("意见执行表引用") REFERENCES sales."意见执行表" ("执行记录ID");
   ALTER TABLE sales."交付明细表" ADD FOREIGN KEY ("整改处理表引用") REFERENCES sales."整改处理表" ("整改处理记录ID");
   ALTER TABLE analysis."数学模型库" ADD FOREIGN KEY ("维护人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE analysis."指标计算表" ADD FOREIGN KEY ("指标ID") REFERENCES analysis."指标定义表" ("指标ID");
   ALTER TABLE analysis."指标计算表" ADD FOREIGN KEY ("数据集ID") REFERENCES analysis."数据引用登记表" ("数据集ID");
   ALTER TABLE analysis."分析报告登记表" ADD FOREIGN KEY ("复核人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE analysis."报告模型对应表" ADD FOREIGN KEY ("报告ID") REFERENCES analysis."分析报告登记表" ("报告ID");
   ALTER TABLE analysis."报告模型对应表" ADD FOREIGN KEY ("模型ID") REFERENCES analysis."数学模型库" ("模型ID");
   ALTER TABLE analysis."报告数据对应表" ADD FOREIGN KEY ("报告ID") REFERENCES analysis."分析报告登记表" ("报告ID");
   ALTER TABLE analysis."报告数据对应表" ADD FOREIGN KEY ("数据集ID") REFERENCES analysis."数据引用登记表" ("数据集ID");
   ALTER TABLE analysis."报告指标对应表" ADD FOREIGN KEY ("报告ID") REFERENCES analysis."分析报告登记表" ("报告ID");
   ALTER TABLE analysis."报告指标对应表" ADD FOREIGN KEY ("计算记录ID") REFERENCES analysis."指标计算表" ("计算记录ID");
   ALTER TABLE analysis."意见与规划总表" ADD FOREIGN KEY ("报告ID") REFERENCES analysis."分析报告登记表" ("报告ID");
   ALTER TABLE analysis."意见指标对应表" ADD FOREIGN KEY ("意见ID") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE analysis."意见指标对应表" ADD FOREIGN KEY ("计算记录ID") REFERENCES analysis."指标计算表" ("计算记录ID");
   ALTER TABLE analysis."意见复盘表" ADD FOREIGN KEY ("意见ID") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE analysis."意见复盘表" ADD FOREIGN KEY ("计算记录ID") REFERENCES analysis."指标计算表" ("计算记录ID");
   ALTER TABLE analysis."交付记录表" ADD FOREIGN KEY ("确认人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE analysis."意见采纳表" ADD FOREIGN KEY ("意见ID") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE analysis."意见采纳表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE analysis."意见执行表" ADD FOREIGN KEY ("采纳记录ID") REFERENCES analysis."意见采纳表" ("采纳记录ID");
   ALTER TABLE analysis."意见执行表" ADD FOREIGN KEY ("负责人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE analysis."整改处理表" ADD FOREIGN KEY ("整改事项ID") REFERENCES legal."整改跟踪表" ("整改事项ID");
   ALTER TABLE analysis."整改处理表" ADD FOREIGN KEY ("处理人ID") REFERENCES finance."人员档案表" ("人员ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("交付ID") REFERENCES analysis."交付记录表" ("交付ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("数学模型库引用") REFERENCES analysis."数学模型库" ("模型ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("数据引用登记表引用") REFERENCES analysis."数据引用登记表" ("数据集ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("指标定义表引用") REFERENCES analysis."指标定义表" ("指标ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("指标计算表引用") REFERENCES analysis."指标计算表" ("计算记录ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("分析报告登记表引用") REFERENCES analysis."分析报告登记表" ("报告ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("报告模型对应表引用") REFERENCES analysis."报告模型对应表" ("报告模型关联ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("报告数据对应表引用") REFERENCES analysis."报告数据对应表" ("报告数据关联ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("报告指标对应表引用") REFERENCES analysis."报告指标对应表" ("报告指标关联ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("意见与规划总表引用") REFERENCES analysis."意见与规划总表" ("意见ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("意见指标对应表引用") REFERENCES analysis."意见指标对应表" ("意见指标关联ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("意见复盘表引用") REFERENCES analysis."意见复盘表" ("复盘ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("意见采纳表引用") REFERENCES analysis."意见采纳表" ("采纳记录ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("意见执行表引用") REFERENCES analysis."意见执行表" ("执行记录ID");
   ALTER TABLE analysis."交付明细表" ADD FOREIGN KEY ("整改处理表引用") REFERENCES analysis."整改处理表" ("整改处理记录ID");
   ALTER TABLE analysis."数据集输入来源表" ADD FOREIGN KEY ("数据集ID") REFERENCES analysis."数据引用登记表" ("数据集ID");
   ALTER TABLE analysis."数据集输入来源表" ADD FOREIGN KEY ("finance交付ID") REFERENCES finance."交付记录表" ("交付ID");
   ALTER TABLE analysis."数据集输入来源表" ADD FOREIGN KEY ("legal交付ID") REFERENCES legal."交付记录表" ("交付ID");
   ALTER TABLE analysis."数据集输入来源表" ADD FOREIGN KEY ("production交付ID") REFERENCES production."交付记录表" ("交付ID");
   ALTER TABLE analysis."数据集输入来源表" ADD FOREIGN KEY ("rd交付ID") REFERENCES rd."交付记录表" ("交付ID");
   ALTER TABLE analysis."数据集输入来源表" ADD FOREIGN KEY ("sales交付ID") REFERENCES sales."交付记录表" ("交付ID");
   ALTER TABLE analysis."数据集输入来源表" ADD FOREIGN KEY ("analysis交付ID") REFERENCES analysis."交付记录表" ("交付ID");


汇总和文件交付的字段补齐
~~~~~~~~~~~~~~~~~~~~~~~~


库存余额与差异表为指定截止日期的查询结果。每行粒度是“所选基准＋物品版本＋库位＋批次＋所有权主体＋目标单位”；先选择该维度适用的唯一基准，累计基准日期之后至截止时间的库存变化。基准数量按基准日结束时点定义；事件使用业务所属主体约定时区判定日期。期末数量＝基准数量＋同维度已确认净变动；盘点差异＝同一时点实盘数量－账面数量。跨单位先按生效换算统一，缺少基准或换算时结果为空并说明原因。

客户分类统计每行粒度为“分类统计ID＋行业分类＋地区分类＋币种”；字段为客户数、订单数、已核定金额、未分类客户数。客户数按客户ID去重，订单数按订单ID去重，金额按选定口径独立汇总后关联；缺失分类保留为空。客户分类统计结果表已定义分类结果ID及统计维度的组合唯一约束。统计来源为批次绑定的销售交付，不从当前档案变化直接覆盖已发布统计；跨币种客户数不能直接相加为去重客户总数。

三张财务报表已定义批次、行级快照、项目映射及行级来源明细表。每行的来源分录或期初核定为多对多关系，逐行关联来源ID和归集金额，不把多个来源ID放入文本字段。生成规则由会计政策和报表项目映射确定，不在本版擅自指定具体税务、成本或报表归集算法。

PDF、MD及ZIP仍保存为文件；数据库保存文件登记、路径、版本、SHA256以及发布或交付关联。项目发布包由发布批次和发布文件明细查询生成；法务主体资料由主体资料路径交付；分析PDF对应报告ID；财务说明对应报表批次或财务交付ID。文件内容不重复拆成其他部门的业务主录。


跨记录业务核对
~~~~~~~~~~~~~~


以下是本版结构需要配套的业务核对，不属于单行CHECK能完整表达的内容。保存、确认或发布时，在同一事务中核对有关记录；不能仅以“外键存在”判断业务已核定。

#. 资金核对：同笔资金已确认用途及分摊分别核对整笔金额；内部划转和重复记录按核定状态处理，不重复累计。金额的币种沿资金账户查询，其他业务币种必须相符或另登记明确的汇兑依据。
#. 发票核对：分摊金额与分摊税额分别核对整张发票；红字处理按原票和业务性质确认。
#. 数量核对：累计到货、验收、入库、领退料、发货分别按各自事件口径核对，保管移交不直接认定耗用；组合商品发货需核对组合明细，普通发货核对订单行版本。工单订单对应数量需与工单产品及订单履约品一致。
#. 版本核对：工单通过发布批次取得固定BOM版本；发布文件应属于对应项目及适用产品，旧发布不被新版本覆盖。物料版本及产品版本引用只表达身份，日期适用性仍需业务核对。
#. 工时与投入：计价工时累计不得重复使用同一实际工时；归属比例按同一费用或计价来源核对总额。研发归属不重复改变原计价金额。
#. 凭证核对：过账前按主体、币种及期间核对凭证借贷合计，核对科目属于该主体；报表从已过账分录及已核定期初生成。收入、税额、成本的确认依据仍由财务决定。
#. 交付核对：交付明细引用已确认的来源；发布交付后，引用的版本结果应保持对应时点含义，需要修订时生成新交付并明确来源版本。交付引用本身不会自动冻结可变字段。


结构校验说明
~~~~~~~~~~~~


本版SQL用于表达数据结构、关系和查询接口。已通过642条PostgreSQL语句的语法解析，核对146张表的单列主键与475个外键目标，并完成15个视图的字段引用检查。未连接PostgreSQL业务数据库，未导入真实业务数据；语法与引用检查不等同于真实数据库运行验证。跨行核对、报表归集、统计生成和文件打包仍需相应业务实现，不以结构定义代替已完成的应用功能。

SQL语法参考：`PostgreSQL约束 <https://www.postgresql.org/docs/current/ddl-constraints.html>`__、`schema <https://www.postgresql.org/docs/current/ddl-schemas.html>`__、`精确数值类型 <https://www.postgresql.org/docs/current/datatype-numeric.html>`__。
