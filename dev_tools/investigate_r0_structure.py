#!/usr/bin/env python3
"""
INVESTIGATE: What does Round 0 actually contain?

We know from validation:
- R0 player stats: damage is cumulative (R1+R2)
- R0 player stats: time_played_seconds is WRONG (only R1 time)

But what about:
- R0 rounds table: actual_time field?
- Does R0 actual_time = R1+R2 actual_time?
- Or does R0 actual_time = only one round's time?

This will tell us if we can use R0 as reference or not.
"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        host='localhost',
        database='etlegacy',
        user='etlegacy_user',
        password='etlegacy_secure_2025'
    )
    
    print("=" * 80)
    print("🔬 INVESTIGATING Round 0 Data Structure")
    print("=" * 80)
    
    # Get a few matches with all 3 rounds (R0, R1, R2)
    print("\n📊 Checking 5 recent complete matches (R0 + R1 + R2)...")
    print("-" * 80)
    
    matches = await conn.fetch("""
        SELECT r.gaming_session_id, r.map_name, r.round_date, r.round_time
        FROM rounds r
        WHERE r.round_number = 0
        ORDER BY r.round_date DESC, r.round_time DESC
        LIMIT 5
    """)
    
    for i, match in enumerate(matches, 1):
        session_id = match['gaming_session_id']
        map_name = match['map_name']
        
        print(f"\n{'='*80}")
        print(f"🎮 Match {i}: {map_name} (Session {session_id})")
        print(f"{'='*80}")
        
        # Get all 3 rounds for this match
        rounds = await conn.fetch("""
            SELECT round_number, actual_time, time_limit
            FROM rounds
            WHERE gaming_session_id = $1 AND map_name = $2
            ORDER BY round_number
            LIMIT 3
        """, session_id, map_name)
        
        r0_time = r1_time = r2_time = 0
        
        print("\n📋 ROUNDS TABLE - actual_time field:")
        for r in rounds:
            rnum = r['round_number']
            
            # Convert MM:SS format to seconds
            atime_str = r['actual_time'] if r['actual_time'] else '0:00'
            if ':' in atime_str:
                parts = atime_str.split(':')
                atime = int(parts[0]) * 60 + int(parts[1])
            else:
                atime = int(atime_str) if atime_str else 0
            
            tlimit_str = r['time_limit'] if r['time_limit'] else '0'
            tlimit = int(tlimit_str) if tlimit_str.isdigit() else 0
            
            emoji = "🎯" if rnum == 0 else "1️⃣" if rnum == 1 else "2️⃣"
            print(f"  {emoji} R{rnum}: actual_time = {atime:4d}s ({atime/60:5.1f}min) [{atime_str}]")
            
            if rnum == 0:
                r0_time = atime
            elif rnum == 1:
                r1_time = atime
            elif rnum == 2:
                r2_time = atime
        
        # Check relationships
        print("\n🔍 RELATIONSHIP CHECKS:")
        print(f"  R0 == R1?        {r0_time:4d} == {r1_time:4d}  {'✅ YES' if r0_time == r1_time else '❌ NO'}")
        print(f"  R0 == R2?        {r0_time:4d} == {r2_time:4d}  {'✅ YES' if r0_time == r2_time else '❌ NO'}")
        print(f"  R0 == R1+R2?     {r0_time:4d} == {r1_time+r2_time:4d}  {'✅ YES' if r0_time == (r1_time+r2_time) else '❌ NO'}")
        print(f"  R0 == max(R1,R2)? {r0_time:4d} == {max(r1_time,r2_time):4d}  {'✅ YES' if r0_time == max(r1_time, r2_time) else '❌ NO'}")
        
        # Now check player time_played_seconds
        print("\n👤 PLAYER STATS - time_played_seconds (first player):")
        
        player_times = await conn.fetch("""
            SELECT 
                p.player_name,
                r.round_number,
                p.time_played_seconds
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE r.gaming_session_id = $1 AND r.map_name = $2
            ORDER BY p.player_name, r.round_number
            LIMIT 3
        """, session_id, map_name)
        
        if player_times:
            current_player = None
            p_r0 = p_r1 = p_r2 = 0
            
            for pt in player_times:
                pname = pt['player_name']
                rnum = pt['round_number']
                ptime = pt['time_played_seconds']
                
                if current_player is None:
                    current_player = pname
                    print(f"  Player: {pname}")
                
                if pname == current_player:
                    emoji = "🎯" if rnum == 0 else "1️⃣" if rnum == 1 else "2️⃣"
                    print(f"    {emoji} R{rnum}: {ptime:4d}s")
                    
                    if rnum == 0:
                        p_r0 = ptime
                    elif rnum == 1:
                        p_r1 = ptime
                    elif rnum == 2:
                        p_r2 = ptime
            
            print("\n  🔍 Player Time Relationships:")
            print(f"    R0 == R1?        {p_r0:4d} == {p_r1:4d}  {'✅ YES' if p_r0 == p_r1 else '❌ NO'}")
            print(f"    R0 == R2?        {p_r0:4d} == {p_r2:4d}  {'✅ YES' if p_r0 == p_r2 else '❌ NO'}")
            print(f"    R0 == R1+R2?     {p_r0:4d} == {p_r1+p_r2:4d}  {'✅ YES' if p_r0 == (p_r1+p_r2) else '❌ NO'}")
    
    print("\n" + "=" * 80)
    print("📋 CONCLUSIONS")
    print("=" * 80)
    print("This will tell us:")
    print("  1. What does R0.actual_time contain? (R1? R2? R1+R2? max?)")
    print("  2. What does R0.player.time_played_seconds contain?")
    print("  3. Can we use R0 as a reference or must we always use R1+R2?")
    print("=" * 80)
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
