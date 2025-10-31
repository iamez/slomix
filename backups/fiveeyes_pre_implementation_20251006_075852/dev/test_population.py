#!/usr/bin/env python3
"""
🎮 ET:Legacy Database Population Test
====================================
Simulate populating the database with realistic ET:Legacy game data
to test the complete workflow.
"""

import asyncio
import aiosqlite
from datetime import datetime, timedelta
import random


async def populate_sample_session():
    """Create a sample ET:Legacy session with realistic data"""
    print("🎮 Creating sample ET:Legacy session...")
    
    db_path = "../etlegacy_perfect.db"
    
    # Sample player data (realistic ET:Legacy names and stats)
    sample_players = [
        {"name": "KillerNinja", "skill": "high"},
        {"name": "sniperking", "skill": "medium"},
        {"name": "NewbiePro", "skill": "low"},
        {"name": "MedicMain", "skill": "medium"},
        {"name": "TankBuster", "skill": "high"},
        {"name": "EngiSpammer", "skill": "low"},
        {"name": "FieldOps", "skill": "medium"},
        {"name": "CovertOps", "skill": "high"},
    ]
    
    maps = ["oasis", "goldrush", "battery", "railgun", "fueldump", "braundorf_b4"]
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # 1. Create session
            current_map = random.choice(maps)
            session_start = datetime.now() - timedelta(minutes=30)
            
            insert_session = """
                INSERT INTO sessions (
                    start_time, map_name, status, date, total_rounds, created_at
                ) VALUES (?, ?, 'active', ?, 0, ?)
            """
            cursor = await db.execute(insert_session, (
                session_start.isoformat(),
                current_map,
                session_start.date().isoformat(),
                session_start.isoformat()
            ))
            session_id = cursor.lastrowid
            await db.commit()
            
            print(f"📊 Created session {session_id} on map '{current_map}'")
            
            # 2. Generate realistic player stats
            print("👥 Adding players with realistic stats...")
            
            insert_stats = """
                INSERT INTO player_stats (
                    session_id, player_name, round_type, team,
                    kills, deaths, damage, time_played, time_minutes,
                    dpm, kd_ratio, mvp_points, weapon_stats, achievements
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            teams = ["axis", "allies"]
            players_data = []
            
            for i, player in enumerate(sample_players):
                name = player["name"]
                skill = player["skill"]
                team = teams[i % 2]  # Alternate teams
                
                # Generate stats based on skill level
                if skill == "high":
                    base_kills = random.randint(15, 25)
                    base_deaths = random.randint(5, 12)
                    base_damage = random.randint(1200, 2000)
                elif skill == "medium":
                    base_kills = random.randint(8, 15)
                    base_deaths = random.randint(8, 15)
                    base_damage = random.randint(600, 1200)
                else:  # low skill
                    base_kills = random.randint(3, 10)
                    base_deaths = random.randint(12, 20)
                    base_damage = random.randint(300, 800)
                
                time_played = random.randint(1200, 1800)  # 20-30 minutes
                time_minutes = time_played // 60
                dpm = (base_damage / time_minutes) if time_minutes > 0 else 0
                kd_ratio = (base_kills / base_deaths) if base_deaths > 0 else base_kills
                
                # Calculate MVP points (kills * 2 + damage/10 - deaths)
                mvp_points = (base_kills * 2) + (base_damage // 10) - base_deaths
                
                # Sample weapon stats (JSON-like string)
                weapon_stats = f'{{"mp40": {random.randint(0, base_kills//2)}, "thompson": {random.randint(0, base_kills//2)}, "panzerfaust": {random.randint(0, 3)}}}'
                
                # Sample achievements
                achievements = f'{{"headshots": {random.randint(0, base_kills//3)}, "multikills": {random.randint(0, 2)}}}'
                
                players_data.append((
                    session_id, name, "round", team,
                    base_kills, base_deaths, base_damage, 
                    time_played, time_minutes, round(dpm, 2), 
                    round(kd_ratio, 2), mvp_points,
                    weapon_stats, achievements
                ))
            
            await db.executemany(insert_stats, players_data)
            await db.commit()
            
            print(f"✅ Added {len(players_data)} players to session")
            
            # 3. Display session summary
            print("\n📊 Session Summary:")
            print(f"   Map: {current_map}")
            print(f"   Duration: ~30 minutes")
            print(f"   Players: {len(players_data)}")
            
            # Get team stats
            team_query = """
                SELECT team, 
                       COUNT(*) as player_count,
                       SUM(kills) as total_kills,
                       SUM(deaths) as total_deaths,
                       AVG(kd_ratio) as avg_kd
                FROM player_stats 
                WHERE session_id = ?
                GROUP BY team
            """
            cursor = await db.execute(team_query, (session_id,))
            team_stats = await cursor.fetchall()
            
            print("\n🏆 Team Statistics:")
            for team, count, kills, deaths, avg_kd in team_stats:
                print(f"   {team.upper()}: {count} players, "
                      f"{kills}K/{deaths}D, Avg K/D: {avg_kd:.2f}")
            
            # Get top performers
            top_players_query = """
                SELECT player_name, team, kills, deaths, kd_ratio, mvp_points
                FROM player_stats 
                WHERE session_id = ?
                ORDER BY mvp_points DESC
                LIMIT 3
            """
            cursor = await db.execute(top_players_query, (session_id,))
            top_players = await cursor.fetchall()
            
            print("\n🥇 Top Performers:")
            for i, (name, team, kills, deaths, kd, mvp) in enumerate(top_players, 1):
                print(f"   {i}. {name} ({team}): {kills}K/{deaths}D, "
                      f"K/D: {kd:.2f}, MVP: {mvp}")
            
            # 4. End the session
            session_end = datetime.now()
            update_session = """
                UPDATE sessions 
                SET end_time = ?, status = 'completed', total_rounds = 1
                WHERE id = ?
            """
            await db.execute(update_session, (session_end.isoformat(), session_id))
            await db.commit()
            
            print(f"\n✅ Session {session_id} completed successfully!")
            print(f"📊 Data stored in database: {len(players_data)} player records")
            
            return session_id
            
    except Exception as e:
        print(f"❌ Failed to populate session: {e}")
        import traceback
        traceback.print_exc()
        return None


async def verify_data_quality():
    """Verify the quality of data in the database"""
    print("\n🔍 Verifying data quality...")
    
    db_path = "../etlegacy_perfect.db"
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Check total sessions
            cursor = await db.execute("SELECT COUNT(*) FROM sessions")
            session_count = (await cursor.fetchone())[0]
            
            # Check total player records
            cursor = await db.execute("SELECT COUNT(*) FROM player_stats")
            player_records = (await cursor.fetchone())[0]
            
            # Check data consistency
            consistency_query = """
                SELECT 
                    COUNT(CASE WHEN kills >= 0 THEN 1 END) as valid_kills,
                    COUNT(CASE WHEN deaths >= 0 THEN 1 END) as valid_deaths,
                    COUNT(CASE WHEN damage >= 0 THEN 1 END) as valid_damage,
                    COUNT(CASE WHEN kd_ratio >= 0 THEN 1 END) as valid_kd,
                    COUNT(*) as total_records
                FROM player_stats
            """
            cursor = await db.execute(consistency_query)
            validity = await cursor.fetchone()
            
            print(f"📊 Database Statistics:")
            print(f"   Total Sessions: {session_count}")
            print(f"   Total Player Records: {player_records}")
            print(f"   Data Validity: {validity[0]}/{validity[4]} valid records")
            
            # Check for recent sessions
            recent_query = """
                SELECT id, map_name, status, 
                       datetime(start_time) as start_time
                FROM sessions 
                ORDER BY created_at DESC 
                LIMIT 5
            """
            cursor = await db.execute(recent_query)
            recent_sessions = await cursor.fetchall()
            
            print(f"\n📅 Recent Sessions:")
            for session_id, map_name, status, start_time in recent_sessions:
                print(f"   Session {session_id}: {map_name} ({status}) "
                      f"- {start_time}")
            
            return True
            
    except Exception as e:
        print(f"❌ Data verification failed: {e}")
        return False


async def main():
    """Run database population test"""
    print("🎮 ET:Legacy Database Population Test")
    print("=" * 50)
    
    # Test 1: Populate with sample data
    session_id = await populate_sample_session()
    
    if session_id:
        print(f"\n✅ Sample session {session_id} created successfully!")
        
        # Test 2: Verify data quality
        if await verify_data_quality():
            print("\n🎉 Database population test completed successfully!")
            print("\n🚀 Your bot is ready to handle real ET:Legacy data!")
            print("\nNext steps:")
            print("1. Connect your ET:Legacy server to feed real stats")
            print("2. Test Discord commands with the populated data")
            print("3. Monitor performance with real gameplay sessions")
        else:
            print("\n⚠️ Data verification had issues")
    else:
        print("\n❌ Failed to create sample session")


if __name__ == "__main__":
    asyncio.run(main())