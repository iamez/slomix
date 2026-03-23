-- Migration 022: Add time_played_percent column to player_comprehensive_stats
-- Date: 2026-03-22
-- Description: The parser extracts time_played_percent (alive%) from TAB[8]
--   in stats files, but the column was missing from the schema definition.
--   Production likely already has this column (INSERT works), but fresh
--   deploys would fail. This migration ensures the column exists everywhere.

BEGIN;

ALTER TABLE player_comprehensive_stats
    ADD COLUMN IF NOT EXISTS time_played_percent REAL DEFAULT 0;

COMMENT ON COLUMN player_comprehensive_stats.time_played_percent
    IS 'Percentage of round time the player was alive (alive%), parsed from TAB[8]';

COMMIT;
