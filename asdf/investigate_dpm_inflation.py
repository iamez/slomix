#!/usr/bin/env python3
"""
Check where the DPM inflation happens in the data pipeline
"""
import asyncio
import aiosqlite

async def investigate_dpm_inflation():
    """Find where DPM values get inflated"""
    
    print("🔍 INVESTIGATING DPM INFLATION")
    print("=" * 50)
    
    # Test with our parser first
    import sys
    sys.path.append('./bot')
    from community_stats_parser import C0RNP0RN3StatsParser
    
    parser = C0RNP0RN3StatsParser()
    test_file = "./test_files/2025-09-24-233255-te_escape2-round-1.txt"
    
    result = parser.parse_stats_file(test_file)
    
    print("🤖 PARSER RESULTS:")
    if result['success']:
        for i, player in enumerate(result['players'][:3], 1):
            print(f"   Player {i}: {player['name']}")
            print(f"     DPM: {player.get('dpm', 'N/A'):.1f}")
            print(f"     Damage: {player.get('damage_given', 'N/A')}")
    
    print()
    print("🗄️ DATABASE RESULTS:")
    
    # Check what's in the database
    db_path = './database/etlegacy_perfect.db'
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Find a specific player to compare
            cursor = await db.execute("""
                SELECT 
                    clean_name_final,
                    overall_dpm,
                    total_kills,
                    total_deaths,
                    processed_at
                FROM player_map_stats 
                WHERE clean_name_final LIKE '%vid%' OR clean_name_final LIKE '%olz%'
                ORDER BY overall_dpm DESC
                LIMIT 10
            """)
            
            db_players = await cursor.fetchall()
            
            for player in db_players:
                name, dpm, kills, deaths, processed = player
                print(f"   {name}: {dpm:.1f} DPM (K:{kills} D:{deaths}) - {processed}")
            
            print()
            print("📊 DPM DISTRIBUTION ANALYSIS:")
            
            # Check distribution
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as count,
                    AVG(overall_dpm) as avg_dpm,
                    MIN(overall_dpm) as min_dpm,
                    MAX(overall_dpm) as max_dpm
                FROM player_map_stats 
                WHERE overall_dpm > 0
            """)
            
            stats = await cursor.fetchone()
            print(f"   Total records: {stats[0]}")
            print(f"   Average DPM: {stats[1]:.1f}")
            print(f"   Min DPM: {stats[2]:.1f}")
            print(f"   Max DPM: {stats[3]:.1f}")
            
            # Check for suspiciously high values
            cursor = await db.execute("""
                SELECT COUNT(*) 
                FROM player_map_stats 
                WHERE overall_dpm > 1000
            """)
            
            high_count = await cursor.fetchone()
            print(f"   Records with DPM > 1000: {high_count[0]}")
            
            # Check for realistic values
            cursor = await db.execute("""
                SELECT COUNT(*) 
                FROM player_map_stats 
                WHERE overall_dpm BETWEEN 100 AND 800
            """)
            
            realistic_count = await cursor.fetchone()
            print(f"   Records with DPM 100-800: {realistic_count[0]}")
            
            print()
            print("🎯 HYPOTHESIS:")
            print("   Parser gives ~350 DPM (realistic)")
            print("   Database has ~30,000 DPM (100x inflated)")
            print("   Likely cause: Data from old/buggy import system")
            print("   Solution: Re-import with fixed parser or apply correction")
    
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    asyncio.run(investigate_dpm_inflation())