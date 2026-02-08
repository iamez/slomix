# ✅ Parser Fix Complete - Round 2 Differential Calculation

**Date:** 2026-01-30
**Status:** PARSER FIXED - Database rebuild required

---

## What Was Fixed

### The Bug
ET:Legacy stats files have **MIXED cumulative behavior**:
- **26 fields** are cumulative (R1+R2 total) - need subtraction to get R2-only
- **12 fields** are R2-only (already differential) - use directly, NO subtraction

The parser was treating ALL fields as cumulative, corrupting 12 fields for every R2 record!

### The Fix

**1. Added R2_ONLY_FIELDS constant** (lines 33-54):
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

**2. Modified differential calculation** (lines 540-563):
```python
for key in r2_obj:
    if key in R2_ONLY_FIELDS:
        # Use R2 value directly - already differential!
        differential_player['objective_stats'][key] = r2_obj[key]
    elif key == 'time_played_minutes':
        # Cumulative - subtract R1
        diff_minutes = max(0, r2_time - r1_time)
        differential_player['objective_stats']['time_played_minutes'] = diff_minutes
    elif isinstance(r2_obj[key], (int, float)):
        # Other cumulative fields - subtract R1
        differential_player['objective_stats'][key] = max(0, r2_obj[key] - r1_obj[key])
```

**3. Removed time_dead_ratio recalculation** (lines 641-645):
- Was overwriting the correct R2-only value
- Caused incorrect ratios (19.3% instead of 9.8%)

---

## Test Results

### Before Fix (Buggy)
```
SuperBoyy R2 (from database):
  headshot_kills: 0 (should be 1)          ❌
  time_dead_minutes: -2.8 (should be 1.6)  ❌ NEGATIVE!
  time_dead_ratio: 19.3% (should be 9.8%)  ❌
  denied_playtime: -1 (should be 105)      ❌ NEGATIVE!
```

### After Fix (Correct)
```
SuperBoyy R2 (from parser):
  headshot_kills: 1          ✅
  time_dead_minutes: 1.6     ✅
  time_dead_ratio: 9.8%      ✅
  denied_playtime: 105       ✅
  time_played_minutes: 8.3   ✅
  damage_given: 2528         ✅
```

**All 6 critical fields passed validation!**

---

## Database Impact

**Current state:** ALL R2 records in database have WRONG values for 12 fields

**Affected records:** Every Round 2 record since bot started (~50% of all records)

**Corrupted columns:**
| Field | Current DB Value | Correct Value | Issue |
|-------|------------------|---------------|-------|
| xp | Too low | R2 value | Subtracted R1 |
| death_spree | Too low | R2 value | Subtracted R1 |
| kill_assists | Too low or 0 | R2 value | Subtracted R1 |
| headshot_kills | Too low or 0 | R2 value | Subtracted R1 |
| objectives_stolen | 0 or negative | R2 value | Subtracted R1 |
| dynamites_planted | 0 or negative | R2 value | Subtracted R1 |
| times_revived | 0 or negative | R2 value | Subtracted R1 |
| time_dead_ratio | Recalculated wrong | R2 value | Overwritten |
| time_dead_minutes | Negative or too small | R2 value | Subtracted R1 |
| useful_kills | Too low or 0 | R2 value | Subtracted R1 |
| denied_playtime | Too low | R2 value | Subtracted R1 |
| revives_given | 0 or negative | R2 value | Subtracted R1 |

---

## Next Steps

### Required: Database Rebuild

After fixing the parser, you MUST rebuild the database to correct all R2 records:

```bash
cd /home/samba/share/slomix_discord
python postgresql_database_manager.py
# Choose option 3: Rebuild from scratch
```

This will:
1. Drop all existing tables
2. Recreate schema
3. Re-parse ALL stats files from `local_stats/` with CORRECT logic
4. Import with accurate R2-only values

**Time estimate:** ~10-30 minutes depending on file count

**Data safety:** All stats files preserved in `local_stats/` - rebuild is safe!

---

## Backup Recommendation

Before rebuild, optionally backup current database:

```bash
pg_dump -h localhost -U etlegacy_user -d etlegacy > /tmp/database_backup_before_parser_fix.sql
```

This preserves old (buggy) values for comparison if needed.

---

## Verification After Rebuild

Check SuperBoyy's 2026-01-27 R2 record:

```sql
SELECT
    player_name,
    round_number,
    headshot_kills,
    time_dead_minutes,
    time_dead_ratio,
    denied_playtime
FROM player_comprehensive_stats
WHERE player_guid LIKE 'EDBB5DA9%'
    AND round_date = '2026-01-27'
    AND map_name = 'te_escape2'
ORDER BY round_number;
```

**Expected values:**
- R1: headshot_kills=3, time_dead=4.4, ratio=53.2%, denied=106
- R2: headshot_kills=1, time_dead=1.6, ratio=9.8%, denied=105

---

## Files Modified

1. `/home/samba/share/slomix_discord/bot/community_stats_parser.py`
   - Lines 33-54: Added R2_ONLY_FIELDS constant
   - Lines 540-563: Modified differential calculation logic
   - Lines 641-645: Removed time_dead_ratio recalculation

---

## Root Cause Explanation

**Why ET:Legacy has mixed behavior:**

The Lua stats script (`c0rnp0rn7.lua`) uses two types of variables:

1. **Session-scoped** (accumulate across R1+R2):
   - kills, deaths, damage, time_played
   - These variables keep adding throughout the match

2. **Round-scoped** (reset between rounds):
   - efficiency, headshots, objectives, time_dead
   - `function et_InitGame()` resets these to 0/empty

This design makes sense for gameplay tracking but creates parser complexity!

---

## Success Criteria

✅ Parser correctly identifies 12 R2-only fields
✅ Parser uses R2 values directly for R2-only fields
✅ Parser subtracts R1 for cumulative fields
✅ Test with SuperBoyy's data passes all 6 checks
⏳ Database rebuild with correct values
⏳ Verify R2 records match expected values

---

## User Credit

**This fix was driven by user's correct instinct:**
> "i still have a feeling that round 2 time dead is wrong xD but its just a huntch"

User was 100% right - the "fix" in January made it worse, not better!

Deep investigation revealed the problem was much bigger than time_dead - **12 fields affected**, not just 2.
