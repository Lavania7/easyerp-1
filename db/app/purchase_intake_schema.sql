-- Purchases can be registered from their original order document without item coding.
ALTER TABLE production."采购订单表"
  ADD COLUMN IF NOT EXISTS "采购说明" text,
  ADD COLUMN IF NOT EXISTS "订单金额" numeric(20,4),
  ADD COLUMN IF NOT EXISTS "订单文件路径" text;
