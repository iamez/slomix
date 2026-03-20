-- Migration 019: Add proximity_focus_fire table
-- Date: 2026-03-20
-- Description: Stores per-engagement focus fire events parsed from Lua
--   FOCUS_FIRE section. Tracks coordinated multi-attacker damage bursts
--   with a composite score (timing_tightness*0.6 + dps_score*0.4).

BEGIN;

CREATE TABLE IF NOT EXISTS proximity_focus_fire (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    engagement_id INTEGER NOT NULL,
    target_guid VARCHAR(32) NOT NULL,
    target_name VARCHAR(64) NOT NULL,
    attacker_count INTEGER NOT NULL,
    attacker_guids TEXT NOT NULL,
    total_damage INTEGER NOT NULL,
    duration INTEGER NOT NULL,
    focus_score REAL NOT NULL,
    round_id INTEGER REFERENCES rounds(id),
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, engagement_id)
);

CREATE INDEX IF NOT EXISTS idx_focus_fire_target ON proximity_focus_fire(target_guid);
CREATE INDEX IF NOT EXISTS idx_focus_fire_map ON proximity_focus_fire(map_name);
CREATE INDEX IF NOT EXISTS idx_focus_fire_round ON proximity_focus_fire(round_id);
CREATE INDEX IF NOT EXISTS idx_focus_fire_score ON proximity_focus_fire(focus_score DESC);

COMMIT;
