-- SET QUOTED_IDENTIFIER ON; -- linter hint; migration targets PostgreSQL
-- ============================================================================
-- Migration 005: Date-Based Availability + Multi-Channel Notifications
-- ============================================================================
-- Source-of-truth tables for daily availability and outbound notification safety.
-- ============================================================================

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

CREATE TABLE IF NOT EXISTS availability_user_settings (
    user_id BIGINT PRIMARY KEY,
    sound_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sound_cooldown_seconds INTEGER NOT NULL DEFAULT 480,
    availability_reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

CREATE INDEX IF NOT EXISTS idx_availability_entries_date ON availability_entries(entry_date ASC);
CREATE INDEX IF NOT EXISTS idx_availability_entries_status ON availability_entries(status);
CREATE INDEX IF NOT EXISTS idx_availability_subscriptions_user ON availability_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_availability_channel_links_user ON availability_channel_links(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_ledger_event ON notifications_ledger(event_key);
CREATE INDEX IF NOT EXISTS idx_notifications_ledger_user ON notifications_ledger(user_id);
