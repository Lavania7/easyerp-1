"""Presentation ownership. Legacy SQL remains available for evidence and references."""
WORKFLOW_NAMES = {'意见采纳表', '意见执行表', '整改处理表', '履约提示表', '合规自查表', '整改跟踪表', '生产工单表'}
RETIRED_NAMES = {'期初及结账核实表', '库存基准核定表', '生产工时表', '工时计价表', '证据对应表'}
SUPPORT_NAMES = {'流水来源明细表', '结算分摊表', '发票分摊表', '采购订单行表', '采购归属对应表', '库位档案表',
                 '库存余额与差异表', '库存结存来源明细表'}
AUDIT_NAMES = {'资金用途核定表', '内部划转对应表', '重复记录对应表', '往来未结明细表', '账户核对表'}
ARCHIVE_NAMES = {'会计政策表', '会计科目表', '法规登记表', '适用规则表', '法律文件登记表', '数学模型库', '指标定义表'}
LABELS = {'production.采购订单表': '采购订单', 'production.仓库档案表': '仓储地点',
          'production.库存盘点表': '库存盘点与余额', 'production.生产工单表': '生产执行',
          'production.工单草稿表': '历史生产计划', 'production.工单订单对应表': '生产执行与订单对应'}


def presentation(schema, name):
    area = 'data'
    if name in WORKFLOW_NAMES: area = 'workflow'
    elif name == '工单草稿表' or (schema == 'analysis' and name == '意见与规划总表'): area = 'plans'
    elif name in RETIRED_NAMES or name in SUPPORT_NAMES: area = 'history'
    elif name in AUDIT_NAMES: area = 'audit'
    elif name in ARCHIVE_NAMES or '档案' in name or name.endswith(('主数据表', '版本表')) or name in {'计量单位表', '单位换算表'}: area = 'archive'
    # Warehouse and its location are one operational entry in the archive.
    return {'area': area, 'label': LABELS.get(schema+'.'+name, name),
            'retired': name in RETIRED_NAMES or name in {'意见采纳表', '意见执行表', '整改处理表', '履约提示表', '合规自查表', '整改跟踪表', '工单草稿表'},
            'standalone': name not in SUPPORT_NAMES and name not in RETIRED_NAMES}


def annotate(obj):
    obj.update(presentation(obj['schema'], obj['name']))
    return obj
