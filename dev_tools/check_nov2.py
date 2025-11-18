"""Check Nov 2 sessions"""
import asyncio
import asyncpg

async def check_nov2():
    conn = await asyncpg.connect(
        host='localhost', port=5432, user='etlegacy_user',
        password='etlegacy_secure_2025', database='etlegacy'
    )
    
    print("=== Nov 2, 2025 Sessions ===")
    sessions = await conn.fetch("""
        SELECT gaming_session_id, COUNT(*) as rounds, 
               MIN(round_date) as start, MAX(round_date) as end,
               string_agg(DISTINCT map_name, ', ' ORDER BY map_name) as maps
        FROM rounds 
        WHERE round_date >= '2025-11-02' AND round_date < '2025-11-03'
        GROUP BY gaming_session_id 
        ORDER BY gaming_session_id
    """)
    
    total = 0
    for s in sessions:
        print(f"Session #{s['gaming_session_id']}: {s['rounds']} rounds - {s['maps']}")
        total += s['rounds']
    
    print(f"\nTotal Nov 2 rounds: {total}")
    await conn.close()

asyncio.run(check_nov2())
