-- Migration 025: Add proximity hit region tracking tables
-- Tracks per-damage hit regions (HEAD, ARMS, BODY, LEGS) from Lua et_Damage hook
BEGIN;

CREATE TABLE IF NOT EXISTS proximity_hit_region (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    event_time INTEGER NOT NULL,
    attacker_guid VARCHAR(32) NOT NULL,
    attacker_name VARCHAR(64) NOT NULL,
    victim_guid VARCHAR(32) NOT NULL,
    victim_name VARCHAR(64) NOT NULL,
    weapon_id INTEGER NOT NULL,
    hit_region INTEGER NOT NULL,  -- 0=HEAD, 1=ARMS, 2=BODY, 3=LEGS
    damage INTEGER NOT NULL,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- No UNIQUE constraint: same attacker can hit same victim same region same ms
-- (splash damage + direct hit in same frame)

CREATE INDEX IF NOT EXISTS idx_hit_region_attacker ON proximity_hit_region(attacker_guid);
CREATE INDEX IF NOT EXISTS idx_hit_region_victim ON proximity_hit_region(victim_guid);
CREATE INDEX IF NOT EXISTS idx_hit_region_session ON proximity_hit_region(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_hit_region_weapon ON proximity_hit_region(weapon_id);
CREATE INDEX IF NOT EXISTS idx_hit_region_round ON proximity_hit_region(round_id);
CREATE INDEX IF NOT EXISTS idx_hit_region_region ON proximity_hit_region(hit_region);

-- Aggregate table for fast per-player-per-weapon queries
CREATE TABLE IF NOT EXISTS proximity_hit_region_summary (
    id SERIAL PRIMARY KEY,
    player_guid VARCHAR(32) NOT NULL,
    player_name VARCHAR(64),
    weapon_id INTEGER NOT NULL,
    head_hits INTEGER DEFAULT 0,
    arms_hits INTEGER DEFAULT 0,
    body_hits INTEGER DEFAULT 0,
    legs_hits INTEGER DEFAULT 0,
    head_damage INTEGER DEFAULT 0,
    arms_damage INTEGER DEFAULT 0,
    body_damage INTEGER DEFAULT 0,
    legs_damage INTEGER DEFAULT 0,
    total_hits INTEGER DEFAULT 0,
    total_damage INTEGER DEFAULT 0,
    headshot_pct REAL GENERATED ALWAYS AS (
        CASE WHEN total_hits > 0 THEN (head_hits::REAL / total_hits) * 100 ELSE 0 END
    ) STORED,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_guid, weapon_id)
);

CREATE INDEX IF NOT EXISTS idx_hr_summary_player ON proximity_hit_region_summary(player_guid);

-- Track migration
INSERT INTO schema_migrations (version, filename, applied_at, applied_by, success)
VALUES ('025_hit_region', '025_add_proximity_hit_region.sql', NOW(), 'manual', true)
ON CONFLICT (version) DO NOTHING;

COMMIT;
