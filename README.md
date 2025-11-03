# 🎮 ET:Legacy Stats Bot - The Ultimate Gaming Companion

> **Transform your ET:Legacy gaming sessions into comprehensive statistics and social experiences**

A **production-ready Discord bot** that makes gaming stats **automatic, accurate, and engaging!**

## ✨ What's New (Nov 2025)

- ✅ **100% Data Accuracy** - Validated across 2,700+ field comparisons
- 🔧 **One-Tool Database** - Unified `database_manager.py` with disaster recovery
- 🧹 **Clean Codebase** - Reduced from 1,623 to 370 files (77% cleanup)
- 🎯 **Bug-Free** - Fixed 10+ critical bugs in parser and field mapping
- 🤖 **Smart Automation** - SSH monitoring, auto-posting, voice detection
- 👥 **Advanced Team Detection** - Handles stopwatch mode, roster changes
- 📚 **Complete Documentation** - Validation reports, recovery guides, API docs

## 🚀 Key Highlights

- 📊 **53+ Statistics** - Everything from K/D to team contributions
- 🎙️ **Voice-Activated** - Auto-starts when 6+ players in voice
- ⚡ **Real-Time Posts** - Round summaries posted automatically  
- 👥 **Social First** - @mention anyone for instant stats
- 🏆 **Smart Aliases** - Handles name changes, consolidates stats
- 💾 **Bulletproof** - Auto-backups, duplicate prevention, disaster recovery
- 🔍 **Battle-Tested** - 25 unique players, 1,862 sessions tracked

**[👉 See Full Showcase](docs/README.md)** | **[👉 Show Your Friend](docs/FOR_YOUR_FRIEND.md)**

---

## ⚡ Quick Start for AI Agents

**👉 READ FIRST**: [`docs/AI_AGENT_GUIDE.md`](docs/AI_AGENT_GUIDE.md) - Complete reference guide

**Current Schema**: UNIFIED (7 tables, 53 columns)  
**Database Manager**: `database_manager.py` - THE ONLY TOOL FOR DATABASE OPERATIONS  
**Database**: `bot/etlegacy_production.db` (1,862 sessions, 25 unique players)

**🚨 Disaster Recovery**: See [`DISASTER_RECOVERY.md`](DISASTER_RECOVERY.md) for database recovery without AI assistance

---

## 🌟 Core Features

### **Stats & Analytics** 📊
- **Comprehensive Stats** - 53+ fields including K/D, DPM, accuracy, headshots, revives
- **Weapon Breakdowns** - Detailed stats for 28+ weapons per player
- **Team Performance** - Stopwatch scoring, team detection, roster tracking
- **Session History** - Complete match archives with differential calculations
- **Smart Aliases** - Automatic player name consolidation across matches
- **Leaderboards** - Rankings by K/D, DPM, accuracy, and 11 other metrics

### **Automation & Intelligence** 🤖
- **Voice Detection** - Auto-starts monitoring when 6+ players join voice
- **SSH Monitoring** - Watches server for new EndStats files (30s intervals)
- **Auto-Posting** - Round summaries posted automatically to Discord
- **Map Completion** - Aggregate stats when all rounds finish
- **Session Summaries** - Auto-posts when everyone leaves voice
- **Zero-Config** - Fully autonomous once enabled

**To enable:** Set `AUTOMATION_ENABLED=true` and `SSH_ENABLED=true` in `.env`  
**See:** [PRODUCTION_AUTOMATION_GUIDE.md](PRODUCTION_AUTOMATION_GUIDE.md) for setup

### **Data Quality & Reliability** ✅
- **100% Validated** - 2,700+ field comparisons verified accurate
- **Bug-Free Parser** - Fixed emoji encoding, midnight crossover, field mapping
- **Smart Differential** - Correct Round 2 calculations (cumulative - Round 1)
- **Duplicate Prevention** - UNIQUE constraints, transaction safety, processed file tracking
- **Auto-Recovery** - Database auto-creates tables, directories, and backups
- **Disaster Recovery** - 5-minute restore without AI assistance

### **Developer Experience** 💻
- **One Database Tool** - `database_manager.py` handles ALL operations
- **Modular Architecture** - Bot split into cogs, core classes extracted
- **Clean Codebase** - 370 production files (down from 1,623)
- **Comprehensive Docs** - Validation reports, API guides, recovery procedures
- **Type Hints** - Full typing throughout core modules

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment  
cp .env.example .env
# Edit .env with your Discord bot token and server details

# Setup database (first time only)
python database_manager.py
# Choose option 1 (Create fresh database)
# Then option 2 (Import all files)

# Run the bot
python bot/ultimate_bot.py
```

## 📋 Main Commands

- `!stats <player>` - Player statistics
- `!top_dpm` - DPM leaderboard  
- `!session_stats` - Session analytics
- `!link_me` - Link Discord to game stats
- `!mvp` - Show MVP awards

## 📁 Project Structure

```
slomix/
├── database_manager.py         # 🔧 ONE TOOL for all database operations
├── DISASTER_RECOVERY.md        # 🚨 5-minute recovery without AI
├── VALIDATION_COMPLETE_SUMMARY.md  # ✅ 100% accuracy verification
├── PRODUCTION_AUTOMATION_GUIDE.md  # 🤖 Automation setup
│
├── bot/                        # Core Discord bot
│   ├── ultimate_bot.py         # Main bot (4,700 lines) ⭐
│   ├── community_stats_parser.py   # EndStats parser (970 lines) ⭐
│   ├── etlegacy_production.db  # Production database (1,862 sessions)
│   ├── cogs/                   # Modular command cogs (15 files)
│   │   ├── stats_cog.py        # Player stats commands
│   │   ├── leaderboard_cog.py  # Leaderboard commands
│   │   ├── session_cog.py      # Session management
│   │   ├── link_cog.py         # Player linking
│   │   └── admin_cog.py        # Admin utilities
│   ├── core/                   # Core systems (9 modules)
│   │   ├── achievement_system.py   # Achievement detection
│   │   ├── season_manager.py   # Quarterly seasons
│   │   └── stats_cache.py      # Performance caching
│   └── services/               # Background services
│       └── automation/         # SSH monitoring, auto-posting
│
├── tools/                      # Utilities & analysis (18 files)
│   ├── stopwatch_scoring.py    # Team scoring logic
│   ├── dynamic_team_detector.py    # Advanced team detection
│   ├── session_summary_generator.py    # Session analytics
│   └── ssh_sync_and_import.py  # SSH integration
│
├── server/                     # Server-side components
│   ├── endstats_modified.lua   # Modified EndStats script
│   ├── c0rnp0rn3.lua          # Custom server mod
│   └── etlegacy_bot           # SSH key for server access
│
├── docs/                       # Documentation
│   ├── AI_AGENT_GUIDE.md      # Complete reference for AI
│   └── archive/               # Historical docs
│
├── dev/                        # Development tools
│   └── bulk_import_stats.py   # Bulk importer (873 lines)
│
└── local_stats/                # EndStats files from server
    └── last_session.zip        # Latest session backup
```

**Production Files:** 370 tracked files (cleaned from 1,623)  
**Core Codebase:** ~15,000 lines across main components

## 🔧 Configuration

1. **Discord Bot Setup**:
   - Create Discord application at https://discord.com/developers/applications
   - Copy bot token to `.env` file
   - Invite bot to your Discord server

2. **Server Connection**:
   - Configure server SSH connection details
   - Set up EndStats file monitoring
   - Configure database paths

## 🎯 DPM Calculation

The bot uses accurate DPM calculations accounting for actual playtime:
```
DPM = damage_given ÷ (round_time × playtime_percent ÷ 100)
```

This ensures players who join mid-round aren't penalized with inflated DPM values.

## 📊 Database (100% Validated)

- **Sessions**: 1,862 gaming sessions (all 2025 data imported & verified)
- **Players**: 25 unique players with comprehensive stats
- **Validation**: 100% accuracy across 2,700+ field comparisons (Nov 2025)
- **Tables**: 7 tables
  - `sessions` - Gaming session metadata
  - `player_comprehensive_stats` - 53 fields per player/round
  - `weapon_comprehensive_stats` - 28+ weapons per player
  - `player_links` - Discord to game account mapping
  - `processed_files` - Duplicate prevention tracking
  - `session_teams` - Team compositions and scoring
  - `player_aliases` - Name change tracking
- **Schema**: UNIFIED 53-column schema with stopwatch scoring
- **Protection**: UNIQUE constraints, transaction safety, auto-backups
- **Auto-Recovery**: Creates missing tables/directories automatically

## 🛠️ Development

### Database Operations (UNIFIED TOOL)
```bash
# THE ONLY database tool - handles everything
python database_manager.py

# Interactive Menu:
# 1 - Create fresh database (with backup)
# 2 - Import all files (incremental, safe, tracks processed files)
# 3 - Rebuild from scratch (nuclear option with safety confirmation)
# 4 - Fix specific date range (surgical repairs)
# 5 - Validate database (health check)
# 6 - Quick test (10 files for testing)
```

**Protection Built-In:**
- ✅ Transaction safety (BEGIN/COMMIT/ROLLBACK)
- ✅ Duplicate prevention (UNIQUE constraints + processed file tracking)
- ✅ Automatic backups before destructive operations
- ✅ Progress tracking with ETA

⚠️ **CRITICAL**: Never create new database/import scripts. Use `database_manager.py` for ALL operations. See [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) for emergency procedures.

### Bug Fixes Applied (Nov 2025)

**Parser Fixes:**
- ✅ Emoji encoding crashes (Windows compatibility)
- ✅ Midnight crossover (Round 1 search across date boundary)
- ✅ Accuracy calculation (now calculated from weapon totals)
- ✅ Time dead ratio (recalculated for Round 2)

**Database Insertion Fixes:**
- ✅ 10 critical field mapping errors corrected
- ✅ team_damage_given/received (wrong source object)
- ✅ headshot_kills (was using 'headshots' instead)
- ✅ useful_kills (wrong field name)
- ✅ constructions (was hardcoded 0)
- ✅ multikills (wrong field names for 2x-6x)

**Team Detection Fixes:**
- ✅ Multiple plays of same map (now uses session_id + map + round key)
- ✅ Stopwatch team swaps (100% accuracy)
- ✅ Substitution tracking (roster change detection)

### Testing & Validation
```bash
# Comprehensive validation (2,700+ field comparisons)
python generate_html_report.py

# Test parser on sample files
python bot/community_stats_parser.py local_stats/sample.txt

# Database health check
python database_manager.py  # Choose option 5

# SSH monitoring test
python test_ssh_monitoring.py
```

### Code Architecture

**Modular Bot Structure:**
- `bot/ultimate_bot.py` - Main bot (4,700 lines, down from 8,000)
- `bot/cogs/` - 15 command cogs (organized by feature)
- `bot/core/` - 9 core classes (extracted from main)
- `bot/services/automation/` - Background services

**Type Hints & Documentation:**
- Full type hints in all core modules
- Comprehensive docstrings with examples
- Module-level documentation

### Adding New Features
- **Bot commands:** Add new cog in `bot/cogs/`
- **Parser logic:** Edit `bot/community_stats_parser.py`
- **Database operations:** Edit `database_manager.py` (never create new scripts!)
- **Automation:** Edit `bot/services/automation/`

## 🚀 Deployment

**Quick Deploy:**
```bash
# 1. Clone and setup
git clone https://github.com/iamez/slomix.git
cd slomix
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your Discord token and server details

# 3. Initialize database
python database_manager.py  # Choose option 1, then option 2

# 4. Start bot
python bot/ultimate_bot.py
```

**Production Setup:**
- [LAPTOP_DEPLOYMENT_GUIDE.md](LAPTOP_DEPLOYMENT_GUIDE.md) - Laptop/desktop deployment
- [PRODUCTION_AUTOMATION_GUIDE.md](PRODUCTION_AUTOMATION_GUIDE.md) - Automation setup
- [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) - Emergency procedures

## 📈 Statistics Tracking

The bot tracks **53+ comprehensive statistics** including:

**Combat Stats:**
- Kills, deaths, K/D ratio (with >20 game minimum for leaderboards)
- Damage given/received, damage per minute (DPM)
- Accuracy (calculated from weapon totals)
- Headshot HITS and headshot KILLS (distinct metrics!)
- Gibs and team damage tracking

**Objective Stats:**
- Revives given and times revived
- Constructions and repairs
- Flag captures and returns
- Plant/defuse actions
- Useful kills (objective-related)

**Weapon Stats:**
- 28+ weapons tracked individually
- Per-weapon kills, deaths, headshots, accuracy
- Ammo usage and efficiency

**Performance Metrics:**
- Killing sprees (best streak)
- Death sprees (worst streak)
- Multikills (2x through 6x+)
- Time dead ratio
- Self-kills tracking

**Team Performance:**
- Stopwatch scoring (attack/defense times)
- Team detection (handles roster changes)
- Round differentials (cumulative - Round 1)
- Map completion summaries

## 🏆 Recent Achievements (Nov 2025)

**Data Quality:** ✅
- Validated 100% accuracy (2,700+ field comparisons)
- Fixed 10+ critical bugs in parser and database insertion
- Documented headshot HITS vs KILLS distinction
- Verified revives tracking (both types working)

**Developer Experience:** 🚀
- Created unified `database_manager.py` (replaced 20+ scattered tools)
- Added disaster recovery guide (5-minute restore, no AI needed)
- Cleaned codebase 77% (1,623 → 370 files)
- Refactored bot into modular cogs (8,000 → 4,700 lines in main)

**Automation & Features:** 🤖
- Implemented SSH monitoring with auto-posting
- Added voice detection for session start/end
- Enhanced team detection for stopwatch mode
- Added map completion summaries
- Channel restrictions for bot commands

**Documentation:** 📚
- Comprehensive validation reports
- Complete API documentation for AI agents
- Production automation guides
- Field mapping documentation

## 📚 Documentation

**For Users:**
- [README.md](README.md) - This file (overview)
- [COMMANDS.md](COMMANDS.md) - All bot commands
- [COMMAND_CHEAT_SHEET.md](COMMAND_CHEAT_SHEET.md) - Quick reference

**For Developers:**
- [docs/AI_AGENT_GUIDE.md](docs/AI_AGENT_GUIDE.md) - Complete reference for AI
- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) - All config options
- [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) - Emergency procedures
- [PRODUCTION_AUTOMATION_GUIDE.md](PRODUCTION_AUTOMATION_GUIDE.md) - Automation setup

**Technical Details:**
- [VALIDATION_COMPLETE_SUMMARY.md](VALIDATION_COMPLETE_SUMMARY.md) - 100% validation results
- [VALIDATION_FINDINGS_NOV3.md](VALIDATION_FINDINGS_NOV3.md) - Detailed findings
- [ADVANCED_TEAM_DETECTION.md](ADVANCED_TEAM_DETECTION.md) - Team detection system
- [PRE_DEPLOYMENT_TEST_RESULTS.md](PRE_DEPLOYMENT_TEST_RESULTS.md) - All tests passed

---

## 📜 License

MIT License - See [LICENSE](LICENSE) for details

---

**Status:** Production-ready (Nov 2025) - 100% validated, fully automated, battle-tested with 1,862 sessions
