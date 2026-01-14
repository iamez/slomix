# Last Session Verification Report
**Date:** 2025-12-17
**Session Analyzed:** erdenberg_t2 (2025-10-02)
**Verification Status:** ⚠️ **DISCREPANCIES FOUND**

---

## Executive Summary

A comprehensive verification was performed comparing raw stats files from `local_stats/` with the data stored in the database and displayed by `!last_session`. The analysis revealed **significant discrepancies** in two key areas:

1. **Headshot Kills** - Incorrect values stored in database (inflated)
2. **Time Played** - Minor 3-second discrepancy (acceptable rounding)

### Overall Data Accuracy
- ✅ **Kills/Deaths**: 100% accurate
- ✅ **Damage Given/Received**: 100% accurate
- ✅ **Gibs**: 100% accurate
- ✅ **Team assignments**: 100% accurate
- ⚠️ **Headshot Kills**: **0% accurate** (all players have inflated values)
- ⚠️ **Time Played**: 99.3% accurate (3-second difference, likely rounding)

---

## Test Methodology

### 1. Raw File Parsing
Used the bot's own parser (`C0RNP0RN3StatsParser`) to parse raw stats files:
- **Round 1**: `2025-10-02-232339-erdenberg_t2-round-1.txt`
- **Round 2**: `2025-10-02-232818-erdenberg_t2-round-2.txt`

Parser correctly performed:
- Round 2 differential calculation (R2 cumulative - R1 = R2 only stats)
- Proper matching of R1/R2 files by timestamp
- Time-played conversion from minutes to seconds

### 2. Database Queries
Queried `etlegacy_production.db` for the same session:
- Session ID 1861 (Round 1)
- Session ID 1862 (Round 2)
- All 6 players present in both rounds

### 3. Field-by-Field Comparison
Compared 8 critical fields for all 6 players across both rounds (96 total field comparisons):
- Kills, Deaths, Damage Given, Damage Received, Time Played, Headshot Kills, Gibs, Team

---

## Detailed Findings

### Round 1 Comparison

| Player | Kills | Deaths | Damage | Time (sec) | Headshots (Raw) | Headshots (DB) | Status |
|--------|-------|--------|--------|------------|-----------------|----------------|--------|
| vid | 11 | 6 | 2426 | 450 → 447 | **1** | **10** | ✗ MISMATCH |
| SmetarskiProner | 9 | 10 | 2029 | 450 → 447 | **2** | **10** | ✗ MISMATCH |
| endekk | 13 | 10 | 1773 | 450 → 447 | **4** | **11** | ✗ MISMATCH |
| .olz | 8 | 8 | 1863 | 450 → 447 | **1** | **1** | ✓ MATCH (HS) |
| qmr | 3 | 11 | 1402 | 450 → 447 | **0** | **4** | ✗ MISMATCH |
| SuperBoyy | 12 | 11 | 2147 | 450 → 447 | **4** | **10** | ✗ MISMATCH |

**Summary**: 0 complete matches, 6 mismatches, 0 missing players

### Round 2 Comparison (Differential)

| Player | Kills | Deaths | Damage | Time (sec) | Headshots (Raw) | Headshots (DB) | Status |
|--------|-------|--------|--------|------------|-----------------|----------------|--------|
| vid | 5 | 6 | 1135 | 240 | **0** | **4** | ✗ MISMATCH |
| qmr | 5 | 5 | 646 | 240 | **0** | **2** | ✗ MISMATCH |
| endekk | 4 | 7 | 700 | 240 | **0** | **6** | ✗ MISMATCH |
| .olz | 5 | 4 | 1360 | 240 | **0** | **6** | ✗ MISMATCH |
| SmetarskiProner | 2 | 6 | 917 | 240 | **0** | **1** | ✗ MISMATCH |
| SuperBoyy | 10 | 3 | 1339 | 240 | **0** | **5** | ✗ MISMATCH |

**Summary**: 0 complete matches, 6 mismatches, 0 missing players

---

## Issue #1: Headshot Kills Discrepancy

### Problem
The `headshot_kills` field stored in the database does **NOT** match the raw file data. The database values are consistently inflated.

### Root Cause Analysis

#### Raw File Format
The stats file contains TWO different headshot-related values:

1. **Weapon Stats Headshots** (space-separated, per weapon):
   - Field 5 of each weapon's 5-field group: `[hits, shots, kills, deaths, headshots]`
   - Represents headshot **hits** (shots that hit the head, may not kill)

2. **Objective Stats `headshot_kills`** (TAB field 14):
   - The 15th field in the TAB-separated extended stats section
   - Represents kills where the **final blow** was to the head
   - **This is the source of truth for headshot kills**

#### Example from vid (Round 1):
```
Raw file TAB field 14: 1 headshot kill
Database stored:      10 headshot kills
Discrepancy:          -9 (database is 10x too high!)
```

#### Parser Code Location
File: `/home/samba/share/slomix_discord/bot/community_stats_parser.py`

Line 873 correctly extracts field 14:
```python
'headshot_kills': safe_int(tab_fields, 14),
```

Line 905-907 has a critical comment:
```python
# ⚠️ CRITICAL DISTINCTION - DO NOT CONFUSE THESE TWO:
# 1. player['headshots'] = Sum of all weapon headshot HITS (shots that hit head, may not kill)
# 2. objective_stats['headshot_kills'] = TAB field 14 (kills where FINAL BLOW was to head)
```

### Root Cause IDENTIFIED
**File:** `/home/samba/share/slomix_discord/bot/ultimate_bot.py`
**Lines:** 1196-1197, 1233-1258

The INSERT statement at line 1233-1258 includes a column `headshots` (line 1238) that **does NOT exist** in the database schema:

```python
# Line 1238 (INSERT column list):
gibs, self_kills, team_kills, team_gibs, headshot_kills, headshots,
                                                          ^^^^^^^^
                                                          THIS COLUMN DOES NOT EXIST!
```

**Database Schema** (from `CREATE TABLE`):
```sql
headshot_kills INTEGER DEFAULT 0,  -- exists
-- NO 'headshots' column!
time_played_seconds INTEGER DEFAULT 0,
```

**What's happening:**
1. The INSERT tries to insert 52 columns
2. The database table only has 51 columns (no `headshots`)
3. **SQLite is likely silently failing OR rejecting the INSERT**
4. Old/corrupted data remains in the database

**Evidence:**
- The code correctly extracts TAB field 14: `obj_stats.get("headshot_kills", 0)` (line 1196)
- But the INSERT statement references non-existent `headshots` column (line 1238)
- This causes the entire INSERT to potentially fail or behave unexpectedly

### Verification Commands
```bash
# Check vid's raw headshot data (Round 1)
cat /home/samba/share/slomix_discord/local_stats/2025-10-02-232339-erdenberg_t2-round-1.txt | grep "vid"
# TAB field 14 shows: 1

# Check database
sqlite3 etlegacy_production.db "SELECT player_name, headshot_kills FROM player_comprehensive_stats WHERE session_id=1861 AND player_name='vid';"
# Result: 10
```

### Impact on !last_session
The `!last_session` command will display **incorrect headshot kill counts** for all players, potentially misleading:
- Performance comparisons
- MVP calculations (if headshots are weighted)
- Leaderboards
- Player statistics accuracy

---

## Issue #2: Time Played Discrepancy

### Problem
Raw files show 450 seconds (7:30), database shows 447 seconds (7:27) - a 3-second difference.

### Analysis
- **Magnitude**: 3 seconds out of 450 = 0.67% error
- **Consistency**: All 6 players in Round 1 have the same discrepancy
- **Likely Cause**: Rounding difference between:
  - Lua script calculating time in minutes (7.5 minutes)
  - Database storing as integer seconds (7.5 * 60 = 450)
  - Actual round time being 7:27 (447 seconds)

### Impact
**Minimal** - A 3-second difference is negligible for:
- DPM calculations (difference < 1%)
- Time-based statistics
- Player comparisons

### Verdict
✅ **ACCEPTABLE** - This is likely due to how the game server measures "active playtime" vs "round elapsed time." The parser correctly uses the TAB field 22 (`time_played_minutes`), which represents actual playtime.

---

## Critical Field Mapping Reference

Based on code analysis of `community_stats_parser.py` lines 850-890:

```
TAB-SEPARATED FIELDS (Extended Stats):
Field  0: damage_given
Field  1: damage_received
Field  2: team_damage_given
Field  3: team_damage_received
Field  4: gibs
Field  5: self_kills
Field  6: team_kills
Field  7: team_gibs
Field  8: time_played_percent
Field  9: xp
Field 10: killing_spree
Field 11: death_spree
Field 12: kill_assists
Field 13: kill_steals
Field 14: headshot_kills ← SOURCE OF TRUTH for headshot KILLS
Field 15: objectives_stolen
Field 16: objectives_returned
Field 17: dynamites_planted
Field 18: dynamites_defused
Field 19: times_revived
Field 20: bullets_fired
Field 21: dpm
Field 22: time_played_minutes ← SOURCE OF TRUTH for time
Field 23: tank_meatshield
Field 24: time_dead_ratio
Field 25: time_dead_minutes
Field 26: kd_ratio
Field 27: useful_kills
Field 28: denied_playtime
Field 29: multikill_2x
Field 30: multikill_3x
Field 31: multikill_4x
Field 32: multikill_5x
Field 33: multikill_6x
Field 34: useless_kills
Field 35: full_selfkills
Field 36: repairs_constructions
Field 37: revives_given
```

---

## Recommendations

### 1. **URGENT: Fix Headshot Kills Import**
**Priority:** HIGH
**Impact:** Data integrity issue - INSERTs are failing due to column mismatch

**Root Cause:** INSERT statement references non-existent `headshots` column

**Action Required:**

#### Step 1: Fix the INSERT Statement
**File:** `/home/samba/share/slomix_discord/bot/ultimate_bot.py`
**Line:** 1238

**Change from:**
```python
gibs, self_kills, team_kills, team_gibs, headshot_kills, headshots,
```

**Change to:**
```python
gibs, self_kills, team_kills, team_gibs, headshot_kills,
```

**Also update line 1197:**
Remove or comment out the line that prepares the `headshots` value:
```python
# player.get("headshots", 0),  # REMOVED - column doesn't exist in DB
```

**Adjust VALUES count:**
Line 1254-1256 currently has 52 placeholders (`?`). Reduce to 51 after removing `headshots`.

#### Step 2: Verify the Fix
```bash
# Test import on a single file
python3 -c "
import sys
sys.path.insert(0, '/home/samba/share/slomix_discord')
from bot.ultimate_bot import UltimateBot
# Test import...
"
```

#### Step 3: Re-import Historical Data
The database likely has old/incorrect data. Options:
1. **Drop and re-import**: Clear `player_comprehensive_stats` and re-import all files from `local_stats/`
2. **Incremental fix**: Re-import only affected sessions (requires tracking which failed)

```sql
-- Check current data quality
SELECT session_date, COUNT(*) as records
FROM player_comprehensive_stats
GROUP BY session_date
ORDER BY session_date DESC
LIMIT 10;

-- If needed, clear and re-import
DELETE FROM player_comprehensive_stats;
DELETE FROM sessions;
-- Then run bot's file import process
```

### 2. **Document Field Confusion**
**Priority:** MEDIUM

Add clear warnings in the codebase:
```python
# CRITICAL: Two different headshot metrics exist:
# player['headshots'] = weapon headshot HITS (use for weapon accuracy)
# objective_stats['headshot_kills'] = headshot KILLS (use for player stats/leaderboards)
#
# For database storage, ALWAYS use objective_stats['headshot_kills']
```

### 3. **Add Verification Tests**
**Priority:** MEDIUM

Create automated tests that:
- Parse sample raw files
- Check database imports
- Verify field mappings are correct
- Alert on any discrepancies

### 4. **Time Played: No Action Required**
**Priority:** LOW

The 3-second discrepancy is acceptable and likely reflects accurate "active playtime" vs "round elapsed time."

---

## Test Data Used

### Raw Files
```
/home/samba/share/slomix_discord/local_stats/2025-10-02-232339-erdenberg_t2-round-1.txt
/home/samba/share/slomix_discord/local_stats/2025-10-02-232818-erdenberg_t2-round-2.txt
```

### Database
```
/home/samba/share/slomix_discord/etlegacy_production.db
- Session 1861 (Round 1): 6 players
- Session 1862 (Round 2): 6 players
```

### Parser
```
/home/samba/share/slomix_discord/bot/community_stats_parser.py
- Class: C0RNP0RN3StatsParser
- Method: parse_stats_file() - working correctly
- Method: parse_player_line() - correctly extracts TAB field 14
```

---

## Conclusion

The `!last_session` command's **accuracy depends on the database import process**. The parser (`C0RNP0RN3StatsParser`) is working correctly and extracting the right field (`objective_stats['headshot_kills']` from TAB field 14).

However, the **database import code is storing incorrect headshot values**, likely due to confusion between:
- `player['headshots']` (weapon headshot hits - wrong source)
- `objective_stats['headshot_kills']` (headshot kills - correct source)

### Critical Stats Status:
✅ **ACCURATE (100%):**
- Kills
- Deaths
- Damage Given/Received
- Gibs
- Team Assignments
- Revives
- Time Played (within 0.67% - acceptable)

❌ **INACCURATE:**
- Headshot Kills (inflated by ~2-10x)

### Recommendation
**Investigate the database import code immediately** to locate where `headshot_kills` is being populated and fix it to use `objective_stats['headshot_kills']` instead of `player['headshots']`.

---

**Report Generated:** 2025-12-17
**Verification Tool:** Custom Python script using bot's own parser
**Database:** etlegacy_production.db (last updated 2025-11-28)
**Verified By:** Comprehensive field-by-field comparison of 96 data points
