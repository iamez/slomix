-- WS1C / Proximity v4.2 reaction telemetry storage
-- Adds per-engagement reaction timing metrics from tracker REACTION_METRICS section.

CREATE TABLE IF NOT EXISTS proximity_reaction_metric (
    id SERIAL PRIMARY KEY,

    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    engagement_id INTEGER NOT NULL,
    target_guid VARCHAR(32) NOT NULL,
    target_name VARCHAR(64) NOT NULL,
    target_team VARCHAR(10) NOT NULL,
    target_class VARCHAR(16) NOT NULL,

    outcome VARCHAR(20) NOT NULL,
    num_attackers INTEGER NOT NULL DEFAULT 0,

    return_fire_ms INTEGER,
    dodge_reaction_ms INTEGER,
    support_reaction_ms INTEGER,

    start_time_ms INTEGER NOT NULL DEFAULT 0,
    end_time_ms INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, round_start_unix, engagement_id, target_guid)
);

CREATE INDEX IF NOT EXISTS idx_reaction_session
    ON proximity_reaction_metric(session_date, round_number);

CREATE INDEX IF NOT EXISTS idx_reaction_target
    ON proximity_reaction_metric(target_guid);

CREATE INDEX IF NOT EXISTS idx_reaction_class
    ON proximity_reaction_metric(target_class);
