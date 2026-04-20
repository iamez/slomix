-- migrations/041_performance_indexes.sql
-- Performance indexes discovered during the Performance Mandelbrot RCA audit
-- (2026-04-20).
--
-- Two missing indexes on hot query paths:
--
-- (1) player_aliases(LOWER(alias)) — functional index for ILIKE / LOWER(...)
--     LIKE queries. Dev DB has ~50k alias rows; bot (!rank, !compare),
--     website autocomplete, and player_resolver_service all do
--     `WHERE LOWER(alias) LIKE LOWER(?)` which currently triggers a full
--     seq scan. Functional btree supports LIKE 'prefix%' and equality
--     when the left side is wrapped in LOWER(). Expected: 50ms → <1ms
--     for single-row alias lookups.
--
-- (2) storytelling_kill_impact(session_date, killer_guid) — composite
--     index for session-scoped detail queries. idx_kis_session and
--     idx_kis_killer already exist separately, but the common detail
--     query pattern filters on both (e.g. "KIS per player in this
--     session") and currently uses a bitmap AND. Composite index turns
--     that into a single index scan. Expected: 200ms → 50ms per
--     per-player query.
--
-- Both are pure additions; existing indexes are kept (no rebuild, no
-- data movement).

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Functional index on player_aliases for LOWER(alias) LIKE / ILIKE
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_player_aliases_alias_lower
    ON player_aliases (LOWER(alias));

-- ---------------------------------------------------------------------------
-- 2. Composite index on storytelling_kill_impact(session_date, killer_guid)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_kis_session_killer
    ON storytelling_kill_impact (session_date, killer_guid);

-- ---------------------------------------------------------------------------
-- Tracker
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('041_performance_indexes', '041_performance_indexes.sql', 'self')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Verification:
--   SELECT indexname FROM pg_indexes
--   WHERE indexname IN (
--       'idx_player_aliases_alias_lower',
--       'idx_kis_session_killer'
--   );
--   -- Expected: 2 rows
--
--   EXPLAIN ANALYZE
--   SELECT guid FROM player_aliases WHERE LOWER(alias) = LOWER('cornporn') LIMIT 1;
--   -- Expected: Index Scan using idx_player_aliases_alias_lower
--
--   EXPLAIN ANALYZE
--   SELECT * FROM storytelling_kill_impact
--   WHERE session_date = '2026-04-15' AND killer_guid = 'abcd1234...';
--   -- Expected: Index Scan using idx_kis_session_killer
