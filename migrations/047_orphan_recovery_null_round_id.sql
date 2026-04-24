-- migrations/047_orphan_recovery_null_round_id.sql
-- Class A orphan recovery: rows with round_id IS NULL where an exact
-- (map_name, round_number, round_start_unix) match exists in `rounds`.
--
-- Background: migration 046 rebound 47,486 mis-linked rows via
-- `(map, round_start_unix)` exact match, but its WHERE clause included
-- `t.round_id IS NOT NULL` (comment on line 22 of 046: "Rows with NULL
-- round_id are left for the relinker cron"). That relinker cron exists
-- (`bot/cogs/proximity_mixins/relinker_mixin.py`) but only fires on
-- proximity panels not the full 23 tables, so historical NULLs never
-- got paired. RCA on 2026-04-24 found ~11,139 such orphan rows still
-- holding a NULL linkage despite an exact-match rounds row being
-- present.
--
-- This migration mirrors 046's UPDATE block on all 23 tables, this
-- time FOR rows where round_id IS NULL. Uses `round_number` guard +
-- `round_start_unix > 0` to match 046's tightened version and allow
-- the composite index from migration 014.
--
-- Idempotent. Zero risk — exact (map_name, round_number, round_start_unix)
-- equality has no ambiguity; if the match exists the bind is correct.

BEGIN;

UPDATE combat_engagement t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE player_track t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE lua_round_teams t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_carrier_event t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_carrier_kill t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_carrier_return t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_combat_position t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_construction_event t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_crossfire_opportunity t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_escort_credit t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_focus_fire t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_hit_region t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_kill_outcome t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_lua_trade_kill t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_objective_focus t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_objective_run t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_reaction_metric t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_spawn_timing t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_support_summary t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_team_cohesion t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_team_push t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_trade_event t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

UPDATE proximity_vehicle_progress t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NULL;

INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('047_orphan_recovery_null_round_id',
        '047_orphan_recovery_null_round_id.sql',
        'self')
ON CONFLICT (version) DO NOTHING;

COMMIT;
