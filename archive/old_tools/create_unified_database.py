#!/usr/bin/env python3
"""
Create database with UNIFIED schema (all fields in player_comprehensive_stats)
This matches what the Discord bot expects!
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = "etlegacy_production.db"


def backup_current_database():
    """Backup current database if it exists"""
    if os.path.exists(DB_PATH):
        backup_name = f"etlegacy_production_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        print(f"📦 Backing up current database to: {backup_name}")
        import shutil
        shutil.copy2(DB_PATH, backup_name)
        print(f"✅ Backup created")
        return backup_name
    return None


def create_unified_schema():
    """Create database with UNIFIED schema - all fields in player_comprehensive_stats"""
    
    print("\n🏗️  Creating database with UNIFIED schema...")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            defender_team INTEGER DEFAULT 0,
            winner_team INTEGER DEFAULT 0,
            time_limit TEXT,
            actual_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Created sessions table")
    
    # Create player_comprehensive_stats with ALL FIELDS (unified schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
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
        )
    ''')
    print("✅ Created player_comprehensive_stats table (UNIFIED - ALL FIELDS)")
    
    # Create weapon_comprehensive_stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weapon_comprehensive_stats (
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
        )
    ''')
    print("✅ Created weapon_comprehensive_stats table")
    
    # Create player_links table (Discord linking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_links (
            discord_id BIGINT PRIMARY KEY,
            discord_username TEXT NOT NULL,
            et_guid TEXT UNIQUE NOT NULL,
            et_name TEXT,
            linked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified BOOLEAN DEFAULT FALSE
        )
    ''')
    print("✅ Created player_links table")
    
    # Create processed_files table (for import tracking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            file_hash TEXT,
            success BOOLEAN DEFAULT 1,
            error_message TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Created processed_files table")
    
    # Create session_teams table (for team tracking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_start_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            team_name TEXT NOT NULL,
            player_guids TEXT NOT NULL,
            player_names TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_start_date, map_name, team_name)
        )
    ''')
    print("✅ Created session_teams table")
    
    # Create player_aliases table (for name tracking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT NOT NULL,
            alias TEXT NOT NULL,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            times_seen INTEGER DEFAULT 1,
            UNIQUE(guid, alias)
        )
    ''')
    print("✅ Created player_aliases table")
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_session ON player_comprehensive_stats(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_guid ON player_comprehensive_stats(player_guid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_clean_name ON player_comprehensive_stats(clean_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(session_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_weapon_stats_session ON weapon_comprehensive_stats(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_teams_date ON session_teams(session_start_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_teams_map ON session_teams(map_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player_aliases_guid ON player_aliases(guid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player_aliases_alias ON player_aliases(alias)')
    print("✅ Created performance indexes")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ DATABASE CREATED WITH UNIFIED SCHEMA")
    print("=" * 80)
    print("\n📋 Schema Summary:")
    print("  • sessions: Session metadata (with defender_team, winner_team)")
    print("  • player_comprehensive_stats: ALL player stats in ONE table (53 columns)")
    print("  • weapon_comprehensive_stats: Weapon-specific stats")
    print("  • player_links: Discord account linking")
    print("  • processed_files: Import tracking (duplicate prevention)")
    print("  • session_teams: Team roster tracking")
    print("  • player_aliases: Player name tracking")
    print("\n🎯 This schema matches what the Discord bot expects!")
    print("\nNext step: Run import with simple_bulk_import.py")


def main():
    print("\n" + "=" * 80)
    print("🎮 ET:Legacy Database Creator - UNIFIED SCHEMA")
    print("=" * 80)
    
    # Check if database exists
    if os.path.exists(DB_PATH):
        print(f"\n⚠️  Database '{DB_PATH}' already exists!")
        response = input("Do you want to:\n  1. Backup and recreate\n  2. Cancel\nChoice (1/2): ")
        
        if response == "1":
            backup_current_database()
            print(f"\n🗑️  Deleting old database...")
            os.remove(DB_PATH)
            print("✅ Old database deleted")
        else:
            print("❌ Cancelled")
            return
    
    # Create new unified schema
    create_unified_schema()
    
    print("\n" + "=" * 80)
    print("🎉 READY TO IMPORT!")
    print("=" * 80)
    print("\nRun this command to import all stats:")
    print("  python tools/simple_bulk_import.py local_stats/*.txt")
    print("\nOr import specific year:")
    print("  python tools/simple_bulk_import.py local_stats/2025-*.txt")


if __name__ == "__main__":
    main()
