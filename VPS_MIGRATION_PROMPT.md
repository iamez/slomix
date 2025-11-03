# 🚀 VPS Infrastructure Migration - AI Agent Prompt

## 📋 Project Overview
Migrate ET:Legacy Discord Bot from single-machine SQLite setup to multi-VPS PostgreSQL infrastructure with separate database and bot servers.

## 🎯 Architecture Goals

### Current Setup (Single Machine)
```
┌─────────────────────────────────────┐
│     Local PC/Laptop                 │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Discord Bot                │  │
│  │   - ultimate_bot.py          │  │
│  │   - SSH to game server       │  │
│  │   - File processing          │  │
│  │   - SQLite (local file)      │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   SQLite Database            │  │
│  │   - etlegacy_production.db   │  │
│  │   - Local file only          │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Target Setup (Multi-VPS)
```
┌─────────────────────────────────────────────────────────────┐
│                     VPS 1: Database Server                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │   PostgreSQL 15+                                    │  │
│  │   - Production database                             │  │
│  │   - Automated backups                               │  │
│  │   - SSL/TLS encryption                              │  │
│  │   - Connection pooling                              │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ Secure connection (SSL/SSH tunnel)
                            │
┌─────────────────────────────────────────────────────────────┐
│                     VPS 2: Bot Server                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │   Discord Bot (Python)                              │  │
│  │   - ultimate_bot.py                                 │  │
│  │   - PostgreSQL client (asyncpg)                     │  │
│  │   - SSH to game server                              │  │
│  │   - File processing                                 │  │
│  │   - Systemd service (auto-restart)                  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ SSH for stats files
                            │
┌─────────────────────────────────────────────────────────────┐
│                   Game Server                               │
│  - ET:Legacy dedicated server                              │
│  - Generates stats files                                   │
│  - SSH access for bot                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Dev Environments (PC + Laptop)                 │
│                                                             │
│  - Connect to VPS Database (read-only or dev schema)       │
│  - Test bot code locally                                   │
│  - Deploy to VPS when ready                                │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Technical Requirements

### 1. Database Migration (SQLite → PostgreSQL)

#### Current State
- **Database**: SQLite 3
- **Library**: `aiosqlite` (async SQLite)
- **Connection**: `async with aiosqlite.connect(self.db_path) as db:`
- **Location**: Local file `bot/etlegacy_production.db`
- **Files using SQLite**:
  - `bot/ultimate_bot.py` (10+ connections)
  - `bot/cogs/last_session_cog.py` (1 connection)
  - `bot/core/team_history.py` (uses sqlite3)
  - `database_manager.py` (main database tool)

#### Target State
- **Database**: PostgreSQL 15+
- **Library**: `asyncpg` (async PostgreSQL, fastest Python driver)
- **Connection**: `async with asyncpg.create_pool(DATABASE_URL) as pool:`
- **Location**: VPS 1 (remote server)
- **Connection String**: `postgresql://user:pass@vps1.domain.com:5432/etlegacy_stats`

#### Required Changes
1. **Replace imports**:
   ```python
   # OLD
   import sqlite3
   import aiosqlite
   
   # NEW
   import asyncpg
   ```

2. **Update connection pattern**:
   ```python
   # OLD (SQLite)
   async with aiosqlite.connect(self.db_path) as db:
       cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
       row = await cursor.fetchone()
   
   # NEW (PostgreSQL)
   async with self.db_pool.acquire() as conn:
       row = await conn.fetchrow("SELECT * FROM sessions WHERE id = $1", session_id)
   ```

3. **SQL Syntax Changes**:
   - Placeholders: `?` → `$1, $2, $3`
   - Auto-increment: `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
   - Date functions: `datetime('now')` → `NOW()`
   - String concat: `||` works in both
   - PRAGMA commands: Remove (PostgreSQL doesn't use PRAGMA)

4. **Schema Migration**:
   - Convert `bot/schema.sql` from SQLite to PostgreSQL syntax
   - Data migration script (export SQLite → import PostgreSQL)
   - Preserve all indexes and constraints

### 2. Code Files Requiring Updates

#### Critical Files (MUST UPDATE)
1. **`bot/ultimate_bot.py`** (~4000 lines)
   - 10+ `aiosqlite.connect()` calls
   - Replace with connection pool
   - Update all SQL queries (? → $1)
   - Remove SQLite-specific error handling
   
2. **`bot/cogs/last_session_cog.py`**
   - 1 connection for last session queries
   - Update SQL syntax
   
3. **`bot/core/team_history.py`**
   - Uses `sqlite3` for team tracking
   - Switch to asyncpg
   
4. **`database_manager.py`** (~1100 lines)
   - Main database tool
   - Handles imports, rebuilds, validation
   - Critical for data integrity

5. **`bot/schema.sql`**
   - Convert to PostgreSQL DDL
   - Test thoroughly before migration

#### Supporting Files (REVIEW & UPDATE)
- `tools/stopwatch_scoring.py` - May query database
- Any analysis scripts that directly access DB

### 3. New Dependencies

#### Add to `requirements.txt`:
```
# PostgreSQL async driver (REQUIRED)
asyncpg>=0.29.0

# Connection pooling (optional, asyncpg has built-in)
# sqlalchemy[asyncio]>=2.0.0  # If you want ORM

# SSL support for secure connections
cryptography>=41.0.0

# Environment-based config (already have)
python-dotenv>=1.0.0
```

#### Remove from `requirements.txt`:
```
aiosqlite>=0.19.0  # No longer needed
```

### 4. Environment Configuration

#### Update `.env.example`:
```bash
# ==================
# DATABASE SETTINGS (PostgreSQL)
# ==================
DATABASE_URL=postgresql://etlegacy_user:secure_password@vps1.domain.com:5432/etlegacy_stats
DATABASE_HOST=vps1.domain.com
DATABASE_PORT=5432
DATABASE_NAME=etlegacy_stats
DATABASE_USER=etlegacy_user
DATABASE_PASSWORD=secure_password_here
DATABASE_SSL_MODE=require  # require, verify-ca, or verify-full
DATABASE_POOL_MIN=5
DATABASE_POOL_MAX=20

# ==================
# LEGACY (For backwards compatibility / dev)
# ==================
# Uncomment to use local SQLite in dev:
# DATABASE_PATH=bot/etlegacy_production.db
# DATABASE_TYPE=sqlite  # or 'postgresql'
```

### 5. Database Abstraction Layer

#### Create `bot/core/database.py`:
```python
"""
Database abstraction layer for ET:Legacy bot.
Supports both SQLite (dev) and PostgreSQL (production).
"""
import os
import asyncpg
from typing import Optional

class DatabasePool:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.db_url = os.getenv("DATABASE_URL")
    
    async def initialize(self):
        """Create connection pool on bot startup."""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=5,
            max_size=20,
            command_timeout=60,
            ssl='require'  # Force SSL
        )
    
    async def close(self):
        """Close connection pool on bot shutdown."""
        if self.pool:
            await self.pool.close()
    
    def acquire(self):
        """Get a database connection from pool."""
        return self.pool.acquire()
```

### 6. VPS Setup Requirements

#### VPS 1: Database Server
```bash
# OS: Ubuntu 22.04 LTS
# RAM: 4GB minimum (8GB recommended)
# Storage: 50GB SSD
# Specs needed for:
# - PostgreSQL server
# - Automated backups
# - Monitoring

# Install PostgreSQL 15
sudo apt update
sudo apt install postgresql-15 postgresql-contrib-15

# Configure PostgreSQL
# - Create database: etlegacy_stats
# - Create user: etlegacy_user
# - Set secure password
# - Enable SSL/TLS
# - Configure pg_hba.conf for remote connections
# - Set up automated backups (pg_dump daily)
# - Install monitoring (pgAdmin or similar)

# Firewall rules
# - Allow port 5432 from Bot VPS only
# - Deny all other connections
# - SSH on non-standard port (security)
```

#### VPS 2: Bot Server
```bash
# OS: Ubuntu 22.04 LTS
# RAM: 2GB minimum (4GB recommended)
# Storage: 20GB SSD
# Specs needed for:
# - Python 3.11+
# - Discord bot
# - SSH client (for game server)

# Install Python and dependencies
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Create systemd service for bot
# - Auto-start on boot
# - Auto-restart on crash
# - Logging to journalctl

# Install monitoring
# - Uptime monitoring
# - Error alerting
# - Resource usage tracking

# Firewall rules
# - Allow outbound HTTPS (Discord API)
# - Allow outbound to Database VPS
# - Allow SSH to Game Server
# - Deny all inbound (except SSH for management)
```

### 7. Data Migration Strategy

#### Phase 1: Preparation (NO DOWNTIME)
1. Set up VPS 1 with PostgreSQL
2. Create database schema
3. Test connection from Bot VPS
4. Run migration test with copy of data

#### Phase 2: Migration (2-hour downtime window)
1. Stop bot on local machine
2. Export SQLite data to SQL dump
3. Import data into PostgreSQL
4. Verify data integrity (row counts, checksums)
5. Deploy bot to VPS 2
6. Test all commands
7. Monitor for 1 hour

#### Phase 3: Cleanup
1. Keep SQLite backup for 1 week
2. Document rollback procedure
3. Update all documentation
4. Inform users of new infrastructure

### 8. Rollback Plan

If migration fails:
```bash
# Option A: Instant rollback (within 2 hours)
# - Stop bot on VPS 2
# - Start bot on local machine with SQLite
# - Announce temporary issue

# Option B: Partial rollback
# - Keep PostgreSQL database
# - Run bot locally, connect to remote DB
# - Debug connection issues

# Option C: Full rollback with data loss
# - Restore SQLite from backup
# - Re-import recent sessions
# - Start bot locally
```

### 9. Testing Checklist

Before going live:
- [ ] Connection pool works
- [ ] All queries return correct data
- [ ] Discord commands work
- [ ] File processing works
- [ ] Stats posting works
- [ ] Database writes succeed
- [ ] Error handling works
- [ ] Bot auto-restarts on crash
- [ ] Backups are running
- [ ] Monitoring is active
- [ ] Dev environment can connect
- [ ] Performance is acceptable (< 100ms queries)

### 10. Security Considerations

- [ ] PostgreSQL user has minimal permissions
- [ ] SSL/TLS enabled for database connections
- [ ] Firewall rules restrict access
- [ ] SSH keys for VPS access (no passwords)
- [ ] `.env` file never committed to git
- [ ] Database backups encrypted
- [ ] VPS auto-updates enabled
- [ ] Fail2ban installed (brute-force protection)
- [ ] Monitoring for suspicious activity

## 📊 Estimated Complexity

### High Complexity (Significant Rewrites)
- **`bot/ultimate_bot.py`**: 10+ connection points, all queries need updating
- **`database_manager.py`**: Core import logic, SQL syntax changes
- **Schema migration**: Data integrity critical

### Medium Complexity
- **`bot/cogs/last_session_cog.py`**: Single connection, straightforward
- **`bot/core/team_history.py`**: Team tracking logic
- **VPS setup**: Infrastructure as code

### Low Complexity
- **Environment configuration**: Copy `.env`, update values
- **Requirements**: Add/remove packages
- **Documentation**: Update deployment guides

## ⚠️ Critical Risks

1. **Data Loss**: SQLite → PostgreSQL migration could corrupt data
   - **Mitigation**: Multiple backups, test migration first
   
2. **Query Performance**: PostgreSQL behaves differently than SQLite
   - **Mitigation**: Index optimization, connection pooling
   
3. **Connection Issues**: Network between VPSs could be unstable
   - **Mitigation**: Retry logic, connection pooling, health checks
   
4. **Downtime**: Migration requires bot to be offline
   - **Mitigation**: Schedule during low-usage time, announce in advance

## 🎯 Success Criteria

✅ Bot runs 24/7 on VPS 2
✅ Database on VPS 1 with automated backups
✅ Dev environments can connect for testing
✅ Query performance < 100ms for most queries
✅ Zero data loss during migration
✅ Uptime > 99.5% after migration
✅ Easy to deploy updates (git pull + restart)

## 📚 Reference Documentation

- **asyncpg docs**: https://magicstack.github.io/asyncpg/
- **PostgreSQL migration guide**: https://wiki.postgresql.org/wiki/Converting_from_other_Databases_to_PostgreSQL
- **Discord.py + asyncpg example**: https://gist.github.com/EvieePy/d78c061a4798ae81be9825468fe146be
- **Systemd service tutorial**: https://www.digitalocean.com/community/tutorials/how-to-use-systemctl-to-manage-systemd-services-and-units

---

## 🤖 AI Agent Instructions

When implementing this migration, follow these priorities:

1. **Create abstraction layer FIRST** (`bot/core/database.py`)
2. **Test with both SQLite and PostgreSQL** (use env var to switch)
3. **Update files incrementally** (one at a time, test after each)
4. **Preserve existing functionality** (don't add features during migration)
5. **Document every change** (commit messages should be detailed)
6. **Create migration script** (automate SQLite → PostgreSQL)
7. **Write rollback script** (in case of emergency)

**Do NOT**:
- Change bot logic during migration
- Skip testing any file
- Assume queries will work without testing
- Delete SQLite code until PostgreSQL is proven stable

**Questions to ask before starting**:
1. Should we support both SQLite (dev) and PostgreSQL (prod)?
2. Do we need ORM (SQLAlchemy) or raw SQL (asyncpg)?
3. What's the downtime tolerance for migration?
4. Who has access to VPS servers for setup?
5. What's the budget for VPS hosting?
