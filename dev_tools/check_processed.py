"""Check what Nov 2 files were processed"""
import asyncio
import asyncpg

async def check_processed():
    conn = await asyncpg.connect(
        host='localhost', port=5432, user='etlegacy_user',
        password='etlegacy_secure_2025', database='etlegacy'
    )
    
    print("=== Nov 2 Processed Files ===")
    files = await conn.fetch("""
        SELECT filename, processed_at
        FROM processed_files 
        WHERE filename LIKE '%2025-11-02%'
        ORDER BY filename
    """)
    
    print(f"Total files processed: {len(files)}")
    for f in files:
        print(f"{f['filename']}")
    
    await conn.close()

asyncio.run(check_processed())
