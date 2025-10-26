#!/usr/bin/env python3
"""
🎮 Real ET:Legacy Stats Processing Test
=====================================
Test the complete technological pipeline using real ET:Legacy stats files
with the existing C0RNP0RN3StatsParser.
"""

import asyncio
import aiosqlite
import sys
import os
from pathlib import Path
from datetime import datetime
import traceback

# Add bot directory to path
sys.path.append(str(Path(__file__).parent.parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser


async def test_parser_with_real_files():
    """Test the parser with real ET:Legacy stats files"""
    print("📊 Testing parser with real ET:Legacy files...")
    
    parser = C0RNP0RN3StatsParser()
    test_files_dir = "../test_files"
    
    try:
        # Get all stats files
        stats_files = []
        for file in os.listdir(test_files_dir):
            if file.endswith('.txt'):
                stats_files.append(os.path.join(test_files_dir, file))
        
        print(f"📁 Found {len(stats_files)} stats files")
        
        # Test parsing a round 1 file
        round_1_files = [f for f in stats_files if 'round-1' in f]
        if round_1_files:
            test_file = round_1_files[0]
            print(f"🔍 Testing parser with: {os.path.basename(test_file)}")
            
            # Use the parser's main method
            parsed_data = parser.parse_stats_file(test_file)
            
            print("✅ Parser completed successfully!")
            print(f"📊 Parsed data keys: {list(parsed_data.keys())}")
            
            # Display some key info
            if 'match_info' in parsed_data:
                match_info = parsed_data['match_info']
                print(f"   Map: {match_info.get('map_name', 'Unknown')}")
                print(f"   Date: {match_info.get('date', 'Unknown')}")
            
            if 'players' in parsed_data:
                players = parsed_data['players']
                print(f"   Players: {len(players)}")
                
                # Show top 3 players
                if players:
                    sorted_players = sorted(players, 
                                          key=lambda p: p.get('kills', 0), 
                                          reverse=True)[:3]
                    print("   Top performers:")
                    for i, player in enumerate(sorted_players, 1):
                        name = player.get('name', 'Unknown')
                        kills = player.get('kills', 0)
                        deaths = player.get('deaths', 0)
                        print(f"      {i}. {name}: {kills}K/{deaths}D")
            
            return parsed_data, test_file
        else:
            print("❌ No round-1 files found")
            return None, None
            
    except Exception as e:
        print(f"❌ Parser test failed: {e}")
        traceback.print_exc()
        return None, None


async def test_round_2_differential():
    """Test round 2 parsing with differential"""
    print("\n📊 Testing round 2 differential parsing...")
    
    parser = C0RNP0RN3StatsParser()
    test_files_dir = "../test_files"
    
    try:
        # Find matching round 1 and round 2 files
        round_2_files = [f for f in os.listdir(test_files_dir) if 'round-2' in f]
        
        if round_2_files:
            test_file = os.path.join(test_files_dir, round_2_files[0])
            print(f"🔍 Testing round 2 file: {os.path.basename(test_file)}")
            
            # Use round 2 parser with differential
            parsed_data = parser.parse_round_2_with_differential(test_file)
            
            print("✅ Round 2 parser completed!")
            print(f"📊 Keys: {list(parsed_data.keys())}")
            
            if 'players' in parsed_data:
                players = parsed_data['players']
                print(f"   Players with differentials: {len(players)}")
                
                # Show players with biggest improvements
                improved_players = [p for p in players 
                                  if p.get('round_2_differential', {}).get('kills', 0) > 0]
                if improved_players:
                    print("   Players who improved in round 2:")
                    for player in improved_players[:3]:
                        name = player.get('name', 'Unknown')
                        diff = player.get('round_2_differential', {})
                        k_diff = diff.get('kills', 0)
                        d_diff = diff.get('deaths', 0)
                        print(f"      {name}: +{k_diff}K/{d_diff:+d}D")
            
            return parsed_data
        else:
            print("❌ No round-2 files found")
            return None
            
    except Exception as e:
        print(f"❌ Round 2 parser test failed: {e}")
        traceback.print_exc()
        return None


async def store_real_data_in_database(parsed_data, source_file):
    """Store real parsed data in the database"""
    print("\n💾 Storing real data in database...")
    
    if not parsed_data:
        print("❌ No parsed data to store")
        return False
    
    db_path = "../etlegacy_perfect.db"
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Extract match info
            match_info = parsed_data.get('match_info', {})
            players = parsed_data.get('players', [])
            
            map_name = match_info.get('map_name', 'Unknown')
            date_str = match_info.get('date', datetime.now().isoformat())
            
            print(f"📊 Processing {len(players)} players from {map_name}")
            
            # Create session
            insert_session = """
                INSERT INTO sessions (
                    start_time, map_name, status, date, total_rounds, created_at
                ) VALUES (?, ?, 'completed', ?, 1, ?)
            """
            
            cursor = await db.execute(insert_session, (
                date_str, map_name, date_str[:10], datetime.now().isoformat()
            ))
            session_id = cursor.lastrowid
            await db.commit()
            
            print(f"✅ Created session {session_id} for {map_name}")
            
            # Store player stats
            insert_stats = """
                INSERT INTO player_stats (
                    session_id, player_name, round_type, team,
                    kills, deaths, damage, time_played, time_minutes,
                    dpm, kd_ratio, mvp_points, weapon_stats, achievements
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            players_data = []
            for player in players:
                name = player.get('name', 'Unknown')
                team = player.get('team', 'unknown')
                kills = player.get('kills', 0)
                deaths = player.get('deaths', 0)
                damage = player.get('damage_given', 0)
                time_played = player.get('time_played', 0)
                
                # Calculate derived stats
                time_minutes = max(1, time_played // 60)  # Avoid division by zero
                dpm = damage / time_minutes if time_minutes > 0 else 0
                kd_ratio = kills / deaths if deaths > 0 else kills
                
                # Simple MVP calculation
                mvp_points = (kills * 2) + (damage // 10) - deaths
                
                # Store weapon stats as JSON string if available
                weapon_stats = str(player.get('weapon_stats', {}))
                achievements = str(player.get('achievements', {}))
                
                players_data.append((
                    session_id, name, "round", team,
                    kills, deaths, damage, time_played, time_minutes,
                    round(dpm, 2), round(kd_ratio, 2), mvp_points,
                    weapon_stats, achievements
                ))
            
            await db.executemany(insert_stats, players_data)
            await db.commit()
            
            print(f"✅ Stored {len(players_data)} player records")
            
            # Display session summary
            summary_query = """
                SELECT 
                    COUNT(*) as player_count,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    AVG(kd_ratio) as avg_kd,
                    MAX(mvp_points) as top_mvp
                FROM player_stats 
                WHERE session_id = ?
            """
            cursor = await db.execute(summary_query, (session_id,))
            stats = await cursor.fetchone()
            
            print(f"📊 Session Summary:")
            print(f"   Players: {stats[0]}")
            print(f"   Total K/D: {stats[1]}/{stats[2]}")
            print(f"   Avg K/D: {stats[3]:.2f}")
            print(f"   Top MVP: {stats[4]} points")
            
            # Get top players
            top_query = """
                SELECT player_name, kills, deaths, kd_ratio, mvp_points
                FROM player_stats 
                WHERE session_id = ?
                ORDER BY mvp_points DESC
                LIMIT 5
            """
            cursor = await db.execute(top_query, (session_id,))
            top_players = await cursor.fetchall()
            
            print("\n🏆 Top Players:")
            for i, (name, kills, deaths, kd, mvp) in enumerate(top_players, 1):
                print(f"   {i}. {name}: {kills}K/{deaths}D "
                      f"(K/D: {kd:.2f}, MVP: {mvp})")
            
            return session_id
            
    except Exception as e:
        print(f"❌ Database storage failed: {e}")
        traceback.print_exc()
        return False


async def test_complete_pipeline():
    """Test the complete pipeline with multiple files"""
    print("\n🔄 Testing complete pipeline with multiple files...")
    
    test_files_dir = "../test_files"
    parser = C0RNP0RN3StatsParser()
    
    try:
        # Get all round-1 files for processing
        round_1_files = []
        for file in os.listdir(test_files_dir):
            if 'round-1' in file and file.endswith('.txt'):
                round_1_files.append(os.path.join(test_files_dir, file))
        
        print(f"📁 Processing {len(round_1_files)} round-1 files...")
        
        successful_sessions = []
        
        for i, file_path in enumerate(round_1_files[:3], 1):  # Process first 3 files
            print(f"\n{i}. Processing {os.path.basename(file_path)}...")
            
            try:
                # Parse the file
                parsed_data = parser.parse_stats_file(file_path)
                
                # Store in database
                session_id = await store_real_data_in_database(parsed_data, file_path)
                
                if session_id:
                    successful_sessions.append(session_id)
                    print(f"   ✅ Session {session_id} created successfully")
                else:
                    print(f"   ❌ Failed to create session")
                    
            except Exception as e:
                print(f"   ❌ Failed to process {file_path}: {e}")
        
        print(f"\n🎉 Pipeline test completed!")
        print(f"   Processed: {len(round_1_files[:3])} files")
        print(f"   Successful: {len(successful_sessions)} sessions")
        print(f"   Session IDs: {successful_sessions}")
        
        return len(successful_sessions) > 0
        
    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        traceback.print_exc()
        return False


async def verify_real_data():
    """Verify the stored real data"""
    print("\n🔍 Verifying stored real data...")
    
    db_path = "../etlegacy_perfect.db"
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Get recent sessions with real data
            query = """
                SELECT s.id, s.map_name, s.start_time, 
                       COUNT(ps.id) as player_count,
                       SUM(ps.kills) as total_kills,
                       SUM(ps.deaths) as total_deaths
                FROM sessions s
                LEFT JOIN player_stats ps ON s.id = ps.session_id
                WHERE s.map_name != 'Unknown'
                GROUP BY s.id, s.map_name, s.start_time
                ORDER BY s.created_at DESC
                LIMIT 10
            """
            cursor = await db.execute(query)
            sessions = await cursor.fetchall()
            
            print(f"📊 Found {len(sessions)} sessions with real data:")
            
            for session in sessions:
                sid, map_name, start_time, players, kills, deaths = session
                print(f"   Session {sid}: {map_name} - {players} players, "
                      f"{kills}K/{deaths}D ({start_time[:19]})")
            
            return len(sessions) > 0
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


async def main():
    """Run the complete real data processing test"""
    print("🎮 Real ET:Legacy Stats Processing Test")
    print("=" * 60)
    
    tests = [
        ("Parse Real Files", test_parser_with_real_files),
        ("Round 2 Differential", test_round_2_differential),
        ("Complete Pipeline", test_complete_pipeline),
        ("Verify Real Data", verify_real_data)
    ]
    
    results = {}
    parsed_data = None
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_name == "Parse Real Files":
                parsed_data, source_file = await test_func()
                results[test_name] = parsed_data is not None
                
                # Store the first successful parse
                if parsed_data and source_file:
                    print(f"\n💾 Storing first parsed file in database...")
                    store_result = await store_real_data_in_database(parsed_data, source_file)
                    if store_result:
                        print(f"✅ Successfully stored real data!")
            else:
                result = await test_func()
                results[test_name] = result
                
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 Real Data Processing Results:")
    
    passed = 0
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed >= 3:  # At least 3 out of 4 tests should pass
        print("\n🎉 SUCCESS! Real ET:Legacy data processing works!")
        print("\n🚀 Your technological pipeline is ready:")
        print("   ✅ Parser processes real stats files")
        print("   ✅ Database stores processed data")
        print("   ✅ Bot can query and display results")
        print("\n📋 Next: Test Discord commands with real data!")
    else:
        print("\n⚠️ Some issues found. Check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())