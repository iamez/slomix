-- Migration 028: Add Proximity v6 Carrier Intelligence Tables
-- Date: 2026-03-25
-- Description: Carrier event and carrier kill tracking for objective intelligence

BEGIN;

-- Table 1: proximity_carrier_event
-- One row per carrier lifecycle: pickup → outcome (secured/killed/dropped/round_end)
CREATE TABLE IF NOT EXISTS proximity_carrier_event (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    carrier_guid VARCHAR(32) NOT NULL,
    carrier_name VARCHAR(64) NOT NULL,
    carrier_team VARCHAR(10) NOT NULL,
    flag_team VARCHAR(16) NOT NULL,
    pickup_time INTEGER NOT NULL,
    drop_time INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    outcome VARCHAR(16) NOT NULL,
    carry_distance REAL NOT NULL DEFAULT 0,
    beeline_distance REAL NOT NULL DEFAULT 0,
    efficiency REAL NOT NULL DEFAULT 0,
    path_samples INTEGER NOT NULL DEFAULT 0,
    pickup_x INTEGER DEFAULT 0,
    pickup_y INTEGER DEFAULT 0,
    pickup_z INTEGER DEFAULT 0,
    drop_x INTEGER DEFAULT 0,
    drop_y INTEGER DEFAULT 0,
    drop_z INTEGER DEFAULT 0,
    killer_guid VARCHAR(32) DEFAULT '',
    killer_name VARCHAR(64) DEFAULT '',
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, carrier_guid, pickup_time)
);

CREATE INDEX IF NOT EXISTS idx_carrier_event_session ON proximity_carrier_event(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_carrier_event_carrier ON proximity_carrier_event(carrier_guid);
CREATE INDEX IF NOT EXISTS idx_carrier_event_outcome ON proximity_carrier_event(outcome);
CREATE INDEX IF NOT EXISTS idx_carrier_event_map ON proximity_carrier_event(map_name);
CREATE INDEX IF NOT EXISTS idx_carrier_event_round_id ON proximity_carrier_event(round_id) WHERE round_id IS NOT NULL;

-- Table 2: proximity_carrier_kill
-- One row per carrier death caused by an enemy player
CREATE TABLE IF NOT EXISTS proximity_carrier_kill (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    kill_time INTEGER NOT NULL,
    carrier_guid VARCHAR(32) NOT NULL,
    carrier_name VARCHAR(64) NOT NULL,
    carrier_team VARCHAR(10) NOT NULL,
    killer_guid VARCHAR(32) NOT NULL,
    killer_name VARCHAR(64) NOT NULL,
    killer_team VARCHAR(10) NOT NULL,
    means_of_death INTEGER NOT NULL DEFAULT 0,
    carrier_distance_at_kill REAL NOT NULL DEFAULT 0,
    flag_team VARCHAR(16) NOT NULL,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, carrier_guid, kill_time)
);

CREATE INDEX IF NOT EXISTS idx_carrier_kill_session ON proximity_carrier_kill(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_carrier_kill_carrier ON proximity_carrier_kill(carrier_guid);
CREATE INDEX IF NOT EXISTS idx_carrier_kill_killer ON proximity_carrier_kill(killer_guid);
CREATE INDEX IF NOT EXISTS idx_carrier_kill_map ON proximity_carrier_kill(map_name);
CREATE INDEX IF NOT EXISTS idx_carrier_kill_round_id ON proximity_carrier_kill(round_id) WHERE round_id IS NOT NULL;

-- Track migration
INSERT INTO schema_migrations (version, filename, applied_at, applied_by, success)
VALUES ('028_carrier_intel', '028_add_proximity_v6_carrier_intel.sql', NOW(), 'manual', true)
ON CONFLICT (version) DO NOTHING;

COMMIT;
