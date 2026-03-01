import asyncio
import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

from bot.config import load_config
from bot.core.database_adapter import create_adapter


async def check_schema():
    config = load_config()
    adapter_kwargs = config.get_database_adapter_kwargs()

    db = create_adapter(**adapter_kwargs)
    await db.connect()

    try:
        # Check for player_comprehensive_stats table
        print("Checking for 'player_comprehensive_stats' table...")
        exists = await db.fetch_val(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'player_comprehensive_stats'
            );
        """
        )
        print(f"Table 'player_comprehensive_stats' exists: {exists}")

        if exists:
            # Show columns
            columns = await db.fetch_all(
                """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'player_comprehensive_stats'
                ORDER BY column_name;
            """
            )
            print("Columns in player_comprehensive_stats table:")
            for col in columns:
                print(f" - {col[0]} ({col[1]})")
        else:
            print("Table does not exist.")

    finally:
        await db.close()


if __name__ == "__main__":
    # Ensure we use Postgres env vars
    os.environ["DATABASE_TYPE"] = "postgresql"
    asyncio.run(check_schema())
