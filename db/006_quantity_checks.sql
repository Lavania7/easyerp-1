CREATE TABLE erp_ops.schema_upgrade_log (
 upgrade_id text PRIMARY KEY, from_build text NOT NULL, to_build text NOT NULL,
 source_sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now()
);
