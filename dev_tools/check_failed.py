import asyncio
import asyncpg
from bot.config import load_config

async def check_failed_files():
    config = load_config()
    
    conn = await asyncpg.connect(
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password
    )
    
    # Check the 2 problem files
    result = await conn.fetch("""
        SELECT filename, success, error_message 
        FROM processed_files 
        WHERE filename LIKE '%etl_frostbite%' OR filename LIKE '%224353%'
        ORDER BY filename
    """)
    
    print("\n=== Import Status for Problem Files ===\n")
    if result:
        for r in result:
            print(f"File: {r['filename']}")
            print(f"  Success: {r['success']}")
            print(f"  Error: {r['error_message']}\n")
    else:
        print("❌ No records found - files were never attempted to import!\n")
    
    await conn.close()

asyncio.run(check_failed_files())
