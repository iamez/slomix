"""Check what data exists for the last gaming session"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='etlegacy_user',
        password='etlegacy_secure_2025',
        database='etlegacy'
    )
    
    print("\n🔍 Checking Last Gaming Session Data\n")
    print("="*70)
    
    # Get the most recent gaming_session_id
    result = await conn.fetchrow("""
        SELECT gaming_session_id
        FROM rounds
        WHERE gaming_session_id IS NOT NULL
        ORDER BY round_date DESC, round_time DESC
        LIMIT 1
    """)
    
    if not result:
        print("❌ No gaming sessions found!")
        await conn.close()
        return
    
    latest_gaming_session_id = result['gaming_session_id']
    print(f"📊 Latest gaming_session_id: {latest_gaming_session_id}\n")
    
    # Get all rounds for this gaming session
    rounds = await conn.fetch("""
        SELECT 
            id,
            round_date,
            round_time,
            map_name,
            round_number,
            gaming_session_id
        FROM rounds
        WHERE gaming_session_id = $1
        ORDER BY round_date, round_time
    """, latest_gaming_session_id)
    
    print(f"📁 This session has {len(rounds)} rounds:\n")
    for r in rounds:
        print(f"  Round {r['id']:4d}: {r['round_date']} {r['round_time']} - {r['map_name']:20s} R{r['round_number']}")
    
    # Get player stats count for this session
    round_ids = [r['id'] for r in rounds]
    
    player_stats = await conn.fetchrow("""
        SELECT COUNT(*) as count, COUNT(DISTINCT player_guid) as unique_players
        FROM player_comprehensive_stats
        WHERE round_id = ANY($1)
    """, round_ids)
    
    print(f"\n👥 Player stats: {player_stats['count']} records, {player_stats['unique_players']} unique players")
    
    # Check what _fetch_session_data query returns
    print(f"\n{'='*70}")
    print("🔍 What _fetch_session_data() returns:\n")
    
    sessions = await conn.fetch("""
        SELECT id, map_name, round_number, actual_time
        FROM rounds
        WHERE gaming_session_id = $1
        ORDER BY round_date, round_time
    """, latest_gaming_session_id)
    
    print(f"Session data returned: {len(sessions)} rounds")
    for s in sessions:
        print(f"  ID: {s['id']}, Map: {s['map_name']}, Round: {s['round_number']}, Time: {s['actual_time']}")
    
    # Check all gaming sessions to see the pattern
    print(f"\n{'='*70}")
    print("📊 All Gaming Sessions:\n")
    
    all_sessions = await conn.fetch("""
        SELECT 
            gaming_session_id,
            COUNT(*) as rounds,
            MIN(round_date || ' ' || round_time) as first_round,
            MAX(round_date || ' ' || round_time) as last_round
        FROM rounds
        GROUP BY gaming_session_id
        ORDER BY gaming_session_id DESC
        LIMIT 5
    """)
    
    for s in all_sessions:
        print(f"Session #{s['gaming_session_id']:2d}: {s['rounds']:2d} rounds | {s['first_round']} → {s['last_round']}")
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
