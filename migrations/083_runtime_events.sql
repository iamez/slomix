-- Runtime v2 R01: initial canonical imports only; no backfill or consumers.
-- Apply before explicitly enabling EVENT_STREAM_ENABLED (default false).
-- Identity metadata is a historical snapshot, deliberately not a foreign key:
-- deleting a source round must neither erase its journal nor block repairs.
-- Sequence allocation is NOT commit order. Future consumers need receipts,
-- not just id > last_seen; NOTIFY is only a best-effort wake-up.
CREATE TABLE IF NOT EXISTS runtime_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type = 'round_stats_imported'),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    round_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL CHECK (round_number IN (1, 2)),
    gaming_session_id INTEGER,
    source_filename TEXT NOT NULL,
    source_payload_sha256 TEXT CHECK (
        source_payload_sha256 IS NULL OR source_payload_sha256 ~ '^[0-9a-f]{64}$'
    ),
    validation_passed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (round_id, event_type)
);

COMMENT ON TABLE runtime_events IS
    'Initial import journal, not final round state. NULL session/hash means unavailable at import. No pruning in R01.';
