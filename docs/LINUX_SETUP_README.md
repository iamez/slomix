# Linux VPS Setup - Quick Start

> **Note:** This guide has been updated to use the new unified `install.sh` script.  
> Old scripts (`setup_linux_bot.sh`, `vps_install.sh`, `vps_setup.sh`) are deprecated.  
> See [INSTALL_SCRIPTS_DEPRECATED.md](../INSTALL_SCRIPTS_DEPRECATED.md) for migration details.

## One-Command Installation

### Step 1: Copy install script to your VPS

```bash
# On your Windows machine, from the stats directory
scp -i ~/.ssh/etlegacy_bot install.sh et@puran.hehe.si:/tmp/
```

### Step 2: Run the setup script on VPS

```bash
# SSH into your VPS
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si

# Run the unified install script
sudo bash /tmp/install.sh --full --interactive
```

**Alternative: Automated (non-interactive) installation**
```bash
sudo bash /tmp/install.sh --full --auto
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

## Installation Options

The unified `install.sh` script supports multiple modes:

### Full Installation (Recommended for new VPS)
```bash
# Interactive (prompts for all settings)
sudo ./install.sh --full --interactive

# Automatic (auto-generates passwords)
sudo ./install.sh --full --auto
```

### VPS Setup (Repository already cloned)
```bash
# Interactive
sudo ./install.sh --vps --interactive

# Automatic
sudo ./install.sh --vps --auto
```

### Environment Only (No database/systemd)
```bash
# For development or testing
./install.sh --env-only
```

### View All Options
```bash
./install.sh --help
```

---

## What You'll Need

When using interactive mode (`--interactive`), the script will ask for:
- **Discord Bot Token** - From your `.env` file: `DISCORD_BOT_TOKEN`
- **PostgreSQL Password** - Will be auto-generated in `--auto` mode or prompted in `--interactive` mode

In auto mode (`--auto`), passwords are generated automatically and saved to `.env`.

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
- `/slomix/.env` - Bot configuration (with your token and database password)
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
cat /slomix/.env
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

The install script uses these default values:

**PostgreSQL:**
- Host: `localhost`
- Port: `5432`
- Database: `etlegacy`
- User: `etlegacy_user`
- Password: Auto-generated (saved to `.env`)

**Paths:**
- Deploy directory: `/slomix` (configurable with `--deploy-dir`)
- Stats path: `local_stats/`

You can customize these with command-line options:
```bash
sudo ./install.sh --full --auto \
  --deploy-dir /opt/mybot \
  --pg-user myuser \
  --pg-database mydb
```

---

## Security Notes

After installation:

1. **Secure .env file**
   ```bash
   chmod 600 /slomix/.env
   ```
   (This is done automatically by the install script)

2. **Review generated password**
   ```bash
   cat /slomix/.env | grep POSTGRES_PASSWORD
   ```

3. **Change PostgreSQL password** (optional)
   ```bash
   sudo -u postgres psql
   ALTER USER etlegacy_user WITH PASSWORD 'your_new_password';
   \q
   # Update /slomix/.env with new password
   ```

3. **Firewall rules**
   ```bash
   # PostgreSQL should only listen on localhost (default)
   sudo ss -tunlp | grep 5432
   ```

---

## Migrating from Old Scripts

If you previously used `setup_linux_bot.sh`, `vps_install.sh`, or `vps_setup.sh`:

- All functionality is preserved in `install.sh`
- See [INSTALL_SCRIPTS_DEPRECATED.md](../INSTALL_SCRIPTS_DEPRECATED.md) for migration guide
- Old scripts still work but show deprecation warnings

**Migration examples:**
```bash
# Old: ./setup_linux_bot.sh
# New: sudo ./install.sh --full --interactive

# Old: ./vps_install.sh
# New: sudo ./install.sh --vps --auto

# Old: ./vps_setup.sh
# New: sudo ./install.sh --vps --interactive
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
