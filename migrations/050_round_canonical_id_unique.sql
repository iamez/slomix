-- Migration 050: Add UNIQUE constraint on round_canonical_id
-- Per ADR docs/ADR_round_canonical_id.md (Phase 3, layer A)
--
-- Partial UNIQUE index — only enforces uniqueness for non-NULL rows.
-- This allows historic rounds without round_start_unix to coexist
-- (canonical_id stays NULL, no constraint applied).
--
-- Prerequisite: migration 049 applied + backfill executed.
-- Verify before running: COUNT(canonical_id) == COUNT(DISTINCT canonical_id)
--
-- Rollback: DROP INDEX IF EXISTS uniq_rounds_canonical_id;

BEGIN;

-- Pre-flight check: refuse if duplicates already present (would block creation)
DO $$
DECLARE
    dup_count int;
BEGIN
    SELECT COUNT(*) INTO dup_count FROM (
        SELECT round_canonical_id, COUNT(*) c
        FROM rounds
        WHERE round_canonical_id IS NOT NULL
        GROUP BY round_canonical_id
        HAVING COUNT(*) > 1
    ) x;
    IF dup_count > 0 THEN
        RAISE EXCEPTION 'Refusing migration: % duplicate round_canonical_id values exist. Resolve manually first.', dup_count;
    END IF;
END $$;

-- Drop the non-unique partial index from migration 049 (will be replaced)
DROP INDEX IF EXISTS idx_rounds_canonical_id;

-- Create partial UNIQUE index — enforces uniqueness only for non-NULL rows
CREATE UNIQUE INDEX uniq_rounds_canonical_id
    ON rounds(round_canonical_id)
    WHERE round_canonical_id IS NOT NULL;

COMMENT ON INDEX uniq_rounds_canonical_id IS
    'UNIQUE partial index on round_canonical_id (NULL rows excluded). '
    'Enables INSERT ... ON CONFLICT (round_canonical_id) DO UPDATE pattern '
    'in Phase 3 layer B. See docs/ADR_round_canonical_id.md.';

COMMIT;
