-- migrations/036_schema_drift_sync.sql
-- Schema drift sync (batch fix from 2026-04-19 audit).
--
-- Covers 5 separate drift categories discovered during Mega Audit v3+v4 post-mortem:
--   1. session_teams.session_identity — generated column + unique index (runtime-only in team_manager.py)
--   2. round_correlations — full CREATE TABLE (previously only in tools/schema_postgresql.sql, no migration)
--   3. greatshot_analysis.total_kills — column added ad-hoc
--   4. 4 runtime indexes created from Python (availability_notifier, external_channels, processed_files)
--   5. schema_migrations tracker catchup for migrations 030-035 (applied but unrecorded)
--
-- ALL STATEMENTS ARE IDEMPOTENT — safe to run on any DB:
--   - Dev (columns exist): ALTER/CREATE skipped with NOTICE, UPDATE/INSERT no-op
--   - Prod (likely same): same behavior
--   - Fresh install: all objects created cleanly

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. session_teams.session_identity (generated column + unique index)
-- ---------------------------------------------------------------------------
-- Referenced in bot/core/team_manager.py (fallback session lookup).
-- Currently created at bot startup via CREATE TABLE IF NOT EXISTS, but the table
-- ALREADY exists from schema_postgresql.sql (without this column), so the
-- runtime CREATE is a no-op and the column never gets added on fresh installs.

ALTER TABLE session_teams
    ADD COLUMN IF NOT EXISTS session_identity TEXT
    GENERATED ALWAYS AS (COALESCE((gaming_session_id)::text, session_start_date)) STORED;

CREATE UNIQUE INDEX IF NOT EXISTS session_teams_identity_unique
    ON session_teams(session_identity, map_name, team_name);


-- ---------------------------------------------------------------------------
-- 2. round_correlations — full table definition
-- ---------------------------------------------------------------------------
-- Previously only in tools/schema_postgresql.sql. A pure-migration install
-- (no schema file apply) would leave the table missing. 23 original columns +
-- 2 proximity flags added in migration 034.

CREATE TABLE IF NOT EXISTS round_correlations (
    id SERIAL PRIMARY KEY,
    correlation_id VARCHAR(64) UNIQUE NOT NULL,
    match_id VARCHAR(128) NOT NULL,
    map_name VARCHAR(64) NOT NULL,
    r1_round_id INTEGER REFERENCES rounds(id),
    r2_round_id INTEGER REFERENCES rounds(id),
    summary_round_id INTEGER REFERENCES rounds(id),
    r1_lua_teams_id INTEGER REFERENCES lua_round_teams(id),
    r2_lua_teams_id INTEGER REFERENCES lua_round_teams(id),
    has_r1_stats BOOLEAN DEFAULT FALSE,
    has_r2_stats BOOLEAN DEFAULT FALSE,
    has_r1_lua_teams BOOLEAN DEFAULT FALSE,
    has_r2_lua_teams BOOLEAN DEFAULT FALSE,
    has_r1_gametime BOOLEAN DEFAULT FALSE,
    has_r2_gametime BOOLEAN DEFAULT FALSE,
    has_r1_endstats BOOLEAN DEFAULT FALSE,
    has_r2_endstats BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'pending',
    completeness_pct INTEGER DEFAULT 0,
    r1_arrived_at TIMESTAMP,
    r2_arrived_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    has_r1_proximity BOOLEAN DEFAULT FALSE,
    has_r2_proximity BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_round_corr_match_id ON round_correlations(match_id);
CREATE INDEX IF NOT EXISTS idx_round_corr_status ON round_correlations(status);


-- ---------------------------------------------------------------------------
-- 3. greatshot_analysis.total_kills (ad-hoc column, used in UPSERT)
-- ---------------------------------------------------------------------------
-- website/backend/services/greatshot_jobs.py INSERTs this column via ON CONFLICT.
-- Fresh install would fail at first UPSERT.

ALTER TABLE greatshot_analysis
    ADD COLUMN IF NOT EXISTS total_kills INTEGER DEFAULT 0;


-- ---------------------------------------------------------------------------
-- 4. Runtime indexes (currently created in Python at bot/service startup)
-- ---------------------------------------------------------------------------
-- These indexes live only in Python code, so a DB that boots without the bot
-- (e.g., website-only environment, fresh schema apply) misses them.

-- From bot/services/availability_notifier_service.py
CREATE INDEX IF NOT EXISTS idx_notifications_ledger_user_event
    ON notifications_ledger(user_id, event_key);

-- From bot/cogs/availability_mixins/external_channels_mixin.py
CREATE INDEX IF NOT EXISTS idx_availability_promotion_jobs_due
    ON availability_promotion_jobs(status, run_at);

-- From archive/diagnostics/add_processed_files_table.py (archived but applied)
CREATE INDEX IF NOT EXISTS idx_processed_files_success
    ON processed_files(success);
CREATE INDEX IF NOT EXISTS idx_processed_files_success_processed_at
    ON processed_files(success, processed_at);


-- ---------------------------------------------------------------------------
-- 5. schema_migrations tracker catchup
-- ---------------------------------------------------------------------------
-- Migrations 030-035 were applied to dev+prod but never inserted into the
-- schema_migrations tracker. Without these rows, any migration runner would
-- re-run them (safe due to idempotence, but confusing).
-- Also backfills 036 (this migration) for clean tracking.

INSERT INTO schema_migrations (version, filename, applied_by)
VALUES
    ('030_objective_runs', '030_add_proximity_objective_runs.sql', 'drift-catchup-036'),
    ('031_skill_history_session', '031_add_skill_history_session_scope.sql', 'drift-catchup-036'),
    ('032_storytelling_kill_impact', '032_add_storytelling_kill_impact.sql', 'drift-catchup-036'),
    ('033_oksii_adoption', '033_add_oksii_adoption_fields.sql', 'drift-catchup-036'),
    ('034_proximity_correlation_flags', '034_add_proximity_correlation_flags.sql', 'drift-catchup-036'),
    ('035_guid_canonical', '035_add_guid_canonical_columns.sql', 'drift-catchup-036'),
    ('036_schema_drift_sync', '036_schema_drift_sync.sql', 'self')
ON CONFLICT (version) DO NOTHING;


COMMIT;

-- Verification queries (run manually after migration):
--
--   -- (1) session_identity column + unique index exist
--   SELECT column_name, generation_expression FROM information_schema.columns
--    WHERE table_name='session_teams' AND column_name='session_identity';
--   SELECT indexname FROM pg_indexes WHERE indexname='session_teams_identity_unique';
--
--   -- (2) round_correlations has 25 columns
--   SELECT COUNT(*) FROM information_schema.columns
--    WHERE table_name='round_correlations';   -- expect 25
--
--   -- (3) greatshot_analysis.total_kills exists
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name='greatshot_analysis' AND column_name='total_kills';
--
--   -- (4) 4 runtime indexes present
--   SELECT indexname FROM pg_indexes
--    WHERE indexname IN (
--      'idx_notifications_ledger_user_event',
--      'idx_availability_promotion_jobs_due',
--      'idx_processed_files_success',
--      'idx_processed_files_success_processed_at'
--    );
--
--   -- (5) schema_migrations tracker up to 036
--   SELECT version, filename, applied_by FROM schema_migrations
--    WHERE version LIKE '03%' OR version LIKE '035%' OR version LIKE '036%'
--    ORDER BY version;
