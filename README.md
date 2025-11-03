# 🎮 ET:Legacy Stats Bot - The Ultimate Gaming Companion

> **Transform your ET:Legacy gaming sessions into comprehensive statistics and social experiences**

An **intelligent Discord bot** that makes gaming stats **automatic, social, and fun!**

- 📊 **53+ Statistics** - Tracks everything from K/D to team contributions
- 🤖 **Automation Ready** - Voice detection & auto-posting built, requires configuration
- 👥 **Social First** - @mention anyone for instant stats
- 🏆 **Smart Aliases** - Handles name changes, consolidates stats
- ⚡ **Production Ready** - 25 unique players, 1,862 sessions tracked

**[👉 See Full Showcase](docs/README.md)** | **[👉 Show Your Friend](docs/FOR_YOUR_FRIEND.md)**

---

## ⚡ Quick Start for AI Agents

**👉 READ FIRST**: [`docs/AI_AGENT_GUIDE.md`](docs/AI_AGENT_GUIDE.md) - Complete reference guide

**Current Schema**: UNIFIED (7 tables, 53 columns)  
**Database Manager**: `database_manager.py` - THE ONLY TOOL FOR DATABASE OPERATIONS  
**Database**: `bot/etlegacy_production.db` (1,862 sessions, 25 unique players)

**🚨 Disaster Recovery**: See [`DISASTER_RECOVERY.md`](DISASTER_RECOVERY.md) for database recovery without AI assistance

---

## 🌟 Key Features

### **Live Now** ✅
- 📊 **Smart Stats** - `!stats vid` or `!stats @vid` (instant lookup)
- 🔗 **Interactive Linking** - React with 1️⃣2️⃣3️⃣ to link your account
- 🎯 **Alias Tracking** - All name changes consolidated automatically
- 🎮 **Session History** - `!last_session` shows your recent matches
- 🏆 **Leaderboards** - Rankings by K/D, DPM, and 11 other stats
- 🔧 **SSH Sync** - `!sync_stats` manually syncs server files
- 📈 **Session Management** - `!session_start` / `!session_end` commands

### **Available - Requires Configuration** ⚙️
**All automation features are fully implemented and ready to use!**

- 🎙️ **Voice Detection** - 6+ in voice = auto-start monitoring
- ⚡ **Real-Time Posts** - Round summaries posted automatically
- 🏁 **Session Summaries** - Auto-posts when everyone leaves voice
- 🤖 **Zero Commands** - Fully autonomous operation

**To enable:** Set `AUTOMATION_ENABLED=true` and `SSH_ENABLED=true` in your `.env` file.  
**See:** [AUTOMATION_SETUP_GUIDE.md](AUTOMATION_SETUP_GUIDE.md) for detailed instructions.

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
stats/
├── database_manager.py    # 🏗️ THE ONLY database tool (create, import, rebuild)
├── DISASTER_RECOVERY.md   # 🚨 Database recovery guide (no AI needed)
├── bot/                   # Core bot files & database
│   ├── ultimate_bot.py     # Main production bot (4700+ lines)
│   ├── community_stats_parser.py  # EndStats parser (970 lines)
│   └── etlegacy_production.db # Production DB (1,862 sessions)
├── dev/                   # Development scripts (bulk_import_stats.py)
├── tools/                 # Analysis and utility tools
├── server/               # Server-side files (SSH keys, Lua scripts)
├── docs/                 # Documentation
├── local_stats/          # EndStats files from game server
├── test_files/           # Sample files for testing
├── logs/                 # Application logs
├── archive/              # Old/deprecated tools
│   └── old_tools/        # Archived import/database scripts (20+)
└── config/               # Configuration templates
```

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

## 📊 Database

- **Sessions**: 1,862 gaming sessions tracked (all 2025 data imported)
- **Players**: 25 unique player GUIDs with comprehensive stats
- **Tables**: 7 tables (sessions, player_comprehensive_stats, weapon_comprehensive_stats, player_links, processed_files, session_teams, player_aliases)
- **Schema**: UNIFIED 53-column schema with stopwatch scoring support
- **Auto-linking**: Discord users automatically linked to game stats
- **MVP System**: Automatic MVP detection and awards

## 🛠️ Development

### Database Operations
```bash
# ALL database operations use database_manager.py
python database_manager.py

# Options:
# 1 - Create fresh database
# 2 - Import all files (incremental, safe)
# 3 - Rebuild from scratch (nuclear option)
# 4 - Fix specific date range
# 5 - Validate database
# 6 - Quick test (10 files)
```

⚠️ **IMPORTANT**: Never create new import/database scripts. Use `database_manager.py` for ALL operations.

### Running Tests
```bash
# Test parser functionality
python bot/community_stats_parser.py

# Test database health
python database_manager.py  # Choose option 5

# Test Discord bot features
python bot/ultimate_bot.py --test-mode
```

### Adding New Features
- Bot commands: Edit `bot/ultimate_bot.py`
- Parser logic: Edit `bot/community_stats_parser.py`  
- Database operations: Edit `database_manager.py` (not new scripts!)

## 🚀 Deployment

See `docs/SETUP.md` for detailed deployment instructions including:
- Linux server deployment
- SSH key configuration
- Database backup procedures
- Monitoring and logging

## 📈 Statistics Tracking

The bot tracks comprehensive statistics including:
- Damage per minute (DPM) with accurate playtime calculation
- Kill/Death ratios and accuracy
- Weapon-specific statistics and headshot percentages
- Team performance and round differentials
- MVP awards and session analytics

---

**Clean Migration**: This project was migrated from a 300+ file development environment to this organized structure for maintainability and production deployment.
