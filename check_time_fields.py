#!/usr/bin/env python3
"""Check time field values in database"""
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
    print("RECENT PLAYER TIME FIELDS")
    print("=" * 80)

    query = """
        SELECT
            player_name,
            time_dead_minutes,
            time_played_minutes,
            denied_playtime,
            time_played_seconds,
            round_date,
            round_number
        FROM player_comprehensive_stats
        ORDER BY round_date DESC, round_id DESC
        LIMIT 15
    """

    rows = await db.fetch_all(query)

    for row in rows:
        name, time_dead_mins, time_played_mins, denied_play, time_sec, rd, rn = row
        print(f"\nPlayer: {name}")
        print(f"  Round: {rd} R{rn}")
        print(f"  time_dead_minutes: {time_dead_mins}")
        print(f"  time_played_minutes: {time_played_mins}")
        print(f"  time_played_seconds: {time_sec}")
        print(f"  denied_playtime: {denied_play}")

        # Test the formatting logic
        time_dead = time_dead_mins or 0
        time_played = time_played_mins or 0
        time_denied = denied_play or 0

        # Current formatting (from round_publisher_service.py)
        dead_min = int(time_dead)
        dead_sec = int((time_dead % 1) * 60)
        time_dead_str = f"{dead_min}:{dead_sec:02d}"

        denied_min = int(time_denied // 60)
        denied_sec = int(time_denied % 60)
        time_denied_str = f"{denied_min}:{denied_sec:02d}"

        played_min = int(time_played)
        played_sec = int((time_played % 1) * 60)
        time_played_str = f"{played_min}:{played_sec:02d}"

        print(f"  Formatted: Played={time_played_str} Dead={time_dead_str} Denied={time_denied_str}")

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
