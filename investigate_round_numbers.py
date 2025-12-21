#!/usr/bin/env python3
"""Investigate round number values"""
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
    print("ROUND NUMBER INVESTIGATION")
    print("=" * 80)

    # Check what round_number values exist
    query = """
        SELECT DISTINCT round_number, COUNT(*) as count
        FROM player_comprehensive_stats
        GROUP BY round_number
        ORDER BY round_number
    """
    rows = await db.fetch_all(query)

    print("\nRound number distribution:")
    for row in rows:
        round_num, count = row
        print(f"  Round {round_num}: {count} records")

    # Check recent Round 2 data
    print("\n" + "=" * 80)
    print("RECENT ROUND 2 DATA")
    print("=" * 80)

    query = """
        SELECT
            r.id,
            r.round_date,
            r.round_time,
            r.map_name,
            r.round_number,
            COUNT(p.id) as player_count,
            AVG(p.time_dead_minutes) as avg_time_dead,
            AVG(p.time_played_minutes) as avg_time_played,
            AVG(p.denied_playtime) as avg_denied
        FROM rounds r
        LEFT JOIN player_comprehensive_stats p ON r.id = p.round_id
        WHERE r.round_number = 2
        GROUP BY r.id, r.round_date, r.round_time, r.map_name, r.round_number
        ORDER BY r.round_date DESC, r.id DESC
        LIMIT 10
    """

    rows = await db.fetch_all(query)

    for row in rows:
        rid, rd, rt, map_name, rn, pc, avg_dead, avg_played, avg_denied = row
        print(f"\nRound {rid}: {rd} {rt} - {map_name} (R{rn})")
        print(f"  Players: {pc}")
        print(f"  Avg time_dead_minutes: {avg_dead}")
        print(f"  Avg time_played_minutes: {avg_played}")
        print(f"  Avg denied_playtime: {avg_denied}")

    # Check if there are matching R1 files for recent R2 files with 0 time_dead
    print("\n" + "=" * 80)
    print("CHECKING R1/R2 PAIRS WITH ZERO TIME_DEAD")
    print("=" * 80)

    query = """
        WITH zero_r2 AS (
            SELECT DISTINCT round_id, round_date, map_name
            FROM player_comprehensive_stats
            WHERE round_number = 2 AND time_dead_minutes = 0
            AND round_date >= '2025-12-15'
        )
        SELECT
            z.round_date,
            z.map_name,
            r1.id as r1_round_id,
            r2.id as r2_round_id,
            r1.round_time as r1_time,
            r2.round_time as r2_time,
            (SELECT AVG(time_dead_minutes) FROM player_comprehensive_stats WHERE round_id = r1.id) as r1_avg_dead,
            (SELECT AVG(time_dead_minutes) FROM player_comprehensive_stats WHERE round_id = r2.id) as r2_avg_dead
        FROM zero_r2 z
        LEFT JOIN rounds r1 ON z.round_date = r1.round_date AND z.map_name = r1.map_name AND r1.round_number = 1
        LEFT JOIN rounds r2 ON z.round_date = r2.round_date AND z.map_name = r2.map_name AND r2.round_number = 2
        ORDER BY z.round_date DESC
        LIMIT 10
    """

    rows = await db.fetch_all(query)

    for row in rows:
        rd, map_name, r1_id, r2_id, r1_time, r2_time, r1_avg_dead, r2_avg_dead = row
        print(f"\nDate: {rd}, Map: {map_name}")
        print(f"  R1 (id={r1_id}, time={r1_time}): avg_dead={r1_avg_dead}")
        print(f"  R2 (id={r2_id}, time={r2_time}): avg_dead={r2_avg_dead}")

        if r1_avg_dead is not None and r2_avg_dead == 0:
            print(f"  ⚠️ Issue: R1 has deaths but R2 differential is 0!")

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
