-- Migration: Add round_status field for restart/cancellation detection
-- Created: 2025-11-17
-- Purpose: Track round status (completed, cancelled, warmup) to handle match restarts

-- Add round_status column to rounds table
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS round_status VARCHAR(20) DEFAULT 'completed';

-- Add index for faster filtering
CREATE INDEX IF NOT EXISTS idx_rounds_status ON rounds(round_status);
CREATE INDEX IF NOT EXISTS idx_rounds_gaming_session ON rounds(gaming_session_id, map_name, round_number, round_status);

-- Update existing rounds to 'completed' status
UPDATE rounds SET round_status = 'completed' WHERE round_status IS NULL;

-- Add comment for documentation
COMMENT ON COLUMN rounds.round_status IS 'Round status: completed (normal), cancelled (restarted), warmup (practice)';

-- Valid statuses:
-- 'completed' - Normal round that counts toward stats
-- 'cancelled' - Earlier attempt of a restarted round (excluded from session summaries)
-- 'warmup' - Practice round (excluded from stats)
