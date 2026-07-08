-- migrations/060_add_kis_formula_version.sql
-- Add formula_version to storytelling_kill_impact so the KIS cache can be
-- invalidated by version, not just presence.
--
-- Motivation: compute_session_kis() (kis.py) treats "any row exists for
-- this session_date" as "fully computed, serve cached" — after changing
-- KIS multipliers/logic, sessions scored under the OLD formula silently
-- keep stale scores forever, since nothing compares versions (codex, PR
-- #478 follow-up audit finding #9). Backfilling existing rows with the
-- CURRENT version is correct: they WERE computed with today's logic, just
-- never tagged — the column only starts doing useful work the next time
-- FORMULA_VERSION in kis.py changes.
--
-- IDEMPOTENT: ADD COLUMN IF NOT EXISTS, re-runnable with no effect.

ALTER TABLE storytelling_kill_impact
    ADD COLUMN IF NOT EXISTS formula_version VARCHAR(20) NOT NULL DEFAULT 'kis-v2';

CREATE INDEX IF NOT EXISTS idx_kis_session_formula_version
    ON storytelling_kill_impact (session_date, formula_version);
