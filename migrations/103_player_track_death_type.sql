-- Independent lifecycle cause, never reconstructed from positional coverage.
-- NULL means not persisted historically; new unknown source causes use 'unknown'.
-- No backfill: ON CONFLICT imports must not rewrite previously stored lives.
ALTER TABLE player_track ADD COLUMN IF NOT EXISTS death_type TEXT;
COMMENT ON COLUMN player_track.death_type IS
    'Parent source lifecycle cause, independent of path sampling. NULL is historical/unrecorded; unknown is explicit. Includes shutdown; not every end is a death.';
