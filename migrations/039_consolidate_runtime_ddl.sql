-- migrations/039_consolidate_runtime_ddl.sql
-- Consolidate 15+ CREATE TABLE / CREATE INDEX statements that were previously
-- embedded in Python service/cog startup code into a single committed migration.
--
-- Discovered during the full-pipeline Mandelbrot RCA audit (2026-04-20):
-- the schema_postgresql.sql reference file declared only ~37 tables while the
-- live DB has 95 — the gap was partly covered by Python code that runs at
-- bot startup (CREATE TABLE IF NOT EXISTS calls in various services). That
-- works for existing deployments, but a fresh install that applies
-- `migrations/*.sql` **without** the bot booting would miss these tables.
-- Now every table has a committed migration.
--
-- **Source locations** (for audit trail):
--   - `bot/services/matchup_analytics_service.py:875-897`
--   - `bot/services/availability_notifier_service.py:109-166`
--   - `bot/services/monitoring_service.py:85-116`
--   - `bot/core/team_manager.py:49-65` (session_teams — also in schema_postgresql.sql)
--   - `bot/cogs/availability_mixins/external_channels_mixin.py:35-136`
--   - `bot/cogs/availability_mixins/daily_poll_mixin.py:32-76`
--   - `bot/cogs/team_management_cog.py:38-...` (session_teams duplicate)
--
-- ALL STATEMENTS ARE IDEMPOTENT.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. matchup_history (from matchup_analytics_service.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matchup_history (
    id SERIAL PRIMARY KEY,
    matchup_id TEXT NOT NULL,
    lineup_a_hash TEXT NOT NULL,
    lineup_b_hash TEXT NOT NULL,
    lineup_a_guids JSONB NOT NULL,
    lineup_b_guids JSONB NOT NULL,
    session_date TEXT NOT NULL,
    gaming_session_id INTEGER NOT NULL,
    winner_lineup_hash TEXT,
    lineup_a_score INTEGER DEFAULT 0,
    lineup_b_score INTEGER DEFAULT 0,
    map_name TEXT,
    player_stats JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(session_date, gaming_session_id, matchup_id)
);
CREATE INDEX IF NOT EXISTS idx_matchup_history_matchup_id ON matchup_history(matchup_id);
CREATE INDEX IF NOT EXISTS idx_matchup_history_session_date ON matchup_history(session_date);
CREATE INDEX IF NOT EXISTS idx_matchup_history_map ON matchup_history(map_name);


-- ---------------------------------------------------------------------------
-- 2. availability notifier tables (from availability_notifier_service.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS availability_channel_links (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    channel_type TEXT NOT NULL CHECK (channel_type IN ('discord', 'telegram', 'signal')),
    destination TEXT,
    verification_token_hash TEXT,
    token_expires_at TIMESTAMP,
    verification_requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, channel_type)
);

CREATE TABLE IF NOT EXISTS availability_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    channel_type TEXT NOT NULL CHECK (channel_type IN ('discord', 'telegram', 'signal')),
    channel_address TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    verified_at TIMESTAMP,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, channel_type)
);

CREATE TABLE IF NOT EXISTS notifications_ledger (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    event_key TEXT NOT NULL,
    channel_type TEXT NOT NULL CHECK (channel_type IN ('discord', 'telegram', 'signal')),
    sent_at TIMESTAMP,
    message_id TEXT,
    error TEXT,
    retries INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, event_key, channel_type)
);

CREATE INDEX IF NOT EXISTS idx_notifications_ledger_user_event
    ON notifications_ledger(user_id, event_key);
CREATE INDEX IF NOT EXISTS idx_availability_subscriptions_user
    ON availability_subscriptions(user_id);


-- ---------------------------------------------------------------------------
-- 3. server_status_history, voice_status_history (from monitoring_service.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS server_status_history (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    player_count INTEGER DEFAULT 0,
    max_players INTEGER DEFAULT 0,
    map_name TEXT,
    hostname TEXT,
    players JSONB,
    ping_ms INTEGER DEFAULT 0,
    online BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS voice_status_history (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    member_count INTEGER DEFAULT 0,
    channel_id BIGINT,
    channel_name TEXT,
    members JSONB,
    first_joiner_id BIGINT,
    first_joiner_name TEXT
);


-- ---------------------------------------------------------------------------
-- 4. availability entries + promotion + subscription prefs
--    (from external_channels_mixin.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS availability_entries (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_name TEXT,
    entry_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('LOOKING', 'AVAILABLE', 'MAYBE', 'NOT_PLAYING')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, entry_date)
);
CREATE INDEX IF NOT EXISTS idx_availability_entries_date
    ON availability_entries(entry_date);

CREATE TABLE IF NOT EXISTS availability_promotion_campaigns (
    id BIGSERIAL PRIMARY KEY,
    campaign_date DATE NOT NULL,
    target_timezone TEXT NOT NULL DEFAULT 'Europe/Ljubljana',
    target_start_time TIME NOT NULL DEFAULT '21:00',
    initiated_by_user_id BIGINT NOT NULL,
    initiated_by_discord_id BIGINT NOT NULL,
    include_maybe BOOLEAN NOT NULL DEFAULT FALSE,
    include_available BOOLEAN NOT NULL DEFAULT FALSE,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (
        status IN ('scheduled', 'running', 'sent', 'followup_sent', 'partial', 'failed', 'cancelled')
    ),
    idempotency_key TEXT NOT NULL,
    recipient_count INTEGER NOT NULL DEFAULT 0,
    channels_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    recipients_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (campaign_date, initiated_by_user_id),
    UNIQUE (campaign_date, idempotency_key)
);

CREATE TABLE IF NOT EXISTS availability_promotion_jobs (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES availability_promotion_campaigns(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL CHECK (
        job_type IN ('send_reminder_2045', 'send_start_2100', 'voice_check_2100')
    ),
    run_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'sent', 'skipped', 'failed')
    ),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    last_error TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (campaign_id, job_type)
);
CREATE INDEX IF NOT EXISTS idx_availability_promotion_jobs_due
    ON availability_promotion_jobs(status, run_at);

CREATE TABLE IF NOT EXISTS availability_promotion_send_logs (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES availability_promotion_campaigns(id) ON DELETE CASCADE,
    job_id BIGINT REFERENCES availability_promotion_jobs(id) ON DELETE SET NULL,
    user_id BIGINT NOT NULL,
    channel_type TEXT NOT NULL CHECK (channel_type IN ('discord', 'telegram', 'signal')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed', 'skipped')),
    message_id TEXT,
    error TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscription_preferences (
    user_id BIGINT PRIMARY KEY,
    allow_promotions BOOLEAN NOT NULL DEFAULT FALSE,
    preferred_channel TEXT NOT NULL DEFAULT 'any'
        CHECK (preferred_channel IN ('discord', 'telegram', 'signal', 'any')),
    telegram_handle_encrypted TEXT,
    signal_handle_encrypted TEXT,
    quiet_hours JSONB NOT NULL DEFAULT '{}'::jsonb,
    timezone TEXT NOT NULL DEFAULT 'Europe/Ljubljana',
    notify_threshold INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ---------------------------------------------------------------------------
-- 5. daily polls + responses + reminder prefs (from daily_poll_mixin.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_polls (
    id SERIAL PRIMARY KEY,
    poll_date DATE NOT NULL UNIQUE,
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL UNIQUE,
    guild_id BIGINT NOT NULL,
    threshold_reached BOOLEAN DEFAULT FALSE,
    threshold_notified_at TIMESTAMP,
    reminder_sent_at TIMESTAMP,
    event_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS poll_responses (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER NOT NULL,
    discord_user_id BIGINT NOT NULL,
    discord_username TEXT,
    response_type TEXT NOT NULL CHECK (response_type IN ('yes', 'no', 'tentative')),
    responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(poll_id, discord_user_id)
);

CREATE TABLE IF NOT EXISTS poll_reminder_preferences (
    discord_user_id BIGINT PRIMARY KEY,
    discord_username TEXT,
    threshold_notify BOOLEAN DEFAULT TRUE,
    game_time_notify BOOLEAN DEFAULT TRUE,
    notify_method TEXT DEFAULT 'dm' CHECK (notify_method IN ('dm', 'channel', 'none')),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_daily_polls_date
    ON daily_polls(poll_date DESC);
CREATE INDEX IF NOT EXISTS idx_poll_responses_poll
    ON poll_responses(poll_id);
CREATE INDEX IF NOT EXISTS idx_poll_responses_user
    ON poll_responses(discord_user_id);
CREATE INDEX IF NOT EXISTS idx_poll_responses_type
    ON poll_responses(response_type);


-- ---------------------------------------------------------------------------
-- 6. Tracker
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('039_consolidate_runtime_ddl', '039_consolidate_runtime_ddl.sql', 'self')
ON CONFLICT (version) DO NOTHING;


COMMIT;

-- Verification:
--   SELECT COUNT(*) FROM information_schema.tables
--    WHERE table_schema='public'
--      AND table_name IN (
--        'matchup_history',
--        'availability_channel_links', 'availability_subscriptions',
--        'notifications_ledger',
--        'server_status_history', 'voice_status_history',
--        'availability_entries', 'availability_promotion_campaigns',
--        'availability_promotion_jobs', 'availability_promotion_send_logs',
--        'subscription_preferences',
--        'daily_polls', 'poll_responses', 'poll_reminder_preferences'
--      );
--   -- Expected: 14
