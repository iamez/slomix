#!/usr/bin/env python3
"""
Diagnostic script to understand time calculation issues in round_number=0
We need to figure out:
1. Is R0 time = R1 time only? R2 time only? Something else?
2. What should we use for accurate DPM calculation?
"""

import asyncio
import asyncpg

async def main():
    # Connect to PostgreSQL
    conn = await asyncpg.connect(
        host='192.168.64.116',
        port=5432,
        user='etlegacy_user',
        password='etlegacy_secure_2025',
        database='etlegacy'
    )
    
    print("=" * 80)
    print("TIME CALCULATION DIAGNOSTIC - Understanding Round 0 vs R1+R2")
    print("=" * 80)
    
    # Get latest gaming session
    gaming_session_id = await conn.fetchval("""
        SELECT gaming_session_id 
        FROM rounds 
        WHERE gaming_session_id IS NOT NULL 
        ORDER BY round_date DESC, round_time DESC 
        LIMIT 1
    """)
    
    print(f"\nAnalyzing gaming_session_id: {gaming_session_id}")
    print("-" * 80)
    
    # Get a few sample matches to analyze
    matches = await conn.fetch("""
        SELECT DISTINCT map_name, 
               MIN(id) as first_round_id,
               STRING_AGG(CAST(id AS TEXT), ',' ORDER BY round_number) as round_ids
        FROM rounds
        WHERE gaming_session_id = $1
        GROUP BY map_name
        ORDER BY MIN(id)
        LIMIT 3
    """, gaming_session_id)
    
    for match in matches:
        map_name = match['map_name']
        round_ids = match['round_ids'].split(',')
        
        print(f"\n📍 MAP: {map_name}")
        print(f"   Round IDs: {round_ids}")
        print("-" * 60)
        
        # Get time details for each round
        for round_id in round_ids:
            round_data = await conn.fetchrow("""
                SELECT round_number, actual_time
                FROM rounds
                WHERE id = $1
            """, int(round_id))
            
            # Get player times for this round
            player_times = await conn.fetch("""
                SELECT player_name,
                       time_played_seconds,
                       time_played_minutes,
                       time_dead_minutes,
                       time_dead_ratio,
                       denied_playtime
                FROM player_comprehensive_stats
                WHERE round_id = $1
                ORDER BY player_name
                LIMIT 3
            """, int(round_id))
            
            print(f"\n   Round {round_data['round_number']} (ID: {round_id})")
            print(f"   Actual time: {round_data['actual_time']}s")
            print("   Player times:")
            
            for pt in player_times:
                print(f"     {pt['player_name']:<15} play: {pt['time_played_seconds']}s ({pt['time_played_minutes']:.1f}m)")
                print(f"     {'':15} dead: {pt['time_dead_minutes']:.1f}m ({pt['time_dead_ratio']:.1f}%)")
                print(f"     {'':15} denied: {pt['denied_playtime']}s")
        
        # Now compare aggregated times
        print(f"\n   📊 AGGREGATED COMPARISON FOR {map_name}:")
        
        # Get R0 aggregate
        r0_stats = await conn.fetchrow("""
            SELECT SUM(time_played_seconds) as total_play,
                   SUM(time_dead_minutes * 60) as total_dead,
                   SUM(denied_playtime) as total_denied,
                   SUM(damage_given) as total_damage,
                   COUNT(DISTINCT player_guid) as player_count
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE r.gaming_session_id = $1 
              AND r.map_name = $2
              AND r.round_number = 0
        """, gaming_session_id, map_name)
        
        # Get R1 aggregate
        r1_stats = await conn.fetchrow("""
            SELECT SUM(time_played_seconds) as total_play,
                   SUM(time_dead_minutes * 60) as total_dead,
                   SUM(denied_playtime) as total_denied,
                   SUM(damage_given) as total_damage
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE r.gaming_session_id = $1 
              AND r.map_name = $2
              AND r.round_number = 1
        """, gaming_session_id, map_name)
        
        # Get R2 aggregate
        r2_stats = await conn.fetchrow("""
            SELECT SUM(time_played_seconds) as total_play,
                   SUM(time_dead_minutes * 60) as total_dead,
                   SUM(denied_playtime) as total_denied,
                   SUM(damage_given) as total_damage
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE r.gaming_session_id = $1 
              AND r.map_name = $2
              AND r.round_number = 2
        """, gaming_session_id, map_name)
        
        if r0_stats and r1_stats and r2_stats:
            print(f"\n   Round 0 totals: {r0_stats['total_play']}s play, {r0_stats['total_damage']} dmg")
            print(f"   Round 1 totals: {r1_stats['total_play']}s play, {r1_stats['total_damage']} dmg")
            print(f"   Round 2 totals: {r2_stats['total_play']}s play, {r2_stats['total_damage']} dmg")
            print(f"   R1+R2 combined: {r1_stats['total_play'] + r2_stats['total_play']}s play, {r1_stats['total_damage'] + r2_stats['total_damage']} dmg")
            
            # Check relationships
            print("\n   🔍 RELATIONSHIPS:")
            print(f"   R0 time == R1 time? {r0_stats['total_play'] == r1_stats['total_play']}")
            print(f"   R0 time == R2 time? {r0_stats['total_play'] == r2_stats['total_play']}")
            print(f"   R0 time == R1+R2? {r0_stats['total_play'] == r1_stats['total_play'] + r2_stats['total_play']}")
            print(f"   R0 time == average(R1,R2)? {abs(r0_stats['total_play'] - (r1_stats['total_play'] + r2_stats['total_play'])/2) < 100}")
            
            print(f"\n   R0 damage == R1 damage? {r0_stats['total_damage'] == r1_stats['total_damage']}")
            print(f"   R0 damage == R2 damage? {r0_stats['total_damage'] == r2_stats['total_damage']}")
            print(f"   R0 damage == R1+R2? {r0_stats['total_damage'] == r1_stats['total_damage'] + r2_stats['total_damage']}")
            
            # Calculate DPMs
            if r0_stats['total_play'] > 0:
                dpm_r0 = (r0_stats['total_damage'] * 60) / r0_stats['total_play']
                print(f"\n   DPM using R0 time: {dpm_r0:.1f}")
            
            r12_time = r1_stats['total_play'] + r2_stats['total_play']
            if r12_time > 0:
                dpm_r12 = (r0_stats['total_damage'] * 60) / r12_time
                print(f"   DPM using R1+R2 time: {dpm_r12:.1f}")
            
            if r1_stats['total_play'] > 0:
                dpm_r1_only = (r1_stats['total_damage'] * 60) / r1_stats['total_play']
                print(f"   DPM using R1 only: {dpm_r1_only:.1f}")
    
    print("\n" + "=" * 80)
    print("CONCLUSIONS:")
    print("-" * 80)
    
    # Get overall session stats
    session_stats = await conn.fetchrow("""
        SELECT 
            COUNT(DISTINCT CASE WHEN round_number = 0 THEN id END) as r0_count,
            COUNT(DISTINCT CASE WHEN round_number = 1 THEN id END) as r1_count,
            COUNT(DISTINCT CASE WHEN round_number = 2 THEN id END) as r2_count
        FROM rounds
        WHERE gaming_session_id = $1
    """, gaming_session_id)
    
    print(f"Session has {session_stats['r0_count']} R0, {session_stats['r1_count']} R1, {session_stats['r2_count']} R2 rounds")
    
    # Final recommendation
    print("\n📌 RECOMMENDATION:")
    print("Based on the data above, we can determine the correct approach for DPM calculation.")
    print("Look for patterns in the RELATIONSHIPS section to understand how R0 time is stored.")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
