-- migrations/059_add_rounds_start_unix_index.sql
-- Index rounds.round_start_unix for the "latest round" lookup.
--
-- Motivation: the betting auto-open loop (Faza B2, opt-in via
-- BETS_LIFECYCLE_SECONDS) finds the current live session with
--   SELECT gaming_session_id, round_start_unix FROM rounds
--   WHERE gaming_session_id IS NOT NULL AND round_start_unix IS NOT NULL
--   ORDER BY round_start_unix DESC LIMIT 1
-- The only existing round-start index is composite (map_name, round_number,
-- round_start_unix), which can't satisfy a global ORDER BY round_start_unix, so
-- the query falls back to a scan+sort each tick. This descending partial index
-- serves it directly. (Small table today, but the loop runs on an interval — no
-- reason to scan.)
--
-- IDEMPOTENT: CREATE INDEX IF NOT EXISTS, re-runnable with no effect. Purely
-- additive — no data or behaviour change.

CREATE INDEX IF NOT EXISTS idx_rounds_start_unix
    ON public.rounds (round_start_unix DESC)
    WHERE round_start_unix IS NOT NULL AND gaming_session_id IS NOT NULL;
