# 🔧 Database Rebuild Troubleshooting Guide

## 📋 Overview

This guide documents the complete database rebuild process and how to fix common schema issues that occur when rebuilding from scratch.

**Last Updated:** October 6, 2025  
**Database:** etlegacy_production.db (SQLite3)  
**Import Tool:** `tools/simple_bulk_import.py` ✅ CORRECT

---

## 🚨 Common Problem: Schema Mismatch

### The Issue

When rebuilding the database, you may encounter errors like:
```
❌ table player_comprehensive_stats has no column named time_dead_minutes
❌ table weapon_comprehensive_stats has no column named session_date
❌ NOT NULL constraint failed: weapon_comprehensive_stats.weapon_id
```

### Root Cause

The `tools/create_fresh_database.py` script was **out of sync** with `tools/simple_bulk_import.py` and was missing **10+ required columns** across multiple tables.

**This has been FIXED** as of October 6, 2025.

---

## ✅ Correct Rebuild Process

### Step 1: Pre-Flight Check

**ALWAYS validate schema BEFORE attempting import:**

```powershell
python validate_schema.py
```

Expected output if everything is correct:
```
✅ DATABASE IS READY FOR IMPORT!
   All required columns present
   No constraint issues detected
```

If you see issues, **fix them before importing** (see Fixing Schema Issues below).

### Step 2: Clear Database (if needed)

```powershell
python tools/full_database_rebuild.py
```

**⚠️ WARNING:** This only CLEARS the database. It does NOT import files.

### Step 3: Create Fresh Database

```powershell
python tools/create_fresh_database.py
```

This creates `etlegacy_production.db` with the complete schema including:
- ✅ All 51 required player stat columns
- ✅ All 12 required weapon stat columns  
- ✅ All 5 required session columns
- ✅ Proper constraints (no NOT NULL on weapon_id/weapon_name)

### Step 4: Validate Schema (CRITICAL!)

```powershell
python validate_schema.py
```

**DO NOT PROCEED** if this shows any missing columns or constraint issues!

### Step 5: Run Import

```powershell
$env:PYTHONIOENCODING='utf-8'; python tools/simple_bulk_import.py
```

Expected result:
- Processes all .txt files in `local_stats/` directory
- Some parser errors are NORMAL (malformed files, Round 2 processing)
- Database constraint errors = schema problems (go back to Step 4)

### Step 6: Verify Results

```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); player_count = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(*) FROM sessions'); session_count = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats'); unique_players = cursor.fetchone()[0]; print(f'\n📊 Import Results:'); print(f'Player records: {player_count}'); print(f'Sessions: {session_count}'); print(f'Unique players: {unique_players}')"
```

### Step 7: Check for Duplicates

```powershell
python check_duplicates.py
```

Expected: 0 duplicates (all records should be unique)

---

## 🛠️ Fixing Schema Issues

If `validate_schema.py` reports missing columns, here's how to fix them:

### Missing Columns in `sessions` Table

```sql
-- Example: Missing actual_time
ALTER TABLE sessions ADD COLUMN actual_time TEXT;
```

### Missing Columns in `player_comprehensive_stats` Table

```sql
-- Example fixes (add as needed)
ALTER TABLE player_comprehensive_stats ADD COLUMN time_dead_minutes REAL DEFAULT 0.0;
ALTER TABLE player_comprehensive_stats ADD COLUMN efficiency REAL DEFAULT 0.0;
ALTER TABLE player_comprehensive_stats ADD COLUMN objectives_completed INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN objectives_destroyed INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN revives_given INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN constructions INTEGER DEFAULT 0;
```

### Missing Columns in `weapon_comprehensive_stats` Table

```sql
-- Example fixes (add as needed)
ALTER TABLE weapon_comprehensive_stats ADD COLUMN session_date TEXT;
ALTER TABLE weapon_comprehensive_stats ADD COLUMN map_name TEXT;
ALTER TABLE weapon_comprehensive_stats ADD COLUMN round_number INTEGER;
ALTER TABLE weapon_comprehensive_stats ADD COLUMN player_name TEXT;
```

### NOT NULL Constraint Issues

If `weapon_id` or `weapon_name` have NOT NULL constraints:

```python
# Use Python to recreate table without constraints
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Create new table without NOT NULL
cursor.execute('''
    CREATE TABLE weapon_comprehensive_stats_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        session_date TEXT,
        map_name TEXT,
        round_number INTEGER,
        player_guid TEXT NOT NULL,
        player_name TEXT,
        weapon_id INTEGER,        -- No NOT NULL
        weapon_name TEXT,         -- No NOT NULL
        kills INTEGER DEFAULT 0,
        deaths INTEGER DEFAULT 0,
        hits INTEGER DEFAULT 0,
        shots INTEGER DEFAULT 0,
        headshots INTEGER DEFAULT 0,
        accuracy REAL DEFAULT 0.0,
        headshot_ratio REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (id)
    )
''')

# Drop old table
cursor.execute('DROP TABLE weapon_comprehensive_stats')

# Rename new table
cursor.execute('ALTER TABLE weapon_comprehensive_stats_new RENAME TO weapon_comprehensive_stats')

conn.commit()
conn.close()

print("✅ Fixed NOT NULL constraints")
```

---

## 📊 Required Schema Reference

### Sessions Table (5 columns)
1. `session_date` (TEXT)
2. `map_name` (TEXT)
3. `round_number` (INTEGER)
4. `time_limit` (TEXT)
5. `actual_time` (TEXT) ⚠️ **Often missing**

### Player Comprehensive Stats (51 columns)

**Basic Stats:**
- session_id, session_date, map_name, round_number
- player_guid, player_name, clean_name, team

**Combat Stats:**
- kills, deaths, damage_given, damage_received
- team_damage_given, team_damage_received
- gibs, self_kills, team_kills, team_gibs, headshot_kills

**Time Stats:**
- time_played_seconds, time_played_minutes
- time_dead_minutes ⚠️ **Often missing**
- time_dead_ratio

**Performance Stats:**
- xp, kd_ratio, dpm
- efficiency ⚠️ **Often missing**
- bullets_fired, accuracy

**Advanced Stats:**
- kill_assists
- objectives_completed ⚠️ **Often missing**
- objectives_destroyed ⚠️ **Often missing**
- objectives_stolen, objectives_returned
- dynamites_planted, dynamites_defused
- times_revived
- revives_given ⚠️ **Often missing**
- constructions ⚠️ **Often missing**
- most_useful_kills, useless_kills, kill_steals
- denied_playtime, tank_meatshield

**Multikill Stats:**
- double_kills, triple_kills, quad_kills
- multi_kills, mega_kills
- killing_spree_best, death_spree_worst

### Weapon Comprehensive Stats (12 columns)

1. `session_id` (INTEGER)
2. `session_date` (TEXT) ⚠️ **Often missing**
3. `map_name` (TEXT) ⚠️ **Often missing**
4. `round_number` (INTEGER) ⚠️ **Often missing**
5. `player_guid` (TEXT)
6. `player_name` (TEXT) ⚠️ **Often missing**
7. `weapon_name` (TEXT) - **NO NOT NULL CONSTRAINT**
8. `kills` (INTEGER)
9. `deaths` (INTEGER)
10. `headshots` (INTEGER)
11. `shots` (INTEGER)
12. `hits` (INTEGER)

---

## 🚫 Wrong Tools (DO NOT USE)

### ❌ `dev/bulk_import_stats.py`
- Uses SPLIT schema (old approach)
- Will fail with unified database

### ❌ `tools/fixed_bulk_import.py`
- Uses different database
- Not for production use

### ❌ `tools/full_database_rebuild.py` (for import)
- Only CLEARS database
- Does NOT import files
- Use `tools/simple_bulk_import.py` instead

---

## 💡 Important Notes

### Failed Imports Don't Create Duplicates

SQLite uses transactions - when an import fails:
- **ALL inserts are rolled back** (0 records inserted)
- No partial imports occur
- Database state is unchanged
- Safe to retry after fixing schema

### Validation is Critical

The `validate_schema.py` script was created specifically to catch ALL schema issues before import:
- Checks all 3 tables
- Reports missing columns clearly
- Detects constraint issues
- **USE IT BEFORE EVERY IMPORT**

### Common Pitfall

❌ **Don't assume** `create_fresh_database.py` creates a complete schema  
✅ **Always validate** with `validate_schema.py` before importing

---

## 📝 Session History (Oct 6, 2025)

This troubleshooting guide was created after a database rebuild session that involved:
- **7 failed import attempts** (missing columns discovered incrementally)
- **10 manual schema fixes** across 3 tables
- **2 constraint removals** (weapon_id, weapon_name)
- **Final success:** 21,070 unique records imported from 3,253 files

**Lessons Learned:**
1. ❌ Database creation script was missing 10+ columns
2. ✅ Fixed `create_fresh_database.py` with all required columns
3. ✅ Enhanced `validate_schema.py` to check ALL tables
4. ✅ Created this troubleshooting guide for future reference

---

## 🔄 Quick Reference Commands

```powershell
# Validate before import (CRITICAL!)
python validate_schema.py

# Clear database
python tools/full_database_rebuild.py

# Create fresh database with complete schema
python tools/create_fresh_database.py

# Import stats files
$env:PYTHONIOENCODING='utf-8'; python tools/simple_bulk_import.py

# Check results
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); print(f'Records: {cursor.fetchone()[0]}'); cursor.execute('SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats'); print(f'Players: {cursor.fetchone()[0]}')"

# Check for duplicates
python check_duplicates.py
```

---

## 🎯 Success Criteria

After a successful rebuild:
- ✅ `validate_schema.py` shows no issues
- ✅ Import completes without database constraint errors
- ✅ Expected number of records imported (~21K for 3,253 files)
- ✅ 0 duplicates detected
- ✅ Bot starts and commands work
- ✅ Stats match expected values (not inflated)

---

**If you encounter issues not covered here, document them and update this guide!**
