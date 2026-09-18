-- Receipts certify a transactional DB effect, never delivery to every worker.
CREATE TABLE IF NOT EXISTS runtime_consumer_receipts (
    consumer_name TEXT NOT NULL CHECK (consumer_name ~ '^[a-z0-9_.:-]{1,64}$'),
    event_id BIGINT NOT NULL REFERENCES runtime_events(id) ON DELETE RESTRICT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (consumer_name, event_id)
);
CREATE TABLE IF NOT EXISTS runtime_cache_generations (
    cache_name TEXT PRIMARY KEY CHECK (cache_name ~ '^[a-z0-9_.:-]{1,64}$'),
    generation BIGINT NOT NULL DEFAULT 0 CHECK (generation >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
