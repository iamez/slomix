-- Migration: Engagement Features (MVP Voting, Player Titles, Rare Achievements)
-- Created: 2025-11-20
-- Branch: future-feature
-- Description: Adds tables for MVP voting system and player title/badge system

-- ============================================
-- MVP Voting System
-- ============================================

CREATE TABLE IF NOT EXISTS mvp_votes (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    vote_count INTEGER NOT NULL,
    total_votes INTEGER NOT NULL,
    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, player_guid)
);

CREATE INDEX IF NOT EXISTS idx_mvp_votes_session ON mvp_votes(session_id);
CREATE INDEX IF NOT EXISTS idx_mvp_votes_player ON mvp_votes(player_guid);

COMMENT ON TABLE mvp_votes IS 'Stores community MVP voting results for gaming sessions';
COMMENT ON COLUMN mvp_votes.session_id IS 'Gaming session ID from rounds.gaming_session_id';
COMMENT ON COLUMN mvp_votes.player_guid IS 'Player GUID - links to player_comprehensive_stats';
COMMENT ON COLUMN mvp_votes.vote_count IS 'Number of votes this player received';
COMMENT ON COLUMN mvp_votes.total_votes IS 'Total votes cast in this session';

-- ============================================
-- Player Titles/Badges System
-- ============================================

CREATE TABLE IF NOT EXISTS player_titles (
    id SERIAL PRIMARY KEY,
    player_guid TEXT NOT NULL,
    title_id TEXT NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_equipped BOOLEAN DEFAULT FALSE,
    UNIQUE(player_guid, title_id)
);

CREATE INDEX IF NOT EXISTS idx_player_titles_guid ON player_titles(player_guid);
CREATE INDEX IF NOT EXISTS idx_player_titles_equipped ON player_titles(player_guid, is_equipped);

COMMENT ON TABLE player_titles IS 'Tracks unlocked titles and equipped badges for players';
COMMENT ON COLUMN player_titles.player_guid IS 'Player GUID - links to player_comprehensive_stats';
COMMENT ON COLUMN player_titles.title_id IS 'Title identifier (e.g., sharpshooter, fragger, medic)';
COMMENT ON COLUMN player_titles.is_equipped IS 'Whether this title is currently displayed';

-- ============================================
-- Migration Complete
-- ============================================

-- Note: Rare Achievements Service does not require additional tables
-- It reads from existing player_comprehensive_stats and rounds tables

-- To verify tables were created:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('mvp_votes', 'player_titles');
