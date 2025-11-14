import asyncio
import sys
from pathlib import Path
sys.path.insert(0, '.')
from bot.config import load_config
from postgresql_database_manager import PostgreSQLDatabase

async def main():
    # Load config
    config = load_config()
    
    # Create database manager
    db_config = {
        'host': config.postgres_host,
        'port': config.postgres_port,
        'database': config.postgres_database,
        'user': config.postgres_user,
        'password': config.postgres_password
    }
    
    db = PostgreSQLDatabase(db_config)
    await db.connect()
    
    # Try to import one of the missing files
    test_file = Path('local_stats/2025-11-11-222852-te_escape2-round-1.txt')
    
    print(f"Attempting to import: {test_file}")
    print("="*80)
    
    if not test_file.exists():
        print(f"❌ File not found: {test_file}")
        return
    
    try:
        success, message = await db.process_file(test_file)
        print(f"\nResult: {'✅ SUCCESS' if success else '❌ FAILED'}")
        print(f"Message: {message}")
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
    
    await db.disconnect()

asyncio.run(main())
