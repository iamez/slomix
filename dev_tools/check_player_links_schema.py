import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(
        database='etlegacy',
        user='etlegacy_user',
        password='etlegacy_secure_2025',
        host='localhost'
    )
    
    result = await conn.fetch("""
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_name = 'player_links'
        ORDER BY ordinal_position
    """)
    
    print('\nplayer_links table schema:')
    for row in result:
        print(f"  {row['column_name']:20} {row['data_type']:15} ({row['udt_name']})")
    
    # Check if table has any data
    count = await conn.fetchval("SELECT COUNT(*) FROM player_links")
    print(f'\nRows in player_links: {count}')
    
    if count > 0:
        sample = await conn.fetch("SELECT * FROM player_links LIMIT 3")
        print('\nSample data:')
        for row in sample:
            print(f"  {dict(row)}")
    
    await conn.close()

asyncio.run(check())
