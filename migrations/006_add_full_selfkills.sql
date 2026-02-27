-- Migration: 006_add_full_selfkills.sql
-- Purpose: Add full_selfkills to player_comprehensive_stats (optional stat)
-- Created: 2026-02-03

ALTER TABLE player_comprehensive_stats
ADD COLUMN IF NOT EXISTS full_selfkills INTEGER DEFAULT 0;

COMMENT ON COLUMN player_comprehensive_stats.full_selfkills IS
'Count of selfkills while at full health (from c0rnp0rn field 35).';
