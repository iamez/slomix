-- Migration: Add match_predictions table for competitive analytics
-- Created: 2025-11-28
-- Purpose: Store automated match predictions from PredictionEngine
-- Phase: 4 - Database Tables & Live Scoring

-- ============================================================================
-- TABLE: match_predictions
-- Stores predictions made when teams split into voice channels
-- ============================================================================
CREATE TABLE IF NOT EXISTS match_predictions (
    id SERIAL PRIMARY KEY,

    -- When and where
    prediction_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_date TEXT NOT NULL,
    map_name TEXT,
    format TEXT NOT NULL,  -- "3v3", "4v4", "5v5", "6v6"

    -- Team composition
    team_a_channel_id BIGINT NOT NULL,
    team_b_channel_id BIGINT NOT NULL,
    team_a_guids TEXT NOT NULL,  -- JSON array: ["guid1", "guid2", ...]
    team_b_guids TEXT NOT NULL,  -- JSON array: ["guid1", "guid2", ...]
    team_a_discord_ids TEXT NOT NULL,  -- JSON array: [123456789, ...]
    team_b_discord_ids TEXT NOT NULL,  -- JSON array: [123456789, ...]

    -- Prediction results
    team_a_win_probability REAL NOT NULL,  -- 0.0 to 1.0
    team_b_win_probability REAL NOT NULL,  -- 0.0 to 1.0
    confidence TEXT NOT NULL,  -- "high", "medium", "low"
    confidence_score REAL NOT NULL,  -- 0.0 to 1.0

    -- Factor scores (for analysis)
    h2h_score REAL NOT NULL,
    form_score REAL NOT NULL,
    map_score REAL NOT NULL,
    subs_score REAL NOT NULL,
    weighted_score REAL NOT NULL,

    -- Details
    key_insight TEXT NOT NULL,
    h2h_details TEXT,  -- JSON with detailed breakdown
    form_details TEXT,
    map_details TEXT,
    subs_details TEXT,

    -- Actual outcome (filled in after match)
    actual_winner INTEGER,  -- 1 = Team A, 2 = Team B, 0 = draw/cancelled
    team_a_actual_score INTEGER,  -- Round wins
    team_b_actual_score INTEGER,  -- Round wins
    prediction_correct BOOLEAN,  -- Did we predict the correct winner?
    prediction_accuracy REAL,  -- How close was the probability?

    -- Discord integration
    discord_message_id BIGINT,  -- For editing prediction embeds
    discord_channel_id BIGINT,  -- Where prediction was posted

    -- Metadata
    guid_coverage REAL NOT NULL,  -- % of players with linked accounts
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_predictions_session_date ON match_predictions(session_date);
CREATE INDEX IF NOT EXISTS idx_predictions_prediction_time ON match_predictions(prediction_time DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_format ON match_predictions(format);
CREATE INDEX IF NOT EXISTS idx_predictions_confidence ON match_predictions(confidence);
CREATE INDEX IF NOT EXISTS idx_predictions_discord_msg ON match_predictions(discord_message_id);

-- Index for accuracy analysis
CREATE INDEX IF NOT EXISTS idx_predictions_outcome ON match_predictions(actual_winner)
    WHERE actual_winner IS NOT NULL;

-- Comments for documentation
COMMENT ON TABLE match_predictions IS 'Stores automated match predictions from competitive analytics system (Phase 3-4)';
COMMENT ON COLUMN match_predictions.team_a_guids IS 'JSON array of player GUIDs for Team A';
COMMENT ON COLUMN match_predictions.team_b_guids IS 'JSON array of player GUIDs for Team B';
COMMENT ON COLUMN match_predictions.actual_winner IS '1 = Team A won, 2 = Team B won, 0 = draw/cancelled, NULL = not played yet';
COMMENT ON COLUMN match_predictions.prediction_correct IS 'TRUE if predicted winner matches actual_winner';
COMMENT ON COLUMN match_predictions.prediction_accuracy IS 'Calculated accuracy metric (Brier score or similar)';
