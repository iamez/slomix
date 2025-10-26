#!/usr/bin/env python3
"""
Populate Player Aliases from Historical Data
============================================

Purpose: Scan player_comprehensive_stats and populate player_aliases table

This script:
1. Reads all player records from player_comprehensive_stats
2. Groups by (player_guid, clean_name) 
3. Tracks first_seen, last_seen, times_used for each alias
4. Inserts into player_aliases table
5. Provides detailed progress report

Author: AI Agent
Date: October 4, 2025
"""

import sqlite3
import os
from datetime import datetime
from collections import defaultdict


DATABASE_PATH = "etlegacy_production.db"


def check_prerequisites():
    """Verify database and tables exist"""
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Database not found: {DATABASE_PATH}")
        return False
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Check player_aliases table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='player_aliases'
    """)
    if not cursor.fetchone():
        print(f"❌ player_aliases table not found!")
        print(f"   Run: python tools/create_player_aliases_table.py")
        conn.close()
        return False
    
    # Check player_comprehensive_stats exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='player_comprehensive_stats'
    """)
    if not cursor.fetchone():
        print(f"❌ player_comprehensive_stats table not found!")
        conn.close()
        return False
    
    conn.close()
    return True


def get_current_alias_count():
    """Get count of existing aliases"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM player_aliases")
    count = cursor.fetchone()[0]
    
    conn.close()
    return count


def analyze_aliases_to_populate():
    """Analyze what aliases will be populated"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"\n📊 Analyzing aliases to populate...")
    
    # Get all unique (guid, clean_name) combinations
    cursor.execute("""
        SELECT 
            player_guid,
            COUNT(DISTINCT clean_name) as alias_count,
            COUNT(*) as total_records
        FROM player_comprehensive_stats
        WHERE player_guid IS NOT NULL AND player_guid != ''
        GROUP BY player_guid
        ORDER BY alias_count DESC
    """)
    
    players = cursor.fetchall()
    
    total_guids = len(players)
    total_aliases = sum(p[1] for p in players)
    multi_alias_count = sum(1 for p in players if p[1] > 1)
    
    print(f"   Unique GUIDs: {total_guids}")
    print(f"   Total aliases to create: {total_aliases}")
    print(f"   Players with multiple aliases: {multi_alias_count}")
    
    conn.close()
    return total_aliases


def populate_aliases():
    """Main population logic"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"\n🔄 Populating player_aliases...")
    
    # Get all player records grouped by GUID and clean_name
    print(f"   Fetching player records...")
    cursor.execute("""
        SELECT 
            player_guid,
            player_name,
            clean_name,
            session_date,
            session_id
        FROM player_comprehensive_stats
        WHERE player_guid IS NOT NULL AND player_guid != ''
        ORDER BY player_guid, clean_name, session_date
    """)
    
    all_records = cursor.fetchall()
    print(f"   Retrieved {len(all_records):,} records")
    
    # Group aliases
    print(f"   Grouping aliases...")
    aliases = defaultdict(lambda: {
        'player_name': None,
        'first_seen': None,
        'last_seen': None,
        'times_used': 0
    })
    
    for guid, player_name, clean_name, session_date, session_id in all_records:
        key = (guid, clean_name)
        
        # Update alias info
        if aliases[key]['player_name'] is None:
            aliases[key]['player_name'] = player_name
        
        if aliases[key]['first_seen'] is None:
            aliases[key]['first_seen'] = session_date
        else:
            aliases[key]['first_seen'] = min(aliases[key]['first_seen'], session_date)
        
        if aliases[key]['last_seen'] is None:
            aliases[key]['last_seen'] = session_date
        else:
            aliases[key]['last_seen'] = max(aliases[key]['last_seen'], session_date)
        
        aliases[key]['times_used'] += 1
    
    print(f"   Grouped into {len(aliases):,} unique aliases")
    
    # Insert aliases
    print(f"   Inserting aliases into database...")
    inserted = 0
    skipped = 0
    errors = 0
    
    for (guid, clean_name), data in aliases.items():
        try:
            cursor.execute("""
                INSERT INTO player_aliases 
                (player_guid, player_name, clean_name, first_seen, last_seen, times_used)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                guid,
                data['player_name'],
                clean_name,
                data['first_seen'],
                data['last_seen'],
                data['times_used']
            ))
            inserted += 1
            
            # Progress indicator
            if inserted % 10 == 0:
                print(f"      Progress: {inserted}/{len(aliases)} aliases...", end='\r')
                
        except sqlite3.IntegrityError as e:
            skipped += 1
            # Alias already exists (UNIQUE constraint)
        except Exception as e:
            print(f"\n      ❌ Error inserting {guid}/{clean_name}: {e}")
            errors += 1
    
    print(f"      Progress: {inserted}/{len(aliases)} aliases... Done!")
    
    conn.commit()
    conn.close()
    
    return inserted, skipped, errors


def show_populated_aliases():
    """Show sample of populated aliases"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"\n📋 Sample of populated aliases:")
    
    # Show players with most aliases
    cursor.execute("""
        SELECT 
            player_guid,
            COUNT(*) as alias_count,
            GROUP_CONCAT(clean_name, ', ') as aliases
        FROM player_aliases
        GROUP BY player_guid
        HAVING alias_count > 1
        ORDER BY alias_count DESC
        LIMIT 5
    """)
    
    multi_alias = cursor.fetchall()
    
    if multi_alias:
        print(f"\n   Top 5 players with multiple aliases:")
        for guid, count, aliases_str in multi_alias:
            # Limit displayed aliases to 3
            alias_list = aliases_str.split(', ')[:3]
            display = ', '.join(alias_list)
            if count > 3:
                display += f", ... (+{count-3} more)"
            print(f"      • {guid}: {count} aliases → {display}")
    
    # Show recent aliases
    print(f"\n   Most recently used aliases:")
    cursor.execute("""
        SELECT 
            clean_name,
            player_guid,
            last_seen,
            times_used
        FROM player_aliases
        ORDER BY last_seen DESC
        LIMIT 5
    """)
    
    recent = cursor.fetchall()
    for name, guid, last_seen, times in recent:
        print(f"      • {name:<20} (GUID: {guid}) - Last: {last_seen}, Used: {times}x")
    
    conn.close()


def verify_population():
    """Verify aliases were populated correctly"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"\n✅ Verification:")
    
    # Count total aliases
    cursor.execute("SELECT COUNT(*) FROM player_aliases")
    total_aliases = cursor.fetchone()[0]
    print(f"   Total aliases: {total_aliases}")
    
    # Count unique GUIDs
    cursor.execute("SELECT COUNT(DISTINCT player_guid) FROM player_aliases")
    unique_guids = cursor.fetchone()[0]
    print(f"   Unique GUIDs: {unique_guids}")
    
    # Average aliases per GUID
    avg = total_aliases / unique_guids if unique_guids > 0 else 0
    print(f"   Avg aliases per GUID: {avg:.2f}")
    
    # Check for issues
    cursor.execute("""
        SELECT COUNT(*) FROM player_aliases 
        WHERE first_seen IS NULL OR last_seen IS NULL
    """)
    null_dates = cursor.fetchone()[0]
    if null_dates > 0:
        print(f"   ⚠️ Warning: {null_dates} aliases with NULL dates")
    else:
        print(f"   ✅ All aliases have valid dates")
    
    # Check times_used
    cursor.execute("SELECT MIN(times_used), MAX(times_used) FROM player_aliases")
    min_used, max_used = cursor.fetchone()
    print(f"   Usage range: {min_used} - {max_used} times")
    
    conn.close()


def main():
    """Main execution"""
    print("="*80)
    print("🔄 PLAYER ALIAS POPULATION SCRIPT")
    print("="*80)
    print(f"Database: {DATABASE_PATH}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Step 1: Check prerequisites
    if not check_prerequisites():
        return
    
    # Step 2: Check if already populated
    current_count = get_current_alias_count()
    if current_count > 0:
        print(f"\n⚠️ player_aliases table already contains {current_count} aliases!")
        response = input(f"   Repopulate? (will skip existing) [y/N]: ")
        if response.lower() != 'y':
            print(f"   Aborted by user")
            return
    
    # Step 3: Analyze what will be populated
    expected_aliases = analyze_aliases_to_populate()
    
    # Step 4: Populate
    inserted, skipped, errors = populate_aliases()
    
    # Step 5: Show samples
    show_populated_aliases()
    
    # Step 6: Verify
    verify_population()
    
    # Summary
    print(f"\n" + "="*80)
    print(f"📋 SUMMARY")
    print(f"="*80)
    print(f"✅ Aliases inserted: {inserted}")
    if skipped > 0:
        print(f"⏭️  Aliases skipped: {skipped} (already existed)")
    if errors > 0:
        print(f"❌ Errors: {errors}")
    
    print(f"\n📝 Next steps:")
    print(f"   1. Verify aliases: python check_aliases.py")
    print(f"   2. Migrate Discord mappings: python tools/migrate_discord_mappings.py")
    print(f"   3. Update bot commands to use aliases")
    
    print(f"\n✅ Alias population complete!")


if __name__ == "__main__":
    main()
