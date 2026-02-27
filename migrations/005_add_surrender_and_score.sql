-- Migration: 005_add_surrender_and_score.sql
-- Purpose: Add surrender vote tracking and match score columns to lua_round_teams
-- Version: 1.4.0
-- Created: 2026-01-25
-- Part of: Lua Webhook Feature - Surrender & Live Score Tracking

-- ============================================================================
-- SURRENDER VOTE TRACKING
-- ============================================================================
-- These columns track who called a surrender vote and which team surrendered.
-- This allows the bot to show "Allies surrendered (called by player123)" in stats.

-- GUID of the player who called the surrender vote
ALTER TABLE lua_round_teams
ADD COLUMN IF NOT EXISTS surrender_caller_guid VARCHAR(32);

-- Display name of the player who called the surrender vote
ALTER TABLE lua_round_teams
ADD COLUMN IF NOT EXISTS surrender_caller_name VARCHAR(64);

-- Team that surrendered (1=Axis, 2=Allies, 0=no surrender)
-- Note: This is the team that LOST via surrender, not the winner
ALTER TABLE lua_round_teams
ADD COLUMN IF NOT EXISTS surrender_team INTEGER DEFAULT 0;

-- ============================================================================
-- MATCH SCORE TRACKING
-- ============================================================================
-- These columns track the running score within a match (across R1 and R2).
-- Useful for live score display and historical analysis.

-- Number of rounds won by Axis in this match
ALTER TABLE lua_round_teams
ADD COLUMN IF NOT EXISTS axis_score INTEGER DEFAULT 0;

-- Number of rounds won by Allies in this match
ALTER TABLE lua_round_teams
ADD COLUMN IF NOT EXISTS allies_score INTEGER DEFAULT 0;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================
COMMENT ON COLUMN lua_round_teams.surrender_caller_guid IS 'GUID of player who called surrender vote (v1.4.0)';
COMMENT ON COLUMN lua_round_teams.surrender_caller_name IS 'Name of player who called surrender vote (v1.4.0)';
COMMENT ON COLUMN lua_round_teams.surrender_team IS 'Team that surrendered: 1=Axis, 2=Allies, 0=no surrender (v1.4.0)';
COMMENT ON COLUMN lua_round_teams.axis_score IS 'Running Axis wins in match at time of this round (v1.4.0)';
COMMENT ON COLUMN lua_round_teams.allies_score IS 'Running Allies wins in match at time of this round (v1.4.0)';

-- ============================================================================
-- INDEX FOR SURRENDER QUERIES
-- ============================================================================
-- Index for queries that filter by surrender (e.g., "find all surrendered rounds")
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_surrender
ON lua_round_teams(surrender_team)
WHERE surrender_team > 0;
