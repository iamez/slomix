import asyncio
import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

from bot.config import load_config
from bot.core.database_adapter import create_adapter


async def debug_stats():
    config = load_config()
    adapter_kwargs = config.get_database_adapter_kwargs()

    db = create_adapter(**adapter_kwargs)
    await db.connect()

    try:
        print("Querying random player...")
        query = "SELECT player_name FROM player_comprehensive_stats LIMIT 1"
        row = await db.fetch_one(query)

        if row:
            print(f"Found player: {row[0]}")
            player_name = row[0]

            # Now query stats for this player
            print(f"Querying stats for {player_name}...")
            query = """
                SELECT
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    SUM(p.damage_given) as total_damage,
                    SUM(p.time_played_seconds) as total_time,
                    COUNT(DISTINCT p.round_date) as total_games,
                    SUM(p.xp) as total_xp,
                    SUM(CASE WHEN p.team = r.winner_team THEN 1 ELSE 0 END) as total_wins,
                    MAX(p.round_date) as last_seen
                FROM player_comprehensive_stats p
                LEFT JOIN rounds r ON p.round_date = r.round_date AND p.map_name = r.map_name
                WHERE p.player_name = $1
            """
            row = await db.fetch_one(query, (player_name,))
            print("Result:", row)
        else:
            print("No players found.")

    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        await db.close()


if __name__ == "__main__":
    # Ensure we use Postgres env vars
    os.environ["DATABASE_TYPE"] = "postgresql"
    asyncio.run(debug_stats())
