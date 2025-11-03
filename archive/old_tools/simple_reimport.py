"""
Simple re-import using existing backfill_weapon_stats.py pattern
"""
import sqlite3
import sys
from pathlib import Path

# Add bot directory
sys.path.insert(0, str(Path(__file__).parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser
import aiosqlite
import asyncio


async def reimport_sessions():
    """Delete and re-import Oct 28 & 30"""
    
    # Get sessions list
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, session_date, map_name, round_number
        FROM sessions
        WHERE session_date LIKE '2025-10-28%' OR session_date LIKE '2025-10-30%'
        ORDER BY session_date, map_name, round_number
    """)
    
    sessions = cursor.fetchall()
    print(f"Found {len(sessions)} sessions")
    
    response = input(f"Delete and re-import {len(sessions)} sessions? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted")
        return
    
    # Delete
    print("\nDeleting...")
    session_ids = [s[0] for s in sessions]
    placeholders = ','.join(['?'] * len(session_ids))
    
    cursor.execute(f"DELETE FROM weapon_comprehensive_stats WHERE session_id IN ({placeholders})", session_ids)
    print(f"  Deleted {cursor.rowcount} weapon rows")
    
    cursor.execute(f"DELETE FROM player_comprehensive_stats WHERE session_id IN ({placeholders})", session_ids)
    print(f"  Deleted {cursor.rowcount} player rows")
    
    cursor.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", session_ids)
    print(f"  Deleted {cursor.rowcount} session rows")
    
    conn.commit()
    conn.close()
    
    # Re-import
    print("\nRe-importing...")
    parser = C0RNP0RN3StatsParser()
    db = await aiosqlite.connect('bot/etlegacy_production.db')
    
    reimported = 0
    for _, session_date, map_name, round_num in sessions:
        filename = f"{session_date}-{map_name}-round-{round_num}.txt"
        filepath = Path('local_stats') / filename
        
        if not filepath.exists():
            print(f"❌ {filename} - file not found")
            continue
        
        # Parse
        result = parser.parse_stats_file(str(filepath))
        if not result or 'players' not in result:
            print(f"❌ {filename} - parse failed")
            continue
        
        # Insert session
        await db.execute("""
            INSERT INTO sessions (
                session_date, map_name, round_number, defender_team, winner_team,
                original_time_limit, time_to_beat, completion_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_date,
            map_name,
            round_num,
            result.get('defender_team', 0),
            result.get('winner_team', 0),
            result.get('original_time_limit', ''),
            result.get('time_to_beat', ''),
            result.get('completion_time', ''),
        ))
        
        session_id = (await db.execute("SELECT last_insert_rowid()")).fetchone()[0]
        
        # Insert players using FIXED code
        for player in result.get('players', []):
            obj_stats = player.get('objective_stats', {})
            
            await db.execute("""
                INSERT INTO player_comprehensive_stats (
                    session_id, session_date, map_name, round_number,
                    player_guid, player_name, clean_name, team,
                    kills, deaths, damage_given, damage_received,
                    team_damage_given, team_damage_received,
                    gibs, self_kills, team_kills, team_gibs, headshot_kills,
                    time_played_seconds, time_played_minutes,
                    xp, kd_ratio, dpm, bullets_fired,
                    most_useful_kills, useless_kills, constructions,
                    double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                    killing_spree_best, death_spree_worst
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, session_date, map_name, round_num,
                player.get('guid', ''), player.get('name', ''), player.get('name', ''), player.get('team', 0),
                player.get('kills', 0), player.get('deaths', 0),
                player.get('damage_given', 0), player.get('damage_received', 0),
                obj_stats.get('team_damage_given', 0),  # ✅ FIXED
                obj_stats.get('team_damage_received', 0),  # ✅ FIXED
                obj_stats.get('gibs', 0), obj_stats.get('self_kills', 0),
                obj_stats.get('team_kills', 0), obj_stats.get('team_gibs', 0),
                obj_stats.get('headshot_kills', 0),  # ✅ FIXED
                player.get('time_played_seconds', 0), player.get('time_played_seconds', 0) / 60.0,
                obj_stats.get('xp', 0),
                player.get('kd_ratio', 0), player.get('dpm', 0),
                obj_stats.get('bullets_fired', 0),
                obj_stats.get('useful_kills', 0),  # ✅ FIXED
                obj_stats.get('useless_kills', 0),
                obj_stats.get('repairs_constructions', 0),  # ✅ FIXED
                obj_stats.get('multikill_2x', 0),  # ✅ FIXED
                obj_stats.get('multikill_3x', 0),  # ✅ FIXED
                obj_stats.get('multikill_4x', 0),  # ✅ FIXED
                obj_stats.get('multikill_5x', 0),  # ✅ FIXED
                obj_stats.get('multikill_6x', 0),  # ✅ FIXED
                obj_stats.get('killing_spree', 0),
                obj_stats.get('death_spree', 0),
            ))
        
        await db.commit()
        print(f"✅ {filename}")
        reimported += 1
    
    await db.close()
    print(f"\n✅ Done! Re-imported {reimported}/{len(sessions)}")
    
    # Verify
    print("\nVerifying SuperBoyy...")
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT team_damage_given, team_damage_received, headshot_kills, most_useful_kills, double_kills
        FROM player_comprehensive_stats
        WHERE session_date LIKE '2025-10-28-212120%' AND player_name LIKE '%SuperBoyy%'
    """)
    row = cursor.fetchone()
    if row:
        print(f"  team_damage_given: {row[0]} (expected 85)")
        print(f"  team_damage_received: {row[1]} (expected 18)")
        print(f"  headshot_kills: {row[2]} (expected 4)")
        print(f"  most_useful_kills: {row[3]} (expected 2)")
        print(f"  double_kills: {row[4]} (expected 2)")
        if row[0] == 85 and row[1] == 18 and row[2] == 4 and row[3] == 2 and row[4] == 2:
            print("\n🎉 ALL FIXED!")
    conn.close()


if __name__ == '__main__':
    asyncio.run(reimport_sessions())
