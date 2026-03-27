-- Migration 032: Kill Impact Score (KIS) — Smart Storytelling Stats Phase 1
-- Materialized per-kill impact scores with context multipliers

CREATE TABLE IF NOT EXISTS storytelling_kill_impact (
    id SERIAL PRIMARY KEY,
    kill_outcome_id INTEGER REFERENCES proximity_kill_outcome(id) ON DELETE CASCADE,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    killer_guid VARCHAR(32) NOT NULL,
    killer_name VARCHAR(64) DEFAULT '',
    victim_guid VARCHAR(32) NOT NULL,
    victim_name VARCHAR(64) DEFAULT '',

    -- Impact multipliers (each 1.0 = neutral)
    base_impact REAL NOT NULL DEFAULT 1.0,
    carrier_multiplier REAL DEFAULT 1.0,
    push_multiplier REAL DEFAULT 1.0,
    crossfire_multiplier REAL DEFAULT 1.0,
    spawn_multiplier REAL DEFAULT 1.0,
    outcome_multiplier REAL DEFAULT 1.0,
    class_multiplier REAL DEFAULT 1.0,
    distance_multiplier REAL DEFAULT 1.0,
    total_impact REAL NOT NULL,

    -- Context flags
    is_carrier_kill BOOLEAN DEFAULT FALSE,
    is_during_push BOOLEAN DEFAULT FALSE,
    is_crossfire BOOLEAN DEFAULT FALSE,
    is_objective_area BOOLEAN DEFAULT FALSE,
    kill_time_ms INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kill_outcome_id)
);

CREATE INDEX IF NOT EXISTS idx_kis_session ON storytelling_kill_impact(session_date);
CREATE INDEX IF NOT EXISTS idx_kis_killer ON storytelling_kill_impact(killer_guid);
CREATE INDEX IF NOT EXISTS idx_kis_map ON storytelling_kill_impact(map_name);
