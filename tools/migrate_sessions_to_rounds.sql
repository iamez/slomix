-- ============================================================
-- PHASE 2 DATABASE MIGRATION: sessions → rounds
-- Date: November 4, 2025
-- Database: bot/etlegacy_production.db
-- ============================================================

-- STEP 1: Create new rounds table with CORRECT naming
-- ============================================================
CREATE TABLE rounds (
    id INTEGER PRIMARY KEY,
    round_date TEXT NOT NULL,  -- Was: session_date
    round_time TEXT NOT NULL,  -- Was: session_time
    match_id TEXT,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    
    -- Time tracking
    time_limit TEXT,
    actual_time TEXT,
    
    -- Outcomes
    winner_team INTEGER DEFAULT 0,
    defender_team INTEGER DEFAULT 0,
    is_tied INTEGER DEFAULT 0,
    round_outcome TEXT,
    
    -- Relationships
    gaming_session_id INTEGER,  -- ✅ Phase 1 addition
    map_id INTEGER,
    
    -- Stopwatch fields
    original_time_limit TEXT,
    time_to_beat TEXT,
    completion_time TEXT,
    
    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint
    UNIQUE(round_date, round_time, map_name, round_number)
);

-- STEP 2: Copy ALL data from sessions to rounds
-- ============================================================
INSERT INTO rounds (
    id, round_date, round_time, match_id, map_name, round_number,
    time_limit, actual_time, winner_team, defender_team, is_tied,
    round_outcome, gaming_session_id, map_id, original_time_limit,
    time_to_beat, completion_time, created_at
)
SELECT 
    id, session_date, session_time, match_id, map_name, round_number,
    time_limit, actual_time, winner_team, defender_team, is_tied,
    round_outcome, gaming_session_id, map_id, original_time_limit,
    time_to_beat, completion_time, created_at
FROM sessions;

-- STEP 3: Update player_comprehensive_stats table
-- ============================================================
-- SQLite doesn't support ALTER COLUMN, so we recreate the table

-- Create new table structure with round_id
CREATE TABLE player_comprehensive_stats_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,  -- Was: session_id
    round_date TEXT NOT NULL,   -- Was: session_date
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    clean_name TEXT NOT NULL,
    team INTEGER,
    
    -- Core combat stats
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    damage_given INTEGER DEFAULT 0,
    damage_received INTEGER DEFAULT 0,
    team_damage_given INTEGER DEFAULT 0,
    team_damage_received INTEGER DEFAULT 0,
    
    -- Special kills
    gibs INTEGER DEFAULT 0,
    self_kills INTEGER DEFAULT 0,
    team_kills INTEGER DEFAULT 0,
    team_gibs INTEGER DEFAULT 0,
    headshot_kills INTEGER DEFAULT 0,
    
    -- Time tracking
    time_played_seconds INTEGER DEFAULT 0,
    time_played_minutes REAL DEFAULT 0,
    time_dead_minutes REAL DEFAULT 0,
    time_dead_ratio REAL DEFAULT 0,
    
    -- Performance metrics
    xp INTEGER DEFAULT 0,
    kd_ratio REAL DEFAULT 0,
    dpm REAL DEFAULT 0,
    hsr REAL DEFAULT 0,
    
    -- Objectives
    obj_captured INTEGER DEFAULT 0,
    obj_destroyed INTEGER DEFAULT 0,
    obj_returned INTEGER DEFAULT 0,
    obj_taken INTEGER DEFAULT 0,
    
    -- Support actions
    revives INTEGER DEFAULT 0,
    ammogiven INTEGER DEFAULT 0,
    healthgiven INTEGER DEFAULT 0,
    
    -- Other stats
    efficiency REAL DEFAULT 0,
    num_rounds INTEGER DEFAULT 0,
    poisoned INTEGER DEFAULT 0,
    
    -- Accuracy
    total_accuracy REAL DEFAULT 0,
    
    -- Metadata
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    FOREIGN KEY (round_id) REFERENCES rounds(id),
    UNIQUE(round_id, player_guid)
);

-- Copy all player stats data
INSERT INTO player_comprehensive_stats_new
SELECT * FROM player_comprehensive_stats;

-- Drop old table
DROP TABLE player_comprehensive_stats;

-- Rename new table
ALTER TABLE player_comprehensive_stats_new RENAME TO player_comprehensive_stats;

-- STEP 4: Update weapon_comprehensive_stats table
-- ============================================================

-- Create new table structure with round_id
CREATE TABLE weapon_comprehensive_stats_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,  -- Was: session_id
    round_date TEXT NOT NULL,   -- Was: session_date
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    weapon_name TEXT NOT NULL,
    
    -- Weapon stats
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    headshots INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    
    -- Metadata
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    FOREIGN KEY (round_id) REFERENCES rounds(id),
    UNIQUE(round_id, player_guid, weapon_name)
);

-- Copy all weapon stats data
INSERT INTO weapon_comprehensive_stats_new
SELECT * FROM weapon_comprehensive_stats;

-- Drop old table
DROP TABLE weapon_comprehensive_stats;

-- Rename new table
ALTER TABLE weapon_comprehensive_stats_new RENAME TO weapon_comprehensive_stats;

-- STEP 5: Drop old sessions table
-- ============================================================
DROP TABLE sessions;

-- STEP 6: Recreate all indexes with CORRECT names
-- ============================================================

-- Rounds table indexes
CREATE INDEX idx_rounds_date ON rounds(round_date);
CREATE INDEX idx_rounds_match_id ON rounds(match_id);
CREATE INDEX idx_rounds_gaming_session_id ON rounds(gaming_session_id);
CREATE INDEX idx_rounds_date_time ON rounds(round_date, round_time);

-- Player stats indexes
CREATE INDEX idx_player_stats_round ON player_comprehensive_stats(round_id);
CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid);
CREATE INDEX idx_player_stats_clean_name ON player_comprehensive_stats(clean_name);
CREATE INDEX idx_players_dpm ON player_comprehensive_stats(dpm DESC);
CREATE INDEX idx_players_kd ON player_comprehensive_stats(kd_ratio DESC);

-- Weapon stats indexes
CREATE INDEX idx_weapon_stats_round ON weapon_comprehensive_stats(round_id);
CREATE INDEX idx_weapons_player ON weapon_comprehensive_stats(player_guid);
