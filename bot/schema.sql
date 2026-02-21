-- Schema export (no data)
-- Tables must be created before indexes

-- table sessions (referenced by other tables)
CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            defender_team INTEGER DEFAULT 0,
            winner_team INTEGER DEFAULT 0,
            time_limit TEXT,
            actual_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

-- table player_aliases
CREATE TABLE player_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT NOT NULL,
            alias TEXT NOT NULL,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            times_seen INTEGER DEFAULT 1,
            UNIQUE(guid, alias)
        );

-- table player_comprehensive_stats
CREATE TABLE player_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
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
            full_selfkills INTEGER DEFAULT 0,
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
            efficiency REAL DEFAULT 0,

            -- Weapon stats
            bullets_fired INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0,

            -- Objective stats (IN THIS TABLE - UNIFIED!)
            kill_assists INTEGER DEFAULT 0,
            objectives_completed INTEGER DEFAULT 0,
            objectives_destroyed INTEGER DEFAULT 0,
            objectives_stolen INTEGER DEFAULT 0,
            objectives_returned INTEGER DEFAULT 0,
            dynamites_planted INTEGER DEFAULT 0,
            dynamites_defused INTEGER DEFAULT 0,
            times_revived INTEGER DEFAULT 0,
            revives_given INTEGER DEFAULT 0,

            -- Advanced objective stats (IN THIS TABLE - UNIFIED!)
            most_useful_kills INTEGER DEFAULT 0,
            useless_kills INTEGER DEFAULT 0,
            kill_steals INTEGER DEFAULT 0,
            denied_playtime INTEGER DEFAULT 0,
            constructions INTEGER DEFAULT 0,
            tank_meatshield REAL DEFAULT 0,

            -- Multikills (IN THIS TABLE - UNIFIED!)
            double_kills INTEGER DEFAULT 0,
            triple_kills INTEGER DEFAULT 0,
            quad_kills INTEGER DEFAULT 0,
            multi_kills INTEGER DEFAULT 0,
            mega_kills INTEGER DEFAULT 0,

            -- Sprees (IN THIS TABLE - UNIFIED!)
            killing_spree_best INTEGER DEFAULT 0,
            death_spree_worst INTEGER DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

-- table player_links
CREATE TABLE player_links (
            discord_id BIGINT PRIMARY KEY,
            discord_username TEXT NOT NULL,
            et_guid TEXT UNIQUE NOT NULL,
            et_name TEXT,
            linked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified BOOLEAN DEFAULT FALSE
        );

-- table processed_files
CREATE TABLE processed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            file_hash TEXT,
            success BOOLEAN DEFAULT 1,
            error_message TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

-- table session_teams
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

-- table weapon_comprehensive_stats
CREATE TABLE weapon_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
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
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

-- ============================================================
-- INDEXES (created after tables exist)
-- ============================================================

-- Indexes for player_aliases
CREATE INDEX idx_aliases_alias ON player_aliases(alias);
CREATE INDEX idx_aliases_guid ON player_aliases(guid);

-- Indexes for player_comprehensive_stats
CREATE INDEX idx_player_stats_clean_name ON player_comprehensive_stats(clean_name);
CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid);
CREATE INDEX idx_player_stats_session ON player_comprehensive_stats(session_id);
CREATE INDEX idx_players_dpm ON player_comprehensive_stats(dpm DESC);
CREATE INDEX idx_players_kd ON player_comprehensive_stats(kd_ratio DESC);

-- Indexes for session_teams
CREATE INDEX idx_session_teams_date ON session_teams(session_start_date);
CREATE INDEX idx_session_teams_map ON session_teams(map_name);

-- Indexes for sessions
CREATE INDEX idx_sessions_date ON sessions(session_date);

-- Indexes for weapon_comprehensive_stats
CREATE INDEX idx_weapon_stats_session ON weapon_comprehensive_stats(session_id);
CREATE INDEX idx_weapons_player ON weapon_comprehensive_stats(player_guid);
