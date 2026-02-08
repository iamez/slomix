-- Migration: Add accurate timing metadata columns to rounds table
-- Version: 001
-- Date: 2026-01-22
-- Purpose: Support Lua webhook with accurate timing data (surrender fix, pause tracking)
--
-- These columns store accurate timing data from the Lua script that runs on
-- the game server. The Lua script captures the actual round_end time when
-- the gamestate transitions to INTERMISSION, which gives us correct timing
-- even when teams surrender (stats files show full map duration on surrender).
--
-- Run this migration with:
--   psql -d etlegacy -f migrations/001_add_timing_metadata_columns.sql

-- Add columns for accurate Unix timestamps (from Lua)
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS round_start_unix BIGINT;
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS round_end_unix BIGINT;

-- Add column for actual played duration in seconds (corrects surrender bug)
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS actual_duration_seconds INTEGER;

-- Add columns for pause tracking
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS total_pause_seconds INTEGER DEFAULT 0;
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS pause_count INTEGER DEFAULT 0;

-- Add column for how the round ended
-- Values: 'time_expired', 'objective', 'surrender', 'unknown'
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS end_reason VARCHAR(20);

-- Add index for querying by end reason (useful for stats)
CREATE INDEX IF NOT EXISTS idx_rounds_end_reason ON rounds(end_reason);

-- Verify columns were added
DO $$
BEGIN
    RAISE NOTICE 'Migration 001 complete. New columns added to rounds table:';
    RAISE NOTICE '  - round_start_unix (BIGINT)';
    RAISE NOTICE '  - round_end_unix (BIGINT)';
    RAISE NOTICE '  - actual_duration_seconds (INTEGER)';
    RAISE NOTICE '  - total_pause_seconds (INTEGER)';
    RAISE NOTICE '  - pause_count (INTEGER)';
    RAISE NOTICE '  - end_reason (VARCHAR)';
END $$;
