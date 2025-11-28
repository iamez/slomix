import asyncio
import os
import sys
from bot.config import load_config
from bot.core.database_adapter import create_adapter

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)


async def check_schema():
    config = load_config()
    adapter_kwargs = config.get_database_adapter_kwargs()

    # Force Postgres for this check
    if config.database_type == "sqlite":
        print("Config is SQLite, but checking Postgres schema...")
        # Manually construct Postgres kwargs if needed, or just fail if not configured
        # For now, assuming environment is set correctly for prod
        pass

    db = create_adapter(**adapter_kwargs)
    await db.connect()

    try:
        # Check for player_links table
        print("Checking for 'player_links' table...")
        exists = await db.fetch_val(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'player_links'
            );
        """
        )
        print(f"Table 'player_links' exists: {exists}")

        if exists:
            # Show columns
            columns = await db.fetch_all(
                """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'player_links';
            """
            )
            print("Columns:")
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
