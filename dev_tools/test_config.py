import os
from bot.config import BotConfig

print("Environment Variables:")
print(f"  DATABASE_TYPE = {os.getenv('DATABASE_TYPE')}")
print(f"  POSTGRES_HOST = {os.getenv('POSTGRES_HOST')}")
print(f"  POSTGRES_DATABASE = {os.getenv('POSTGRES_DATABASE')}")

print("\nBotConfig values:")
config = BotConfig()
print(f"  database_type = {config.database_type}")
print(f"  postgres_host = {config.postgres_host}")
print(f"  postgres_database = {config.postgres_database}")
