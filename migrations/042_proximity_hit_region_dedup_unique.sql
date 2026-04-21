-- migrations/042_proximity_hit_region_dedup_unique.sql
-- Dedup proximity_hit_region and enforce natural uniqueness going
-- forward. Discovered during the proximity audit (2026-04-21):
-- the INSERT in proximity/parser/parser.py had no ON CONFLICT target
-- and the table had no UNIQUE constraint beyond the serial PK, so every
-- reimport / parser retry silently duplicated rows.
--
-- Dev DB: 112 410 rows total, 103 514 unique on the 7-column natural
-- key → 8 896 duplicates (≈ 8 %). Duplicates inflate Combat score,
-- headshot rate, weapon accuracy, and any leaderboard aggregating over
-- hit_region totals.
--
-- Strategy:
--   1. Keep the earliest `id` per natural-key group (oldest import).
--   2. DELETE later `id` copies.
--   3. CREATE UNIQUE CONSTRAINT so future INSERTs must go through
--      ON CONFLICT (match added in the parser commit on this PR).
--   4. Tracker INSERT.
--
-- Safe to re-run: the dedup is idempotent once UNIQUE is in place
-- (no duplicates remain). The UNIQUE constraint uses IF NOT EXISTS.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Dedup — keep the earliest row per natural-key group
-- ---------------------------------------------------------------------------
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY session_date, round_number, round_start_unix,
                            attacker_guid, victim_guid, event_time, weapon_id
               ORDER BY id ASC
           ) AS rn
    FROM proximity_hit_region
)
DELETE FROM proximity_hit_region phr
USING ranked
WHERE phr.id = ranked.id
  AND ranked.rn > 1;

-- ---------------------------------------------------------------------------
-- 2. Unique constraint — prevent future duplicates.
--    Named explicitly for schema clarity and easier inspection via
--    `\d proximity_hit_region` / pg_constraint. The parser uses a
--    column-list ON CONFLICT target rather than ON CONSTRAINT, so the
--    name itself is not referenced by code (just by operators).
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'proximity_hit_region_natural_key'
          AND conrelid = 'proximity_hit_region'::regclass
    ) THEN
        ALTER TABLE proximity_hit_region
        ADD CONSTRAINT proximity_hit_region_natural_key
        UNIQUE (session_date, round_number, round_start_unix,
                attacker_guid, victim_guid, event_time, weapon_id);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3. Tracker
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('042_proximity_hit_region_dedup_unique',
        '042_proximity_hit_region_dedup_unique.sql', 'self')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Verification:
--   -- (1) No duplicates remain
--   SELECT session_date, round_number, round_start_unix,
--          attacker_guid, victim_guid, event_time, weapon_id, COUNT(*) c
--   FROM proximity_hit_region
--   GROUP BY 1,2,3,4,5,6,7
--   HAVING COUNT(*) > 1;
--   -- Expected: 0 rows
--
--   -- (2) Constraint present
--   SELECT conname FROM pg_constraint
--   WHERE conname = 'proximity_hit_region_natural_key';
--   -- Expected: 1 row
--
--   -- (3) Dedup row count
--   SELECT COUNT(*) FROM proximity_hit_region;
--   -- Expected: ~103 514 on dev (was 112 410)
