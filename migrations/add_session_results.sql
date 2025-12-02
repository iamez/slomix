-- Migration: Add session_results table for competitive analytics
-- Created: 2025-11-28
-- Purpose: Track actual match outcomes for prediction accuracy analysis
-- Phase: 4 - Database Tables & Live Scoring
-- Note: PostgreSQL dialect - SET QUOTED_IDENTIFIER/ANSI_NULLS not applicable

-- ============================================================================
-- TABLE: session_results
-- Aggregated session results for competitive matches
-- ============================================================================
CREATE TABLE IF NOT EXISTS session_results (
    id SERIAL PRIMARY KEY,

    -- Session identification
    session_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    gaming_session_id INTEGER,  -- Links to rounds.gaming_session_id

    -- Team composition
    team_1_guids TEXT NOT NULL,  -- JSON array: ["guid1", "guid2", ...]
    team_2_guids TEXT NOT NULL,  -- JSON array: ["guid1", "guid2", ...]
    team_1_names TEXT NOT NULL,  -- JSON array: ["Player1", "Player2", ...]
    team_2_names TEXT NOT NULL,  -- JSON array: ["Player1", "Player2", ...]

    -- Match format
    format TEXT NOT NULL,  -- "3v3", "4v4", "5v5", "6v6"
    total_rounds INTEGER NOT NULL,

    -- Match outcome
    team_1_score INTEGER NOT NULL DEFAULT 0,  -- Round wins for team 1
    team_2_score INTEGER NOT NULL DEFAULT 0,  -- Round wins for team 2
    winning_team INTEGER NOT NULL,  -- 1 = Team 1, 2 = Team 2, 0 = draw

    -- Round-by-round details
    round_details TEXT,  -- JSON: [{"round": 1, "winner": 1, "time": "12:45"}, ...]
    round_numbers TEXT NOT NULL,  -- JSON array: [1, 2, 3, 4]

    -- Session timing
    session_start TIMESTAMP NOT NULL,
    session_end TIMESTAMP,
    duration_minutes INTEGER,

    -- Team statistics (aggregated from player_comprehensive_stats)
    team_1_total_kills INTEGER DEFAULT 0,
    team_1_total_deaths INTEGER DEFAULT 0,
    team_1_total_damage INTEGER DEFAULT 0,
    team_2_total_kills INTEGER DEFAULT 0,
    team_2_total_deaths INTEGER DEFAULT 0,
    team_2_total_damage INTEGER DEFAULT 0,

    -- Roster changes
    had_substitutions BOOLEAN DEFAULT FALSE,
    substitution_details TEXT,  -- JSON with sub info

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure one result per session
    UNIQUE(session_date, map_name, gaming_session_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_session_results_date ON session_results(session_date DESC);
CREATE INDEX IF NOT EXISTS idx_session_results_map ON session_results(map_name);
CREATE INDEX IF NOT EXISTS idx_session_results_format ON session_results(format);
CREATE INDEX IF NOT EXISTS idx_session_results_winner ON session_results(winning_team);
CREATE INDEX IF NOT EXISTS idx_session_results_gaming_session ON session_results(gaming_session_id);

-- Index for team lookup (for H2H analysis)
CREATE INDEX IF NOT EXISTS idx_session_results_teams ON session_results(team_1_guids, team_2_guids);

-- Comments for documentation
COMMENT ON TABLE session_results IS 'Aggregated match results for competitive analytics and prediction accuracy tracking (Phase 4)';
COMMENT ON COLUMN session_results.team_1_guids IS 'JSON array of player GUIDs for Team 1';
COMMENT ON COLUMN session_results.team_2_guids IS 'JSON array of player GUIDs for Team 2';
COMMENT ON COLUMN session_results.winning_team IS '1 = Team 1 won, 2 = Team 2 won, 0 = draw';
COMMENT ON COLUMN session_results.round_details IS 'JSON array with round-by-round results including winner, time, scores';
COMMENT ON COLUMN session_results.had_substitutions IS 'TRUE if players joined/left mid-session';


-- ============================================================================
-- TABLE: map_performance
-- Track player performance on specific maps (for prediction engine)
-- ============================================================================
CREATE TABLE IF NOT EXISTS map_performance (
    id SERIAL PRIMARY KEY,

    -- Player and map
    player_guid TEXT NOT NULL,
    map_name TEXT NOT NULL,

    -- Performance metrics (rolling averages)
    matches_played INTEGER NOT NULL DEFAULT 0,
    total_rounds INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    win_rate REAL NOT NULL DEFAULT 0.0,

    -- Combat stats (averages)
    avg_kills REAL NOT NULL DEFAULT 0.0,
    avg_deaths REAL NOT NULL DEFAULT 0.0,
    avg_kd_ratio REAL NOT NULL DEFAULT 0.0,
    avg_dpm REAL NOT NULL DEFAULT 0.0,
    avg_efficiency REAL NOT NULL DEFAULT 0.0,

    -- Last updated
    last_match_date TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- One record per player per map
    UNIQUE(player_guid, map_name)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_map_performance_guid ON map_performance(player_guid);
CREATE INDEX IF NOT EXISTS idx_map_performance_map ON map_performance(map_name);
CREATE INDEX IF NOT EXISTS idx_map_performance_winrate ON map_performance(win_rate DESC);

-- Comments
COMMENT ON TABLE map_performance IS 'Player performance statistics per map for prediction engine (Phase 4)';
COMMENT ON COLUMN map_performance.win_rate IS 'Win rate on this map (0.0 to 1.0)';
COMMENT ON COLUMN map_performance.avg_dpm IS 'Average damage per minute on this map';
