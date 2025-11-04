#!/usr/bin/env python3
"""
Migration: Add defender_team and winner_team columns to sessions table

These fields are extracted from the stats file header:
- header_parts[4] = defender_team (1=Axis, 2=Allies)
- header_parts[5] = winner_team (1=Axis, 2=Allies, 0=Draw)

The game engine automatically determines the winner based on:
- Stopwatch mode: Which team completed objectives faster
- Objectives: Which team completed/defended objectives
- Time comparison: Automatic comparison of round times
"""

import sqlite3
import sys
from pathlib import Path


def migrate(db_path: str = "etlegacy_production.db"):
    """Add winner_team and defender_team columns to sessions table"""
    
    print(f"\n🔧 Migration: Adding winner_team and defender_team columns")
    print(f"   Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'winner_team' in columns and 'defender_team' in columns:
            print("   ✅ Columns already exist - skipping migration")
            return
        
        # Add defender_team column
        if 'defender_team' not in columns:
            print("   📊 Adding defender_team column...")
            cursor.execute("""
                ALTER TABLE sessions 
                ADD COLUMN defender_team INTEGER DEFAULT 0
            """)
            print("      ✅ defender_team column added")
        else:
            print("   ⏭️  defender_team already exists")
        
        # Add winner_team column
        if 'winner_team' not in columns:
            print("   🏆 Adding winner_team column...")
            cursor.execute("""
                ALTER TABLE sessions 
                ADD COLUMN winner_team INTEGER DEFAULT 0
            """)
            print("      ✅ winner_team column added")
        else:
            print("   ⏭️  winner_team already exists")
        
        conn.commit()
        
        # Verify
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"\n   ✅ Migration complete!")
        print(f"   📊 Sessions table now has {len(columns)} columns")
        print(f"   🏆 winner_team: {'FOUND' if 'winner_team' in columns else 'NOT FOUND'}")
        print(f"   📊 defender_team: {'FOUND' if 'defender_team' in columns else 'NOT FOUND'}")
        
    except Exception as e:
        print(f"   ❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Migrate main database
    print("\n" + "="*60)
    print("MIGRATION: Add winner_team and defender_team to sessions")
    print("="*60)
    
    migrate("etlegacy_production.db")
    
    # Check if github folder exists
    github_db = Path("github/etlegacy_production.db")
    if github_db.exists():
        print("\n" + "="*60)
        print("GITHUB: Migrating github database")
        print("="*60)
        migrate(str(github_db))
    
    print("\n✅ All migrations complete!\n")
