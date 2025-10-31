#!/usr/bin/env python3
"""
🔍 Database Diagnostic Script
==============================
This script checks:
1. What tables exist in the database
2. What columns each table has
3. Whether tables are being populated
4. What column names the bot SHOULD be using

Run this to understand your database structure!
"""

import sqlite3
import sys
import os

def diagnose_database(db_path='etlegacy_production.db'):
    """Diagnose database schema and contents"""
    
    print("=" * 80)
    print("🔍 DATABASE DIAGNOSTIC REPORT")
    print("=" * 80)
    print(f"\n📁 Database: {db_path}\n")
    
    if not os.path.exists(db_path):
        print(f"❌ ERROR: Database file not found!")
        print(f"   Looked for: {os.path.abspath(db_path)}")
        print(f"\n💡 Try:")
        print(f"   - Check you're in the right directory")
        print(f"   - Look for: etlegacy_fixed_bulk.db")
        print(f"   - Look for: etlegacy_comprehensive.db")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # ============================================================================
    # CHECK 1: What tables exist?
    # ============================================================================
    print("📊 TABLES IN DATABASE:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = cursor.fetchall()
    
    if not tables:
        print("❌ No tables found in database!")
        return False
    
    for (table_name,) in tables:
        print(f"  ✅ {table_name}")
    
    print(f"\n📈 Total tables: {len(tables)}")
    
    # ============================================================================
    # CHECK 2: player_comprehensive_stats schema
    # ============================================================================
    print("\n" + "=" * 80)
    print("📋 player_comprehensive_stats COLUMNS:")
    print("-" * 80)
    
    cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
    pcs_columns = cursor.fetchall()
    
    if not pcs_columns:
        print("❌ player_comprehensive_stats table not found!")
    else:
        print(f"✅ Found {len(pcs_columns)} columns:")
        print()
        
        # Group columns by category for easier reading
        name_columns = []
        guid_columns = []
        stat_columns = []
        
        for col_id, col_name, col_type, not_null, default, pk in pcs_columns:
            if 'name' in col_name.lower():
                name_columns.append(col_name)
            elif 'guid' in col_name.lower():
                guid_columns.append(col_name)
            else:
                stat_columns.append(col_name)
        
        if name_columns:
            print("  🏷️  NAME COLUMNS:")
            for col in name_columns:
                print(f"     - {col}")
        
        if guid_columns:
            print("\n  🆔 GUID COLUMNS:")
            for col in guid_columns:
                print(f"     - {col}")
        
        print(f"\n  📊 STAT COLUMNS: {len(stat_columns)} columns")
        print(f"     (kills, deaths, damage_given, etc.)")
    
    # ============================================================================
    # CHECK 3: player_aliases schema
    # ============================================================================
    print("\n" + "=" * 80)
    print("📋 player_aliases COLUMNS:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='player_aliases'
    """)
    
    if not cursor.fetchone():
        print("❌ player_aliases table DOES NOT EXIST!")
        print("   This is why !stats and !link aren't working!")
        print()
        print("💡 SOLUTION:")
        print("   1. The table needs to be created")
        print("   2. Run backfill_aliases.py to populate it")
    else:
        cursor.execute("PRAGMA table_info(player_aliases)")
        alias_columns = cursor.fetchall()
        
        print(f"✅ Found {len(alias_columns)} columns:")
        for col_id, col_name, col_type, not_null, default, pk in alias_columns:
            print(f"   - {col_name} ({col_type})")
        
        # Check if populated
        cursor.execute("SELECT COUNT(*) FROM player_aliases")
        alias_count = cursor.fetchone()[0]
        
        print(f"\n📊 Aliases in table: {alias_count:,}")
        
        if alias_count == 0:
            print("   ⚠️  TABLE IS EMPTY! Run backfill_aliases.py")
        else:
            print("   ✅ Table is populated")
            
            # Show sample
            cursor.execute("""
                SELECT guid, alias, times_seen, last_seen 
                FROM player_aliases 
                ORDER BY times_seen DESC 
                LIMIT 5
            """)
            samples = cursor.fetchall()
            
            print("\n   📝 Sample aliases:")
            for guid, alias, times, last in samples:
                print(f"      {alias[:20]:20} (GUID: {guid}, seen {times}x)")
    
    # ============================================================================
    # CHECK 4: player_links schema
    # ============================================================================
    print("\n" + "=" * 80)
    print("📋 player_links COLUMNS:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='player_links'
    """)
    
    if not cursor.fetchone():
        print("❌ player_links table DOES NOT EXIST!")
    else:
        cursor.execute("PRAGMA table_info(player_links)")
        link_columns = cursor.fetchall()
        
        print(f"✅ Found {len(link_columns)} columns:")
        for col_id, col_name, col_type, not_null, default, pk in link_columns:
            print(f"   - {col_name} ({col_type})")
        
        # Check if populated
        cursor.execute("SELECT COUNT(*) FROM player_links")
        link_count = cursor.fetchone()[0]
        
        print(f"\n📊 Links in table: {link_count:,}")
        
        if link_count == 0:
            print("   ⚠️  TABLE IS EMPTY! No players linked yet")
        else:
            print("   ✅ Table is populated")
            
            # Show sample
            cursor.execute("""
                SELECT et_guid, discord_id, et_name 
                FROM player_links 
                LIMIT 5
            """)
            samples = cursor.fetchall()
            
            print("\n   📝 Sample links:")
            for guid, discord_id, name in samples:
                print(f"      {name[:20]:20} → Discord: {discord_id}")
    
    # ============================================================================
    # CHECK 5: Data population check
    # ============================================================================
    print("\n" + "=" * 80)
    print("📊 DATA POPULATION CHECK:")
    print("-" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
    pcs_count = cursor.fetchone()[0]
    
    print(f"✅ player_comprehensive_stats: {pcs_count:,} records")
    
    if pcs_count == 0:
        print("   ⚠️  NO DATA! Have you imported any stats files?")
    else:
        # Show sample player names
        cursor.execute("""
            SELECT DISTINCT player_name, clean_name, clean_name_final 
            FROM player_comprehensive_stats 
            LIMIT 5
        """)
        samples = cursor.fetchall()
        
        print("\n   📝 Sample player names:")
        for player_name, clean_name, clean_name_final in samples:
            print(f"      player_name: {player_name}")
            print(f"      clean_name: {clean_name}")
            print(f"      clean_name_final: {clean_name_final}")
            print()
    
    # ============================================================================
    # CHECK 6: Critical findings
    # ============================================================================
    print("=" * 80)
    print("🎯 CRITICAL FINDINGS:")
    print("-" * 80)
    
    # Check for player_name column
    cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
    columns = [col[1] for col in cursor.fetchall()]
    
    has_player_name = 'player_name' in columns
    has_clean_name = 'clean_name' in columns
    has_clean_name_final = 'clean_name_final' in columns
    
    print()
    if has_player_name:
        print("✅ player_name column EXISTS")
    else:
        print("❌ player_name column MISSING")
        
    if has_clean_name:
        print("✅ clean_name column EXISTS")
    else:
        print("❌ clean_name column MISSING")
        
    if has_clean_name_final:
        print("✅ clean_name_final column EXISTS")
    else:
        print("❌ clean_name_final column MISSING")
    
    print()
    print("💡 RECOMMENDED FIXES:")
    print()
    
    if not has_player_name and (has_clean_name or has_clean_name_final):
        print("⚠️  Your database uses 'clean_name' NOT 'player_name'!")
        print("   The bot queries need to be updated to use 'clean_name'")
        print()
        print("   SOLUTION:")
        print("   Replace all: player_name")
        print("   With: clean_name  (or clean_name_final)")
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='player_aliases'
    """)
    if not cursor.fetchone():
        print("❌ player_aliases table MISSING!")
        print("   This is breaking !stats and !link commands")
        print()
        print("   SOLUTION:")
        print("   1. Create the table (check database schema)")
        print("   2. Run backfill_aliases.py")
    else:
        cursor.execute("SELECT COUNT(*) FROM player_aliases")
        if cursor.fetchone()[0] == 0:
            print("⚠️  player_aliases table is EMPTY!")
            print("   This is breaking !stats and !link commands")
            print()
            print("   SOLUTION:")
            print("   Run: python3 backfill_aliases.py")
    
    print()
    print("=" * 80)
    print("✅ DIAGNOSTIC COMPLETE")
    print("=" * 80)
    
    conn.close()
    return True

if __name__ == "__main__":
    # Try to find database
    db_paths = [
        'etlegacy_production.db',
        'etlegacy_fixed_bulk.db',
        'etlegacy_comprehensive.db',
        '../etlegacy_production.db',
        'dev/etlegacy_production.db',
    ]
    
    # Check if user provided path
    if len(sys.argv) > 1:
        db_paths.insert(0, sys.argv[1])
    
    found = False
    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f"\n🔍 Found database: {db_path}\n")
            diagnose_database(db_path)
            found = True
            break
    
    if not found:
        print("\n❌ Could not find database file!")
        print("\nTried:")
        for path in db_paths:
            print(f"  - {path}")
        print("\n💡 Usage:")
        print("  python3 diagnose_database.py")
        print("  python3 diagnose_database.py /path/to/your/database.db")
        sys.exit(1)
