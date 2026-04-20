-- migrations/038_add_player_track_round_linkage.sql
-- Add round-linkage columns to player_track — were added ad-hoc on dev DB
-- during Lua v6 integration but never committed to migrations/.
--
-- Discovered 2026-04-19 during post-Mega-Audit schema drift sweep:
--   /api/proximity/round/{round_id}/tracks queries `WHERE pt.round_id = $1`
--   but the column was missing on slomix_vm, causing UndefinedColumnError
--   on any call to this endpoint.
--
-- IDEMPOTENT (all IF NOT EXISTS / WHERE guards):
--   - Dev DB already has columns populated → UPDATE 0 rows
--   - VM DB missing columns → CREATE + backfill
--   - Re-run on either: safe

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Add round-linkage columns
-- ---------------------------------------------------------------------------
ALTER TABLE player_track
    ADD COLUMN IF NOT EXISTS round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL;
ALTER TABLE player_track
    ADD COLUMN IF NOT EXISTS round_link_source VARCHAR(32);
ALTER TABLE player_track
    ADD COLUMN IF NOT EXISTS round_link_reason VARCHAR(64);
ALTER TABLE player_track
    ADD COLUMN IF NOT EXISTS round_linked_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_player_track_round_id
    ON player_track(round_id);


-- ---------------------------------------------------------------------------
-- 2. Backfill round_id for existing rows
-- ---------------------------------------------------------------------------
-- Match on round_start_unix + trimmed session_date + map_name. On rows where
-- no match exists (bot rounds, surrender edge cases, subst-only rounds),
-- round_id remains NULL — calling code already handles this gracefully.

DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    WITH matched AS (
        UPDATE player_track pt
        SET round_id = r.id,
            round_link_source = 'migration_038_backfill',
            round_link_reason = 'session_date+round_start_unix+map_name match',
            round_linked_at = CURRENT_TIMESTAMP
        FROM rounds r
        WHERE pt.round_id IS NULL
          AND pt.round_start_unix IS NOT NULL
          AND pt.round_start_unix = r.round_start_unix
          AND pt.session_date::text = SUBSTR(r.round_date, 1, 10)
          AND pt.map_name = r.map_name
        RETURNING 1
    )
    SELECT COUNT(*) INTO updated_count FROM matched;
    RAISE NOTICE 'player_track round_id backfill: updated % rows', updated_count;
END $$;


-- ---------------------------------------------------------------------------
-- 3. Tracker
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('038_player_track_round_linkage', '038_add_player_track_round_linkage.sql', 'self')
ON CONFLICT (version) DO NOTHING;


COMMIT;

-- Verification queries (run manually after migration):
--
--   -- (1) 4 new columns present
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name='player_track' AND column_name IN
--      ('round_id','round_link_source','round_link_reason','round_linked_at')
--    ORDER BY column_name;   -- expect 4 rows
--
--   -- (2) Index present
--   SELECT indexname FROM pg_indexes WHERE indexname='idx_player_track_round_id';
--
--   -- (3) Backfill coverage
--   SELECT COUNT(*) AS total,
--          COUNT(round_id) AS linked,
--          ROUND(100.0 * COUNT(round_id) / NULLIF(COUNT(*), 0), 1) AS linked_pct
--   FROM player_track;
--
--   -- (4) Tracker row
--   SELECT version, filename, applied_by FROM schema_migrations
--    WHERE version = '038_player_track_round_linkage';
