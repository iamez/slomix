-- SQLite Schema Export
-- Exported from: bot/etlegacy_production.db
-- Date: 2025-11-05

CREATE INDEX idx_aliases_guid ON player_aliases(guid);

CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid);

CREATE INDEX idx_player_stats_round ON player_comprehensive_stats(round_id);

CREATE INDEX idx_rounds_date_map ON rounds(round_date, map_name);

CREATE INDEX idx_rounds_match_id ON rounds(match_id);

CREATE INDEX idx_weapon_stats_guid ON weapon_comprehensive_stats(player_guid);

CREATE INDEX idx_weapon_stats_round ON weapon_comprehensive_stats(round_id);

CREATE TABLE player_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guid TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    times_seen INTEGER DEFAULT 1,
                    UNIQUE(guid, alias)
                );

CREATE TABLE player_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    FOREIGN KEY (round_id) REFERENCES rounds(id),
                    
                    -- ✅ DUPLICATE PREVENTION
                    UNIQUE(round_id, player_guid)
                );

CREATE TABLE player_links (
                    discord_id BIGINT PRIMARY KEY,
                    discord_username TEXT NOT NULL,
                    et_guid TEXT UNIQUE NOT NULL,
                    et_name TEXT,
                    linked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified BOOLEAN DEFAULT FALSE
                );

CREATE TABLE processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    file_hash TEXT,
                    success BOOLEAN DEFAULT 1,
                    error_message TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

CREATE TABLE rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

CREATE TABLE session_teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_start_date TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    player_guids TEXT NOT NULL,
                    player_names TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_start_date, map_name, team_name)
                );

CREATE TABLE sqlite_sequence(name,seq);

CREATE TABLE weapon_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    FOREIGN KEY (round_id) REFERENCES rounds(id),
                    
                    -- ✅ DUPLICATE PREVENTION
                    UNIQUE(round_id, player_guid, weapon_name)
                );

