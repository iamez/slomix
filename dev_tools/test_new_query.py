"""
Test the NEW _get_latest_session_date query
"""
import sqlite3
import asyncio
import aiosqlite

async def test_new_query():
    async with aiosqlite.connect('bot/etlegacy_production.db') as db:
        print("Testing NEW _get_latest_session_date query:")
        print("="*70)
        
        # New simplified query
        async with db.execute(
            """
            SELECT SUBSTR(s.round_date, 1, 10) as date
            FROM rounds s
            WHERE EXISTS (
                SELECT 1 FROM player_comprehensive_stats p
                WHERE p.round_id = s.id
            )
            AND SUBSTR(s.round_date, 1, 4) = '2025'
            ORDER BY s.round_date DESC
            LIMIT 1
            """
        ) as cursor:
            result = await cursor.fetchone()
            latest_date = result[0] if result else None
            print(f"Query returns: {latest_date}")
        
        print("\nWhat sessions exist on that date:")
        print("="*70)
        if latest_date:
            async with db.execute("""
                SELECT round_date, map_name, round_number, map_id
                FROM rounds
                WHERE SUBSTR(round_date, 1, 10) = ?
                ORDER BY round_date
                LIMIT 5
            """, (latest_date,)) as cursor:
                rows = await cursor.fetchall()
                print(f"First 5 sessions on {latest_date}:")
                for row in rows:
                    print(f"  {row[0]} - {row[1]} R{row[2]} (map_id={row[3]})")
            
            async with db.execute("""
                SELECT round_date, map_name, round_number, map_id
                FROM rounds
                WHERE SUBSTR(round_date, 1, 10) = ?
                ORDER BY round_date DESC
                LIMIT 3
            """, (latest_date,)) as cursor:
                rows = await cursor.fetchall()
                print(f"\nLast 3 sessions on {latest_date}:")
                for row in rows:
                    print(f"  {row[0]} - {row[1]} R{row[2]} (map_id={row[3]})")

asyncio.run(test_new_query())
