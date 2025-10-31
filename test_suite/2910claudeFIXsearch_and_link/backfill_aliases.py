#!/usr/bin/env python3
"""
🔄 Player Aliases Backfill Script
=================================

This script populates the player_aliases table from existing player_comprehensive_stats data.

Run this ONCE after deploying the fixed bot to populate aliases for all historical games.

Usage:
    python3 backfill_aliases.py
    
Or with custom DB path:
    python3 backfill_aliases.py /path/to/etlegacy_production.db
"""

import sqlite3
import sys
from datetime import datetime

def backfill_aliases(db_path='etlegacy_production.db'):
    """Backfill player aliases from existing comprehensive stats"""
    
    print("=" * 70)
    print("🔄 PLAYER ALIASES BACKFILL SCRIPT")
    print("=" * 70)
    print(f"\n📊 Database: {db_path}\n")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if player_aliases table exists
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_aliases'
        ''')
        
        if not cursor.fetchone():
            print("❌ Error: player_aliases table does not exist!")
            print("\nPlease create the table first:")
            print('''
CREATE TABLE player_aliases (
    guid TEXT NOT NULL,
    alias TEXT NOT NULL,
    first_seen TEXT,
    last_seen TEXT,
    times_seen INTEGER DEFAULT 1,
    PRIMARY KEY (guid, alias)
);
            ''')
            return False
        
        print("✅ player_aliases table found\n")
        
        # Get current count
        cursor.execute('SELECT COUNT(*) FROM player_aliases')
        before_count = cursor.fetchone()[0]
        print(f"📊 Current aliases in database: {before_count:,}\n")
        
        # Get all unique GUID+name combinations from comprehensive stats
        print("🔍 Scanning player_comprehensive_stats table...")
        cursor.execute('''
            SELECT 
                player_guid, 
                player_name,
                MIN(session_date) as first_seen,
                MAX(session_date) as last_seen,
                COUNT(*) as times_seen
            FROM player_comprehensive_stats
            WHERE player_guid != 'UNKNOWN' AND player_name != 'Unknown'
            GROUP BY player_guid, player_name
            ORDER BY times_seen DESC
        ''')
        
        backfill_data = cursor.fetchall()
        
        if not backfill_data:
            print("⚠️ No player data found in player_comprehensive_stats table")
            return False
        
        print(f"✅ Found {len(backfill_data):,} unique player name combinations\n")
        
        # Show sample of what will be added
        print("📋 Sample of aliases to add:")
        print("-" * 70)
        for guid, alias, first, last, times in backfill_data[:5]:
            print(f"  • {alias[:30]:30} (GUID: {guid}) - seen {times:,}x")
        if len(backfill_data) > 5:
            print(f"  ... and {len(backfill_data) - 5:,} more")
        print()
        
        # Confirm before proceeding
        response = input("🚀 Proceed with backfill? [Y/n]: ").strip().lower()
        if response and response not in ('y', 'yes'):
            print("❌ Backfill cancelled")
            return False
        
        print("\n⚙️  Processing aliases...")
        
        # Insert into player_aliases (ignore if already exists)
        inserted = 0
        updated = 0
        skipped = 0
        
        for guid, alias, first, last, times in backfill_data:
            # Check if alias already exists
            cursor.execute('''
                SELECT times_seen, first_seen, last_seen 
                FROM player_aliases 
                WHERE guid = ? AND alias = ?
            ''', (guid, alias))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update if our data is newer or has more occurrences
                old_times, old_first, old_last = existing
                
                # Determine if we should update
                should_update = False
                new_first = first if first < old_first else old_first
                new_last = last if last > old_last else old_last
                new_times = max(times, old_times)
                
                if new_first != old_first or new_last != old_last or new_times != old_times:
                    should_update = True
                
                if should_update:
                    cursor.execute('''
                        UPDATE player_aliases
                        SET first_seen = ?, last_seen = ?, times_seen = ?
                        WHERE guid = ? AND alias = ?
                    ''', (new_first, new_last, new_times, guid, alias))
                    updated += 1
                else:
                    skipped += 1
            else:
                # Insert new alias
                cursor.execute('''
                    INSERT INTO player_aliases 
                    (guid, alias, first_seen, last_seen, times_seen)
                    VALUES (?, ?, ?, ?, ?)
                ''', (guid, alias, first, last, times))
                inserted += 1
            
            # Progress indicator
            if (inserted + updated + skipped) % 100 == 0:
                print(f"  ... processed {inserted + updated + skipped:,} aliases")
        
        # Commit changes
        conn.commit()
        
        # Get final count
        cursor.execute('SELECT COUNT(*) FROM player_aliases')
        after_count = cursor.fetchone()[0]
        
        # Get some statistics
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT guid) as total_players,
                SUM(times_seen) as total_occurrences
            FROM player_aliases
        ''')
        stats = cursor.fetchone()
        total_players, total_occurrences = stats
        
        # Report results
        print("\n" + "=" * 70)
        print("✅ BACKFILL COMPLETE!")
        print("=" * 70)
        print(f"\n📊 Results:")
        print(f"  • New aliases inserted:    {inserted:,}")
        print(f"  • Existing aliases updated: {updated:,}")
        print(f"  • Aliases skipped:          {skipped:,}")
        print(f"\n  • Before: {before_count:,} aliases")
        print(f"  • After:  {after_count:,} aliases")
        print(f"  • Added:  {after_count - before_count:,} aliases")
        print(f"\n📈 Database Summary:")
        print(f"  • Total unique players: {total_players:,}")
        print(f"  • Total name occurrences: {total_occurrences:,}")
        print(f"  • Average names per player: {after_count / total_players:.1f}")
        
        # Show top aliases
        print(f"\n🏆 Most frequently seen players:")
        cursor.execute('''
            SELECT alias, guid, times_seen
            FROM player_aliases
            ORDER BY times_seen DESC
            LIMIT 5
        ''')
        top_players = cursor.fetchall()
        for i, (alias, guid, times) in enumerate(top_players, 1):
            print(f"  {i}. {alias[:30]:30} - {times:,}x games")
        
        conn.close()
        
        print("\n✅ Backfill successful! Your !stats and !link commands should now work.\n")
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point"""
    # Get database path from command line or use default
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'etlegacy_production.db'
    
    print()
    success = backfill_aliases(db_path)
    
    if success:
        print("💡 Next steps:")
        print("  1. Restart your Discord bot")
        print("  2. Test with: !link")
        print("  3. Test with: !stats YourPlayerName")
        print()
        sys.exit(0)
    else:
        print("\n❌ Backfill failed - please fix the errors above and try again\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
