# 🚀 Quick-Start Fix Guide

**PRIORITY: Do these 5 things RIGHT NOW before touching anything else**

---

## Step 1: Fix Merge Conflicts (5 minutes)

### Fix .gitignore

```powershell
# Open in editor and remove conflict markers
code .gitignore
```text

**Choose this version and save:**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment
.env
*.env
.env.local
.env.template

# Database
*.db
*.db-journal
*.sqlite
*.sqlite3
backup*.db
*_backup_*.db

# Stats Files
local_stats/*.txt
!local_stats/.gitkeep

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# Temporary
temp/
tmp/
*.tmp

# OS
.DS_Store
Thumbs.db

# Test artifacts
.pytest_cache/
.coverage
htmlcov/

# IMPORTANT: Never commit these directories
publish_temp/
publish_clean/
github/
```text

### Fix .env.example

```powershell
code .env.example
```text

**Choose this version and save:**

```bash
# ET:Legacy Discord Bot - Configuration Template
# Copy this file to .env and fill in your values

# ==================
# REQUIRED SETTINGS
# ==================

# Discord Bot Token (Get from: https://discord.com/developers/applications)
DISCORD_BOT_TOKEN=your_bot_token_here

# Your Discord Server ID
GUILD_ID=your_server_id_here

# Channel where stats will be posted
STATS_CHANNEL_ID=your_channel_id_here

# ==================
# OPTIONAL: SSH Monitoring
# ==================
SSH_ENABLED=false
SSH_HOST=your.server.com
SSH_PORT=22
SSH_USER=username
SSH_KEY_PATH=~/.ssh/id_rsa
REMOTE_STATS_DIR=/path/to/gamestats
SSH_CHECK_INTERVAL=30

# ==================
# OPTIONAL: Voice Channel Automation
# ==================
AUTOMATION_ENABLED=false
GAMING_VOICE_CHANNELS=channel_id1,channel_id2
ACTIVE_PLAYER_THRESHOLD=6
INACTIVE_DURATION_SECONDS=180
```text

### Fix README.md

```powershell
code README.md
```text

**Use the github/README.md content** (it's cleaner):

```powershell
Copy-Item github\README.md README.md -Force
```yaml

---

## Step 2: Set Up Virtual Environment (2 minutes)

```powershell
# Navigate to project
cd "c:\Users\seareal\Documents\stats"

# Create virtual environment (if doesn't exist)
python -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import discord; import aiosqlite; print('✅ Dependencies installed')"
```yaml

---

## Step 3: Clean Up Root Directory (3 minutes)

```powershell
# Create archive directory for diagnostics
New-Item -ItemType Directory -Force -Path "archive\diagnostics"

# Move all check_*.py files to archive
Get-ChildItem -Filter "check_*.py" | Move-Item -Destination "archive\diagnostics\"

# Move analysis scripts
Get-ChildItem -Filter "analyze_*.py" | Move-Item -Destination "archive\diagnostics\"

# Move comparison scripts
Get-ChildItem -Filter "compare_*.py" | Move-Item -Destination "archive\diagnostics\"

# Move debug scripts
Get-ChildItem -Filter "debug_*.py" | Move-Item -Destination "archive\diagnostics\"

# Move verification scripts  
Get-ChildItem -Filter "verify_*.py" | Move-Item -Destination "archive\diagnostics\"

# Move test spam
Get-ChildItem -Filter "test_*.py" | Where-Object { $_.Name -ne "test_suite.py" } | Move-Item -Destination "archive\diagnostics\"

# Move add_*.py migration scripts
Get-ChildItem -Filter "add_*.py" | Move-Item -Destination "archive\diagnostics\"

Write-Host "✅ Root directory cleaned!"
```sql

---

## Step 4: Delete Duplicate Directories (1 minute)

**⚠️ DANGER ZONE - Make sure you've committed your work first!**

```powershell
# Backup first (just in case)
git status
git add -A
git commit -m "Backup before cleanup"

# Delete duplicates
Remove-Item -Recurse -Force "publish_temp"
Remove-Item -Recurse -Force "publish_clean"

# DON'T delete github/ yet - we'll handle it properly in Step 5
```bash

---

## Step 5: Fix Git Workflow (5 minutes)

### Current Problem

You're manually copying files to `github/` folder, which is wrong. Git should manage this.

### Proper Solution

```powershell
# 1. Your main directory is already a git repo
cd "c:\Users\seareal\Documents\stats"

# 2. Check remote
git remote -v
# Should show: origin  git@github.com:iamez/slomix.git

# 3. Add/update files in main directory
git add bot/
git add tools/
git add database/
git add requirements.txt
git add README.md
git add .env.example
git add .gitignore

# 4. Commit changes
git commit -m "Code cleanup and merge conflict resolution"

# 5. Push directly to GitHub
git push origin main

# 6. NOW delete the github/ folder (it's redundant)
Remove-Item -Recurse -Force "github"
```text

### New Workflow Going Forward

```powershell
# Edit files in main directory
code bot\ultimate_bot.py

# Stage changes
git add bot\ultimate_bot.py

# Commit
git commit -m "Fix: Add error handling to stats command"

# Push to GitHub
git push origin main

# DONE! No manual copying needed.
```yaml

---

## Step 6: Test Everything (5 minutes)

```powershell
# Activate venv
.venv\Scripts\Activate.ps1

# Test database access
python -c "import sqlite3; conn = sqlite3.connect('bot/etlegacy_production.db'); print('✅ Database accessible')"

# Test parser
python -c "from bot.community_stats_parser import C0RNP0RN3StatsParser; parser = C0RNP0RN3StatsParser(); print('✅ Parser loads')"

# Test bot imports (don't run, just import)
python -c "import sys; sys.path.insert(0, 'bot'); from ultimate_bot import UltimateETLegacyBot; print('✅ Bot imports successfully')"
```bash

---

## ✅ DONE

Your workspace is now:

- ✅ No merge conflicts
- ✅ Virtual environment set up
- ✅ Root directory clean (72 files moved to archive)
- ✅ No duplicate directories
- ✅ Proper git workflow established

---

## 🎯 What's Next?

Now you can start on the **real work** - refactoring that 9,587-line monster bot file.

See `REFACTORING_PLAN.md` for the step-by-step guide to split it up.

---

## 🆘 If Something Goes Wrong

```powershell
# Restore from git
git reset --hard HEAD
git clean -fd

# Or restore from backup commit
git log --oneline
git reset --hard <commit-hash>
```

**Pro tip:** Commit often, push often. Git is your safety net! 🛡️
