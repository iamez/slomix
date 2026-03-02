-- Migration: 007_add_round_id_to_lua_round_teams.sql
-- Purpose: Link lua_round_teams to rounds via round_id for reliable joins
-- Created: 2026-02-03

ALTER TABLE lua_round_teams
ADD COLUMN IF NOT EXISTS round_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_lua_round_teams_round_id
ON lua_round_teams(round_id);

COMMENT ON COLUMN lua_round_teams.round_id IS 'FK to rounds.id when resolvable (links Lua webhook rows to rounds)';
