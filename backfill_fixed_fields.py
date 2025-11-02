"""
Backfill script to re-import affected sessions with fixed field mappings

This will:
1. Delete existing player_comprehensive_stats for Oct 28 & 30
2. Re-import all sessions using the fixed bot code
3. Verify the data is now correct
"""
import asyncio
import sqlite3
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))

from ultimate_bot import UltimateETLegacyBot


async def backfill_sessions():
    """Backfill all Oct 28 & 30 sessions"""
    
    print("=" * 80)
    print("BACKFILL: Re-importing Oct 28 & 30 sessions with fixed field mappings")
    print("=" * 80)
    
    # Get list of affected sessions
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, session_date, map_name, round_number
        FROM sessions
        WHERE session_date LIKE '2025-10-28%' OR session_date LIKE '2025-10-30%'
        ORDER BY session_date, map_name, round_number
    """)
    
    sessions = cursor.fetchall()
    print(f"\nFound {len(sessions)} sessions to backfill\n")
    
    # Get count of player stats to delete
    cursor.execute("""
        SELECT COUNT(*)
        FROM player_comprehensive_stats
        WHERE session_id IN (
            SELECT id FROM sessions
            WHERE session_date LIKE '2025-10-28%' OR session_date LIKE '2025-10-30%'
        )
    """)
    
    player_count = cursor.fetchone()[0]
    print(f"Will delete {player_count} existing player stat records")
    print(f"Will re-import {len(sessions)} session files")
    
    input("\nPress ENTER to continue or CTRL+C to cancel...")
    
    # Delete existing sessions (will cascade delete player stats)
    print("\n" + "=" * 80)
    print("Step 1: Deleting existing sessions and player stats...")
    print("=" * 80)
    
    # First delete player stats (no foreign key on delete cascade)
    cursor.execute("""
        DELETE FROM player_comprehensive_stats
        WHERE session_id IN (
            SELECT id FROM sessions
            WHERE session_date LIKE '2025-10-28%' OR session_date LIKE '2025-10-30%'
        )
    """)
    player_deleted = cursor.rowcount
    print(f"✅ Deleted {player_deleted} player stat records")
    
    # Then delete sessions
    cursor.execute("""
        DELETE FROM sessions
        WHERE session_date LIKE '2025-10-28%' OR session_date LIKE '2025-10-30%'
    """)
    session_deleted = cursor.rowcount
    print(f"✅ Deleted {session_deleted} session records")
    
    conn.commit()
    
    conn.close()
    
    # Re-import sessions using the bot
    print("\n" + "=" * 80)
    print("Step 2: Re-importing sessions with fixed mappings...")
    print("=" * 80)
    
    # Create bot instance (we need it for the import methods)
    bot = UltimateETLegacyBot()
    
    success_count = 0
    fail_count = 0
    
    for session_id, session_date, map_name, round_num in sessions:
        filename = f"{session_date}-{map_name}-round-{round_num}.txt"
        file_path = Path('local_stats') / filename
        
        if not file_path.exists():
            print(f"❌ File not found: {filename}")
            fail_count += 1
            continue
        
        try:
            # Import the session using bot's process method
            result = await bot.process_gamestats_file(str(file_path), filename)
            
            if result:
                print(f"✅ {filename}")
                success_count += 1
            else:
                print(f"⚠️  {filename} (process returned None)")
                fail_count += 1
                
        except Exception as e:
            print(f"❌ {filename}: {e}")
            fail_count += 1
    
    print("\n" + "=" * 80)
    print("BACKFILL COMPLETE")
    print("=" * 80)
    print(f"✅ Successfully re-imported: {success_count}")
    print(f"❌ Failed: {fail_count}")
    
    # Verify the fixes
    print("\n" + "=" * 80)
    print("Step 3: Verifying fixes...")
    print("=" * 80)
    
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    # Check a specific session we know had issues
    cursor.execute("""
        SELECT 
            player_name,
            team_damage_given,
            team_damage_received,
            headshot_kills,
            most_useful_kills,
            double_kills
        FROM player_comprehensive_stats
        WHERE session_id = (
            SELECT id FROM sessions 
            WHERE session_date = '2025-10-28-212120' 
            AND map_name = 'etl_adlernest'
            AND round_number = 1
        )
        AND player_name LIKE '%SuperBoyy%'
    """)
    
    row = cursor.fetchone()
    
    if row:
        player_name, tdg, tdr, hs, useful, double = row
        print(f"\nSample verification (SuperBoyy from 2025-10-28-212120):")
        print(f"  Player: {player_name}")
        print(f"  team_damage_given: {tdg} (expected 85)")
        print(f"  team_damage_received: {tdr} (expected 18)")
        print(f"  headshot_kills: {hs} (expected 4)")
        print(f"  most_useful_kills: {useful} (expected 2)")
        print(f"  double_kills: {double} (expected 2)")
        
        if tdg == 85 and tdr == 18 and hs == 4 and useful == 2 and double == 2:
            print("\n🎉 VERIFICATION PASSED! All fields correct!")
        else:
            print("\n⚠️  Some fields don't match expected values")
    else:
        print("\n⚠️  Could not find SuperBoyy in test session")
    
    # Get overall stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN team_damage_given > 0 THEN 1 ELSE 0 END) as has_tdg,
            SUM(CASE WHEN headshot_kills > 0 THEN 1 ELSE 0 END) as has_hs,
            SUM(CASE WHEN most_useful_kills > 0 THEN 1 ELSE 0 END) as has_useful,
            SUM(CASE WHEN double_kills > 0 THEN 1 ELSE 0 END) as has_double
        FROM player_comprehensive_stats
        WHERE session_id IN (
            SELECT id FROM sessions
            WHERE session_date LIKE '2025-10-28%' OR session_date LIKE '2025-10-30%'
        )
    """)
    
    total, has_tdg, has_hs, has_useful, has_double = cursor.fetchone()
    
    if total and total > 0:
        print(f"\nOverall statistics ({total} player records):")
        print(f"  Players with team_damage_given > 0: {has_tdg} "
              f"({has_tdg/total*100:.1f}%)")
        print(f"  Players with headshot_kills > 0: {has_hs} "
              f"({has_hs/total*100:.1f}%)")
        print(f"  Players with most_useful_kills > 0: {has_useful} "
              f"({has_useful/total*100:.1f}%)")
        print(f"  Players with double_kills > 0: {has_double} "
              f"({has_double/total*100:.1f}%)")
    else:
        print(f"\n⚠️  No player records found after backfill!")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Backfill complete! Database updated with correct field values.")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(backfill_sessions())
