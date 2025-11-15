import asyncio
import sys
from pathlib import Path
sys.path.insert(0, '.')
from postgresql_database_manager import PostgreSQLDatabaseManager

async def main():
    db = PostgreSQLDatabaseManager(stats_dir='local_stats')
    await db.connect()
    
    # The 4 missing files
    missing_files = [
        'local_stats/2025-11-11-222852-te_escape2-round-1.txt',
        'local_stats/2025-11-11-223323-te_escape2-round-2.txt',
        'local_stats/2025-11-11-233403-braundorf_b4-round-1.txt',
        'local_stats/2025-11-11-233911-braundorf_b4-round-2.txt',
    ]
    
    print("Re-importing 4 missing files...")
    print("="*80)
    
    for filepath in missing_files:
        filename = Path(filepath).name
        
        # STEP 1: Clear processed_files entry
        print(f"\n📄 {filename}")
        print(f"   Clearing processed status...")
        
        async with db.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM processed_files WHERE filename = $1",
                filename
            )
        
        print(f"   ✅ Cleared from processed_files")
        
        # STEP 2: Attempt fresh import
        print(f"   Attempting fresh import...")
        
        test_file = Path(filepath)
        if not test_file.exists():
            print(f"   ❌ File not found: {filepath}")
            continue
        
        try:
            success, message = await db.process_file(test_file)
            if success:
                print(f"   ✅ SUCCESS: {message}")
            else:
                print(f"   ❌ FAILED: {message}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("Verifying database...")
    
    # Check rounds table
    async with db.pool.acquire() as conn:
        result = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM rounds 
            WHERE round_date LIKE '2025-11-11%' 
              AND round_number IN (1, 2)
        """)
        print(f"Total R1+R2 rounds in database: {result}")
    
    await db.disconnect()

asyncio.run(main())
