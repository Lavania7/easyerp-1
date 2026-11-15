-- Generated from readme.md. Run bin/build_schema.py to regenerate.
-- readme.md:105
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

-- readme.md:121
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

-- readme.md:141
CREATE TABLE finance."流水文件登记表" (
  "流水文件ID" text PRIMARY KEY,
  "账户ID" text NOT NULL,
  "导出时间" timestamptz NOT NULL,
  "覆盖开始日期" date,
  "覆盖结束日期" date,
  "文件路径" text NOT NULL,
  "文件校验值" text NOT NULL
);

-- readme.md:159
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

-- readme.md:181
CREATE TABLE finance."流水来源明细表" (
  "流水来源ID" text PRIMARY KEY,
  "资金记录ID" text NOT NULL,
  "流水文件ID" text NOT NULL,
  "来源行号" integer NOT NULL,
  UNIQUE ("流水文件ID", "来源行号")
);

-- readme.md:197
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

-- readme.md:217
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

-- readme.md:238
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

-- readme.md:259
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

-- readme.md:290
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

-- readme.md:317
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

-- readme.md:342
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

-- readme.md:364
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

-- readme.md:390
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

-- readme.md:422
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

-- readme.md:452
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

-- readme.md:479
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

-- readme.md:506
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

-- readme.md:528
CREATE TABLE finance."发票分摊表" (
  "发票分摊ID" text PRIMARY KEY,
  "票据ID" text NOT NULL,
  "销售订单行ID" text,
  "采购订单行ID" text,
  "分摊金额" numeric(20,4) NOT NULL,
  "分摊税额" numeric(20,4) NOT NULL,
  CHECK (num_nonnulls("销售订单行ID", "采购订单行ID") = 1)
);

-- readme.md:548
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

-- readme.md:573
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

-- readme.md:597
CREATE TABLE finance."税款缴退明细表" (
  "缴退ID" text PRIMARY KEY,
  "记录ID" text NOT NULL,
  "资金记录ID" text NOT NULL,
  "缴退日期" date NOT NULL,
  "缴退类型" text NOT NULL,
  "缴退金额" numeric(20,4) NOT NULL,
  "回执路径" text
);

-- readme.md:617
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

-- readme.md:638
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

-- readme.md:660
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

-- readme.md:686
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

-- readme.md:711
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

-- readme.md:732
CREATE TABLE finance."现金流量表" (
  "现金流量行ID" text PRIMARY KEY,
  "报表批次ID" text NOT NULL,
  "项目代码" text NOT NULL,
  "项目名称" text NOT NULL,
  "显示顺序" integer NOT NULL,
  "本期金额" numeric(20,4),
  UNIQUE ("报表批次ID", "项目代码")
);

-- readme.md:752
CREATE TABLE finance."利润表" (
  "利润行ID" text PRIMARY KEY,
  "报表批次ID" text NOT NULL,
  "项目代码" text NOT NULL,
  "项目名称" text NOT NULL,
  "显示顺序" integer NOT NULL,
  "本期金额" numeric(20,4),
  UNIQUE ("报表批次ID", "项目代码")
);

-- readme.md:770
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

-- readme.md:791
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

-- readme.md:810
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

-- readme.md:829
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

-- readme.md:848
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

-- readme.md:869
CREATE TABLE finance."意见采纳表" (
  "采纳记录ID" text PRIMARY KEY,
  "意见ID" text NOT NULL,
  "决定日期" date NOT NULL,
  "采纳结论" text NOT NULL,
  "目标" text,
  "负责人ID" text
);

-- readme.md:886
CREATE TABLE finance."意见执行表" (
  "执行记录ID" text PRIMARY KEY,
  "采纳记录ID" text NOT NULL,
  "执行时间" timestamptz NOT NULL,
  "执行内容" text NOT NULL,
  "实际结果" text,
  "证据路径" text,
  "负责人ID" text
);

-- readme.md:904
CREATE TABLE finance."整改处理表" (
  "整改处理记录ID" text PRIMARY KEY,
  "整改事项ID" text NOT NULL,
  "处理时间" timestamptz NOT NULL,
  "处理内容" text NOT NULL,
  "结果" text,
  "证据路径" text,
  "处理人ID" text
);

-- readme.md:924
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

-- readme.md:997
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

-- readme.md:1015
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

-- readme.md:1036
CREATE TABLE legal."适用规则表" (
  "规则ID" text PRIMARY KEY,
  "法规ID" text NOT NULL,
  "条文定位" text NOT NULL,
  "适用条件" text NOT NULL,
  "责任部门" text NOT NULL
);

-- readme.md:1054
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

-- readme.md:1075
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

-- readme.md:1097
CREATE TABLE legal."履约提示表" (
  "提示ID" text PRIMARY KEY,
  "审阅ID" text NOT NULL,
  "履约节点" text NOT NULL,
  "责任部门" text NOT NULL,
  "期限" date NOT NULL,
  "状态" text NOT NULL,
  CHECK ("状态" IN ('待履约', '已履约', '已取消'))
);

-- readme.md:1117
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

-- readme.md:1142
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

-- readme.md:1167
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

-- readme.md:1189
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

-- readme.md:1210
CREATE TABLE legal."意见采纳表" (
  "采纳记录ID" text PRIMARY KEY,
  "意见ID" text NOT NULL,
  "决定日期" date NOT NULL,
  "采纳结论" text NOT NULL,
  "目标" text,
  "负责人ID" text
);

-- readme.md:1227
CREATE TABLE legal."意见执行表" (
  "执行记录ID" text PRIMARY KEY,
  "采纳记录ID" text NOT NULL,
  "执行时间" timestamptz NOT NULL,
  "执行内容" text NOT NULL,
  "实际结果" text,
  "证据路径" text,
  "负责人ID" text
);

-- readme.md:1245
CREATE TABLE legal."整改处理表" (
  "整改处理记录ID" text PRIMARY KEY,
  "整改事项ID" text NOT NULL,
  "处理时间" timestamptz NOT NULL,
  "处理内容" text NOT NULL,
  "结果" text,
  "证据路径" text,
  "处理人ID" text
);

-- readme.md:1265
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

-- readme.md:1328
CREATE TABLE production."设备档案表" (
  "设备ID" text PRIMARY KEY,
  "设备名称" text NOT NULL,
  "规格" text,
  "所在地点" text,
  "启用状态" text NOT NULL,
  CHECK ("启用状态" IN ('启用', '停用'))
);

-- readme.md:1343
CREATE TABLE production."供应商档案表" (
  "供应商ID" text PRIMARY KEY,
  "名称" text NOT NULL,
  "联系方式" text,
  "统一社会信用代码" text,
  "户名" text,
  "账户ID" text,
  "开户行" text
);

-- readme.md:1360
CREATE TABLE production."采购合同表" (
  "采购合同ID" text PRIMARY KEY,
  "供应商ID" text NOT NULL,
  "签署日期" date,
  "合同文件路径" text NOT NULL,
  "状态" text NOT NULL,
  CHECK ("状态" IN ('草稿', '已签署', '已终止'))
);

-- readme.md:1379
CREATE TABLE production."采购订单表" (
  "采购单ID" text PRIMARY KEY,
  "采购合同ID" text,
  "供应商ID" text NOT NULL,
  "创建日期" date NOT NULL,
  "状态" text NOT NULL,
  "币种" char(3) NOT NULL,
  CHECK ("状态" IN ('草稿', '已下单', '部分到货', '已完成', '已取消'))
);

-- readme.md:1397
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

-- readme.md:1422
CREATE TABLE production."保管方档案表" (
  "保管方ID" text PRIMARY KEY,
  "名称" text NOT NULL,
  "主体ID" text
);

-- readme.md:1438
CREATE TABLE production."仓库档案表" (
  "仓库ID" text PRIMARY KEY,
  "地点" text NOT NULL,
  "保管方ID" text NOT NULL,
  "主体ID" text NOT NULL,
  "启用状态" text NOT NULL,
  CHECK ("启用状态" IN ('启用', '停用'))
);

-- readme.md:1457
CREATE TABLE production."库位档案表" (
  "库位ID" text PRIMARY KEY,
  "仓库ID" text NOT NULL,
  "库位代码" text NOT NULL,
  UNIQUE ("仓库ID", "库位代码")
);

-- readme.md:1474
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

-- readme.md:1498
CREATE TABLE production."到货记录表" (
  "到货ID" text PRIMARY KEY,
  "采购订单行ID" text NOT NULL,
  "到货时间" timestamptz NOT NULL,
  "数量" numeric(20,6) NOT NULL,
  "单位ID" text NOT NULL,
  "凭证路径" text,
  CHECK ("数量" > 0)
);

-- readme.md:1516
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

-- readme.md:1541
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

-- readme.md:1575
CREATE TABLE production."工单草稿表" (
  "草稿登记ID" text PRIMARY KEY,
  "计划说明" text NOT NULL,
  "登记时间" timestamptz NOT NULL,
  "负责人ID" text,
  "状态" text NOT NULL,
  CHECK ("状态" IN ('待下达', '已下达', '已取消'))
);

-- readme.md:1594
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

-- readme.md:1621
CREATE TABLE production."工单订单对应表" (
  "工单订单关联ID" text PRIMARY KEY,
  "工单号" text NOT NULL,
  "销售订单行ID" text NOT NULL,
  "对应数量" numeric(20,6) NOT NULL,
  "单位ID" text NOT NULL,
  "订单组合明细ID" text,
  UNIQUE ("工单号", "销售订单行ID")
);

-- readme.md:1639
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

-- readme.md:1663
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

-- readme.md:1691
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

-- readme.md:1711
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

-- readme.md:1736
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

-- readme.md:1763
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

-- readme.md:1787
CREATE TABLE production."采购归属对应表" (
  "采购归属ID" text PRIMARY KEY,
  "采购订单行ID" text NOT NULL,
  "分摊ID" text NOT NULL,
  "归属数量" numeric(20,6) NOT NULL,
  "单位ID" text NOT NULL,
  "依据" text NOT NULL,
  UNIQUE ("采购订单行ID", "分摊ID")
);

-- readme.md:1807
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

-- readme.md:1830
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

-- readme.md:1855
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

-- readme.md:1879
CREATE TABLE production."库存结存来源明细表" (
  "结存来源ID" text PRIMARY KEY,
  "库存结存ID" text NOT NULL,
  "库存事件ID" text NOT NULL,
  "统一单位数量" numeric(20,6) NOT NULL,
  "换算ID" text,
  UNIQUE ("库存结存ID", "库存事件ID")
);

-- readme.md:1896
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

-- readme.md:1917
CREATE TABLE production."意见采纳表" (
  "采纳记录ID" text PRIMARY KEY,
  "意见ID" text NOT NULL,
  "决定日期" date NOT NULL,
  "采纳结论" text NOT NULL,
  "目标" text,
  "负责人ID" text
);

-- readme.md:1934
CREATE TABLE production."意见执行表" (
  "执行记录ID" text PRIMARY KEY,
  "采纳记录ID" text NOT NULL,
  "执行时间" timestamptz NOT NULL,
  "执行内容" text NOT NULL,
  "实际结果" text,
  "证据路径" text,
  "负责人ID" text
);

-- readme.md:1952
CREATE TABLE production."整改处理表" (
  "整改处理记录ID" text PRIMARY KEY,
  "整改事项ID" text NOT NULL,
  "处理时间" timestamptz NOT NULL,
  "处理内容" text NOT NULL,
  "结果" text,
  "证据路径" text,
  "处理人ID" text
);

-- readme.md:1972
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

-- readme.md:2044
CREATE TABLE rd."计量单位表" (
  "单位ID" text PRIMARY KEY,
  "单位名称" text NOT NULL,
  "备注" text
);

-- readme.md:2060
CREATE TABLE rd."产品主数据表" (
  "PID" text PRIMARY KEY,
  "名称" text NOT NULL,
  "规格" text NOT NULL,
  "单位ID" text NOT NULL,
  "类别" text NOT NULL
);

-- readme.md:2076
CREATE TABLE rd."物料主数据表" (
  "MID" text PRIMARY KEY,
  "名称" text NOT NULL,
  "规格" text NOT NULL,
  "单位ID" text NOT NULL,
  "类别" text NOT NULL
);

-- readme.md:2092
CREATE TABLE rd."项目草稿表" (
  "草稿登记ID" text PRIMARY KEY,
  "项目描述" text NOT NULL,
  "登记日期" date NOT NULL,
  "状态" text NOT NULL,
  CHECK ("状态" IN ('待确认', '已立项', '已取消'))
);

-- readme.md:2108
CREATE TABLE rd."项目登记表" (
  "项目ID" text PRIMARY KEY,
  "草稿登记ID" text,
  "项目名称" text NOT NULL,
  "负责人ID" text,
  "开始日期" date,
  "结束日期" date,
  "确认依据" text NOT NULL
);

-- readme.md:2126
CREATE TABLE rd."产品版本表" (
  "产品版本ID" text PRIMARY KEY,
  "项目ID" text NOT NULL,
  "PID" text NOT NULL,
  "版本名称" text NOT NULL,
  "生效日期" date,
  "确认依据" text NOT NULL,
  UNIQUE ("PID", "版本名称")
);

-- readme.md:2146
CREATE TABLE rd."物料版本表" (
  "物料版本ID" text PRIMARY KEY,
  "MID" text NOT NULL,
  "版本名称" text NOT NULL,
  "生效日期" date,
  "确认依据" text NOT NULL,
  UNIQUE ("MID", "版本名称")
);

-- readme.md:2165
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

-- readme.md:2188
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

-- readme.md:2210
CREATE TABLE rd."BOM登记表" (
  "BOM登记ID" text PRIMARY KEY,
  "产品版本ID" text NOT NULL,
  "BOM版本" text NOT NULL,
  "确认依据" text NOT NULL,
  UNIQUE ("产品版本ID", "BOM版本")
);

-- readme.md:2228
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

-- readme.md:2258
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

-- readme.md:2286
CREATE TABLE rd."研发事项来源表" (
  "来源关联ID" text PRIMARY KEY,
  "研发事项ID" text NOT NULL,
  "检验ID" text,
  "需求ID" text,
  "售后事件ID" text,
  CHECK (num_nonnulls("检验ID", "需求ID", "售后事件ID") = 1)
);

-- readme.md:2303
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

-- readme.md:2324
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

-- readme.md:2345
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

-- readme.md:2367
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

-- readme.md:2386
CREATE TABLE rd."发布文件明细表" (
  "发布文件明细ID" text PRIMARY KEY,
  "发布批次ID" text NOT NULL,
  "文件ID" text NOT NULL,
  UNIQUE ("发布批次ID", "文件ID")
);

-- readme.md:2401
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

-- readme.md:2422
CREATE TABLE rd."意见采纳表" (
  "采纳记录ID" text PRIMARY KEY,
  "意见ID" text NOT NULL,
  "决定日期" date NOT NULL,
  "采纳结论" text NOT NULL,
  "目标" text,
  "负责人ID" text
);

-- readme.md:2439
CREATE TABLE rd."意见执行表" (
  "执行记录ID" text PRIMARY KEY,
  "采纳记录ID" text NOT NULL,
  "执行时间" timestamptz NOT NULL,
  "执行内容" text NOT NULL,
  "实际结果" text,
  "证据路径" text,
  "负责人ID" text
);

-- readme.md:2457
CREATE TABLE rd."整改处理表" (
  "整改处理记录ID" text PRIMARY KEY,
  "整改事项ID" text NOT NULL,
  "处理时间" timestamptz NOT NULL,
  "处理内容" text NOT NULL,
  "结果" text,
  "证据路径" text,
  "处理人ID" text
);

-- readme.md:2477
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

-- readme.md:2537
CREATE TABLE sales."渠道档案表" (
  "渠道ID" text PRIMARY KEY,
  "渠道名称" text NOT NULL,
  "平台名称" text NOT NULL,
  "店铺标识" text NOT NULL,
  UNIQUE ("平台名称", "店铺标识")
);

-- readme.md:2551
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

-- readme.md:2570
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

-- readme.md:2591
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

-- readme.md:2614
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

-- readme.md:2639
CREATE TABLE sales."销售合同表" (
  "销售合同ID" text PRIMARY KEY,
  "客户ID" text NOT NULL,
  "签署日期" date,
  "合同文件路径" text NOT NULL,
  "状态" text NOT NULL,
  CHECK ("状态" IN ('草稿', '已签署', '已终止'))
);

-- readme.md:2656
CREATE TABLE sales."合同订单对应表" (
  "合同订单关联ID" text PRIMARY KEY,
  "销售合同ID" text NOT NULL,
  "订单ID" text NOT NULL,
  UNIQUE ("销售合同ID", "订单ID")
);

-- readme.md:2671
CREATE TABLE sales."销售动作表" (
  "销售动作ID" text PRIMARY KEY,
  "客户ID" text NOT NULL,
  "订单ID" text,
  "销售合同ID" text,
  "发生时间" timestamptz NOT NULL,
  "行为记录" text NOT NULL
);

-- readme.md:2690
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

-- readme.md:2721
CREATE TABLE sales."组合商品表" (
  "组合商品ID" text PRIMARY KEY,
  "组合名称" text NOT NULL,
  "定义版本" text NOT NULL,
  "生效日期" date NOT NULL,
  "失效日期" date
);

-- readme.md:2737
CREATE TABLE sales."组合商品明细表" (
  "组合明细ID" text PRIMARY KEY,
  "组合商品ID" text NOT NULL,
  "产品版本ID" text NOT NULL,
  "换算数量" numeric(20,6) NOT NULL,
  "单位ID" text NOT NULL,
  UNIQUE ("组合商品ID", "产品版本ID"),
  CHECK ("换算数量" > 0)
);

-- readme.md:2757
CREATE TABLE sales."订单组合明细表" (
  "订单组合明细ID" text PRIMARY KEY,
  "销售订单行ID" text NOT NULL,
  "组合明细ID" text NOT NULL,
  "应履约数量" numeric(20,6) NOT NULL,
  UNIQUE ("销售订单行ID", "组合明细ID")
);

-- readme.md:2775
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

-- readme.md:2802
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

-- readme.md:2827
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

-- readme.md:2848
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

-- readme.md:2869
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

-- readme.md:2888
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

-- readme.md:2910
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

-- readme.md:2931
CREATE TABLE sales."意见采纳表" (
  "采纳记录ID" text PRIMARY KEY,
  "意见ID" text NOT NULL,
  "决定日期" date NOT NULL,
  "采纳结论" text NOT NULL,
  "目标" text,
  "负责人ID" text
);

-- readme.md:2948
CREATE TABLE sales."意见执行表" (
  "执行记录ID" text PRIMARY KEY,
  "采纳记录ID" text NOT NULL,
  "执行时间" timestamptz NOT NULL,
  "执行内容" text NOT NULL,
  "实际结果" text,
  "证据路径" text,
  "负责人ID" text
);

-- readme.md:2966
CREATE TABLE sales."整改处理表" (
  "整改处理记录ID" text PRIMARY KEY,
  "整改事项ID" text NOT NULL,
  "处理时间" timestamptz NOT NULL,
  "处理内容" text NOT NULL,
  "结果" text,
  "证据路径" text,
  "处理人ID" text
);

-- readme.md:2986
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

-- readme.md:3043
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

-- readme.md:3064
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

-- readme.md:3084
CREATE TABLE analysis."指标定义表" (
  "指标ID" text PRIMARY KEY,
  "指标名称" text NOT NULL,
  "版本" text NOT NULL,
  "公式" text NOT NULL,
  "单位" text NOT NULL,
  "适用条件" text NOT NULL,
  UNIQUE ("指标名称", "版本")
);

-- readme.md:3104
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

-- readme.md:3125
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

-- readme.md:3144
CREATE TABLE analysis."报告模型对应表" (
  "报告模型关联ID" text PRIMARY KEY,
  "报告ID" text NOT NULL,
  "模型ID" text NOT NULL,
  UNIQUE ("报告ID", "模型ID")
);

-- readme.md:3159
CREATE TABLE analysis."报告数据对应表" (
  "报告数据关联ID" text PRIMARY KEY,
  "报告ID" text NOT NULL,
  "数据集ID" text NOT NULL,
  UNIQUE ("报告ID", "数据集ID")
);

-- readme.md:3174
CREATE TABLE analysis."报告指标对应表" (
  "报告指标关联ID" text PRIMARY KEY,
  "报告ID" text NOT NULL,
  "计算记录ID" text NOT NULL,
  UNIQUE ("报告ID", "计算记录ID")
);

-- readme.md:3191
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

-- readme.md:3214
CREATE TABLE analysis."意见指标对应表" (
  "意见指标关联ID" text PRIMARY KEY,
  "意见ID" text NOT NULL,
  "计算记录ID" text NOT NULL,
  UNIQUE ("意见ID", "计算记录ID")
);

-- readme.md:3229
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

-- readme.md:3248
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

-- readme.md:3269
CREATE TABLE analysis."意见采纳表" (
  "采纳记录ID" text PRIMARY KEY,
  "意见ID" text NOT NULL,
  "决定日期" date NOT NULL,
  "采纳结论" text NOT NULL,
  "目标" text,
  "负责人ID" text
);

-- readme.md:3286
CREATE TABLE analysis."意见执行表" (
  "执行记录ID" text PRIMARY KEY,
  "采纳记录ID" text NOT NULL,
  "执行时间" timestamptz NOT NULL,
  "执行内容" text NOT NULL,
  "实际结果" text,
  "证据路径" text,
  "负责人ID" text
);

-- readme.md:3304
CREATE TABLE analysis."整改处理表" (
  "整改处理记录ID" text PRIMARY KEY,
  "整改事项ID" text NOT NULL,
  "处理时间" timestamptz NOT NULL,
  "处理内容" text NOT NULL,
  "结果" text,
  "证据路径" text,
  "处理人ID" text
);

-- readme.md:3324
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

-- readme.md:3352
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
