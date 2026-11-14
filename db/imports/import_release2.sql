-- Add source snapshots without interpreting them as operational postings.
CREATE TABLE IF NOT EXISTS erp_ops.source_workbook_record (
 record_id text PRIMARY KEY, file_id text NOT NULL REFERENCES erp_ops.source_import_file,
 sheet_name text NOT NULL, row_no integer NOT NULL CHECK(row_no>0),
 record_kind text NOT NULL, source_key text NOT NULL, source_data jsonb NOT NULL,
 derived_data jsonb NOT NULL, mapped_ids jsonb NOT NULL,
 UNIQUE(file_id,sheet_name,row_no)
);
CREATE TABLE IF NOT EXISTS erp_ops.source_import_definition (
 change_id text PRIMARY KEY, object_name text NOT NULL,
 previous_definition text NOT NULL, changed_at timestamptz NOT NULL DEFAULT now()
);


-- Missing version, unit or confirmation evidence must not enter the approved view.
















GRANT SELECT ON erp_ops.source_workbook_record,erp_ops.source_import_definition
TO easyerp_read,easyerp_app;
