-- Migration 015: Add Weapon Accuracy and Revive Tracking Tables
-- Date: 2026-03-12
-- Description: Adds per-weapon accuracy stats and spatial revive analytics
--   for the proximity pipeline. proximity_weapon_accuracy tracks per-round
--   per-player weapon performance with a generated accuracy_pct column.
--   proximity_revive records medic revive events with spatial context
--   (position, distance to nearest enemy, under-fire flag).

BEGIN;

-- Table 1: proximity_weapon_accuracy
CREATE TABLE IF NOT EXISTS proximity_weapon_accuracy (
    id SERIAL PRIMARY KEY,
    round_id INTEGER,
    map_name TEXT,
    player_guid TEXT NOT NULL,
    player_name TEXT,
    team TEXT,
    weapon_id INTEGER NOT NULL,
    shots_fired INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    kills INTEGER DEFAULT 0,
    headshots INTEGER DEFAULT 0,
    accuracy_pct REAL GENERATED ALWAYS AS (
        CASE WHEN shots_fired > 0 THEN (hits::REAL / shots_fired) * 100 ELSE 0 END
    ) STORED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_weapon_accuracy_player ON proximity_weapon_accuracy(player_guid);
CREATE INDEX IF NOT EXISTS idx_weapon_accuracy_round ON proximity_weapon_accuracy(round_id);
CREATE INDEX IF NOT EXISTS idx_weapon_accuracy_map_weapon ON proximity_weapon_accuracy(map_name, weapon_id);

-- Table 2: proximity_revive
CREATE TABLE IF NOT EXISTS proximity_revive (
    id SERIAL PRIMARY KEY,
    round_id INTEGER,
    map_name TEXT,
    medic_guid TEXT,
    medic_name TEXT,
    revived_guid TEXT NOT NULL,
    revived_name TEXT,
    revive_time INTEGER,
    revive_x REAL,
    revive_y REAL,
    revive_z REAL,
    distance_to_enemy REAL,
    under_fire BOOLEAN DEFAULT FALSE,
    nearest_enemy_guid TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_revive_round ON proximity_revive(round_id);
CREATE INDEX IF NOT EXISTS idx_revive_medic ON proximity_revive(medic_guid);
CREATE INDEX IF NOT EXISTS idx_revive_revived ON proximity_revive(revived_guid);

COMMIT;
