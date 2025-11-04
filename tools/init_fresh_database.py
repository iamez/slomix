#!/usr/bin/env python3
"""
Initialize Fresh Database with Complete Schema
Creates bot/etlegacy_production.db with all required tables
"""

import sqlite3
import sys
from pathlib import Path


def create_fresh_database(db_path="bot/etlegacy_production.db"):
    """Create fresh database with complete schema including processed_files"""
    
    # Ensure bot directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database if present
    if Path(db_path).exists():
        print(f"⚠️  Database exists: {db_path}")
        response = input("Delete and recreate? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(1)
        Path(db_path).unlink()
        print(f"✓ Deleted {db_path}")
    
    print(f"\n{'='*70}")
    print(f"CREATING FRESH DATABASE: {db_path}")
    print('='*70)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. Sessions table
    print("\n1. Creating sessions table...")
    c.execute('''
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            defender_team INTEGER DEFAULT 0,
            winner_team INTEGER DEFAULT 0,
            time_limit TEXT,
            actual_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_date, map_name, round_number)
        )
    ''')
    print("   ✓ sessions table created")
    
    # 2. Player comprehensive stats table
    print("\n2. Creating player_comprehensive_stats table...")
    c.execute('''
        CREATE TABLE player_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            guid TEXT,
            team INTEGER NOT NULL,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            gibs INTEGER DEFAULT 0,
            suicides INTEGER DEFAULT 0,
            teamkills INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            damage_given INTEGER DEFAULT 0,
            damage_received INTEGER DEFAULT 0,
            damage_team INTEGER DEFAULT 0,
            hits INTEGER DEFAULT 0,
            shots INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0,
            revives INTEGER DEFAULT 0,
            ammogiven INTEGER DEFAULT 0,
            healthgiven INTEGER DEFAULT 0,
            poisoned INTEGER DEFAULT 0,
            knifekills INTEGER DEFAULT 0,
            killpeak INTEGER DEFAULT 0,
            efficiency REAL DEFAULT 0.0,
            score INTEGER DEFAULT 0,
            dyn_planted INTEGER DEFAULT 0,
            dyn_defused INTEGER DEFAULT 0,
            obj_captured INTEGER DEFAULT 0,
            obj_destroyed INTEGER DEFAULT 0,
            obj_returned INTEGER DEFAULT 0,
            obj_taken INTEGER DEFAULT 0,
            obj_checkpoint INTEGER DEFAULT 0,
            obj_killed INTEGER DEFAULT 0,
            obj_protected INTEGER DEFAULT 0,
            time_played TEXT,
            time_played_seconds INTEGER DEFAULT 0,
            num_rounds INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    ''')
    print("   ✓ player_comprehensive_stats table created (49 columns)")
    
    # 3. Weapon comprehensive stats table
    print("\n3. Creating weapon_comprehensive_stats table...")
    c.execute('''
        CREATE TABLE weapon_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            weapon_name TEXT NOT NULL,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            hits INTEGER DEFAULT 0,
            shots INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    ''')
    print("   ✓ weapon_comprehensive_stats table created")
    
    # 4. Player links table
    print("\n4. Creating player_links table...")
    c.execute('''
        CREATE TABLE player_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            primary_name TEXT NOT NULL,
            alias_name TEXT NOT NULL,
            guid TEXT,
            link_type TEXT DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(primary_name, alias_name)
        )
    ''')
    print("   ✓ player_links table created")
    
    # 5. Processed files table (NEW - for duplicate prevention)
    print("\n5. Creating processed_files table...")
    c.execute('''
        CREATE TABLE processed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("   ✓ processed_files table created")
    
    # Create indexes for performance
    print("\n6. Creating indexes...")
    c.execute('''
        CREATE INDEX idx_player_stats_session 
        ON player_comprehensive_stats(session_id)
    ''')
    c.execute('''
        CREATE INDEX idx_player_stats_name 
        ON player_comprehensive_stats(player_name)
    ''')
    c.execute('''
        CREATE INDEX idx_weapon_stats_session 
        ON weapon_comprehensive_stats(session_id)
    ''')
    c.execute('''
        CREATE INDEX idx_weapon_stats_player 
        ON weapon_comprehensive_stats(player_name)
    ''')
    c.execute('''
        CREATE INDEX idx_sessions_date 
        ON sessions(session_date)
    ''')
    c.execute('''
        CREATE INDEX idx_processed_files_filename 
        ON processed_files(filename)
    ''')
    print("   ✓ 6 indexes created")
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ FRESH DATABASE CREATED SUCCESSFULLY")
    print('='*70)
    print(f"\nDatabase: {db_path}")
    print("Tables created:")
    print("  1. sessions (9 columns)")
    print("  2. player_comprehensive_stats (49 columns)")
    print("  3. weapon_comprehensive_stats (11 columns)")
    print("  4. player_links (6 columns)")
    print("  5. processed_files (6 columns) ← NEW for duplicate prevention")
    print("  6. 6 performance indexes")
    print("\nNext step: Import stats with duplicate prevention")
    print(f"  python tools/simple_bulk_import.py local_stats/*.txt")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "bot/etlegacy_production.db"
    
    create_fresh_database(db_path)
