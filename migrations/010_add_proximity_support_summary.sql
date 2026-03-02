-- Add support uptime summary + isolation metadata

ALTER TABLE proximity_trade_event
    ADD COLUMN IF NOT EXISTS nearest_teammate_dist REAL,
    ADD COLUMN IF NOT EXISTS is_isolation_death BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS proximity_support_summary (
    id SERIAL PRIMARY KEY,

    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    support_samples INTEGER NOT NULL DEFAULT 0,
    total_samples INTEGER NOT NULL DEFAULT 0,
    support_uptime_pct REAL,

    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, round_start_unix)
);

CREATE INDEX IF NOT EXISTS idx_support_summary_session
    ON proximity_support_summary(session_date, round_number);
