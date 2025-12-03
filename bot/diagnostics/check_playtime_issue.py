import asyncio
import sys
sys.path.insert(0, '.')
from bot.core.database_adapter import create_adapter
from bot.config import load_config

async def main():
    config = load_config()
    db = create_adapter(**config.get_database_adapter_kwargs())
    await db.connect()

    print("🔍 Checking playtime calculation for gaming session 22...\n")

    # Get actual round times
    rounds = await db.fetch_all("""
        SELECT id, map_name, round_number, actual_time
        FROM rounds
        WHERE gaming_session_id = 22
          AND round_number IN (1, 2)
        ORDER BY id
    """)

    print("📊 Rounds in session 22:\n")
    total_round_time = 0
    for round_id, map_name, rnd, actual_time in rounds:
        print(f"  Round {round_id}: {map_name} R{rnd} - actual_time: {actual_time}")
        # Parse actual_time (format: "5:23" = 5 minutes 23 seconds)
        if actual_time and ':' in actual_time:
            parts = actual_time.split(':')
            minutes = int(parts[0])
            seconds = int(parts[1]) if len(parts) > 1 else 0
            total_seconds = minutes * 60 + seconds
            total_round_time += total_seconds

    print(f"\n✅ Total round time (if you played all rounds): {total_round_time // 60}:{total_round_time % 60:02d}")

    # Now check what time_played_seconds shows per player
    player_times = await db.fetch_all("""
        SELECT p.player_name,
               SUM(p.time_played_seconds) as total_time_played,
               COUNT(DISTINCT p.round_id) as rounds_played
        FROM player_comprehensive_stats p
        WHERE p.round_id IN (
            SELECT id FROM rounds
            WHERE gaming_session_id = 22
            AND round_number IN (1, 2)
        )
        GROUP BY p.player_guid, p.player_name
        ORDER BY total_time_played DESC
    """)

    print("\n📊 Player time_played_seconds from database:\n")
    for name, time_played, rounds_played in player_times:
        minutes = int(time_played // 60)
        seconds = int(time_played % 60)
        print(f"  {name}: {minutes}:{seconds:02d} ({rounds_played} rounds)")

    print("\n❌ PROBLEM: time_played_seconds varies per player!")
    print("   This suggests it's tracking 'alive time' not 'round duration'")
    print("\n✅ SOLUTION: Calculate playtime from actual_time of rounds played")
    print(f"   Everyone who played all {len(rounds)} rounds = {total_round_time // 60}:{total_round_time % 60:02d}")

    await db.close()

asyncio.run(main())
