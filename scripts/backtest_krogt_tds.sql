-- Phase-0 backtest: KROGT + TDS over last 25 valid gaming sessions (READ-ONLY).
-- Usage: psql -h 127.0.0.1 -U etlegacy_user -d etlegacy -f scripts/backtest_krogt_tds.sql
--
-- First-run findings (dev, 2026-07-04, 13 players >=20 rounds):
--  * KROGT per-ROUND saturates (everyone 98-100%): CS KAST / R6 KOST work per-round
--    because there a round IS one life; in ET with respawns the K component is
--    trivially true. v2 must move to per-LIFE grain (kill_outcome + spawn_timing)
--    or a contribution-diversity score. Sub-components DO discriminate
--    (post R0-filter rerun: R 56-83%, T 56-75%, O 17-27%) and are usable standalone.
--  * TDS discriminates (10.8-24.4%) and its input is clean (median denied 7.3s,
--    max 57.8s, no negatives) BUT (a) only ~66% of valid rounds have kill_outcome
--    coverage — a production implementation must scope the denominator to covered
--    rounds EXPLICITLY (here it is accidentally correct only because uncovered
--    rounds have NULL actual_duration_seconds); (b) TDS ranking closely tracks
--    DPM, so ship it as a complement/divergence highlight, not a headline, and
--    integrate with the existing KPR (kill permanence) from ET Rating v2 rather
--    than adding a third kill-value formula.
-- (plain SELECT headers instead of psql \echo so non-psql SQL linters can parse this file)
SELECT '=== KROGT (% rounds with K/R/O/G/T contribution), min 20 rounds ===' AS section;
WITH last_sessions AS (
  -- played rounds only here too: a session whose only valid row is an R0
  -- match summary must not consume one of the 25 slots (codex P2, PR #434)
  SELECT DISTINCT gaming_session_id AS gsid FROM rounds
  WHERE is_valid IS DISTINCT FROM FALSE AND gaming_session_id IS NOT NULL
    AND round_number IN (1, 2)
  ORDER BY gsid DESC LIMIT 25
),
rr AS (
  SELECT pcs.player_guid, MAX(pcs.player_name) AS name, r.id AS round_id,
         MAX(pcs.kills) AS kills, MAX(pcs.revives_given) AS revs,
         MAX(COALESCE(pcs.objectives_completed,0)+COALESCE(pcs.objectives_destroyed,0)
            +COALESCE(pcs.objectives_stolen,0)+COALESCE(pcs.objectives_returned,0)) AS objs,
         MAX(pcs.gibs) AS gibs
  FROM player_comprehensive_stats pcs
  JOIN rounds r ON r.id = pcs.round_id
  WHERE r.gaming_session_id IN (SELECT gsid FROM last_sessions)
    AND r.is_valid IS DISTINCT FROM FALSE
    -- played rounds only: round_number=0 match-summary rows are cumulative
    -- duplicates and would double-count each map (codex P2, PR #434)
    AND r.round_number IN (1, 2)
    AND pcs.player_guid NOT LIKE 'OMNIBOT%' AND pcs.player_name NOT LIKE '[BOT]%'
  GROUP BY pcs.player_guid, r.id
),
traded AS (
  SELECT UPPER(LEFT(original_victim_guid,8)) AS g8, round_id
  FROM proximity_lua_trade_kill WHERE round_id IS NOT NULL GROUP BY 1,2
)
SELECT MAX(rr.name) AS player, COUNT(*) AS rounds,
  ROUND(100.0*COUNT(*) FILTER (WHERE kills>0)/COUNT(*),1) AS k_pct,
  ROUND(100.0*COUNT(*) FILTER (WHERE revs>0)/COUNT(*),1) AS r_pct,
  ROUND(100.0*COUNT(*) FILTER (WHERE objs>0)/COUNT(*),1) AS o_pct,
  ROUND(100.0*COUNT(*) FILTER (WHERE gibs>0)/COUNT(*),1) AS g_pct,
  ROUND(100.0*COUNT(*) FILTER (WHERE t.g8 IS NOT NULL)/COUNT(*),1) AS t_pct,
  ROUND(100.0*COUNT(*) FILTER (WHERE kills>0 OR revs>0 OR objs>0 OR gibs>0 OR t.g8 IS NOT NULL)/COUNT(*),1) AS krogt_pct
FROM rr
LEFT JOIN traded t ON t.round_id = rr.round_id AND t.g8 = UPPER(LEFT(rr.player_guid,8))
GROUP BY rr.player_guid
HAVING COUNT(*) >= 20
ORDER BY krogt_pct DESC;

SELECT '=== TDS (effective denied seconds / played round seconds, %), min 20 rounds ===' AS section;
WITH last_sessions AS (
  -- played rounds only here too: a session whose only valid row is an R0
  -- match summary must not consume one of the 25 slots (codex P2, PR #434)
  SELECT DISTINCT gaming_session_id AS gsid FROM rounds
  WHERE is_valid IS DISTINCT FROM FALSE AND gaming_session_id IS NOT NULL
    AND round_number IN (1, 2)
  ORDER BY gsid DESC LIMIT 25
),
k AS (
  SELECT UPPER(LEFT(killer_guid_canonical,8)) AS g8, round_id, SUM(effective_denied_ms) AS denied_ms
  FROM proximity_kill_outcome WHERE round_id IS NOT NULL GROUP BY 1,2
)
SELECT MAX(p.player_name) AS player, COUNT(*) AS rounds,
  ROUND(SUM(COALESCE(k.denied_ms,0))/1000.0/60,1) AS denied_min,
  ROUND(100.0*SUM(COALESCE(k.denied_ms,0))/1000.0/NULLIF(SUM(r.actual_duration_seconds),0),1) AS tds_pct
FROM player_comprehensive_stats p
JOIN rounds r ON r.id = p.round_id
LEFT JOIN k ON k.round_id = r.id AND k.g8 = UPPER(LEFT(p.player_guid,8))
WHERE r.gaming_session_id IN (SELECT gsid FROM last_sessions)
  AND r.is_valid IS DISTINCT FROM FALSE
  AND r.round_number IN (1, 2)  -- exclude round_number=0 match-summary rows
  AND p.player_guid NOT LIKE 'OMNIBOT%' AND p.player_name NOT LIKE '[BOT]%'
GROUP BY p.player_guid
HAVING COUNT(*) >= 20
ORDER BY tds_pct DESC;
