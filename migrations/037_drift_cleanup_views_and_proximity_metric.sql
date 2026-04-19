-- migrations/037_drift_cleanup_views_and_proximity_metric.sql
-- Cleanup of low-priority drifts from 2026-04-19 audit.
--
-- Brings into the MAIN repo's migrations what was previously only defined in
-- the sister `proximity/schema/schema.sql` file:
--   1. `proximity_reaction_metric` table + 3 indexes (41,619 rows in dev DB)
--   2. 4 views: teamplay_leaderboard, best_duos, map_hotspots, session_engagement_summary
--
-- ALL STATEMENTS ARE IDEMPOTENT.
--
-- Not included (future separate PR, requires explicit approval):
--   - DROP COLUMN player_comprehensive_stats.time_dead_minutes_original (dead, always NULL)
--   - DROP TABLE server_status_history_backup_20260207 (orphan backup)
--   - Remove player_synergies reference from disabled synergy_analytics cog

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. proximity_reaction_metric
-- ---------------------------------------------------------------------------
-- Copied from proximity/schema/schema.sql:504 (sister project).
-- The main repo had no CREATE for this table, relying on the sister project
-- to run first. This makes the main install self-contained.

CREATE TABLE IF NOT EXISTS proximity_reaction_metric (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    engagement_id INTEGER NOT NULL,
    target_guid VARCHAR(32) NOT NULL,
    target_name VARCHAR(64) NOT NULL,
    target_team VARCHAR(10) NOT NULL,
    target_class VARCHAR(16) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    num_attackers INTEGER NOT NULL DEFAULT 0,
    return_fire_ms INTEGER,
    dodge_reaction_ms INTEGER,
    support_reaction_ms INTEGER,
    start_time_ms INTEGER NOT NULL DEFAULT 0,
    end_time_ms INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, engagement_id, target_guid)
);

-- Indexes require table ownership. On dev/prod, proximity_reaction_metric is
-- owned by `website_app` (created by the sister proximity project), so
-- etlegacy_user cannot add indexes to it. Skip gracefully if owner mismatch.
-- On fresh install (where etlegacy_user creates the table above), this block
-- runs normally.
DO $$
DECLARE
    t_owner TEXT;
BEGIN
    SELECT tableowner INTO t_owner FROM pg_tables
    WHERE tablename = 'proximity_reaction_metric';

    IF t_owner = CURRENT_USER THEN
        CREATE INDEX IF NOT EXISTS idx_reaction_session
            ON proximity_reaction_metric(session_date, round_number);
        CREATE INDEX IF NOT EXISTS idx_reaction_target
            ON proximity_reaction_metric(target_guid);
        CREATE INDEX IF NOT EXISTS idx_reaction_class
            ON proximity_reaction_metric(target_class);
        RAISE NOTICE 'proximity_reaction_metric: 3 indexes ensured (owner=%)', t_owner;
    ELSE
        RAISE NOTICE 'proximity_reaction_metric: skipping index creation (owner=% != %)',
                     t_owner, CURRENT_USER;
    END IF;
END $$;


-- ---------------------------------------------------------------------------
-- 2. Analytics views (from proximity/schema/schema.sql)
-- ---------------------------------------------------------------------------
-- These 4 views exist in dev DB via the sister project but are not in the
-- main repo's schema. Adding CREATE OR REPLACE ensures idempotence.

-- Note: PostgreSQL ROUND(value, precision) only works with NUMERIC. Source
-- columns here are INTEGER/REAL, so we cast to ::numeric for rounding.

-- Top teamplay (crossfire) leaderboard
CREATE OR REPLACE VIEW teamplay_leaderboard AS
SELECT
    player_name,
    player_guid,
    crossfire_kills,
    crossfire_participations,
    ROUND((100.0 * crossfire_kills / NULLIF(crossfire_participations, 0))::numeric, 1) as crossfire_kill_rate,
    ROUND(avg_crossfire_delay_ms::numeric, 0) as avg_sync_ms,
    solo_kills,
    focus_escapes,
    times_focused,
    ROUND((100.0 * focus_escapes / NULLIF(times_focused, 0))::numeric, 1) as focus_survival_rate
FROM player_teamplay_stats
WHERE crossfire_participations > 0
ORDER BY crossfire_kills DESC;

-- Best duo partners
CREATE OR REPLACE VIEW best_duos AS
SELECT
    player1_name,
    player2_name,
    crossfire_count,
    crossfire_kills,
    ROUND((100.0 * crossfire_kills / NULLIF(crossfire_count, 0))::numeric, 1) as kill_rate,
    ROUND(avg_delay_ms::numeric, 0) as sync_ms,
    games_together
FROM crossfire_pairs
WHERE crossfire_count >= 5
ORDER BY crossfire_kills DESC;

-- Map hotspots (kill/death density grid cells)
CREATE OR REPLACE VIEW map_hotspots AS
SELECT
    map_name,
    grid_x,
    grid_y,
    total_kills,
    total_deaths,
    total_kills + total_deaths as total_combat
FROM map_kill_heatmap
ORDER BY map_name, total_combat DESC;

-- Engagement summary per session+map
CREATE OR REPLACE VIEW session_engagement_summary AS
SELECT
    session_date,
    map_name,
    COUNT(*) as total_engagements,
    SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) as kills,
    SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) as escapes,
    SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) as crossfire_engagements,
    ROUND(AVG(duration_ms)::numeric, 0) as avg_duration_ms,
    ROUND(AVG(num_attackers)::numeric, 2) as avg_attackers
FROM combat_engagement
GROUP BY session_date, map_name
ORDER BY session_date DESC;


-- ---------------------------------------------------------------------------
-- 3. Tracker row
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('037_drift_cleanup_views', '037_drift_cleanup_views_and_proximity_metric.sql', 'self')
ON CONFLICT (version) DO NOTHING;


COMMIT;

-- Verification (run manually after migration):
--
--   SELECT tablename FROM pg_tables WHERE tablename='proximity_reaction_metric';
--   SELECT viewname  FROM pg_views WHERE viewname IN ('teamplay_leaderboard','best_duos','map_hotspots','session_engagement_summary');
--   SELECT version   FROM schema_migrations WHERE version='037_drift_cleanup_views';
