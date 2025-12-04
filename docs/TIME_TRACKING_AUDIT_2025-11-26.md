# Time Tracking Pipeline Audit
**Date:** 2025-11-26
**Status:** 🚨 CRITICAL BUG FOUND

---

## Executive Summary

**CRITICAL BUG:** All players in a round show the same `time_played_seconds` value (the round duration), instead of their individual play time. This affects DPM calculations and all time-based statistics.

---

## Complete Time Metrics Inventory

### 1. Player-Level Time Metrics (per player per round)

| Field | Type | Source | What It Should Track | What It Actually Tracks |
|-------|------|--------|---------------------|-------------------------|
| **time_played_seconds** | INTEGER | Parser (❌ WRONG) | Individual player time in round | ❌ **ROUND DURATION (same for all players)** |
| **time_played_minutes** | REAL | Parser | Same as above but in minutes | ❌ **ROUND DURATION / 60 (same for all players)** |
| **time_dead_minutes** | REAL | Lua TAB Field 25 (✅ CORRECT) | Time player was dead | ✅ **Individual player dead time** |
| **time_dead_ratio** | REAL | Lua TAB Field 24 (✅ CORRECT) | Percentage of time dead (0-100) | ✅ **Individual percentage** |
| **denied_playtime** | INTEGER | Lua TAB Field 28 (✅ CORRECT) | Milliseconds enemies were dead from YOUR damage | ✅ **Individual denied time** |

### 2. Round-Level Time Metrics (per round)

| Field | Type | Source | What It Tracks |
|-------|------|--------|----------------|
| **time_limit** | TEXT | Lua Header Field 6 | Server's map time limit setting (e.g., "20:00") |
| **actual_time** | TEXT | Lua Header Field 7 | How long the round actually lasted (e.g., "12:34") |
| **actual_playtime_seconds** | INTEGER | Lua Header Field 9 (NEW format) | Exact round duration in seconds |

---

## The Bug Explained

### What Lua Outputs (c0rnp0rn.lua line 270):

```lua
-- TAB Field 22: roundNum((tp/1000)/60, 1)
-- where tp = timeAxis + timeAllies (in milliseconds)
```

**TAB Field 22 = Individual player's total time on both teams (in minutes)**

Example:
- Player A: TAB Field 22 = 15.0 (played full round)
- Player B: TAB Field 22 = 8.5 (joined late)
- Player C: TAB Field 22 = 12.3 (left early)

### What Parser Does (community_stats_parser.py):

**Step 1 (line 854):** ✅ Correctly reads TAB Field 22
```python
'time_played_minutes': safe_float(tab_fields, 22)
```

**Step 2 (lines 664-693):** ❌ **OVERWRITES with round duration!**
```python
# Get round duration from header
if actual_playtime_seconds is not None:
    round_time_seconds = int(actual_playtime_seconds)  # e.g., 900 seconds
else:
    round_time_seconds = self.parse_time_to_seconds(actual_time)

# Apply SAME time to ALL players
for player in players:
    player['time_played_seconds'] = round_time_seconds  # ❌ BUG!
    player['time_played_minutes'] = round_time_seconds / 60.0
```

Result:
- Player A: time_played_seconds = 900 ✅ (correct, played full round)
- Player B: time_played_seconds = 900 ❌ (wrong, only played 510 seconds)
- Player C: time_played_seconds = 900 ❌ (wrong, only played 738 seconds)

### Database Evidence:

```sql
-- Round 7483 (278 seconds total)
round_id | player_name     | time_played_seconds | time_dead_minutes
7483     | bronze.         | 278                 | 1.40         ✅ Individual
7483     | Cru3lzor.       | 278                 | 0.95         ✅ Individual
7483     | vid             | 278                 | 0.18         ✅ Individual
         | (all same)      | (all 278!)          | (all different) ✅
```

**Proof:** `time_dead_minutes` is different per player (✅ correct), but `time_played_seconds` is identical (❌ bug).

---

## Impact Analysis

### 1. DPM (Damage Per Minute) is Wrong

**Current calculation (lines 687-690):**
```python
if round_time_seconds > 0:
    player['dpm'] = (damage_given * 60) / round_time_seconds
```

**Problem:** Uses round time instead of player's actual time

**Example:**
- Player B did 3000 damage in 8.5 minutes (joined late)
- But DPM calculated as: `(3000 * 60) / 900 = 200 DPM`
- Correct DPM should be: `(3000 * 60) / 510 = 352.9 DPM`

**Result:** Players who join late or play less have artificially LOW DPM!

### 2. Time-Based Stats are Meaningless

- "Time played" shows round duration, not actual player time
- Can't distinguish between full-time players and late joiners
- Session summaries show wrong total play time
- Can't calculate actual "kills per minute" per player

### 3. Efficiency Metrics are Skewed

Any metric that uses time is wrong:
- Damage per minute
- Kills per minute
- Revives per minute
- XP per minute

---

## Why time_dead_minutes is Correct

**Lua script (line 257-260):**
```lua
if tp > 120000 then
    topshots[i][14] = roundNum((death_time_total[i] / tp) * 100, 1)  -- ratio
end
topshots[i][14] = roundNum((death_time_total[i] / 60000), 1)  -- minutes
```

The lua script **calculates and outputs** `time_dead_minutes` and `time_dead_ratio` directly. The parser just reads these values from TAB fields 24 & 25, never overwrites them.

---

## Time Metrics Sources

### From LUA Script (c0rnp0rn.lua):

| TAB Field | What Lua Outputs | Formula | Notes |
|-----------|------------------|---------|-------|
| Field 8 | `timePlayed` (percentage) | `(timePlayed / (timeAxis + timeAllies)) * 100` | Percentage of round player was alive |
| Field 21 | `dpm` | `(damageGiven * 60) / ((tp/1000)/60)` | ✅ Lua calculates DPM correctly |
| **Field 22** | **time_played_minutes** | **`(timeAxis + timeAllies) / 1000 / 60`** | ✅ **Individual player time** |
| Field 24 | `time_dead_ratio` | `(death_time_total / tp) * 100` | Percentage dead |
| Field 25 | `time_dead_minutes` | `death_time_total / 60000` | Minutes dead |
| Field 28 | `denied_playtime` | `topshots[i][16] / 1000` | Seconds (not milliseconds) |

### From Header (fields 6-9):

| Field | Content | Example | Usage |
|-------|---------|---------|-------|
| 6 | `map_time` (time limit) | "20:00" | Map setting |
| 7 | `actual_time` (round duration) | "12:34" | How long round lasted |
| 9 | `actual_playtime_seconds` | 754 | NEW format: exact seconds |

### In Database:

| Column | Should Be | Actually Is |
|--------|-----------|-------------|
| `time_played_seconds` | Individual player time | ❌ Round duration |
| `time_played_minutes` | Individual / 60 | ❌ Round duration / 60 |
| `time_dead_minutes` | Individual dead time | ✅ Correct |
| `time_dead_ratio` | Individual % dead | ✅ Correct |
| `denied_playtime` | Individual denied | ✅ Correct |

---

## Correct Time Calculations

### What SHOULD happen:

```python
# 1. Read individual player time from TAB field 22
player_time_minutes = safe_float(tab_fields, 22)  # From lua
player_time_seconds = int(player_time_minutes * 60)

# 2. Store individual time
player['time_played_seconds'] = player_time_seconds  # ✅ INDIVIDUAL
player['time_played_minutes'] = player_time_minutes

# 3. Calculate DPM using PLAYER'S time
if player_time_seconds > 0:
    player['dpm'] = (damage_given * 60) / player_time_seconds  # ✅ CORRECT
```

### What ACTUALLY happens:

```python
# 1. Read individual player time
player_time_minutes = safe_float(tab_fields, 22)  # ✅ Correctly read

# 2. OVERWRITE with round time
round_time_seconds = parse_round_duration_from_header()
player['time_played_seconds'] = round_time_seconds  # ❌ BUG!

# 3. Calculate DPM using ROUND time
if round_time_seconds > 0:
    player['dpm'] = (damage_given * 60) / round_time_seconds  # ❌ WRONG!
```

---

## The Fix

### File: `bot/community_stats_parser.py`

**Lines 664-693: REMOVE the time overwrite**

```python
# BEFORE (WRONG):
for player in players:
    player['time_played_seconds'] = round_time_seconds  # ❌ Overwrites individual time
    player['time_played_minutes'] = round_time_seconds / 60.0

# AFTER (CORRECT):
for player in players:
    # Use individual player time from TAB field 22 (already in objective_stats)
    player_time_minutes = player.get('objective_stats', {}).get('time_played_minutes', 0)
    player_time_seconds = int(player_time_minutes * 60) if player_time_minutes > 0 else 0

    # Store individual time
    player['time_played_seconds'] = player_time_seconds  # ✅ Individual
    player['time_played_minutes'] = player_time_minutes

    # Calculate DPM using PLAYER's actual time
    if player_time_seconds > 0:
        player['dpm'] = (damage_given * 60) / player_time_seconds
    else:
        player['dpm'] = 0.0
```

---

## Round Time vs Player Time

### When are they different?

1. **Player joins late**
   - Round: 15:00 (900 seconds)
   - Player: 8:30 (510 seconds) - joined at 6:30 mark

2. **Player leaves early**
   - Round: 15:00 (900 seconds)
   - Player: 10:15 (615 seconds) - left at 10:15 mark

3. **Player disconnects/reconnects**
   - Round: 15:00 (900 seconds)
   - Player: 12:20 (740 seconds) - missed 2:40 while reconnecting

4. **Spectator joins mid-round**
   - Round: 15:00 (900 seconds)
   - Player: 3:00 (180 seconds) - spectated first 12 minutes

### When are they the same?

- Player joined at round start AND played until round end
- This is the ONLY case where they should match

---

## Other Time Questions

### Q: What about "map time"?
- **Not tracked directly**
- We have `time_limit` (map setting) and `actual_time` (how long round ran)
- "Map time" = sum of both rounds' `actual_time` values

### Q: What about "round time"?
- Stored in `sessions` table as `actual_time` (TEXT, MM:SS format)
- Also in header field 9 as `actual_playtime_seconds` (INTEGER, NEW format)

### Q: What about "session time"?
- Not stored directly
- Calculate by summing all `actual_time` values for rounds in session

### Q: Should DPM use player time or round time?
- **PLAYER TIME!**
- DPM = "damage per minute of playtime"
- If player only played 5 minutes, divide by 5, not by round's 15 minutes

---

## Verification Steps

1. ✅ **Check database** - Confirmed all players show same time_played_seconds
2. ✅ **Check lua script** - Confirmed TAB Field 22 is individual player time
3. ✅ **Check parser** - Confirmed parser overwrites individual time with round time
4. ⏳ **Fix parser** - Remove the overwrite, use TAB field 22 value
5. ⏳ **Test with sample file** - Verify players show different times
6. ⏳ **Recalculate existing data** - Optional: fix historical data

---

## Recommendations

### Priority 1: Fix the Parser (CRITICAL)
- **File:** `bot/community_stats_parser.py` lines 664-693
- **Action:** Use TAB field 22 instead of round time for `time_played_seconds`
- **Impact:** Fixes all future imports

### Priority 2: Document Time Semantics
- **File:** `docs/FIELD_MAPPING.md`
- **Action:** Clarify that `time_played_seconds` is individual player time, not round time
- **Impact:** Prevents future confusion

### Priority 3: Fix Historical Data (Optional)
- **Action:** Re-parse all stats files to update database with correct times
- **Impact:** Fixes DPM and time-based stats for historical rounds
- **Note:** This is a big job - 7483 rounds would need re-import

### Priority 4: Add Validation
- **Action:** Add warning if all players have identical time (likely indicates bug)
- **Impact:** Early detection of similar issues

---

## Summary

### Time Metrics Tracked:
1. **time_played_seconds** - Individual player time in round (❌ currently broken)
2. **time_played_minutes** - Same as above in minutes (❌ currently broken)
3. **time_dead_minutes** - Individual time spent dead (✅ correct)
4. **time_dead_ratio** - Percentage of time dead (✅ correct)
5. **denied_playtime** - Time enemies were dead due to your damage (✅ correct)
6. **actual_time** (rounds table) - Round duration (✅ correct)
7. **time_limit** (rounds table) - Map time limit setting (✅ correct)

### Root Cause:
Parser overwrites individual player time (TAB field 22) with round duration (header field 7/9)

### Solution:
Use TAB field 22 value instead of round duration for player time

### Impact:
- All DPM calculations wrong
- All time-based stats meaningless
- Can't distinguish late joiners from full-timers

---

**Status:** 🚨 Awaiting fix
