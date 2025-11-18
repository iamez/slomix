"""
Quick fix to restore PostgreSQL configuration
"""
import json
from pathlib import Path

print("🔧 Applying quick fix for PostgreSQL configuration...")

# Create bot_config.json with PostgreSQL settings
config = {
    "database_type": "postgresql",
    "postgresql": {
        "host": "localhost",
        "port": 5432,
        "database": "et_stats", 
        "user": "postgres",
        "password": "postgres"  # Update this with your actual password
    },
    "discord": {
        "token": "your_discord_token_here"  # Update with actual token from .env
    },
    "stats": {
        "local_stats_path": "local_stats"
    }
}

config_file = Path('bot_config.json')
if not config_file.exists():
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    print("✅ Created bot_config.json with PostgreSQL configuration")
    print("⚠️  UPDATE the password in bot_config.json with your actual PostgreSQL password!")
else:
    print("⚠️  bot_config.json already exists - not overwriting")
    print("    Manually ensure it has database_type: 'postgresql'")

print("\nNext steps:")
print("1. Update password in bot_config.json")
print("2. Run: python postgresql_database_manager.py")
print("3. Should see the database manager menu")