-- PostgreSQL Migration Script
-- Migration: Add team tracking tables and columns
-- Created: 2026-01-10
-- Purpose: Enable team name assignment and historical tracking
-- Reference: docs/FIX_TEAM_TRACKING.md

-- ============================================================================
-- TABLE: team_pool
-- Pool of available team names for random assignment
-- ============================================================================
CREATE TABLE IF NOT EXISTS team_pool (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,           -- Internal name: 'sWat', 'S*F', etc.
    display_name TEXT,                   -- Optional formatted display name
    color INTEGER,                       -- Discord embed color (hex as int)
    active BOOLEAN DEFAULT TRUE,         -- Can exclude teams from pool
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed with OG teams (colors as Discord embed int values)
INSERT INTO team_pool (name, display_name, color) VALUES
    ('sWat', 'sWat', 3447003),            -- Blue (#3498DB)
    ('S*F', 'S*F', 15158332),             -- Red (#E74C3C)
    ('madDogz', 'madDogz', 15105570),     -- Orange (#E67E22)
    ('slomix', 'slomix', 10181046),       -- Purple (#9B59B6)
    ('puran', 'puran', 3066993),          -- Green (#2ECC71)
    ('insAne', 'insAne', 15844367),       -- Gold (#F1C40F)
    ('allbad', 'allbad', 9807270)         -- Gray (#95A5A6)
ON CONFLICT (name) DO NOTHING;

-- Index for active team lookup
CREATE INDEX IF NOT EXISTS idx_team_pool_active ON team_pool(active) WHERE active = TRUE;

-- Comments
COMMENT ON TABLE team_pool IS 'Pool of team names for random session assignment';
COMMENT ON COLUMN team_pool.color IS 'Discord embed color as integer (e.g., 0x3498DB = 3447003)';
COMMENT ON COLUMN team_pool.active IS 'FALSE to exclude from random pool without deleting';


-- ============================================================================
-- ALTER TABLE: session_results
-- Add team name columns for team identity tracking
-- ============================================================================
ALTER TABLE session_results ADD COLUMN IF NOT EXISTS team_1_name TEXT;
ALTER TABLE session_results ADD COLUMN IF NOT EXISTS team_2_name TEXT;

-- Index for team name lookups (for win/loss records)
CREATE INDEX IF NOT EXISTS idx_session_results_team1_name ON session_results(team_1_name);
CREATE INDEX IF NOT EXISTS idx_session_results_team2_name ON session_results(team_2_name);

-- Comments
COMMENT ON COLUMN session_results.team_1_name IS 'Team name from pool (e.g., sWat, madDogz)';
COMMENT ON COLUMN session_results.team_2_name IS 'Team name from pool (e.g., sWat, madDogz)';


-- ============================================================================
-- ALTER TABLE: session_teams
-- Add color column for team display
-- ============================================================================
ALTER TABLE session_teams ADD COLUMN IF NOT EXISTS color INTEGER;

COMMENT ON COLUMN session_teams.color IS 'Discord embed color for this team (from team_pool)';
