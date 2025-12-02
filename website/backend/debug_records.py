import asyncio
import os
from bot.core.database_adapter import create_adapter as create_postgres_adapter
from bot.config import load_config


async def main():
    config = load_config()
    adapter_kwargs = config.get_database_adapter_kwargs()
    db = create_postgres_adapter(**adapter_kwargs)
    await db.connect()

    print("Connected to DB")

    # Check count
    count = await db.fetch_val("SELECT COUNT(*) FROM player_comprehensive_stats")
    print(f"Total rows: {count}")

    # Check columns
    try:
        row = await db.fetch_one("SELECT * FROM player_comprehensive_stats LIMIT 1")
        if row:
            print("First row found")
            # We can't easily get column names from fetch_one result in this adapter if it returns tuple
            # But we can try to select specific columns

            try:
                print("Testing query for kills...")
                rows = await db.fetch_all(
                    "SELECT player_name, kills FROM player_comprehensive_stats WHERE time_played_seconds > 0 ORDER BY kills DESC LIMIT 1"
                )
                print(f"Kills query result: {rows}")
            except Exception as e:
                print(f"Kills query failed: {e}")

            try:
                print("Testing query for damage...")
                rows = await db.fetch_all(
                    "SELECT player_name, damage_given FROM player_comprehensive_stats WHERE time_played_seconds > 0 ORDER BY damage_given DESC LIMIT 1"
                )
                print(f"Damage query result: {rows}")
            except Exception as e:
                print(f"Damage query failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
