-- Migration 013: Add Proximity v5 Teamplay Analytics Tables
-- Date: 2026-02-23
-- Description: Adds 5 new tables for v5 teamplay pipeline

BEGIN;

-- Table 1: proximity_spawn_timing
CREATE TABLE IF NOT EXISTS proximity_spawn_timing (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    killer_guid VARCHAR(32) NOT NULL,
    killer_name VARCHAR(64) NOT NULL,
    killer_team VARCHAR(10) NOT NULL,
    victim_guid VARCHAR(32) NOT NULL,
    victim_name VARCHAR(64) NOT NULL,
    victim_team VARCHAR(10) NOT NULL,
    kill_time INTEGER NOT NULL,
    enemy_spawn_interval INTEGER NOT NULL,
    time_to_next_spawn INTEGER NOT NULL,
    spawn_timing_score REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, killer_guid, victim_guid, kill_time)
);
CREATE INDEX IF NOT EXISTS idx_spawn_timing_session ON proximity_spawn_timing(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_spawn_timing_killer ON proximity_spawn_timing(killer_guid);
CREATE INDEX IF NOT EXISTS idx_spawn_timing_score ON proximity_spawn_timing(spawn_timing_score DESC);

-- Table 2: proximity_team_cohesion
CREATE TABLE IF NOT EXISTS proximity_team_cohesion (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    sample_time INTEGER NOT NULL,
    team VARCHAR(10) NOT NULL,
    alive_count INTEGER NOT NULL,
    centroid_x REAL NOT NULL,
    centroid_y REAL NOT NULL,
    dispersion REAL NOT NULL,
    max_spread REAL NOT NULL,
    straggler_count INTEGER NOT NULL,
    buddy_pair_guids VARCHAR(128),
    buddy_distance REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, team, sample_time)
);
CREATE INDEX IF NOT EXISTS idx_team_cohesion_session ON proximity_team_cohesion(session_date, round_number);

-- Table 3: proximity_crossfire_opportunity
CREATE TABLE IF NOT EXISTS proximity_crossfire_opportunity (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    event_time INTEGER NOT NULL,
    target_guid VARCHAR(32) NOT NULL,
    target_name VARCHAR(64) NOT NULL,
    target_team VARCHAR(10) NOT NULL,
    teammate1_guid VARCHAR(32) NOT NULL,
    teammate2_guid VARCHAR(32) NOT NULL,
    angular_separation REAL NOT NULL,
    was_executed BOOLEAN NOT NULL DEFAULT FALSE,
    damage_within_window INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, target_guid, event_time, teammate1_guid, teammate2_guid)
);
CREATE INDEX IF NOT EXISTS idx_crossfire_opp_session ON proximity_crossfire_opportunity(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_crossfire_opp_executed ON proximity_crossfire_opportunity(was_executed);

-- Table 4: proximity_team_push
CREATE TABLE IF NOT EXISTS proximity_team_push (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    team VARCHAR(10) NOT NULL,
    avg_speed REAL NOT NULL,
    direction_x REAL NOT NULL,
    direction_y REAL NOT NULL,
    alignment_score REAL NOT NULL,
    push_quality REAL NOT NULL,
    participant_count INTEGER NOT NULL,
    toward_objective VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, team, start_time)
);
CREATE INDEX IF NOT EXISTS idx_team_push_session ON proximity_team_push(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_team_push_quality ON proximity_team_push(push_quality DESC);

-- Table 5: proximity_lua_trade_kill
CREATE TABLE IF NOT EXISTS proximity_lua_trade_kill (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    original_kill_time INTEGER NOT NULL,
    traded_kill_time INTEGER NOT NULL,
    delta_ms INTEGER NOT NULL,
    original_victim_guid VARCHAR(32) NOT NULL,
    original_victim_name VARCHAR(64) NOT NULL,
    original_killer_guid VARCHAR(32) NOT NULL,
    original_killer_name VARCHAR(64) NOT NULL,
    trader_guid VARCHAR(32) NOT NULL,
    trader_name VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, original_victim_guid, original_kill_time, trader_guid)
);
CREATE INDEX IF NOT EXISTS idx_lua_trade_session ON proximity_lua_trade_kill(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_lua_trade_trader ON proximity_lua_trade_kill(trader_guid);

COMMIT;
