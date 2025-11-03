"""
Fresh Database Import - Wipe and reimport all stats from scratch
"""

import sqlite3
import os
import sys
import glob
from datetime import datetime

# Add bot to path
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

DB_PATH = 'bot/etlegacy_production.db'

def create_fresh_database():
    """Create a fresh database with the schema"""
    print("="*80)
    print("🗑️  WIPING DATABASE")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drop all tables
    cursor.execute("DROP TABLE IF EXISTS player_comprehensive_stats")
    cursor.execute("DROP TABLE IF EXISTS weapon_comprehensive_stats")
    cursor.execute("DROP TABLE IF EXISTS sessions")
    cursor.execute("DROP TABLE IF EXISTS processed_files")
    cursor.execute("DROP TABLE IF EXISTS player_aliases")
    cursor.execute("DROP TABLE IF EXISTS player_links")
    cursor.execute("DROP TABLE IF EXISTS session_teams")
    
    print("✅ Dropped all tables")
    
    # Create sessions table
    cursor.execute("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            duration_seconds INTEGER,
            winner_team INTEGER,
            axis_score INTEGER DEFAULT 0,
            allies_score INTEGER DEFAULT 0,
            total_players INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_date, map_name, round_number)
        )
    """)
    
    # Create player_comprehensive_stats table
    cursor.execute("""
        CREATE TABLE player_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            player_guid TEXT NOT NULL,
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
            headshot_kills INTEGER DEFAULT 0,
            time_played_seconds INTEGER DEFAULT 0,
            time_played_minutes REAL DEFAULT 0,
            time_dead_minutes REAL DEFAULT 0,
            time_dead_ratio REAL DEFAULT 0,
            xp INTEGER DEFAULT 0,
            kd_ratio REAL DEFAULT 0,
            dpm REAL DEFAULT 0,
            efficiency REAL DEFAULT 0,
            bullets_fired INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0,
            kill_assists INTEGER DEFAULT 0,
            objectives_completed INTEGER DEFAULT 0,
            objectives_destroyed INTEGER DEFAULT 0,
            objectives_stolen INTEGER DEFAULT 0,
            objectives_returned INTEGER DEFAULT 0,
            dynamites_planted INTEGER DEFAULT 0,
            dynamites_defused INTEGER DEFAULT 0,
            times_revived INTEGER DEFAULT 0,
            revives_given INTEGER DEFAULT 0,
            most_useful_kills INTEGER DEFAULT 0,
            useless_kills INTEGER DEFAULT 0,
            kill_steals INTEGER DEFAULT 0,
            denied_playtime INTEGER DEFAULT 0,
            constructions INTEGER DEFAULT 0,
            tank_meatshield REAL DEFAULT 0,
            double_kills INTEGER DEFAULT 0,
            triple_kills INTEGER DEFAULT 0,
            quad_kills INTEGER DEFAULT 0,
            multi_kills INTEGER DEFAULT 0,
            mega_kills INTEGER DEFAULT 0,
            killing_spree_best INTEGER DEFAULT 0,
            death_spree_worst INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Create processed_files table
    cursor.execute("""
        CREATE TABLE processed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create player_aliases table
    cursor.execute("""
        CREATE TABLE player_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT NOT NULL,
            alias TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            times_seen INTEGER DEFAULT 1,
            UNIQUE(guid, alias)
        )
    """)
    
    # Create indices
    cursor.execute("CREATE INDEX idx_sessions_date ON sessions(session_date)")
    cursor.execute("CREATE INDEX idx_player_stats_session ON player_comprehensive_stats(session_id)")
    cursor.execute("CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid)")
    cursor.execute("CREATE INDEX idx_player_stats_date ON player_comprehensive_stats(session_date)")
    cursor.execute("CREATE INDEX idx_player_aliases_guid ON player_aliases(guid)")
    
    conn.commit()
    conn.close()
    
    print("✅ Created fresh database schema")

def import_all_files():
    """Import all stats files"""
    print("\n" + "="*80)
    print("📥 IMPORTING ALL STATS FILES")
    print("="*80 + "\n")
    
    parser = C0RNP0RN3StatsParser()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all files sorted
    all_files = sorted(glob.glob('bot/local_stats/2025-*.txt'))
    
    print(f"📁 Found {len(all_files)} files to import\n")
    
    imported = 0
    failed = 0
    
    for filepath in all_files:
        filename = os.path.basename(filepath)
        
        try:
            # Parse file
            parsed_data = parser.parse_stats_file(filepath)
            
            if not parsed_data.get('success', False):
                print(f"❌ {filename}: Parse failed - {parsed_data.get('error', 'Unknown')}")
                failed += 1
                continue
            
            # Extract session info
            session_date = filename[:19]  # YYYY-MM-DD-HHMMSS
            map_name = parsed_data.get('map_name', 'unknown')
            round_num = parsed_data.get('round_num', 0)
            players = parsed_data.get('players', [])
            
            # Insert session
            cursor.execute("""
                INSERT OR IGNORE INTO sessions 
                (session_date, map_name, round_number, total_players)
                VALUES (?, ?, ?, ?)
            """, (session_date, map_name, round_num, len(players)))
            
            # Get session ID
            cursor.execute("""
                SELECT id FROM sessions 
                WHERE session_date = ? AND map_name = ? AND round_number = ?
            """, (session_date, map_name, round_num))
            
            session_id = cursor.fetchone()[0]
            
            # Insert players
            for player in players:
                player_name = player.get('name', '')
                player_guid = player.get('guid', '')
                
                cursor.execute("""
                    INSERT INTO player_comprehensive_stats
                    (session_id, session_date, map_name, round_number, player_guid, player_name,
                     kills, deaths, damage_given, damage_received, headshot_kills,
                     time_played_minutes, accuracy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, session_date, map_name, round_num, player_guid, player_name,
                    player.get('kills', 0),
                    player.get('deaths', 0),
                    player.get('damage_given', 0),
                    player.get('damage_received', 0),
                    player.get('headshots', 0),
                    player.get('time_played', 0),
                    player.get('accuracy', 0)
                ))
                
                # Update aliases
                cursor.execute("""
                    INSERT OR REPLACE INTO player_aliases
                    (guid, alias, first_seen, last_seen, times_seen)
                    VALUES (
                        ?,
                        ?,
                        COALESCE((SELECT first_seen FROM player_aliases WHERE guid=? AND alias=?), ?),
                        ?,
                        COALESCE((SELECT times_seen FROM player_aliases WHERE guid=? AND alias=?), 0) + 1
                    )
                """, (player_guid, player_name, player_guid, player_name, session_date,
                      session_date, player_guid, player_name))
            
            # Mark as processed
            cursor.execute("""
                INSERT OR IGNORE INTO processed_files (filename)
                VALUES (?)
            """, (filename,))
            
            imported += 1
            if imported % 50 == 0:
                print(f"  ✅ Imported {imported} files...")
                conn.commit()
            
        except Exception as e:
            print(f"❌ {filename}: {e}")
            failed += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*80}")
    print(f"📊 IMPORT COMPLETE")
    print(f"{'='*80}")
    print(f"✅ Imported: {imported} files")
    print(f"❌ Failed: {failed} files")
    print()

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🔥 FRESH DATABASE IMPORT")
    print("="*80)
    print()
    print("⚠️  WARNING: This will DELETE ALL existing data!")
    print()
    
    response = input("Type 'YES' to continue: ")
    
    if response.strip().upper() != 'YES':
        print("❌ Cancelled")
        sys.exit(0)
    
    create_fresh_database()
    import_all_files()
    
    print("✅ All done! Database is fresh and ready.")
