-- Migration: 002_add_lua_round_teams_table.sql
-- Purpose: Store team composition data captured by Lua webhook at round end
-- This data is separate from stats file parsing - it's real-time capture from game engine
--
-- Created: 2026-01-22
-- Part of: Lua Webhook Feature (SESSION_2026-01-22_LUA_WEBHOOK_FEATURE.md)

-- Table to store Lua-captured team composition per round
-- Links to rounds table via match_id + round_number (same pattern as other tables)
CREATE TABLE IF NOT EXISTS lua_round_teams (
    id SERIAL PRIMARY KEY,

    -- Link to the round (same keys used in rounds table)
    match_id VARCHAR(64) NOT NULL,
    round_number INTEGER NOT NULL,

    -- Team composition as JSON arrays
    -- Format: [{"guid":"ABC123...","name":"PlayerName"}, ...]
    axis_players JSONB DEFAULT '[]'::jsonb,
    allies_players JSONB DEFAULT '[]'::jsonb,

    -- Timing metadata from Lua (duplicated here for easy access, also in rounds table)
    round_start_unix BIGINT,
    round_end_unix BIGINT,
    actual_duration_seconds INTEGER,
    total_pause_seconds INTEGER DEFAULT 0,
    pause_count INTEGER DEFAULT 0,
    end_reason VARCHAR(20),

    -- Winner from game engine (1=Axis, 2=Allies, 0=unknown)
    winner_team INTEGER,

    -- Defender team for stopwatch mode (1=Axis, 2=Allies)
    defender_team INTEGER,

    -- Map info for reference
    map_name VARCHAR(64),
    time_limit_minutes INTEGER,

    -- Metadata
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    lua_version VARCHAR(16),

    -- Ensure one record per round
    UNIQUE(match_id, round_number)
);

-- Index for fast lookups by match
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_match_id ON lua_round_teams(match_id);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_captured_at ON lua_round_teams(captured_at);

-- Add comments for documentation
COMMENT ON TABLE lua_round_teams IS 'Team composition and timing data captured by Lua webhook at round end. Separate from stats file parsing - this is real-time game engine data.';
COMMENT ON COLUMN lua_round_teams.axis_players IS 'JSON array of players on Axis team: [{"guid":"...","name":"..."}]';
COMMENT ON COLUMN lua_round_teams.allies_players IS 'JSON array of players on Allies team: [{"guid":"...","name":"..."}]';
COMMENT ON COLUMN lua_round_teams.actual_duration_seconds IS 'Accurate round duration from Lua - fixes surrender timing bug';
COMMENT ON COLUMN lua_round_teams.end_reason IS 'How round ended: objective, surrender, time_expired';
