import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from website.backend.mock_database_adapter import create_mock_adapter

async def test():
    print("Initializing Mock Adapter...")
    db = create_mock_adapter()
    
    print("\nTesting Latest Session Date...")
    # Query from SessionDataService.get_latest_session_date
    query = """
            SELECT SUBSTR(s.round_date, 1, 10) as date
            FROM rounds s
            WHERE EXISTS (
                SELECT 1 FROM player_comprehensive_stats p
                WHERE p.round_id = s.id
            )
            AND s.round_number IN (1, 2)
            AND (s.round_status IN ('completed', 'cancelled', 'substitution') OR s.round_status IS NULL)
            ORDER BY
                s.round_date DESC,
                CAST(REPLACE(s.round_time, ':', '') AS INTEGER) DESC
            LIMIT 1
            """
    res = await db.fetch_one(query)
    print(f"Result: {res}")

    print("\nTesting Fetch Session Data (Rounds)...")
    # Query from SessionDataService.fetch_session_data
    query = """
            SELECT id, map_name, round_number, actual_time
            FROM rounds
            WHERE gaming_session_id = ?
              AND round_number IN (1, 2)
              AND (round_status IN ('completed', 'cancelled', 'substitution') OR round_status IS NULL)
            ORDER BY
                round_date,
                CAST(REPLACE(round_time, ':', '') AS INTEGER)
            """
    res = await db.fetch_all(query, (100,))
    print(f"Result: {res}")

    print("\nTesting Leaderboard...")
    query = "SELECT * FROM player_comprehensive_stats GROUP BY player_name"
    res = await db.fetch_all(query)
    print(f"Result: {len(res)} rows")

if __name__ == "__main__":
    asyncio.run(test())
