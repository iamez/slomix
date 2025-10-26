#!/usr/bin/env python3
"""
Apply Hardcoded Player Links from auto_link_database.py
This script will apply all the DEFAULT_AUTO_LINK_MAPPINGS to your current database
"""
import sqlite3
from auto_link_database import DEFAULT_AUTO_LINK_MAPPINGS

def apply_hardcoded_links():
    """Apply all hardcoded mappings from auto_link_database.py to the current database"""
    DATABASE_PATH = 'etlegacy_fixed_bulk.db'
    
    print("🔗 Applying Hardcoded Player Links from auto_link_database.py")
    print("="*70)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Check current links
    cursor.execute('SELECT COUNT(*) FROM player_links')
    current_links = cursor.fetchone()[0]
    print(f"📊 Current links in database: {current_links}")
    
    links_added = 0
    links_skipped = 0
    errors = 0
    
    print(f"\n🎯 Processing {len(DEFAULT_AUTO_LINK_MAPPINGS)} hardcoded mappings...")
    print("-"*70)
    
    for guid, (discord_id, discord_name) in DEFAULT_AUTO_LINK_MAPPINGS.items():
        try:
            # Check if player exists in player_round_stats
            cursor.execute('''
                SELECT clean_name_final, SUM(kills), COUNT(*) 
                FROM player_round_stats 
                WHERE player_guid = ? 
                GROUP BY player_guid
            ''', (guid,))
            
            player_data = cursor.fetchone()
            
            if not player_data:
                print(f"⚠️  GUID {guid} not found in player_round_stats - skipping")
                links_skipped += 1
                continue
                
            et_name, kills, rounds = player_data
            
            # Check if already linked
            cursor.execute('SELECT discord_id FROM player_links WHERE et_guid = ?', (guid,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"⏭️  {et_name:<15} already linked (Discord ID: {existing[0]}) - skipping")
                links_skipped += 1
                continue
            
            # Insert the link
            cursor.execute('''
                INSERT INTO player_links (et_guid, discord_id, discord_username, et_name, verified)
                VALUES (?, ?, ?, ?, ?)
            ''', (guid, discord_id, discord_name, et_name, True))
            
            print(f"✅ {et_name:<15} → {discord_name:<20} | {kills:5,} kills, {rounds:4,} rounds")
            links_added += 1
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: player_links.discord_id" in str(e):
                print(f"❌ Discord ID {discord_id} already used for another player - skipping {guid}")
            else:
                print(f"❌ Error linking {guid}: {e}")
            errors += 1
        except Exception as e:
            print(f"❌ Unexpected error with {guid}: {e}")
            errors += 1
    
    conn.commit()
    
    # Final summary
    print("\n" + "="*70)
    print("📈 FINAL SUMMARY:")
    print(f"   ✅ Links added: {links_added}")
    print(f"   ⏭️  Links skipped: {links_skipped}")
    print(f"   ❌ Errors: {errors}")
    
    # Show updated count
    cursor.execute('SELECT COUNT(*) FROM player_links')
    final_links = cursor.fetchone()[0]
    print(f"   📊 Total links in database: {final_links}")
    
    if links_added > 0:
        print(f"\n🎉 Successfully added {links_added} new player links!")
        print("   You can now use: python link_existing.py linked")
    
    conn.close()

def show_hardcoded_mappings():
    """Display all hardcoded mappings from auto_link_database.py"""
    print("\n🗂️ HARDCODED MAPPINGS from auto_link_database.py:")
    print("="*80)
    print(f"{'GUID':<10} {'Discord ID':<20} {'Discord Name':<25} {'Status'}")
    print("-"*80)
    
    conn = sqlite3.connect('etlegacy_fixed_bulk.db')
    cursor = conn.cursor()
    
    for guid, (discord_id, discord_name) in DEFAULT_AUTO_LINK_MAPPINGS.items():
        # Check if player exists
        cursor.execute('SELECT clean_name_final, SUM(kills) FROM player_round_stats WHERE player_guid = ? GROUP BY player_guid', (guid,))
        player_data = cursor.fetchone()
        
        if player_data:
            et_name, kills = player_data
            status = f"✅ {et_name} ({kills:,} kills)"
        else:
            status = "❌ Not found in database"
            
        print(f"{guid:<10} {discord_id:<20} {discord_name:<25} {status}")
    
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        show_hardcoded_mappings()
    else:
        apply_hardcoded_links()
        
        print("\n💡 USAGE:")
        print("   python apply_hardcoded_links.py        # Apply all mappings")
        print("   python apply_hardcoded_links.py show   # Show all mappings")
        print("   python link_existing.py linked         # View linked players")