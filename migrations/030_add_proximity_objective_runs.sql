-- Migration 030: Add Proximity Objective Run Intelligence
-- Date: 2026-03-25
-- Description: Tracks engineer objective runs with path clearing attribution,
--              solo/team classification, denied runs, and approach metrics.

BEGIN;

CREATE TABLE IF NOT EXISTS proximity_objective_run (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    -- Engineer info
    engineer_guid VARCHAR(32) NOT NULL,
    engineer_name VARCHAR(64) NOT NULL DEFAULT '',
    engineer_team VARCHAR(10) NOT NULL DEFAULT '',

    -- Action info
    action_type VARCHAR(32) NOT NULL,  -- dynamite_plant, objective_destroyed, construction_complete, dynamite_defuse, approach_killed
    track_name VARCHAR(64) NOT NULL DEFAULT '',
    action_time INTEGER NOT NULL,

    -- Approach metrics
    approach_time_ms INTEGER DEFAULT 0,
    approach_distance REAL DEFAULT 0,
    beeline_distance REAL DEFAULT 0,
    path_efficiency REAL DEFAULT 0,  -- beeline/approach, 0.0-1.0

    -- Combat context (30s window, 800u radius)
    self_kills INTEGER DEFAULT 0,
    team_kills INTEGER DEFAULT 0,
    escort_guids TEXT DEFAULT '',  -- pipe-separated GUIDs
    enemies_nearby INTEGER DEFAULT 0,
    nearby_teammates INTEGER DEFAULT 0,

    -- Classification
    run_type VARCHAR(32) NOT NULL DEFAULT 'unknown',  -- solo, assisted, unopposed, contested_solo, team_effort, denied

    -- Position
    obj_x INTEGER DEFAULT 0,
    obj_y INTEGER DEFAULT 0,
    obj_z INTEGER DEFAULT 0,

    -- Denied run info (only for approach_killed)
    killer_guid VARCHAR(32) DEFAULT '',
    killer_name VARCHAR(64) DEFAULT '',

    -- Round linkage
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, engineer_guid, action_time, action_type)
);

CREATE INDEX IF NOT EXISTS idx_prox_obj_run_session ON proximity_objective_run(session_date);
CREATE INDEX IF NOT EXISTS idx_prox_obj_run_map ON proximity_objective_run(map_name);
CREATE INDEX IF NOT EXISTS idx_prox_obj_run_engineer ON proximity_objective_run(engineer_guid);
CREATE INDEX IF NOT EXISTS idx_prox_obj_run_type ON proximity_objective_run(run_type);
CREATE INDEX IF NOT EXISTS idx_prox_obj_run_action ON proximity_objective_run(action_type);

-- Track migration
INSERT INTO schema_migrations (version, filename, applied_at, applied_by, success)
VALUES ('030_objective_runs', '030_add_proximity_objective_runs.sql', NOW(), 'manual', true)
ON CONFLICT (version) DO NOTHING;

COMMIT;
