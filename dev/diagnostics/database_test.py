#!/usr/bin/env python3
"""
Database connectivity test for ETLegacy bot
"""
import asyncio
import aiosqlite

async def test_database():
    """Test database connection and basic structure"""
    db_path = './etlegacy_perfect.db'
    
    try:
        print("🔍 Testing database connection...")
        async with aiosqlite.connect(db_path) as db:
            print("✅ Database connection successful!")
            
            # Check if main tables exist
            tables_to_check = [
                'sessions', 
                'player_round_stats', 
                'player_map_stats', 
                'player_links', 
                'player_display_names'
            ]
            
            print("\n📊 Checking table structure...")
            for table in tables_to_check:
                try:
                    cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
                    count = await cursor.fetchone()
                    print(f"✅ {table}: {count[0]} records")
                except Exception as e:
                    print(f"❌ {table}: Error - {e}")
            
            # Test a sample query for DPM data
            print("\n🎯 Testing DPM data...")
            cursor = await db.execute("""
                SELECT clean_name_final, overall_dpm 
                FROM player_map_stats 
                WHERE overall_dpm > 0 
                ORDER BY overall_dpm DESC 
                LIMIT 5
            """)
            results = await cursor.fetchall()
            
            if results:
                print("✅ DPM data found:")
                for player, dpm in results:
                    print(f"   {player}: {dpm:.1f} DPM")
            else:
                print("⚠️  No DPM data found")
                
    except Exception as e:
        print(f"❌ Database test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_database())