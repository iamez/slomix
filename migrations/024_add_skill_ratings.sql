-- Migration 024: Add skill rating tables
-- Date: 2026-03-23
-- Description: Individual performance rating system (Option C from research).
--   Stores per-player aggregate ratings + per-round rating history.
--   Completely isolated - does not modify any existing tables.

BEGIN;

-- Aggregate skill rating per player (latest computed rating)
CREATE TABLE IF NOT EXISTS player_skill_ratings (
    player_guid TEXT PRIMARY KEY,
    display_name TEXT,
    et_rating REAL NOT NULL DEFAULT 0,
    rating_class TEXT DEFAULT 'unknown',
    games_rated INTEGER DEFAULT 0,
    last_rated_at TIMESTAMPTZ DEFAULT NOW(),
    components JSONB DEFAULT '{}'
);

-- Per-round rating history for trend tracking
CREATE TABLE IF NOT EXISTS player_skill_history (
    id SERIAL PRIMARY KEY,
    player_guid TEXT NOT NULL,
    round_id INTEGER,
    et_rating REAL NOT NULL,
    components JSONB DEFAULT '{}',
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skill_ratings_rating ON player_skill_ratings(et_rating DESC);
CREATE INDEX IF NOT EXISTS idx_skill_history_guid ON player_skill_history(player_guid);
CREATE INDEX IF NOT EXISTS idx_skill_history_date ON player_skill_history(calculated_at DESC);

COMMIT;
