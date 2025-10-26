# 🚀 Database Rebuild Quick Start Guide

**Last Updated:** October 6, 2025

## 🎯 When to Use This Guide

Use this guide when you need to:
- Rebuild database from scratch
- Import stats files from `local_stats/` directory
- Fix corrupted statistics
- Start with a clean database

## ⚡ The 5-Step Process

### Step 1: Validate Current State (Optional)

Check if your current database has issues:

```powershell
python validate_schema.py
```

If you see ❌ errors, you'll need to rebuild or fix schema.

### Step 2: Clear Database

```powershell
python tools/full_database_rebuild.py
```

**What this does:** Deletes all data from tables (sessions, player_comprehensive_stats, weapon_comprehensive_stats)

### Step 3: Create Fresh Schema

```powershell
python tools/create_fresh_database.py
```

**What this does:** Creates `etlegacy_production.db` with complete schema (all 68 columns across all tables)

### Step 4: Validate Schema ⚠️ CRITICAL

```powershell
python validate_schema.py
```

**Expected output:**
```
✅ DATABASE IS READY FOR IMPORT!
   All required columns present
   No constraint issues detected
```

**If you see ❌ errors:** DO NOT PROCEED! See [DATABASE_REBUILD_TROUBLESHOOTING.md](DATABASE_REBUILD_TROUBLESHOOTING.md)

### Step 5: Import Stats Files

```powershell
$env:PYTHONIOENCODING='utf-8'; python tools/simple_bulk_import.py
```

**What this does:** 
- Imports all `.txt` files from `local_stats/` directory
- Creates session records
- Creates player stat records
- Creates weapon stat records

**Expected output:**
- Progress messages for each file
- Some parser errors are NORMAL (malformed files)
- Database constraint errors = SCHEMA PROBLEM (go back to Step 4)

## ✅ Verify Success

### Check Import Results

```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); player_count = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(*) FROM sessions'); session_count = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats'); unique_players = cursor.fetchone()[0]; print(f'\n📊 Import Results:\nPlayer records: {player_count}\nSessions: {session_count}\nUnique players: {unique_players}\n')"
```

**Expected results:**
- Player records: ~21,000 (for 3,253 files)
- Sessions: ~3,153
- Unique players: ~36

### Check for Duplicates

```powershell
python check_duplicates.py
```

**Expected output:**
```
✅ No duplicates - all records are unique!
```

## 🎮 Start the Bot

After successful rebuild:

```powershell
cd bot
python ultimate_bot.py
```

Test with Discord commands:
- `!stats` - Check player stats
- `!last_session` - View recent session
- `!top kills` - Top players by kills

## 🚨 Common Issues

### Issue: "table has no column named X"

**Solution:** Schema is incomplete. Run `validate_schema.py` and follow fix instructions.

### Issue: "NOT NULL constraint failed"

**Solution:** Table constraints are wrong. See [DATABASE_REBUILD_TROUBLESHOOTING.md](DATABASE_REBUILD_TROUBLESHOOTING.md) section on constraint issues.

### Issue: Import completes but 0 records

**Solution:** Parser errors or file format issues. Check that `.txt` files are in `local_stats/` directory.

### Issue: Stats look inflated/wrong

**Solution:** Run `check_duplicates.py` to verify no duplication occurred.

## 📚 More Help

For detailed troubleshooting, schema reference, and advanced fixes:
- **[DATABASE_REBUILD_TROUBLESHOOTING.md](DATABASE_REBUILD_TROUBLESHOOTING.md)** - Complete troubleshooting guide
- **[AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md)** - Full database documentation

## 💡 Pro Tips

1. **Always validate before import** - Saves time by catching issues early
2. **Failed imports don't create duplicates** - SQLite transactions roll back on error
3. **Some parser errors are normal** - Malformed files, Round 2 processing
4. **Keep this guide updated** - Document any new issues you encounter

## 📊 Expected Performance

- **Import time:** ~2-5 minutes for 3,253 files
- **Database size:** ~50-100 MB
- **Memory usage:** Low (SQLite is efficient)

---

**Last rebuild:** October 6, 2025  
**Result:** ✅ 21,070 unique records from 3,253 files  
**Issues encountered:** 10 missing columns (now fixed)  
**Time taken:** ~6 hours (due to schema discovery process)  
**Future rebuilds:** Should take ~5 minutes with fixed scripts
