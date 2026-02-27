-- Migration: 008_add_lua_spawn_stats.sql
-- Purpose: Store per-player spawn/death timing captured by stats_discord_webhook.lua (v1.6.0)
-- Created: 2026-02-06

CREATE TABLE IF NOT EXISTS lua_spawn_stats (
    id SERIAL PRIMARY KEY,

    -- Link to the round (matches lua_round_teams/rounds)
    match_id VARCHAR(64) NOT NULL,
    round_number INTEGER NOT NULL,
    round_id INTEGER,

    -- Round context
    map_name VARCHAR(64),
    round_end_unix BIGINT,

    -- Player identity
    player_guid VARCHAR(32),
    player_name VARCHAR(64),

    -- Spawn/death timing
    spawn_count INTEGER DEFAULT 0,
    death_count INTEGER DEFAULT 0,
    dead_seconds INTEGER DEFAULT 0,
    avg_respawn_seconds INTEGER DEFAULT 0,
    max_respawn_seconds INTEGER DEFAULT 0,

    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(match_id, round_number, player_guid)
);

CREATE INDEX IF NOT EXISTS idx_lua_spawn_stats_match_id ON lua_spawn_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_lua_spawn_stats_round_id ON lua_spawn_stats(round_id);
CREATE INDEX IF NOT EXISTS idx_lua_spawn_stats_round_end ON lua_spawn_stats(round_end_unix);

COMMENT ON TABLE lua_spawn_stats IS 'Per-player spawn/death timing captured by Lua webhook (v1.6.0).';
COMMENT ON COLUMN lua_spawn_stats.dead_seconds IS 'Total time spent dead (seconds) based on death→spawn intervals.';
COMMENT ON COLUMN lua_spawn_stats.avg_respawn_seconds IS 'Average respawn time (dead_seconds / death_count).';
