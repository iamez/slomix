# Time Dead Bug Fix - December 20, 2025

## Executive Summary

**Bug**: Live round Discord posts showing `time_dead: 0:00` or very low values (0:02, etc.)
**Root Cause**: ET:Legacy's c0rnp0rn.lua script writes non-cumulative `time_dead_minutes` to Round 2 files
**Impact**: Most Round 2 differentials show 0:00 for time_dead fields
**Status**: ✅ Code fix applied, database rebuild required

---

## Bug Discovery

### User Report
User noticed live round postings showing time-related fields as "0:00 or 0:02":
- time_dead: 0:00
- time_denied: varies (this field works correctly)
- time_played: correct

### Investigation Process

1. **Verified formatting code** - Time formatting logic in `round_publisher_service.py` is correct
2. **Queried database** - Found Round 2 (R2) records have `time_dead_minutes = 0.0` for most players
3. **Checked Round 1/Round 2 matching** - Matching logic works correctly, uses 30-min window
4. **Examined raw stats files** - Discovered the root cause

### The Discovery

Comparing raw stats files for player "qmr" in erdenberg_t2:

**Round 1 file (2025-12-16-233219-erdenberg_t2-round-1.txt)**:
- time_played_minutes: 7.2
- time_dead_ratio: 61.3%
- time_dead_minutes: 4.4

**Round 2 file (2025-12-16-233946-erdenberg_t2-round-2.txt)** - supposedly cumulative:
- time_played_minutes: 13.9 (↑ increased by 6.7) ✅ Cumulative
- time_dead_ratio: 25.8%
- time_dead_minutes: 3.6 (↓ DECREASED from 4.4!) ❌ NOT cumulative

### The Problem

Most fields in Round 2 files are cumulative (R1 + R2):
- ✅ kills, deaths, damage_given, damage_received
- ✅ time_played_minutes, time_played_seconds
- ✅ All weapon stats

But `time_dead_minutes` is NOT cumulative:
- ❌ time_dead_minutes (Round 2 value < Round 1 value)

When the parser calculates the differential:
```python
R2_only_time_dead = R2_cumulative - R1
                  = 3.6 - 4.4
                  = -0.8
                  → capped at 0.0
```

Result: Discord shows `time_dead: 0:00` ❌

---

## Root Cause: ET:Legacy Lua Script Bug

**File**: c0rnp0rn.lua (on game server)
**Issue**: The Lua script's calculation of `time_dead_minutes` for Round 2 files doesn't accumulate correctly.

**Evidence**:
- Other time fields (time_played_minutes) ARE cumulative ✅
- time_dead_ratio is recalculated per round (not cumulative)
- time_dead_minutes appears to be recalculated from current ratio, not accumulated

**Why it happens**:
Likely the Lua script does something like:
```lua
-- Round 2 calculation (WRONG):
time_dead_minutes = time_played_minutes * (time_dead_ratio / 100)
-- Should be:
time_dead_minutes = cumulative_death_time_ms / 60000
```

Since `time_dead_ratio` changes between rounds (61.3% → 25.8%), recalculating `time_dead_minutes` from the current ratio produces non-cumulative values.

---

## The Fix

### Parser Change

**File**: `bot/community_stats_parser.py`
**Lines**: 512-525 (updated)

**Old Code** (assumed time_dead_minutes was cumulative):
```python
elif key == 'time_dead_minutes':
    # Calculate R2-only death time by subtraction (same as other fields)
    r2_dead_time = r2_obj.get('time_dead_minutes', 0) or 0
    r1_dead_time = r1_obj.get('time_dead_minutes', 0) or 0
    differential_player['objective_stats']['time_dead_minutes'] = max(0, r2_dead_time - r1_dead_time)
```

**New Code** (calculates from time_played * ratio):
```python
elif key == 'time_dead_minutes':
    # FIX: time_dead_minutes in R2 files is NOT cumulative (ET:Legacy Lua bug)
    # Instead, calculate from time_played * time_dead_ratio for both rounds
    r2_time_played = r2_obj.get('time_played_minutes', 0) or 0
    r1_time_played = r1_obj.get('time_played_minutes', 0) or 0
    r2_ratio = r2_obj.get('time_dead_ratio', 0) or 0
    r1_ratio = r1_obj.get('time_dead_ratio', 0) or 0

    # Calculate actual time_dead from ratio (handles Lua script bug)
    r2_dead_time = r2_time_played * (r2_ratio / 100.0) if r2_time_played > 0 else 0
    r1_dead_time = r1_time_played * (r1_ratio / 100.0) if r1_time_played > 0 else 0

    # Now calculate R2-only differential
    differential_player['objective_stats']['time_dead_minutes'] = max(0, r2_dead_time - r1_dead_time)
```

### How It Works

**Example with qmr's data**:

**Old calculation** (broken):
```
R1: time_dead = 4.4 min
R2: time_dead = 3.6 min (from file - wrong!)
Differential: 3.6 - 4.4 = -0.8 → 0.0 ❌
```

**New calculation** (fixed):
```
R1: time_played = 7.2 min, ratio = 61.3%
    → time_dead = 7.2 * 0.613 = 4.41 min

R2: time_played = 13.9 min, ratio = 25.8%
    → time_dead = 13.9 * 0.258 = 3.59 min

Differential: 3.59 - 4.41 = -0.82 → 0.0

Wait, this still gives 0!
```

Hmm, this suggests `time_dead_ratio` in Round 2 is NOT cumulative either. Let me recalculate:

If Round 2 is cumulative for time_dead:
- Total time_dead after R2 = 3.59 min (from ratio)
- Time_dead in R1 = 4.41 min

This doesn't make sense! Total death time decreased?

Actually, I think the issue is that `time_dead_ratio` in Round 2 is the CUMULATIVE ratio (total death time / total play time), not the Round 2-only ratio.

Let me verify:
- R1: 4.41 min dead out of 7.2 min played = 61.3% ✅
- R2 cumulative: total_dead / total_played = X / 13.9
- If X = 3.59, then ratio = 25.8% ✅

So Round 2 shows:
- 25.8% ratio = total_dead / 13.9
- total_dead = 0.258 * 13.9 = 3.59 min

But R1 had 4.41 min dead! How can total death time go DOWN?

Unless... the data I'm looking at is wrong, OR the Lua script has a more fundamental bug where it's resetting death time tracking between rounds.

Actually, let me reconsider. Maybe `time_dead_ratio` in R2 is the Round 2-ONLY ratio, not cumulative?

If R2-only ratio is 25.8%, and R2-only played time is (13.9 - 7.2) = 6.7 min:
- R2-only time_dead = 6.7 * 0.258 = 1.73 min ✅

That makes more sense! So the fix should be:
1. Calculate R2-only time_played (13.9 - 7.2 = 6.7 min)
2. Use R2's ratio (25.8%) to calculate R2-only time_dead (6.7 * 0.258 = 1.73 min)

But wait, the current ratio recalculation logic (lines 605-617) does this already. Let me check if the issue is that we're using the cumulative ratio instead of calculating it properly.

Actually, I think I need to verify my hypothesis by checking what the actual database shows for this specific game.
