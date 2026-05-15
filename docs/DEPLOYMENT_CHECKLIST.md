# VPS Deployment Checklist

## ✅ Pre-Deployment Verification (Nov 6, 2025)

### Critical Files Present in GitHub

- [x] `bot/ultimate_bot.py` (~2,100 lines after mega-audit cog-mixin split) - Main bot entry point
- [x] `bot/community_stats_parser.py` - Stats file parser **[FIXED]**
- [x] `bot/config.py` - Configuration loader
- [x] `bot/logging_config.py` - Logging setup
- [x] `bot/services/session_graph_generator.py` - Graph generation (replaced legacy `bot/image_generator.py`)
- [x] `postgresql_database_manager.py` - Database CLI tool
- [x] `tools/stopwatch_scoring.py` - Stopwatch calculator
- (Note: `tools/postgresql_db_manager.py` and other one-time migration helpers are now gitignored — they live on legacy hosts but are not part of a fresh clone. Use the root-level `postgresql_database_manager.py` instead.)
- [x] `requirements.txt` - All dependencies **[FIXED]**
- [x] `.env.example` - Environment template
- [x] `.gitignore` - Proper exclusions **[FIXED]**
- [x] `README.md` - Complete setup guide

### Cogs Present (20 total under `bot/cogs/`; representative)

- [x] `bot/cogs/admin_cog.py`
- [x] `bot/cogs/stats_cog.py`
- [x] `bot/cogs/leaderboard_cog.py`
- [x] `bot/cogs/last_session_cog.py`
- [x] `bot/cogs/session_cog.py`
- [x] `bot/cogs/session_management_cog.py`
- [x] `bot/cogs/link_cog.py`
- [x] `bot/cogs/sync_cog.py`
- [x] `bot/cogs/team_cog.py`
- [x] `bot/cogs/team_management_cog.py`
- [x] `bot/cogs/automation_commands.py`
- [x] `bot/cogs/server_control.py`

Full list: `ls bot/cogs/*.py` (or see `bot/cogs/CLAUDE.md`).

### Core Modules Present (18 total under `bot/core/`; representative)

- [x] `bot/core/database_adapter.py`
- [x] `bot/core/team_manager.py`
- [x] `bot/core/substitution_detector.py`
- [x] `bot/core/achievement_system.py`
- [x] `bot/core/season_manager.py`
- [x] `bot/core/stats_cache.py`

Full list: `ls bot/core/*.py` (or see `bot/core/CLAUDE.md`).

### Automation Services Present

- [x] `bot/services/automation/database_maintenance.py`
- [x] `bot/services/automation/health_monitor.py`
- [x] `bot/services/automation/metrics_logger.py`
- [x] `bot/services/automation/INTEGRATION_GUIDE.md` (note: doc, not a service module)

(SSH monitoring lives in `bot/automation/ssh_handler.py` + `file_tracker.py`,
not under `bot/services/automation/`.)

### Documentation Complete

- [x] `docs/TECHNICAL_OVERVIEW.md` - Complete pipeline & architecture
- [x] `docs/DATA_PIPELINE.html` - Visual diagram
- [x] `docs/FIELD_MAPPING.html` - Field reference
- [x] `docs/SYSTEM_ARCHITECTURE.md` - Historical docs

---

## 🐛 Issues Found & Fixed

### Issue 1: Parser Missing ❌ → ✅

**Problem:** `bot/community_stats_parser.py` was excluded by .gitignore
**Impact:** Bot would crash on startup (import error)
**Fix:** Removed from .gitignore exclusions, force-added to git
**Status:** ✅ FIXED

### Issue 2: Corrupted requirements.txt ❌ → ✅

**Problem:** requirements.txt had merge conflict markers and duplicates
**Impact:** `pip install -r requirements.txt` would fail
**Fix:** Recreated clean requirements.txt with proper formatting
**Status:** ✅ FIXED

### Issue 3: .gitignore Too Aggressive ❌ → ✅

**Problem:** .gitignore excluded essential parser file
**Impact:** Missing critical 875-line stats parser
**Fix:** Updated .gitignore to only exclude actual test/helper files
**Status:** ✅ FIXED

---

## 🚀 VPS Deployment Steps

### 1. Clone Repository

```bash
git clone https://github.com/iamez/slomix.git
cd slomix
# Default branch is `main`; the historical `vps-network-migration`
# branch referenced in older versions of this guide no longer exists.
```

### 2. Verify Files

```bash
# Check critical files exist
ls bot/ultimate_bot.py
ls bot/community_stats_parser.py
ls postgresql_database_manager.py
ls requirements.txt

# Sanity check tracked file count (currently ~1,100)
git ls-files | wc -l
```

### 3. Setup Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 4. Setup PostgreSQL

```bash
sudo apt install postgresql postgresql-contrib

# Create user first, then DB owned by that user, then grant privileges.
# (Matches the bootstrap pattern in install.sh — running `createdb`
# before `createuser` leaves the DB owned by `postgres` and the app
# user cannot connect.)
sudo -u postgres createuser etlegacy_user -P            # prompts for password
sudo -u postgres createdb -O etlegacy_user etlegacy
sudo -u postgres psql -d etlegacy -c "GRANT ALL ON SCHEMA public TO etlegacy_user;"
```

### 5. Configure Environment

```bash
cp .env.example .env
nano .env
```

Edit .env (key names must match `.env.example`; see also `docs/CLAUDE.md`):

```env
DISCORD_BOT_TOKEN=your_actual_token
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=your_secure_password_here
LOCAL_STATS_PATH=/path/to/stats/files
AUTOMATION_ENABLED=true
```

### 6. Initialize Database

```bash
python postgresql_database_manager.py
# Select: 1 - Initialize schema
```

### 7. Test Bot

```bash
python bot/ultimate_bot.py
```

Should see:

```text

Loaded extension 'admin'
Loaded extension 'stats'
Loaded extension 'leaderboard'
...
Bot is ready!

```

### 8. Setup Systemd Service

```bash
sudo nano /etc/systemd/system/et-bot.service
```

```ini
[Unit]
Description=Enemy Territory Stats Bot
After=network.target postgresql.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/slomix
Environment="PATH=/path/to/slomix/.venv/bin"
ExecStart=/path/to/slomix/.venv/bin/python bot/ultimate_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable et-bot
sudo systemctl start et-bot
sudo systemctl status et-bot
```

---

## ✅ Final Verification Checklist

Before deploying, verify:

- [ ] All 48+ files present in `git ls-files`
- [ ] `bot/community_stats_parser.py` exists (875 lines)
- [ ] `requirements.txt` is clean (no merge conflicts)
- [ ] `.env.example` has all required variables
- [ ] PostgreSQL connection credentials ready
- [ ] Discord bot token ready
- [ ] Stats file path configured
- [ ] All 20 cogs load without errors
- [ ] Database initializes successfully
- [ ] Bot connects to Discord

---

## 📊 Repository Stats

- **Main Bot:** ~2,100 lines (after cog-mixin split)
- **Parser:** ~1,450 lines
- **Cogs:** 20 modules
- **Core Systems:** 18 modules
- **Automation:** 4+ services
- **Documentation:** multiple guides under `docs/`
- **Dependencies:** see `requirements.txt`

---

## 🔒 Security Reminders

**NEVER commit:**

- Discord bot tokens
- Database passwords
- `.env` files
- Production configs

**Use .env for:**

- `DISCORD_BOT_TOKEN`
- `POSTGRES_PASSWORD`
- All sensitive credentials

---

## 📞 Troubleshooting

### Bot won't start

```bash
# Check dependencies
pip list | grep discord
pip list | grep asyncpg

# Check imports
python -c "from bot.core.database_adapter import create_adapter"
python -c "from tools.stopwatch_scoring import StopwatchScoring"
python -c "import bot.community_stats_parser"
```

### Database connection fails

```bash
# Test PostgreSQL
psql -h localhost -U etlegacy_user -d etlegacy

# Check service
sudo systemctl status postgresql
```

### Missing files

```bash
# Re-clone repository (default branch is `main`)
git clone https://github.com/iamez/slomix.git
cd slomix

# Verify critical files
ls bot/community_stats_parser.py
ls postgresql_database_manager.py
```

---

**Deployment Ready:** ✅ YES (after fixes applied)
**Last Verified:** November 6, 2025
**Branch:** main
