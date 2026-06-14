-- ============================================================================
-- Migration 010: Season awards + Parimutuel predictions (VISION_2026 S4 "TEKMA")
-- ============================================================================
-- - season_awards: permanent engraved season awards (MVP/Iron Man/Most Improved/
--   Oracle + manual), keyed (season_id, award_key, player_guid).
-- - user_points / parimutuel_markets / parimutuel_bets: valueless-points
--   parimutuel betting on the session winner (one changeable bet per market).
-- Idempotent (CREATE ... IF NOT EXISTS). Tables owned by etlegacy_user;
-- defensive website_app grants mirror 008/009.
-- ============================================================================

CREATE TABLE IF NOT EXISTS season_awards (
    id BIGSERIAL PRIMARY KEY,
    season_id TEXT NOT NULL,
    award_key TEXT NOT NULL,           -- 'mvp' | 'iron_man' | 'most_improved' | 'oracle' | manual
    player_guid TEXT NOT NULL,
    player_name TEXT,
    value_text TEXT,
    value_num REAL,
    source JSONB DEFAULT '{}'::jsonb,
    created_by_user_id BIGINT REFERENCES website_users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (season_id, award_key, player_guid)
);
CREATE INDEX IF NOT EXISTS idx_season_awards_season ON season_awards (season_id, award_key);

CREATE TABLE IF NOT EXISTS user_points (
    user_id BIGINT PRIMARY KEY REFERENCES website_users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 100,
    lifetime_earned INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parimutuel_markets (
    id BIGSERIAL PRIMARY KEY,
    gaming_session_id INTEGER,
    session_date DATE,
    market_type TEXT NOT NULL DEFAULT 'session_winner',
    team_a_label TEXT NOT NULL DEFAULT 'Team A',
    team_b_label TEXT NOT NULL DEFAULT 'Team B',
    status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'closed' | 'settled'
    outcome TEXT,                          -- 'team_a' | 'team_b' | 'void'
    total_pool INTEGER NOT NULL DEFAULT 0,
    created_by_user_id BIGINT REFERENCES website_users(id) ON DELETE SET NULL,
    opens_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closes_at TIMESTAMP,
    settled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_parimutuel_markets_status ON parimutuel_markets (status, id DESC);

CREATE TABLE IF NOT EXISTS parimutuel_bets (
    id BIGSERIAL PRIMARY KEY,
    market_id BIGINT NOT NULL REFERENCES parimutuel_markets(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE CASCADE,
    choice TEXT NOT NULL,                  -- 'team_a' | 'team_b'
    amount INTEGER NOT NULL,
    payout INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'won' | 'lost' | 'refunded'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (market_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_parimutuel_bets_market ON parimutuel_bets (market_id, choice);

-- Defensive grants (no-op if website_app role is absent) — mirrors 008/009.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
            season_awards, user_points, parimutuel_markets, parimutuel_bets TO website_app;
        GRANT USAGE, SELECT, UPDATE ON SEQUENCE
            season_awards_id_seq, parimutuel_markets_id_seq, parimutuel_bets_id_seq TO website_app;
    END IF;
END;
$$;
