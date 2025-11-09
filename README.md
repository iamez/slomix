# Enemy Territory Stats Bot

A comprehensive Discord bot for tracking and analyzing Wolfenstein: Enemy Territory game statistics with PostgreSQL backend.

> **📍 Branch Status:** `system-security-optimization`  
> **🎯 Current Focus:** Performance upgrades, security hardening, and voice-based team detection  
> **📋 Full Roadmap:** See [PERFORMANCE_UPGRADES_ROADMAP.md](PERFORMANCE_UPGRADES_ROADMAP.md) for 10-phase implementation plan

## 🎮 Features

### ✅ Production Ready
- **Player Stats**: Track kills, deaths, K/D ratio, accuracy, damage, XP, and more
- **Weapon Stats**: Detailed weapon usage, accuracy, headshots, kills per weapon
- **Map Performance**: Per-map statistics and performance tracking
- **Gaming Sessions**: Automatic session detection and consolidation
- **Leaderboards**: Top players, weapons, maps, and performance rankings
- **Last Session Analytics**: 6 comprehensive graphs (K/D, weapons, maps, teams, etc.)
- **Auto-Import**: Monitors stats directory and imports new files automatically
- **Voice Detection**: Monitors Discord voice channels, detects gaming sessions (6+ players)
- **PostgreSQL Backend**: Fast, scalable database with transaction safety
- **Duplicate Prevention**: SHA256 hash-based file tracking

### 🚧 In Development (This Branch)

**Phase 1: Voice Activity Tracking** ⏳
- Track Discord voice participants during gaming sessions
- Link Discord users to ET player GUIDs
- Monitor join/leave times, channel assignments
- Build historical voice activity database

**Phase 2: Gaming Session Management** 📋
- Proper `gaming_sessions` table schema
- Link rounds to voice-detected sessions
- Track session duration, participant lists
- Session summary command with voice data

**Phase 9: Security & Permissions** 🔐 **CRITICAL**
- Role-based command access (PUBLIC, TRUSTED, MODERATOR, ADMIN, OWNER)
- Whitelist master admin (Discord ID: 231165917604741121)
- Protect dangerous commands (!rebuild, !import, VPS control)
- Audit logging for all admin actions
- Rate limiting to prevent abuse
- Substitution tracking via voice channel switches

**Phase 3-8: Performance Optimization** ⚡
- Redis caching layer (5-min TTL → sub-second queries)
- Leaderboard pre-computation (refresh on import)
- Advanced database indexing
- Async I/O optimization
- Pagination for large datasets
- Advanced analytics (heatmaps, timelines, dashboards)

**Bonus: Voice-Based Team Detection** 🎯
- 100% accurate team assignment (vs 50-80% algorithmic)
- If players in "Team A Channel" vs "Team B Channel" = instant perfect teams
- Confidence scoring: Voice=1.0, Manual=0.9, Algorithmic=0.5-0.8
- Real-time roster updates as players move channels
- Substitution detection when players switch teams mid-game

**See Full Plan:** [PERFORMANCE_UPGRADES_ROADMAP.md](PERFORMANCE_UPGRADES_ROADMAP.md) (1,700+ lines, 10 phases)

## 📋 Requirements

### System Requirements
- Python 3.8+
- PostgreSQL 12+
- Discord Bot Token
- 500MB+ disk space

### Python Dependencies
```
discord.py>=2.0.0
asyncpg>=0.27.0
Pillow>=9.0.0
matplotlib>=3.5.0
python-dotenv>=0.19.0
aiofiles>=0.8.0
```

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/iamez/slomix.git
cd slomix
```

### 2. Install Dependencies
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Setup PostgreSQL Database
```bash
# Login to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE et_stats;
CREATE USER et_bot WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE et_stats TO et_bot;
\q
```

### 4. Configure Bot
Create `.env` file in root directory:
```env
DISCORD_TOKEN=your_discord_bot_token_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=et_stats
POSTGRES_USER=et_bot
POSTGRES_PASSWORD=your_secure_password
LOCAL_STATS_PATH=C:\path\to\stats\files
AUTOMATION_ENABLED=true
```

### 5. Initialize Database Schema
```bash
python postgresql_database_manager.py
# Select option 1: Initialize schema
# Select option 3: Import from local files (if you have stats files)
```

### 6. Run Bot
```bash
python bot/ultimate_bot.py
```

## 💡 Bot Entry Point

The main bot file is `bot/ultimate_bot.py` (not `main.py`). Run it directly:
```bash
# Windows
python bot\ultimate_bot.py

# Linux/Mac
python bot/ultimate_bot.py
```

## 📁 Project Structure

```
slomix/
├── bot/                                    # Main bot code
│   ├── ultimate_bot.py                    # Main bot entry point (4837 lines)
│   ├── config.py                          # Bot configuration
│   ├── logging_config.py                  # Logging setup
│   ├── image_generator.py                 # Graph generation
│   │
│   ├── cogs/                              # Discord command modules (14 cogs)
│   │   ├── admin_cog.py                   # Database admin commands
│   │   ├── stats_cog.py                   # Player statistics commands
│   │   ├── leaderboard_cog.py             # Rankings and leaderboards
│   │   ├── last_session_cog.py            # Comprehensive session analytics (111KB)
│   │   ├── session_cog.py                 # Session viewing
│   │   ├── session_management_cog.py      # Session control
│   │   ├── link_cog.py                    # Player Discord linking
│   │   ├── sync_cog.py                    # Data synchronization
│   │   ├── team_cog.py                    # Team tracking
│   │   ├── team_management_cog.py         # Team management
│   │   ├── automation_commands.py         # Automation controls
│   │   ├── server_control.py              # Server management
│   │   ├── synergy_analytics.py           # Player synergy analysis
│   │   └── synergy_analytics_fixed.py     # Fixed synergy analysis
│   │
│   ├── core/                              # Core systems (9 modules)
│   │   ├── database_adapter.py            # SQLite/PostgreSQL abstraction
│   │   ├── team_manager.py                # Team detection & tracking
│   │   ├── advanced_team_detector.py      # Advanced team detection
│   │   ├── team_detector_integration.py   # Team detector integration
│   │   ├── substitution_detector.py       # Player substitution detection
│   │   ├── team_history.py                # Team history tracking
│   │   ├── achievement_system.py          # Achievement tracking
│   │   ├── season_manager.py              # Season management
│   │   └── stats_cache.py                 # Statistics caching
│   │
│   └── services/automation/               # Automation services (4 modules)
│       ├── ssh_monitor.py                 # SSH file monitoring
│       ├── database_maintenance.py        # Database maintenance
│       ├── health_monitor.py              # System health monitoring
│       ├── metrics_logger.py              # Metrics logging
│       └── INTEGRATION_GUIDE.md           # Automation integration guide
│
├── tools/                                  # Essential tools
│   ├── stopwatch_scoring.py              # Stopwatch mode scoring calculator
│   └── postgresql_db_manager.py           # PostgreSQL database manager
│
├── postgresql_database_manager.py         # Main database management CLI
├── requirements.txt                        # Python dependencies
├── .env.example                           # Environment variables template
└── README.md                              # This file
```

## 🎯 Discord Commands

### Player Statistics (PUBLIC - Everyone)
- `!stats [player]` - Get detailed player statistics
- `!stats @mention` - Get stats for mentioned Discord user
- `!top [stat]` - View leaderboards (kd, kills, accuracy, etc)
- `!compare <player1> <player2>` - Compare two players

### Session Analysis (PUBLIC - Everyone)
- `!last_session` - Generate comprehensive 6-graph analysis of last gaming session
- `!sessions` - List recent gaming sessions
- `!session <number>` - View specific session details

### Map & Weapon Stats (PUBLIC - Everyone)
- `!maps` - List all maps with stats
- `!map <name>` - Get detailed map statistics
- `!weapons` - View weapon usage statistics
- `!weapon <name>` - Get specific weapon stats

### Admin Commands (ADMIN+ - Restricted)
- `!import` - Manually trigger stats import
- `!check_schema` - Verify database schema
- `!status` - Check bot and automation status
- `!resync` - Force resync with database

### Owner Commands (OWNER ONLY - You!)
- `!rebuild` - ⚠️ DANGER: Rebuild entire database (wipes all data)
- `!shutdown` - Shutdown the bot

> **🔐 Security Note:** Phase 9 will implement role-based permissions.  
> Currently all commands are public - **security update is critical priority!**

## 🔧 Database Management

### Using the CLI Tool
```bash
python postgresql_database_manager.py
```

**Options:**
1. **Initialize Schema** - Create all tables and indexes
2. **Clear Database** - Drop all data (keeps schema)
3. **Import from Local Files** - Bulk import stats files
4. **Rebuild Database** - Complete wipe and reimport
5. **Verify Data Integrity** - Check for issues
6. **Export Backup** - Create database backup

### Database Schema Highlights
- **rounds**: Round-level data (map, date, duration, team scores)
- **player_stats**: Player performance per round
- **weapon_stats**: Weapon usage per player per round
- **processed_files**: Track imported files (SHA256 hash)
- **gaming_sessions**: Consolidated gaming sessions
- **player_aliases**: Link Steam GUIDs to Discord users

## 📊 Gaming Session Logic

**Session Detection:**
- Rounds within 12 hours = same session
- Gap > 12 hours = new session
- Automatic consolidation on import
- Session stats calculated from all rounds

**Session Metrics:**
- Total rounds played
- Unique maps
- Session duration
- Player count range
- Aggregate statistics

## 🤖 Automation System

**Auto-Import Features:**
- Monitors `LOCAL_STATS_PATH` for new files
- Scans every 60 seconds
- Only imports new files (hash-based detection)
- Calculates R2 differential stats automatically
- Groups into gaming sessions
- Transaction-safe with rollback on errors

**Enable/Disable:**
```python
# In .env file:
AUTOMATION_ENABLED=true  # or false
```

## 🐛 Troubleshooting

### Bot Won't Start
```bash
# Check Python version
python --version  # Should be 3.8+

# Check dependencies
pip list | grep discord
pip list | grep asyncpg

# Verify .env file exists
cat .env  # Linux/Mac
type .env  # Windows
```

### Database Connection Issues
```bash
# Test PostgreSQL connection
psql -h localhost -U et_bot -d et_stats

# Check PostgreSQL is running
# Linux:
sudo systemctl status postgresql
# Windows: Check Services

# Verify credentials in .env match database
```

### Import Failing
```bash
# Check file permissions
# Verify LOCAL_STATS_PATH is correct
# Check logs/database_manager.log for errors

# Manual import test:
python postgresql_database_manager.py
# Select option 3
```

### Graphs Not Generating
```bash
# Verify matplotlib installation
pip install --upgrade matplotlib Pillow

# Check font cache
python -c "import matplotlib; matplotlib.font_manager._rebuild()"

# Test graph generation manually in database manager
```

## 📚 Additional Documentation

### 🗺️ This Branch: Performance & Security Roadmap
- **[PERFORMANCE_UPGRADES_ROADMAP.md](PERFORMANCE_UPGRADES_ROADMAP.md)** - **PRIMARY GUIDE FOR THIS BRANCH**
  - 10-phase implementation plan (1,700+ lines)
  - Voice activity tracking & team detection
  - Redis caching, database optimization
  - **Security & permissions system (CRITICAL)**
  - Rate limiting, audit logging, role-based access
  - Voice-based team detection (100% accuracy)
  - ML predictions, automated backups, health checks
  
### 📖 Technical Documentation (Main Branch)
- **[docs/TECHNICAL_OVERVIEW.md](docs/TECHNICAL_OVERVIEW.md)** - Complete technical documentation
  - Full data pipeline: Game Server → Database → Discord
  - System architecture and design decisions
  - Database schema (50+ fields per player)
  - Field mapping: exactly what data we capture
  - Performance optimizations
  - Security & data integrity

- **[docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md)** - Visual pipeline diagram (interactive)
- **[docs/FIELD_MAPPING.md](docs/FIELD_MAPPING.md)** - Complete field reference with examples
- **[docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md)** - Historical system documentation

### 🔧 Integration Guides
- **[bot/services/automation/INTEGRATION_GUIDE.md](bot/services/automation/INTEGRATION_GUIDE.md)** - Automation system setup
  - SSH file monitoring
  - Real-time round stats posting
  - Database maintenance
  - Health monitoring
  - Metrics logging

---

## 🚀 Quick Start (This Branch)

### Current VPS Deployment
```bash
# Already running on VPS
Host: samba@192.168.64.116
Database: PostgreSQL (etlegacy @ localhost:5432)
Status: ✅ Bot running, voice detection active
```

### Local Development Setup
```bash
# Clone this branch
git clone -b system-security-optimization https://github.com/iamez/slomix.git
cd slomix

# Install dependencies
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Initialize database
python postgresql_database_manager.py
# Select option 1: Initialize schema

# Run bot
python bot/ultimate_bot.py
```

### Priority Tasks (Before Merging to Main)

**🔐 Phase 9: Security (MUST DO)**
1. Implement permission system (`bot/core/permissions.py`)
2. Add role-based decorators to all commands
3. Whitelist master admin (Discord ID: 231165917604741121)
4. Create `admin_audit_log` table
5. Add rate limiting to prevent spam
6. Test permission denials

**📊 Phase 1: Voice Tracking (SHOULD DO)**
1. Create `voice_sessions` table
2. Build `VoiceSessionManager` class
3. Link Discord users to ET GUIDs
4. Track session participants

**⚡ Phase 3: Redis Caching (NICE TO HAVE)**
1. Install Redis on VPS
2. Migrate hot queries to cache
3. Pre-compute leaderboards

**See:** [PERFORMANCE_UPGRADES_ROADMAP.md](PERFORMANCE_UPGRADES_ROADMAP.md) for complete implementation details

---

## 🚢 VPS Deployment

### Quick Deploy (Debian/Ubuntu)
```bash
# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib

# Setup PostgreSQL
sudo -u postgres createdb et_stats
sudo -u postgres createuser et_bot -P

# Clone and setup
git clone https://github.com/iamez/slomix.git
cd slomix
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your settings

# Initialize database
python postgresql_database_manager.py
# Select option 1: Initialize schema

# Run bot
python bot/ultimate_bot.py
```

### Systemd Service Setup
Create `/etc/systemd/system/et-bot.service`:
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

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable et-bot
sudo systemctl start et-bot
sudo systemctl status et-bot
```

## 🔐 Security Notes

**⚠️ Branch Status: Security NOT yet implemented!**
- Phase 9 (Security & Permissions) is planned but not coded
- Currently **ALL commands are public** - anyone can run `!rebuild`, `!import`, etc.
- **DO NOT use in production** until Phase 9 is complete

**Planned Security (Phase 9):**
- Role-based permissions (PUBLIC, TRUSTED, MODERATOR, ADMIN, OWNER)
- Master admin whitelist (Discord ID: 231165917604741121)
- Audit logging for all admin actions
- Rate limiting to prevent spam
- Command decorators: `@requires_permission(PermissionLevel.OWNER)`

**Current Security Best Practices:**
- ✅ Never commit Discord tokens or database passwords
- ✅ Use `.env` files for secrets (in `.gitignore`)
- ✅ SHA256 hash-based duplicate detection
- ✅ Transaction-safe database operations
- ❌ No command permissions (CRITICAL TO FIX)

**See:** [PERFORMANCE_UPGRADES_ROADMAP.md - Phase 9](PERFORMANCE_UPGRADES_ROADMAP.md#phase-9-security--permissions-system-critical) for implementation plan

---

## 📝 License

This project is private and proprietary.

## 🤝 Contributing

This is a private bot for specific ET servers. External contributions are not currently accepted.

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Review `bot/services/automation/INTEGRATION_GUIDE.md` for automation setup
3. Check bot logs (console output or logs directory)
4. Review database logs in `postgresql_manager.log`
5. Use `postgresql_database_manager.py` for database health checks
6. Contact server administrators

---

**Version:** 2.0  
**Last Updated:** November 2025  
**Python:** 3.8+  
**Database:** PostgreSQL 12+  
**Discord.py:** 2.0+
