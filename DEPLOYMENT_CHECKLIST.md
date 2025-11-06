# VPS Deployment Checklist

## ✅ Pre-Deployment Verification (Nov 6, 2025)

### Critical Files Present in GitHub
- [x] `bot/ultimate_bot.py` (4,452 lines) - Main bot entry point
- [x] `bot/community_stats_parser.py` (875 lines) - Stats file parser **[FIXED]**
- [x] `bot/config.py` - Configuration loader
- [x] `bot/logging_config.py` - Logging setup
- [x] `bot/image_generator.py` - Graph generation
- [x] `postgresql_database_manager.py` - Database CLI tool
- [x] `tools/stopwatch_scoring.py` - Stopwatch calculator
- [x] `tools/postgresql_db_manager.py` - PostgreSQL utilities
- [x] `requirements.txt` - All dependencies **[FIXED]**
- [x] `.env.example` - Environment template
- [x] `.gitignore` - Proper exclusions **[FIXED]**
- [x] `README.md` - Complete setup guide

### All 14 Cogs Present
- [x] `bot/cogs/admin_cog.py`
- [x] `bot/cogs/stats_cog.py`
- [x] `bot/cogs/leaderboard_cog.py`
- [x] `bot/cogs/last_session_cog.py` (111KB)
- [x] `bot/cogs/session_cog.py`
- [x] `bot/cogs/session_management_cog.py`
- [x] `bot/cogs/link_cog.py`
- [x] `bot/cogs/sync_cog.py`
- [x] `bot/cogs/team_cog.py`
- [x] `bot/cogs/team_management_cog.py`
- [x] `bot/cogs/automation_commands.py`
- [x] `bot/cogs/server_control.py`
- [x] `bot/cogs/synergy_analytics.py`
- [x] `bot/cogs/synergy_analytics_fixed.py`

### All 9 Core Modules Present
- [x] `bot/core/database_adapter.py`
- [x] `bot/core/team_manager.py`
- [x] `bot/core/advanced_team_detector.py`
- [x] `bot/core/team_detector_integration.py`
- [x] `bot/core/substitution_detector.py`
- [x] `bot/core/team_history.py`
- [x] `bot/core/achievement_system.py`
- [x] `bot/core/season_manager.py`
- [x] `bot/core/stats_cache.py`

### All 4 Automation Services Present
- [x] `bot/services/automation/ssh_monitor.py`
- [x] `bot/services/automation/database_maintenance.py`
- [x] `bot/services/automation/health_monitor.py`
- [x] `bot/services/automation/metrics_logger.py`
- [x] `bot/services/automation/INTEGRATION_GUIDE.md`

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
git checkout vps-network-migration
```

### 2. Verify Files
```bash
# Check critical files exist
ls bot/ultimate_bot.py
ls bot/community_stats_parser.py
ls postgresql_database_manager.py
ls requirements.txt

# Count files (should be 49+)
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
sudo -u postgres createdb et_stats
sudo -u postgres createuser et_bot -P
# Enter secure password
```

### 5. Configure Environment
```bash
cp .env.example .env
nano .env
```

Edit .env:
```env
DISCORD_TOKEN=your_actual_token
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=et_stats
POSTGRES_USER=et_bot
POSTGRES_PASSWORD=your_password
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
```
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
- [ ] All 14 cogs load without errors
- [ ] Database initializes successfully
- [ ] Bot connects to Discord

---

## 📊 Repository Stats

- **Total Files:** 49
- **Main Bot:** 4,452 lines
- **Parser:** 875 lines
- **Cogs:** 14 modules
- **Core Systems:** 9 modules
- **Automation:** 4 services
- **Documentation:** 4 comprehensive guides
- **Dependencies:** 11 Python packages

---

## 🔒 Security Reminders

**NEVER commit:**
- Discord bot tokens
- Database passwords
- `.env` files
- Production configs

**Use .env for:**
- `DISCORD_TOKEN`
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
psql -h localhost -U et_bot -d et_stats

# Check service
sudo systemctl status postgresql
```

### Missing files
```bash
# Re-clone repository
git clone https://github.com/iamez/slomix.git
cd slomix
git checkout vps-network-migration

# Verify critical files
ls bot/community_stats_parser.py
ls postgresql_database_manager.py
```

---

**Deployment Ready:** ✅ YES (after fixes applied)
**Last Verified:** November 6, 2025
**Branch:** vps-network-migration
