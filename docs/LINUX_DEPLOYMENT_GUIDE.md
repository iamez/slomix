# Linux VPS Deployment Guide

## Automated Deployment (Recommended)

### Prerequisites

1. Python 3.8+ installed on Windows
2. SSH key configured for VPS access
3. `.env` file with all configuration

### Run Deployment

**Option 1: Windows Batch Script**

```batch
deploy.bat
```text

**Option 2: Python Script Directly**

```bash
python deploy_to_linux.py
```sql

The script will automatically:

- ✓ Test SSH connection
- ✓ Install PostgreSQL 16
- ✓ Install Python dependencies
- ✓ Clone/update repository
- ✓ Create bot configuration
- ✓ Initialize database
- ✓ Create systemd service
- ✓ Start the bot

---

## Manual Deployment (If Automated Script Fails)

### Step 1: Connect to VPS

```bash
ssh samba@192.168.64.116
```text

### Step 2: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install PostgreSQL
sudo apt install -y postgresql-16 postgresql-contrib

# Install Python
sudo apt install -y python3 python3-pip python3-venv git

# Install build dependencies
sudo apt install -y python3-dev libpq-dev
```text

### Step 3: Setup PostgreSQL

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE USER etlegacy_user WITH PASSWORD 'REDACTED_DB_PASSWORD';
CREATE DATABASE etlegacy OWNER etlegacy_user;
GRANT ALL PRIVILEGES ON DATABASE etlegacy TO etlegacy_user;
\c etlegacy
GRANT ALL ON SCHEMA public TO etlegacy_user;
\q
```text

### Step 4: Clone Repository

```bash
cd /slomix
git clone -b vps-network-migration https://github.com/iamez/slomix.git .
```text

### Step 5: Configure Bot

Create `/slomix/bot/config.json`:

```json
{
  "token": "YOUR_DISCORD_TOKEN_FROM_ENV",
  "database_type": "postgresql",
  "db_config": {
    "host": "localhost",
    "port": 5432,
    "database": "etlegacy",
    "user": "etlegacy_user",
    "password": "REDACTED_DB_PASSWORD"
  }
}
```text

### Step 6: Setup Python Environment

```bash
cd /slomix
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```text

### Step 7: Populate Database

```bash
cd /slomix
venv/bin/python3 postgresql_database_manager.py
```python

This will:

- Create all database tables
- Import stats from `/home/et/.etlegacy/legacy/gamestats`
- Calculate gaming sessions
- Run validation checks

### Step 8: Create Systemd Service

```bash
sudo nano /etc/systemd/system/etlegacy-bot.service
```text

Paste this content:

```ini
[Unit]
Description=ET Legacy Discord Bot
After=network.target postgresql.service

[Service]
Type=simple
User=samba
WorkingDirectory=/slomix
Environment="PATH=/slomix/venv/bin"
ExecStart=/slomix/venv/bin/python3 /slomix/bot/ultimate_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```text

### Step 9: Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable etlegacy-bot
sudo systemctl start etlegacy-bot
```text

### Step 10: Verify Deployment

```bash
# Check service status
sudo systemctl status etlegacy-bot

# View live logs
sudo journalctl -u etlegacy-bot -f

# Check database
psql -U etlegacy_user -d etlegacy -c "SELECT COUNT(*) FROM rounds;"
```yaml

---

## Post-Deployment Management

### View Logs

```bash
# Live logs (follow mode)
sudo journalctl -u etlegacy-bot -f

# Last 100 lines
sudo journalctl -u etlegacy-bot -n 100

# Logs from today
sudo journalctl -u etlegacy-bot --since today
```text

### Control Bot Service

```bash
# Restart bot
sudo systemctl restart etlegacy-bot

# Stop bot
sudo systemctl stop etlegacy-bot

# Start bot
sudo systemctl start etlegacy-bot

# Check status
sudo systemctl status etlegacy-bot
```sql

### Update Bot Code

```bash
cd /slomix
git pull origin vps-network-migration
sudo systemctl restart etlegacy-bot
```text

### Database Management

```bash
# Connect to PostgreSQL
psql -U etlegacy_user -d etlegacy

# Check stats count
SELECT COUNT(*) FROM rounds;
SELECT COUNT(*) FROM player_comprehensive_stats;
SELECT COUNT(*) FROM weapon_comprehensive_stats;

# Check gaming sessions
SELECT gaming_session_id, COUNT(*) as rounds
FROM rounds
GROUP BY gaming_session_id
ORDER BY gaming_session_id;
```python

### Re-import Stats (Nuclear Rebuild)

```bash
cd /slomix
venv/bin/python3 postgresql_database_manager.py
sudo systemctl restart etlegacy-bot
```yaml

---

## Troubleshooting

### Bot Won't Start

```bash
# Check logs for errors
sudo journalctl -u etlegacy-bot -n 50

# Check if PostgreSQL is running
sudo systemctl status postgresql

# Test database connection
psql -U etlegacy_user -d etlegacy -c "SELECT 1;"

# Check config file
cat /slomix/bot/config.json
```text

### Database Connection Issues

```bash
# Reset PostgreSQL password
sudo -u postgres psql
ALTER USER etlegacy_user WITH PASSWORD 'REDACTED_DB_PASSWORD';
\q

# Check PostgreSQL is listening
sudo ss -tunlp | grep 5432

# Edit pg_hba.conf if needed
sudo nano /etc/postgresql/16/main/pg_hba.conf
```text

### Permission Issues

```bash
# Fix ownership
sudo chown -R samba:samba /slomix

# Fix PostgreSQL permissions
sudo -u postgres psql -d etlegacy
GRANT ALL ON SCHEMA public TO etlegacy_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO etlegacy_user;
```python

### Import Stats Not Working

```bash
# Check stats directory exists and has files
ls -la /home/et/.etlegacy/legacy/gamestats/

# Check samba user can access stats
sudo -u samba ls /home/et/.etlegacy/legacy/gamestats/

# If permission denied, add samba to et group
sudo usermod -aG et samba
```sql

---

## Configuration from .env

The deployment script reads these values from your `.env` file:

- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `GUILD_ID` - Your Discord server ID
- `SSH_HOST` - VPS hostname (default: from .env)
- `SSH_USER` - SSH username (default: samba)
- `SSH_KEY_PATH` - Path to SSH private key
- `REMOTE_STATS_PATH` - Stats directory on VPS

PostgreSQL credentials (default):

- Host: localhost
- Port: 5432
- Database: etlegacy
- User: etlegacy_user
- Password: REDACTED_DB_PASSWORD

---

## Testing Deployment

Once deployed, test these Discord commands:

1. `!last_session` - Should show latest session stats with embeds and graphs
2. `!session` - Should list all available sessions
3. `!stats player_name` - Should show player statistics
4. `!leaderboard` - Should show top players
5. `!help` - Should show all available commands

Expected data:

- 245 rounds
- 18 gaming sessions
- 1,651 player stats
- 12,005 weapon stats
- Date range: 2025-10-17 to 2025-11-04

---

## Security Notes

1. **Never commit config.json or .env to git** - Contains sensitive tokens
2. **Use strong PostgreSQL password** - Default is example only
3. **Secure SSH keys** - Keep private keys safe, use ed25519 or RSA 4096+
4. **Firewall rules** - Only allow necessary ports (SSH, PostgreSQL internal only)
5. **Regular updates** - Keep system, PostgreSQL, and bot dependencies updated

---

## Backup Strategy

### Database Backup

```bash
# Backup database
pg_dump -U etlegacy_user etlegacy > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
psql -U etlegacy_user etlegacy < backup_20251105_120000.sql
```text

### Full Backup

```bash
# Backup everything
tar -czf slomix_backup_$(date +%Y%m%d).tar.gz /slomix
```yaml

---

## Performance Monitoring

### Check Resource Usage

```bash
# CPU and memory
htop

# Disk space
df -h

# PostgreSQL stats
psql -U etlegacy_user -d etlegacy -c "SELECT pg_size_pretty(pg_database_size('etlegacy'));"
```text

### Optimize PostgreSQL

```bash
# Run VACUUM ANALYZE periodically
psql -U etlegacy_user -d etlegacy -c "VACUUM ANALYZE;"

# Check for slow queries
psql -U etlegacy_user -d etlegacy -c "SELECT query, calls, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

---

## Getting Help

If you encounter issues:

1. Check logs: `sudo journalctl -u etlegacy-bot -n 100`
2. Check database: `psql -U etlegacy_user -d etlegacy`
3. Check service status: `sudo systemctl status etlegacy-bot`
4. Check bot code: Review error messages in logs
5. Nuclear rebuild: Re-run `postgresql_database_manager.py`

The bot uses comprehensive validation and should report any data issues in logs.
