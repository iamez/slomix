"""
Debug what _get_latest_session_date actually returns
"""
import sqlite3
import asyncio
import aiosqlite

async def test_query():
    async with aiosqlite.connect('bot/etlegacy_production.db') as db:
        print("Testing _get_latest_session_date query:")
        print("="*70)
        
        # Exact query from last_session_cog.py
        async with db.execute(
            """
            SELECT MIN(SUBSTR(s.session_date, 1, 10)) as start_date
            FROM sessions s
            WHERE SUBSTR(s.session_date, 1, 10) IN (
                SELECT DISTINCT SUBSTR(session_date, 1, 10)
                FROM sessions
                ORDER BY session_date DESC
                LIMIT 2
            )
            AND EXISTS (
                SELECT 1 FROM player_comprehensive_stats p
                WHERE p.session_id = s.id
            )
            """
        ) as cursor:
            result = await cursor.fetchone()
            latest_date = result[0] if result else None
            print(f"Query returns: {latest_date}")
        
        print("\nBreaking down the query:")
        print("="*70)
        
        # Step 1: Get last 2 distinct dates
        async with db.execute("""
            SELECT DISTINCT SUBSTR(session_date, 1, 10) as date
            FROM sessions
            ORDER BY session_date DESC
            LIMIT 2
        """) as cursor:
            dates = await cursor.fetchall()
            print("Last 2 distinct dates from sessions:")
            for row in dates:
                print(f"  {row[0]}")
        
        # Step 2: Get MIN of those
        if dates:
            print(f"\nMIN of those 2 dates: {min(d[0] for d in dates)}")
        
        print("\nSessions on each date:")
        print("="*70)
        for date in dates:
            async with db.execute("""
                SELECT COUNT(*) as count,
                       MIN(session_date) as earliest,
                       MAX(session_date) as latest
                FROM sessions
                WHERE SUBSTR(session_date, 1, 10) = ?
            """, (date[0],)) as cursor:
                row = await cursor.fetchone()
                print(f"{date[0]}: {row[0]} sessions ({row[1]} to {row[2]})")
        
        print("\nWhat SHOULD be the latest session (by session_date):")
        print("="*70)
        async with db.execute("""
            SELECT session_date, map_name, round_number
            FROM sessions
            ORDER BY session_date DESC
            LIMIT 3
        """) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                print(f"  {row[0]} - {row[1]} R{row[2]}")

asyncio.run(test_query())
