"""Create the explicitly labelled, isolated UI sample database once."""
from pathlib import Path
import sys
from data import ROOT
from easyerp import ERP

e=ERP()
db=e.c['database']+'_ui_demo'
e.ensure_database(db)
exists=e.sql('SELECT count(*) FROM finance."人员档案表";',db=db).stdout.strip()
if exists!='0':
    print('Isolated UI demo already prepared; existing sample retained.')
    sys.exit(0)
e.sql(file=ROOT/'tests'/'business.sql',db=db)
e.sql('''BEGIN;
UPDATE legal."公司主体档案表" SET "公司名称"='示例智造（演示）' WHERE "主体ID"='co';
UPDATE finance."人员档案表" SET "姓名"='林青（演示）' WHERE "人员ID"='person';
UPDATE rd."产品主数据表" SET "名称"='工业控制板',"规格"='EC-01 · 标准版' WHERE "PID"='pid';
UPDATE rd."项目登记表" SET "项目名称"='控制板迭代项目' WHERE "项目ID"='project';
UPDATE finance."资金账户档案表" SET "账户名"='经营账户 · 演示' WHERE "账户ID"='account';
UPDATE finance."资金流水表" SET "交易摘要"='控制板订单收款（演示）' WHERE "资金记录ID"='cash';
UPDATE sales."渠道档案表" SET "渠道名称"='企业直销（演示）' WHERE "渠道ID"='channel';
INSERT INTO sales."客户档案表"("客户ID","客户名称","客户来源标识","产业分类","地区分类") VALUES ('customer','青禾设备（演示）','DEMO-001','设备制造','华东');
UPDATE sales."销售订单登记表" SET "客户ID"='customer' WHERE "订单ID"='order';
UPDATE sales."销售订单行表" SET "交期"='2026-10-28',"收货信息"='演示收货信息' WHERE "销售订单行ID"='line';
UPDATE production."生产工单表" SET "下达依据"='控制板小批量制造（演示）',"负责人ID"='person',"计划结束日期"='2026-10-26',"状态"='执行中' WHERE "工单号"='work';
INSERT INTO production."完工记录表" VALUES ('finished','work','batch','2026-10-18',4,0,'unit',NULL);
INSERT INTO production."生产工时表"("工时ID","工单号","工序","人员ID","开始时间","结束时间","有效工时") VALUES ('prod-hours','work','装配','person','2026-10-18T08:00:00Z','2026-10-18T10:30:00Z',2.5);
UPDATE finance."收入成本确认表" SET "确认收入"=80,"税额"=NULL,"结转成本"=45,"状态"='已核定',"确认依据"='仅用于界面演示，不代表真实核定或税务口径' WHERE "确认ID"='recognition';
INSERT INTO finance."资金流水表" VALUES ('pending-cash','account','2026-10-19T09:00:00Z',20,'支出','DEMO-P002','采购付款用途待核定（演示）');
INSERT INTO finance."资金用途核定表"("用途核定ID","资金记录ID","用途","状态") VALUES ('pending-purpose','pending-cash','采购用途候选（演示）','待核定');
INSERT INTO finance."账户期间余额表" VALUES ('balance','account','2026-10-01','2026-10-20',1,500,580,'仅演示样本','person');
INSERT INTO finance."账户核对表" VALUES ('reconcile','balance',580,'已核定','演示核对',1);
INSERT INTO sales."售后事件表"("售后事件ID","销售订单行ID","类型","发生时间","原因","处理状态") VALUES ('after','line','使用咨询','2026-10-20T10:00:00Z','客户反馈：需要确认安装接口（演示）','新建');
COMMIT;''',db=db)
print('Isolated sample ready: '+db)
