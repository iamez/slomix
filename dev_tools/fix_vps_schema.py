#!/usr/bin/env python3
"""
Add missing times_seen column to player_aliases table on VPS
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def add_times_seen_column():
    """Add times_seen column to player_aliases table"""
    
    # Get database connection info
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost').split(':')[0],
        'port': int(os.getenv('POSTGRES_HOST', 'localhost:5432').split(':')[1]) if ':' in os.getenv('POSTGRES_HOST', 'localhost:5432') else 5432,
        'database': os.getenv('POSTGRES_DATABASE', 'et_stats'),
        'user': os.getenv('POSTGRES_USER', 'et_bot'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }
    
    print(f"Connecting to PostgreSQL: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")
    
    conn = await asyncpg.connect(**db_config)
    
    try:
        # Check if column exists
        result = await conn.fetchrow("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'player_aliases' 
            AND column_name = 'times_seen'
        """)
        
        if result:
            print("✅ Column 'times_seen' already exists in player_aliases table")
        else:
            print("⚙️ Adding 'times_seen' column to player_aliases table...")
            
            await conn.execute("""
                ALTER TABLE player_aliases 
                ADD COLUMN times_seen INTEGER DEFAULT 1
            """)
            
            print("✅ Successfully added 'times_seen' column!")
        
        # Show current schema
        print("\n📋 Current player_aliases schema:")
        columns = await conn.fetch("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'player_aliases' 
            ORDER BY ordinal_position
        """)
        
        for col in columns:
            default = col['column_default'] if col['column_default'] else 'NULL'
            print(f"  - {col['column_name']}: {col['data_type']} (default: {default})")
        
    finally:
        await conn.close()
        print("\n✅ Database connection closed")

if __name__ == '__main__':
    asyncio.run(add_times_seen_column())
