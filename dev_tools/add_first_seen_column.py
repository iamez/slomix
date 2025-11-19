#!/usr/bin/env python3
"""
Add missing 'first_seen' column to player_aliases table on VPS.
This completes the schema migration to match expected structure.
"""

import asyncio
import asyncpg
import sys


async def add_first_seen_column():
    """Add first_seen column to player_aliases table."""
    
    print("🔧 Connecting to PostgreSQL database...")
    try:
        # Use environment variables or default values
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        conn = await asyncpg.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost').split(':')[0],
            port=int(os.getenv('POSTGRES_HOST', 'localhost:5432').split(':')[1]) if ':' in os.getenv('POSTGRES_HOST', 'localhost:5432') else 5432,
            database=os.getenv('POSTGRES_DATABASE', 'etlegacy'),
            user=os.getenv('POSTGRES_USER', 'etlegacy_user'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        print("✅ Connected successfully!")
        
        # Check if column already exists
        print("\n🔍 Checking if 'first_seen' column already exists...")
        check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'player_aliases' 
            AND column_name = 'first_seen'
        """
        existing = await conn.fetchval(check_query)
        
        if existing:
            print("⚠️  Column 'first_seen' already exists - skipping")
            await conn.close()
            return
        
        # Add the column with default value
        print("➕ Adding 'first_seen' column...")
        alter_query = """
            ALTER TABLE player_aliases 
            ADD COLUMN first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """
        await conn.execute(alter_query)
        
        print("✅ Successfully added 'first_seen' column!")
        
        # Update existing rows to set first_seen = last_seen if NULL
        print("\n🔄 Backfilling 'first_seen' for existing rows...")
        update_query = """
            UPDATE player_aliases 
            SET first_seen = last_seen 
            WHERE first_seen IS NULL AND last_seen IS NOT NULL
        """
        updated = await conn.execute(update_query)
        print(f"✅ Updated {updated.split()[-1]} existing rows")
        
        # Show final schema
        print("\n📋 Current player_aliases schema:")
        schema_query = """
            SELECT 
                column_name,
                data_type,
                column_default
            FROM information_schema.columns
            WHERE table_name = 'player_aliases'
            ORDER BY ordinal_position
        """
        columns = await conn.fetch(schema_query)
        for col in columns:
            default = col['column_default'] or 'NULL'
            print(f"  - {col['column_name']}: {col['data_type']} (default: {default})")
        
        await conn.close()
        print("\n✅ Schema update complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(add_first_seen_column())
