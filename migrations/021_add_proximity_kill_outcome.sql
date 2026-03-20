-- Migration 021: Add proximity_kill_outcome table
-- Date: 2026-03-20
-- Description: Tracks what happens after each kill — revived, gibbed, or tapped out.
--   Enables Kill Permanence Rate (KPR), Team Denial Score (TDS), and
--   corrected effective_denied_time (fixing the engine's broken denied_playtime).

BEGIN;

CREATE TABLE IF NOT EXISTS proximity_kill_outcome (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    kill_time INTEGER NOT NULL,
    victim_guid VARCHAR(32) NOT NULL,
    victim_name VARCHAR(64) NOT NULL,
    killer_guid VARCHAR(32) NOT NULL,
    killer_name VARCHAR(64),
    kill_mod INTEGER DEFAULT 0,
    outcome VARCHAR(16) NOT NULL,
    outcome_time INTEGER NOT NULL,
    delta_ms INTEGER NOT NULL,
    effective_denied_ms INTEGER NOT NULL,
    gibber_guid VARCHAR(32) DEFAULT '',
    gibber_name VARCHAR(64) DEFAULT '',
    reviver_guid VARCHAR(32) DEFAULT '',
    reviver_name VARCHAR(64) DEFAULT '',
    round_id INTEGER REFERENCES rounds(id),
    round_link_source VARCHAR(32),
    round_link_reason VARCHAR(64),
    round_linked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, kill_time, victim_guid)
);

CREATE INDEX IF NOT EXISTS idx_kill_outcome_victim ON proximity_kill_outcome(victim_guid);
CREATE INDEX IF NOT EXISTS idx_kill_outcome_killer ON proximity_kill_outcome(killer_guid);
CREATE INDEX IF NOT EXISTS idx_kill_outcome_outcome ON proximity_kill_outcome(outcome);
CREATE INDEX IF NOT EXISTS idx_kill_outcome_session ON proximity_kill_outcome(session_date);
CREATE INDEX IF NOT EXISTS idx_kill_outcome_round ON proximity_kill_outcome(round_id);

COMMIT;
