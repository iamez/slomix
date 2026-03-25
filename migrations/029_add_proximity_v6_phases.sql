-- Migration 029: Add Proximity v6 Phases 1.5-4 Tables
-- Date: 2026-03-25
-- Description: Flag returns, vehicle progress, escort credit, construction events

BEGIN;

-- Table 1: proximity_carrier_return (Phase 1.5 — flag returns)
CREATE TABLE IF NOT EXISTS proximity_carrier_return (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    return_time INTEGER NOT NULL,
    returner_guid VARCHAR(32) NOT NULL,
    returner_name VARCHAR(64) NOT NULL,
    returner_team VARCHAR(10) NOT NULL,
    flag_team VARCHAR(16) NOT NULL,
    original_carrier_guid VARCHAR(32) DEFAULT '',
    drop_time INTEGER NOT NULL,
    return_delay_ms INTEGER NOT NULL DEFAULT 0,
    drop_x INTEGER DEFAULT 0,
    drop_y INTEGER DEFAULT 0,
    drop_z INTEGER DEFAULT 0,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, returner_guid, return_time)
);

CREATE INDEX IF NOT EXISTS idx_carrier_return_session ON proximity_carrier_return(session_date, round_number, round_start_unix);
CREATE INDEX IF NOT EXISTS idx_carrier_return_returner ON proximity_carrier_return(returner_guid);
CREATE INDEX IF NOT EXISTS idx_carrier_return_flag_team ON proximity_carrier_return(flag_team);
CREATE INDEX IF NOT EXISTS idx_carrier_return_map ON proximity_carrier_return(map_name);
CREATE INDEX IF NOT EXISTS idx_carrier_return_round_id ON proximity_carrier_return(round_id) WHERE round_id IS NOT NULL;

-- Table 2: proximity_vehicle_progress (Phase 2)
CREATE TABLE IF NOT EXISTS proximity_vehicle_progress (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    vehicle_name VARCHAR(64) NOT NULL,
    vehicle_type VARCHAR(32) NOT NULL DEFAULT 'script_mover',
    start_x INTEGER DEFAULT 0,
    start_y INTEGER DEFAULT 0,
    start_z INTEGER DEFAULT 0,
    end_x INTEGER DEFAULT 0,
    end_y INTEGER DEFAULT 0,
    end_z INTEGER DEFAULT 0,
    total_distance REAL NOT NULL DEFAULT 0,
    max_health INTEGER DEFAULT 0,
    final_health INTEGER DEFAULT 0,
    destroyed_count INTEGER DEFAULT 0,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, vehicle_name)
);

CREATE INDEX IF NOT EXISTS idx_vehicle_progress_session ON proximity_vehicle_progress(session_date, round_number, round_start_unix);
CREATE INDEX IF NOT EXISTS idx_vehicle_progress_vehicle ON proximity_vehicle_progress(vehicle_name);
CREATE INDEX IF NOT EXISTS idx_vehicle_progress_map ON proximity_vehicle_progress(map_name);
CREATE INDEX IF NOT EXISTS idx_vehicle_progress_round_id ON proximity_vehicle_progress(round_id) WHERE round_id IS NOT NULL;

-- Table 3: proximity_escort_credit (Phase 2)
CREATE TABLE IF NOT EXISTS proximity_escort_credit (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    player_guid VARCHAR(32) NOT NULL,
    player_name VARCHAR(64) NOT NULL,
    player_team VARCHAR(10) NOT NULL,
    vehicle_name VARCHAR(64) NOT NULL,
    mounted_time_ms INTEGER DEFAULT 0,
    proximity_time_ms INTEGER DEFAULT 0,
    total_escort_distance REAL DEFAULT 0,
    credit_distance REAL DEFAULT 0,
    samples INTEGER DEFAULT 0,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, player_guid, vehicle_name)
);

CREATE INDEX IF NOT EXISTS idx_escort_credit_session ON proximity_escort_credit(session_date, round_number, round_start_unix);
CREATE INDEX IF NOT EXISTS idx_escort_credit_player ON proximity_escort_credit(player_guid);
CREATE INDEX IF NOT EXISTS idx_escort_credit_vehicle ON proximity_escort_credit(vehicle_name);
CREATE INDEX IF NOT EXISTS idx_escort_credit_map ON proximity_escort_credit(map_name);
CREATE INDEX IF NOT EXISTS idx_escort_credit_round_id ON proximity_escort_credit(round_id) WHERE round_id IS NOT NULL;

-- Table 4: proximity_construction_event (Phase 3)
CREATE TABLE IF NOT EXISTS proximity_construction_event (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    event_time INTEGER NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    player_guid VARCHAR(32) NOT NULL,
    player_name VARCHAR(64) NOT NULL,
    player_team VARCHAR(10) NOT NULL,
    track_name VARCHAR(64) DEFAULT '',
    player_x INTEGER DEFAULT 0,
    player_y INTEGER DEFAULT 0,
    player_z INTEGER DEFAULT 0,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, player_guid, event_time, event_type)
);

CREATE INDEX IF NOT EXISTS idx_construction_event_session ON proximity_construction_event(session_date, round_number, round_start_unix);
CREATE INDEX IF NOT EXISTS idx_construction_event_player ON proximity_construction_event(player_guid);
CREATE INDEX IF NOT EXISTS idx_construction_event_type ON proximity_construction_event(event_type);
CREATE INDEX IF NOT EXISTS idx_construction_event_track ON proximity_construction_event(track_name);
CREATE INDEX IF NOT EXISTS idx_construction_event_map ON proximity_construction_event(map_name);
CREATE INDEX IF NOT EXISTS idx_construction_event_round_id ON proximity_construction_event(round_id) WHERE round_id IS NOT NULL;

-- Track migration
INSERT INTO schema_migrations (version, filename, applied_at, applied_by, success)
VALUES ('029_v6_phases', '029_add_proximity_v6_phases.sql', NOW(), 'manual', true)
ON CONFLICT (version) DO NOTHING;

COMMIT;
