#!/usr/bin/env python3
"""
Production Database Creator
============================
Purpose: Create fresh etlegacy_production.db with comprehensive schema

CRITICAL: Each round (Round 1 and Round 2) is stored as SEPARATE session!

Schema includes:
- sessions: Match/round metadata (each round = 1 session)
- player_comprehensive_stats: All player stats per session  
- weapon_comprehensive_stats: Per-weapon stats per session
- player_links: Discord ↔ GUID mapping
- processed_files: Import tracking

Created: October 3, 2025
Location: /dev folder (as per ground rules)
"""

import sqlite3
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DatabaseCreator')


def create_production_database():
    """Create the production database with comprehensive schema"""
    
    db_path = "etlegacy_production.db"
    
    # Remove existing database if it exists
    if os.path.exists(db_path):
        backup_name = f"etlegacy_production_backup_{os.path.getmtime(db_path):.0f}.db"
        os.rename(db_path, backup_name)
        logger.info(f"📦 Backed up existing database to: {backup_name}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    logger.info("🏗️  Creating production database schema...")
    
    # =====================================================================
    # SESSIONS TABLE
    # Each round is a SEPARATE session (Round 1 and Round 2 are separate)
    # =====================================================================
    cursor.execute('''
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date DATE NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            time_limit TEXT,
            actual_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    logger.info("✅ Created table: sessions")
    
    # =====================================================================
    # PLAYER COMPREHENSIVE STATS TABLE
    # All player statistics for each session/round
    # =====================================================================
    cursor.execute('''
        CREATE TABLE player_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_guid TEXT NOT NULL,
            player_name TEXT NOT NULL,
            clean_name TEXT NOT NULL,
            team INTEGER NOT NULL,
            
            -- Basic combat stats
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            damage_given INTEGER DEFAULT 0,
            damage_received INTEGER DEFAULT 0,
            
            -- Advanced stats
            headshot_kills INTEGER DEFAULT 0,
            kd_ratio REAL DEFAULT 0.0,
            dpm REAL DEFAULT 0.0,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    logger.info("✅ Created table: player_comprehensive_stats")
    
    # =====================================================================
    # WEAPON COMPREHENSIVE STATS TABLE
    # Per-weapon statistics for each player/session
    # =====================================================================
    cursor.execute('''
        CREATE TABLE weapon_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_guid TEXT NOT NULL,
            weapon_id INTEGER,
            weapon_name TEXT NOT NULL,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            hits INTEGER DEFAULT 0,
            shots INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    logger.info("✅ Created table: weapon_comprehensive_stats")
    
    # =====================================================================
    # PLAYER LINKS TABLE
    # Discord user ↔ In-game GUID mapping
    # =====================================================================
    cursor.execute('''
        CREATE TABLE player_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_guid TEXT UNIQUE NOT NULL,
            discord_id TEXT UNIQUE NOT NULL,
            discord_username TEXT,
            player_name TEXT,
            linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    logger.info("✅ Created table: player_links")
    
    # =====================================================================
    # PROCESSED FILES TABLE
    # Track which stat files have been imported
    # =====================================================================
    cursor.execute('''
        CREATE TABLE processed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER,
            player_count INTEGER,
            success INTEGER DEFAULT 1
        )
    ''')
    logger.info("✅ Created table: processed_files")
    
    # =====================================================================
    # INDEXES for performance
    # =====================================================================
    cursor.execute('''
        CREATE INDEX idx_sessions_date_map 
        ON sessions(session_date, map_name)
    ''')
    
    cursor.execute('''
        CREATE INDEX idx_player_stats_session 
        ON player_comprehensive_stats(session_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX idx_player_stats_guid 
        ON player_comprehensive_stats(player_guid)
    ''')
    
    cursor.execute('''
        CREATE INDEX idx_weapon_stats_session 
        ON weapon_comprehensive_stats(session_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX idx_weapon_stats_guid 
        ON weapon_comprehensive_stats(player_guid)
    ''')
    
    logger.info("✅ Created performance indexes")
    
    # Commit and close
    conn.commit()
    conn.close()
    
    logger.info(f"\n🎉 Database created successfully: {db_path}")
    logger.info(f"   Size: {os.path.getsize(db_path) / 1024:.2f} KB")
    logger.info("\n📝 Schema Summary:")
    logger.info("   • sessions - Round metadata (each round separate)")
    logger.info("   • player_comprehensive_stats - Player stats per round")
    logger.info("   • weapon_comprehensive_stats - Weapon stats per round")
    logger.info("   • player_links - Discord user linking")
    logger.info("   • processed_files - Import tracking")
    logger.info("\n✅ Ready for bulk import!")


if __name__ == "__main__":
    create_production_database()
