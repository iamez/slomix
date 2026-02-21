-- ============================================================================
-- PostgreSQL Schema Reference for ET:Legacy Discord Bot (Slomix)
-- ============================================================================
-- Generated from production database: 2026-02-08
-- PostgreSQL 14 | Database: etlegacy
-- Total tables: 37 (excluding one-off backup tables)
--
-- Sections:
--   1. Core Bot Tables (7)
--   2. Lua Webhook Tables (2)
--   3. Round Detail Tables (3)
--   4. Competitive Analytics Tables (3)
--   5. Permission & Team Management Tables (3)
--   6. Session/Matchup Tables (2)
--   7. Website Monitoring Tables (4)
--   8. Proximity Tracking Tables (8)
--   9. Greatshot Demo Pipeline Tables (4)
--  10. Indexes
--  11. Seed Data
-- ============================================================================


-- ============================================================================
-- 1. CORE BOT TABLES
-- ============================================================================

-- Rounds: Main rounds/matches table
CREATE TABLE IF NOT EXISTS rounds (
    id SERIAL PRIMARY KEY,
    match_id TEXT,
    round_number INTEGER,
    round_date TEXT,
    round_time TEXT,
    map_name TEXT,
    time_limit TEXT,
    actual_time TEXT,
    defender_team INTEGER DEFAULT 0,
    winner_team INTEGER DEFAULT 0,
    is_tied BOOLEAN DEFAULT FALSE,
    round_outcome TEXT,
    gaming_session_id INTEGER,
    round_status VARCHAR(20) DEFAULT 'completed',
    -- Lua webhook timing (surrender fix, pause tracking)
    round_start_unix BIGINT,
    round_end_unix BIGINT,
    actual_duration_seconds INTEGER,
    total_pause_seconds INTEGER DEFAULT 0,
    pause_count INTEGER DEFAULT 0,
    end_reason VARCHAR(20),
    -- Bot round detection
    is_bot_round BOOLEAN DEFAULT FALSE,
    bot_player_count INTEGER DEFAULT 0,
    human_player_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, round_number)
);

-- Player comprehensive stats: 53+ columns per player per round
CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    round_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    clean_name TEXT,
    team INTEGER DEFAULT 0,
    -- Core combat
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    damage_given INTEGER DEFAULT 0,
    damage_received INTEGER DEFAULT 0,
    team_damage_given INTEGER DEFAULT 0,
    team_damage_received INTEGER DEFAULT 0,
    gibs INTEGER DEFAULT 0,
    self_kills INTEGER DEFAULT 0,
    full_selfkills INTEGER DEFAULT 0,
    team_kills INTEGER DEFAULT 0,
    team_gibs INTEGER DEFAULT 0,
    headshot_kills INTEGER DEFAULT 0,
    headshots INTEGER DEFAULT 0,
    -- Time tracking
    time_played_seconds INTEGER DEFAULT 0,
    time_played_minutes REAL DEFAULT 0,
    time_dead_minutes REAL DEFAULT 0,
    time_dead_ratio REAL DEFAULT 0,
    -- Performance metrics
    xp REAL DEFAULT 0,
    kd_ratio REAL DEFAULT 0,
    dpm REAL DEFAULT 0,
    efficiency REAL DEFAULT 0,
    -- Weapon stats
    bullets_fired INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0,
    -- Objective stats
    kill_assists INTEGER DEFAULT 0,
    objectives_completed INTEGER DEFAULT 0,
    objectives_destroyed INTEGER DEFAULT 0,
    objectives_stolen INTEGER DEFAULT 0,
    objectives_returned INTEGER DEFAULT 0,
    dynamites_planted INTEGER DEFAULT 0,
    dynamites_defused INTEGER DEFAULT 0,
    times_revived INTEGER DEFAULT 0,
    revives_given INTEGER DEFAULT 0,
    -- Advanced objective stats
    most_useful_kills INTEGER DEFAULT 0,
    useless_kills INTEGER DEFAULT 0,
    kill_steals INTEGER DEFAULT 0,
    denied_playtime INTEGER DEFAULT 0,
    constructions INTEGER DEFAULT 0,
    tank_meatshield INTEGER DEFAULT 0,
    -- Multikills
    double_kills INTEGER DEFAULT 0,
    triple_kills INTEGER DEFAULT 0,
    quad_kills INTEGER DEFAULT 0,
    multi_kills INTEGER DEFAULT 0,
    mega_kills INTEGER DEFAULT 0,
    -- Sprees
    killing_spree_best INTEGER DEFAULT 0,
    death_spree_worst INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    UNIQUE(round_id, player_guid)
);

-- Weapon comprehensive stats: Per-weapon breakdown per player per round
CREATE TABLE IF NOT EXISTS weapon_comprehensive_stats (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    round_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    weapon_name TEXT NOT NULL,
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    headshots INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    UNIQUE(round_id, player_guid, weapon_name)
);

-- Processed files: Track which stats files have been imported
CREATE TABLE IF NOT EXISTS processed_files (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    file_hash TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session teams: Team compositions for gaming sessions
CREATE TABLE IF NOT EXISTS session_teams (
    id SERIAL PRIMARY KEY,
    session_start_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    team_name TEXT NOT NULL,
    player_guids JSONB,
    player_names JSONB,
    color INTEGER,
    gaming_session_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_start_date, map_name, team_name)
);

-- Player links: Discord account to ET:Legacy GUID linking
CREATE TABLE IF NOT EXISTS player_links (
    id SERIAL PRIMARY KEY,
    player_guid TEXT UNIQUE NOT NULL,
    discord_id BIGINT UNIQUE NOT NULL,
    discord_username TEXT,
    player_name TEXT,
    display_name TEXT,
    display_name_source TEXT DEFAULT 'auto',
    display_name_updated_at TIMESTAMP,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player aliases: Player name/GUID tracking with frequency
CREATE TABLE IF NOT EXISTS player_aliases (
    id SERIAL PRIMARY KEY,
    guid TEXT NOT NULL,
    alias TEXT NOT NULL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    times_seen INTEGER DEFAULT 1,
    UNIQUE(guid, alias)
);

-- Achievement notification ledger: Restart-safe dedupe for live milestone posts
CREATE TABLE IF NOT EXISTS achievement_notification_ledger (
    id SERIAL PRIMARY KEY,
    achievement_id TEXT UNIQUE NOT NULL,
    player_guid TEXT NOT NULL,
    achievement_type VARCHAR(16) NOT NULL,
    milestone_threshold TEXT NOT NULL,
    claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- 2. LUA WEBHOOK TABLES
-- ============================================================================

-- Lua round teams: Real-time webhook data from game server Lua script
CREATE TABLE IF NOT EXISTS lua_round_teams (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(64) NOT NULL,
    round_number INTEGER NOT NULL,
    axis_players JSONB DEFAULT '[]'::jsonb,
    allies_players JSONB DEFAULT '[]'::jsonb,
    round_start_unix BIGINT,
    round_end_unix BIGINT,
    actual_duration_seconds INTEGER,
    total_pause_seconds INTEGER DEFAULT 0,
    pause_count INTEGER DEFAULT 0,
    end_reason VARCHAR(20),
    winner_team INTEGER,
    defender_team INTEGER,
    map_name VARCHAR(64),
    time_limit_minutes INTEGER,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    lua_version VARCHAR(16),
    lua_warmup_seconds INTEGER DEFAULT 0,
    lua_warmup_start_unix BIGINT DEFAULT 0,
    lua_pause_events JSONB DEFAULT '[]'::jsonb,
    surrender_caller_guid VARCHAR(64),
    surrender_caller_name VARCHAR(64),
    surrender_team INTEGER DEFAULT 0,
    axis_score INTEGER DEFAULT 0,
    allies_score INTEGER DEFAULT 0,
    round_id INTEGER,
    UNIQUE(match_id, round_number)
);

-- Lua spawn stats: Per-player spawn/death timing from Lua
CREATE TABLE IF NOT EXISTS lua_spawn_stats (
    id SERIAL PRIMARY KEY,
    match_id VARCHAR(64) NOT NULL,
    round_number INTEGER NOT NULL,
    round_id INTEGER,
    map_name VARCHAR(64),
    round_end_unix BIGINT,
    player_guid VARCHAR(32),
    player_name VARCHAR(64),
    spawn_count INTEGER DEFAULT 0,
    death_count INTEGER DEFAULT 0,
    dead_seconds INTEGER DEFAULT 0,
    avg_respawn_seconds INTEGER DEFAULT 0,
    max_respawn_seconds INTEGER DEFAULT 0,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, round_number, player_guid)
);


-- ============================================================================
-- 3. ROUND DETAIL TABLES
-- ============================================================================

-- Round awards: End-of-round awards from endstats.lua
CREATE TABLE IF NOT EXISTS round_awards (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    round_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    award_name TEXT NOT NULL,
    player_name TEXT NOT NULL,
    player_guid TEXT,
    award_value TEXT NOT NULL,
    award_value_numeric REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE
);

-- Round vs stats: Player vs player kill/death stats
CREATE TABLE IF NOT EXISTS round_vs_stats (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    round_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    player_guid TEXT,
    kills INTEGER NOT NULL DEFAULT 0,
    deaths INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE
);

-- Processed endstats files: Track endstats file processing
CREATE TABLE IF NOT EXISTS processed_endstats_files (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    round_id INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE SET NULL
);


-- ============================================================================
-- 4. COMPETITIVE ANALYTICS TABLES
-- ============================================================================

-- Match predictions: Automated match predictions
CREATE TABLE IF NOT EXISTS match_predictions (
    id SERIAL PRIMARY KEY,
    prediction_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_date TEXT NOT NULL,
    map_name TEXT,
    format TEXT NOT NULL,
    team_a_channel_id BIGINT NOT NULL,
    team_b_channel_id BIGINT NOT NULL,
    team_a_guids TEXT NOT NULL,
    team_b_guids TEXT NOT NULL,
    team_a_discord_ids TEXT NOT NULL,
    team_b_discord_ids TEXT NOT NULL,
    team_a_win_probability REAL NOT NULL,
    team_b_win_probability REAL NOT NULL,
    confidence TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    h2h_score REAL NOT NULL,
    form_score REAL NOT NULL,
    map_score REAL NOT NULL,
    subs_score REAL NOT NULL,
    weighted_score REAL NOT NULL,
    key_insight TEXT NOT NULL,
    h2h_details TEXT,
    form_details TEXT,
    map_details TEXT,
    subs_details TEXT,
    actual_winner INTEGER,
    team_a_actual_score INTEGER,
    team_b_actual_score INTEGER,
    prediction_correct BOOLEAN,
    prediction_accuracy REAL,
    discord_message_id BIGINT,
    discord_channel_id BIGINT,
    guid_coverage REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session results: Aggregated match outcomes
CREATE TABLE IF NOT EXISTS session_results (
    id SERIAL PRIMARY KEY,
    session_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    gaming_session_id INTEGER,
    team_1_guids TEXT NOT NULL,
    team_2_guids TEXT NOT NULL,
    team_1_names TEXT NOT NULL,
    team_2_names TEXT NOT NULL,
    format TEXT NOT NULL,
    total_rounds INTEGER NOT NULL,
    team_1_score INTEGER NOT NULL DEFAULT 0,
    team_2_score INTEGER NOT NULL DEFAULT 0,
    winning_team INTEGER NOT NULL,
    round_details TEXT,
    round_numbers TEXT NOT NULL,
    session_start TIMESTAMP NOT NULL,
    session_end TIMESTAMP,
    duration_minutes INTEGER,
    team_1_total_kills INTEGER DEFAULT 0,
    team_1_total_deaths INTEGER DEFAULT 0,
    team_1_total_damage INTEGER DEFAULT 0,
    team_2_total_kills INTEGER DEFAULT 0,
    team_2_total_deaths INTEGER DEFAULT 0,
    team_2_total_damage INTEGER DEFAULT 0,
    had_substitutions BOOLEAN DEFAULT FALSE,
    substitution_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    team_1_name TEXT,
    team_2_name TEXT,
    UNIQUE(session_date, map_name, gaming_session_id)
);

-- Map performance: Player per-map rolling averages
CREATE TABLE IF NOT EXISTS map_performance (
    id SERIAL PRIMARY KEY,
    player_guid TEXT NOT NULL,
    map_name TEXT NOT NULL,
    matches_played INTEGER NOT NULL DEFAULT 0,
    total_rounds INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    win_rate REAL NOT NULL DEFAULT 0.0,
    avg_kills REAL NOT NULL DEFAULT 0.0,
    avg_deaths REAL NOT NULL DEFAULT 0.0,
    avg_kd_ratio REAL NOT NULL DEFAULT 0.0,
    avg_dpm REAL NOT NULL DEFAULT 0.0,
    avg_efficiency REAL NOT NULL DEFAULT 0.0,
    last_match_date TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_guid, map_name)
);


-- ============================================================================
-- 5. PERMISSION & TEAM MANAGEMENT TABLES
-- ============================================================================

-- User permissions: 3-tier permission system (root/admin/moderator)
CREATE TABLE IF NOT EXISTS user_permissions (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255),
    tier VARCHAR(50) NOT NULL CHECK (tier IN ('root', 'admin', 'moderator')),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by BIGINT,
    reason TEXT
);

-- Permission audit log: Audit trail for permission changes
CREATE TABLE IF NOT EXISTS permission_audit_log (
    id SERIAL PRIMARY KEY,
    target_discord_id BIGINT NOT NULL,
    action VARCHAR(50) NOT NULL CHECK (action IN ('add', 'remove', 'promote', 'demote')),
    old_tier VARCHAR(50),
    new_tier VARCHAR(50),
    changed_by BIGINT NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT
);

-- Team pool: Pool of team names for assignment
CREATE TABLE IF NOT EXISTS team_pool (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT,
    color INTEGER,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- 6. SESSION/MATCHUP TABLES
-- ============================================================================

-- Matchup history: Lineup vs lineup analytics with JSONB
CREATE TABLE IF NOT EXISTS matchup_history (
    id SERIAL PRIMARY KEY,
    matchup_id TEXT NOT NULL,
    lineup_a_hash TEXT NOT NULL,
    lineup_b_hash TEXT NOT NULL,
    lineup_a_guids JSONB NOT NULL,
    lineup_b_guids JSONB NOT NULL,
    session_date TEXT NOT NULL,
    gaming_session_id INTEGER NOT NULL,
    winner_lineup_hash TEXT,
    lineup_a_score INTEGER DEFAULT 0,
    lineup_b_score INTEGER DEFAULT 0,
    map_name TEXT,
    player_stats JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(session_date, gaming_session_id, matchup_id)
);


-- ============================================================================
-- 7. WEBSITE MONITORING TABLES
-- ============================================================================

-- Server status history: Game server activity tracking
CREATE TABLE IF NOT EXISTS server_status_history (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    player_count INT NOT NULL DEFAULT 0,
    max_players INT NOT NULL DEFAULT 20,
    map_name VARCHAR(255),
    hostname VARCHAR(255),
    players JSONB DEFAULT '[]',
    ping_ms INT,
    online BOOLEAN NOT NULL DEFAULT false
);

-- Voice members: Current voice channel members
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

-- Voice status history: Voice channel activity history
CREATE TABLE IF NOT EXISTS voice_status_history (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    member_count INT NOT NULL DEFAULT 0,
    channel_id BIGINT,
    channel_name VARCHAR(255),
    members JSONB DEFAULT '[]',
    first_joiner_id BIGINT,
    first_joiner_name VARCHAR(255)
);

-- Live status: Current live game/voice status (website widget)
CREATE TABLE IF NOT EXISTS live_status (
    id SERIAL PRIMARY KEY,
    status_type VARCHAR(50) NOT NULL,
    data JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================================
-- 8. PROXIMITY TRACKING TABLES
-- ============================================================================

-- Combat engagement: Combat event tracking
CREATE TABLE IF NOT EXISTS combat_engagement (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    engagement_id INTEGER NOT NULL,
    start_time_ms INTEGER NOT NULL,
    end_time_ms INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    target_guid VARCHAR(32) NOT NULL,
    target_name VARCHAR(64) NOT NULL,
    target_team VARCHAR(10) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    total_damage_taken INTEGER NOT NULL,
    killer_guid VARCHAR(32),
    killer_name VARCHAR(64),
    position_path JSONB NOT NULL DEFAULT '[]',
    start_x REAL NOT NULL,
    start_y REAL NOT NULL,
    start_z REAL NOT NULL,
    end_x REAL NOT NULL,
    end_y REAL NOT NULL,
    end_z REAL NOT NULL,
    distance_traveled REAL NOT NULL,
    attackers JSONB NOT NULL DEFAULT '[]',
    num_attackers INTEGER NOT NULL,
    is_crossfire BOOLEAN NOT NULL DEFAULT FALSE,
    crossfire_delay_ms INTEGER,
    crossfire_participants JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, engagement_id)
);

-- Crossfire pairs: Player duo coordination tracking
CREATE TABLE IF NOT EXISTS crossfire_pairs (
    id SERIAL PRIMARY KEY,
    player1_guid VARCHAR(32) NOT NULL,
    player1_name VARCHAR(64),
    player2_guid VARCHAR(32) NOT NULL,
    player2_name VARCHAR(64),
    crossfire_count INTEGER DEFAULT 0,
    crossfire_kills INTEGER DEFAULT 0,
    total_combined_damage INTEGER DEFAULT 0,
    avg_delay_ms REAL,
    games_together INTEGER DEFAULT 0,
    first_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player1_guid, player2_guid)
);

-- Player teamplay stats: Aggregated teamplay statistics
CREATE TABLE IF NOT EXISTS player_teamplay_stats (
    id SERIAL PRIMARY KEY,
    player_guid VARCHAR(32) NOT NULL UNIQUE,
    player_name VARCHAR(64) NOT NULL,
    crossfire_participations INTEGER DEFAULT 0,
    crossfire_kills INTEGER DEFAULT 0,
    crossfire_damage INTEGER DEFAULT 0,
    crossfire_final_blows INTEGER DEFAULT 0,
    avg_crossfire_delay_ms REAL,
    solo_kills INTEGER DEFAULT 0,
    solo_engagements INTEGER DEFAULT 0,
    times_targeted INTEGER DEFAULT 0,
    times_focused INTEGER DEFAULT 0,
    focus_escapes INTEGER DEFAULT 0,
    focus_deaths INTEGER DEFAULT 0,
    solo_escapes INTEGER DEFAULT 0,
    solo_deaths INTEGER DEFAULT 0,
    avg_escape_distance REAL,
    avg_engagement_duration_ms REAL,
    total_damage_taken INTEGER DEFAULT 0,
    total_damage_dealt_crossfire INTEGER DEFAULT 0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Map kill heatmap: Grid-based kill/death density
CREATE TABLE IF NOT EXISTS map_kill_heatmap (
    id SERIAL PRIMARY KEY,
    map_name VARCHAR(64) NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    grid_size INTEGER DEFAULT 512,
    total_kills INTEGER DEFAULT 0,
    axis_kills INTEGER DEFAULT 0,
    allies_kills INTEGER DEFAULT 0,
    total_deaths INTEGER DEFAULT 0,
    axis_deaths INTEGER DEFAULT 0,
    allies_deaths INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(map_name, grid_x, grid_y)
);

-- Map movement heatmap: Traffic patterns
CREATE TABLE IF NOT EXISTS map_movement_heatmap (
    id SERIAL PRIMARY KEY,
    map_name VARCHAR(64) NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    grid_size INTEGER DEFAULT 512,
    traversal_count INTEGER DEFAULT 0,
    combat_count INTEGER DEFAULT 0,
    escape_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(map_name, grid_x, grid_y)
);

-- Player track: Full player movement tracking
CREATE TABLE IF NOT EXISTS player_track (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    player_guid VARCHAR(32) NOT NULL,
    player_name VARCHAR(64) NOT NULL,
    team VARCHAR(10) NOT NULL,
    player_class VARCHAR(16) NOT NULL,
    spawn_time_ms INTEGER NOT NULL,
    death_time_ms INTEGER,
    duration_ms INTEGER,
    first_move_time_ms INTEGER,
    time_to_first_move_ms INTEGER,
    sample_count INTEGER NOT NULL,
    path JSONB NOT NULL DEFAULT '[]',
    total_distance REAL,
    avg_speed REAL,
    sprint_percentage REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, player_guid, spawn_time_ms)
);

-- Proximity trade event: Trade opportunities per death
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
    nearest_teammate_dist REAL,
    is_isolation_death BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, round_start_unix, victim_guid, death_time_ms)
);

-- Proximity support summary: Support uptime tracking
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

-- Proximity objective focus: Per-player objective proximity
CREATE TABLE IF NOT EXISTS proximity_objective_focus (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    player_guid VARCHAR(32) NOT NULL,
    player_name VARCHAR(64) NOT NULL,
    team VARCHAR(10) NOT NULL,
    objective VARCHAR(64) NOT NULL,
    avg_distance REAL NOT NULL,
    time_within_radius_ms INTEGER NOT NULL,
    samples INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, round_number, player_guid)
);


-- ============================================================================
-- 9. GREATSHOT DEMO PIPELINE TABLES
-- ============================================================================

-- Greatshot demos: Uploaded demo files
CREATE TABLE IF NOT EXISTS greatshot_demos (
    id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    extension TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    content_hash_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error TEXT,
    metadata_json JSONB,
    warnings_json JSONB,
    analysis_json_path TEXT,
    report_txt_path TEXT,
    processing_started_at TIMESTAMP,
    processing_finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Greatshot analysis: Demo analysis results
CREATE TABLE IF NOT EXISTS greatshot_analysis (
    demo_id TEXT PRIMARY KEY REFERENCES greatshot_demos(id) ON DELETE CASCADE,
    metadata_json JSONB NOT NULL,
    stats_json JSONB NOT NULL,
    events_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Greatshot highlights: Extracted highlight clips
CREATE TABLE IF NOT EXISTS greatshot_highlights (
    id TEXT PRIMARY KEY,
    demo_id TEXT NOT NULL REFERENCES greatshot_demos(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    player TEXT,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    meta_json JSONB,
    clip_demo_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Greatshot renders: Rendered video clips
CREATE TABLE IF NOT EXISTS greatshot_renders (
    id TEXT PRIMARY KEY,
    highlight_id TEXT NOT NULL REFERENCES greatshot_highlights(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued',
    mp4_path TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- 10. INDEXES
-- ============================================================================

-- Core table indexes
CREATE INDEX IF NOT EXISTS idx_rounds_date ON rounds(round_date);
CREATE INDEX IF NOT EXISTS idx_rounds_status ON rounds(round_status);
CREATE INDEX IF NOT EXISTS idx_rounds_gaming_session ON rounds(gaming_session_id, map_name, round_number, round_status);
CREATE INDEX IF NOT EXISTS idx_player_stats_round ON player_comprehensive_stats(round_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_guid ON player_comprehensive_stats(player_guid);
CREATE INDEX IF NOT EXISTS idx_weapon_stats_round ON weapon_comprehensive_stats(round_id);
CREATE INDEX IF NOT EXISTS idx_processed_files_filename ON processed_files(filename);

-- Lua webhook indexes
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_match_id ON lua_round_teams(match_id);
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_captured_at ON lua_round_teams(captured_at);
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_round_id ON lua_round_teams(round_id);
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_surrender ON lua_round_teams(surrender_team) WHERE surrender_team > 0;
CREATE INDEX IF NOT EXISTS idx_lua_spawn_stats_match_id ON lua_spawn_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_lua_spawn_stats_round_id ON lua_spawn_stats(round_id);
CREATE INDEX IF NOT EXISTS idx_lua_spawn_stats_round_end ON lua_spawn_stats(round_end_unix);

-- Round detail indexes
CREATE INDEX IF NOT EXISTS idx_round_awards_round ON round_awards(round_id);
CREATE INDEX IF NOT EXISTS idx_round_awards_player ON round_awards(player_guid);
CREATE INDEX IF NOT EXISTS idx_round_awards_name ON round_awards(award_name);
CREATE INDEX IF NOT EXISTS idx_round_vs_stats_round ON round_vs_stats(round_id);
CREATE INDEX IF NOT EXISTS idx_round_vs_stats_player ON round_vs_stats(player_guid);
CREATE INDEX IF NOT EXISTS idx_processed_endstats_filename ON processed_endstats_files(filename);
CREATE UNIQUE INDEX IF NOT EXISTS uq_processed_endstats_round_id ON processed_endstats_files(round_id) WHERE round_id IS NOT NULL AND success = TRUE;
CREATE INDEX IF NOT EXISTS idx_achievement_ledger_player_guid ON achievement_notification_ledger(player_guid);

-- Predictions indexes
CREATE INDEX IF NOT EXISTS idx_predictions_session_date ON match_predictions(session_date);
CREATE INDEX IF NOT EXISTS idx_predictions_prediction_time ON match_predictions(prediction_time DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_format ON match_predictions(format);
CREATE INDEX IF NOT EXISTS idx_predictions_confidence ON match_predictions(confidence);
CREATE INDEX IF NOT EXISTS idx_predictions_discord_msg ON match_predictions(discord_message_id);
CREATE INDEX IF NOT EXISTS idx_predictions_outcome ON match_predictions(actual_winner) WHERE actual_winner IS NOT NULL;

-- Session results indexes
CREATE INDEX IF NOT EXISTS idx_session_results_date ON session_results(session_date DESC);
CREATE INDEX IF NOT EXISTS idx_session_results_map ON session_results(map_name);
CREATE INDEX IF NOT EXISTS idx_session_results_format ON session_results(format);
CREATE INDEX IF NOT EXISTS idx_session_results_gaming_session ON session_results(gaming_session_id);
CREATE INDEX IF NOT EXISTS idx_session_results_winner ON session_results(winning_team);
CREATE INDEX IF NOT EXISTS idx_session_results_teams ON session_results(team_1_guids, team_2_guids);
CREATE INDEX IF NOT EXISTS idx_session_results_team1_name ON session_results(team_1_name);
CREATE INDEX IF NOT EXISTS idx_session_results_team2_name ON session_results(team_2_name);

-- Map performance indexes
CREATE INDEX IF NOT EXISTS idx_map_performance_guid ON map_performance(player_guid);
CREATE INDEX IF NOT EXISTS idx_map_performance_map ON map_performance(map_name);
CREATE INDEX IF NOT EXISTS idx_map_performance_winrate ON map_performance(win_rate DESC);

-- Permission indexes
CREATE INDEX IF NOT EXISTS idx_user_permissions_discord_id ON user_permissions(discord_id);
CREATE INDEX IF NOT EXISTS idx_user_permissions_tier ON user_permissions(tier);
CREATE INDEX IF NOT EXISTS idx_audit_target ON permission_audit_log(target_discord_id);
CREATE INDEX IF NOT EXISTS idx_audit_changed_by ON permission_audit_log(changed_by);

-- Team pool indexes
CREATE INDEX IF NOT EXISTS idx_team_pool_active ON team_pool(active) WHERE active = true;

-- Matchup history indexes
CREATE INDEX IF NOT EXISTS idx_matchup_history_matchup_id ON matchup_history(matchup_id);
CREATE INDEX IF NOT EXISTS idx_matchup_history_session_date ON matchup_history(session_date);
CREATE INDEX IF NOT EXISTS idx_matchup_history_map ON matchup_history(map_name);

-- Greatshot indexes
CREATE INDEX IF NOT EXISTS idx_greatshot_demos_user_created_at ON greatshot_demos(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_greatshot_demos_status ON greatshot_demos(status);
CREATE INDEX IF NOT EXISTS idx_greatshot_highlights_demo_id ON greatshot_highlights(demo_id);
CREATE INDEX IF NOT EXISTS idx_greatshot_renders_highlight ON greatshot_renders(highlight_id);


-- ============================================================================
-- 10. SEED DATA
-- ============================================================================

-- Default team pool
INSERT INTO team_pool (name, display_name, color, active) VALUES
    ('sWat', 'sWat', 3447003, TRUE),
    ('S*F', 'S*F', 15158332, TRUE),
    ('madDogz', 'madDogz', 15105570, TRUE),
    ('slomix', 'slomix', 10181046, TRUE),
    ('puran', 'puran', 3066993, TRUE),
    ('insAne', 'insAne', 15844367, TRUE),
    ('allbad', 'allbad', 9807270, TRUE)
ON CONFLICT (name) DO NOTHING;

-- Root user permission (bot owner)
INSERT INTO user_permissions (discord_id, username, tier, added_by, reason) VALUES
    (231165917604741121, 'seareal', 'root', 231165917604741121, 'System initialization - Bot owner')
ON CONFLICT (discord_id) DO NOTHING;


-- ============================================================================
-- NOTES
-- ============================================================================
--
-- Tables NOT managed by postgresql_database_manager.py rebuild:
--   - user_permissions, permission_audit_log (admin config, preserved on rebuild)
--   - team_pool (team config, preserved on rebuild)
--   - server_status_history, voice_members, voice_status_history, live_status (website)
--   - All proximity tables (separate proximity subsystem)
--
-- To apply this schema to a fresh database:
--   1. CREATE DATABASE etlegacy;
--   2. psql -d etlegacy -f tools/schema_postgresql.sql
--   3. Update .env with database credentials
--   4. Run: python postgresql_database_manager.py (option 1)
--
-- For production, use postgresql_database_manager.py which handles:
--   - Schema creation with IF NOT EXISTS
--   - Column migrations for existing databases
--   - Bulk import from local_stats/
--   - Validation and verification
