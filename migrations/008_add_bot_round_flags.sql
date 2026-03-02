-- Migration: Add bot-only round flags for Omni-bot sessions
-- Created: 2026-02-04

ALTER TABLE rounds ADD COLUMN IF NOT EXISTS is_bot_round BOOLEAN DEFAULT FALSE;
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS bot_player_count INTEGER DEFAULT 0;
ALTER TABLE rounds ADD COLUMN IF NOT EXISTS human_player_count INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_rounds_is_bot_round ON rounds(is_bot_round);
