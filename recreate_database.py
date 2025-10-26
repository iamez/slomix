#!/usr/bin/env python3
"""
Recreate the database from scratch and import all stats files.
Run this AFTER manually deleting etlegacy_production.db
"""

import os
import sqlite3

DB_PATH = "etlegacy_production.db"


def create_database_schema():
    """Create all tables with proper schema"""
    print("Creating database schema...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create sessions table (matches import script)
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            time_limit TEXT,
            actual_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''
    )

    # Create player_comprehensive_stats table (matches import script columns)
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            player_guid TEXT,
            player_name TEXT NOT NULL,
            clean_name TEXT,
            team INTEGER,
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
            time_played_seconds INTEGER DEFAULT 0,
            time_played_minutes REAL DEFAULT 0.0,
            time_display TEXT,
            xp INTEGER DEFAULT 0,
            dpm REAL DEFAULT 0.0,
            kd_ratio REAL DEFAULT 0.0,
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
            revives_given INTEGER DEFAULT 0,
            bullets_fired INTEGER DEFAULT 0,
            tank_meatshield INTEGER DEFAULT 0,
            time_dead_ratio REAL DEFAULT 0.0,
            most_useful_kills INTEGER DEFAULT 0,
            denied_playtime INTEGER DEFAULT 0,
            useless_kills INTEGER DEFAULT 0,
            full_selfkills INTEGER DEFAULT 0,
            repairs_constructions INTEGER DEFAULT 0,
            double_kills INTEGER DEFAULT 0,
            triple_kills INTEGER DEFAULT 0,
            quad_kills INTEGER DEFAULT 0,
            multi_kills INTEGER DEFAULT 0,
            mega_kills INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    '''
    )

    # Create weapon_comprehensive_stats table
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS weapon_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            player_guid TEXT,
            player_name TEXT NOT NULL,
            weapon_name TEXT NOT NULL,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            hits INTEGER DEFAULT 0,
            shots INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0,
            damage_given INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    '''
    )

    # Create player_links table (for Discord linking)
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS player_links (
            player_guid TEXT PRIMARY KEY,
            player_name TEXT NOT NULL,
            discord_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''
    )

    # Create indices for better query performance
    cursor.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_sessions_date
        ON sessions(session_date)
    '''
    )

    cursor.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_player_stats_session
        ON player_comprehensive_stats(session_id)
    '''
    )

    cursor.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_player_stats_name
        ON player_comprehensive_stats(player_name)
    '''
    )

    cursor.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_weapon_stats_session
        ON weapon_comprehensive_stats(session_id)
    '''
    )

    cursor.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_weapon_stats_player
        ON weapon_comprehensive_stats(player_name)
    '''
    )

    conn.commit()
    conn.close()

    print("✅ Database schema created successfully!")


def main():
    """Main execution"""
    if os.path.exists(DB_PATH):
        print(f"❌ ERROR: {DB_PATH} already exists!")
        print(f"Please delete it manually first:")
        print(f"   del {DB_PATH}")
        return

    print(f"Creating fresh database: {DB_PATH}")
    create_database_schema()

    print("\n" + "=" * 60)
    print("✅ DATABASE CREATED SUCCESSFULLY!")
    print("=" * 60)
    print("\nNext step: Import all stats files")
    print("Run: python tools/simple_bulk_import.py local_stats")


if __name__ == "__main__":
    main()
