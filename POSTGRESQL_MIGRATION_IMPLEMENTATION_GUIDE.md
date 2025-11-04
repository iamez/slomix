# 📘 PostgreSQL Migration - Step-by-Step Implementation Guide

**Date**: November 4, 2025  
**Branch**: `vps-network-migration`  
**For**: Developers implementing the PostgreSQL migration

---

## 🎯 Overview

This guide provides detailed, copy-paste-ready instructions for migrating the ET:Legacy Discord Bot from SQLite to PostgreSQL.

**Total Time**: 80 hours (~2-3 weeks part-time)  
**Phases**: 12  
**Current Progress**: Phase 1-2 complete (abstraction layer + config)

---

## 📋 Phase-by-Phase Implementation

### ✅ Phase 1: Database Abstraction Layer (COMPLETE)

**Status**: ✅ Done  
**Files Created**:
- `bot/core/database_adapter.py`
- `bot/config.py`

**What Was Done**:
- Created `SQLiteAdapter` class
- Created `PostgreSQLAdapter` class
- Implemented query translation (? → $1, $2)
- Added connection pooling
- Created config system

**Validation**:
```python
# Test the adapter
from bot.core.database_adapter import create_adapter
adapter = create_adapter('sqlite', db_path='bot/etlegacy_production.db')
await adapter.connect()
result = await adapter.fetch_one("SELECT COUNT(*) FROM rounds")
print(f"Total rounds: {result[0]}")
await adapter.close()
```

---

### 🟡 Phase 2: Update Bot Core (IN PROGRESS)

**Status**: 🟡 In Progress  
**File**: `bot/ultimate_bot.py` (~4800 lines)  
**Estimated Time**: 12 hours  
**Dependencies**: Phase 1 complete

#### Step 2.1: Add Imports

**Location**: Top of file (after existing imports)

```python
# Add these imports
from bot.core.database_adapter import create_adapter, DatabaseAdapter
from bot.config import load_config
```

#### Step 2.2: Update Bot Initialization

**Location**: `__init__` method of main bot class

**Find**:
```python
def __init__(self):
    super().__init__(command_prefix='!', intents=intents)
    self.db_path = os.getenv('DATABASE_PATH', 'bot/etlegacy_production.db')
```

**Replace with**:
```python
def __init__(self):
    super().__init__(command_prefix='!', intents=intents)
    
    # Load configuration
    self.config = load_config()
    
    # Create database adapter
    adapter_kwargs = self.config.get_database_adapter_kwargs()
    self.db_adapter = create_adapter(**adapter_kwargs)
    
    # Keep db_path for backward compatibility (some helpers might use it)
    self.db_path = self.config.sqlite_db_path if self.config.database_type == 'sqlite' else None
```

#### Step 2.3: Add setup_hook for Connection Pool

**Location**: Add new method to bot class

```python
async def setup_hook(self):
    """Initialize database connection pool before bot starts."""
    await self.db_adapter.connect()
    logger.info("✅ Database adapter connected")
    
    # Validate schema
    await self.validate_database_schema()
```

#### Step 2.4: Add close method for Cleanup

**Location**: Add new method to bot class

```python
async def close(self):
    """Clean up database connections before shutdown."""
    await self.db_adapter.close()
    logger.info("🔌 Database adapter closed")
    await super().close()
```

#### Step 2.5: Update validate_database_schema Method

**Find**:
```python
async def validate_database_schema(self):
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute("PRAGMA table_info(player_comprehensive_stats)")
```

**Replace with**:
```python
async def validate_database_schema(self):
    """Validate database has correct schema (works with both SQLite and PostgreSQL)."""
    try:
        # Check player_comprehensive_stats has 54 columns
        if self.config.database_type == 'sqlite':
            # SQLite: Use PRAGMA
            async with self.db_adapter.connection() as conn:
                cursor = await conn.execute("PRAGMA table_info(player_comprehensive_stats)")
                columns = await cursor.fetchall()
                actual_columns = len(columns)
        else:
            # PostgreSQL: Query information_schema
            async with self.db_adapter.connection() as conn:
                actual_columns = await self.db_adapter.fetch_val(
                    """
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_name = 'player_comprehensive_stats'
                    """
                )
        
        expected_columns = 54
        if actual_columns != expected_columns:
            error_msg = (
                f"❌ DATABASE SCHEMA MISMATCH!\n"
                f"Expected: {expected_columns} columns\n"
                f"Found: {actual_columns} columns\n"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        logger.info(f"✅ Database schema validated: {actual_columns} columns")
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        raise
```

#### Step 2.6: Update Database Connection Pattern (26 locations)

**Pattern to Find**:
```python
async with aiosqlite.connect(self.db_path) as db:
    cursor = await db.execute(query, params)
    result = await cursor.fetchone()
```

**Replace with**:
```python
async with self.db_adapter.connection() as conn:
    result = await self.db_adapter.fetch_one(query, params)
```

**Helper Script** (create `tools/update_connections.py`):
```python
#!/usr/bin/env python3
"""
Helper script to identify connection points that need updating.
Run this to get a list of all lines that need manual review.
"""
import re

def find_connections(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    pattern = re.compile(r'async with aiosqlite\.connect')
    matches = []
    
    for i, line in enumerate(lines, 1):
        if pattern.search(line):
            matches.append((i, line.strip()))
    
    return matches

if __name__ == "__main__":
    file_path = "bot/ultimate_bot.py"
    matches = find_connections(file_path)
    
    print(f"Found {len(matches)} connection points in {file_path}:")
    for line_num, line_text in matches:
        print(f"  Line {line_num}: {line_text}")
```

#### Step 2.7: Update SQL Queries with datetime('now')

**Find** (4 occurrences):
```sql
VALUES (?, ?, ?, ?, datetime('now'), 1)
```

**Replace with**:
```sql
VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
```

**Locations**:
- Line ~1408
- Line ~1556  
- Line ~1707
- Line ~1903

#### Step 2.8: Update date arithmetic query

**Find** (1 occurrence):
```sql
HAVING MAX(p.round_date) >= date('now', '-30 days')
```

**Replace with**:
```sql
HAVING MAX(p.round_date) >= CURRENT_DATE - INTERVAL '30 days'
```

**Location**: Line ~1094

#### Step 2.9: Test Bot Startup

```bash
# Ensure DATABASE_TYPE is set to sqlite for testing
echo "DATABASE_TYPE=sqlite" >> .env

# Start bot
python bot/ultimate_bot.py
```

**Expected Output**:
```
✅ Database adapter connected
✅ Database schema validated: 54 columns
🤖 Bot is ready!
```

#### Step 2.10: Test Basic Commands

Test these commands in Discord:
- `!help` - Should show commands
- `!last` - Should show last session
- `!stats` - Should show player stats
- `!leaderboard` - Should show leaderboard

**If all work**: ✅ Phase 2 complete, move to Phase 3  
**If any fail**: Debug before proceeding

---

### ⏳ Phase 3: Update Cogs (One at a Time)

**Status**: ⏳ Not Started  
**Estimated Time**: 15 hours total  
**Strategy**: Update one cog at a time, test after each

#### Phase 3.1: Update link_cog.py (4 hours)

**File**: `bot/cogs/link_cog.py`  
**Connections**: 5 locations  

**Changes**:
1. Replace all `async with aiosqlite.connect(self.bot.db_path)` with adapter
2. Update type hints: `"aiosqlite.Connection"` → `"asyncpg.Connection"` or remove quotes
3. Test Discord linking commands

**Testing**:
```
!link <player_name>
!unlink
!linked
```

#### Phase 3.2: Update last_session_cog.py (6 hours)

**File**: `bot/cogs/last_session_cog.py`  
**Connections**: 1 main + helpers  
**Complexity**: High (complex queries)

**Testing**:
```
!last
!last <date>
!lastsession
```

#### Phase 3.3: Update stats_cog.py (3 hours)

**File**: `bot/cogs/stats_cog.py`  
**Connections**: 4 locations

**Testing**:
```
!stats
!stats <player>
!playerstats
```

#### Phase 3.4: Update leaderboard_cog.py (2 hours)

**File**: `bot/cogs/leaderboard_cog.py`  
**Connections**: 2 locations

**Testing**:
```
!leaderboard
!leaderboard kills
!leaderboard accuracy
```

#### Phase 3.5: Update Other Cogs (5 hours total)

Files to update:
- `bot/cogs/admin_cog.py` (1 hour)
- `bot/cogs/session_cog.py` (1 hour)
- `bot/cogs/team_management_cog.py` (1 hour)
- `bot/cogs/synergy_analytics.py` (2 hours)

---

### ⏳ Phase 4: Update Automation Services (4 hours)

**Files**:
- `bot/automation_enhancements.py`
- `bot/services/automation/ssh_monitor.py`
- `bot/services/automation/metrics_logger.py`
- `bot/services/automation/database_maintenance.py`

**Note**: These are background services, test carefully to ensure they don't break monitoring.

---

### ⏳ Phase 5: Convert Schema to PostgreSQL (8 hours)

**Task**: Create `schema_postgresql.sql`

#### Step 5.1: Export Current Schema

```bash
# Export SQLite schema
sqlite3 bot/etlegacy_production.db .schema > schema_sqlite.sql
```

#### Step 5.2: Convert Schema

**Create**: `schema_postgresql.sql`

**Conversion Rules**:
1. `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
2. `TEXT` → `VARCHAR(255)` or `TEXT` (review case-by-case)
3. `datetime('now')` → `CURRENT_TIMESTAMP`
4. Add `NOT NULL` where appropriate
5. Add indexes

**Example Conversion**:

```sql
-- BEFORE (SQLite)
CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guid TEXT NOT NULL,
    player_name TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(guid)
);

-- AFTER (PostgreSQL)
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    guid VARCHAR(50) NOT NULL UNIQUE,
    player_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_players_guid ON players(guid);
CREATE INDEX idx_players_name ON players(player_name);
```

#### Step 5.3: Test Schema Creation

```bash
# Install PostgreSQL locally first (see Phase 8)

# Create test database
createdb etlegacy_test

# Run schema
psql etlegacy_test < schema_postgresql.sql

# Verify tables
psql etlegacy_test -c "\dt"
```

---

### ⏳ Phase 6: Create Migration Script (8 hours)

**Task**: Create `tools/migrate_to_postgresql.py`

**Purpose**: Export all data from SQLite and import to PostgreSQL

#### Migration Script Structure

```python
#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script
Exports all data from SQLite and imports to PostgreSQL with validation.
"""
import asyncio
import sqlite3
import asyncpg
from datetime import datetime

class DatabaseMigration:
    def __init__(self, sqlite_path, postgres_config):
        self.sqlite_path = sqlite_path
        self.postgres_config = postgres_config
        self.tables = [
            'players',
            'rounds',
            'player_comprehensive_stats',
            'discord_links',
            'player_aliases',
            'session_teams',
            # ... add all tables
        ]
    
    async def export_sqlite_data(self):
        """Export all data from SQLite."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        data = {}
        for table in self.tables:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            data[table] = [dict(row) for row in rows]
            print(f"✅ Exported {len(data[table])} rows from {table}")
        
        conn.close()
        return data
    
    async def import_to_postgresql(self, data):
        """Import data to PostgreSQL."""
        conn = await asyncpg.connect(**self.postgres_config)
        
        for table, rows in data.items():
            if not rows:
                continue
            
            # Build INSERT query
            columns = rows[0].keys()
            placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
            query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({placeholders})
            """
            
            # Insert in batches
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                await conn.executemany(query, [tuple(row.values()) for row in batch])
            
            print(f"✅ Imported {len(rows)} rows to {table}")
        
        await conn.close()
    
    async def validate_migration(self):
        """Validate row counts match."""
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        pg_conn = await asyncpg.connect(**self.postgres_config)
        
        mismatches = []
        for table in self.tables:
            sqlite_count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            pg_count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            
            if sqlite_count != pg_count:
                mismatches.append(f"{table}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
            else:
                print(f"✅ {table}: {sqlite_count} rows match")
        
        sqlite_conn.close()
        await pg_conn.close()
        
        if mismatches:
            print("❌ VALIDATION FAILED:")
            for mismatch in mismatches:
                print(f"  {mismatch}")
            return False
        
        print("✅ All tables validated successfully")
        return True
    
    async def run(self):
        """Run full migration."""
        print("🚀 Starting migration...")
        print(f"📁 SQLite: {self.sqlite_path}")
        print(f"🐘 PostgreSQL: {self.postgres_config['host']}:{self.postgres_config['database']}")
        
        # Export
        data = await self.export_sqlite_data()
        
        # Import
        await self.import_to_postgresql(data)
        
        # Validate
        success = await self.validate_migration()
        
        if success:
            print("✅ Migration complete!")
        else:
            print("❌ Migration failed validation")
            return False
        
        return True

async def main():
    migration = DatabaseMigration(
        sqlite_path='bot/etlegacy_production.db',
        postgres_config={
            'host': 'localhost',
            'port': 5432,
            'database': 'etlegacy_stats',
            'user': 'etlegacy',
            'password': 'your_password'
        }
    )
    
    await migration.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### ⏳ Phase 7: Testing with SQLite (6 hours)

**Goal**: Ensure adapter doesn't break existing functionality

**Steps**:
1. Set `DATABASE_TYPE=sqlite` in config
2. Run bot locally
3. Test ALL commands systematically
4. Check logs for errors
5. Monitor performance

**Test Checklist**:
```
[ ] Bot starts successfully
[ ] !help command works
[ ] !last command shows sessions
[ ] !stats command shows player stats
[ ] !leaderboard shows rankings
[ ] !link/!unlink for Discord linking
[ ] Stats auto-posting works
[ ] SSH monitoring works (if enabled)
[ ] No memory leaks over 1 hour
[ ] Performance is same as before
```

---

### ⏳ Phase 8: Install PostgreSQL Locally (2 hours)

**Platform-specific instructions**:

#### Windows:
```powershell
# Download PostgreSQL installer
# https://www.postgresql.org/download/windows/

# Or use Chocolatey
choco install postgresql

# Or use Windows Subsystem for Linux (WSL)
wsl --install
# Then follow Linux instructions in WSL
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### macOS:
```bash
# Using Homebrew
brew install postgresql
brew services start postgresql
```

#### Create Database:
```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE etlegacy_stats;
CREATE USER etlegacy WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE etlegacy_stats TO etlegacy;
\q
```

#### Test Connection:
```bash
psql -h localhost -U etlegacy -d etlegacy_stats
# Enter password when prompted
# Should see: etlegacy_stats=#
```

---

### ⏳ Phase 9: Test with Local PostgreSQL (10 hours)

**Steps**:

1. **Create Schema**:
```bash
psql -h localhost -U etlegacy -d etlegacy_stats < schema_postgresql.sql
```

2. **Run Migration Script**:
```bash
python tools/migrate_to_postgresql.py
```

3. **Update Config**:
```bash
# In .env or bot_config.json
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy_stats
POSTGRES_USER=etlegacy
POSTGRES_PASSWORD=your_secure_password
```

4. **Start Bot**:
```bash
python bot/ultimate_bot.py
```

5. **Test Everything**:
- Run through entire test checklist
- Check PostgreSQL logs for errors
- Monitor connection pool
- Test under load

---

### ⏳ Phase 10: VPS Setup (Variable - future)

This phase happens when you're ready to deploy to production.

See `VPS_MIGRATION_SUMMARY.md` for VPS selection and setup.

---

### ⏳ Phase 11: Production Migration (3 hours)

**Day-of-migration checklist**: See Phase 3 of `VPS_MIGRATION_SUMMARY.md`

---

### ⏳ Phase 12: Post-Migration Monitoring (1 week)

**Daily tasks**:
- Check error logs
- Monitor connection pool
- Verify data integrity
- Check performance metrics
- Collect user feedback

---

## 🚨 Troubleshooting Guide

### Issue: "Pool exhausted" error

**Symptom**: Bot stops responding, logs show "pool exhausted"

**Cause**: Connection pool is full

**Fix**:
```python
# In bot/config.py, increase pool size
POSTGRES_MAX_POOL=50  # Increase from 20
```

### Issue: "column does not exist"

**Symptom**: Query fails with column not found

**Cause**: Schema mismatch

**Fix**:
```sql
-- Check actual columns
\d player_comprehensive_stats

-- Compare with expected schema
```

### Issue: Type mismatch errors

**Symptom**: "cannot compare TEXT with INTEGER"

**Cause**: PostgreSQL is stricter with types

**Fix**:
```python
# Ensure parameter types match
# WRONG:
params = (str(player_id),)  # ID is INTEGER in DB

# RIGHT:
params = (int(player_id),)
```

---

## 📊 Progress Tracking

Update this section as you complete phases:

```
✅ Phase 1: Database Abstraction Layer (2 hours) - COMPLETE
✅ Phase 2: Bot Configuration System (1 hour) - COMPLETE
🟡 Phase 3: Update Bot Core (12 hours) - IN PROGRESS
⏳ Phase 4: Update Cogs (15 hours) - NOT STARTED
⏳ Phase 5: Update Automation (4 hours) - NOT STARTED
⏳ Phase 6: Convert Schema (8 hours) - NOT STARTED
⏳ Phase 7: Migration Script (8 hours) - NOT STARTED
⏳ Phase 8: Test with SQLite (6 hours) - NOT STARTED
⏳ Phase 9: Install PostgreSQL (2 hours) - NOT STARTED
⏳ Phase 10: Test with PostgreSQL (10 hours) - NOT STARTED
⏳ Phase 11: VPS Setup (Variable) - FUTURE
⏳ Phase 12: Production Migration (3 hours) - FUTURE
⏳ Phase 13: Monitoring (1 week) - FUTURE

Total Completed: 3 hours / 80 hours (4%)
```

---

## 🎓 Learning Resources

**PostgreSQL Documentation**:
- https://www.postgresql.org/docs/
- https://www.postgresql.org/docs/current/tutorial.html

**asyncpg Documentation**:
- https://magicstack.github.io/asyncpg/

**SQL Syntax Differences**:
- https://wiki.postgresql.org/wiki/Things_to_find_out_about_when_moving_from_MySQL

---

**Last Updated**: November 4, 2025  
**Next Review**: After Phase 3 completion  
**Maintained By**: Development Team
