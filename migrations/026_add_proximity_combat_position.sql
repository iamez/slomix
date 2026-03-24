-- Migration 026: Add proximity combat position tracking table
-- Captures killer + victim positions on every kill for weapon-specific heatmaps and kill lines
BEGIN;

CREATE TABLE IF NOT EXISTS proximity_combat_position (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    event_time INTEGER NOT NULL,
    event_type VARCHAR(16) NOT NULL DEFAULT 'kill',
    attacker_guid VARCHAR(32) NOT NULL,
    attacker_name VARCHAR(64),
    attacker_team VARCHAR(10),
    attacker_class VARCHAR(16),
    victim_guid VARCHAR(32) NOT NULL,
    victim_name VARCHAR(64),
    victim_team VARCHAR(10),
    victim_class VARCHAR(16),
    attacker_x INTEGER NOT NULL,
    attacker_y INTEGER NOT NULL,
    attacker_z INTEGER NOT NULL,
    victim_x INTEGER NOT NULL,
    victim_y INTEGER NOT NULL,
    victim_z INTEGER NOT NULL,
    weapon_id INTEGER NOT NULL,
    means_of_death INTEGER NOT NULL,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, event_time, attacker_guid, victim_guid)
);

CREATE INDEX IF NOT EXISTS idx_combat_pos_session ON proximity_combat_position(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_combat_pos_map ON proximity_combat_position(map_name);
CREATE INDEX IF NOT EXISTS idx_combat_pos_attacker ON proximity_combat_position(attacker_guid);
CREATE INDEX IF NOT EXISTS idx_combat_pos_victim ON proximity_combat_position(victim_guid);
CREATE INDEX IF NOT EXISTS idx_combat_pos_weapon ON proximity_combat_position(weapon_id);
CREATE INDEX IF NOT EXISTS idx_combat_pos_round ON proximity_combat_position(round_id);
CREATE INDEX IF NOT EXISTS idx_combat_pos_class ON proximity_combat_position(victim_class);

-- Track migration
INSERT INTO schema_migrations (version, filename, applied_at, applied_by, success)
VALUES ('026_combat_position', '026_add_proximity_combat_position.sql', NOW(), 'manual', true)
ON CONFLICT (version) DO NOTHING;

COMMIT;
