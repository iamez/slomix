"""
Quick script to check what rounds are in the last gaming session
Uses direct PostgreSQL connection
"""
import asyncio
import asyncpg

async def main():
    # Connect to PostgreSQL
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='etlegacy_user',
        password='etlegacy_secure_2025',
        database='etlegacy'
    )
    
    # Get latest gaming session ID
    result = await conn.fetchrow(
        """
        SELECT gaming_session_id 
        FROM rounds 
        WHERE gaming_session_id IS NOT NULL 
        ORDER BY round_date DESC, round_time DESC 
        LIMIT 1
        """
    )
    
    if not result:
        print("No sessions found")
        return
    
    session_id = result['gaming_session_id']
    print(f"Latest gaming_session_id: {session_id}")
    print()
    
    # Count rounds by type
    rounds = await conn.fetch(
        """
        SELECT round_number, COUNT(*) as cnt 
        FROM rounds 
        WHERE gaming_session_id = $1 
        GROUP BY round_number
        ORDER BY round_number
        """,
        session_id
    )
    
    print("Round counts:")
    for row in rounds:
        print(f"  Round {row['round_number']}: {row['cnt']} entries")
    print()
    
    # Get all round details
    all_rounds = await conn.fetch(
        """
        SELECT id, map_name, round_number, round_date, round_time 
        FROM rounds 
        WHERE gaming_session_id = $1 
        ORDER BY round_date, round_time, round_number
        """,
        session_id
    )
    
    print(f"All rounds (total {len(all_rounds)}):")
    for row in all_rounds:
        print(f"  ID {row['id']}: {row['map_name']:20s} R{row['round_number']}  {row['round_date']} {row['round_time']}")
    print()
    
    # Check player stats for one player across round types
    player_stats = await conn.fetch(
        """
        SELECT r.round_number, p.player_name, p.kills, p.deaths, p.damage_given
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = $1
          AND p.player_name = (
              SELECT player_name FROM player_comprehensive_stats 
              WHERE round_id IN (SELECT id FROM rounds WHERE gaming_session_id = $1)
              LIMIT 1
          )
        ORDER BY r.round_date, r.round_time, r.round_number
        """,
        session_id
    )
    
    if player_stats:
        print(f"Sample player stats ({player_stats[0]['player_name']}):")
        for row in player_stats:
            print(f"  Round {row['round_number']}: {row['kills']} kills, {row['deaths']} deaths, {row['damage_given']} damage")
    print()
    
    # Check for duplicate players in round_number=0
    duplicates = await conn.fetch(
        """
        SELECT p.player_name, r.id as round_id, r.map_name, COUNT(*) as cnt
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = $1
          AND r.round_number = 0
        GROUP BY p.player_name, r.id, r.map_name
        HAVING COUNT(*) > 1
        """,
        session_id
    )
    
    if duplicates:
        print("⚠️  DUPLICATE PLAYERS FOUND IN ROUND 0:")
        for row in duplicates:
            print(f"  {row['player_name']} in {row['map_name']} (round {row['round_id']}): {row['cnt']} entries")
    else:
        print("✅ No duplicate players in round_number=0")
    print()
    
    # Check total stats when querying round_number=0 only
    total_r0 = await conn.fetchrow(
        """
        SELECT p.player_name,
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_seconds) as total_time
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = $1
          AND r.round_number = 0
          AND p.player_name = $2
        GROUP BY p.player_name
        """,
        session_id, player_stats[0]['player_name'] if player_stats else '.wjs'
    )
    
    if total_r0:
        print(f"Total stats for {total_r0['player_name']} (round_number=0 only, with SUM):")
        print(f"  {total_r0['total_kills']} kills, {total_r0['total_deaths']} deaths, {total_r0['total_damage']} damage")
        print(f"  {total_r0['total_time']} seconds = {total_r0['total_time']//60}:{total_r0['total_time']%60:02d}")
        dpm = (total_r0['total_damage'] * 60.0) / total_r0['total_time'] if total_r0['total_time'] > 0 else 0
        print(f"  Calculated DPM: {dpm:.1f}")
    print()
    
    # Check ONE SINGLE MATCH to see R0 vs R1+R2 time
    print("Checking FIRST MATCH time values (etl_adlernest):")
    first_match = await conn.fetch(
        """
        SELECT r.round_number, p.player_name, p.time_played_seconds, p.damage_given
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = $1
          AND r.map_name = 'etl_adlernest'
          AND p.player_name = $2
        ORDER BY r.round_number
        """,
        session_id, player_stats[0]['player_name'] if player_stats else '.wjs'
    )
    
    for row in first_match:
        print(f"  Round {row['round_number']}: {row['time_played_seconds']}s ({row['time_played_seconds']//60}:{row['time_played_seconds']%60:02d}), {row['damage_given']} damage")
    
    if len(first_match) >= 2:
        r1_time = next((r['time_played_seconds'] for r in first_match if r['round_number'] == 1), 0)
        r2_time = next((r['time_played_seconds'] for r in first_match if r['round_number'] == 2), 0)
        r0_time = next((r['time_played_seconds'] for r in first_match if r['round_number'] == 0), 0)
        print(f"  R1+R2 time: {r1_time + r2_time}s vs R0 time: {r0_time}s")
        print(f"  Difference: {abs((r1_time + r2_time) - r0_time)}s")
    print()
    
    # Compare to ALL rounds (R0+R1+R2)
    total_all = await conn.fetchrow(
        """
        SELECT p.player_name,
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_seconds) as total_time
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = $1
          AND p.player_name = $2
        GROUP BY p.player_name
        """,
        session_id, player_stats[0]['player_name'] if player_stats else '.wjs'
    )
    
    if total_all:
        print(f"Total stats for {total_all['player_name']} (ALL rounds R0+R1+R2, with SUM):")
        print(f"  {total_all['total_kills']} kills, {total_all['total_deaths']} deaths, {total_all['total_damage']} damage")
        print(f"  {total_all['total_time']} seconds = {total_all['total_time']//60}:{total_all['total_time']%60:02d}")
        dpm_all = (total_all['total_damage'] * 60.0) / total_all['total_time'] if total_all['total_time'] > 0 else 0
        print(f"  Calculated DPM: {dpm_all:.1f}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
