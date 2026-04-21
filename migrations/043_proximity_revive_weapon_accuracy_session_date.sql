-- migrations/043_proximity_revive_weapon_accuracy_session_date.sql
-- Add `session_date` to proximity_revive and proximity_weapon_accuracy
-- so their endpoints can scope by play time instead of DB ingest time
-- (audit P8, 2026-04-21).
--
-- Both tables were created with only `round_id` + `map_name` +
-- `created_at`. The `/api/proximity-revives` and weapon-accuracy
-- endpoints then filtered `created_at >= CURRENT_DATE - Nd`, which
-- silently drifts whenever a parser replay or backfill rewrites
-- `created_at = NOW()` — rows appear in/out of the window based on
-- ingest time, not when the round was actually played.
--
-- Adding `session_date` as a DATE column backfilled from `rounds.round_date`
-- via the existing `round_id` FK makes these two tables consistent with
-- every other `proximity_*` table (which already carry session_date) and
-- unlocks a session-time filter in the endpoints.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS + backfill skipped on already-
-- populated rows (WHERE session_date IS NULL).

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. proximity_revive
-- ---------------------------------------------------------------------------
ALTER TABLE proximity_revive
    ADD COLUMN IF NOT EXISTS session_date DATE;

UPDATE proximity_revive pr
SET session_date = CASE
        WHEN r.round_date ~ '^\d{4}-\d{2}-\d{2}'
            THEN SUBSTR(r.round_date, 1, 10)::date
        ELSE NULL
    END
FROM rounds r
WHERE pr.round_id = r.id
  AND pr.session_date IS NULL;

CREATE INDEX IF NOT EXISTS idx_proximity_revive_session_date
    ON proximity_revive (session_date);

-- ---------------------------------------------------------------------------
-- 2. proximity_weapon_accuracy
-- ---------------------------------------------------------------------------
ALTER TABLE proximity_weapon_accuracy
    ADD COLUMN IF NOT EXISTS session_date DATE;

UPDATE proximity_weapon_accuracy pwa
SET session_date = CASE
        WHEN r.round_date ~ '^\d{4}-\d{2}-\d{2}'
            THEN SUBSTR(r.round_date, 1, 10)::date
        ELSE NULL
    END
FROM rounds r
WHERE pwa.round_id = r.id
  AND pwa.session_date IS NULL;

CREATE INDEX IF NOT EXISTS idx_proximity_weapon_accuracy_session_date
    ON proximity_weapon_accuracy (session_date);

-- ---------------------------------------------------------------------------
-- 3. Tracker
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('043_proximity_revive_weapon_accuracy_session_date',
        '043_proximity_revive_weapon_accuracy_session_date.sql',
        'self')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Verification:
--   -- (1) columns present
--   SELECT table_name, column_name
--   FROM information_schema.columns
--   WHERE column_name = 'session_date'
--     AND table_name IN ('proximity_revive', 'proximity_weapon_accuracy');
--   -- Expected: 2 rows
--
--   -- (2) backfill coverage
--   SELECT 'proximity_revive' t,
--          COUNT(*) total,
--          COUNT(*) FILTER (WHERE session_date IS NOT NULL) backfilled
--   FROM proximity_revive
--   UNION ALL
--   SELECT 'proximity_weapon_accuracy',
--          COUNT(*), COUNT(*) FILTER (WHERE session_date IS NOT NULL)
--   FROM proximity_weapon_accuracy;
--   -- Expected: backfilled ≈ total for rows with non-NULL round_id
