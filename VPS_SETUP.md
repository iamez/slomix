# ET:Legacy Discord Bot - VPS Quick Setup Guide

## Prerequisites
- Debian/Ubuntu Linux VPS
- Root or sudo access
- Bot code in: `/home/samba/share/slomix_discord/`

## Installation Steps

### 1. SSH into your VPS
```bash
ssh your_user@your_vps_ip
cd /home/samba/share/slomix_discord/
```

### 2. Make install script executable and run it
```bash
chmod +x vps_install.sh
./vps_install.sh
```

The script will:
- ✅ Install Python 3, pip, PostgreSQL
- ✅ Create database `etlegacy`
- ✅ Create user `etlegacy_user`
- ✅ Set up Python virtual environment
- ✅ Install all Python packages
- ✅ Create `.env` configuration file
- ✅ Initialize database tables

### 3. Edit `.env` file with your credentials
```bash
nano .env
```

**Required settings:**
```bash
# Discord
DISCORD_BOT_TOKEN=YOUR_ACTUAL_DISCORD_TOKEN_HERE

# PostgreSQL (password must match what you set in install script)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=change_this_password
POSTGRES_MIN_POOL=10
POSTGRES_MAX_POOL=30

# Stats Files
LOCAL_STATS_PATH=/path/to/your/stats/files
```

Save and exit (Ctrl+X, Y, Enter)

### 4. Start the bot
```bash
chmod +x start_bot.sh
./start_bot.sh
```

## Troubleshooting

**PostgreSQL password issue:**
```bash
sudo -u postgres psql
ALTER USER etlegacy_user WITH PASSWORD 'your_new_password';
\q
```
Then update `.env` with the new password.

**Database doesn't exist:**
```bash
sudo -u postgres psql
CREATE DATABASE etlegacy;
GRANT ALL PRIVILEGES ON DATABASE etlegacy TO etlegacy_user;
\q
```

**Check if bot is running:**
```bash
ps aux | grep python
```

**View bot logs:**
```bash
tail -f logs/bot.log
```

**Stop the bot:**
```bash
pkill -f "python bot/ultimate_bot.py"
```

## Running as a Service (Optional)

Create systemd service to auto-start bot:

```bash
sudo nano /etc/systemd/system/etlegacy-bot.service
```

Paste this:
```ini
[Unit]
Description=ET:Legacy Discord Bot
After=network.target postgresql.service

[Service]
Type=simple
User=samba
WorkingDirectory=/home/samba/share/slomix_discord
ExecStart=/home/samba/share/slomix_discord/venv/bin/python /home/samba/share/slomix_discord/bot/ultimate_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable etlegacy-bot
sudo systemctl start etlegacy-bot
sudo systemctl status etlegacy-bot
```

View logs:
```bash
sudo journalctl -u etlegacy-bot -f
```
