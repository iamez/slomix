# 🎮 ET:Legacy Stats Bot - Complete Setup Guide

> **Production-grade Discord bot for Wolfenstein: Enemy Territory (ET:Legacy) server statistics**

[![Status](https://img.shields.io/badge/status-production--ready-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10+-blue)]()
[![PostgreSQL](https://img.shields.io/badge/postgresql-14+-blue)]()

Automatically downloads, parses, and displays ET:Legacy game statistics in Discord with 6-layer data validation and zero data loss.

---

## 📋 Table of Contents

- [Quick Start (5 Minutes)](#-quick-start-5-minutes)
- [Detailed Setup Guide](#-detailed-setup-guide)
- [Configuration Reference](#-configuration-reference)
- [Troubleshooting](#-troubleshooting)
- [Production Deployment](#-production-deployment)
- [Commands Reference](#-commands-reference)

---

## 🚀 Quick Start (5 Minutes)

**Prerequisites Check:**
- ✅ Python 3.10 or higher
- ✅ PostgreSQL 14 or higher
- ✅ Discord account + server with admin access
- ✅ SSH access to ET:Legacy game server (optional, for auto-monitoring)

**Installation:**

```bash
# 1. Clone repository
git clone https://github.com/yourusername/slomix.git
cd slomix

# 2. Create virtual environment (Linux/Mac)
python3.10 -m venv .venv
source .venv/bin/activate

# Windows:
# python -m venv .venv
# .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup database
# Install PostgreSQL if needed:
# Ubuntu/Debian: sudo apt install postgresql-14
# macOS: brew install postgresql@14
# Windows: Download from https://www.enterprisedb.com/downloads/postgres-postgresql-downloads

# Create database
sudo -u postgres createuser -P etlegacy_user
# Enter password when prompted
sudo -u postgres createdb -O etlegacy_user etlegacy

# Create schema
python recreate_database.py

# 5. Configure bot
cp .env.example .env
nano .env  # Edit with your settings (see Configuration section)

# 6. Start bot
python bot/ultimate_bot.py
```

**Verify It Works:**
1. Bot should appear online in Discord (green status)
2. Type `!ping` in any bot command channel
3. Bot responds with latency info = SUCCESS! ✅

---

## 📚 Detailed Setup Guide

### Step 1: Prerequisites

#### 1.1 Python 3.10+

**Check your version:**
```bash
python3 --version  # Must be 3.10.0 or higher
```

**Install Python 3.10+ if needed:**

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
```

**macOS (using Homebrew):**
```bash
brew install python@3.10
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) and install.

---

#### 1.2 PostgreSQL 14+

**Check if installed:**
```bash
psql --version  # Should be 14.0 or higher
```

**Install PostgreSQL:**

**Ubuntu/Debian:**
```bash
sudo apt install postgresql-14 postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS:**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Windows:**
Download installer from [EnterpriseDB](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)

---

### Step 2: Database Setup

#### 2.1 Create Database User

```bash
# Create user with password
sudo -u postgres createuser -P etlegacy_user
# Enter a secure password when prompted (save it for later!)
```

#### 2.2 Create Database

```bash
# Create database owned by etlegacy_user
sudo -u postgres createdb -O etlegacy_user etlegacy
```

#### 2.3 Verify Connection

```bash
# Test connection (use password from step 2.1)
psql -U etlegacy_user -d etlegacy -h localhost -c "SELECT version();"
```

**Troubleshooting:**
- If you get "Peer authentication failed", edit `/etc/postgresql/14/main/pg_hba.conf`:
  ```
  # Change this line:
  local   all   all   peer
  # To:
  local   all   all   md5
  ```
  Then reload: `sudo systemctl reload postgresql`

#### 2.4 Create Database Schema

```bash
cd /path/to/slomix
python recreate_database.py
```

**Expected output:**
```
✅ Database schema created successfully
✅ Tables created: rounds, player_comprehensive_stats, weapon_comprehensive_stats...
✅ Indexes created
✅ Ready to import data
```

---

### Step 3: Discord Bot Setup

#### 3.1 Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Name it (e.g., "ET:Legacy Stats Bot")
4. Click **"Create"**

#### 3.2 Create Bot User

1. Click **"Bot"** tab in left sidebar
2. Click **"Add Bot"** → **"Yes, do it!"**
3. **Copy the token** (click "Reset Token" if needed)
   - **SAVE THIS TOKEN** - you'll need it for `.env` file
   - **NEVER share this token publicly!**

#### 3.3 Enable Intents (CRITICAL!)

Still on the Bot page, scroll down to **"Privileged Gateway Intents"**:

- ✅ **SERVER MEMBERS INTENT** - REQUIRED
- ✅ **PRESENCE INTENT** - REQUIRED
- ✅ **MESSAGE CONTENT INTENT** - REQUIRED

Click **"Save Changes"**

#### 3.4 Generate Invite URL

1. Click **"OAuth2"** → **"URL Generator"** in left sidebar
2. Select scopes:
   - ✅ `bot`
3. Select bot permissions:
   - ✅ Read Messages/View Channels
   - ✅ Send Messages
   - ✅ Send Messages in Threads
   - ✅ Embed Links
   - ✅ Attach Files
   - ✅ Read Message History
   - ✅ Add Reactions
   - ✅ Connect (for voice channel monitoring)
   - ✅ Use Voice Activity

   **OR** just select `Administrator` (easier but less secure)

4. Copy the generated URL at bottom
5. Open URL in browser, select your server, authorize

#### 3.5 Get Channel IDs

**Enable Developer Mode in Discord:**
1. Discord → User Settings (gear icon)
2. Advanced → Enable **Developer Mode**

**Copy Channel IDs:**
1. Right-click any text channel → Copy ID
2. Right-click any voice channel → Copy ID
3. Save these IDs for `.env` configuration

**You Need:**
- **GAMING_VOICE_CHANNELS**: Voice channels to monitor for active players
- **BOT_COMMAND_CHANNELS**: Text channels where bot commands work
- **STATS_CHANNEL_ID**: Where bot posts match summaries
- **ADMIN_CHANNEL_ID**: Where bot sends error alerts

---

### Step 4: SSH Setup (Optional - for Auto-Monitoring)

**Skip this if you're manually importing stats files.**

#### 4.1 Generate SSH Key

```bash
# Generate key pair
ssh-keygen -t rsa -b 4096 -f ~/.ssh/etlegacy_bot -C "discord-bot"
# Press Enter for no passphrase (or set one if you prefer)

# Set correct permissions
chmod 600 ~/.ssh/etlegacy_bot
chmod 644 ~/.ssh/etlegacy_bot.pub
```

#### 4.2 Add Public Key to Game Server

```bash
# Copy public key to server
ssh-copy-id -i ~/.ssh/etlegacy_bot.pub YOUR_USER@YOUR_GAME_SERVER

# OR manually:
cat ~/.ssh/etlegacy_bot.pub
# Copy output, then SSH to server and add to ~/.ssh/authorized_keys
```

#### 4.3 Test Connection

```bash
# Test SSH connection
ssh -i ~/.ssh/etlegacy_bot YOUR_USER@YOUR_GAME_SERVER

# Should connect without password!
# If successful, type 'exit'
```

**Windows Users:**
- Use `C:\Users\YourName\.ssh\etlegacy_bot` as key path
- Use PuTTY/PuTTYgen to generate keys if needed

---

### Step 5: Configuration

#### 5.1 Copy Environment Template

```bash
cp .env.example .env
```

#### 5.2 Edit .env File

```bash
nano .env  # Or use your preferred editor
```

**Required Settings:**

```env
# ============================================
# REQUIRED - Bot Core Configuration
# ============================================

# Discord Bot Token (from Step 3.2)
DISCORD_BOT_TOKEN=YOUR_TOKEN_HERE

# PostgreSQL Connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=your_password_from_step_2.1

# ============================================
# REQUIRED - Discord Channel IDs (from Step 3.5)
# ============================================

# Voice channels to monitor (comma-separated)
GAMING_VOICE_CHANNELS=123456789012345678,987654321098765432

# Text channels where bot commands work
BOT_COMMAND_CHANNELS=123456789012345678

# Channel for match summary posts
STATS_CHANNEL_ID=123456789012345678

# Channel for admin/error alerts
ADMIN_CHANNEL_ID=123456789012345678

# ============================================
# OPTIONAL - Automation Settings
# ============================================

# Enable automatic stats monitoring
AUTOMATION_ENABLED=true

# Enable SSH monitoring
SSH_ENABLED=true

# SSH Configuration (from Step 4)
SSH_HOST=your.gameserver.com
SSH_PORT=22
SSH_USER=etlegacy
SSH_KEY_PATH=/home/youruser/.ssh/etlegacy_bot
REMOTE_STATS_PATH=/home/et/.etlegacy/legacy/gamestats

# How often to check for new files (seconds)
SSH_CHECK_INTERVAL=60

# On startup, only process files from last X hours
SSH_STARTUP_LOOKBACK_HOURS=24

# ============================================
# OPTIONAL - Session Detection
# ============================================

# How many players needed to start session
SESSION_START_THRESHOLD=6

# Min players before session ends
SESSION_END_THRESHOLD=2

# Wait time before ending session (seconds)
SESSION_END_DELAY=300

# ============================================
# OPTIONAL - Advanced Settings
# ============================================

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Local directory for downloaded stats
LOCAL_STATS_PATH=./local_stats

# Metrics database (SQLite)
METRICS_DB_PATH=bot/data/metrics.db
```

**Windows Users:**
Use Windows paths with forward slashes or escaped backslashes:
```env
SSH_KEY_PATH=C:/Users/YourName/.ssh/etlegacy_bot
LOCAL_STATS_PATH=C:/Users/YourName/slomix/local_stats
```

---

### Step 6: First Run

#### 6.1 Start the Bot

```bash
# Activate virtual environment if not already
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Start bot
python bot/ultimate_bot.py
```

**Expected Output:**
```
2024-11-18 12:00:00 | INFO | bot.core | 🚀 ET:LEGACY DISCORD BOT - STARTING UP
2024-11-18 12:00:00 | INFO | DatabaseAdapter | ✅ PostgreSQL pool created: localhost:5432/etlegacy
2024-11-18 12:00:01 | INFO | bot.core | ✅ Ultimate Bot initialization complete!
2024-11-18 12:00:02 | INFO | bot.core | 🚀 Ultimate ET:Legacy Bot logged in as YourBotName#1234
2024-11-18 12:00:02 | INFO | bot.core | 📊 Commands Loaded: 60
```

#### 6.2 Verify Bot is Online

1. Open Discord
2. Check your server's member list
3. Bot should appear with **green status (online)**

#### 6.3 Test Basic Commands

In a bot command channel, type:

```
!ping
```

**Expected Response:**
```
🏓 Ultimate Bot Status
Bot Latency: 45ms
DB Latency: 2ms
Active Session: No
Commands: 60
```

**SUCCESS!** ✅ Bot is working!

---

## 🎯 Getting Your First Stats

### Option 1: Automatic Monitoring (Recommended)

If you set `AUTOMATION_ENABLED=true` and `SSH_ENABLED=true`:

Bot will automatically:
1. Check game server every 60 seconds
2. Download new `.txt` stat files
3. Parse and import to database
4. Post match summaries to `STATS_CHANNEL_ID`

**Just play games and stats appear automatically!**

---

### Option 2: Manual Import from Local Files

If you have `.txt` files locally:

```bash
# Copy files to local_stats directory
cp /path/to/*.txt local_stats/

# Import via Discord command
!sync_stats

# OR run Python script
python tools/simple_bulk_import.py
```

---

### Option 3: Manual Sync from Server

In Discord:

```
!sync_today    # Last 24 hours
!sync_week     # Last 7 days
!sync_month    # Last 30 days
!sync_all      # Everything (careful!)
```

Bot will SSH to server, download files, and import them.

---

## 📖 Commands Reference

### Player Stats
- `!ping` - Check bot status
- `!stats @player` - Player statistics
- `!compare @player1 @player2` - Compare two players
- `!leaderboard` or `!lb` - Top players
- `!season_info` - Current season info

### Sessions & Matches
- `!last_session` - Most recent match
- `!last_session maps` - Per-map breakdown
- `!last_session combat` - Combat stats
- `!last_session obj` - Objective stats
- `!session 2024-11-18` - Specific date
- `!rounds` or `!sessions` - List all sessions

### Team Analysis (if enabled)
- `!synergy @player1 @player2` - Player chemistry
- `!best_duos` - Top duos
- `!team_builder` - Suggested teams

### Manual Sync
- `!sync_stats` - Import local files
- `!sync_today` - Last 24h from server
- `!sync_week` - Last 7 days
- `!sync_month` - Last 30 days

### Admin Commands
- `!cache_clear` - Clear stats cache
- `!reload` - Reload a cog
- `!health` - System health check
- `!ssh_stats` - SSH monitoring status

---

## 🔧 Configuration Reference

### Complete .env Variables

**Core Settings:**
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ Yes | - | Discord bot token |
| `POSTGRES_HOST` | ✅ Yes | localhost | PostgreSQL host |
| `POSTGRES_PORT` | No | 5432 | PostgreSQL port |
| `POSTGRES_DATABASE` | ✅ Yes | etlegacy | Database name |
| `POSTGRES_USER` | ✅ Yes | - | Database user |
| `POSTGRES_PASSWORD` | ✅ Yes | - | Database password |

**Discord Channels:**
| Variable | Required | Description |
|----------|----------|-------------|
| `GAMING_VOICE_CHANNELS` | ✅ Yes | Voice channels to monitor (comma-separated) |
| `BOT_COMMAND_CHANNELS` | ✅ Yes | Text channels for commands |
| `STATS_CHANNEL_ID` | No | Where to post match summaries |
| `ADMIN_CHANNEL_ID` | No | Where to post errors/alerts |

**Automation:**
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUTOMATION_ENABLED` | No | false | Enable auto-processing |
| `SSH_ENABLED` | No | false | Enable SSH monitoring |
| `SSH_HOST` | If SSH enabled | - | Game server hostname |
| `SSH_PORT` | No | 22 | SSH port |
| `SSH_USER` | If SSH enabled | - | SSH username |
| `SSH_KEY_PATH` | If SSH enabled | - | Path to SSH private key |
| `REMOTE_STATS_PATH` | If SSH enabled | - | Path to stats on server |
| `SSH_CHECK_INTERVAL` | No | 60 | Check interval (seconds) |

**Session Detection:**
| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_START_THRESHOLD` | 6 | Players needed to start session |
| `SESSION_END_THRESHOLD` | 2 | Min players before ending |
| `SESSION_END_DELAY` | 300 | Wait time before ending (sec) |

**Advanced:**
| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `LOCAL_STATS_PATH` | ./local_stats | Local directory for stats files |
| `METRICS_DB_PATH` | bot/data/metrics.db | Metrics database path |

---

## 🐛 Troubleshooting

### Bot Won't Start

**Error: `ModuleNotFoundError: No module named 'discord'`**

**Solution:**
```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

---

**Error: `KeyError: 'DISCORD_BOT_TOKEN'`**

**Solution:**
- Check `.env` file exists in project root
- Verify `DISCORD_BOT_TOKEN` is set
- No spaces around `=`: `DISCORD_BOT_TOKEN=abc123` ✅ not `DISCORD_BOT_TOKEN = abc123` ❌

---

**Error: `psycopg2.OperationalError: FATAL: database "etlegacy" does not exist`**

**Solution:**
```bash
# Create database
sudo -u postgres createuser -P etlegacy_user  # If user doesn't exist
sudo -u postgres createdb -O etlegacy_user etlegacy

# Create schema
python recreate_database.py
```

---

### Database Connection Issues

**Error: `connection refused` or `could not connect`**

**Solution:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Start if stopped
sudo systemctl start postgresql

# Verify connection manually
psql -U etlegacy_user -d etlegacy -h localhost
```

---

**Error: `Peer authentication failed for user "etlegacy_user"`**

**Solution:**
Edit `/etc/postgresql/14/main/pg_hba.conf`:
```
# Change:
local   all   all   peer

# To:
local   all   all   md5
```
Then reload: `sudo systemctl reload postgresql`

---

### SSH Monitoring Issues

**Error: `SSH list files error: Authentication failed`**

**Solution:**
```bash
# Test SSH connection manually
ssh -i ~/.ssh/etlegacy_bot YOUR_USER@YOUR_SERVER

# If fails, regenerate and copy key
ssh-keygen -t rsa -b 4096 -f ~/.ssh/etlegacy_bot
ssh-copy-id -i ~/.ssh/etlegacy_bot.pub YOUR_USER@YOUR_SERVER

# Check key permissions
chmod 600 ~/.ssh/etlegacy_bot
```

---

**Error: `Permission denied (publickey)`**

**Solution:**
- Verify public key is in server's `~/.ssh/authorized_keys`
- Check file permissions on server:
  ```bash
  chmod 700 ~/.ssh
  chmod 600 ~/.ssh/authorized_keys
  ```
- Verify `SSH_KEY_PATH` in `.env` points to private key (NOT `.pub` file)

---

### Discord Bot Issues

**Bot is offline in Discord**

**Solutions:**
1. Check bot is running: `ps aux | grep ultimate_bot`
2. Check logs: `tail -f logs/bot.log`
3. Verify intents enabled in Discord Developer Portal
4. Regenerate bot token if compromised

---

**Commands don't work**

**Solutions:**
1. Verify you're in a `BOT_COMMAND_CHANNELS` channel
2. Check bot has permissions in that channel
3. Try `!ping` - if this doesn't work, bot isn't running
4. Check logs for errors

---

**"No stats found" for players**

**Solutions:**
1. Verify database has data: `psql -U etlegacy_user -d etlegacy -c "SELECT COUNT(*) FROM rounds;"`
2. Check R0 filtering isn't over-filtering
3. Import stats: `!sync_stats` or `!sync_today`

---

### Where Are the Logs?

```bash
# Main bot log
tail -f logs/bot.log

# Errors only
tail -f logs/errors.log

# Database operations
tail -f logs/database.log

# Commands executed
tail -f logs/commands.log
```

---

### Complete Reset (Nuclear Option)

**Warning:** This deletes all data!

```bash
# Stop bot
pkill -f ultimate_bot.py

# Drop and recreate database
sudo -u postgres dropdb etlegacy
sudo -u postgres createdb -O etlegacy_user etlegacy

# Recreate schema
python recreate_database.py

# Restart bot
python bot/ultimate_bot.py
```

---

## 🚀 Production Deployment

### Option 1: systemd Service (Linux - Recommended)

**Create service file:**

```bash
sudo nano /etc/systemd/system/etlegacy-bot.service
```

**Paste this (edit paths):**

```ini
[Unit]
Description=ET:Legacy Discord Stats Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_GROUP
WorkingDirectory=/path/to/slomix
Environment="PATH=/path/to/slomix/.venv/bin"
ExecStart=/path/to/slomix/.venv/bin/python bot/ultimate_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/path/to/slomix/logs/systemd.log
StandardError=append:/path/to/slomix/logs/systemd.log

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable etlegacy-bot

# Start now
sudo systemctl start etlegacy-bot

# Check status
sudo systemctl status etlegacy-bot

# View logs
sudo journalctl -u etlegacy-bot -f
```

**Manage service:**
```bash
sudo systemctl stop etlegacy-bot     # Stop
sudo systemctl restart etlegacy-bot  # Restart
sudo systemctl status etlegacy-bot   # Status
```

---

### Option 2: screen (Simple Method)

**Start in detached screen:**

```bash
# Create new screen session
screen -S etbot

# Activate venv and start bot
cd /path/to/slomix
source .venv/bin/activate
python bot/ultimate_bot.py

# Detach: Press Ctrl+A, then D
```

**Manage screen session:**

```bash
# List sessions
screen -ls

# Reattach to session
screen -r etbot

# Kill session
screen -S etbot -X quit
```

---

### Option 3: tmux (Alternative to screen)

```bash
# Create new session
tmux new -s etbot

# Activate venv and start bot
cd /path/to/slomix
source .venv/bin/activate
python bot/ultimate_bot.py

# Detach: Press Ctrl+B, then D
```

**Manage tmux:**

```bash
# List sessions
tmux ls

# Attach to session
tmux attach -t etbot

# Kill session
tmux kill-session -t etbot
```

---

### Log Rotation (Recommended)

**Create `/etc/logrotate.d/etlegacy-bot`:**

```
/path/to/slomix/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    create 0644 YOUR_USER YOUR_GROUP
}
```

**Test configuration:**
```bash
sudo logrotate -d /etc/logrotate.d/etlegacy-bot
sudo logrotate -f /etc/logrotate.d/etlegacy-bot
```

---

### Monitoring (Optional)

**Health Check Script:**

```bash
#!/bin/bash
# check_bot.sh - Add to cron

if ! pgrep -f "ultimate_bot.py" > /dev/null; then
    echo "Bot is down! Restarting..."
    systemctl start etlegacy-bot
fi
```

**Add to crontab:**
```bash
crontab -e

# Check every 5 minutes
*/5 * * * * /path/to/check_bot.sh
```

---

## 🔄 Updating the Bot

### Safe Update Procedure

```bash
# 1. Backup database
pg_dump -U etlegacy_user etlegacy > backup_$(date +%Y%m%d).sql

# 2. Stop bot
sudo systemctl stop etlegacy-bot  # or pkill -f ultimate_bot.py

# 3. Pull updates
git pull origin main

# 4. Check for schema changes
git log --oneline --grep="schema\|migration\|database" HEAD@{1}..HEAD

# 5. Update dependencies
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# 6. Migrate database if needed
# Check commit messages for migration instructions

# 7. Restart bot
sudo systemctl start etlegacy-bot

# 8. Verify
!ping  # In Discord
```

---

### Rolling Back

```bash
# Stop bot
sudo systemctl stop etlegacy-bot

# Restore database
psql -U etlegacy_user -d etlegacy < backup_YYYYMMDD.sql

# Revert code
git checkout previous_commit_hash

# Restart
sudo systemctl start etlegacy-bot
```

---

## 🛡️ Security Best Practices

### Protect Your Bot Token

**✅ DO:**
- Keep `.env` in `.gitignore`
- Never commit tokens to git
- Regenerate token if exposed
- Use environment variables in production

**❌ DON'T:**
- Share your token
- Commit `.env` to repository
- Post screenshots with tokens visible

---

### PostgreSQL Security

**✅ DO:**
- Use strong passwords
- Restrict network access
- Keep PostgreSQL updated
- Regular backups

**❌ DON'T:**
- Use default passwords
- Expose PostgreSQL to internet
- Run as root user

---

### SSH Key Security

**✅ DO:**
- Use 4096-bit RSA keys
- Set proper file permissions (600)
- Use passphrase for production
- Restrict key to specific commands (advanced)

**❌ DON'T:**
- Share private keys
- Use weak keys (1024-bit)
- Leave keys world-readable

---

## 📚 Additional Resources

- **ET:Legacy Official Site:** https://www.etlegacy.com/
- **Discord.py Documentation:** https://discordpy.readthedocs.io/
- **PostgreSQL Documentation:** https://www.postgresql.org/docs/
- **Python Virtual Environments:** https://docs.python.org/3/tutorial/venv.html

---

## 🐛 Common Issues - Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Bot offline | Not running / token invalid | Check process, verify token |
| Commands don't work | Wrong channel / no permissions | Check `BOT_COMMAND_CHANNELS`, permissions |
| Database errors | DB not created / wrong credentials | Check `.env`, recreate schema |
| SSH errors | Wrong key / permissions | Test SSH manually, check permissions |
| "No stats found" | No data imported | Run `!sync_stats` or `!sync_today` |
| Duplicate responses | Multiple bot processes | Kill all: `pkill -f ultimate_bot` |
| ImportError | Dependencies not installed | `pip install -r requirements.txt` |

---

## 💬 Getting Help

1. **Check logs:** `logs/bot.log`, `logs/errors.log`
2. **Search issues:** GitHub Issues tab
3. **Ask in Discord:** [Your Discord server link]
4. **Create issue:** [GitHub Issues link]

When reporting issues, include:
- ✅ Python version: `python --version`
- ✅ PostgreSQL version: `psql --version`
- ✅ Relevant log excerpts
- ✅ Steps to reproduce

---

## 📄 License

[Your License Here]

---

## 🙏 Credits

Built for the ET:Legacy community with ❤️

---

**Happy fragging! 🎮**
