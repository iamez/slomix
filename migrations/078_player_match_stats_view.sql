-- migrations/078_player_match_stats_view.sql
-- player_match_stats: a match's totals per player, DERIVED from the two halves.
--
-- The original "map summary" idea (2025) stored these totals as extra
-- player_comprehensive_stats rows stamped round_number = 0. The implementation
-- copied the parsed R2 file wholesale (`match_summary =
-- round_2_cumulative_result.copy()`, commit ee500692): the file's kills and
-- damage really are cumulative, but its playtime is not, so DPM read off R0
-- came out roughly doubled (574 vs 285) and every consumer was moved to
-- `round_number IN (1, 2)` instead. Nothing has read R0 since.
--
-- Measured 2026-08-19, R0 vs the sum of the halves, valid completed rounds:
-- 2025 rows never matched on time (0 of 2,981); rows from 2026-03 on match
-- within 6s in 99.8% of 2,266 cases, because the per-player TAB playtime fix
-- (commit 64d6f570, 2026-02-21) incidentally repaired them. So the idea works
-- now — but a stored copy is duplicated state that has to be kept in step, and
-- that is exactly what failed twice. A view cannot drift: it IS the sum.
--
-- Structural gates live here: halves only, a real match, a round the pipeline
-- itself calls valid, and a half the player actually played. That last one is
-- not squeamishness — 8 half-rows carry time_played_seconds = 0, four of them
-- with kills or damage on them, and folding those into a match total adds
-- damage to a denominator that gained no seconds. The records surface has
-- always dropped them; without this gate exactly one match-player row would
-- change value the day the view goes live.
--
-- Per-surface POLICY deliberately stays out: excluding [BOT]/OMNIBOT names is
-- a decision each surface makes, and baking it in would make the view useless
-- for bot-round diagnostics. `halves` lets a caller demand a complete match.
--
-- IDEMPOTENT.

BEGIN;

CREATE OR REPLACE VIEW player_match_stats AS
SELECT
    r.match_id,
    pcs.player_guid,
    MAX(pcs.player_name)          AS player_name,
    MAX(pcs.map_name)             AS map_name,
    MIN(pcs.round_date)           AS round_date,
    MAX(r.gaming_session_id)      AS gaming_session_id,
    COUNT(*)                      AS halves,
    SUM(pcs.kills)                AS kills,
    SUM(pcs.deaths)               AS deaths,
    SUM(pcs.damage_given)         AS damage_given,
    SUM(pcs.damage_received)      AS damage_received,
    SUM(pcs.headshots)            AS headshots,
    SUM(pcs.headshot_kills)       AS headshot_kills,
    SUM(pcs.xp)                   AS xp,
    SUM(pcs.gibs)                 AS gibs,
    SUM(pcs.revives_given)        AS revives_given,
    SUM(pcs.times_revived)        AS times_revived,
    SUM(pcs.time_played_seconds)  AS time_played_seconds,
    -- Damage per minute from the SUMMED seconds. Averaging the two halves'
    -- stored dpm, or dividing by a minute value rounded first, shifts the
    -- result by up to 0.1 on matches whose minute value does not terminate.
    CASE
        WHEN SUM(pcs.time_played_seconds) > 0
        THEN ROUND(SUM(pcs.damage_given) * 60.0 / SUM(pcs.time_played_seconds), 1)
    END                           AS dpm
FROM player_comprehensive_stats pcs
JOIN rounds r ON r.id = pcs.round_id
WHERE pcs.round_number IN (1, 2)
  AND pcs.time_played_seconds > 0
  AND r.match_id IS NOT NULL
  AND r.is_valid IS DISTINCT FROM FALSE
  AND r.round_status IS DISTINCT FROM 'orphan_r2'
GROUP BY r.match_id, pcs.player_guid;

COMMENT ON VIEW player_match_stats IS
    'Per-player totals for one match, summed from its R1 and R2 rows. Use this '
    'instead of the round_number = 0 rows, which are a stored copy of the R2 '
    'capture and are read by nothing (see migration header and docs/CLAUDE.md). '
    'Structural gates only (valid round, a half the player actually played) — '
    'filter [BOT]/OMNIBOT names per surface.';

-- Grant each role only if it exists, so a fresh CI/test database (which has
-- etlegacy_user but NOT website_app) applies cleanly while dev and prod get the
-- real grants. Same pattern as migrations 073 and 077.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
    GRANT SELECT ON player_match_stats TO website_app;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etlegacy_user') THEN
    GRANT SELECT ON player_match_stats TO etlegacy_user;
  END IF;
END $$;

COMMIT;
