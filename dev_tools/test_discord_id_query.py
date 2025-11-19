import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect(
        database='etlegacy',
        user='etlegacy_user',
        password='etlegacy_secure_2025',
        host='localhost'
    )
    
    # Test with int (correct way)
    discord_id = 121791571468353536
    print(f"Testing with int: {discord_id} (type: {type(discord_id).__name__})")
    
    try:
        result = await conn.fetchrow(
            "SELECT et_guid, et_name FROM player_links WHERE discord_id = $1",
            discord_id
        )
        print(f"✅ Result: {dict(result) if result else 'None'}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test with string (wrong way - should fail)
    discord_id_str = "121791571468353536"
    print(f"\nTesting with string: {discord_id_str} (type: {type(discord_id_str).__name__})")
    
    try:
        result = await conn.fetchrow(
            "SELECT et_guid, et_name FROM player_links WHERE discord_id = $1",
            discord_id_str
        )
        print(f"✅ Result: {dict(result) if result else 'None'}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await conn.close()

asyncio.run(test())
