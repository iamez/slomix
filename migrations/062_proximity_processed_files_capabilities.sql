-- migrations/062_proximity_processed_files_capabilities.sql
-- Telemetry capability tracking for ET Performance v3 (audit AUD-007; §6).
--
-- v3 must distinguish a TRUE zero (the event genuinely didn't happen) from
-- MISSING telemetry (the tracker never captured that signal for the round).
-- Recording the tracker version, canonical round key, and a capabilities map
-- per processed file lets the rating compute per-round coverage instead of
-- guessing from neutral defaults.
--
-- IDEMPOTENT / additive: ADD COLUMN IF NOT EXISTS. Existing rows get NULL
-- capabilities (unknown) — the v3 shadow falls back to its population-level
-- coverage proxy until a backfill (owner-gated) populates these.

BEGIN;

ALTER TABLE proximity_processed_files
    ADD COLUMN IF NOT EXISTS tracker_version TEXT,
    ADD COLUMN IF NOT EXISTS round_key TEXT,
    ADD COLUMN IF NOT EXISTS capabilities JSONB;

COMMENT ON COLUMN proximity_processed_files.tracker_version IS
    'Lua tracker version string that produced the file (e.g. 6.02) — lets v3 map which telemetry signals were even possible';
COMMENT ON COLUMN proximity_processed_files.round_key IS
    'Canonical round key (session_date|map|round|start_unix) for joining a file to its round';
COMMENT ON COLUMN proximity_processed_files.capabilities IS
    'JSONB flags for which telemetry signals this file carried (e.g. {"kill_outcome": true, "combat_position": true, "shot_fired": false}) — a false/absent flag means MISSING, not a real zero';

CREATE INDEX IF NOT EXISTS idx_proximity_processed_round_key
    ON proximity_processed_files (round_key)
    WHERE round_key IS NOT NULL;

COMMIT;
