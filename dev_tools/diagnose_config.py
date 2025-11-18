"""
Diagnose configuration issues and restore PostgreSQL functionality
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

print("=" * 80)
print("🔍 CONFIGURATION DIAGNOSIS")
print("=" * 80)

# 1. Check what config files exist
print("\n[1] Checking configuration files...")
config_files = {
    '.env': Path('.env'),
    'bot_config.json': Path('bot_config.json'),
    '.env.example': Path('.env.example')
}

for name, path in config_files.items():
    if path.exists():
        print(f"  ✅ {name} exists ({path.stat().st_size} bytes)")
        if name == '.env':
            # Load and check critical values
            load_dotenv()
            db_type = os.getenv('DATABASE_TYPE')
            pg_host = os.getenv('POSTGRES_HOST')
            pg_db = os.getenv('POSTGRES_DATABASE')
            print(f"     DATABASE_TYPE = {db_type or 'NOT SET'}")
            print(f"     POSTGRES_HOST = {pg_host or 'NOT SET'}")
            print(f"     POSTGRES_DATABASE = {pg_db or 'NOT SET'}")
    else:
        print(f"  ❌ {name} not found")

# 2. Check if bot_config.json has database settings
if Path('bot_config.json').exists():
    print("\n[2] Checking bot_config.json...")
    with open('bot_config.json', 'r') as f:
        config = json.load(f)
        db_type = config.get('database_type', 'NOT SET')
        pg_config = config.get('postgresql', {})
        print(f"  database_type: {db_type}")
        if pg_config:
            print(f"  PostgreSQL config found: {pg_config.get('host', 'NO HOST')}")

# 3. Test BotConfig loading
print("\n[3] Testing BotConfig class...")
try:
    from bot.config import BotConfig
    bc = BotConfig()
    print(f"  BotConfig.database_type = {bc.database_type}")
    print(f"  BotConfig.postgres_host = {getattr(bc, 'postgres_host', 'NOT SET')}")
    print(f"  BotConfig.postgres_database = {getattr(bc, 'postgres_database', 'NOT SET')}")
except Exception as e:
    print(f"  ❌ Error loading BotConfig: {e}")

# 4. Check environment variables directly
print("\n[4] Checking environment variables...")
env_vars = ['DATABASE_TYPE', 'POSTGRES_HOST', 'POSTGRES_DATABASE', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
for var in env_vars:
    value = os.getenv(var)
    if value:
        if 'PASSWORD' in var:
            print(f"  {var} = {'*' * 8}")
        else:
            print(f"  {var} = {value}")
    else:
        print(f"  {var} = NOT SET")

print("\n" + "=" * 80)
print("📝 DIAGNOSIS COMPLETE")
print("=" * 80)