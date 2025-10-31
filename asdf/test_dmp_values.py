#!/usr/bin/env python3
"""
Test DPM calculation functionality
"""
import asyncio
import aiosqlite


async def test_dpm_calculation():
    """Test current DPM values and realistic ranges"""
    db_path = './database/etlegacy_perfect.db'
    
    try:
        async with aiosqlite.connect(db_path) as db:
            print("🎯 Testing current DPM calculations...")
            
            # Check DPM distribution
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    MIN(overall_dpm) as min_dpm,
                    MAX(overall_dpm) as max_dpm,
                    AVG(overall_dpm) as avg_dpm
                FROM player_map_stats 
                WHERE overall_dpm > 0
            """)
            stats = await cursor.fetchone()
            
            print(f"📊 DPM Statistics:")
            print(f"   Total records: {stats[0]}")
            print(f"   Min DPM: {stats[1]:.1f}")
            print(f"   Max DPM: {stats[2]:.1f}")
            print(f"   Avg DPM: {stats[3]:.1f}")
            
            # Check if values are realistic (should be roughly 100-2000 for ET)
            if stats[2] > 5000:
                print("⚠️  WARNING: DPM values appear inflated!")
                print("   Expected range: 100-2000 DPM for realistic gameplay")
                print("   Current max suggests DPM calculation bug exists")
            else:
                print("✅ DPM values appear realistic")
                
            # Show top 10 DPM
            print("\n🏆 Top 10 DPM Players:")
            cursor = await db.execute("""
                SELECT clean_name_final, overall_dpm, total_kills, total_deaths
                FROM player_map_stats 
                WHERE overall_dpm > 0 
                ORDER BY overall_dpm DESC 
                LIMIT 10
            """)
            
            for i, (name, dpm, kills, deaths) in enumerate(await cursor.fetchall(), 1):
                print(f"   {i:2}. {name}: {dpm:.1f} DPM (K:{kills} D:{deaths})")
                
    except Exception as e:
        print(f"❌ DPM test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_dpm_calculation())