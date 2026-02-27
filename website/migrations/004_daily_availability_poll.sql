-- ============================================================================
-- Migration 004: Daily Availability Poll + Reminders
-- ============================================================================
-- Adds tables for the daily "Who can play tonight?" Discord poll system.
-- Tracks poll messages, user responses, and notification preferences.
-- ============================================================================

-- Daily polls: One row per daily poll message
CREATE TABLE IF NOT EXISTS daily_polls (
    id SERIAL PRIMARY KEY,
    poll_date DATE NOT NULL UNIQUE,               -- One poll per day
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL UNIQUE,
    guild_id BIGINT NOT NULL,
    threshold_reached BOOLEAN DEFAULT FALSE,       -- Has YES count hit threshold?
    threshold_notified_at TIMESTAMP,               -- When threshold notification was sent
    reminder_sent_at TIMESTAMP,                    -- When game-time reminder was sent
    event_id BIGINT,                               -- Discord Scheduled Event ID (if created)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Poll responses: Tracks each user's reaction
CREATE TABLE IF NOT EXISTS poll_responses (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER NOT NULL REFERENCES daily_polls(id) ON DELETE CASCADE,
    discord_user_id BIGINT NOT NULL,
    discord_username TEXT,
    response_type TEXT NOT NULL CHECK (response_type IN ('yes', 'no', 'tentative')),
    responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(poll_id, discord_user_id)               -- One response per user per poll
);

-- Reminder preferences: Per-user opt-in for notifications
CREATE TABLE IF NOT EXISTS poll_reminder_preferences (
    discord_user_id BIGINT PRIMARY KEY,
    discord_username TEXT,
    threshold_notify BOOLEAN DEFAULT TRUE,         -- Notify when threshold reached
    game_time_notify BOOLEAN DEFAULT TRUE,         -- Notify at game start time
    notify_method TEXT DEFAULT 'dm' CHECK (notify_method IN ('dm', 'channel', 'none')),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_daily_polls_date ON daily_polls(poll_date DESC);
CREATE INDEX IF NOT EXISTS idx_poll_responses_poll ON poll_responses(poll_id);
CREATE INDEX IF NOT EXISTS idx_poll_responses_user ON poll_responses(discord_user_id);
CREATE INDEX IF NOT EXISTS idx_poll_responses_type ON poll_responses(response_type);
