-- migrations/057_add_rounds_is_valid.sql
-- Add a single-source-of-truth "counts for stats" flag to rounds.
--
-- Motivation: while waiting for a substitution, players sometimes run a filler
-- map (e.g. mp_sillyctf, a CTF map) that is NOT a competitive stopwatch round.
-- Those rounds leak into leaderboards / map stats / profiles. We mark them
-- is_valid = FALSE so every aggregate/display can exclude them with one
-- predicate (AND r.is_valid), instead of scattering map-name checks everywhere.
--
-- The classifier that sets this is config-driven (EXCLUDED_MAPS, default
-- mp_sillyctf) — see bot/core/round_contract.is_filler_map. A separate backfill
-- flips existing filler rounds (scripts/backfill_rounds_is_valid.py).
--
-- IDEMPOTENT (035-style): ADD COLUMN IF NOT EXISTS, re-runnable with no effect.
-- Purely additive — existing rows default to TRUE, all current behaviour
-- unchanged until a row is explicitly flagged FALSE.

BEGIN;

ALTER TABLE public.rounds
    ADD COLUMN IF NOT EXISTS is_valid BOOLEAN NOT NULL DEFAULT TRUE;

-- Partial index: the only interesting lookups are "the few invalid rounds".
CREATE INDEX IF NOT EXISTS idx_rounds_is_valid_false
    ON public.rounds (id) WHERE is_valid = FALSE;

COMMIT;
