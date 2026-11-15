-- Unit IDs remain stable; preserve retired values outside editable business fields.
CREATE TABLE IF NOT EXISTS erp_ops.unit_profile_retired_fields (
  upgrade_id text NOT NULL,
  unit_id text NOT NULL,
  unit_code text,
  measurement_dimension text,
  archived_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (upgrade_id,unit_id)
);
REVOKE ALL ON erp_ops.unit_profile_retired_fields FROM PUBLIC,easyerp_app,easyerp_read;

ALTER TABLE rd."计量单位表" ADD COLUMN IF NOT EXISTS "备注" text;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_attribute
      WHERE attrelid='rd."计量单位表"'::regclass
      AND attname='单位代码' AND NOT attisdropped) THEN
    INSERT INTO erp_ops.unit_profile_retired_fields
      (upgrade_id,unit_id,unit_code,measurement_dimension)
      SELECT '009_unit_profile',"单位ID","单位代码","计量维度" FROM rd."计量单位表";
    -- RESTRICT rolls back on an unreviewed dependency; never cascade.
    ALTER TABLE rd."计量单位表" DROP COLUMN "单位代码" RESTRICT;
    ALTER TABLE rd."计量单位表" DROP COLUMN "计量维度" RESTRICT;
  END IF;
END $$;
