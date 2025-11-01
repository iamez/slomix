#!/usr/bin/env python3
"""
Check database for alias detection and linking system
"""

import sqlite3

DB_PATH = "etlegacy_production.db"

def check_database_structure():
    """Check tables and their schemas"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("📊 DATABASE STRUCTURE")
    print("=" * 80)
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\n✅ Found {len(tables)} tables:")
    for table in tables:
        print(f"  • {table[0]}")
    
    # Check player_links table
    print("\n" + "=" * 80)
    print("🔗 PLAYER_LINKS TABLE")
    print("=" * 80)
    
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='player_links'")
    result = cursor.fetchone()
    
    if result:
        print("\n✅ player_links table exists:")
        print(result[0])
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM player_links")
        count = cursor.fetchone()[0]
        print(f"\n📊 Total linked accounts: {count}")
        
        # Show sample data
        cursor.execute("SELECT * FROM player_links LIMIT 5")
        links = cursor.fetchall()
        if links:
            print("\n📋 Sample linked accounts:")
            for link in links:
                print(f"  {link}")
    else:
        print("❌ player_links table does NOT exist!")
    
    # Check for multiple aliases (same GUID, different names)
    print("\n" + "=" * 80)
    print("👥 ALIAS DETECTION - Same GUID, Different Names")
    print("=" * 80)
    
    query = """
    SELECT 
        player_guid,
        COUNT(DISTINCT player_name) as name_count,
        COUNT(DISTINCT clean_name) as clean_name_count,
        GROUP_CONCAT(DISTINCT player_name) as all_names,
        GROUP_CONCAT(DISTINCT clean_name) as all_clean_names,
        COUNT(*) as total_records
    FROM player_comprehensive_stats
    GROUP BY player_guid
    HAVING COUNT(DISTINCT player_name) > 1
    ORDER BY name_count DESC
    LIMIT 10
    """
    
    cursor.execute(query)
    aliases = cursor.fetchall()
    
    if aliases:
        print(f"\n✅ Found {len(aliases)} players with multiple aliases:")
        for i, alias in enumerate(aliases, 1):
            guid, name_count, clean_count, names, clean_names, records = alias
            print(f"\n{i}. GUID: {guid}")
            print(f"   Names ({name_count}): {names}")
            print(f"   Clean names ({clean_count}): {clean_names}")
            print(f"   Total records: {records}")
    else:
        print("✅ No aliases found (or all players use consistent names)")
    
    # Check for similar names (potential aliases by name similarity)
    print("\n" + "=" * 80)
    print("🔍 POTENTIAL ALIASES - Similar Clean Names")
    print("=" * 80)
    
    query = """
    SELECT 
        clean_name,
        COUNT(DISTINCT player_guid) as guid_count,
        GROUP_CONCAT(DISTINCT player_guid) as all_guids,
        GROUP_CONCAT(DISTINCT player_name) as all_names,
        COUNT(*) as total_records
    FROM player_comprehensive_stats
    GROUP BY clean_name
    HAVING COUNT(DISTINCT player_guid) > 1
    ORDER BY guid_count DESC
    LIMIT 10
    """
    
    cursor.execute(query)
    similar = cursor.fetchall()
    
    if similar:
        print(f"\n⚠️ Found {len(similar)} clean names with multiple GUIDs:")
        for i, sim in enumerate(similar, 1):
            clean, guid_count, guids, names, records = sim
            print(f"\n{i}. Clean Name: {clean}")
            print(f"   GUIDs ({guid_count}): {guids[:100]}...")
            print(f"   Names: {names[:100]}...")
            print(f"   Total records: {records}")
    else:
        print("✅ No clean name conflicts found")
    
    # Check player_comprehensive_stats for GUID/name distribution
    print("\n" + "=" * 80)
    print("📈 PLAYER STATISTICS")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats")
    unique_guids = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT player_name) FROM player_comprehensive_stats")
    unique_names = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT clean_name) FROM player_comprehensive_stats")
    unique_clean = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
    total_records = cursor.fetchone()[0]
    
    print(f"\n✅ Unique GUIDs: {unique_guids}")
    print(f"✅ Unique player_names: {unique_names}")
    print(f"✅ Unique clean_names: {unique_clean}")
    print(f"✅ Total records: {total_records}")
    print(f"\n📊 Name variation ratio: {unique_names / unique_guids:.2f} names per GUID")
    
    conn.close()


if __name__ == "__main__":
    check_database_structure()
