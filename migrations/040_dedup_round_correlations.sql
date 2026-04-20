-- migrations/040_dedup_round_correlations.sql
-- Deduplicate round_correlations rows that share the same (r1_round_id, r2_round_id)
-- and enforce future uniqueness via a partial UNIQUE index.
--
-- Discovered during the Layer 3 Mandelbrot audit (2026-04-20):
-- One (r1, r2) pair can have 4-9 duplicate correlation rows because the
-- correlation service creates a new row per pipeline event (stats R1,
-- stats R2, Lua R1, Lua R2) using slightly different match_id timestamps.
-- The existing ±30s merge window catches most of these, but simultaneous
-- Lua + stats events race past it.
--
-- Effect on analytics: GROUP BY (r1_round_id, r2_round_id) over-counted
-- matches by 4-9x for affected pairs (10 matches on dev DB have 4+ dupes).
--
-- Strategy:
--   1. For each (r1, r2) pair, keep the row with highest completeness_pct
--      (tie-break: earliest created_at).
--   2. Delete the losers (84 rows on dev DB).
--   3. Add partial UNIQUE index so future duplicates are rejected at
--      insert time by the correlation service.
--
-- NOT touched: rows where either FK is NULL (96 `both_null` + 84 `partial`
-- = 180 rows). Those need a separate backfill migration; partial index
-- correctly allows NULL duplicates.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Dedup — DELETE losers using CTE + ROW_NUMBER window function
-- ---------------------------------------------------------------------------
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY r1_round_id, r2_round_id
               ORDER BY completeness_pct DESC NULLS LAST,
                        created_at ASC
           ) AS rn
    FROM round_correlations
    WHERE r1_round_id IS NOT NULL
      AND r2_round_id IS NOT NULL
)
DELETE FROM round_correlations rc
USING ranked
WHERE rc.id = ranked.id
  AND ranked.rn > 1;

-- ---------------------------------------------------------------------------
-- 2. Partial UNIQUE index — enforce future (r1, r2) uniqueness
--    NULL pairs are allowed (multiple pending correlations may still be
--    created before rounds land; the partial WHERE clause excludes them).
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS round_correlations_r1_r2_unique
    ON round_correlations(r1_round_id, r2_round_id)
    WHERE r1_round_id IS NOT NULL
      AND r2_round_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. Tracker
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('040_dedup_round_correlations', '040_dedup_round_correlations.sql', 'self')
ON CONFLICT (version) DO NOTHING;


COMMIT;

-- Verification:
--   -- (1) No duplicate matched pairs remain
--   SELECT r1_round_id, r2_round_id, COUNT(*) c
--   FROM round_correlations
--   WHERE r1_round_id IS NOT NULL AND r2_round_id IS NOT NULL
--   GROUP BY r1_round_id, r2_round_id
--   HAVING COUNT(*) > 1;
--   -- Expected: 0 rows
--
--   -- (2) Partial unique index present
--   SELECT indexname FROM pg_indexes
--   WHERE indexname='round_correlations_r1_r2_unique';
--   -- Expected: 1 row
--
--   -- (3) NULL rows untouched
--   SELECT COUNT(*) FROM round_correlations
--   WHERE r1_round_id IS NULL OR r2_round_id IS NULL;
--   -- Expected: ~180 rows (unchanged)
