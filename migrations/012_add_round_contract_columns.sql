-- Migration: 012_add_round_contract_columns.sql
-- Purpose: Persist WS0 score/stopwatch contract fields on rounds
-- Created: 2026-02-12

ALTER TABLE rounds
ADD COLUMN IF NOT EXISTS score_confidence VARCHAR(32);

ALTER TABLE rounds
ADD COLUMN IF NOT EXISTS round_stopwatch_state VARCHAR(16);

ALTER TABLE rounds
ADD COLUMN IF NOT EXISTS time_to_beat_seconds INTEGER;

ALTER TABLE rounds
ADD COLUMN IF NOT EXISTS next_timelimit_minutes INTEGER;

CREATE INDEX IF NOT EXISTS idx_rounds_score_confidence
ON rounds(score_confidence);

CREATE INDEX IF NOT EXISTS idx_rounds_stopwatch_state
ON rounds(round_stopwatch_state);

COMMENT ON COLUMN rounds.score_confidence IS 'WS0 confidence state: verified_header|time_fallback|ambiguous|missing';
COMMENT ON COLUMN rounds.round_stopwatch_state IS 'WS0 stopwatch state: FULL_HOLD|TIME_SET';
COMMENT ON COLUMN rounds.time_to_beat_seconds IS 'WS0 stopwatch contract value for R1 TIME_SET rounds';
COMMENT ON COLUMN rounds.next_timelimit_minutes IS 'WS0 computed next timelimit for stopwatch rounds';
