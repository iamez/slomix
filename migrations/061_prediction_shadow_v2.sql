-- migrations/061_prediction_shadow_v2.sql
-- Prediction shadow program (audit AUD-006; remediation plan §5).
--
-- Predictions run in silent shadow first: every generated prediction is
-- stored with its full feature snapshot and coverage so calibration evidence
-- (Brier, reliability bins) can accrue BEFORE anything is published. Public
-- surfaces only show rows with publish_state = 'published'.
--
-- publish_state values: 'shadow' (stored, never shown), 'published'
-- (posted to Discord / visible on /api/predictions/recent).
--
-- IDEMPOTENT: ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS,
-- purely additive.

BEGIN;

ALTER TABLE match_predictions
    ADD COLUMN IF NOT EXISTS model_version TEXT NOT NULL DEFAULT 'heuristic-v1',
    ADD COLUMN IF NOT EXISTS publish_state TEXT NOT NULL DEFAULT 'shadow',
    ADD COLUMN IF NOT EXISTS prediction_event_key TEXT,
    ADD COLUMN IF NOT EXISTS feature_snapshot JSONB,
    ADD COLUMN IF NOT EXISTS feature_coverage JSONB,
    ADD COLUMN IF NOT EXISTS eligibility_reasons TEXT,
    ADD COLUMN IF NOT EXISTS gaming_session_id INTEGER,
    ADD COLUMN IF NOT EXISTS brier_score REAL;

-- Preserve visibility for predictions that were ALREADY posted to Discord
-- before this migration: the new publish_state defaults every legacy row to
-- 'shadow', but rows with a discord_message_id were public. Without this
-- backfill they would vanish from /api/predictions/recent and the bot's
-- !predictions commands (which now filter to publish_state='published').
-- (Codex review on #511.) Idempotent: only flips still-'shadow' posted rows.
UPDATE match_predictions
   SET publish_state = 'published'
 WHERE discord_message_id IS NOT NULL
   AND publish_state = 'shadow';

-- Deterministic dedup: a repeated voice split for the same evening/format/
-- rosters maps to the same event key and must not create a second row.
CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_event_key
    ON match_predictions (prediction_event_key)
    WHERE prediction_event_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_predictions_publish_state
    ON match_predictions (publish_state);

COMMENT ON COLUMN match_predictions.model_version IS
    'Formula/model version that generated this row (e.g. heuristic-v1.1); versions are never mixed in one calibration report';
COMMENT ON COLUMN match_predictions.publish_state IS
    'shadow = stored for calibration only, published = user-visible';
COMMENT ON COLUMN match_predictions.prediction_event_key IS
    'sha256 of (session_date, format, map, order-invariant sorted rosters) — dedups repeated voice splits';
COMMENT ON COLUMN match_predictions.feature_snapshot IS
    'Full factor outputs at prediction time (as-of snapshot; later results must never leak in)';
COMMENT ON COLUMN match_predictions.feature_coverage IS
    'Per-factor {available, sample_size, window} — a missing factor is recorded, not presented as evidence';
COMMENT ON COLUMN match_predictions.brier_score IS
    'Raw Brier score vs resolved binary outcome; NULL for draws/cancelled (excluded from binary calibration)';

COMMIT;
