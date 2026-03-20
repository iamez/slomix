-- Migration 020: Add proximity_processed_files table
-- Date: 2026-03-20
-- Description: Tracks which proximity files have been imported and whether
--   aggregate updates (player_teamplay_stats, crossfire_pairs, heatmaps)
--   were applied. Prevents reimport from doubling aggregate statistics.

BEGIN;

CREATE TABLE IF NOT EXISTS proximity_processed_files (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    file_hash TEXT,
    aggregates_applied BOOLEAN DEFAULT FALSE,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
