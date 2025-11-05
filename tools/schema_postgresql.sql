-- PostgreSQL Schema for ET:Legacy Discord Bot
-- Converted from SQLite schema
-- Date: 2025-11-05
-- 
-- Key Conversions:
-- - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
-- - TEXT → VARCHAR(n) or TEXT (kept TEXT for flexibility)
-- - BIGINT → BIGINT (no change)
-- - BOOLEAN → BOOLEAN (no change)
-- - TIMESTAMP DEFAULT CURRENT_TIMESTAMP → TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- - UNIQUE constraints preserved
-- - FOREIGN KEY constraints preserved
-- - Added ON DELETE CASCADE where appropriate

-- ============================================================================
-- TABLE: rounds
-- Main rounds/matches table
-- ============================================================================
CREATE TABLE IF NOT EXISTS rounds (
    id SERIAL PRIMARY KEY,
    round_date TEXT NOT NULL,
    round_time TEXT NOT NULL,
    match_id TEXT NOT NULL,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    time_limit TEXT,
    actual_time TEXT,
    winner_team INTEGER DEFAULT 0,
    defender_team INTEGER DEFAULT 0,
    is_tied BOOLEAN DEFAULT FALSE,
    round_outcome TEXT,
    gaming_session_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, round_number)
);

-- ============================================================================
-- TABLE: player_comprehensive_stats
-- Main player statistics table (54 columns)
-- ============================================================================
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
    
    -- Core combat stats
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    damage_given INTEGER DEFAULT 0,
    damage_received INTEGER DEFAULT 0,
    team_damage_given INTEGER DEFAULT 0,
    team_damage_received INTEGER DEFAULT 0,
    gibs INTEGER DEFAULT 0,
    self_kills INTEGER DEFAULT 0,
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
    xp INTEGER DEFAULT 0,
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
    tank_meatshield REAL DEFAULT 0,
    
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
    
    -- Constraints
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    UNIQUE(round_id, player_guid)
);

-- ============================================================================
-- TABLE: weapon_comprehensive_stats
-- Weapon-specific statistics per player per round
-- ============================================================================
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
    
    -- Constraints
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
    UNIQUE(round_id, player_guid, weapon_name)
);

-- ============================================================================
-- TABLE: player_aliases
-- Player name/alias tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS player_aliases (
    id SERIAL PRIMARY KEY,
    guid TEXT NOT NULL,
    alias TEXT NOT NULL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    times_seen INTEGER DEFAULT 1,
    UNIQUE(guid, alias)
);

-- ============================================================================
-- TABLE: player_links
-- Discord account to ET:Legacy GUID linking
-- ============================================================================
CREATE TABLE IF NOT EXISTS player_links (
    discord_id BIGINT PRIMARY KEY,
    discord_username TEXT NOT NULL,
    et_guid TEXT UNIQUE NOT NULL,
    et_name TEXT,
    linked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified BOOLEAN DEFAULT FALSE
);

-- ============================================================================
-- TABLE: session_teams
-- Team compositions for gaming sessions
-- ============================================================================
CREATE TABLE IF NOT EXISTS session_teams (
    id SERIAL PRIMARY KEY,
    session_start_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    team_name TEXT NOT NULL,
    player_guids TEXT NOT NULL,
    player_names TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_start_date, map_name, team_name)
);

-- ============================================================================
-- TABLE: processed_files
-- Track which endstats files have been imported
-- ============================================================================
CREATE TABLE IF NOT EXISTS processed_files (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    file_hash TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES for Performance
-- ============================================================================

-- Player stats indexes
CREATE INDEX IF NOT EXISTS idx_player_stats_guid ON player_comprehensive_stats(player_guid);
CREATE INDEX IF NOT EXISTS idx_player_stats_round ON player_comprehensive_stats(round_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_date ON player_comprehensive_stats(round_date);
CREATE INDEX IF NOT EXISTS idx_player_stats_map ON player_comprehensive_stats(map_name);

-- Weapon stats indexes
CREATE INDEX IF NOT EXISTS idx_weapon_stats_guid ON weapon_comprehensive_stats(player_guid);
CREATE INDEX IF NOT EXISTS idx_weapon_stats_round ON weapon_comprehensive_stats(round_id);

-- Rounds indexes
CREATE INDEX IF NOT EXISTS idx_rounds_date_map ON rounds(round_date, map_name);
CREATE INDEX IF NOT EXISTS idx_rounds_match_id ON rounds(match_id);
CREATE INDEX IF NOT EXISTS idx_rounds_date ON rounds(round_date);

-- Aliases indexes
CREATE INDEX IF NOT EXISTS idx_aliases_guid ON player_aliases(guid);
CREATE INDEX IF NOT EXISTS idx_aliases_last_seen ON player_aliases(last_seen);

-- Links indexes
CREATE INDEX IF NOT EXISTS idx_links_et_guid ON player_links(et_guid);

-- ============================================================================
-- VIEWS for Compatibility (Optional)
-- ============================================================================

-- View to mimic SQLite's autoincrement behavior tracking
-- Not strictly necessary in PostgreSQL but kept for reference
COMMENT ON TABLE rounds IS 'Main rounds/matches table with full game metadata';
COMMENT ON TABLE player_comprehensive_stats IS 'Comprehensive player statistics (54 columns) - main stats table';
COMMENT ON TABLE weapon_comprehensive_stats IS 'Per-weapon statistics for each player per round';
COMMENT ON TABLE player_aliases IS 'Player name/GUID tracking with frequency';
COMMENT ON TABLE player_links IS 'Discord to ET:Legacy account linking';
COMMENT ON TABLE session_teams IS 'Team compositions for gaming sessions';
COMMENT ON TABLE processed_files IS 'Track imported endstats files to prevent duplicates';

-- ============================================================================
-- NOTES
-- ============================================================================
-- 
-- Migration Checklist:
-- 1. Create database: CREATE DATABASE etlegacy;
-- 2. Run this schema: psql -d etlegacy -f schema_postgresql.sql
-- 3. Update bot config: database_type=postgresql
-- 4. Test connection: bot should connect and validate schema
-- 5. Run migration script to copy data from SQLite
-- 
-- Key Differences from SQLite:
-- - SERIAL instead of AUTOINCREMENT (auto-managed sequences)
-- - Better index support and query optimization
-- - REAL → DOUBLE PRECISION (but REAL still works)
-- - Better concurrent access handling
-- - VACUUM not needed (autovacuum handles it)
-- 
-- Compatibility Notes:
-- - All queries using ? placeholders must use $1, $2, etc. in PostgreSQL
-- - This is handled by the DatabaseAdapter in bot/core/database_adapter.py
-- - datetime('now') → CURRENT_TIMESTAMP (handled by adapter)
-- - date('now', '-30 days') → CURRENT_DATE - INTERVAL '30 days' (handled by adapter)
