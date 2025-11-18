"""Quick check for gaming_session_id in PostgreSQL"""
import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='etlegacy_user',
        password='etlegacy_secure_2025',
        database='etlegacy'
    )
    
    # Check total rounds
    total = await conn.fetchval("SELECT COUNT(*) FROM rounds")
    print(f"Total rounds: {total}")
    
    # Check rounds with gaming_session_id
    with_session = await conn.fetchval(
        "SELECT COUNT(*) FROM rounds WHERE gaming_session_id IS NOT NULL"
    )
    print(f"Rounds with gaming_session_id: {with_session}")
    
    # Check most recent round
    recent = await conn.fetchrow(
        """
        SELECT id, round_date, round_time, gaming_session_id, map_name
        FROM rounds
        ORDER BY round_date DESC, round_time DESC
        LIMIT 1
        """
    )
    print(f"\nMost recent round:")
    print(f"  ID: {recent['id']}")
    print(f"  Date: {recent['round_date']}")
    print(f"  Time: {recent['round_time']}")
    print(f"  Gaming Session ID: {recent['gaming_session_id']}")
    print(f"  Map: {recent['map_name']}")
    
    # Check if gaming_session_id column exists
    cols = await conn.fetch(
        """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'rounds'
        ORDER BY ordinal_position
        """
    )
    print(f"\nRounds table columns:")
    for col in cols:
        print(f"  {col['column_name']}: {col['data_type']}")
    
    await conn.close()

asyncio.run(check())
