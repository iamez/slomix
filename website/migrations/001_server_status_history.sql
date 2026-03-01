-- Server Status History Table
-- Tracks game server activity for website charts and analytics
-- Run: psql -h 192.168.64.116 -U etlegacy_user -d etlegacy -f 001_server_status_history.sql

CREATE TABLE IF NOT EXISTS server_status_history (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    player_count INT NOT NULL DEFAULT 0,
    max_players INT NOT NULL DEFAULT 20,
    map_name VARCHAR(255),
    hostname VARCHAR(255),
    players JSONB DEFAULT '[]',  -- Array of {name, score, ping}
    ping_ms INT,
    online BOOLEAN NOT NULL DEFAULT false
);

-- Index for time-based queries (charts)
CREATE INDEX IF NOT EXISTS idx_server_status_history_recorded_at
ON server_status_history(recorded_at DESC);

-- Index for finding peak times
CREATE INDEX IF NOT EXISTS idx_server_status_history_player_count
ON server_status_history(player_count DESC) WHERE online = true;

-- Grant permissions to bot user
GRANT SELECT, INSERT ON server_status_history TO etlegacy_user;
GRANT USAGE, SELECT ON SEQUENCE server_status_history_id_seq TO etlegacy_user;

\echo ''
\echo '=========================================='
\echo 'server_status_history table created!'
\echo ''
\echo 'The monitoring service will now record'
\echo 'server activity every 10 minutes.'
\echo '=========================================='
