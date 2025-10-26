# 🔧 DPM Calculation Fix - Implementation Notes

**Date:** October 3, 2025  
**Backup:** `database_backups/dpm_fix_20251003_103546/`

## Problem Summary

Bot shows **35-55% incorrect DPM values** because it uses `AVG(dpm)` which averages per-round DPM values instead of calculating weighted average based on actual playtime.

### Example Error:
- Player: s&o.lgz (2024-12-29)
- Bot shows: 360.13 DPM
- Should be: 559.72 DPM
- **Error: 55% too low!**

## Root Cause

**Current bot query:**
```sql
SELECT AVG(p.dpm) as dpm
FROM player_comprehensive_stats p
GROUP BY p.player_name
```

This averages DPM values across rounds of different durations:
- Round 1: 10 min, 2500 dmg → 250 DPM
- Round 2: 5 min, 2000 dmg → 400 DPM
- Bot: (250 + 400) / 2 = **325 DPM** ❌
- Should be: 4500 / 15 = **300 DPM** ✅

## Solution

### Step 1: Add time_played_minutes column ✅
```sql
ALTER TABLE player_comprehensive_stats 
ADD COLUMN time_played_minutes REAL DEFAULT 0.0;
```

### Step 2: Update bulk_import_stats.py ✅
Extract `time_played_minutes` from parser and store it:
```python
time_played_minutes = objective_stats.get('time_played_minutes', 0.0)
```

### Step 3: Update bot query ✅
Calculate weighted DPM:
```sql
SELECT 
    SUM(p.damage_given) as total_damage,
    SUM(p.time_played_minutes) as total_minutes,
    CASE 
        WHEN SUM(p.time_played_minutes) > 0 
        THEN SUM(p.damage_given) / SUM(p.time_played_minutes)
        ELSE 0 
    END as weighted_dpm
FROM player_comprehensive_stats p
GROUP BY p.player_name
```

## Changes Made

### Files Modified:

1. **Database Schema** (`etlegacy_production.db`)
   - Added `time_played_minutes REAL` column to `player_comprehensive_stats`

2. **dev/bulk_import_stats.py** (lines ~170-220)
   - Added `time_played_minutes` to INSERT statement
   - Extract from `objective_stats.get('time_played_minutes', 0.0)`

3. **bot/ultimate_bot.py** (line ~767)
   - Changed from `AVG(p.dpm)` to `SUM(damage)/SUM(time_played_minutes)`
   - Added CASE statement to handle division by zero

## Testing Plan

1. ✅ Create backup
2. ⏳ Add database column
3. ⏳ Update bulk import script
4. ⏳ Update bot query
5. ⏳ Re-import database (populate new field)
6. ⏳ Run `quick_dpm_debug.py` to verify accuracy

## Expected Results

After fix, DPM values should be:
- ✅ Mathematically correct (weighted by playtime)
- ✅ Match manual calculation: total_damage / total_minutes
- ✅ No more 35-55% errors
- ✅ Fair comparison across players with different play patterns

## Rollback Plan

If anything goes wrong:
```powershell
# Restore from backup
Copy-Item "database_backups\dpm_fix_20251003_103546\etlegacy_production_before_dpm_fix.db" "etlegacy_production.db" -Force
```

## Notes

- Parser already extracts `time_played_minutes` (Field 22 in stats files)
- c0rnp0rn3.lua tracks this internally even when actual_time shows 0:00
- No data loss - we're adding a column, not removing anything
- Existing DPM column stays intact (per-round values remain)
- Bot will just calculate aggregated DPM differently

## Why This Works

The c0rnp0rn3.lua script provides both:
- **Field 21:** `dpm` (already calculated per round)
- **Field 22:** `time_played_minutes` (actual playtime per round)

By storing Field 22 and using it for aggregation, we get accurate DPM even when:
- Players join/leave mid-round
- Rounds have different durations
- Round 2 files show 0:00 actual_time
- Players play different number of rounds

This is the **mathematically correct** way to aggregate rate-based statistics.
