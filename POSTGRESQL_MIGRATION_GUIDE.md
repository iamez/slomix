# PostgreSQL Migration Guide
**ET:Legacy Discord Bot - SQLite to PostgreSQL Migration**

## 📋 Overview

All Python code has been successfully migrated to use the database adapter pattern. The bot works perfectly with SQLite. This guide covers migrating to PostgreSQL.

## ✅ What's Done

- ✅ All 8 cogs migrated
- ✅ All automation services migrated  
- ✅ Database adapter pattern implemented
- ✅ Opus's datetime fixes applied
- ✅ Bot tested with SQLite - ZERO regressions
- ✅ PostgreSQL schema created (`tools/schema_postgresql.sql`)
- ✅ Migration script created (`tools/migrate_to_postgresql.py`)

## 🚀 Migration Steps

### Step 1: Install PostgreSQL Locally (Windows)

1. Download PostgreSQL installer:
   https://www.postgresql.org/download/windows/

2. Run installer:
   - Install PostgreSQL 16.x or newer
   - Remember the postgres user password
   - Default port 5432 is fine

3. Add PostgreSQL to PATH (installer usually does this)

### Step 2: Create Database

```powershell
# Open Command Prompt or PowerShell
psql -U postgres

# In psql prompt:
CREATE DATABASE etlegacy;
CREATE USER etlegacy_user WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE etlegacy TO etlegacy_user;
\q
```

### Step 3: Apply Schema

```powershell
cd C:\Users\seareal\Documents\stats
psql -U etlegacy_user -d etlegacy -f tools/schema_postgresql.sql
```

### Step 4: Update Configuration

Edit `config.json`:

```json
{
  "database_type": "sqlite",
  "sqlite_path": "bot/etlegacy_production.db",
  "postgresql_host": "localhost",
  "postgresql_port": 5432,
  "postgresql_database": "etlegacy",
  "postgresql_user": "etlegacy_user",
  "postgresql_password": "your_secure_password_here"
}
```

**Note:** Keep `database_type` as `"sqlite"` for now!

### Step 5: Run Migration Script

```powershell
# Make sure bot is stopped
# Make a backup first!
cp bot/etlegacy_production.db bot/etlegacy_production.backup.db

# Run migration
python tools/migrate_to_postgresql.py
```

The script will:
- Show what will be migrated
- Ask for confirmation
- Copy all data in batches
- Verify row counts
- Report success/failures

**Expected output:**
```
✅ rounds: SQLite=X, PostgreSQL=X
✅ player_comprehensive_stats: SQLite=X, PostgreSQL=X
✅ weapon_comprehensive_stats: SQLite=X, PostgreSQL=X
✅ player_aliases: SQLite=X, PostgreSQL=X
✅ player_links: SQLite=X, PostgreSQL=X
✅ session_teams: SQLite=X, PostgreSQL=X
✅ processed_files: SQLite=X, PostgreSQL=X
```

### Step 6: Switch to PostgreSQL

Edit `config.json`:

```json
{
  "database_type": "postgresql",
  ...
}
```

### Step 7: Test Bot

```powershell
.\restart_bot.bat
```

Check startup logs for:
```
✅ Configuration loaded: database_type=postgresql
✅ PostgreSQL Adapter initialized
✅ Connected to database: localhost:5432/etlegacy
```

### Step 8: Test All Commands

Test in Discord:
- `!help` - Bot responds
- `!link` - Linking works
- `!stats <player>` - Stats display correctly
- `!leaderboard` - Leaderboard works
- `!last` - Last session works
- `!session` - Session commands work

### Step 9: Monitor

Let bot run for a few hours monitoring logs for any issues.

## 🔧 Troubleshooting

### "Cannot connect to PostgreSQL"
```powershell
# Check PostgreSQL is running
psql -U postgres -c "SELECT version();"

# Check firewall allows port 5432
# Check pg_hba.conf allows local connections
```

### "Row counts don't match"
- Check migration script output
- Look for error messages
- Re-run migration after fixing issues

### "Bot errors with PostgreSQL"
- Switch back to SQLite temporarily:
  ```json
  "database_type": "sqlite"
  ```
- Check logs for specific errors
- Verify schema was applied correctly

## 🎯 VPS Deployment (Future)

Once local PostgreSQL testing passes:

1. Install PostgreSQL on VPS
2. Copy schema: `scp tools/schema_postgresql.sql user@vps:/path/`
3. Apply schema on VPS
4. Run migration script (point to VPS)
5. Update bot config on VPS
6. Monitor for 1 week

## 📊 Performance Benefits

PostgreSQL advantages:
- ✅ Better concurrent access
- ✅ Improved query performance
- ✅ Automatic VACUUM (maintenance)
- ✅ Better index support
- ✅ Production-grade reliability
- ✅ Easier backups (pg_dump)

## 🔄 Rollback Plan

If PostgreSQL has issues:

1. Stop bot
2. Edit config.json:
   ```json
   "database_type": "sqlite"
   ```
3. Restart bot
4. Bot continues with SQLite (no data loss)

## 📝 Files Created

- `tools/schema_postgresql.sql` - PostgreSQL schema
- `tools/schema_sqlite.sql` - SQLite schema export  
- `tools/migrate_to_postgresql.py` - Migration script
- `tools/export_schema.py` - Schema export utility
- `POSTGRESQL_MIGRATION_GUIDE.md` - This guide

## ✅ Success Criteria

Before considering migration complete:

- [ ] PostgreSQL installed locally
- [ ] Database and schema created
- [ ] Migration script runs successfully
- [ ] Row counts verified (all match)
- [ ] Bot starts with `database_type=postgresql`
- [ ] All commands tested and working
- [ ] Bot runs stable for 24+ hours
- [ ] Performance is equal or better
- [ ] Backup strategy in place

## 🎉 You're Ready!

Your bot is fully prepared for PostgreSQL migration. The adapter pattern makes switching seamless - just update config and restart!
