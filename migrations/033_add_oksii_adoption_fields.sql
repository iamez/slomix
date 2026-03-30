-- Migration 033: Oksii Stats Adoption — new context fields for KIS v2
-- Adds killer_health, alive_count, reinforcement timing to proximity tables
-- Adds corresponding multiplier columns to storytelling_kill_impact
-- Adds session_round_scores table for BOX scoring

BEGIN;

-- ========== PROXIMITY COMBAT POSITION — new Oksii fields ==========
ALTER TABLE proximity_combat_position
    ADD COLUMN IF NOT EXISTS killer_health INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS axis_alive INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS allies_alive INTEGER DEFAULT 0;

-- ========== PROXIMITY SPAWN TIMING — raw reinforcement seconds ==========
ALTER TABLE proximity_spawn_timing
    ADD COLUMN IF NOT EXISTS killer_reinf REAL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS victim_reinf REAL DEFAULT 0;

-- ========== STORYTELLING KILL IMPACT — new multiplier columns ==========
ALTER TABLE storytelling_kill_impact
    ADD COLUMN IF NOT EXISTS health_multiplier REAL DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS alive_multiplier REAL DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS reinf_multiplier REAL DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS killer_health INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS axis_alive INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS allies_alive INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS victim_reinf REAL DEFAULT 0;

-- ========== BOX SCORING — per-round team scores ==========
CREATE TABLE IF NOT EXISTS session_round_scores (
    id SERIAL PRIMARY KEY,
    gaming_session_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    map_name VARCHAR(64) NOT NULL,
    round_date DATE,

    -- Stopwatch state
    round_stopwatch_state VARCHAR(16),  -- FULL_HOLD, TIME_SET, null
    actual_time_seconds INTEGER,
    time_to_beat_seconds INTEGER,

    -- Team scores (BOX system: 2pt/win, 1pt/draw)
    team_a_name VARCHAR(64),
    team_b_name VARCHAR(64),
    team_a_round_points INTEGER DEFAULT 0,
    team_b_round_points INTEGER DEFAULT 0,
    round_winner VARCHAR(64),  -- team name or 'draw'

    -- Cumulative map scores
    team_a_map_points INTEGER DEFAULT 0,
    team_b_map_points INTEGER DEFAULT 0,
    map_winner VARCHAR(64),    -- only set on R2

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gaming_session_id, round_number, map_name)
);

CREATE INDEX IF NOT EXISTS idx_srs_session ON session_round_scores(gaming_session_id);
CREATE INDEX IF NOT EXISTS idx_srs_date ON session_round_scores(round_date);

COMMIT;
