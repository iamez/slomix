-- Durable input only: not a correction-completion or transport-delivery receipt.
CREATE TABLE IF NOT EXISTS lua_correction_inputs (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL CHECK (source_key ~ '^[a-z0-9_.:-]{1,64}$'),
    payload_version INTEGER NOT NULL CHECK (payload_version = 1),
    payload_digest TEXT NOT NULL CHECK (payload_digest ~ '^[a-f0-9]{64}$'),
    map_name TEXT NOT NULL CHECK (map_name ~ '^[a-z0-9_-]{1,128}$'),
    round_number INTEGER NOT NULL CHECK (round_number IN (1, 2)),
    round_start_unix BIGINT NOT NULL CHECK (round_start_unix > 0),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_key, payload_version, payload_digest)
);
CREATE INDEX IF NOT EXISTS idx_lua_correction_inputs_identity
    ON lua_correction_inputs (source_key, map_name, round_number, round_start_unix);
