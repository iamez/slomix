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
    try:
        # Check rounds schema
        print("Checking rounds schema...")
        columns = await db.fetch_all(
            """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'rounds';
            """
        )
        print("Rounds Columns:")
        for col in columns:
            print(f" - {col[0]} ({col[1]})")

    finally:
        await db.close()


if __name__ == "__main__":
    # Ensure we use Postgres env vars
    os.environ["DATABASE_TYPE"] = "postgresql"
    asyncio.run(check_schema())
