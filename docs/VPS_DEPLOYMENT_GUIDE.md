# VPS Deployment Guide - Split Architecture

**ET:Legacy Discord Bot - PostgreSQL Database + Bot on Separate Servers**

## 🏗️ Architecture Overview

```text
┌─────────────────────┐         ┌─────────────────────┐
│   VPS 1: Database   │◄───────►│   VPS 2: Bot        │
│   PostgreSQL Server │  5432   │   Discord Bot       │
│   (Debian/Arch)     │         │   (Debian/Arch)     │
└─────────────────────┘         └─────────────────────┘
```bash

**Recommended Setup:**

- **VPS 1 (Database)**: 2GB RAM, 20GB SSD - Hosts PostgreSQL
- **VPS 2 (Bot)**: 1GB RAM, 10GB SSD - Hosts Discord bot

## 📋 Prerequisites

- Two VPS servers with SSH access
- Root/sudo access on both
- Discord bot token
- GitHub repository access

---

## 🗄️ Part 1: Database Server Setup

Choose your database server OS and follow the appropriate section.

### Option A: Debian/Ubuntu Database Server

```bash
# 1. SSH into your database server
ssh root@your-db-server-ip

# 2. Download setup script
wget https://raw.githubusercontent.com/iamez/slomix/vps-network-migration/tools/setup_postgresql_debian.sh

# Or use git:
git clone https://github.com/iamez/slomix.git /tmp/slomix
cd /tmp/slomix
git checkout vps-network-migration

# 3. Make script executable
chmod +x tools/setup_postgresql_debian.sh

# 4. Run setup script
sudo ./tools/setup_postgresql_debian.sh

# 5. Save the credentials displayed (they're also in /root/etlegacy_db_credentials.txt)
```text

### Option B: Arch/EndeavourOS Database Server

```bash
# 1. SSH into your database server
ssh root@your-db-server-ip

# 2. Download setup script
wget https://raw.githubusercontent.com/iamez/slomix/vps-network-migration/tools/setup_postgresql_arch.sh

# Or use git:
git clone https://github.com/iamez/slomix.git /tmp/slomix
cd /tmp/slomix
git checkout vps-network-migration

# 3. Make script executable
chmod +x tools/setup_postgresql_arch.sh

# 4. Run setup script
sudo ./tools/setup_postgresql_arch.sh

# 5. Save the credentials displayed
```text

### Apply Database Schema

```bash
# On database server, copy schema from your local machine:
# (Run this from your Windows machine)
scp tools/schema_postgresql.sql root@DB_SERVER_IP:/tmp/

# On database server, apply schema:
sudo -u postgres psql -d etlegacy -f /tmp/schema_postgresql.sql

# Verify schema was applied:
sudo -u postgres psql -d etlegacy -c "\dt"
```text

### Secure Database Server

```bash
# Edit pg_hba.conf to restrict access to bot server only
# Debian/Ubuntu:
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Arch/EndeavourOS:
sudo nano /var/lib/postgres/data/pg_hba.conf

# Replace this line:
host    etlegacy    etlegacy_user    0.0.0.0/0    md5

# With (replace BOT_SERVER_IP with your bot server's actual IP):
host    etlegacy    etlegacy_user    BOT_SERVER_IP/32    md5

# Restart PostgreSQL:
sudo systemctl restart postgresql
```yaml

---

## 🤖 Part 2: Bot Server Setup

Choose your bot server OS and follow the appropriate section.

### Option A: Debian/Ubuntu Bot Server

```bash
# 1. SSH into your bot server
ssh root@your-bot-server-ip

# 2. Download setup script
git clone https://github.com/iamez/slomix.git /tmp/slomix
cd /tmp/slomix
git checkout vps-network-migration

# 3. Run bot server setup
sudo ./tools/setup_bot_server_debian.sh

# 4. Clone repository as etlegacy user
sudo -u etlegacy git clone https://github.com/iamez/slomix.git /home/etlegacy/bot
cd /home/etlegacy/bot
sudo -u etlegacy git checkout vps-network-migration

# 5. Create virtual environment
sudo -u etlegacy python3 -m venv /home/etlegacy/bot/.venv

# 6. Install requirements
sudo -u etlegacy /home/etlegacy/bot/.venv/bin/pip install -r requirements.txt

# 7. Create config.json
sudo -u etlegacy nano /home/etlegacy/bot/config.json
```text

### Option B: Arch/EndeavourOS Bot Server

```bash
# 1. SSH into your bot server
ssh root@your-bot-server-ip

# 2. Download setup script
git clone https://github.com/iamez/slomix.git /tmp/slomix
cd /tmp/slomix
git checkout vps-network-migration

# 3. Run bot server setup
sudo ./tools/setup_bot_server_arch.sh

# 4. Clone repository as etlegacy user
sudo -u etlegacy git clone https://github.com/iamez/slomix.git /home/etlegacy/bot
cd /home/etlegacy/bot
sudo -u etlegacy git checkout vps-network-migration

# 5. Create virtual environment
sudo -u etlegacy python -m venv /home/etlegacy/bot/.venv

# 6. Install requirements
sudo -u etlegacy /home/etlegacy/bot/.venv/bin/pip install -r requirements.txt

# 7. Create config.json
sudo -u etlegacy nano /home/etlegacy/bot/config.json
```text

### Configure Bot

Create `/home/etlegacy/bot/config.json`:

```json
{
  "token": "YOUR_DISCORD_BOT_TOKEN_HERE",
  "database_type": "postgresql",
  "postgresql_host": "DB_SERVER_IP_HERE",
  "postgresql_port": 5432,
  "postgresql_database": "etlegacy",
  "postgresql_user": "etlegacy_user",
  "postgresql_password": "PASSWORD_FROM_DB_SERVER",
  "stats_channel_id": "YOUR_DISCORD_CHANNEL_ID",
  "admin_channel_id": "YOUR_DISCORD_CHANNEL_ID"
}
```text

### Test Database Connection

```bash
# Install PostgreSQL client if not already installed
# Debian/Ubuntu:
sudo apt install postgresql-client

# Arch:
sudo pacman -S postgresql-libs

# Test connection from bot server to database server:
psql -h DB_SERVER_IP -U etlegacy_user -d etlegacy -c "SELECT version();"
```sql

---

## 📦 Part 3: Migrate Data

### Option 1: Migrate from Windows to VPS

```bash
# On your Windows machine:
# 1. Copy database to bot server
scp bot/etlegacy_production.db etlegacy@BOT_SERVER_IP:/home/etlegacy/bot/bot/

# 2. Copy migration script if needed
scp tools/migrate_to_postgresql.py etlegacy@BOT_SERVER_IP:/home/etlegacy/bot/tools/

# 3. SSH into bot server
ssh etlegacy@BOT_SERVER_IP

# 4. Run migration
cd /home/etlegacy/bot
.venv/bin/python tools/migrate_to_postgresql.py
```text

### Option 2: Fresh Start (No Migration)

If you're starting fresh without existing data:

```bash
# Schema is already applied, so just start the bot!
sudo systemctl start etlegacy-bot
sudo systemctl status etlegacy-bot
```yaml

---

## 🚀 Part 4: Start the Bot

```bash
# Start the bot service
sudo systemctl start etlegacy-bot

# Enable auto-start on boot
sudo systemctl enable etlegacy-bot

# Check status
sudo systemctl status etlegacy-bot

# View logs
sudo journalctl -u etlegacy-bot -f

# Or view log file directly
tail -f /home/etlegacy/bot/logs/bot.log
```sql

---

## 🔧 Maintenance & Monitoring

### Update Bot Code

```bash
# SSH to bot server
ssh etlegacy@BOT_SERVER_IP

# Pull latest code
cd /home/etlegacy/bot
git pull origin vps-network-migration

# Restart bot
sudo systemctl restart etlegacy-bot
```text

### Database Backup

```bash
# SSH to database server
ssh root@DB_SERVER_IP

# Manual backup
pg_dump -U etlegacy_user -d etlegacy -F c -f /tmp/etlegacy_backup_$(date +%Y%m%d).dump

# Automated daily backup (add to crontab)
sudo crontab -e
# Add this line:
0 3 * * * pg_dump -U etlegacy_user -d etlegacy -F c -f /backups/etlegacy_$(date +\%Y\%m\%d).dump
```text

### Monitor Bot

```bash
# Check bot status
sudo systemctl status etlegacy-bot

# View live logs
sudo journalctl -u etlegacy-bot -f

# Check last 100 lines
sudo journalctl -u etlegacy-bot -n 100

# Check for errors
sudo journalctl -u etlegacy-bot | grep ERROR
```text

### Restart Bot

```bash
sudo systemctl restart etlegacy-bot
```text

### Stop Bot

```bash
sudo systemctl stop etlegacy-bot
```sql

---

## 🔒 Security Checklist

- [ ] Database server firewall configured (only allow port 5432 from bot server IP)
- [ ] pg_hba.conf restricted to bot server IP only
- [ ] SSH key authentication enabled (disable password auth)
- [ ] Strong passwords used for PostgreSQL user
- [ ] Regular backups scheduled
- [ ] Bot config.json has proper permissions (600)
- [ ] Discord bot token kept secure
- [ ] SSL/TLS for PostgreSQL connection (optional but recommended)

---

## 🐛 Troubleshooting

### Bot Can't Connect to Database

```bash
# Test connection from bot server:
psql -h DB_SERVER_IP -U etlegacy_user -d etlegacy

# Check PostgreSQL is listening:
# On DB server:
sudo netstat -plnt | grep 5432

# Check firewall on DB server:
sudo ufw status  # or iptables -L
```text

### Bot Won't Start

```bash
# Check logs for errors:
sudo journalctl -u etlegacy-bot -n 50

# Check config.json is valid:
python3 -m json.tool /home/etlegacy/bot/config.json

# Test bot manually:
cd /home/etlegacy/bot
.venv/bin/python bot/ultimate_bot.py
```text

### Migration Fails

```bash
# Check database is accessible:
psql -h DB_SERVER_IP -U etlegacy_user -d etlegacy -c "\dt"

# Check SQLite database exists:
ls -lh /home/etlegacy/bot/bot/etlegacy_production.db

# Run migration with verbose output:
.venv/bin/python tools/migrate_to_postgresql.py
```yaml

---

## 📊 Performance Tuning (Optional)

For large databases, tune PostgreSQL on DB server:

```bash
# Edit PostgreSQL config
# Debian/Ubuntu:
sudo nano /etc/postgresql/*/main/postgresql.conf

# Arch:
sudo nano /var/lib/postgres/data/postgresql.conf

# Recommended settings for 2GB RAM server:
shared_buffers = 512MB
effective_cache_size = 1536MB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1

# Restart PostgreSQL:
sudo systemctl restart postgresql
```

---

## ✅ Success Criteria

- [ ] Database server PostgreSQL running and accessible
- [ ] Schema applied successfully
- [ ] Bot server can connect to database
- [ ] Bot starts without errors
- [ ] All Discord commands working
- [ ] Logs show no errors
- [ ] Auto-start on boot configured
- [ ] Backups scheduled

---

## 🎉 You're Done

Your bot is now running with a production-ready split architecture:

- PostgreSQL on dedicated database server
- Discord bot on separate application server
- Secure network configuration
- Automated startup and monitoring

**Next Steps:**

- Monitor for 24-48 hours
- Test all commands thoroughly
- Set up monitoring/alerting (optional)
- Document your specific configuration
