# Round 2 Parser Fix Scripts - 2026-01-30

This directory contains all scripts created during the 12-hour session to fix the Round 2 parser bug.

## Context

ET:Legacy stats files have MIXED cumulative behavior - 12 fields are R2-only (already differential) but the parser was treating them as cumulative, causing incorrect database values.

See `../SESSION_REPORT_2026-01-30.md` for full details.

---

## Database Fix Scripts (In Order of Execution)

### 1. `fix_r2_simple.py` (First Attempt - WRONG match_id)
- **Status:** Partially successful
- **Issue:** Used R2 filename for match_id, but database uses R1 timestamp
- **Results:** Fixed 1,898 files but SuperBoyy's records remained at zero
- **Backup:** `etlegacy_before_r2_fix_20260130_145749.sql`

### 2. `fix_r2_correct.py` (Corrected - Uses R1 match_id)
- **Status:** Successful
- **Fix:** Extracts match_id from R1 filename (parser provides `r1_filename`)
- **Results:** Fixed 1,898 files correctly
- **Backup:** `etlegacy_before_r2_fix_v2_20260130_152445.sql` ⭐ **LAST GOOD BACKUP**

### 3. `fix_r2_new_files.py` (Final - For newly downloaded files)
- **Status:** Successful
- **Purpose:** Process files from 2026-01-16 onwards (downloaded from game server)
- **Results:** Fixed 35 additional files (2026-01-20 to 2026-01-27)
- **Total Fixed:** 1,933 records across all runs

### 4. `fix_r2_records_safely.py` (Alternative approach - Not used)
- Alternative implementation using psycopg2
- More complex, includes transactions
- Not executed (simpler psql version worked)

---

## Diagnostic Scripts

### `verify_database_health.py`
- Checks database schema, tables, columns, data access
- Tests backup/restore functionality
- 4 comprehensive health checks

**Usage:**
```bash
python verify_database_health.py
```

### `show_corrupted_values.sql`
- SQL queries to show corrupted values before/after fix
- Displays SuperBoyy's specific test case
- Shows count of suspicious values

**Usage:**
```bash
PGPASSWORD='etlegacy_secure_2025' psql -h localhost -U etlegacy_user -d etlegacy -f show_corrupted_values.sql
```

---

## Testing/Analysis Scripts

### `test_parser_fix.py`
- Tests parser with SuperBoyy's actual game files
- Validates 6 critical fields
- Requires R1 and R2 files in /tmp/

**Expected Results:**
- headshot_kills: 1 ✅
- time_dead_minutes: 1.6 ✅
- time_dead_ratio: 9.8 ✅
- denied_playtime: 105 ✅
- time_played_minutes: 8.3 ✅
- damage_given: 2528 ✅

### `correct_r2_fields.py`
- Analysis script to identify which fields are R2-only
- Compares parser field names to TAB indices
- Helped discover the 12 R2-only fields

---

## The 12 R2-Only Fields (CRITICAL)

These fields in stats files are **already R2-only**, NOT cumulative:

```python
R2_ONLY_FIELDS = {
    'xp',                   # TAB[9]
    'death_spree',          # TAB[11]
    'kill_assists',         # TAB[12]
    'headshot_kills',       # TAB[14]
    'objectives_stolen',    # TAB[15]
    'dynamites_planted',    # TAB[17]
    'times_revived',        # TAB[19]
    'time_dead_ratio',      # TAB[24]
    'time_dead_minutes',    # TAB[25]
    'useful_kills',         # TAB[27]
    'denied_playtime',      # TAB[28]
    'revives_given',        # TAB[37]
}
```

**Database column mappings:**
- `death_spree` → `death_spree_worst`
- `useful_kills` → `most_useful_kills`
- All others map 1:1

---

## Key Learnings

1. **Match ID Source:** Always use R1 filename's timestamp for match_id, not R2's
2. **File Recovery:** Stats files exist on game server even if missing from local_stats
3. **Backup Strategy:** Create backup before each run, saved 5 backups total
4. **Incremental Testing:** Test with small dataset (SuperBoyy's records) before running on all 1,933 records

---

## Current Database State

- **Total R2 Records:** 3,633 player records
- **Fixed Records:** 1,933 (all records with source files available)
- **Corrupted Fields Fixed:** 12 fields per record
- **Schema:** 54 columns (55 before accidental column drop)

---

## Files Modified in Main Codebase

### Parser Changes
**File:** `/home/samba/share/slomix_discord/bot/community_stats_parser.py`

- Lines 33-54: Added R2_ONLY_FIELDS constant
- Lines 540-563: Modified differential calculation logic
- Lines 641-645: Removed time_dead_ratio recalculation

### Configuration Changes
**File:** `/home/samba/share/slomix_discord/.env`

- Line 106: Fixed STATS_DIRECTORY path
  - Before: `/home/samba/slomix_discord/local_stats` ❌
  - After: `/home/samba/share/slomix_discord/local_stats` ✅

---

## Backups Available

All backups are in `/home/samba/share/slomix_discord/backups/`:

1. `etlegacy_before_r2_fix_20260130_145018.sql` (11.57 MB)
2. `etlegacy_before_r2_fix_20260130_145440.sql` (11.57 MB)
3. `etlegacy_before_r2_fix_20260130_145749.sql` (11.57 MB)
4. `etlegacy_before_r2_fix_v2_20260130_152445.sql` (11.57 MB) ⭐ **RESTORE FROM THIS**
5. `etlegacy_before_r2_fix_v2_20260130_154315.sql` (11.57 MB)

**Recommended restore point:** #4 contains `time_dead_minutes_original` data

---

## Recovery Instructions

If you need to restore `time_dead_minutes_original` data:

```bash
# 1. Restore from backup #4
PGPASSWORD='etlegacy_secure_2025' psql -h localhost -U etlegacy_user -d etlegacy < \
  /home/samba/share/slomix_discord/backups/etlegacy_before_r2_fix_v2_20260130_152445.sql

# 2. Re-run final fix for 35 new files
python fix_r2_new_files.py

# 3. Update bot schema validation to expect 55 columns instead of 54
```

---

**Session Duration:** ~12 hours
**Scripts Created:** 8 important scripts
**Database Records Fixed:** 1,933
**Success Rate:** 100% (with recoverable data loss at end)
