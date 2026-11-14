业务编号规则
============

短 ID = 主录前缀 + 至少三位36进制流水。长 ID 和 SHA-256 仅供后台及 Agent。
长 ID = 部门简写-主录前缀-编号生成年月日-流水的十进制值，SHA-256 = SHA256(UTF-8 长 ID)。

.. list-table::
   :header-rows: 1

   * - 主录
     - 部门
     - 前缀
   * - analysis.交付明细表
     - ANA
     - ADL
   * - analysis.交付记录表
     - ANA
     - AD
   * - analysis.分析报告登记表
     - ANA
     - AR
   * - analysis.意见与规划总表
     - ANA
     - AP
   * - analysis.意见复盘表
     - ANA
     - AV
   * - analysis.意见执行表
     - ANA
     - AE
   * - analysis.意见指标对应表
     - ANA
     - AMI
   * - analysis.意见采纳表
     - ANA
     - AA
   * - analysis.报告指标对应表
     - ANA
     - ARI
   * - analysis.报告数据对应表
     - ANA
     - ARD
   * - analysis.报告模型对应表
     - ANA
     - ARM
   * - analysis.指标定义表
     - ANA
     - MI
   * - analysis.指标计算表
     - ANA
     - MC
   * - analysis.数学模型库
     - ANA
     - ML
   * - analysis.数据引用登记表
     - ANA
     - DS
   * - analysis.数据集输入来源表
     - ANA
     - DSI
   * - analysis.整改处理表
     - ANA
     - ACR
   * - finance.交付明细表
     - FIN
     - FDL
   * - finance.交付记录表
     - FIN
     - FD
   * - finance.人员档案表
     - FIN
     - HR
   * - finance.会计凭证表
     - FIN
     - JV
   * - finance.会计分录表
     - FIN
     - JE
   * - finance.会计政策表
     - FIN
     - APO
   * - finance.会计科目表
     - FIN
     - GL
   * - finance.内部划转对应表
     - FIN
     - TR
   * - finance.利润表
     - FIN
     - PL
   * - finance.利润表来源明细表
     - FIN
     - PLS
   * - finance.发票分摊表
     - FIN
     - IA
   * - finance.发票登记表
     - FIN
     - INV
   * - finance.工时计价表
     - FIN
     - LR
   * - finance.往来未结明细表
     - FIN
     - OB
   * - finance.意见执行表
     - FIN
     - FE
   * - finance.意见采纳表
     - FIN
     - FA
   * - finance.报表批次表
     - FIN
     - FB
   * - finance.报表项目映射表
     - FIN
     - FM
   * - finance.收入成本确认表
     - FIN
     - RC
   * - finance.整改处理表
     - FIN
     - FCR
   * - finance.期初及结账核实表
     - FIN
     - FC
   * - finance.流水文件登记表
     - FIN
     - FF
   * - finance.流水来源明细表
     - FIN
     - FS
   * - finance.现金流量表
     - FIN
     - CF
   * - finance.现金流量表来源明细表
     - FIN
     - CFS
   * - finance.税款缴退明细表
     - FIN
     - TP
   * - finance.纳税申报记录表
     - FIN
     - TD
   * - finance.结算分摊表
     - FIN
     - SA
   * - finance.账户期间余额表
     - FIN
     - BAL
   * - finance.账户核对表
     - FIN
     - REC
   * - finance.费用归属表
     - FIN
     - EXP
   * - finance.资产台账
     - FIN
     - AST
   * - finance.资产负债表
     - FIN
     - BS
   * - finance.资产负债表来源明细表
     - FIN
     - BSS
   * - finance.资金流水表
     - FIN
     - F
   * - finance.资金用途核定表
     - FIN
     - FU
   * - finance.资金账户档案表
     - FIN
     - ACC
   * - finance.重复记录对应表
     - FIN
     - DUP
   * - legal.交付明细表
     - LEG
     - LDL
   * - legal.交付记录表
     - LEG
     - LD
   * - legal.公司主体档案表
     - LEG
     - CO
   * - legal.合同审阅表
     - LEG
     - CR
   * - legal.合规自查表
     - LEG
     - CC
   * - legal.履约提示表
     - LEG
     - REM
   * - legal.意见执行表
     - LEG
     - LE
   * - legal.意见采纳表
     - LEG
     - LA
   * - legal.整改处理表
     - LEG
     - LCR
   * - legal.整改跟踪表
     - LEG
     - CT
   * - legal.法律文件登记表
     - LEG
     - DOC
   * - legal.法规登记表
     - LEG
     - LAW
   * - legal.证据对应表
     - LEG
     - EV
   * - legal.适用规则表
     - LEG
     - RUL
   * - production.交付明细表
     - PRD
     - PDL
   * - production.交付记录表
     - PRD
     - PD
   * - production.仓库档案表
     - PRD
     - WH
   * - production.供应商档案表
     - PRD
     - SUP
   * - production.保管方档案表
     - PRD
     - KP
   * - production.到货记录表
     - PRD
     - ARR
   * - production.发货记录表
     - PRD
     - SHP
   * - production.委外物料流转表
     - PRD
     - OUT
   * - production.完工记录表
     - PRD
     - CMP
   * - production.工单草稿表
     - PRD
     - DRF
   * - production.工单订单对应表
     - PRD
     - WOL
   * - production.库位档案表
     - PRD
     - LOC
   * - production.库存余额与差异表
     - PRD
     - STB
   * - production.库存变动表
     - PRD
     - STK
   * - production.库存基准核定表
     - PRD
     - BAS
   * - production.库存盘点表
     - PRD
     - CNT
   * - production.库存结存来源明细表
     - PRD
     - STS
   * - production.意见执行表
     - PRD
     - PE
   * - production.意见采纳表
     - PRD
     - PA
   * - production.报废记录表
     - PRD
     - SCR
   * - production.整改处理表
     - PRD
     - PCR
   * - production.生产工单表
     - PRD
     - WO
   * - production.生产工时表
     - PRD
     - PH
   * - production.生产领退料表
     - PRD
     - MAT
   * - production.设备档案表
     - PRD
     - EQ
   * - production.质量检验表
     - PRD
     - QC
   * - production.采购合同表
     - PRD
     - PC
   * - production.采购归属对应表
     - PRD
     - PAL
   * - production.采购订单行表
     - PRD
     - POL
   * - production.采购订单表
     - PRD
     - PO
   * - production.验收记录表
     - PRD
     - GR
   * - rd.BOM明细表
     - RND
     - BL
   * - rd.BOM登记表
     - RND
     - BOM
   * - rd.交付明细表
     - RND
     - RDL
   * - rd.交付记录表
     - RND
     - RD
   * - rd.产品主数据表
     - RND
     - P
   * - rd.产品版本表
     - RND
     - PV
   * - rd.产品规格表
     - RND
     - PS
   * - rd.单位换算表
     - RND
     - UC
   * - rd.发布批次表
     - RND
     - REL
   * - rd.发布文件明细表
     - RND
     - RFL
   * - rd.意见执行表
     - RND
     - RE
   * - rd.意见采纳表
     - RND
     - RA
   * - rd.整改处理表
     - RND
     - RCR
   * - rd.物料主数据表
     - RND
     - M
   * - rd.物料版本表
     - RND
     - MV
   * - rd.研发事项来源表
     - RND
     - RSC
   * - rd.研发工时表
     - RND
     - RH
   * - rd.研发投入归属表
     - RND
     - RI
   * - rd.计量单位表
     - RND
     - U
   * - rd.设计变更与验证表
     - RND
     - EC
   * - rd.项目文件登记表
     - RND
     - RF
   * - rd.项目登记表
     - RND
     - PJ
   * - rd.项目草稿表
     - RND
     - PJD
   * - sales.交付明细表
     - SAL
     - SDL
   * - sales.交付记录表
     - SAL
     - SD
   * - sales.合同订单对应表
     - SAL
     - COL
   * - sales.售后事件表
     - SAL
     - AS
   * - sales.商品对应表
     - SAL
     - MAP
   * - sales.客户分类统计批次表
     - SAL
     - CSB
   * - sales.客户分类统计结果表
     - SAL
     - CSR
   * - sales.客户档案表
     - SAL
     - C
   * - sales.客户需求表
     - SAL
     - DEM
   * - sales.平台文件登记表
     - SAL
     - SF
   * - sales.意见执行表
     - SAL
     - SE
   * - sales.意见采纳表
     - SAL
     - SAD
   * - sales.整改处理表
     - SAL
     - SCC
   * - sales.渠道档案表
     - SAL
     - CH
   * - sales.组合商品明细表
     - SAL
     - BND
   * - sales.组合商品表
     - SAL
     - BD
   * - sales.订单导出快照表
     - SAL
     - SNP
   * - sales.订单组合明细表
     - SAL
     - SBL
   * - sales.销售动作表
     - SAL
     - ACT
   * - sales.销售合同表
     - SAL
     - SC
   * - sales.销售期间覆盖表
     - SAL
     - COV
   * - sales.销售订单登记表
     - SAL
     - S
   * - sales.销售订单行表
     - SAL
     - SL


编号生成日期使用 Europe/Berlin 本地日历；事件录入和业务日期沿用既有口径。首次迁移的日期时区校正记录保存在同次迁移目录的 date-correction.json，既有数据备份和迁移原回执均保留。
