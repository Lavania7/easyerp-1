# 数据导入箱

把需要 Agent 处理的原始文件放到 [inbox](inbox/)：

- `finance`：资金、结算、发票、财务核定资料。
- `sales`：订单、客户、售后、需求。
- `production`：采购、库存、工单与实际生产事件。
- `rd`：产品、物料、BOM、研发与发布。
- `legal`：主体、合同、规则、整改。
- `analysis`：指标、报告、意见与反馈。
- `unclassified`：跨部门或无法判断归属的文件。

也可以直接放到 `inbox`，由 Agent 分类。原名保留；不要修改文件来凑表头。

放好后告诉 Agent：**“处理 import/inbox，更新正式库，按前端导入规则确认空缺和已有记录。”**

仅放入文件不会自动入库。Agent 保留原件，把来源副本、字段映射、标准 CSV、检查和回执放在 [batches](batches/)。完整说明见[文件导入流程](../docs/import-workflow.md)，业务含义以[全局规则](../docs/global-rules.md)为准。

这些目录中的实际业务文件不提交 Git；需要保留的原件、批次和数据库备份请另行备份。
