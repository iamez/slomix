-- Scheduling state is separate from retained payload and completion receipts.
CREATE TABLE IF NOT EXISTS lua_correction_attempts (
    input_id BIGINT PRIMARY KEY REFERENCES lua_correction_inputs(id) ON DELETE RESTRICT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    next_due_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    outcome TEXT NOT NULL DEFAULT 'pending' CHECK (outcome IN (
        'pending', 'applied', 'already_applied', 'missing_input', 'missing_round',
        'target_changed', 'ambiguous_round', 'conflicting_revision',
        'rejected', 'database_error', 'unexpected_error', 'contended'
    )),
    terminal BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (attempts < 5 OR terminal)
);
CREATE INDEX IF NOT EXISTS idx_lua_correction_attempts_due
    ON lua_correction_attempts (next_due_at, input_id) WHERE NOT terminal;
