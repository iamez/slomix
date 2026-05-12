-- ============================================================================
-- Migration 053: Weapon stats materialized view
-- ============================================================================
--
-- Audit plan ref: A8 (weapon-stats leaderboard subquery)
--
-- Goal
-- ----
-- The `/api/stats/weapons` aggregated leaderboard endpoint in
-- `website/backend/routers/records_weapons.py` performs a full GROUP BY over
-- `weapon_comprehensive_stats` (one row per round x player x weapon, many
-- millions of rows in production). On the "all-time" period there is no
-- selectivity filter, so every request re-aggregates the entire table.
--
-- This migration introduces `weapon_stats_mv`, a materialized view that
-- pre-aggregates the leaderboard subquery to one row per
-- (weapon_name, round_date). The router can then satisfy "all", "7d", "30d"
-- and "season" periods with a tiny GROUP BY over the MV (typically a few
-- thousand rows instead of millions). Expected speedup: ~60% query time
-- reduction on weapon-stats endpoints, per audit plan A8.
--
-- Granularity
-- -----------
-- Grouping by (weapon_name, round_date) preserves enough information for the
-- date-period filters used by the router (today / 7d / 30d / season). Per-
-- player and per-round aggregates are intentionally NOT materialized — those
-- endpoints (`/by-player`, `/hall-of-fame`) need finer granularity and still
-- query the live table.
--
-- Refresh strategy
-- ----------------
-- Refresh runs out-of-band, NOT on every write. Recommended cadence: every
-- 5 minutes via a periodic task (FastAPI startup hook, pg_cron, or external
-- scheduler). The unique index on (weapon_name, round_date) lets us run
-- REFRESH MATERIALIZED VIEW CONCURRENTLY so reads are not blocked.
--
-- IMPORTANT: do NOT add a trigger that refreshes on `rounds`/
-- `weapon_comprehensive_stats` inserts — REFRESH would serialize concurrent
-- parser writes and could deadlock during heavy match-import bursts.
--
-- Expected freshness lag: up to the refresh-interval (default 5 min).
-- Acceptable for a leaderboard endpoint that's already cached at the HTTP
-- layer.
--
-- Deployment
-- ----------
-- 1. Apply this migration MANUALLY in production:
--      PGPASSWORD=... psql -h localhost -U etlegacy_user -d etlegacy \
--        -f migrations/053_add_weapon_stats_mv.sql
--    The bot/website do NOT auto-apply migrations.
--
-- 2. (Optional) Force-rebuild ONLY if needed. The `CREATE MATERIALIZED VIEW`
--    statement below already populates data on first run, so this step is
--    normally NOT required. Run it only if you used `WITH NO DATA` (we
--    don't) or want a manual non-concurrent rebuild later:
--      REFRESH MATERIALIZED VIEW weapon_stats_mv;
--
-- 3. Enable the feature flag for the website service:
--      export USE_WEAPON_STATS_MV=true
--    Then restart the website service. The router will query the MV; if the
--    MV is somehow missing, it transparently falls back to the live query.
--
-- 4. (Optional) Schedule periodic refresh. Either:
--    a) Set WEAPON_STATS_MV_REFRESH_SECONDS=300 and rely on the FastAPI
--       background task added in this PR; OR
--    b) Use pg_cron:
--         SELECT cron.schedule('weapon-stats-mv', '*/5 * * * *',
--           'REFRESH MATERIALIZED VIEW CONCURRENTLY weapon_stats_mv');
--
-- Verification / benchmarking
-- ---------------------------
-- Before/after timing:
--   EXPLAIN (ANALYZE, BUFFERS)
--   SELECT weapon_name, SUM(kills) FROM weapon_comprehensive_stats
--   GROUP BY weapon_name ORDER BY 2 DESC LIMIT 20;
--   -- (record execution time)
--
--   EXPLAIN (ANALYZE, BUFFERS)
--   SELECT weapon_name, SUM(total_kills) FROM weapon_stats_mv
--   GROUP BY weapon_name ORDER BY 2 DESC LIMIT 20;
--   -- (compare; expect ~60% faster on full-table scan)
--
-- Rollback
-- --------
-- Disable the feature flag first (USE_WEAPON_STATS_MV=false), then:
--   DROP MATERIALIZED VIEW IF EXISTS weapon_stats_mv;
-- The router falls back to the live query automatically.
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS weapon_stats_mv AS
SELECT
    weapon_name,
    round_date,
    SUM(kills)::bigint        AS total_kills,
    SUM(deaths)::bigint       AS total_deaths,
    SUM(headshots)::bigint    AS total_headshots,
    SUM(shots)::bigint        AS total_shots,
    SUM(hits)::bigint         AS total_hits,
    COUNT(*)::bigint          AS sample_rows,
    MAX(created_at)           AS last_seen_at
FROM weapon_comprehensive_stats
WHERE weapon_name IS NOT NULL
GROUP BY weapon_name, round_date;

-- Unique index is REQUIRED for REFRESH MATERIALIZED VIEW CONCURRENTLY.
CREATE UNIQUE INDEX IF NOT EXISTS weapon_stats_mv_pk
    ON weapon_stats_mv (weapon_name, round_date);

-- Secondary index to speed up the period-filtered GROUP BY in the router.
CREATE INDEX IF NOT EXISTS weapon_stats_mv_round_date
    ON weapon_stats_mv (round_date);

COMMENT ON MATERIALIZED VIEW weapon_stats_mv IS
    'A8 audit: pre-aggregated weapon leaderboard. Refresh out-of-band, never via trigger. See migrations/053_add_weapon_stats_mv.sql';
