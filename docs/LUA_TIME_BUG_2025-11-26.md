# LUA Script Time Tracking Bug
**Date:** 2025-11-26
**Status:** 🚨 CRITICAL - Parser fixed, but LUA has deeper issue

---

## Summary

I fixed the **parser bug** (it was overwriting individual time with round time), BUT I discovered a **deeper bug in the LUA script**:

**TAB Field 22 outputs 0.0 for ALL players in Round 1!**

---

## What I Fixed

### Parser Fix (✅ DONE)
**File:** `bot/community_stats_parser.py` lines 674-705

**Before:**
```python
for player in players:
    player['time_played_seconds'] = round_time_seconds  # ❌ Same for all
```

**After:**
```python
for player in players:
    # Use INDIVIDUAL time from TAB field 22
    player_time_minutes = player.get('objective_stats', {}).get('time_played_minutes', 0)

    if player_time_minutes > 0:
        player_time_seconds = int(player_time_minutes * 60)  # ✅ Individual
    else:
        player_time_seconds = round_time_seconds  # Fallback if TAB field is 0
```

This fix is **correct** and will work once the LUA script outputs proper individual times.

---

## What's Still Broken

### LUA Script Problem (❌ NOT FIXED)

**File:** `c0rnp0rn.lua` line 270, TAB field 22

```lua
-- Line 227: tp = timeAxis + timeAllies
-- Line 270: TAB field 22 = roundNum((tp/1000)/60, 1)
```

**Expected:** Each player should have different `tp` values (their individual play time)

**Reality:** All players have `tp = 0` in Round 1!

### Evidence from Stats Files:

**Round 1 (`2025-11-25-232932-etl_frostbite-round-1.txt`):**
```
Player              TAB Field 22
bronze.             0.0    ❌
.olz                0.0    ❌
SmetarskiProner     0.0    ❌
SuperBoyy           0.0    ❌
.wjs                0.0    ❌
Cru3lzor.           0.0    ❌
qmr                 0.0    ❌
vid                 0.0    ❌
```

**Round 2 Cumulative (`2025-11-25-233502-etl_frostbite-round-2.txt`):**
```
Player              TAB Field 22
SmetarskiProner     13.8   (all same)
qmr                 13.8   (all same)
SuperBoyy           13.8   (all same)
bronze.             13.8   (all same)
vid                 13.8   (all same)
.wjs                13.8   (all same)
Cru3lzor.           13.8   (all same)
.olz                13.8   (all same)
```

---

## Why This Happens

### Theory 1: Game Engine Values Not Populated Yet

**Lines 224-227 in c0rnp0rn.lua:**
```lua
local timeAxis = et.gentity_get(i, "sess.time_axis")
local timeAllies = et.gentity_get(i, "sess.time_allies")
local tp = timeAxis + timeAllies
```

These values come from the ET:Legacy game engine session data. If the engine hasn't populated them yet when the lua script runs, they'll be 0.

**When does the script run?**
- At "intermission" (end of round)
- Maybe the game engine finalizes time tracking AFTER the lua script runs?

### Theory 2: Time Tracking Only Works After First Round

- Round 1: `sess.time_axis` and `sess.time_allies` are still 0 (not initialized)
- Round 2: Values are now populated with cumulative time from both rounds

### Theory 3: All Players Really Have Same Time

- Unlikely but possible: All players joined at round start and played full duration
- But then TAB field 22 wouldn't be 0.0 for Round 1

---

## Impact

### With Current Setup:

1. **Round 1:**
   - TAB field 22 = 0.0 for all players
   - Parser falls back to round duration (9:09 = 549 seconds)
   - All players show same time ❌
   - DPM is wrong for players who joined late/left early

2. **Round 2:**
   - TAB field 22 = 13.8 minutes for all players (cumulative)
   - Differential calculation: 13.8 - 0.0 = 13.8 minutes
   - But actual R2 duration is 4:38 (4.6 minutes)
   - Parser uses differential, which falls back to round time ❌

### Result:
**Everyone still shows the same time**, just like before the parser fix!

---

## Possible Solutions

### Option 1: Fix LUA Script ⭐ (BEST)

**Problem:** `timeAxis + timeAllies` is 0 or same for everyone

**Solutions:**
1. Use a different time source from game engine
2. Track time manually in lua (store join time, calculate elapsed)
3. Call the stats collection at a different time (after engine finalizes time)

**Where to look:**
- `c0rnp0rn.lua` line 224-227: Getting time values
- `c0rnp0rn.lua` line 270: Outputting TAB field 22
- ET:Legacy docs: What other time fields are available from `et.gentity_get()`?

### Option 2: Use Alternative Time Source

**Instead of TAB field 22, use something else:**

1. **TAB Field 8** (`timePlayed` percentage):
   ```lua
   -- Line 229: timePlayed = (100.0 * timePlayed / (timeAxis + timeAllies))
   ```
   - This is a percentage (0-100)
   - Calculate: `player_time = (timePlayed / 100) * round_duration`
   - But if `timeAxis + timeAllies` is 0, this will be 0/0 = NaN

2. **Use DPM** to back-calculate time:
   ```
   time = (damage * 60) / DPM
   ```
   - TAB field 21 has DPM
   - But if DPM is also calculated wrong, this won't help

3. **Use time_dead_ratio** to derive alive time:
   ```
   alive_time = round_time * (1 - time_dead_ratio/100)
   ```
   - TAB field 24 has time_dead_ratio
   - But this assumes round_time = player_time, which may not be true

### Option 3: Accept Round Time for Now

**Reality check:** Maybe all players really DO have the same time?

- If everyone joins at round start and plays until round end
- Then using round time is actually correct!
- The bug would only affect:
  - Players who join late
  - Players who disconnect mid-round
  - Players who spec for part of the round

**How common is this?**
- Check if some players have different kill counts / death counts
- If kills/deaths vary widely but time is same → bug confirmed
- If kills/deaths are proportional to time → maybe not a bug?

---

## Testing Steps

### 1. Check if Time Values Exist in Game Engine

Add debug output to lua script:
```lua
print(string.format("Player %s: timeAxis=%d, timeAllies=%d, tp=%d",
    name, timeAxis, timeAllies, tp))
```

Run a test round and check server console output.

### 2. Check Other Time Fields

Try these ET:Legacy entity fields:
- `et.gentity_get(i, "sess.time_played")` - Already used for percentage
- `et.gentity_get(i, "client.sess.timerun_checkpoint")` - Timerun mod
- `et.trap_Milliseconds()` - Current server time
- Manual tracking: Store join time, calculate elapsed at intermission

### 3. Check When Script Runs

Add timestamp to stats file:
```lua
local script_time = et.trap_Milliseconds()
-- Output this somewhere to see when script executes
```

Compare with round end time to see if timing is the issue.

---

## Workaround (Temporary)

Until the LUA script is fixed, the parser will:
1. Try to use TAB field 22 (individual time)
2. Fall back to round duration if TAB field 22 is 0 or invalid
3. ✅ This is what my parser fix already does!

**Pros:**
- Works for future files if LUA gets fixed
- Safe fallback for current files

**Cons:**
- Still shows same time for all players in current files
- DPM calculations still wrong for late joiners/early leavers

---

## Next Steps

1. ⏳ **Investigate LUA script** - Why is `timeAxis + timeAllies` zero or same for everyone?
2. ⏳ **Test alternative time sources** - Can we use different engine fields?
3. ⏳ **Add debug output** - Log time values during round to understand behavior
4. ⏳ **Check ET:Legacy docs** - What time fields are available from game engine?
5. ⏳ **Consider manual time tracking** - Track player join/leave events in lua

---

## Files Modified

### ✅ Parser Fix (DONE)
- `bot/community_stats_parser.py` lines 674-705
- Now uses TAB field 22 if available, falls back to round time

### ❌ LUA Script (NOT FIXED)
- `c0rnp0rn.lua` line 227: `tp = timeAxis + timeAllies`
- `c0rnp0rn.lua` line 270: TAB field 22 = `roundNum((tp/1000)/60, 1)`
- **Issue:** All players have tp=0 (R1) or tp=same_value (R2)

---

## Status

- ✅ **Parser:** Fixed to use individual time from TAB field 22
- ❌ **LUA Script:** Outputs 0.0 or same value for all players
- ⏳ **Solution:** Need to fix LUA script to output actual individual player times

**Current behavior:** Parser falls back to round time (same for all), so bug still visible in practice.
