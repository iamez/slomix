-- Existing receipts do not prove parent-gated ingestion. Never backfill TRUE.
-- New strict runtime imports set this on INSERT in the same transaction as
-- source binding, parent validation and child writes. A pending/failed import
-- rolls it back. ON CONFLICT preserves the original provenance.
ALTER TABLE proximity_processed_files
    ADD COLUMN IF NOT EXISTS runtime_parent_gate BOOLEAN NOT NULL DEFAULT FALSE;
