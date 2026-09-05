-- ============================================================================
-- 082: vehicle progress — when the mover moved, and who took it down
-- Created: 2026-09-05
-- Purpose: docs/design/20 slice 2 (match moments). The escort-mover moment
--   had no timestamp: proximity_vehicle_progress carried the vehicle's start
--   and end POSITION but no time, so the moment was pinned to the end of the
--   round (detail.timestamp_source = "round_end"). destroyed_count was a bare
--   integer from a health poll with no attacker.
--   The Lua tracker v6.14 now writes four trailing fields on the
--   VEHICLE_PROGRESS line (first/last_move_time — the mover's own motion —
--   and first/last_escort_time — its motion with a player mounted or within
--   escort_radius, i.e. WHEN THE ESCORT HAPPENED — all gameTime() ms
--   since round start, the same base as proximity_carrier_kill.kill_time,
--   stored unconverted) and a VEHICLE_DESTROYED section (one row per
--   destruction: time, attacker, means of death, health before). The
--   destruction rows live on the vehicle's own row as JSONB — one vehicle,
--   one round, one row — rather than a second table with its own round-link
--   bookkeeping.
--   NULL means "the recording predates v6.14 or the mover never moved"; it
--   is not 0. The parser writes NULL for the Lua's 0.
-- Idempotent: every statement is IF NOT EXISTS.
-- ============================================================================

ALTER TABLE proximity_vehicle_progress
    ADD COLUMN IF NOT EXISTS first_move_time INTEGER,
    ADD COLUMN IF NOT EXISTS last_move_time INTEGER,
    ADD COLUMN IF NOT EXISTS first_escort_time INTEGER,
    ADD COLUMN IF NOT EXISTS last_escort_time INTEGER,
    ADD COLUMN IF NOT EXISTS destroyed_events JSONB;

COMMENT ON COLUMN proximity_vehicle_progress.first_move_time IS
    'v6.14: first tick the mover moved, gameTime() ms since round start (as carrier kill_time). NULL = pre-v6.14 recording or never moved.';
COMMENT ON COLUMN proximity_vehicle_progress.last_move_time IS
    'v6.14: last tick the mover moved, gameTime() ms since round start. NULL = pre-v6.14 recording or never moved.';
COMMENT ON COLUMN proximity_vehicle_progress.first_escort_time IS
    'v6.14: first moving tick with a player mounted or within escort_radius — when the escort began (a supply truck drives itself at round start, so first_move_time is not it). Same base; NULL = pre-v6.14 or never escorted.';
COMMENT ON COLUMN proximity_vehicle_progress.last_escort_time IS
    'v6.14: last escorted moving tick, same base; NULL = pre-v6.14 or never escorted.';
COMMENT ON COLUMN proximity_vehicle_progress.destroyed_events IS
    'v6.14: JSON list of {time, attacker_guid, attacker_name, attacker_team, means_of_death, health_before}; attacker empty when the poll saw the death without a hit. NULL = pre-v6.14 recording; [] = never destroyed.';
