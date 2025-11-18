#!/usr/bin/env python3
"""
Deep dive into sw_goldrush_te match from Session 19
User says: R2 was a surrender, both rounds show 12:00 (720s)
Let's see what really happened.
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
    
    print("=" * 90)
    print("🔍 DEEP DIVE: sw_goldrush_te Match (Session 19)")
    print("=" * 90)
    
    # Get all 3 rounds for this map
    rounds = await conn.fetch("""
        SELECT id, round_number, actual_time, time_limit, round_outcome, winner_team
        FROM rounds
        WHERE gaming_session_id = 19 AND map_name = 'sw_goldrush_te'
        ORDER BY round_number
    """)
    
    print("\n📋 ROUNDS TABLE DATA:")
    print("-" * 90)
    
    round_ids = {}
    for r in rounds:
        rnum = r['round_number']
        round_ids[rnum] = r['id']
        
        # Parse time
        atime_str = r['actual_time'] if r['actual_time'] else '0:00'
        if ':' in atime_str:
            parts = atime_str.split(':')
            atime = int(parts[0]) * 60 + int(parts[1])
        else:
            atime = int(atime_str) if atime_str else 0
        
        tlimit = r['time_limit'] if r['time_limit'] else 'Unknown'
        outcome = r['round_outcome'] if r['round_outcome'] else 'Unknown'
        winner = r['winner_team'] if r['winner_team'] else 'Unknown'
        
        emoji = "🎯" if rnum == 0 else "1️⃣" if rnum == 1 else "2️⃣"
        print(f"{emoji} Round {rnum} (ID {r['id']})")
        print(f"   actual_time:  {atime}s ({atime/60:.1f}min) [{atime_str}]")
        print(f"   time_limit:   {tlimit}")
        print(f"   outcome:      {outcome}")
        print(f"   winner_team:  {winner}")
        print()
    
    # Get player stats for each round
    print("=" * 90)
    print("👤 PLAYER STATS PER ROUND:")
    print("=" * 90)
    
    for rnum in [0, 1, 2]:
        if rnum not in round_ids:
            continue
        
        rid = round_ids[rnum]
        emoji = "🎯" if rnum == 0 else "1️⃣" if rnum == 1 else "2️⃣"
        
        print(f"\n{emoji} ROUND {rnum} (ID {rid}):")
        print("-" * 90)
        
        players = await conn.fetch("""
            SELECT 
                player_name,
                time_played_seconds,
                kills,
                deaths,
                damage_given
            FROM player_comprehensive_stats
            WHERE round_id = $1
            ORDER BY kills DESC
        """, rid)
        
        print(f"{'Player':<15} | {'Time Played':>12} | {'Kills':>6} | {'Deaths':>6} | {'Damage':>8}")
        print("-" * 90)
        
        for p in players:
            name = p['player_name']
            time_s = p['time_played_seconds']
            kills = p['kills']
            deaths = p['deaths']
            damage = p['damage_given']
            
            print(f"{name:<15} | {time_s:6,}s ({time_s/60:5.1f}m) | {kills:6} | {deaths:6} | {damage:8,}")
    
    # Compare R0 vs R1+R2
    print("\n" + "=" * 90)
    print("🔄 COMPARISON: R0 vs (R1 + R2)")
    print("=" * 90)
    
    # Get one player's stats across all rounds
    comparison = await conn.fetch("""
        SELECT 
            p.player_name,
            r.round_number,
            p.time_played_seconds,
            p.kills,
            p.deaths,
            p.damage_given
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = 19 
          AND r.map_name = 'sw_goldrush_te'
        ORDER BY p.player_name, r.round_number
        LIMIT 9
    """)
    
    # Group by player
    current_player = None
    p_r0 = p_r1 = p_r2 = None
    
    for row in comparison:
        pname = row['player_name']
        rnum = row['round_number']
        
        if current_player != pname:
            if current_player is not None and p_r0 and p_r1 and p_r2:
                # Print comparison for previous player
                print(f"\n👤 {current_player}")
                print(f"   Time:   R0={p_r0['time']:4d}s  R1={p_r1['time']:4d}s  R2={p_r2['time']:4d}s  R1+R2={p_r1['time']+p_r2['time']:4d}s")
                print(f"           R0==R1+R2? {p_r0['time']} == {p_r1['time']+p_r2['time']} {'✅' if p_r0['time']==(p_r1['time']+p_r2['time']) else '❌'}")
                print(f"   Kills:  R0={p_r0['kills']:3d}  R1={p_r1['kills']:3d}  R2={p_r2['kills']:3d}  R1+R2={p_r1['kills']+p_r2['kills']:3d}")
                print(f"           R0==R1+R2? {p_r0['kills']} == {p_r1['kills']+p_r2['kills']} {'✅' if p_r0['kills']==(p_r1['kills']+p_r2['kills']) else '❌'}")
                print(f"   Damage: R0={p_r0['dmg']:5,}  R1={p_r1['dmg']:5,}  R2={p_r2['dmg']:5,}  R1+R2={p_r1['dmg']+p_r2['dmg']:5,}")
                print(f"           R0==R1+R2? {p_r0['dmg']} == {p_r1['dmg']+p_r2['dmg']} {'✅' if p_r0['dmg']==(p_r1['dmg']+p_r2['dmg']) else '❌'}")
            
            current_player = pname
            p_r0 = p_r1 = p_r2 = None
        
        data = {
            'time': row['time_played_seconds'],
            'kills': row['kills'],
            'deaths': row['deaths'],
            'dmg': row['damage_given']
        }
        
        if rnum == 0:
            p_r0 = data
        elif rnum == 1:
            p_r1 = data
        elif rnum == 2:
            p_r2 = data
    
    # Print last player
    if current_player and p_r0 and p_r1 and p_r2:
        print(f"\n👤 {current_player}")
        print(f"   Time:   R0={p_r0['time']:4d}s  R1={p_r1['time']:4d}s  R2={p_r2['time']:4d}s  R1+R2={p_r1['time']+p_r2['time']:4d}s")
        print(f"           R0==R1+R2? {p_r0['time']} == {p_r1['time']+p_r2['time']} {'✅' if p_r0['time']==(p_r1['time']+p_r2['time']) else '❌'}")
        print(f"   Kills:  R0={p_r0['kills']:3d}  R1={p_r1['kills']:3d}  R2={p_r2['kills']:3d}  R1+R2={p_r1['kills']+p_r2['kills']:3d}")
        print(f"           R0==R1+R2? {p_r0['kills']} == {p_r1['kills']+p_r2['kills']} {'✅' if p_r0['kills']==(p_r1['kills']+p_r2['kills']) else '❌'}")
        print(f"   Damage: R0={p_r0['dmg']:5,}  R1={p_r1['dmg']:5,}  R2={p_r2['dmg']:5,}  R1+R2={p_r1['dmg']+p_r2['dmg']:5,}")
        print(f"           R0==R1+R2? {p_r0['dmg']} == {p_r1['dmg']+p_r2['dmg']} {'✅' if p_r0['dmg']==(p_r1['dmg']+p_r2['dmg']) else '❌'}")
    
    print("\n" + "=" * 90)
    print("📋 CONCLUSIONS:")
    print("=" * 90)
    print("This will show us:")
    print("  1. If R2 was really a surrender (should see low time/kills)")
    print("  2. Why all rounds show 12:00 (720s)")
    print("  3. Whether R0 time = R1 time, R2 time, or R1+R2 time for this match")
    print("  4. Whether R0 damage/kills are cumulative even when R2 is surrender")
    print("=" * 90)
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
