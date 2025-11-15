import asyncio
import sys
sys.path.insert(0, '.')
from bot.core.database_adapter import create_adapter
from bot.config import load_config

async def main():
    config = load_config()
    db = create_adapter(**config.get_database_adapter_kwargs())
    await db.connect()

    # Check gaming_session_ids for 2025-11-11
    print("Gaming sessions on 2025-11-11:\n")
    sessions = await db.fetch_all("""
        SELECT DISTINCT gaming_session_id,
               MIN(round_date || ' ' || round_time) as start_time,
               MAX(round_date || ' ' || round_time) as end_time,
               COUNT(*) as round_count,
               STRING_AGG(DISTINCT map_name, ', ' ORDER BY map_name) as maps
        FROM rounds
        WHERE round_date LIKE '2025-11-11%'
          AND round_number IN (1, 2)
        GROUP BY gaming_session_id
        ORDER BY gaming_session_id
    """)

    for session_id, start, end, count, maps in sessions:
        print(f"Session ID {session_id}:")
        print(f"  Time: {start} → {end}")
        print(f"  Rounds: {count}")
        print(f"  Maps: {maps}")
        print()

    # Now check if qmr data is from another date
    print("="*80)
    print("Where did qmr come from?\n")

    qmr_data = await db.fetch_all("""
        SELECT r.round_date, r.gaming_session_id, COUNT(*) as rounds
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE p.player_name = 'qmr'
          AND r.round_number IN (1, 2)
        GROUP BY r.round_date, r.gaming_session_id
        ORDER BY r.round_date DESC
        LIMIT 5
    """)

    for date, session_id, rounds in qmr_data:
        print(f"  {date} - Session {session_id} - {rounds} rounds")

    await db.close()

asyncio.run(main())
