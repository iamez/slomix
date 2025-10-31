#!/usr/bin/env python3
"""
Test session management functionality
"""
import asyncio
import aiosqlite


async def test_session_management():
    """Test session management database operations"""
    db_path = './database/etlegacy_perfect.db'
    
    try:
        async with aiosqlite.connect(db_path) as db:
            print("🎬 Testing session management...")
            
            # Check current sessions
            cursor = await db.execute("""
                SELECT COUNT(*) FROM sessions WHERE session_date = date('now')
            """)
            today_sessions = await cursor.fetchone()
            print(f"📅 Sessions today: {today_sessions[0]}")
            
            # Check latest sessions
            cursor = await db.execute("""
                SELECT id, map_name, session_date, total_players
                FROM sessions 
                ORDER BY id DESC 
                LIMIT 5
            """)
            latest = await cursor.fetchall()
            
            print("\n📋 Latest sessions:")
            for session_id, map_name, date, players in latest:
                print(f"   {session_id}: {map_name} on {date} ({players} players)")
                
            # Check if there are any active sessions (status column may not exist)
            try:
                cursor = await db.execute("""
                    SELECT id, map_name FROM sessions WHERE status = 'active'
                """)
                active = await cursor.fetchall()
                if active:
                    print(f"\n⚠️  Active sessions found: {len(active)}")
                    for sid, map_name in active:
                        print(f"   Session {sid}: {map_name}")
                else:
                    print("\n✅ No active sessions")
            except Exception:
                print("\n📝 No status column in sessions table (older schema)")
                
    except Exception as e:
        print(f"❌ Session test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_session_management())