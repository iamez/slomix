#!/usr/bin/env python3
"""
Clean Database Creator - No Emoji Version
Creates etlegacy_production.db with the exact schema that works with bulk_import_stats.py
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

def create_database():
    """Create fresh production database"""
    
    db_path = "etlegacy_production.db"
    
    # Remove old database if exists
    if os.path.exists(db_path):
        backup_name = f"etlegacy_production_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        os.rename(db_path, backup_name)
        print(f"[BACKUP] Moved existing database to: {backup_name}")
    
    print(f"\n[CREATE] Creating fresh database: {db_path}")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # =====================================================================
    # SESSIONS TABLE - NO UNIQUE CONSTRAINT (allows duplicate maps)
    # =====================================================================
    print("\n[TABLE] Creating sessions table...")
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
    print("  [OK] sessions table created")
    
    # =====================================================================
    # PLAYER COMPREHENSIVE STATS TABLE
    # =====================================================================
    print("\n[TABLE] Creating player_comprehensive_stats table...")
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
            team_damage_given INTEGER DEFAULT 0,
            team_damage_received INTEGER DEFAULT 0,
            gibs INTEGER DEFAULT 0,
            self_kills INTEGER DEFAULT 0,
            team_kills INTEGER DEFAULT 0,
            team_gibs INTEGER DEFAULT 0,
            
            -- Time and XP
            time_axis INTEGER DEFAULT 0,
            time_allies INTEGER DEFAULT 0,
            time_played_seconds INTEGER DEFAULT 0,
            time_played_minutes REAL DEFAULT 0.0,
            xp INTEGER DEFAULT 0,
            
            -- Advanced stats
            killing_spree_best INTEGER DEFAULT 0,
            death_spree_worst INTEGER DEFAULT 0,
            kill_assists INTEGER DEFAULT 0,
            headshot_kills INTEGER DEFAULT 0,
            revives INTEGER DEFAULT 0,
            ammopacks INTEGER DEFAULT 0,
            healthpacks INTEGER DEFAULT 0,
            dpm REAL DEFAULT 0.0,
            kd_ratio REAL DEFAULT 0.0,
            efficiency REAL DEFAULT 0.0,
            
            -- Awards (top 3 rankings)
            award_accuracy INTEGER DEFAULT 0,
            award_damage INTEGER DEFAULT 0,
            award_kills INTEGER DEFAULT 0,
            award_experience INTEGER DEFAULT 0,
            
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    ''')
    print("  [OK] player_comprehensive_stats table created")
    
    # =====================================================================
    # WEAPON COMPREHENSIVE STATS TABLE
    # =====================================================================
    print("\n[TABLE] Creating weapon_comprehensive_stats table...")
    cursor.execute('''
        CREATE TABLE weapon_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_guid TEXT NOT NULL,
            weapon_name TEXT NOT NULL,
            
            hits INTEGER DEFAULT 0,
            shots INTEGER DEFAULT 0,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            
            accuracy REAL DEFAULT 0.0,
            
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    ''')
    print("  [OK] weapon_comprehensive_stats table created")
    
    # =====================================================================
    # PLAYER OBJECTIVE STATS TABLE (25 objective/support fields)
    # =====================================================================
    print("\n[TABLE] Creating player_objective_stats table...")
    cursor.execute('''
        CREATE TABLE player_objective_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_guid TEXT NOT NULL,
            
            -- Objective actions
            objectives_completed INTEGER DEFAULT 0,
            objectives_destroyed INTEGER DEFAULT 0,
            objectives_captured INTEGER DEFAULT 0,
            objectives_defended INTEGER DEFAULT 0,
            objectives_stolen INTEGER DEFAULT 0,
            objectives_returned INTEGER DEFAULT 0,
            
            -- Explosives
            dynamites_planted INTEGER DEFAULT 0,
            dynamites_defused INTEGER DEFAULT 0,
            landmines_planted INTEGER DEFAULT 0,
            landmines_spotted INTEGER DEFAULT 0,
            
            -- Support actions
            revives INTEGER DEFAULT 0,
            ammopacks INTEGER DEFAULT 0,
            healthpacks INTEGER DEFAULT 0,
            
            -- Combat support
            times_revived INTEGER DEFAULT 0,
            kill_assists INTEGER DEFAULT 0,
            
            -- Engineering
            constructions_built INTEGER DEFAULT 0,
            constructions_destroyed INTEGER DEFAULT 0,
            
            -- Advanced stats
            killing_spree_best INTEGER DEFAULT 0,
            death_spree_worst INTEGER DEFAULT 0,
            kill_steals INTEGER DEFAULT 0,
            most_useful_kills INTEGER DEFAULT 0,
            useless_kills INTEGER DEFAULT 0,
            denied_playtime INTEGER DEFAULT 0,
            tank_meatshield REAL DEFAULT 0.0,
            
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    ''')
    print("  [OK] player_objective_stats table created (25 fields)")
    
    # =====================================================================
    # PLAYER LINKS TABLE (Discord <-> GUID mapping)
    # =====================================================================
    print("\n[TABLE] Creating player_links table...")
    cursor.execute('''
        CREATE TABLE player_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT NOT NULL UNIQUE,
            player_guid TEXT NOT NULL,
            player_name TEXT,
            linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("  [OK] player_links table created")
    
    # =====================================================================
    # PROCESSED FILES TABLE (import tracking)
    # =====================================================================
    print("\n[TABLE] Creating processed_files table...")
    cursor.execute('''
        CREATE TABLE processed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER,
            player_count INTEGER,
            success INTEGER DEFAULT 1
        )
    ''')
    print("  [OK] processed_files table created")
    
    # =====================================================================
    # CREATE INDEXES for performance
    # =====================================================================
    print("\n[INDEX] Creating performance indexes...")
    cursor.execute('CREATE INDEX idx_player_stats_session ON player_comprehensive_stats(session_id)')
    cursor.execute('CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid)')
    cursor.execute('CREATE INDEX idx_weapon_stats_session ON weapon_comprehensive_stats(session_id)')
    cursor.execute('CREATE INDEX idx_weapon_stats_guid ON weapon_comprehensive_stats(player_guid)')
    cursor.execute('CREATE INDEX idx_objective_stats_session ON player_objective_stats(session_id)')
    cursor.execute('CREATE INDEX idx_objective_stats_guid ON player_objective_stats(player_guid)')
    cursor.execute('CREATE INDEX idx_sessions_date ON sessions(session_date)')
    cursor.execute('CREATE INDEX idx_sessions_map ON sessions(map_name)')
    print("  [OK] All indexes created")
    
    # =====================================================================
    # COMMIT AND CLOSE
    # =====================================================================
    conn.commit()
    conn.close()
    
    # Verify database was created
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"\n[SUCCESS] Database created successfully!")
        print(f"  File: {db_path}")
        print(f"  Size: {size:,} bytes")
        print(f"\n[READY] Ready for bulk import!")
        print(f"  Run: python dev/bulk_import_stats.py --year 2025")
        return True
    else:
        print(f"\n[ERROR] Database creation failed!")
        return False


if __name__ == '__main__':
    try:
        success = create_database()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Exception during database creation: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
