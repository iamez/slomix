-- 072_repair_miscancelled_complete_rounds.sql
-- Repair rounds the restart detector wrongly marked 'cancelled' when they were
-- actually completed. A round that shares its match_id with a COMPLETED
-- counterpart of the other round_number was a finished map, not a restart false
-- start (two fast back-to-back plays of one map land their R2s <5 min apart,
-- which the QUICK_RESTART path miscancelled — see _detect_and_mark_restarts,
-- now guarded). Affects 8 rounds across gsids 10/20/40/41/42/99/125/144
-- (e.g. gsid 144 et_brewdog R2 = round 11206), each restoring a dropped map to
-- session scoring. Idempotent: only flips 'cancelled' → 'completed' where a
-- completed counterpart proves the match finished.
UPDATE rounds r
SET round_status = 'completed'
WHERE r.round_status = 'cancelled'
  AND r.is_valid
  AND r.round_number IN (1, 2)
  AND r.match_id IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM rounds r2
    WHERE r2.match_id = r.match_id
      AND r2.round_number = (CASE WHEN r.round_number = 1 THEN 2 ELSE 1 END)
      AND r2.round_status = 'completed'
  );
