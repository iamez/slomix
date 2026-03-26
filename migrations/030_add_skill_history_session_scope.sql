-- Migration 030: Add session/map scope to skill rating history
-- Date: 2026-03-26
-- Description: Enables per-session and per-map rating snapshots
--   for trend visualization and drill-down.

BEGIN;

-- Add session scope columns to history table
ALTER TABLE player_skill_history
    ADD COLUMN IF NOT EXISTS session_date DATE,
    ADD COLUMN IF NOT EXISTS map_name TEXT,
    ADD COLUMN IF NOT EXISTS rounds_in_scope INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT 'global';
    -- scope: 'global' (all-time recalc), 'session' (one date), 'map' (one date+map)

-- Index for session-level queries
CREATE INDEX IF NOT EXISTS idx_skill_history_session
    ON player_skill_history(player_guid, session_date DESC)
    WHERE scope = 'session';

-- Index for map-level drill-down
CREATE INDEX IF NOT EXISTS idx_skill_history_map
    ON player_skill_history(player_guid, session_date, map_name)
    WHERE scope = 'map';

COMMIT;
