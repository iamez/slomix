"""
Quick script to wipe PostgreSQL database and re-import all files.
This will use the FIXED bot import logic (process_file instead of import_stats_file).
"""
import asyncio
from postgresql_database_manager import PostgreSQLDatabase
import json

async def reimport_all():
    print("🔄 Starting fresh PostgreSQL import...")
    
    # Load config
    with open('bot/config.json', 'r') as f:
        config = json.load(f)
    
    pg_config = config['postgresql']
    
    # Create database manager
    db_manager = PostgreSQLDatabase({
        'host': pg_config['host'],
        'port': pg_config['port'],
        'database': pg_config['database'],
        'user': pg_config['user'],
        'password': pg_config['password']
    })
    
    # Connect
    await db_manager.connect()
    
    print("\n1️⃣  Wiping existing database...")
    await db_manager.create_fresh_database(backup_existing=True)
    
    print("\n2️⃣  Re-importing all 2025 files...")
    await db_manager.import_all_files(year_filter=2025, progress_callback=True)
    
    print("\n3️⃣  Validating database...")
    validation = await db_manager.validate_database()
    
    print(f"\n✅ Import complete!")
    print(f"   Rounds: {validation['rounds_count']}")
    print(f"   Player stats: {validation['player_stats_count']}")
    print(f"   Weapon stats: {validation['weapon_stats_count']}")
    print(f"   Processed files: {validation['processed_files_count']}")
    
    await db_manager.disconnect()

if __name__ == '__main__':
    asyncio.run(reimport_all())
