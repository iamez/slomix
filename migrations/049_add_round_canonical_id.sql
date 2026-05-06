-- Migration 049: Add round_canonical_id column to rounds table
-- Per ADR docs/ADR_round_canonical_id.md (Phase 1)
--
-- This migration ONLY adds the column + index (nullable). Backfill happens
-- via tools/backfill_round_canonical_id.py. UNIQUE constraint comes in
-- Phase 3 (separate migration) once backfill verified.
--
-- Rollback: ALTER TABLE rounds DROP COLUMN round_canonical_id;
--           DROP INDEX IF EXISTS idx_rounds_canonical_id;

BEGIN;

ALTER TABLE rounds
    ADD COLUMN IF NOT EXISTS round_canonical_id varchar(64) NULL;

-- Non-unique index for fast lookups during dual-mode period (Phase 2).
-- Becomes UNIQUE in Phase 3 (migration 050).
CREATE INDEX IF NOT EXISTS idx_rounds_canonical_id
    ON rounds(round_canonical_id)
    WHERE round_canonical_id IS NOT NULL;

COMMENT ON COLUMN rounds.round_canonical_id IS
    'SHA256(round_start_unix:map_name:round_number)[:16] — content-addressed stable id. See docs/ADR_round_canonical_id.md';

COMMIT;
