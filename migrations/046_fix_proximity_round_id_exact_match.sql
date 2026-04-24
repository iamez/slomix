-- migrations/046_fix_proximity_round_id_exact_match.sql
-- Rebind proximity / Lua rows to the correct `rounds.id` based on
-- exact `(map_name, round_start_unix)` match.
--
-- Discovered 2026-04-23: `resolve_round_id_with_reason` picked the
-- *closest-timestamp* candidate when the same (map, round_number)
-- was replayed multiple times in a scrim session. Engagement /
-- proximity rows carry the Lua `round_start_unix` — and `rounds`
-- stores the same value in its `round_start_unix` column — so an
-- exact match is unambiguous.
--
-- Before this migration's paired code fix (bot/core/round_linker.py
-- `resolved_exact_unix_match` priority branch), the closest-time
-- heuristic biased against the CURRENT round: engagement start falls
-- between the prior round's stats-file time and the current round's
-- stats-file time, so the prior round's time was "closer". Effect:
-- 17,646 proximity rows + 29 lua_round_teams rows were attached to
-- the wrong rounds.id across 15 distinct misbound groups in April.
--
-- This migration rebinds rows where an exact-match rounds row exists
-- and the current round_id is a different rounds.id. Rows with NULL
-- round_id are left for the relinker cron to handle on its normal
-- schedule. Idempotent.

BEGIN;

-- Generic rebind template: for each proximity table with both
-- `round_id` and `round_start_unix`, set round_id to the rounds.id
-- whose (map_name, round_start_unix) match exactly.

-- 23 proximity/engagement tables + lua_round_teams
UPDATE combat_engagement t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE player_track t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE lua_round_teams t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_carrier_event t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_carrier_kill t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_carrier_return t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_combat_position t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_construction_event t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_crossfire_opportunity t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_escort_credit t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_focus_fire t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_hit_region t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_kill_outcome t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_lua_trade_kill t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_objective_focus t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_objective_run t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_reaction_metric t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_spawn_timing t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_support_summary t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_team_cohesion t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_team_push t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_trade_event t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

UPDATE proximity_vehicle_progress t SET round_id = r.id
FROM rounds r
WHERE r.map_name = t.map_name
  AND r.round_number = t.round_number
  AND r.round_start_unix = t.round_start_unix
  AND t.round_start_unix > 0
  AND t.round_id IS NOT NULL
  AND t.round_id != r.id;

INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('046_fix_proximity_round_id_exact_match',
        '046_fix_proximity_round_id_exact_match.sql',
        'self')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Verification:
--   SELECT tbl, COUNT(*) FROM (
--     SELECT 'combat_engagement' AS tbl FROM combat_engagement t
--     JOIN rounds r ON r.id = t.round_id
--     WHERE t.round_start_unix != r.round_start_unix
--   ) x GROUP BY tbl;
--   -- Expected: 0 rows for each table post-migration.
