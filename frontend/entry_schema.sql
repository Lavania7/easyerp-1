-- Additive frontend support; the authoritative business tables stay unchanged.
CREATE TABLE IF NOT EXISTS erp_ops.frontend_entry_audit (
    request_id text PRIMARY KEY,
    payload_hash char(64) NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    database_role text NOT NULL DEFAULT current_user,
    source text NOT NULL DEFAULT 'local_frontend_manual',
    changes jsonb NOT NULL,
    result jsonb NOT NULL
);
REVOKE ALL ON erp_ops.frontend_entry_audit FROM PUBLIC;
GRANT SELECT, INSERT ON erp_ops.frontend_entry_audit TO easyerp_app;
GRANT SELECT ON erp_ops.frontend_entry_audit TO easyerp_read;
