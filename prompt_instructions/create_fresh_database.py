#!/usr/bin/env python3
"""
Create Fresh Production Database with Seconds-Based Schema
Initializes etlegacy_production.db with correct schema including time_played_seconds
"""

import sqlite3
import os
from datetime import datetime

def create_fresh_database():
    """Create production database with seconds-based time storage"""
    
    db_path = "etlegacy_production.db"
    
    # Verify the database doesn't exist
    if os.path.exists(db_path):
        print(f"Database already exists at {db_path}. Deleting it.")
        os.remove(db_path)
    
    print(f"\n🏗️ Creating fresh database: {db_path}")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Sessions table
    print("📋 Creating sessions table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date DATE NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            server_name TEXT,
            config_name TEXT,
            defender_team INTEGER,
            winner_team INTEGER,
            time_limit TEXT,
            next_time_limit TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Comprehensive player stats WITH time_played_seconds from the start!
    print("🎮 Creating player_comprehensive_stats table (WITH SECONDS)...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            player_guid TEXT NOT NULL,
            player_name TEXT NOT NULL,
            clean_name TEXT NOT NULL,
            team INTEGER NOT NULL,
            rounds INTEGER DEFAULT 0,
            
            -- Basic combat stats
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
            
            -- Time and XP (SECONDS-BASED!)
            time_axis INTEGER DEFAULT 0,
            time_allies INTEGER DEFAULT 0,
            time_played_seconds INTEGER DEFAULT 0,         -- PRIMARY TIME FIELD (SECONDS)
            time_played_minutes REAL DEFAULT 0.0,          -- DEPRECATED (backward compatibility)
            time_display TEXT DEFAULT '0:00',              -- MM:SS format for display
            xp INTEGER DEFAULT 0,
            
            -- Advanced analytics from topshots/objective_stats
            killing_spree_best INTEGER DEFAULT 0,
            death_spree_worst INTEGER DEFAULT 0,
            kill_assists INTEGER DEFAULT 0,
            kill_steals INTEGER DEFAULT 0,
            headshot_kills INTEGER DEFAULT 0,
            objectives_stolen INTEGER DEFAULT 0,
            objectives_returned INTEGER DEFAULT 0,
            dynamites_planted INTEGER DEFAULT 0,
            dynamites_defused INTEGER DEFAULT 0,
            times_revived INTEGER DEFAULT 0,
            bullets_fired INTEGER DEFAULT 0,
            dpm REAL DEFAULT 0.0,                          -- Calculated as (damage * 60) / time_played_seconds
            tank_meatshield REAL DEFAULT 0.0,
            time_dead_ratio REAL DEFAULT 0.0,
            most_useful_kills INTEGER DEFAULT 0,
            denied_playtime INTEGER DEFAULT 0,
            useless_kills INTEGER DEFAULT 0,
            full_selfkills INTEGER DEFAULT 0,
            repairs_constructions INTEGER DEFAULT 0,
            
            -- Multikills
            double_kills INTEGER DEFAULT 0,
            triple_kills INTEGER DEFAULT 0,
            quad_kills INTEGER DEFAULT 0,
            multi_kills INTEGER DEFAULT 0,
            mega_kills INTEGER DEFAULT 0,
            
            -- Calculated fields
            kd_ratio REAL DEFAULT 0.0,
            accuracy REAL DEFAULT 0.0,
            headshot_ratio REAL DEFAULT 0.0,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    
    # Weapon stats
    print("🔫 Creating weapon_comprehensive_stats table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weapon_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            player_guid TEXT NOT NULL,
            weapon_id INTEGER NOT NULL,
            weapon_name TEXT NOT NULL,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            hits INTEGER DEFAULT 0,
            shots INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0,
            headshot_ratio REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    
    # Player links for Discord
    print("🔗 Creating player_links table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_guid TEXT UNIQUE NOT NULL,
            discord_id TEXT UNIQUE NOT NULL,
            discord_username TEXT,
            player_name TEXT,
            linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create useful indexes
    print("⚡ Creating indexes...")
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_player_guid 
        ON player_comprehensive_stats(player_guid)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_session_date 
        ON player_comprehensive_stats(session_date)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_player_session 
        ON player_comprehensive_stats(player_guid, session_date)
    ''')
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ Database created successfully!")
    print("\n📊 Schema Details:")
    print("   ✅ time_played_seconds INTEGER (PRIMARY)")
    print("   ✅ time_display TEXT (MM:SS format)")
    print("   ✅ time_played_minutes REAL (DEPRECATED)")
    print("   ✅ DPM formula: (damage * 60) / time_played_seconds")
    print("\n🚀 Ready for bulk import!")
    print("=" * 60 + "\n")
    
    return True

if __name__ == "__main__":
    success = create_fresh_database()
    if success:
        print("✅ Next step: Run bulk import with seconds-based parser!")
    else:
        print("❌ Database creation failed!")
