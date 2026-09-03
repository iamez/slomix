-- ================================================================
-- 081: mark a reconstructed time_dead_minutes as reconstructed
-- ================================================================
-- Created: 2026-09-03
-- Purpose: scripts/repair_dead_time_reconstruction.py rewrites
--   time_dead_minutes for pre-2026-03-24 rows from the engine's own
--   alive% (time_played_percent), because the value the game server's
--   Lua wrote there is inflated ~2.2x (it re-added the whole running
--   limbo time on every 5s tick). The repair is reversible --
--   time_dead_minutes_original keeps the number that was there --
--   but reversibility is not the same as being ASKABLE.
--
--   This project separates absent / zero / derived everywhere else;
--   a consumer must be able to ask "is this row a measurement?" in
--   SQL, not infer it from a date range that will drift the moment
--   another repair touches another era. Same reasoning as
--   rounds.round_status and migration 060's formula_version.
--
--   NULL = never touched by the reconstruction (the overwhelming
--   majority, including every row captured after the Lua fix).
--   FALSE is never written: the flag has two states that matter,
--   "reconstructed" and "not", and a default of FALSE on 75k rows
--   would claim we checked them all.
-- ================================================================

ALTER TABLE player_comprehensive_stats
    ADD COLUMN IF NOT EXISTS time_dead_reconstructed boolean;

COMMENT ON COLUMN player_comprehensive_stats.time_dead_reconstructed IS
    'TRUE = time_dead_minutes was derived from engine alive% by '
    'scripts/repair_dead_time_reconstruction.py; the value the capture file '
    'carried is in time_dead_minutes_original. NULL = untouched measurement.';
