-- Migration: Add display_name support to player_links
-- Date: 2025-11-18
-- Description: Allow linked players to set custom display names

-- Add display_name column (the chosen name to display)
ALTER TABLE player_links
ADD COLUMN display_name TEXT DEFAULT NULL;

-- Add display_name_source column (tracks how name was set)
ALTER TABLE player_links
ADD COLUMN display_name_source TEXT DEFAULT 'auto';

-- Source values:
-- 'auto'   - Using default (most recent alias)
-- 'custom' - Player set a custom name
-- 'alias'  - Player chose from their aliases

-- Add updated_at timestamp
ALTER TABLE player_links
ADD COLUMN display_name_updated_at TIMESTAMP DEFAULT NULL;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_player_links_display_name
ON player_links(display_name);

COMMENT ON COLUMN player_links.display_name IS
'Custom display name chosen by player. NULL means use auto-resolution (most recent alias)';

COMMENT ON COLUMN player_links.display_name_source IS
'How display_name was set: auto (default), custom (user-chosen), alias (from player aliases)';

COMMENT ON COLUMN player_links.display_name_updated_at IS
'Timestamp when display_name was last changed';
