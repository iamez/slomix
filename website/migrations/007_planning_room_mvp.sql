-- ============================================================================
-- Migration 007: Planning Room MVP
-- ============================================================================
-- Adds planning-room persistence for game-night coordination:
-- - One planning session per date
-- - Team-name suggestions + votes
-- - Two-side team assignment scaffolding
-- ============================================================================

CREATE TABLE IF NOT EXISTS planning_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_date DATE NOT NULL UNIQUE,
    created_by_user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE RESTRICT,
    discord_thread_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS planning_team_names (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES planning_sessions(id) ON DELETE CASCADE,
    suggested_by_user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS planning_votes (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES planning_sessions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE CASCADE,
    suggestion_id BIGINT NOT NULL REFERENCES planning_team_names(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (session_id, user_id)
);

CREATE TABLE IF NOT EXISTS planning_teams (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES planning_sessions(id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('A', 'B')),
    captain_user_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (session_id, side)
);

CREATE TABLE IF NOT EXISTS planning_team_members (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES planning_sessions(id) ON DELETE CASCADE,
    team_id BIGINT NOT NULL REFERENCES planning_teams(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (team_id, user_id),
    UNIQUE (session_id, user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_planning_team_names_unique_lower
    ON planning_team_names (session_id, lower(name));
CREATE INDEX IF NOT EXISTS idx_planning_sessions_date ON planning_sessions(session_date DESC);
CREATE INDEX IF NOT EXISTS idx_planning_votes_session ON planning_votes(session_id, suggestion_id);
CREATE INDEX IF NOT EXISTS idx_planning_team_members_session ON planning_team_members(session_id, team_id);
