"""Quick check for rounds in PostgreSQL database"""
import asyncio
import asyncpg
import json

async def check_postgres():
    # Load config
    with open('bot/config.json', 'r') as f:
        config = json.load(f)
    
    pg_config = config['postgresql']
    
    # Connect to PostgreSQL
    conn = await asyncpg.connect(
        host=pg_config['host'],
        port=pg_config['port'],
        database=pg_config['database'],
        user=pg_config['user'],
        password=pg_config['password']
    )
    
    try:
        # Check rounds table
        rounds_count = await conn.fetchval('SELECT COUNT(*) FROM rounds')
        print(f'✓ Rounds in PostgreSQL: {rounds_count}')
        
        # Check players table
        players_count = await conn.fetchval('SELECT COUNT(*) FROM player_comprehensive_stats')
        print(f'✓ Player stats: {players_count}')
        
        # Check weapons table
        weapons_count = await conn.fetchval('SELECT COUNT(*) FROM weapon_comprehensive_stats')
        print(f'✓ Weapon stats: {weapons_count}')
        
        # Check processed_files table
        processed_count = await conn.fetchval('SELECT COUNT(*) FROM processed_files')
        print(f'✓ Processed files: {processed_count}')
        
        # Get table schema
        schema_query = """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'rounds'
            ORDER BY ordinal_position
        """
        columns = await conn.fetch(schema_query)
        print('\n📋 Rounds table columns:')
        for col in columns:
            print(f'  {col["column_name"]:30} {col["data_type"]}')
            
        if rounds_count > 0:
            # Get most recent rounds (use actual columns)
            recent = await conn.fetch(
                'SELECT * FROM rounds ORDER BY id DESC LIMIT 3'
            )
            print('\nMost recent rounds:')
            for row in recent:
                print(f'  Round ID: {row["id"]}')
                print(f'    Columns: {dict(row)}')
        else:
            print('\n❌ NO ROUNDS IN DATABASE!')
            print('This means the bot imported to SQLite instead of PostgreSQL.')
            
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(check_postgres())
