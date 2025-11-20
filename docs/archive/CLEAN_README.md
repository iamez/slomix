# Enemy Territory Stats Bot

A comprehensive Discord bot for tracking and analyzing Wolfenstein: Enemy Territory game statistics with PostgreSQL backend.

## 🎮 Features

### Core Statistics
- **Player Stats**: Track kills, deaths, K/D ratio, accuracy, damage, XP, and more
- **Weapon Stats**: Detailed weapon usage, accuracy, headshots, kills per weapon
- **Map Performance**: Per-map statistics and performance tracking
- **Gaming Sessions**: Automatic session detection and consolidation
- **Leaderboards**: Top players, weapons, maps, and performance rankings

### Advanced Analytics
- **Last Session Command**: Generates 6 comprehensive graphs:
  - Player Performance (K/D, Accuracy, Damage)
  - Weapon Analysis (usage distribution, accuracy comparison)
  - Map Breakdown (rounds played per map)
  - Kill Metrics (total kills, deaths, revives)
  - Team Analysis (team performance comparison)
  - Time-based Metrics (XP gain, damage over time)

### Automation Features
- **Auto-Import**: Monitors local stats directory and imports new files automatically
- **Round Detection**: Intelligent R1/R2 differential stats calculation
- **Session Consolidation**: Groups rounds into gaming sessions (gap threshold: 12 hours)
- **Duplicate Prevention**: SHA256 hash-based duplicate file detection
- **Transaction Safety**: Atomic database operations with rollback support

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
python main.py
```

## 📁 Project Structure

```
slomix/
├── bot/                          # Main bot code
│   ├── cogs/                     # Discord command modules
│   │   ├── leaderboard_cog.py   # Stats commands (!stats, !last_session, etc)
│   │   ├── server_control_cog.py # Server control commands
│   │   └── admin_cog.py         # Admin utilities
│   ├── services/                 # Core services
│   │   ├── automation/          # Auto-import system
│   │   │   ├── service.py       # Main automation service
│   │   │   └── monitor.py       # File system monitor
│   │   ├── graph_generator.py   # Graph generation service
│   │   └── team_detector.py     # Team detection logic
│   ├── database/                 # Database layer
│   │   ├── manager.py           # PostgreSQL manager
│   │   └── schema.sql           # Database schema
│   └── utils/                    # Utilities
│       ├── parsers.py           # Stats file parser
│       └── validators.py        # Data validation
├── postgresql_database_manager.py # Database management CLI
├── main.py                       # Bot entry point
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## 🎯 Discord Commands

### Player Statistics
- `!stats [player]` - Get detailed player statistics
- `!stats @mention` - Get stats for mentioned Discord user
- `!top [stat]` - View leaderboards (kd, kills, accuracy, etc)
- `!compare <player1> <player2>` - Compare two players

### Session Analysis
- `!last_session` - Generate comprehensive 6-graph analysis of last gaming session
- `!sessions` - List recent gaming sessions
- `!session <number>` - View specific session details

### Map & Weapon Stats
- `!maps` - List all maps with stats
- `!map <name>` - Get detailed map statistics
- `!weapons` - View weapon usage statistics
- `!weapon <name>` - Get specific weapon stats

### Admin Commands
- `!import` - Manually trigger stats import
- `!rebuild` - Rebuild database from scratch
- `!status` - Check bot and automation status
- `!resync` - Force resync with database

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

- **[DATA_PIPELINE_EXPLAINED.txt](DATA_PIPELINE_EXPLAINED.txt)** - How stats parsing works
- **[AUTOMATION_SETUP_GUIDE.md](AUTOMATION_SETUP_GUIDE.md)** - Automation system deep dive
- **[VPS_DEPLOYMENT_GUIDE.md](VPS_DEPLOYMENT_GUIDE.md)** - Deploy to Linux VPS
- **[COMPLETE_SYSTEM_RUNDOWN.md](COMPLETE_SYSTEM_RUNDOWN.md)** - Full system architecture

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

# Configure (edit .env file)
nano .env

# Initialize database
python postgresql_database_manager.py

# Run with systemd (see VPS_DEPLOYMENT_GUIDE.md)
```

## 🔐 Security Notes

**⚠️ NEVER commit:**
- Discord bot tokens
- Database passwords
- `.env` files
- `config.json` with secrets

**Use environment variables for:**
- `DISCORD_TOKEN`
- `POSTGRES_PASSWORD`
- Any API keys

## 📝 License

This project is private and proprietary.

## 🤝 Contributing

This is a private bot for specific ET servers. External contributions are not currently accepted.

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Review documentation in `docs/` folder
3. Check logs in `logs/` directory
4. Contact server administrators

---

**Version:** 2.0  
**Last Updated:** November 2025  
**Python:** 3.8+  
**Database:** PostgreSQL 12+  
**Discord.py:** 2.0+
