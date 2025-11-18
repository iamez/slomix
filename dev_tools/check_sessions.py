"""Check gaming sessions in PostgreSQL database"""
import asyncio
import asyncpg
from datetime import datetime

async def check_sessions():
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='etlegacy_user',
        password='etlegacy_secure_2025',
        database='etlegacy'
    )
    
    # Check latest sessions
    print("=== Latest Gaming Sessions ===")
    sessions = await conn.fetch("""
        SELECT 
            gaming_session_id,
            COUNT(*) as round_count,
            MIN(round_date) as session_start,
            MAX(round_date) as session_end,
            COUNT(DISTINCT map_name) as unique_maps
        FROM rounds
        WHERE gaming_session_id IS NOT NULL
        GROUP BY gaming_session_id
        ORDER BY gaming_session_id DESC
        LIMIT 10
    """)
    
    for s in sessions:
        # Parse string dates if necessary
        if isinstance(s['session_start'], str):
            start = datetime.fromisoformat(s['session_start'])
            end = datetime.fromisoformat(s['session_end'])
        else:
            start = s['session_start']
            end = s['session_end']
        
        duration = (end - start).total_seconds() / 60
        print(f"Session #{s['gaming_session_id']}: {s['round_count']} rounds, "
              f"{s['unique_maps']} maps, {duration:.0f} minutes")
    
    # Check last session details
    print("\n=== Last Session Details ===")
    last_session = await conn.fetch("""
        SELECT id, round_date, map_name, round_number, gaming_session_id
        FROM rounds
        WHERE gaming_session_id = (
            SELECT MAX(gaming_session_id) FROM rounds
        )
        ORDER BY round_date
    """)
    
    print(f"Total rounds in last session: {len(last_session)}")
    for r in last_session:
        # Handle string dates
        if isinstance(r['round_date'], str):
            date_str = r['round_date']
        else:
            date_str = r['round_date'].strftime('%Y-%m-%d %H:%M')
        
        print(f"  Round {r['id']}: {date_str} - "
              f"{r['map_name']} R{r['round_number']}")
    
    # Check rounds without session ID
    print("\n=== Rounds WITHOUT gaming_session_id ===")
    no_session = await conn.fetch("""
        SELECT COUNT(*) as count, 
               MIN(round_date) as earliest, 
               MAX(round_date) as latest
        FROM rounds
        WHERE gaming_session_id IS NULL
    """)
    
    if no_session[0]['count'] > 0:
        print(f"⚠️  {no_session[0]['count']} rounds have no gaming_session_id!")
        print(f"   Date range: {no_session[0]['earliest']} to {no_session[0]['latest']}")
    else:
        print("✅ All rounds have gaming_session_id")
    
    # Check total rounds
    total = await conn.fetchval("SELECT COUNT(*) FROM rounds")
    print(f"\n=== Total Rounds: {total} ===")
    
    await conn.close()

asyncio.run(check_sessions())
