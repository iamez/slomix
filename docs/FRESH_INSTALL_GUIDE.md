# 🆕 Fresh Installation Guide - Test Refactored Bot Separately

## Deploy to NEW Folder (Keep Existing Bot Running)

This guide shows how to install the refactored bot in a **new directory** so you can test it while keeping your current bot running.

---

## Step 1: Clone to New Directory

```bash
# SSH to your VPS
ssh your-user@your-vps

# Navigate to parent directory (NOT your current bot folder)
cd ~  # or wherever you want the new installation

# Clone into NEW directory
git clone https://github.com/iamez/slomix.git slomix-refactored

# Enter the new directory
cd slomix-refactored

# Checkout the refactored branch
git checkout claude/architecture-review-framework-01UyGTWjM75BCq5crDQ3qiu5

# Verify you're on the right branch
git branch
# Should show: * claude/architecture-review-framework-01UyGTWjM75BCq5crDQ3qiu5
```sql

---

## Step 2: Copy Configuration from Old Bot

```bash
# Copy .env file from your existing bot
cp ~/slomix/.env ~/slomix-refactored/.env

# Or create new .env if needed
nano .env
```text

**Add these settings:**

```env
# Discord Bot Token
DISCORD_BOT_TOKEN=your_discord_token_here

# PostgreSQL Database (same as your current bot)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy_stats
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password

# Optional: SSH settings (if using remote stats download)
SSH_ENABLED=false
AUTOMATION_ENABLED=false

# Stats directory
STATS_DIRECTORY=./local_stats
```yaml

**⚠️ IMPORTANT:**

- Use the **same database** as your old bot (shares data)
- Use a **different Discord token** if you want to run both bots simultaneously
- Or stop the old bot before starting the new one

---

## Step 3: Create Python Virtual Environment

```bash
# Make sure you're in slomix-refactored directory
cd ~/slomix-refactored

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```text

**Verify installation:**

```bash
# Check discord.py
pip list | grep discord

# Check asyncpg
pip list | grep asyncpg

# Should see:
# discord.py    2.x.x
# asyncpg       0.x.x
```yaml

---

## Step 4: Create local_stats Directory

```bash
# Create stats directory
mkdir -p local_stats

# Option A: Symlink to existing stats directory (shares files with old bot)
ln -s ~/slomix/local_stats ~/slomix-refactored/local_stats

# Option B: Copy existing stats files (independent copy)
cp -r ~/slomix/local_stats/* ~/slomix-refactored/local_stats/

# Option C: Start fresh (no old stats)
# Just leave local_stats/ empty
```yaml

---

## Step 5: Test Import

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Test new StatsCalculator module
python3 << 'PYEOF'
import sys
sys.path.insert(0, '.')

try:
    from bot.stats import StatsCalculator
    
    # Test calculations
    dpm = StatsCalculator.calculate_dpm(1200, 300)
    kd = StatsCalculator.calculate_kd(15, 5)
    acc = StatsCalculator.calculate_accuracy(50, 100)
    
    print("✅ StatsCalculator working!")
    print(f"   DPM: {dpm} (expected: 240.0)")
    print(f"   K/D: {kd} (expected: 3.0)")
    print(f"   Accuracy: {acc}% (expected: 50.0)")
    
    from bot.community_stats_parser import C0RNP0RN3StatsParser
    print("✅ Parser working!")
    
    from bot.core.database_adapter import create_adapter
    print("✅ Database adapter working!")
    
    print("\n🎉 All imports successful!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYEOF
```yaml

---

## Step 6: Stop Old Bot (Optional)

**If you want to test with the same Discord token:**

```bash
# Find old bot process
ps aux | grep ultimate_bot.py

# Stop it
# If using screen:
screen -r etlegacy-bot
# Press Ctrl+C
# Press Ctrl+A then D

# If using systemd:
sudo systemctl stop etlegacy-bot

# If just running in terminal:
# Find PID and kill it
kill <PID>
```yaml

**Or use a different Discord bot token to run both simultaneously!**

---

## Step 7: Start New Bot (Test Mode)

```bash
# Make sure you're in slomix-refactored directory
cd ~/slomix-refactored

# Activate virtual environment
source venv/bin/activate

# Start bot in foreground (for testing)
python3 bot/ultimate_bot.py
```text

**You should see:**

```text

✅ Configuration loaded
✅ PostgreSQL adapter created: localhost:5432/etlegacy_stats
✅ Database adapter connected successfully
✅ Database schema validated
✅ Admin Cog loaded (11 admin commands)
✅ Link Cog loaded (link, unlink, select, list_players, find_player)
✅ Stats Cog loaded (ping, check_achievements, compare, season_info, help_command)
✅ Leaderboard Cog loaded (stats, leaderboard)
✅ Session Cog loaded (session, sessions)
✅ Last Round Cog loaded (last_session with multiple view modes)
✅ Sync Cog loaded
✅ Session Management Cog loaded
✅ Team Management Cog loaded
✅ Team System Cog loaded
✅ Bot ready! Logged in as YourBotName

```yaml

**Press Ctrl+C to stop when done testing**

---

## Step 8: Test Commands in Discord

```text

!ping

# Should respond with latency

!stats yourname

# Should show your stats

!last_session

# Should show latest session

!leaderboard kills

# Should show rankings

```yaml

**Everything should work exactly as before!**

---

## Step 9: Run in Background (Production)

### Option A: Using Screen (Simple)

```bash
# Start screen session with new name
screen -S etlegacy-bot-refactored

# Navigate to directory
cd ~/slomix-refactored

# Activate venv
source venv/bin/activate

# Start bot
python3 bot/ultimate_bot.py

# Detach: Press Ctrl+A then D
# Reattach later: screen -r etlegacy-bot-refactored
```text

### Option B: Using Systemd (Recommended)

**Create service file:**

```bash
sudo nano /etc/systemd/system/etlegacy-bot-refactored.service
```text

**Add:**

```ini
[Unit]
Description=ET:Legacy Discord Stats Bot (Refactored)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/slomix-refactored
Environment="PATH=/home/your-username/slomix-refactored/venv/bin:/usr/bin"
ExecStart=/home/your-username/slomix-refactored/venv/bin/python3 /home/your-username/slomix-refactored/bot/ultimate_bot.py

Restart=always
RestartSec=10

StandardOutput=append:/var/log/etlegacy-bot-refactored.log
StandardError=append:/var/log/etlegacy-bot-refactored-error.log

[Install]
WantedBy=multi-user.target
```text

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable etlegacy-bot-refactored
sudo systemctl start etlegacy-bot-refactored
sudo systemctl status etlegacy-bot-refactored
```text

**View logs:**

```bash
sudo tail -f /var/log/etlegacy-bot-refactored.log
```yaml

---

## 📊 Side-by-Side Comparison

### Your Directories

```python

~/slomix/                          # OLD bot (still working)
├── bot/
│   └── ultimate_bot.py           # 4,708 lines
└── .env

~/slomix-refactored/              # NEW bot (refactored)
├── bot/
│   ├── stats/                    # ⭐ NEW module
│   │   └── calculator.py
│   └── ultimate_bot.py           # 2,687 lines (43% smaller!)
└── .env

```yaml

### Running Both Simultaneously

**Old Bot:**

- Process: `screen -r etlegacy-bot` OR `systemctl status etlegacy-bot`
- Logs: `/var/log/etlegacy-bot.log`
- Directory: `~/slomix/`

**New Bot (Refactored):**

- Process: `screen -r etlegacy-bot-refactored` OR `systemctl status etlegacy-bot-refactored`
- Logs: `/var/log/etlegacy-bot-refactored.log`
- Directory: `~/slomix-refactored/`

**⚠️ Note:** You need **different Discord bot tokens** to run both at the same time!

---

## 🔄 Migration Path (When Ready)

### Once you confirm refactored bot works perfectly

**Option 1: Replace Old Bot**

```bash
# Stop old bot
sudo systemctl stop etlegacy-bot
# or: screen -r etlegacy-bot, then Ctrl+C

# Rename directories
mv ~/slomix ~/slomix-backup
mv ~/slomix-refactored ~/slomix

# Update systemd service to point to ~/slomix
sudo nano /etc/systemd/system/etlegacy-bot.service
# Change WorkingDirectory to /home/your-username/slomix

# Start bot
sudo systemctl daemon-reload
sudo systemctl start etlegacy-bot
```text

**Option 2: Keep New Directory**

```bash
# Just disable old bot
sudo systemctl disable etlegacy-bot
sudo systemctl stop etlegacy-bot

# Run refactored bot as main bot
sudo systemctl enable etlegacy-bot-refactored
sudo systemctl start etlegacy-bot-refactored
```python

---

## ✅ Verification Checklist

Test the refactored bot:

- [ ] Bot starts without errors
- [ ] All 12 cogs load successfully
- [ ] `!ping` responds
- [ ] `!stats <player>` shows correct data
- [ ] `!last_session` shows latest session
- [ ] `!leaderboard` shows rankings
- [ ] Stats files auto-import (if enabled)
- [ ] No database errors
- [ ] Performance seems faster (check import times in logs)

---

## 📈 Performance Comparison

Watch the logs to compare performance:

**Old bot:**

```bash
tail -f /var/log/etlegacy-bot.log | grep "Processed"
# ✅ Processed in 0.45s (12 players, 24 weapons) (WITH WARNINGS)
```text

**New bot (refactored):**

```bash
tail -f /var/log/etlegacy-bot-refactored.log | grep "Processed"
# ✅ Processed in 0.28s (12 players, 24 weapons)
```yaml

**Expected improvement: ~38% faster imports!**

---

## 🗑️ Cleanup (After Migration)

Once you're confident the refactored bot works:

```bash
# Remove old bot directory (backup first!)
tar -czf ~/slomix-backup-$(date +%Y%m%d).tar.gz ~/slomix
rm -rf ~/slomix

# Remove old systemd service
sudo systemctl disable etlegacy-bot
sudo rm /etc/systemd/system/etlegacy-bot.service
sudo systemctl daemon-reload
```yaml

---

## 🆘 Troubleshooting

### Issue: "No module named 'bot.stats'"

```bash
# Check you're in the right directory
pwd
# Should be: /home/your-username/slomix-refactored

# Check virtual environment is activated
which python3
# Should be: /home/your-username/slomix-refactored/venv/bin/python3

# Reinstall requirements
pip install --upgrade -r requirements.txt
```text

### Issue: Database Connection Failed

```bash
# Check .env file
cat .env | grep POSTGRES

# Test PostgreSQL connection
psql -h localhost -U your_db_user -d etlegacy_stats -c "SELECT 1;"
```text

### Issue: Both Bots Conflict

```bash
# Make sure they use different Discord tokens
# OR only run one at a time

# Check which is running:
ps aux | grep ultimate_bot
```yaml

---

## 🎯 Quick Commands Reference

```bash
# Clone fresh
git clone https://github.com/iamez/slomix.git slomix-refactored
cd slomix-refactored
git checkout claude/architecture-review-framework-01UyGTWjM75BCq5crDQ3qiu5

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Test
python3 bot/ultimate_bot.py

# Run in background (screen)
screen -S etlegacy-bot-refactored
python3 bot/ultimate_bot.py
# Ctrl+A, D to detach

# View logs
tail -f /var/log/etlegacy-bot-refactored.log
```

---

**Ready to test!** 🚀

The refactored bot will run independently in `~/slomix-refactored/` without touching your existing `~/slomix/` installation.
