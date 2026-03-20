-- Migration 017: Persisted FIFO round assembler for repeated maps
-- =============================================================================
-- Adds:
--   - rounds.map_play_seq: occurrence order for repeated maps within a session
--   - round_assemblies: authoritative session/map/map_play_seq linker
--   - round_assembly_events: persisted pending/attached non-stats events
--
-- round_correlations remains as a derived compatibility surface for admin and
-- anomaly tooling; the assembler tables are now the primary identity model.
-- =============================================================================

ALTER TABLE rounds
    ADD COLUMN IF NOT EXISTS map_play_seq INTEGER;

CREATE INDEX IF NOT EXISTS idx_rounds_session_map_seq
    ON rounds(gaming_session_id, map_name, map_play_seq);

CREATE TABLE IF NOT EXISTS round_assemblies (
    id SERIAL PRIMARY KEY,
    assembly_key VARCHAR(128) UNIQUE NOT NULL,
    gaming_session_id INTEGER NOT NULL,
    map_name VARCHAR(64) NOT NULL,
    map_play_seq INTEGER NOT NULL,
    r1_round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    r2_round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    summary_round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    r1_lua_teams_id INTEGER REFERENCES lua_round_teams(id) ON DELETE SET NULL,
    r2_lua_teams_id INTEGER REFERENCES lua_round_teams(id) ON DELETE SET NULL,
    has_r1_stats BOOLEAN DEFAULT FALSE,
    has_r2_stats BOOLEAN DEFAULT FALSE,
    has_r1_lua_teams BOOLEAN DEFAULT FALSE,
    has_r2_lua_teams BOOLEAN DEFAULT FALSE,
    has_r1_gametime BOOLEAN DEFAULT FALSE,
    has_r2_gametime BOOLEAN DEFAULT FALSE,
    has_r1_endstats BOOLEAN DEFAULT FALSE,
    has_r2_endstats BOOLEAN DEFAULT FALSE,
    orphan_r2 BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'pending',
    completeness_pct INTEGER DEFAULT 0,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gaming_session_id, map_name, map_play_seq)
);

CREATE INDEX IF NOT EXISTS idx_round_assemblies_status
    ON round_assemblies(status);

CREATE INDEX IF NOT EXISTS idx_round_assemblies_session_map
    ON round_assemblies(gaming_session_id, map_name, map_play_seq);

CREATE TABLE IF NOT EXISTS round_assembly_events (
    id SERIAL PRIMARY KEY,
    event_key VARCHAR(160) UNIQUE NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    match_id VARCHAR(128),
    gaming_session_id INTEGER,
    map_name VARCHAR(64) NOT NULL,
    round_number INTEGER NOT NULL,
    round_id INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    lua_teams_id INTEGER REFERENCES lua_round_teams(id) ON DELETE SET NULL,
    event_unix BIGINT,
    event_at TIMESTAMP,
    attachment_status VARCHAR(20) DEFAULT 'pending',
    assembly_id INTEGER REFERENCES round_assemblies(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    attached_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_round_assembly_events_pending
    ON round_assembly_events(attachment_status, source_type, map_name, round_number, event_at, id);

CREATE INDEX IF NOT EXISTS idx_round_assembly_events_round_id
    ON round_assembly_events(round_id);
