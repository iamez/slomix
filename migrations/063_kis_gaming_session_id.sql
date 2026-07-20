-- migrations/063_kis_gaming_session_id.sql
-- Add gaming_session_id to storytelling_kill_impact (Codex §5/§8 SS-B).
--
-- Motivation: KIS rows are keyed only by session_date, the same scope
-- defect Smart Stats' BOX score had (#524) — a gaming session that crosses
-- midnight has kills split across two independent session_date fragments
-- with no single key to fetch/delete/invalidate them as one unit. This
-- column lets the gsid-native compute path (kis.py
-- compute_session_kis_for_gsid) stamp every row it writes with the
-- resolved gaming_session_id, so a scope-wide DELETE/lookup no longer
-- needs to enumerate every date fragment by hand.
--
-- Nullable and additive: existing rows (and the legacy session_date-only
-- compute_session_kis() path, unchanged by this migration) keep
-- gaming_session_id NULL — nothing currently reads this column, so there
-- is no correctness requirement to backfill it.
--
-- IDEMPOTENT: ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS,
-- re-runnable with no effect.

ALTER TABLE storytelling_kill_impact
    ADD COLUMN IF NOT EXISTS gaming_session_id BIGINT NULL;

CREATE INDEX IF NOT EXISTS idx_kis_gaming_session_id
    ON storytelling_kill_impact (gaming_session_id)
    WHERE gaming_session_id IS NOT NULL;
