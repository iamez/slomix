# VPS Deployment Instructions

## Quick Setup

On your VPS, run these commands:

```bash
cd /home/samba/share/slomix_discord/
chmod +x vps_setup.sh
./vps_setup.sh
```

The script will:
1. ✅ Install system dependencies (Python, PostgreSQL, git)
2. ✅ Create PostgreSQL database `etlegacy` with user `etlegacy_user`
3. ✅ Create Python virtual environment
4. ✅ Install all Python packages from requirements.txt
5. ✅ Create .env file with your configuration
6. ✅ Initialize database schema with all tables
7. ✅ (Optional) Set up systemd service for auto-start

## What You'll Need During Setup

The script will prompt you for:
- **PostgreSQL password** for `etlegacy_user` (choose a secure password)
- **Discord Bot Token** (get from Discord Developer Portal or your local .env file)
- **Discord Guild ID** (your Discord server ID)
- **Stats Channel ID** (optional - channel where stats are posted)

## Database Configuration

The script creates:
```
Database: etlegacy
User:     etlegacy_user
Host:     localhost
Port:     5432
Tables:   7 (auto-created by bot)
```

## After Installation

### Option 1: Run as systemd service (recommended)
```bash
sudo systemctl start etlegacy-bot
sudo systemctl status etlegacy-bot
sudo journalctl -u etlegacy-bot -f  # View logs
```

### Option 2: Run manually
```bash
source .venv/bin/activate
python3 bot/ultimate_bot.py
```

### Option 3: Run in screen (persistent background)
```bash
screen -S etlegacy-bot
source .venv/bin/activate
python3 bot/ultimate_bot.py
# Press Ctrl+A then D to detach
# Reattach with: screen -r etlegacy-bot
```

## Troubleshooting

### Check database connection:
```bash
sudo -u postgres psql -d etlegacy -c "\dt"  # List tables
sudo -u postgres psql -d etlegacy -c "SELECT COUNT(*) FROM rounds;"
```

### Check logs:
```bash
tail -f logs/bot.log
```

### Check Python environment:
```bash
source .venv/bin/activate
python3 -c "import discord; print(discord.__version__)"
```

### Reinstall if needed:
```bash
./vps_setup.sh  # Script is idempotent, safe to re-run
```

## File Locations

```
/home/samba/share/slomix_discord/
├── .env                    # Configuration (created by script)
├── bot/                    # Bot code (14 cogs + core)
├── .venv/                  # Python virtual environment
├── local_stats/            # Stats files directory
├── logs/                   # Bot logs
└── postgresql_database_manager.py
```

## Security Notes

- `.env` file is chmod 600 (only you can read)
- Database user `etlegacy_user` has limited privileges
- Bot runs as your user (not root)
