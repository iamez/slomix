-- migrations/064_backfill_kis_gaming_session_id.sql
-- Backfill storytelling_kill_impact.gaming_session_id from rounds.
--
-- Motivation: 063 added the column nullable and explicitly skipped the
-- backfill ("nothing currently reads this column"). PRs #533/#535/#539 then
-- started reading it as a WHERE filter (useless-defense, PWC crossfire,
-- enabler), so every session computed before the gsid-native path went live
-- (~87% of rows) silently returns empty/zero on those panels. Making the
-- column honest fixes all six read sites at once without touching their
-- queries.
--
-- Join key is the canonical round key (round_start_unix, map_name,
-- round_number) — the same triple _scope_row_filter/round_key_filter_sql
-- use. Keys that map to MORE than one distinct gaming_session_id (1 known
-- duplicate in dev) are skipped rather than guessed: a wrong stamp is worse
-- than a NULL, and NULL rows keep today's behaviour exactly.
--
-- Rows whose round key matches no gsid-stamped round (legacy orphans,
-- ~6% in dev) intentionally stay NULL — they cannot be attributed to a
-- gaming session and should not appear in gsid-scoped panels.
--
-- IDEMPOTENT: only touches rows WHERE gaming_session_id IS NULL, so a
-- re-run finds nothing left to update.

UPDATE storytelling_kill_impact k
SET gaming_session_id = r.gsid
FROM (
    SELECT round_start_unix, map_name, round_number,
           MIN(gaming_session_id) AS gsid
    FROM rounds
    WHERE gaming_session_id IS NOT NULL
      AND round_start_unix IS NOT NULL
      AND round_start_unix > 0
    GROUP BY round_start_unix, map_name, round_number
    HAVING COUNT(DISTINCT gaming_session_id) = 1
) r
WHERE k.gaming_session_id IS NULL
  AND k.round_start_unix = r.round_start_unix
  AND k.map_name = r.map_name
  AND k.round_number = r.round_number;
