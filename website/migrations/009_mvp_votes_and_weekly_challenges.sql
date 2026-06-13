-- ============================================================================
-- Migration 009: MVP votes + Weekly challenges (VISION_2026 Sprint S3 "VEČER")
-- ============================================================================
-- - session_mvp_votes: peer MVP voting on a finished gaming session
--   (one changeable vote per user per session; vision R1 §1.4 peer-voted).
-- - weekly_challenges: admin-defined challenge of the week, surfaced in the
--   morning digest + home.
-- Idempotent (CREATE ... IF NOT EXISTS). Tables owned by etlegacy_user (the
-- website + bot connection role); defensive grants to website_app mirror
-- migration 008 so a website_app role, if present, also works.
-- ============================================================================

CREATE TABLE IF NOT EXISTS session_mvp_votes (
    id BIGSERIAL PRIMARY KEY,
    gaming_session_id INTEGER NOT NULL,
    voter_user_id BIGINT NOT NULL,
    nominated_guid TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (gaming_session_id, voter_user_id)
);
CREATE INDEX IF NOT EXISTS idx_session_mvp_votes_session
    ON session_mvp_votes (gaming_session_id);
CREATE INDEX IF NOT EXISTS idx_session_mvp_votes_nominee
    ON session_mvp_votes (gaming_session_id, nominated_guid);

CREATE TABLE IF NOT EXISTS weekly_challenges (
    id BIGSERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL UNIQUE,   -- Monday of the ISO week
    title TEXT NOT NULL,
    description TEXT,
    created_by_user_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_weekly_challenges_week
    ON weekly_challenges (week_start_date DESC);

-- Defensive grants (no-op if website_app role is absent) — mirrors 008.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
            session_mvp_votes, weekly_challenges TO website_app;
        GRANT USAGE, SELECT ON SEQUENCE
            session_mvp_votes_id_seq, weekly_challenges_id_seq TO website_app;
    END IF;
END;
$$;
