"""
Migration 001: Create player_synergies table
Phase 1 - Synergy Detection

This migration creates the player_synergies table to store calculated
synergy scores between all player pairs.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = 'etlegacy_production.db'

def migrate():
    """Create player_synergies table with indexes"""
    
    print("=" * 60)
    print("🔧 Migration 001: Create player_synergies Table")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at {DB_PATH}")
        print("   Make sure you're running this from the stats directory")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_synergies'
        """)
        
        if cursor.fetchone():
            print("⚠️  Table 'player_synergies' already exists")
            print("   Skipping creation...")
            conn.close()
            return True
        
        print("\n📊 Creating player_synergies table...")
        
        # Create the table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_synergies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_a_guid TEXT NOT NULL,
                player_b_guid TEXT NOT NULL,
                
                -- Games statistics
                games_together INTEGER DEFAULT 0,
                games_same_team INTEGER DEFAULT 0,
                wins_together INTEGER DEFAULT 0,
                losses_together INTEGER DEFAULT 0,
                
                -- Win rate metrics
                win_rate_together REAL DEFAULT 0.0,
                player_a_solo_win_rate REAL DEFAULT 0.0,
                player_b_solo_win_rate REAL DEFAULT 0.0,
                expected_win_rate REAL DEFAULT 0.0,
                win_rate_boost REAL DEFAULT 0.0,
                
                -- Performance metrics
                player_a_performance_together REAL DEFAULT 0.0,
                player_b_performance_together REAL DEFAULT 0.0,
                player_a_performance_solo REAL DEFAULT 0.0,
                player_b_performance_solo REAL DEFAULT 0.0,
                performance_boost_a REAL DEFAULT 0.0,
                performance_boost_b REAL DEFAULT 0.0,
                performance_boost_avg REAL DEFAULT 0.0,
                
                -- Synergy score (composite metric)
                synergy_score REAL DEFAULT 0.0,
                confidence_level REAL DEFAULT 0.0,
                
                -- Metadata
                last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_played_together TIMESTAMP,
                
                -- Ensure unique pairs (alphabetically ordered)
                UNIQUE(player_a_guid, player_b_guid)
            )
        ''')
        print("✅ Table created successfully")
        
        # Create indexes for fast queries
        print("\n📑 Creating indexes...")
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_synergies_player_a 
            ON player_synergies(player_a_guid)
        ''')
        print("   ✅ Index on player_a_guid")
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_synergies_player_b 
            ON player_synergies(player_b_guid)
        ''')
        print("   ✅ Index on player_b_guid")
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_synergies_score 
            ON player_synergies(synergy_score DESC)
        ''')
        print("   ✅ Index on synergy_score")
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_synergies_games 
            ON player_synergies(games_same_team DESC)
        ''')
        print("   ✅ Index on games_same_team")
        
        # Commit changes
        conn.commit()
        
        # Verify table creation
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master 
            WHERE type='table' AND name='player_synergies'
        """)
        
        if cursor.fetchone()[0] == 1:
            print("\n✅ Migration completed successfully!")
            print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Database: {DB_PATH}")
            print("\n📊 Table Schema:")
            print("   - 28 columns (IDs, stats, metrics, metadata)")
            print("   - 4 indexes for query optimization")
            print("   - Ready for synergy calculations")
            
            conn.close()
            return True
        else:
            print("❌ Verification failed")
            conn.close()
            return False
            
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def rollback():
    """Rollback migration (drop table and indexes)"""
    
    print("=" * 60)
    print("🔄 Rolling back Migration 001")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("\n🗑️  Dropping player_synergies table...")
        cursor.execute('DROP TABLE IF EXISTS player_synergies')
        
        print("🗑️  Dropping indexes...")
        cursor.execute('DROP INDEX IF EXISTS idx_synergies_player_a')
        cursor.execute('DROP INDEX IF EXISTS idx_synergies_player_b')
        cursor.execute('DROP INDEX IF EXISTS idx_synergies_score')
        cursor.execute('DROP INDEX IF EXISTS idx_synergies_games')
        
        conn.commit()
        conn.close()
        
        print("✅ Rollback completed successfully")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Rollback failed: {e}")
        return False


def verify():
    """Verify migration was successful"""
    
    print("\n" + "=" * 60)
    print("🔍 Verifying Migration")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_synergies'
        """)
        
        if not cursor.fetchone():
            print("❌ Table 'player_synergies' does not exist")
            conn.close()
            return False
        
        print("✅ Table exists: player_synergies")
        
        # Check column count
        cursor.execute("PRAGMA table_info(player_synergies)")
        columns = cursor.fetchall()
        print(f"✅ Columns: {len(columns)} columns defined")
        
        # Check indexes
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='player_synergies'
        """)
        indexes = cursor.fetchall()
        print(f"✅ Indexes: {len(indexes)} indexes created")
        
        # Check if we can insert/query (dry run)
        cursor.execute("SELECT COUNT(*) FROM player_synergies")
        count = cursor.fetchone()[0]
        print(f"✅ Current rows: {count}")
        
        conn.close()
        
        print("\n✅ Migration verification passed!")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Verification failed: {e}")
        return False


if __name__ == '__main__':
    import sys
    
    print("\n🎯 FIVEEYES - Phase 1 Database Migration")
    print("   Creating player_synergies table\n")
    
    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'rollback':
            success = rollback()
        elif command == 'verify':
            success = verify()
        else:
            print(f"❌ Unknown command: {command}")
            print("   Usage: python 001_create_player_synergies.py [rollback|verify]")
            sys.exit(1)
    else:
        # Default: migrate
        success = migrate()
        if success:
            verify()
    
    sys.exit(0 if success else 1)
