# 🚨 EMERGENCY ROLLBACK GUIDE
**Created**: October 5, 2025, 02:00 UTC  
**Purpose**: Quick recovery if things break  
**Read this WHEN THINGS GO WRONG!**

---

## 🎯 LAST KNOWN GOOD STATE

**Date**: October 5, 2025, 02:00 UTC  
**Status**: ✅ FULLY WORKING

### **What's Working**:
- ✅ Bot connects to Discord
- ✅ Database: 12,414 records, 53 columns (UNIFIED schema)
- ✅ All 13 leaderboard types working
- ✅ Pagination working (!lb 2, !lb dpm 3)
- ✅ Dev badge working (👑 for GUID E587CA5F)
- ✅ Alias system working (player_aliases table)
- ✅ Linking system working (!link, !stats @user)
- ✅ Grenade AOE calculation working

### **Bot File**:
- Path: `bot/ultimate_bot.py`
- Lines: 4,184 lines
- Features: 13 leaderboard types, pagination, linking, @mention support

### **Database File**:
- Path: `etlegacy_production.db`
- Size: ~15 MB
- Tables: 7 (sessions, player_comprehensive_stats, weapon_comprehensive_stats, processed_files, player_links, player_aliases, sqlite_sequence)
- Records: 12,414 player records across 1,456 sessions

---

## 🔴 EMERGENCY ROLLBACK OPTIONS

### **Option 1: Restart Bot** (90% of issues)

```powershell
# Stop current bot
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

# Wait 3 seconds
Start-Sleep -Seconds 3

# Restart bot
python bot/ultimate_bot.py
```

**When to use**: Bot crashed, unresponsive, or acting weird

---

### **Option 2: Restore Bot File from Git** (if bot code is broken)

```powershell
# See what changed
git diff bot/ultimate_bot.py

# If changes look bad, restore from last commit
git checkout HEAD -- bot/ultimate_bot.py

# Then restart bot
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
python bot/ultimate_bot.py
```

**When to use**: Bot won't start, syntax errors, import errors

---

### **Option 3: Manual Bot File Backup** (if no git)

**Create backup NOW** (before making changes):
```powershell
# Backup bot file
Copy-Item bot/ultimate_bot.py bot/ultimate_bot.py.backup

# Later, if needed, restore
Copy-Item bot/ultimate_bot.py.backup bot/ultimate_bot.py -Force
```

**When to use**: About to make risky changes

---

### **Option 4: Restore Database** (NUCLEAR OPTION)

```powershell
# First, check if database is corrupted
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('PRAGMA integrity_check'); print(cursor.fetchone()[0])"

# If corrupted, restore from backup
# (Assuming you have a backup - create one NOW!)
Copy-Item etlegacy_production.db etlegacy_production.db.backup

# To restore later
Copy-Item etlegacy_production.db.backup etlegacy_production.db -Force
```

**When to use**: Database won't open, queries fail with weird errors

---

## 🛠️ QUICK DIAGNOSTICS

### **Test #1: Database Schema Check**
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); c = conn.cursor(); c.execute('PRAGMA table_info(player_comprehensive_stats)'); print(f'Columns: {len(c.fetchall())} (should be 53)');"
```

**Expected**: `Columns: 53 (should be 53)`

---

### **Test #2: Bot Import Check**
```powershell
python -c "import sys; sys.path.append('bot'); from ultimate_bot import UltimateBot; print('✅ Bot imports successfully')"
```

**Expected**: `✅ Bot imports successfully`

---

### **Test #3: Database Records Check**
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); print(f'Records: {c.fetchone()[0]} (should be 12414)');"
```

**Expected**: `Records: 12414 (should be 12414)`

---

### **Test #4: Bot Syntax Check**
```powershell
python -m py_compile bot/ultimate_bot.py
```

**Expected**: No output = success  
**If error**: Syntax error in bot file - restore from backup

---

## 📋 KNOWN ISSUES & FIXES

### **Issue #1: Bot Won't Start**

**Symptoms**:
- Bot exits immediately
- Error: "Database not found"
- Error: "Invalid schema"

**Fix**:
```powershell
# Check database exists
Test-Path etlegacy_production.db

# If missing, restore from backup
Copy-Item etlegacy_production.db.backup etlegacy_production.db

# Restart bot
python bot/ultimate_bot.py
```

---

### **Issue #2: Commands Not Working**

**Symptoms**:
- Bot responds to !ping but not !lb or !stats
- Error: "Command not found"

**Fix**:
```powershell
# Bot may have crashed mid-startup
# Hard restart
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
python bot/ultimate_bot.py

# Wait for "Bot ready with X commands!" message
```

---

### **Issue #3: Database Locked**

**Symptoms**:
- Error: "database is locked"
- Commands timeout

**Fix**:
```powershell
# Stop all python processes
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

# Wait for locks to release
Start-Sleep -Seconds 5

# Restart bot
python bot/ultimate_bot.py
```

---

### **Issue #4: Stats Showing Zeros**

**Symptoms**:
- !stats shows 0 kills, 0 deaths
- Leaderboards empty

**Fix**:
```powershell
# Check database has data
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); print(c.fetchone()[0])"

# If 0, database is empty - restore from backup
Copy-Item etlegacy_production.db.backup etlegacy_production.db -Force
```

---

### **Issue #5: Syntax Error in Bot**

**Symptoms**:
- Error: "SyntaxError: invalid syntax"
- Bot won't start

**Fix**:
```powershell
# Check for syntax errors
python -m py_compile bot/ultimate_bot.py

# If error shown, restore from backup
Copy-Item bot/ultimate_bot.py.backup bot/ultimate_bot.py -Force

# Or restore from git
git checkout HEAD -- bot/ultimate_bot.py

# Restart
python bot/ultimate_bot.py
```

---

## 💾 BACKUP CHECKLIST

**Before making ANY changes, create backups**:

```powershell
# Backup bot file
Copy-Item bot/ultimate_bot.py bot/ultimate_bot.py.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')

# Backup database
Copy-Item etlegacy_production.db etlegacy_production.db.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')

# List backups
Get-ChildItem *.backup*
```

---

## 🔄 FULL SYSTEM RESET (LAST RESORT)

**ONLY IF EVERYTHING IS BROKEN**:

1. **Stop bot**:
   ```powershell
   Stop-Process -Name python -Force -ErrorAction SilentlyContinue
   ```

2. **Restore bot file**:
   ```powershell
   Copy-Item bot/ultimate_bot.py.backup bot/ultimate_bot.py -Force
   ```

3. **Restore database**:
   ```powershell
   Copy-Item etlegacy_production.db.backup etlegacy_production.db -Force
   ```

4. **Verify restoration**:
   ```powershell
   # Check bot syntax
   python -m py_compile bot/ultimate_bot.py
   
   # Check database
   python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); print(c.fetchone()[0])"
   ```

5. **Restart bot**:
   ```powershell
   python bot/ultimate_bot.py
   ```

---

## 📞 HEALTH CHECK SCRIPT

Create this file to quickly check system health:

```python
# health_check.py
import sqlite3
import os
import sys

print("🏥 System Health Check\n")

# Check bot file
bot_path = "bot/ultimate_bot.py"
if os.path.exists(bot_path):
    size = os.path.getsize(bot_path)
    print(f"✅ Bot file exists: {size:,} bytes")
    
    # Check syntax
    try:
        with open(bot_path) as f:
            compile(f.read(), bot_path, 'exec')
        print("✅ Bot syntax valid")
    except SyntaxError as e:
        print(f"❌ Bot syntax error: {e}")
else:
    print("❌ Bot file missing!")

# Check database
db_path = "etlegacy_production.db"
if os.path.exists(db_path):
    size = os.path.getsize(db_path)
    print(f"✅ Database exists: {size:,} bytes")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check schema
        cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
        cols = len(cursor.fetchall())
        print(f"✅ Schema: {cols} columns (expected 53)")
        
        # Check records
        cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
        count = cursor.fetchone()[0]
        print(f"✅ Records: {count:,} player records")
        
        # Check integrity
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        if result == "ok":
            print("✅ Database integrity: OK")
        else:
            print(f"⚠️ Database integrity: {result}")
            
        conn.close()
    except Exception as e:
        print(f"❌ Database error: {e}")
else:
    print("❌ Database missing!")

print("\n🎯 System Status:")
if os.path.exists(bot_path) and os.path.exists(db_path):
    print("✅ READY TO RUN")
else:
    print("❌ NEEDS ATTENTION")
```

**Run it**:
```powershell
python health_check.py
```

---

## 🎯 GOLDEN RULE

**Before ANY changes**:
1. ✅ Create backups
2. ✅ Test in isolation first
3. ✅ Make small changes
4. ✅ Test after each change
5. ✅ Commit to git (if using)

**If tired**:
- 🛑 STOP coding
- 💾 Save backups
- 📋 Document what you did
- 🛌 Resume when fresh

---

**Last Updated**: October 5, 2025, 02:00 UTC  
**Status**: System healthy and documented ✅
