#!/usr/bin/env python3
"""
🗄️ Database Population Test (Fixed)
=====================================
Test script to verify database connectivity, schema, and data population
for the ET:Legacy Discord Bot with correct schema.
"""

import asyncio
import aiosqlite
import sys
from pathlib import Path

# Add bot directory to path
sys.path.append(str(Path(__file__).parent.parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser


async def test_database_connection():
    """Test basic database connectivity"""
    print("🔌 Testing database connection...")
    
    db_path = "etlegacy_perfect.db"
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("SELECT 1")
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


async def check_database_schema():
    """Check if database tables exist with correct structure"""
    print("\n📋 Checking database schema...")
    
    db_path = "etlegacy_perfect.db"
    try:
        async with aiosqlite.connect(db_path) as db:
            # Check for required tables
            tables_query = """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """
            cursor = await db.execute(tables_query)
            tables = [row[0] for row in await cursor.fetchall()]
            
            print(f"📁 Found tables: {tables}")
            
            # Check specific required tables
            required_tables = ['sessions', 'player_stats', 'player_links']
            missing_tables = [t for t in required_tables if t not in tables]
            
            if missing_tables:
                print(f"❌ Missing required tables: {missing_tables}")
                return False
            
            print("✅ All required tables exist")
            
            # Check sessions structure
            cursor = await db.execute("PRAGMA table_info(sessions)")
            sessions_columns = [col[1] for col in await cursor.fetchall()]
            print(f"📊 sessions columns: {sessions_columns}")
            
            # Check player_stats structure
            cursor = await db.execute("PRAGMA table_info(player_stats)")
            player_stats_columns = [col[1] for col in await cursor.fetchall()]
            print(f"📊 player_stats columns: {player_stats_columns}")
            
            # Verify essential columns exist
            required_sessions_cols = ['id', 'map_name', 'start_time', 'status']
            required_stats_cols = ['session_id', 'player_name', 'kills', 'deaths']
            
            missing_session_cols = [c for c in required_sessions_cols 
                                  if c not in sessions_columns]
            missing_stats_cols = [c for c in required_stats_cols 
                                if c not in player_stats_columns]
            
            if missing_session_cols:
                print(f"❌ Missing sessions columns: {missing_session_cols}")
                return False
                
            if missing_stats_cols:
                print(f"❌ Missing player_stats columns: {missing_stats_cols}")
                return False
            
            print("✅ Database schema is correct")
            return True
            
    except Exception as e:
        print(f"❌ Schema check failed: {e}")
        return False


async def test_database_operations():
    """Test basic database CRUD operations with correct schema"""
    print("\n💾 Testing database operations...")
    
    db_path = "etlegacy_perfect.db"
    try:
        async with aiosqlite.connect(db_path) as db:
            # Test session creation with correct columns
            insert_session = """
                INSERT INTO sessions (start_time, map_name, status, date)
                VALUES (datetime('now'), ?, 'active', date('now'))
            """
            cursor = await db.execute(insert_session, ("oasis",))
            session_id = cursor.lastrowid
            await db.commit()
            print(f"✅ Created test session: {session_id}")
            
            # Test player stats insertion with correct columns
            insert_stats = """
                INSERT INTO player_stats (
                    session_id, player_name, kills, deaths, damage, 
                    time_played, round_type, team
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            test_player_data = [
                (session_id, "TestPlayer1", 5, 3, 450, 300, "round", "axis"),
                (session_id, "TestPlayer2", 3, 5, 300, 280, "round", "allies")
            ]
            
            await db.executemany(insert_stats, test_player_data)
            await db.commit()
            print("✅ Inserted test player stats")
            
            # Test data retrieval
            query_stats = """
                SELECT player_name, kills, deaths, damage
                FROM player_stats
                WHERE session_id = ?
            """
            cursor = await db.execute(query_stats, (session_id,))
            results = await cursor.fetchall()
            
            print(f"📊 Retrieved {len(results)} player records:")
            for row in results:
                name, kills, deaths, damage = row
                print(f"   👤 {name}: {kills}K/{deaths}D, {damage} damage")
            
            # Cleanup test data
            await db.execute("DELETE FROM player_stats WHERE session_id = ?", 
                           (session_id,))
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()
            print("🧹 Cleaned up test data")
            
            print("✅ Database operations test passed")
            return True
            
    except Exception as e:
        print(f"❌ Database operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_stats_parser():
    """Test the stats parser functionality"""
    print("\n📈 Testing stats parser...")
    
    try:
        parser = C0RNP0RN3StatsParser()
        print("✅ Stats parser initialized")
        
        # Check if parser has expected methods
        methods = [attr for attr in dir(parser) 
                  if not attr.startswith('_') and callable(getattr(parser, attr))]
        print(f"📝 Parser methods: {methods}")
        
        print("✅ Stats parser test passed")
        return True
        
    except Exception as e:
        print(f"❌ Stats parser test failed: {e}")
        return False


async def test_session_workflow():
    """Test a complete session workflow"""
    print("\n🎯 Testing complete session workflow...")
    
    db_path = "etlegacy_perfect.db"
    try:
        async with aiosqlite.connect(db_path) as db:
            # 1. Create a new session
            print("1️⃣ Creating new session...")
            insert_session = """
                INSERT INTO sessions (start_time, map_name, status, date, total_rounds)
                VALUES (datetime('now'), ?, 'active', date('now'), 0)
            """
            cursor = await db.execute(insert_session, ("goldrush",))
            session_id = cursor.lastrowid
            await db.commit()
            print(f"   ✅ Session created: {session_id}")
            
            # 2. Add multiple players with stats
            print("2️⃣ Adding player stats...")
            insert_stats = """
                INSERT INTO player_stats (
                    session_id, player_name, discord_id, round_type, team,
                    kills, deaths, damage, time_played, time_minutes,
                    dpm, kd_ratio, mvp_points
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            players_data = [
                (session_id, "ProPlayer1", None, "round", "axis", 
                 15, 8, 1200, 1800, 30, 40.0, 1.875, 85),
                (session_id, "ProPlayer2", None, "round", "allies", 
                 12, 10, 980, 1800, 30, 32.67, 1.2, 72),
                (session_id, "NewPlayer", None, "round", "axis", 
                 6, 15, 450, 1200, 20, 22.5, 0.4, 35),
            ]
            
            await db.executemany(insert_stats, players_data)
            await db.commit()
            print(f"   ✅ Added {len(players_data)} players")
            
            # 3. Query session statistics
            print("3️⃣ Calculating session stats...")
            stats_query = """
                SELECT 
                    COUNT(*) as player_count,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    AVG(kd_ratio) as avg_kd,
                    MAX(mvp_points) as top_mvp
                FROM player_stats 
                WHERE session_id = ?
            """
            cursor = await db.execute(stats_query, (session_id,))
            session_stats = await cursor.fetchone()
            
            print(f"   📊 Session Stats:")
            print(f"      Players: {session_stats[0]}")
            print(f"      Total K/D: {session_stats[1]}/{session_stats[2]}")
            print(f"      Avg K/D Ratio: {session_stats[3]:.2f}")
            print(f"      Top MVP: {session_stats[4]} points")
            
            # 4. Get leaderboard
            print("4️⃣ Generating leaderboard...")
            leaderboard_query = """
                SELECT player_name, kills, deaths, kd_ratio, mvp_points
                FROM player_stats 
                WHERE session_id = ?
                ORDER BY mvp_points DESC
            """
            cursor = await db.execute(leaderboard_query, (session_id,))
            leaderboard = await cursor.fetchall()
            
            print("   🏆 Leaderboard:")
            for i, (name, kills, deaths, kd, mvp) in enumerate(leaderboard, 1):
                print(f"      {i}. {name}: {kills}K/{deaths}D "
                      f"(K/D: {kd:.2f}, MVP: {mvp})")
            
            # 5. End session
            print("5️⃣ Ending session...")
            update_session = """
                UPDATE sessions 
                SET end_time = datetime('now'), 
                    status = 'completed',
                    total_rounds = 1
                WHERE id = ?
            """
            await db.execute(update_session, (session_id,))
            await db.commit()
            print("   ✅ Session ended")
            
            # 6. Cleanup
            await db.execute("DELETE FROM player_stats WHERE session_id = ?", 
                           (session_id,))
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()
            print("6️⃣ ✅ Cleaned up test data")
            
            print("✅ Complete session workflow test passed!")
            return True
            
    except Exception as e:
        print(f"❌ Session workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all database tests"""
    print("🧪 ET:Legacy Bot Database Test Suite")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Database Schema", check_database_schema),
        ("Stats Parser", test_stats_parser),
        ("Database Operations", test_database_operations),
        ("Session Workflow", test_session_workflow)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 50)
    print("🎯 Test Results Summary:")
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Database is ready for population.")
        print("\n🚀 Ready to test with real ET:Legacy server data!")
    else:
        print("⚠️ Some tests failed. Check the issues above.")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(main())