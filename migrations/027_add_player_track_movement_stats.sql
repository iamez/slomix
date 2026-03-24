-- Migration 027: Add movement analytics columns to player_track
-- Computed from existing 200ms path samples (stance, sprint, speed, distance)
BEGIN;

ALTER TABLE player_track ADD COLUMN IF NOT EXISTS peak_speed REAL;
ALTER TABLE player_track ADD COLUMN IF NOT EXISTS stance_standing_sec REAL;
ALTER TABLE player_track ADD COLUMN IF NOT EXISTS stance_crouching_sec REAL;
ALTER TABLE player_track ADD COLUMN IF NOT EXISTS stance_prone_sec REAL;
ALTER TABLE player_track ADD COLUMN IF NOT EXISTS sprint_sec REAL;
ALTER TABLE player_track ADD COLUMN IF NOT EXISTS post_spawn_distance REAL;

-- Track migration
INSERT INTO schema_migrations (version, filename, applied_at, applied_by, success)
VALUES ('027_movement_stats', '027_add_player_track_movement_stats.sql', NOW(), 'manual', true)
ON CONFLICT (version) DO NOTHING;

COMMIT;
