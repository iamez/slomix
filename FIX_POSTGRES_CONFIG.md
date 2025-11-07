# 🚨 CRITICAL: Restore PostgreSQL Configuration

## PROBLEM SUMMARY
The bot's configuration was accidentally broken during security fixes. It now defaults to SQLite instead of PostgreSQL, breaking the `postgresql_database_manager.py` tool.

## ROOT CAUSE
File: `bot/config.py` line 37
- Currently: `self.database_type = self._get_config('DATABASE_TYPE', 'sqlite')`  
- Problem: Defaults to 'sqlite' when DATABASE_TYPE not found
- Impact: postgresql_database_manager.py refuses to run

## IMMEDIATE FIX INSTRUCTIONS

### Step 1: Create bot_config.json (PREFERRED METHOD)
Create this file in the project root:

```json
{
  "database_type": "postgresql",
  "postgresql": {
    "host": "localhost",
    "port": 5432,
    "database": "et_stats",
    "user": "postgres",
    "password": "your_password_here"
  },
  "discord": {
    "token": "your_discord_token_here"
  },
  "stats": {
    "local_stats_path": "local_stats"
  }
}
```

### Step 2: Fix BotConfig to properly load config

**File:** `bot/config.py`
**REPLACE lines 30-45** with:

```python
def __init__(self):
    """Initialize configuration"""
    self.logger = logging.getLogger('BotConfig')
    
    # Load from dotenv first
    load_dotenv()
    
    # Try to load bot_config.json
    self.config_data = {}
    config_file = Path('bot_config.json')
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                self.config_data = json.load(f)
                self.logger.info("✅ Loaded bot_config.json")
        except Exception as e:
            self.logger.error(f"Failed to load bot_config.json: {e}")
    
    # CRITICAL: Set database type correctly
    # Priority: ENV > bot_config.json > default to postgresql (not sqlite!)
    self.database_type = os.getenv('DATABASE_TYPE') or \
                        self.config_data.get('database_type') or \
                        'postgresql'  # DEFAULT TO POSTGRESQL
    
    self.logger.info(f"🔧 Configuration loaded: database_type={self.database_type}")
```

### Step 3: Ensure PostgreSQL config is loaded

**Add after line 45 in bot/config.py:**

```python
    # Load PostgreSQL configuration
    if self.database_type == 'postgresql':
        pg_config = self.config_data.get('postgresql', {})
        self.postgres_host = os.getenv('POSTGRES_HOST') or pg_config.get('host', 'localhost')
        self.postgres_port = int(os.getenv('POSTGRES_PORT') or pg_config.get('port', 5432))
        self.postgres_database = os.getenv('POSTGRES_DATABASE') or pg_config.get('database', 'et_stats')
        self.postgres_user = os.getenv('POSTGRES_USER') or pg_config.get('user', 'postgres')
        self.postgres_password = os.getenv('POSTGRES_PASSWORD') or pg_config.get('password', '')
        
        self.logger.info(f"PostgreSQL configured: {self.postgres_user}@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}")
```

### Step 4: Verify the fix

Run this test:
```bash
python -c "from bot.config import BotConfig; bc = BotConfig(); print(f'Database: {bc.database_type}'); print(f'Ready: {bc.database_type == \"postgresql\"}')"
```

Expected output:
```
Database: postgresql
Ready: True
```

### Step 5: Test postgresql_database_manager.py

```bash
python postgresql_database_manager.py
```

Should show the menu without errors.

## VERIFICATION CHECKLIST

- [ ] bot_config.json created with PostgreSQL settings
- [ ] bot/config.py modified to default to 'postgresql' not 'sqlite'  
- [ ] PostgreSQL config attributes added (postgres_host, postgres_database, etc.)
- [ ] Test script shows "Database: postgresql"
- [ ] postgresql_database_manager.py shows menu (no ValueError)

## IF STILL BROKEN

1. Check if PostgreSQL is running:
   ```bash
   psql -U postgres -c "SELECT version();"
   ```

2. Manually set environment variable:
   ```bash
   set DATABASE_TYPE=postgresql
   python postgresql_database_manager.py
   ```

3. Check logs:
   ```bash
   tail -n 50 logs/bot.log
   ```

## IMPORTANT NOTES

- The bot was working with PostgreSQL before today's changes
- The security fixes accidentally changed config loading
- SQLite is only for local testing, PostgreSQL is production
- The database itself is fine, just config loading is broken