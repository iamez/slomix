-- Voice Channel Activity Tracking Tables
-- Run this migration to add voice channel monitoring similar to game server monitoring

-- Table to track current voice channel members
CREATE TABLE IF NOT EXISTS voice_members (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    member_name VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    left_at TIMESTAMPTZ DEFAULT NULL,
    CONSTRAINT unique_active_member UNIQUE (discord_id, left_at)
);

CREATE INDEX idx_voice_members_active ON voice_members(discord_id) WHERE left_at IS NULL;
CREATE INDEX idx_voice_members_joined_at ON voice_members(joined_at DESC);

-- Table to track voice channel activity history (similar to server_status_history)
CREATE TABLE IF NOT EXISTS voice_status_history (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    member_count INT NOT NULL DEFAULT 0,
    channel_id BIGINT,
    channel_name VARCHAR(255),
    members JSONB DEFAULT '[]',  -- Array of {discord_id, name}
    first_joiner_id BIGINT,  -- Who joined first in this session
    first_joiner_name VARCHAR(255)
);

CREATE INDEX idx_voice_status_history_recorded_at ON voice_status_history(recorded_at DESC);
CREATE INDEX idx_voice_status_history_first_joiner ON voice_status_history(first_joiner_id);

-- View for easy querying of current voice status
CREATE OR REPLACE VIEW current_voice_status AS
SELECT 
    COUNT(*) as member_count,
    channel_id,
    channel_name,
    JSONB_AGG(
        JSONB_BUILD_OBJECT(
            'discord_id', discord_id,
            'name', member_name,
            'joined_at', joined_at
        ) ORDER BY joined_at ASC
    ) as members,
    MIN(joined_at) as session_start,
    (SELECT discord_id FROM voice_members WHERE left_at IS NULL ORDER BY joined_at ASC LIMIT 1) as first_joiner_id,
    (SELECT member_name FROM voice_members WHERE left_at IS NULL ORDER BY joined_at ASC LIMIT 1) as first_joiner_name
FROM voice_members
WHERE left_at IS NULL
GROUP BY channel_id, channel_name;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON voice_members TO etlegacy_user;
GRANT SELECT, INSERT ON voice_status_history TO etlegacy_user;
GRANT SELECT ON current_voice_status TO etlegacy_user;
GRANT USAGE, SELECT ON SEQUENCE voice_members_id_seq TO etlegacy_user;
GRANT USAGE, SELECT ON SEQUENCE voice_status_history_id_seq TO etlegacy_user;
