# 🔍 DPM Calculation Investigation Results

## Problem Summary

The DPM (Damage Per Minute) values shown in Discord's `!last_session` command are **mathematically incorrect** due to how Round 2 data is stored.

## Root Cause

### Round 2 Files Have `actual_time = 0:00`
- **19.6% of Round 2 files** show `0:00` for actual_time in stats file headers
- This happens when g_nextTimeLimit cvar is not set properly
- **BUT**: c0rnp0rn3.lua STILL tracks the actual playtime internally
- **RESULT**: The DPM values in Round 2 are calculated correctly by the Lua script, but we can't verify them

### Current Bot Logic
```sql
SELECT AVG(p.dpm) as avg_dpm
FROM player_comprehensive_stats p
WHERE p.session_id IN (...)
GROUP BY p.player_name
```

**This averages per-round DPM values**, which is incorrect when:
- Round 1: 10 minute game → DPM = 250
- Round 2: 5 minute game → DPM = 400
- Average: (250 + 400) / 2 = **325 DPM** ❌

**Correct calculation should be:**
- Total damage: Round1(2500) + Round2(2000) = 4500
- Total time: 10 + 5 = 15 minutes
- DPM: 4500 / 15 = **300 DPM** ✅

## Evidence from Latest Session (2024-12-29)

### Player: .olz
| Round | Map | Actual Time | Damage | DPM in DB | Verification |
|-------|-----|-------------|--------|-----------|--------------|
| R1 | etl_frostbite | 9:24 (564s) | 2469 | 262.66 | ✅ 262.66 |
| R2 | etl_frostbite | 0:00 (0s) | 864 | 274.29 | ❌ Should be unknown |
| R1 | etl_sp_delivery | 11:49 (709s) | 2595 | 219.61 | ✅ 219.61 |
| R2 | etl_sp_delivery | 0:00 (0s) | 1446 | **289.20** | ❌ We can't verify this |
| R1 | supply | 6:39 (399s) | 1517 | 228.12 | ✅ 228.12 |
| R2 | supply | 0:00 (0s) | 1856 | **371.20** | ❌ We can't verify this |

**Result:**
- Bot shows: **280.95 DPM** (AVG of 10 rounds including bad Round 2 values)
- Manual calculation: **399.98 DPM** (16,719 damage ÷ 41.8 minutes)
- **Difference: 119.03 DPM** (42% error!)

### Player: s&o.lgz (Top player by kills)
- Bot shows: **360.13 DPM**
- Manual calculation: **559.72 DPM**
- **Difference: 199.59 DPM** (55% error!)

## Why This Matters

1. **Leaderboards are inaccurate** - Players with more Round 2 games get artificially inflated/deflated DPM
2. **Can't compare players fairly** - Some played more Round 1, others more Round 2
3. **Stats don't match what actually happened** - The lua script knows the truth, but we're averaging wrong

## The Fix Options

### Option 1: Store time_played_minutes in Database ✅ RECOMMENDED
```sql
ALTER TABLE player_comprehensive_stats
ADD COLUMN time_played_minutes REAL DEFAULT 0.0;
```

Then bot uses:
```sql
SELECT 
    SUM(p.damage_given) as total_damage,
    SUM(p.time_played_minutes) as total_minutes,
    (SUM(p.damage_given) / SUM(p.time_played_minutes)) as actual_dpm
FROM player_comprehensive_stats p
GROUP BY p.player_name
```

### Option 2: Use session actual_time ❌ DOESN'T WORK
- Round 2 sessions have actual_time = 0:00
- Can't calculate accurate DPM without player's actual playtime
- Players join/leave mid-round, so session time ≠ player time

### Option 3: Ignore DPM field entirely ❌ WASTEFUL
- The lua script calculates DPM correctly
- We're just not using it properly

## Recommendation

**Modify bulk_import_stats.py to extract and store `time_played_minutes`:**

1. Parser already extracts it: `objective_stats.get('time_played_minutes', 0.0)`
2. Add column to database schema
3. Update bulk import to store it
4. Update bot query to calculate weighted average

This will give us:
- ✅ Accurate DPM across multiple rounds
- ✅ Correct leaderboards
- ✅ Fair player comparisons
- ✅ Works even when Round 2 actual_time is 0:00

## Current Status

**The DPM values you see in Discord are AVERAGES of per-round values**, not actual damage-per-minute played. This causes significant errors (40-55%) when players have different playtimes across rounds.

The c0rnp0rn3.lua script knows the truth (field 21 = dpm, field 22 = time_played_minutes), but we're not using the time data to calculate weighted averages.
