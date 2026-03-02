-- Proximity trade analytics (v1)
-- Stores trade opportunities/attempts/successes per death event

CREATE TABLE IF NOT EXISTS proximity_trade_event (
    id SERIAL PRIMARY KEY,

    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    victim_guid VARCHAR(32) NOT NULL,
    victim_name VARCHAR(64) NOT NULL,
    victim_team VARCHAR(10) NOT NULL,

    killer_guid VARCHAR(32),
    killer_name VARCHAR(64),

    death_time_ms INTEGER NOT NULL,
    trade_window_ms INTEGER NOT NULL,

    opportunity_count INTEGER DEFAULT 0,
    opportunities JSONB NOT NULL DEFAULT '[]',

    attempt_count INTEGER DEFAULT 0,
    attempts JSONB NOT NULL DEFAULT '[]',

    success_count INTEGER DEFAULT 0,
    successes JSONB NOT NULL DEFAULT '[]',

    missed_count INTEGER DEFAULT 0,
    missed_candidates JSONB NOT NULL DEFAULT '[]',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, round_start_unix, victim_guid, death_time_ms)
);

CREATE INDEX IF NOT EXISTS idx_trade_event_session
    ON proximity_trade_event(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_trade_event_victim
    ON proximity_trade_event(victim_guid);
CREATE INDEX IF NOT EXISTS idx_trade_event_killer
    ON proximity_trade_event(killer_guid);
