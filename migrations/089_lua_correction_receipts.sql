-- Successful atomic correction receipt; not a Discord/linking receipt.
CREATE TABLE IF NOT EXISTS lua_correction_receipts (
    input_id BIGINT PRIMARY KEY REFERENCES lua_correction_inputs(id) ON DELETE RESTRICT,
    round_id INTEGER NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
