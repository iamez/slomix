import asyncio
import sys
sys.path.insert(0, '.')
from bot.core.database_adapter import create_adapter
from bot.config import load_config

async def main():
    config = load_config()
    db = create_adapter(**config.get_database_adapter_kwargs())
    await db.connect()

    # Check ALL rounds for 2025-11-11 (including round_number 0)
    print("ALL rounds in database for 2025-11-11 (including match summaries):\n")
    all_rounds = await db.fetch_all("""
        SELECT round_date, round_time, map_name, round_number
        FROM rounds
        WHERE round_date LIKE '2025-11-11%'
        ORDER BY round_date, round_time, round_number
    """)

    print(f"Total rounds (all round_numbers): {len(all_rounds)}\n")
    for date, time, map_name, rnd in all_rounds:
        print(f"{date} {time} - {map_name} R{rnd}")

    # Check specifically for the 4 missing files
    print("\n" + "="*80)
    print("Checking for the 4 missing files:\n")

    missing = [
        ('2025-11-11', '22:28:52', 'te_escape2', 1),
        ('2025-11-11', '22:33:23', 'te_escape2', 2),
        ('2025-11-11', '23:34:03', 'braundorf_b4', 1),
        ('2025-11-11', '23:39:11', 'braundorf_b4', 2),
    ]

    for date, time, map_name, rnd in missing:
        result = await db.fetch_one("""
            SELECT id, round_date, round_time, map_name, round_number
            FROM rounds
            WHERE round_date LIKE $1
              AND round_time = $2
              AND map_name = $3
              AND round_number = $4
        """, (f"{date}%", time, map_name, rnd))

        if result:
            print(f"✅ FOUND: {date} {time} {map_name} R{rnd} (ID: {result[0]})")
        else:
            print(f"❌ MISSING: {date} {time} {map_name} R{rnd}")

    await db.close()

asyncio.run(main())
