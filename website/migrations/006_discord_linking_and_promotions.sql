-- ============================================================================
-- Migration 006: Discord Account Linking + Promotion Campaign Scheduler
-- ============================================================================
-- Adds persistent website user identity rows, Discord account metadata,
-- explicit user->player mapping, audited link events, promotion preferences,
-- and campaign/job/send-log tables for scheduled outreach.
-- ============================================================================

CREATE TABLE IF NOT EXISTS website_users (
    id BIGINT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS discord_accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE CASCADE,
    discord_user_id BIGINT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    display_name TEXT,
    avatar TEXT,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS user_player_links (
    user_id BIGINT PRIMARY KEY REFERENCES website_users(id) ON DELETE CASCADE,
    player_guid TEXT NOT NULL UNIQUE,
    player_name TEXT,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS account_link_audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    discord_user_id BIGINT,
    action TEXT NOT NULL CHECK (
        action IN (
            'discord_linked',
            'discord_unlinked',
            'player_linked',
            'player_unlinked',
            'player_changed'
        )
    ),
    actor_discord_id BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscription_preferences (
    user_id BIGINT PRIMARY KEY REFERENCES website_users(id) ON DELETE CASCADE,
    allow_promotions BOOLEAN NOT NULL DEFAULT FALSE,
    preferred_channel TEXT NOT NULL DEFAULT 'any' CHECK (
        preferred_channel IN ('discord', 'telegram', 'signal', 'any')
    ),
    telegram_handle_encrypted TEXT,
    signal_handle_encrypted TEXT,
    quiet_hours JSONB NOT NULL DEFAULT '{}'::jsonb,
    timezone TEXT NOT NULL DEFAULT 'Europe/Ljubljana',
    notify_threshold INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS availability_promotion_campaigns (
    id BIGSERIAL PRIMARY KEY,
    campaign_date DATE NOT NULL,
    target_timezone TEXT NOT NULL DEFAULT 'Europe/Ljubljana',
    target_start_time TIME NOT NULL DEFAULT '21:00',
    initiated_by_user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE RESTRICT,
    initiated_by_discord_id BIGINT NOT NULL,
    include_maybe BOOLEAN NOT NULL DEFAULT FALSE,
    include_available BOOLEAN NOT NULL DEFAULT FALSE,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (
        status IN (
            'scheduled',
            'running',
            'sent',
            'followup_sent',
            'partial',
            'failed',
            'cancelled'
        )
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

CREATE INDEX IF NOT EXISTS idx_discord_accounts_discord_id ON discord_accounts(discord_user_id);
CREATE INDEX IF NOT EXISTS idx_user_player_links_player_guid ON user_player_links(player_guid);
CREATE INDEX IF NOT EXISTS idx_account_link_audit_user ON account_link_audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscription_preferences_allow_promotions ON subscription_preferences(allow_promotions);
CREATE INDEX IF NOT EXISTS idx_promotion_campaigns_date ON availability_promotion_campaigns(campaign_date DESC);
CREATE INDEX IF NOT EXISTS idx_promotion_campaigns_status ON availability_promotion_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_promotion_jobs_due ON availability_promotion_jobs(status, run_at ASC);
CREATE INDEX IF NOT EXISTS idx_promotion_send_logs_campaign ON availability_promotion_send_logs(campaign_id, created_at DESC);
