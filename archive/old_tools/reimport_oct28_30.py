"""
Re-import Oct 28 & 30 sessions with fixed field mappings

This script will:
1. Identify all sessions from Oct 28 & 30
2. Delete them from the database (sessions + player_comprehensive_stats + weapon_comprehensive_stats)
3. Re-import using the bot's fixed import code
"""
import sqlite3
import asyncio
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))

async def reimport_sessions():
    """Re-import affected sessions"""
    
    # Step 1: Get list of sessions to re-import
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, session_date, map_name, round_number
        FROM sessions
        WHERE session_date LIKE '2025-10-28%' OR session_date LIKE '2025-10-30%'
        ORDER BY session_date, map_name, round_number
    """)
    
    sessions = cursor.fetchall()
    print(f"Found {len(sessions)} sessions to re-import")
    print("=" * 80)
    
    # List them
    for session_id, session_date, map_name, round_num in sessions:
        print(f"  {session_date} {map_name} R{round_num} (ID: {session_id})")
    
    print("=" * 80)
    print(f"\nThis will DELETE and RE-IMPORT {len(sessions)} sessions")
    response = input("Continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Aborted.")
        conn.close()
        return
    
    # Step 2: Delete sessions and related data
    print("\nDeleting old data...")
    
    session_ids = [s[0] for s in sessions]
    placeholders = ','.join(['?'] * len(session_ids))
    
    # Delete weapon stats first (foreign key)
    cursor.execute(f"""
        DELETE FROM weapon_comprehensive_stats
        WHERE session_id IN ({placeholders})
    """, session_ids)
    weapon_deleted = cursor.rowcount
    print(f"  Deleted {weapon_deleted} weapon stat rows")
    
    # Delete player stats
    cursor.execute(f"""
        DELETE FROM player_comprehensive_stats
        WHERE session_id IN ({placeholders})
    """, session_ids)
    player_deleted = cursor.rowcount
    print(f"  Deleted {player_deleted} player stat rows")
    
    # Delete sessions
    cursor.execute(f"""
        DELETE FROM sessions
        WHERE id IN ({placeholders})
    """, session_ids)
    session_deleted = cursor.rowcount
    print(f"  Deleted {session_deleted} session rows")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Deletion complete!")
    print("=" * 80)
    
    # Step 3: Re-import using the bot
    print("\nRe-importing sessions with fixed code...")
    print("=" * 80)
    
    # Import the bot
    from ultimate_bot import UltimateETLegacyBot
    
    # Create bot instance
    bot = UltimateETLegacyBot()
    
    # Re-import each stat file
    reimported = 0
    failed = 0
    
    for session_id, session_date, map_name, round_num in sessions:
        filename = f"{session_date}-{map_name}-round-{round_num}.txt"
        file_path = Path('local_stats') / filename
        
        if not file_path.exists():
            print(f"❌ File not found: {filename}")
            failed += 1
            continue
        
        try:
            # Import the file using bot's method
            await bot.process_gamestats_file(str(file_path), filename)
            print(f"✅ {filename}")
            reimported += 1
        except Exception as e:
            print(f"❌ Failed to import {filename}: {e}")
            failed += 1
    
    print("=" * 80)
    print(f"\n✅ Re-import complete!")
    print(f"   Successfully imported: {reimported}")
    print(f"   Failed: {failed}")
    print(f"   Total: {len(sessions)}")
    
    # Step 4: Verify the fixes
    print("\n" + "=" * 80)
    print("VERIFICATION - Checking SuperBoyy from first session")
    print("=" * 80)
    
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            team_damage_given,
            team_damage_received,
            headshot_kills,
            most_useful_kills,
            double_kills,
            constructions
        FROM player_comprehensive_stats
        WHERE session_date LIKE '2025-10-28-212120%'
          AND player_name LIKE '%SuperBoyy%'
    """)
    
    row = cursor.fetchone()
    if row:
        print(f"team_damage_given: {row[0]} (expected 85)")
        print(f"team_damage_received: {row[1]} (expected 18)")
        print(f"headshot_kills: {row[2]} (expected 4)")
        print(f"most_useful_kills: {row[3]} (expected 2)")
        print(f"double_kills: {row[4]} (expected 2)")
        print(f"constructions: {row[5]} (expected 0)")
        
        if row[0] == 85 and row[1] == 18 and row[2] == 4 and row[3] == 2 and row[4] == 2:
            print("\n🎉 ALL CHECKS PASSED! Fixes are working!")
        else:
            print("\n⚠️  Some values don't match - please review")
    else:
        print("⚠️  Could not find SuperBoyy in re-imported data")
    
    conn.close()

if __name__ == '__main__':
    asyncio.run(reimport_sessions())
