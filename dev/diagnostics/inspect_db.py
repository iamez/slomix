#!/usr/bin/env python3
"""
Database table inspection
"""
import asyncio
import aiosqlite

async def inspect_database():
    """Check what tables actually exist in the database"""
    db_path = './etlegacy_perfect.db'
    
    try:
        print("🔍 Inspecting database structure...")
        async with aiosqlite.connect(db_path) as db:
            print("✅ Database connection successful!")
            
            # Get all table names
            cursor = await db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """)
            tables = await cursor.fetchall()
            
            print(f"\n📊 Found {len(tables)} tables:")
            for table in tables:
                table_name = table[0]
                # Get record count
                try:
                    count_cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = await count_cursor.fetchone()
                    print(f"✅ {table_name}: {count[0]} records")
                    
                    # Get table schema
                    schema_cursor = await db.execute(f"PRAGMA table_info({table_name})")
                    columns = await schema_cursor.fetchall()
                    col_names = [col[1] for col in columns]
                    print(f"   Columns: {', '.join(col_names)}")
                    print()
                except Exception as e:
                    print(f"❌ {table_name}: Error - {e}")
                
    except Exception as e:
        print(f"❌ Database inspection failed: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_database())