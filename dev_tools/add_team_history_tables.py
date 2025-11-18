#!/usr/bin/env python3
"""
Add Team History Tracking Tables

Creates new tables to track team performance and continuity across sessions:

1. team_lineups:
   - Tracks unique team compositions (roster fingerprints)
   - Stores player GUIDs as sorted JSON for matching
   - Tracks first/last seen dates for lineup continuity

2. session_results:
   - Maps sessions to their team lineups
   - Stores final scores and winner
   - Links to session_teams for full roster details

This enables:
- Head-to-head records between specific rosters
- Win rate per lineup
- Team continuity tracking (same roster over multiple sessions)
- Historical performance of player combinations
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = "bot/etlegacy_production.db"


def add_team_history_tables(db_path: str = DB_PATH):
    """Add team history tracking tables to database"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("📊 Adding team history tracking tables...")
    
    # Table 1: team_lineups - Track unique roster compositions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lineup_hash TEXT NOT NULL UNIQUE,
            player_guids TEXT NOT NULL,
            player_count INTEGER NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            total_rounds INTEGER DEFAULT 1,
            total_wins INTEGER DEFAULT 0,
            total_losses INTEGER DEFAULT 0,
            total_ties INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  ✅ Created table: team_lineups")
    
    # Table 2: session_results - Store match outcomes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_date TEXT NOT NULL UNIQUE,
            team_1_lineup_id INTEGER,
            team_2_lineup_id INTEGER,
            team_1_name TEXT NOT NULL,
            team_2_name TEXT NOT NULL,
            team_1_score INTEGER NOT NULL,
            team_2_score INTEGER NOT NULL,
            winner TEXT,
            total_maps INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_1_lineup_id) REFERENCES team_lineups(id),
            FOREIGN KEY (team_2_lineup_id) REFERENCES team_lineups(id)
        )
    """)
    print("  ✅ Created table: session_results")
    
    # Indexes for performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_lineups_hash 
        ON team_lineups(lineup_hash)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_team_lineups_dates 
        ON team_lineups(first_seen, last_seen)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_results_date 
        ON session_results(round_date)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_results_lineups 
        ON session_results(team_1_lineup_id, team_2_lineup_id)
    """)
    
    print("  ✅ Created indexes for performance")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Team history tables added successfully!")
    print("\nNew tables:")
    print("  • team_lineups: Tracks unique roster compositions")
    print("  • session_results: Stores match outcomes and scores")
    print("\nNext steps:")
    print("  1. Backfill existing sessions: python backfill_team_history.py")
    print("  2. Auto-populate on new sessions via _detect_and_store_persistent_teams")


def verify_tables(db_path: str = DB_PATH):
    """Verify tables were created successfully"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('team_lineups', 'session_results')
        ORDER BY name
    """)
    
    tables = cursor.fetchall()
    print(f"\n📋 Found {len(tables)} new tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"  • {table[0]}: {count} rows")
    
    conn.close()


if __name__ == "__main__":
    try:
        add_team_history_tables()
        verify_tables()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
