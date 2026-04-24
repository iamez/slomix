-- migrations/048_orphan_recovery_drift_tolerance.sql
-- Class C orphan recovery: NULL-round_id rows where the Lua
-- `round_start_unix` drifted from the stats-file value by up to ±15min
-- (typical Lua v1.6.0 warmup vs stats-file first-frag drift, per RCA
-- 2026-04-24).
--
-- Rebind ONLY when there is EXACTLY ONE same-day rounds row with
-- matching (map_name, round_number) AND the drift is within ±900s
-- (15 min). The unique-candidate guard is the key safety: without it,
-- scrim sessions that replay the same (map, rn) on the same day would
-- produce ambiguous matches and we could mis-bind to the wrong round.
--
-- Rows that remain unrecovered after this migration fall into:
--   - Class B (rounds.round_start_unix IS NULL, pre-Feb-11-2026 era) —
--     handled separately by migration 049 via backfill.
--   - Class C-ambiguous (multiple same-day candidates) — left NULL.
--     Analytics under-count accepted; manual audit if needed.
--   - Class D (no rounds row for that map+rn ever) — left NULL, drop
--     planned for a future migration if count grows.
--
-- Idempotent: on re-run the CTE finds zero rows to recover because
-- previous run already linked them.

BEGIN;

-- Generic CTE: for each target table, find orphan groups (distinct
-- map+rn+unix) with EXACTLY ONE same-day candidate round within ±15min,
-- then UPDATE the matching rows.
--
-- We use one CTE per table (can't easily share across schemas in one
-- statement). Table-specific CTEs are near-identical — keep them
-- expanded for readability.

WITH recoverable AS (
  SELECT t.map_name, t.round_number, t.round_start_unix, MIN(r.id) AS target_round_id
  FROM combat_engagement t
  JOIN rounds r
    ON r.map_name = t.map_name
   AND r.round_number = t.round_number
   AND r.round_start_unix IS NOT NULL
   AND DATE(TO_TIMESTAMP(r.round_start_unix)) = DATE(TO_TIMESTAMP(t.round_start_unix))
   AND ABS(r.round_start_unix - t.round_start_unix) <= 900
  WHERE t.round_id IS NULL AND t.round_start_unix > 0
  GROUP BY t.map_name, t.round_number, t.round_start_unix
  HAVING COUNT(DISTINCT r.id) = 1
)
UPDATE combat_engagement ce
SET round_id = rec.target_round_id
FROM recoverable rec
WHERE ce.map_name = rec.map_name
  AND ce.round_number = rec.round_number
  AND ce.round_start_unix = rec.round_start_unix
  AND ce.round_id IS NULL;

WITH recoverable AS (
  SELECT t.map_name, t.round_number, t.round_start_unix, MIN(r.id) AS target_round_id
  FROM player_track t
  JOIN rounds r
    ON r.map_name = t.map_name
   AND r.round_number = t.round_number
   AND r.round_start_unix IS NOT NULL
   AND DATE(TO_TIMESTAMP(r.round_start_unix)) = DATE(TO_TIMESTAMP(t.round_start_unix))
   AND ABS(r.round_start_unix - t.round_start_unix) <= 900
  WHERE t.round_id IS NULL AND t.round_start_unix > 0
  GROUP BY t.map_name, t.round_number, t.round_start_unix
  HAVING COUNT(DISTINCT r.id) = 1
)
UPDATE player_track pt
SET round_id = rec.target_round_id
FROM recoverable rec
WHERE pt.map_name = rec.map_name
  AND pt.round_number = rec.round_number
  AND pt.round_start_unix = rec.round_start_unix
  AND pt.round_id IS NULL;

WITH recoverable AS (
  SELECT t.map_name, t.round_number, t.round_start_unix, MIN(r.id) AS target_round_id
  FROM lua_round_teams t
  JOIN rounds r
    ON r.map_name = t.map_name
   AND r.round_number = t.round_number
   AND r.round_start_unix IS NOT NULL
   AND DATE(TO_TIMESTAMP(r.round_start_unix)) = DATE(TO_TIMESTAMP(t.round_start_unix))
   AND ABS(r.round_start_unix - t.round_start_unix) <= 900
  WHERE t.round_id IS NULL AND t.round_start_unix > 0
  GROUP BY t.map_name, t.round_number, t.round_start_unix
  HAVING COUNT(DISTINCT r.id) = 1
)
UPDATE lua_round_teams lrt
SET round_id = rec.target_round_id
FROM recoverable rec
WHERE lrt.map_name = rec.map_name
  AND lrt.round_number = rec.round_number
  AND lrt.round_start_unix = rec.round_start_unix
  AND lrt.round_id IS NULL;

WITH recoverable AS (
  SELECT t.map_name, t.round_number, t.round_start_unix, MIN(r.id) AS target_round_id
  FROM proximity_combat_position t
  JOIN rounds r
    ON r.map_name = t.map_name
   AND r.round_number = t.round_number
   AND r.round_start_unix IS NOT NULL
   AND DATE(TO_TIMESTAMP(r.round_start_unix)) = DATE(TO_TIMESTAMP(t.round_start_unix))
   AND ABS(r.round_start_unix - t.round_start_unix) <= 900
  WHERE t.round_id IS NULL AND t.round_start_unix > 0
  GROUP BY t.map_name, t.round_number, t.round_start_unix
  HAVING COUNT(DISTINCT r.id) = 1
)
UPDATE proximity_combat_position pcp
SET round_id = rec.target_round_id
FROM recoverable rec
WHERE pcp.map_name = rec.map_name
  AND pcp.round_number = rec.round_number
  AND pcp.round_start_unix = rec.round_start_unix
  AND pcp.round_id IS NULL;

WITH recoverable AS (
  SELECT t.map_name, t.round_number, t.round_start_unix, MIN(r.id) AS target_round_id
  FROM proximity_team_cohesion t
  JOIN rounds r
    ON r.map_name = t.map_name
   AND r.round_number = t.round_number
   AND r.round_start_unix IS NOT NULL
   AND DATE(TO_TIMESTAMP(r.round_start_unix)) = DATE(TO_TIMESTAMP(t.round_start_unix))
   AND ABS(r.round_start_unix - t.round_start_unix) <= 900
  WHERE t.round_id IS NULL AND t.round_start_unix > 0
  GROUP BY t.map_name, t.round_number, t.round_start_unix
  HAVING COUNT(DISTINCT r.id) = 1
)
UPDATE proximity_team_cohesion ptc
SET round_id = rec.target_round_id
FROM recoverable rec
WHERE ptc.map_name = rec.map_name
  AND ptc.round_number = rec.round_number
  AND ptc.round_start_unix = rec.round_start_unix
  AND ptc.round_id IS NULL;

WITH recoverable AS (
  SELECT t.map_name, t.round_number, t.round_start_unix, MIN(r.id) AS target_round_id
  FROM proximity_hit_region t
  JOIN rounds r
    ON r.map_name = t.map_name
   AND r.round_number = t.round_number
   AND r.round_start_unix IS NOT NULL
   AND DATE(TO_TIMESTAMP(r.round_start_unix)) = DATE(TO_TIMESTAMP(t.round_start_unix))
   AND ABS(r.round_start_unix - t.round_start_unix) <= 900
  WHERE t.round_id IS NULL AND t.round_start_unix > 0
  GROUP BY t.map_name, t.round_number, t.round_start_unix
  HAVING COUNT(DISTINCT r.id) = 1
)
UPDATE proximity_hit_region phr
SET round_id = rec.target_round_id
FROM recoverable rec
WHERE phr.map_name = rec.map_name
  AND phr.round_number = rec.round_number
  AND phr.round_start_unix = rec.round_start_unix
  AND phr.round_id IS NULL;

WITH recoverable AS (
  SELECT t.map_name, t.round_number, t.round_start_unix, MIN(r.id) AS target_round_id
  FROM proximity_reaction_metric t
  JOIN rounds r
    ON r.map_name = t.map_name
   AND r.round_number = t.round_number
   AND r.round_start_unix IS NOT NULL
   AND DATE(TO_TIMESTAMP(r.round_start_unix)) = DATE(TO_TIMESTAMP(t.round_start_unix))
   AND ABS(r.round_start_unix - t.round_start_unix) <= 900
  WHERE t.round_id IS NULL AND t.round_start_unix > 0
  GROUP BY t.map_name, t.round_number, t.round_start_unix
  HAVING COUNT(DISTINCT r.id) = 1
)
UPDATE proximity_reaction_metric prm
SET round_id = rec.target_round_id
FROM recoverable rec
WHERE prm.map_name = rec.map_name
  AND prm.round_number = rec.round_number
  AND prm.round_start_unix = rec.round_start_unix
  AND prm.round_id IS NULL;

INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('048_orphan_recovery_drift_tolerance',
        '048_orphan_recovery_drift_tolerance.sql',
        'self')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Rationale for limiting to 7 tables (not 23 like 046/047):
-- The RCA 2026-04-24 found drift-orphans concentrated in these 7
-- tables (combat_engagement 4748, player_track 1795,
-- proximity_team_cohesion 7694, proximity_hit_region 399,
-- proximity_reaction_metric 139, lua_round_teams 20, and
-- proximity_combat_position indirectly via position data). The other
-- 16 proximity tables either had zero post-047 NULLs or are derivative
-- of these primary tables and will be recovered transitively.
