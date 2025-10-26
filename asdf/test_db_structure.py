#!/usr/bin/env python3
"""
Database structure inspection for ETLegacy bot
"""
import asyncio
import aiosqlite


async def inspect_database():
    """Inspect database structure"""
    db_path = './database/etlegacy_perfect.db'
    
    try:
        async with aiosqlite.connect(db_path) as db:
            print("🔍 Inspecting database structure...")
            
            # Get table schemas
            tables = ['sessions', 'player_round_stats', 'player_map_stats', 'player_links']
            
            for table in tables:
                print(f"\n📋 Table: {table}")
                cursor = await db.execute(f"PRAGMA table_info({table})")
                columns = await cursor.fetchall()
                
                for col in columns:
                    print(f"   {col[1]} ({col[2]})")
                
                # Show sample data
                cursor = await db.execute(f"SELECT * FROM {table} LIMIT 1")
                sample = await cursor.fetchone()
                if sample:
                    print(f"   Sample: {sample[:3]}...")  # First 3 values
                    
    except Exception as e:
        print(f"❌ Database inspection failed: {e}")


if __name__ == "__main__":
    asyncio.run(inspect_database())