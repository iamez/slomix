# Linux VPS Setup - Quick Start

## One-Command Installation

### Step 1: Copy setup script to your VPS

```bash
# On your Windows machine, from the stats directory
scp -i ~/.ssh/etlegacy_bot setup_linux_bot.sh et@puran.hehe.si:/tmp/
```

### Step 2: Run the setup script on VPS

```bash
# SSH into your VPS
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si

# Run the setup script
sudo bash /tmp/setup_linux_bot.sh
```

The script will:
- ✓ Install PostgreSQL 16
- ✓ Install Python 3 and dependencies  
- ✓ Clone repository to `/slomix`
- ✓ Setup database and import stats
- ✓ Create systemd service
- ✓ Start the bot

**That's it!** The bot will be running as a service.

---

## What You'll Need

When the script runs, it will ask for:
- **Discord Bot Token** - From your `.env` file: `DISCORD_BOT_TOKEN`

That's the only manual input needed!

---

## After Installation

### View logs
```bash
sudo journalctl -u etlegacy-bot -f
```

### Check bot status
```bash
sudo systemctl status etlegacy-bot
```

### Restart bot
```bash
sudo systemctl restart etlegacy-bot
```

### Update bot code
```bash
cd /slomix
bash update_bot.sh
```

---

## Files Created

- `/slomix/` - Bot code and repository
- `/slomix/bot/config.json` - Bot configuration (with your token)
- `/etc/systemd/system/etlegacy-bot.service` - Service file
- PostgreSQL database: `etlegacy` (user: `etlegacy_user`)

---

## Re-import Stats (Nuclear Rebuild)

If you need to re-import all stats:

```bash
cd /slomix
venv/bin/python3 postgresql_database_manager.py
sudo systemctl restart etlegacy-bot
```

---

## Troubleshooting

### Bot won't start
```bash
# Check logs
sudo journalctl -u etlegacy-bot -n 50

# Check config
cat /slomix/bot/config.json
```

### Database connection issues
```bash
# Test database connection
psql -U etlegacy_user -d etlegacy -c "SELECT COUNT(*) FROM rounds;"

# If password fails, reset it
sudo -u postgres psql
ALTER USER etlegacy_user WITH PASSWORD 'etlegacy_secure_2025';
\q
```

### Stats not importing
```bash
# Check stats directory exists
ls -la /home/et/.etlegacy/legacy/gamestats/

# Make sure bot user can access it
sudo chmod -R 755 /home/et/.etlegacy/legacy/gamestats/
```

---

## Configuration from .env

The setup script uses these default values:

**PostgreSQL:**
- Host: `localhost`
- Port: `5432`
- Database: `etlegacy`
- User: `etlegacy_user`
- Password: `etlegacy_secure_2025`

**Paths:**
- Deploy directory: `/slomix`
- Stats path: `/home/et/.etlegacy/legacy/gamestats`

You can edit the script if you need different values.

---

## Security Notes

After installation:

1. **Secure config.json**
   ```bash
   chmod 600 /slomix/bot/config.json
   ```

2. **Change PostgreSQL password** (optional)
   ```bash
   sudo -u postgres psql
   ALTER USER etlegacy_user WITH PASSWORD 'your_new_password';
   \q
   # Update /slomix/bot/config.json with new password
   ```

3. **Firewall rules**
   ```bash
   # PostgreSQL should only listen on localhost (default)
   sudo ss -tunlp | grep 5432
   ```

---

## Uninstall

To completely remove the bot:

```bash
# Stop and disable service
sudo systemctl stop etlegacy-bot
sudo systemctl disable etlegacy-bot
sudo rm /etc/systemd/system/etlegacy-bot.service
sudo systemctl daemon-reload

# Remove database
sudo -u postgres psql -c "DROP DATABASE etlegacy;"
sudo -u postgres psql -c "DROP USER etlegacy_user;"

# Remove bot files
sudo rm -rf /slomix
```

---

## Expected Results

After successful installation, you should have:

- **Bot running** as systemd service
- **Database populated** with stats from game server
- **Discord commands working**: `!last_session`, `!stats`, `!leaderboard`

Test data (from current Windows setup):
- 245 rounds
- 18 gaming sessions  
- 1,651 player stats
- 12,005 weapon stats
- Date range: 2025-10-17 to 2025-11-04

---

## Getting Help

If you encounter issues:

1. Check the logs first: `sudo journalctl -u etlegacy-bot -n 100`
2. Verify database: `psql -U etlegacy_user -d etlegacy`
3. Check service: `sudo systemctl status etlegacy-bot`
4. Re-run setup script if needed (it's safe to run multiple times)

The bot includes comprehensive validation and will report issues in logs.
