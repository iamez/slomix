#!/usr/bin/env python3
"""Check te_escape2 files on 2025-12-20"""
import asyncio
import sys
sys.path.insert(0, '/home/samba/share/slomix_discord')

from bot.core.database_adapter import PostgreSQLAdapter
from bot.config import BotConfig

async def main():
    config = BotConfig()

    db = PostgreSQLAdapter(
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password
    )

    await db.connect()

    print("=" * 80)
    print("TE_ESCAPE2 FILES ON 2025-12-20")
    print("=" * 80)

    # Check all rounds for te_escape2 on Dec 20
    query = """
        SELECT
            r.id,
            r.round_date,
            r.round_time,
            r.map_name,
            r.round_number,
            r.match_id,
            r.actual_time,
            COUNT(p.id) as player_count,
            AVG(p.time_dead_minutes) as avg_time_dead,
            AVG(p.time_played_minutes) as avg_time_played
        FROM rounds r
        LEFT JOIN player_comprehensive_stats p ON r.id = p.round_id
        WHERE r.map_name LIKE '%escape2%' AND r.round_date = '2025-12-20'
        GROUP BY r.id, r.round_date, r.round_time, r.map_name, r.round_number, r.match_id, r.actual_time
        ORDER BY r.round_time, r.round_number
    """

    rows = await db.fetch_all(query)

    for row in rows:
        rid, rd, rt, map_name, rn, match_id, actual_time, pc, avg_dead, avg_played = row
        print(f"\nRound {rid}: {rt} - R{rn} (match_id={match_id})")
        print(f"  actual_time: {actual_time}, players: {pc}")
        print(f"  avg_time_dead: {avg_dead:.2f} min")
        print(f"  avg_time_played: {avg_played:.2f} min")

    print("\n" + "=" * 80)
    print("CHECKING PROCESSED_FILES FOR TE_ESCAPE2 ON DEC 20")
    print("=" * 80)

    query2 = """
        SELECT file_path, import_date
        FROM processed_files
        WHERE file_path LIKE '%2025-12-20%' AND file_path LIKE '%escape2%'
        ORDER BY file_path
    """

    rows2 = await db.fetch_all(query2)

    for row in rows2:
        file_path, import_date = row
        print(f"{file_path} (imported: {import_date})")

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
