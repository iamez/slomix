#!/usr/bin/env python3
"""
Create player_aliases Table in Production Database
=================================================

Purpose: Add alias tracking to etlegacy_production.db

This script:
1. Checks current database structure
2. Creates player_aliases table if needed
3. Verifies table creation
4. Provides migration status report

Author: AI Agent
Date: October 4, 2025
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime


DATABASE_PATH = "etlegacy_production.db"


def check_database_exists():
    """Verify database file exists"""
    if not os.path.exists(DATABASE_PATH):
        expected = Path(__file__).resolve().parent.parent / DATABASE_PATH
        print(f"❌ Database not found: {DATABASE_PATH}")
        print(f"   Expected location: {expected}")
        return False
    
    print(f"✅ Database found: {DATABASE_PATH}")
    return True


def check_existing_tables():
    """Check what tables currently exist"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📊 Existing tables ({len(tables)}):")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   • {table:<30} ({count:,} records)")
    
    conn.close()
    return tables


def check_player_links_structure():
    """Check player_links table structure"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(player_links)")
        columns = cursor.fetchall()
        
        if columns:
            print(f"\n🔗 player_links table structure:")
            print(f"   Columns ({len(columns)}):")
            for col in columns:
                col_id, name, col_type, notnull, default, pk = col
                print(f"      {col_id+1}. {name:<20} {col_type:<15} {'PK' if pk else ''}")
            
            # Count current links
            cursor.execute("SELECT COUNT(*) FROM player_links")
            count = cursor.fetchone()[0]
            print(f"   Current linked accounts: {count}")
            
            return True
        else:
            print(f"\n⚠️ player_links table exists but has no columns (empty)")
            return False
            
    except sqlite3.OperationalError as e:
        print(f"\n⚠️ player_links table not found: {e}")
        return False
    finally:
        conn.close()


def create_player_aliases_table():
    """Create the player_aliases table with indexes"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"\n🏗️ Creating player_aliases table...")
    
    # Check if table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_aliases'")
    if cursor.fetchone():
        print(f"⚠️ Table player_aliases already exists!")
        
        # Show existing structure
        cursor.execute("PRAGMA table_info(player_aliases)")
        columns = cursor.fetchall()
        print(f"   Existing columns ({len(columns)}):")
        for col in columns:
            col_id, name, col_type, notnull, default, pk = col
            print(f"      {name:<20} {col_type:<15}")
        
        conn.close()
        return False
    
    # Create the table
    cursor.execute('''
        CREATE TABLE player_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_guid TEXT NOT NULL,
            player_name TEXT NOT NULL,
            clean_name TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            times_used INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_guid, clean_name)
        )
    ''')
    
    print(f"✅ Table player_aliases created successfully!")
    
    # Create indexes for performance
    print(f"📑 Creating indexes...")
    
    cursor.execute('''
        CREATE INDEX idx_aliases_guid 
        ON player_aliases(player_guid)
    ''')
    print(f"   ✅ Index on player_guid created")
    
    cursor.execute('''
        CREATE INDEX idx_aliases_clean 
        ON player_aliases(clean_name)
    ''')
    print(f"   ✅ Index on clean_name created")
    
    cursor.execute('''
        CREATE INDEX idx_aliases_last_seen 
        ON player_aliases(last_seen DESC)
    ''')
    print(f"   ✅ Index on last_seen created")
    
    conn.commit()
    
    # Verify creation
    cursor.execute("PRAGMA table_info(player_aliases)")
    columns = cursor.fetchall()
    print(f"\n✅ Verification - Table has {len(columns)} columns:")
    for col in columns:
        col_id, name, col_type, notnull, default, pk = col
        pk_str = " [PRIMARY KEY]" if pk else ""
        notnull_str = " NOT NULL" if notnull else ""
        default_str = f" DEFAULT {default}" if default else ""
        print(f"      {name:<20} {col_type:<15}{pk_str}{notnull_str}{default_str}")
    
    conn.close()
    return True


def get_alias_statistics():
    """Get statistics about aliases that will be populated"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"\n📊 Alias Statistics Preview (from player_comprehensive_stats):")
    
    # Count unique GUIDs
    cursor.execute("SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats")
    unique_guids = cursor.fetchone()[0]
    print(f"   Unique GUIDs: {unique_guids}")
    
    # Count unique names
    cursor.execute("SELECT COUNT(DISTINCT player_name) FROM player_comprehensive_stats")
    unique_names = cursor.fetchone()[0]
    print(f"   Unique player_names: {unique_names}")
    
    # Count unique clean names
    cursor.execute("SELECT COUNT(DISTINCT clean_name) FROM player_comprehensive_stats")
    unique_clean = cursor.fetchone()[0]
    print(f"   Unique clean_names: {unique_clean}")
    
    # Calculate ratio
    ratio = unique_names / unique_guids if unique_guids > 0 else 0
    print(f"   Names per GUID: {ratio:.2f}")
    
    # Find players with most aliases
    cursor.execute('''
        SELECT 
            player_guid,
            COUNT(DISTINCT clean_name) as name_count,
            GROUP_CONCAT(DISTINCT clean_name) as names
        FROM player_comprehensive_stats
        GROUP BY player_guid
        HAVING COUNT(DISTINCT clean_name) > 1
        ORDER BY name_count DESC
        LIMIT 5
    ''')
    
    multi_alias_players = cursor.fetchall()
    
    if multi_alias_players:
        print(f"\n   Top 5 players with multiple aliases:")
        for guid, count, names in multi_alias_players:
            names_list = names.split(',')[:3]  # Show first 3
            names_str = ', '.join(names_list)
            if count > 3:
                names_str += f", ... (+{count-3} more)"
            print(f"      • {guid}: {count} aliases ({names_str})")
    
    conn.close()


def main():
    """Main execution"""
    print("="*80)
    print("🔗 PLAYER ALIAS TABLE CREATION SCRIPT")
    print("="*80)
    print(f"Database: {DATABASE_PATH}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Step 1: Check database exists
    if not check_database_exists():
        return
    
    # Step 2: Check existing tables
    existing_tables = check_existing_tables()
    
    # Step 3: Check player_links structure
    check_player_links_structure()
    
    # Step 4: Get alias statistics
    get_alias_statistics()
    
    # Step 5: Create player_aliases table
    success = create_player_aliases_table()
    
    # Summary
    print(f"\n" + "="*80)
    print(f"📋 SUMMARY")
    print(f"="*80)
    
    if success:
        print(f"✅ player_aliases table created successfully!")
        print(f"✅ All indexes created")
        print(f"\n📝 Next steps:")
        print(f"   1. Run: python tools/populate_player_aliases.py")
        print(f"   2. Verify: Check aliases populated correctly")
        print(f"   3. Migrate: Apply hardcoded Discord mappings")
    else:
        print(f"⚠️ Table already exists - no changes made")
        print(f"\n📝 Next steps:")
        print(f"   1. Check if aliases are already populated")
        print(f"   2. Or drop and recreate: DROP TABLE player_aliases")
    
    print(f"\n✅ Script complete!")


if __name__ == "__main__":
    main()
