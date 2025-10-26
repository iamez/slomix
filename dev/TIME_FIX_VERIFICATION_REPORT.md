# 🔍 Time Fix Verification Report

**Date:** October 3, 2025  
**Status:** ✅ PARTIALLY FIXED - Time preservation works, but DPM calculation still uses wrong time

---

## Executive Summary

The `time_played_minutes = 0` bug **HAS BEEN FIXED** ✅

However, a **separate issue remains**: The parser calculates DPM using **session time** instead of **player time**.

---

## What Was Fixed

### Problem
Round 2 differential calculation was **losing** the `time_played_minutes` field:

```python
# BEFORE FIX (Lines 386-398):
differential_player = {
    'guid': r2_player.get('guid', 'UNKNOWN'),
    'name': player_name,
    'team': r2_player['team'],
    'kills': max(0, r2_player['kills'] - r1_player['kills']),
    'deaths': max(0, r2_player['deaths'] - r1_player['deaths']),
    # ... other fields ...
    # ❌ NO objective_stats dictionary!
}
```

**Result:** `time_played_minutes` was never preserved for Round 2 differential players.

### Solution Applied (Lines 399-417)

```python
# AFTER FIX:
differential_player = {
    'guid': r2_player.get('guid', 'UNKNOWN'),
    'name': player_name,
    'team': r2_player['team'],
    'kills': max(0, r2_player['kills'] - r1_player['kills']),
    'deaths': max(0, r2_player['deaths'] - r1_player['deaths']),
    # ... other fields ...
    'objective_stats': {}  # ✅ Added!
}

# ✅ Loop through objective_stats and calculate differentials
r2_obj = r2_player.get('objective_stats', {})
r1_obj = r1_player.get('objective_stats', {})

for key in r2_obj:
    if key == 'time_played_minutes':
        # CRITICAL: Calculate R2-only time
        r2_time = r2_obj.get('time_played_minutes', 0)
        r1_time = r1_obj.get('time_played_minutes', 0)
        differential_player['objective_stats']['time_played_minutes'] = max(0, r2_time - r1_time)
    elif isinstance(r2_obj[key], (int, float)):
        # For numeric fields, calculate differential
        differential_player['objective_stats'][key] = max(0, r2_obj.get(key, 0) - r1_obj.get(key, 0))
    else:
        # For non-numeric, use R2 value
        differential_player['objective_stats'][key] = r2_obj[key]
```

### Verification Results

Testing with **vid** player from October 2, 2025 session:

```
✅ Time Preservation:
  Round 1 time:           3.90 minutes
  Round 2 cumulative:     7.70 minutes
  R2 differential:        3.80 minutes ✅ CORRECT!

✅ Damage Calculation:
  Round 1 damage:         1,328
  Round 2 cumulative:     2,775
  R2 differential:        1,447 ✅ CORRECT!
```

**The fix works!** 🎉

---

## What Still Needs Fixing

### Issue: DPM Uses Wrong Time Denominator

The parser **still calculates DPM using session time** instead of player time:

```python
# Lines 449-454 (Round 2 differential DPM):
round_time_seconds = self.parse_time_to_seconds(round_2_cumulative_data['actual_time'])
round_time_minutes = round_time_seconds / 60.0 if round_time_seconds > 0 else 5.0

if round_time_minutes > 0:
    differential_player['dpm'] = differential_player['damage_given'] / round_time_minutes
    # ❌ WRONG: Uses round_time_minutes (session time)
    # ✅ SHOULD: Use differential_player['objective_stats']['time_played_minutes']
```

### Impact

For **vid** in Round 2:

```
Player time:    3.80 minutes
Session time:   3.85 minutes
Damage:         1,447

❌ Current (session-based):  1447 / 3.85 = 375.84 DPM
✅ Should be (player-based): 1447 / 3.80 = 380.79 DPM

Difference: 4.95 DPM (1.3% error)
```

This is the **"cDPM vs Our DPM"** issue mentioned in the documentation.

---

## Logic Issues Found

### Issue 1: DPM Calculation in Two Places

The parser calculates DPM in **two different places**:

1. **Round 2 Differential** (Lines 449-454)
   - Uses `round_2_cumulative_data['actual_time']` (session time)
   - Should use `differential_player['objective_stats']['time_played_minutes']`

2. **Regular Stats** (Lines 516-524)
   - Uses `actual_time` from header (session time)
   - Should use `player['objective_stats']['time_played_minutes']` if available

### Issue 2: Session Time vs Player Time

**Session time:** How long the round lasted on the server  
**Player time:** How long THIS player was actually in the game

They can differ when:
- Player joins late
- Player leaves early
- Player is dead (time still counting)

**Current logic:** Uses session time for ALL players (treats everyone the same)  
**Correct logic:** Use each player's individual time

### Issue 3: Field 21 vs Field 22

From the raw stats files:

```
Field 21 (DPM):              0.0  ❌ Not calculated by c0rnp0rn3.lua
Field 22 (time_played_min):  3.9  ✅ Player's actual time

Field 23 (tank_meatshield):  Should be Field 23, not 22!
```

**Wait... are we reading the wrong field?**

Let me check the parser field mapping (Line 675):

```python
'time_played_minutes': float(tab_fields[22]),
```

**This reads Field 22** which according to lua is `time_played` (in minutes). ✅ **CORRECT!**

But wait, the documentation says:
> "Field 23 = 7.7 minutes (cumulative R1+R2)"

**Confusion:** Are fields 0-indexed or 1-indexed?

Need to verify the actual field indices!

---

## Critical Questions

### Q1: Are We Reading the Correct Field?

**From lua script field order:**
- Field 20: bullets_fired
- Field 21: DPM (always 0.0)
- Field 22: time_played (in minutes)
- Field 23: tank_meatshield

**Parser reads:**
```python
'bullets_fired': int(tab_fields[20]),      # ✅
'dpm': float(tab_fields[21]),              # ✅ (but always 0.0)
'time_played_minutes': float(tab_fields[22]),  # ✅
'tank_meatshield': float(tab_fields[23]),      # ✅
```

**Conclusion:** ✅ **Fields are correct!** (0-indexed arrays)

The documentation saying "Field 23" was likely referring to **1-indexed** field numbers.

### Q2: Why Does DPM Calculation Use Session Time?

Looking at lines 449-454 and 516-524, the logic is:

```python
# Get session time from header
round_time_seconds = self.parse_time_to_seconds(actual_time)
round_time_minutes = round_time_seconds / 60.0 if round_time_seconds > 0 else 5.0

# Calculate DPM for ALL players using same session time
player['dpm'] = damage_given / round_time_minutes
```

**Why was it designed this way?**
- Simpler calculation
- Session time is always available (from header)
- Player time might not be available (though it should be from Field 22)

**Problem:** Not personalized per player.

### Q3: Should We Use Player Time for DPM?

**Option A:** Keep session-based DPM (current)
- ❌ Not personalized
- ❌ Less accurate
- ✅ Simple fallback when player time unavailable

**Option B:** Use player-based DPM (recommended)
- ✅ More accurate
- ✅ Personalized per player
- ✅ We already have the data (Field 22)
- ⚠️ Need fallback for missing data

**Recommendation:** Use **Option B** with fallback to session time.

---

## Proposed Fix for DPM Calculation

### For Regular Stats (Lines 516-524)

```python
# CURRENT (WRONG):
round_time_minutes = round_time_seconds / 60.0 if round_time_seconds > 0 else 5.0

for player in players:
    damage_given = player.get('damage_given', 0)
    if round_time_minutes > 0:
        player['dpm'] = damage_given / round_time_minutes  # ❌ Session time
    else:
        player['dpm'] = 0.0
```

```python
# PROPOSED (CORRECT):
# Calculate session time as fallback
session_time_minutes = round_time_seconds / 60.0 if round_time_seconds > 0 else 5.0

for player in players:
    damage_given = player.get('damage_given', 0)
    
    # Try to use player's individual time first
    player_time = player.get('objective_stats', {}).get('time_played_minutes', 0)
    
    # Fallback to session time if player time unavailable
    time_to_use = player_time if player_time > 0 else session_time_minutes
    
    if time_to_use > 0:
        player['dpm'] = damage_given / time_to_use  # ✅ Player time!
    else:
        player['dpm'] = 0.0
```

### For Round 2 Differential (Lines 449-454)

```python
# CURRENT (WRONG):
round_time_seconds = self.parse_time_to_seconds(round_2_cumulative_data['actual_time'])
round_time_minutes = round_time_seconds / 60.0 if round_time_seconds > 0 else 5.0

if round_time_minutes > 0:
    differential_player['dpm'] = differential_player['damage_given'] / round_time_minutes
    # ❌ Session time
else:
    differential_player['dpm'] = 0.0
```

```python
# PROPOSED (CORRECT):
# Try to use player's Round 2-only time
player_time = differential_player.get('objective_stats', {}).get('time_played_minutes', 0)

# Fallback to session time if needed
if player_time <= 0:
    round_time_seconds = self.parse_time_to_seconds(round_2_cumulative_data['actual_time'])
    player_time = round_time_seconds / 60.0 if round_time_seconds > 0 else 5.0

if player_time > 0:
    differential_player['dpm'] = differential_player['damage_given'] / player_time
    # ✅ Player time!
else:
    differential_player['dpm'] = 0.0
```

---

## Summary

### ✅ What Works Now
1. **Time preservation in Round 2 differential** - Fixed! ✅
2. **Objective stats preservation** - Fixed! ✅
3. **Data availability** - All time data is now preserved ✅

### ❌ What Still Needs Fixing
1. **DPM calculation uses session time** - Should use player time
2. **Not personalized per player** - Everyone uses same denominator
3. **1.3% error on average** - Small but incorrect

### 🎯 Recommendation

**Apply the proposed DPM fix** to use player time with session time fallback.

This will:
- ✅ Fix the cDPM vs Our DPM discrepancy
- ✅ Provide accurate, personalized DPM
- ✅ Maintain fallback for edge cases
- ✅ No database schema changes needed (just reimport)

---

**Next Steps:**
1. ✅ Time preservation fix - **DONE**
2. ⏳ Apply DPM calculation fix - **PENDING**
3. ⏳ Test with October 2 files - **PENDING**
4. ⏳ Re-import database - **PENDING**
5. ⏳ Verify bot displays correct DPM - **PENDING**

**Last Updated:** October 3, 2025
