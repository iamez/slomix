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
-- use. Two guards mirror session_scope.py's canonical round gate (Copilot
-- review on #546):
--   * rejected rounds (is_valid = FALSE, or round_status outside
--     completed/substitution/NULL) never produce a stamp — a stamped
--     rejected round would leak its kills into every direct
--     gaming_session_id reader even though the canonical scope excludes it;
--   * keys mapping to MORE than one distinct gaming_session_id (1 known
--     duplicate in dev) are skipped rather than guessed: a wrong stamp is
--     worse than a NULL, and NULL rows keep today's behaviour exactly.
--
-- Rows whose round key matches no accepted gsid-stamped round (legacy
-- orphans, ~6% in dev) intentionally stay NULL — they cannot be attributed
-- to a gaming session and should not appear in gsid-scoped panels.
--
-- IDEMPOTENT: statement 1 only touches rows WHERE gaming_session_id IS
-- NULL; statement 2 only un-stamps rows no accepted round can justify
-- (corrective for any earlier run of this migration without the validity
-- gate, and a no-op afterwards).

UPDATE storytelling_kill_impact k
SET gaming_session_id = r.gsid
FROM (
    SELECT round_start_unix, map_name, round_number,
           MIN(gaming_session_id) AS gsid
    FROM rounds
    WHERE gaming_session_id IS NOT NULL
      AND round_start_unix IS NOT NULL
      AND round_start_unix > 0
      AND is_valid IS DISTINCT FROM FALSE
      AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
    GROUP BY round_start_unix, map_name, round_number
    HAVING COUNT(DISTINCT gaming_session_id) = 1
) r
WHERE k.gaming_session_id IS NULL
  AND k.round_start_unix = r.round_start_unix
  AND k.map_name = r.map_name
  AND k.round_number = r.round_number;

-- Corrective pass: remove stamps that no ACCEPTED round of that gaming
-- session justifies (e.g. rows stamped from a rejected round by a pre-gate
-- run of this migration). The gsid-native compute path only ever writes
-- rows for round keys inside the canonical (validity-gated) scope, so its
-- stamps always survive this predicate.
UPDATE storytelling_kill_impact k
SET gaming_session_id = NULL
WHERE k.gaming_session_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM rounds r
      WHERE r.gaming_session_id = k.gaming_session_id
        AND r.round_start_unix = k.round_start_unix
        AND r.map_name = k.map_name
        AND r.round_number = k.round_number
        AND r.is_valid IS DISTINCT FROM FALSE
        AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
  );
