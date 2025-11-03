# 🚨 Database Disaster Recovery Guide

**Last Updated:** November 3, 2025  
**Purpose:** Recover from database corruption, deletion, or catastrophic data loss WITHOUT needing AI assistance

---

## 📋 Table of Contents

1. [Quick Recovery (5 Minutes)](#quick-recovery-5-minutes)
2. [Common Scenarios](#common-scenarios)
3. [Step-by-Step Instructions](#step-by-step-instructions)
4. [Validation](#validation)
5. [Troubleshooting](#troubleshooting)

---

## 🏃 Quick Recovery (5 Minutes)

**If your database is gone or corrupted, do this:**

```powershell
# 1. Navigate to project directory
cd C:\Users\seareal\Documents\stats

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Run database manager
python database_manager.py

# 4. Choose option 3 (Rebuild from scratch)
# 5. Type: YES DELETE EVERYTHING
# 6. Wait 5-10 minutes
# 7. Done! ✅
```

That's it. No AI needed. No token waste.

---

## 🎯 Common Scenarios

### Scenario 1: Database Deleted
**Symptom:** `etlegacy_production.db` is missing  
**Solution:** Rebuild from scratch (Option 3)

### Scenario 2: Corrupted Data
**Symptom:** Wrong stats, duplicate entries, or SQL errors  
**Solution:** Rebuild from scratch (Option 3)

### Scenario 3: Missing Recent Data
**Symptom:** Recent sessions not in database  
**Solution:** Incremental import (Option 2)

### Scenario 4: Bad Data for Specific Dates
**Symptom:** Oct 28-30 has wrong stats  
**Solution:** Fix date range (Option 4)

### Scenario 5: Schema Changes
**Symptom:** Bot crashes with "no such column" errors  
**Solution:** Create fresh database (Option 1) + Import (Option 2)

---

## 📖 Step-by-Step Instructions

### Option 1: Create Fresh Database
**When to use:** Need clean schema with no data

```powershell
python database_manager.py
# Choose: 1
# Result: New empty database with correct schema
```

**What it does:**
- ✅ Creates backup of existing DB (if present)
- ✅ Creates all 7 tables with correct schema
- ✅ Applies 51-field player stats structure
- ✅ Adds UNIQUE constraints (no duplicates)
- ✅ Creates indexes for performance
- ⏱️ Time: ~2 seconds

---

### Option 2: Import All Files (Incremental)
**When to use:** Add new data without touching existing data

```powershell
python database_manager.py
# Choose: 2
# Enter year: 2025 (or leave blank for 2025)
# Result: Only NEW files imported
```

**What it does:**
- ✅ Skips already-processed files (safe)
- ✅ Imports only new stats files
- ✅ Shows progress with ETA
- ✅ NO duplicate data (protected by UNIQUE constraints)
- ⏱️ Time: ~1-2 files per second (~10 min for 1000 files)

**Safety:** This is the SAFEST option. Use this for regular updates.

---

### Option 3: Rebuild from Scratch (NUCLEAR OPTION)
**When to use:** Database is corrupted, has wrong data, or you need to start over

```powershell
python database_manager.py
# Choose: 3
# Confirm: YES DELETE EVERYTHING
# Enter year: 2025
# Result: Fresh database with all data re-imported
```

**What it does:**
- ⚠️ **DELETES EVERYTHING**
- ✅ Creates backup first (safety)
- ✅ Creates fresh schema
- ✅ Re-imports ALL files from scratch
- ⏱️ Time: ~10-15 minutes for full year

**Warning:** This is the nuclear option. Only use when necessary.

---

### Option 4: Fix Specific Date Range
**When to use:** Known bad data for specific dates (e.g., Oct 28-30)

```powershell
python database_manager.py
# Choose: 4
# Start date: 2025-10-28
# End date: 2025-10-30
# Result: Only that date range is deleted and re-imported
```

**What it does:**
- ✅ Surgical deletion of date range
- ✅ Re-imports only those dates
- ✅ Rest of database untouched
- ⏱️ Time: ~1 minute for 2-3 days

**Use case:** When you know specific dates have wrong data.

---

### Option 5: Validate Database
**When to use:** Check if database is healthy

```powershell
python database_manager.py
# Choose: 5
# Result: Statistics and integrity report
```

**What it shows:**
- Total sessions, players, weapons
- Date range
- Orphan sessions (data integrity issues)
- Processing history

---

### Option 6: Quick Test
**When to use:** Test if everything works before full import

```powershell
python database_manager.py
# Choose: 6
# Result: Import 10 files to verify functionality
```

**Use case:** After code changes, verify imports still work.

---

## ✅ Validation

After any recovery operation, validate the database:

```powershell
python database_manager.py
# Choose: 5 (Validate)
```

**Good output looks like:**
```
✅ Database validation passed!
   Sessions:          1,234
   Player stats:      45,678
   Weapon stats:      234,567
   Orphan sessions:   0  ← Should be 0!
```

**Bad output:**
```
⚠️  Database has integrity issues!
   Orphan sessions:   15  ← This means data corruption
```

If you see orphan sessions, run **Option 3 (Rebuild from scratch)**.

---

## 🔧 Troubleshooting

### Problem: "No such file or directory: local_stats"
**Solution:** Make sure you're in the project root directory

```powershell
cd C:\Users\seareal\Documents\stats
python database_manager.py
```

---

### Problem: "Module not found: discord"
**Solution:** Activate virtual environment first

```powershell
.\.venv\Scripts\Activate.ps1
python database_manager.py
```

---

### Problem: "Database is locked"
**Solution:** Close any other Python scripts or bot instances

```powershell
# Find process using database
Get-Process python | Stop-Process -Force

# Then retry
python database_manager.py
```

---

### Problem: Import is slow (< 0.5 files/sec)
**Solution:** This is normal for first import (lots of weapons data)

- Expected: 1-2 files per second
- If slower: Check disk space and antivirus

---

### Problem: "Parse error" on specific files
**Solution:** Check if stats file is corrupted

```powershell
# Look at the file manually
notepad local_stats\2025-10-28-some-file.txt

# If it's corrupted (missing data), delete it
Remove-Item local_stats\2025-10-28-some-file.txt

# Re-run import
python database_manager.py
```

---

## 🎯 Best Practices

### Daily Operations
- Use **Option 2** (Incremental import) for regular updates
- Run **Option 5** (Validate) once a week

### After Code Changes
- Run **Option 6** (Quick test) to verify
- If test passes, run **Option 2** (Full import)

### When Things Break
1. Try **Option 4** (Date range fix) if you know the bad dates
2. If that doesn't work, try **Option 3** (Rebuild from scratch)
3. Always run **Option 5** (Validate) after recovery

### Backups
- Database manager creates automatic backups before destructive operations
- Backups are stored in `bot/` directory with timestamp
- Example: `etlegacy_production.db.backup_20251103_143022`

---

## 📊 Performance Expectations

| Operation | Time | Files Processed |
|-----------|------|-----------------|
| Create fresh DB | 2 sec | 0 |
| Import 10 files | 10 sec | 10 |
| Import 100 files | 1-2 min | 100 |
| Import 1000 files | 10-15 min | 1000 |
| Full year (2025) | 10-15 min | ~1000-2000 |
| Date range fix | 1-2 min | 50-100 |

**Processing rate:** 1-2 files per second on average

---

## 🚨 Emergency Contact

If this guide doesn't solve your problem:

1. Check `database_manager.log` for detailed error messages
2. Run with validation to see what's wrong
3. Look for error patterns in recent log entries

**Common log locations:**
- `C:\Users\seareal\Documents\stats\database_manager.log`
- Check last 50 lines: `Get-Content database_manager.log -Tail 50`

---

## 📝 Change Log

### November 3, 2025 - Initial Version
- Consolidated 20+ scattered tools into ONE tool
- All fixes applied (51 fields, transactions, UNIQUE constraints)
- Tested and verified on production data
- No AI assistance needed for recovery

---

**Remember:** This is THE ONLY database tool. Don't create new import scripts. Everything you need is in `database_manager.py`.

**Questions?** Read this guide first. 99% of problems are covered here.
