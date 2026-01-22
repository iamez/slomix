# Stopwatch Mode Time Metrics - Complete Guide

**Date:** 2025-11-26
**Game Mode:** Competitive Stopwatch (ET:Legacy)
**Status:** ✅ All working correctly

---

## 🎮 Stopwatch Mode Context

**Key Facts:**

- Teams are **LOCKED** at round start
- **NO late joiners** allowed during round
- Everyone plays the **FULL round duration**
- Teams **SWITCH** between Round 1 and Round 2
- **Result:** Everyone has the SAME total playtime ✅

---

## ⏱️ Time Metrics Tracked

### 1. **Round Time** (per round)

**What:** How long a single round lasted

**Source:**

- Header Field 7: `actual_time` (format: "MM:SS")
- Header Field 9: `actual_playtime_seconds` (NEW format: exact seconds)

**Stored In:**

- `sessions` table: `actual_time` (TEXT, "MM:SS" format)

**Example:**

- Round 1: `actual_time = "9:09"` → 549 seconds
- Round 2: `actual_time = "4:38"` → 278 seconds

**Used For:**

- Determining round outcome (fullhold if actual < limit)
- Base for all per-round calculations

---

### 2. **Play Time** (per player per round)

**What:** How long a player was in the round

**In Stopwatch:** Same as round time (everyone plays full duration)

**Source:**

- Round duration (header field 7/9)
- Everyone gets same value ✅ CORRECT

**Stored In:**

- `player_comprehensive_stats` table: `time_played_seconds` (INTEGER)
- `player_comprehensive_stats` table: `time_played_minutes` (REAL, deprecated)

**Example:**

- Round 1 (9:09): All players = 549 seconds
- Round 2 (4:38): All players = 278 seconds

**Used For:**

- DPM calculation: `(damage * 60) / time_played_seconds`
- Kills per minute
- XP per minute
- All per-minute stats

**Note:** In stopwatch, this is always equal to round time. In other modes (campaign, pub), players could join late/leave early, so this would vary per player.

---

### 3. **Dead Time** (per player per round)

**What:** How long a player spent dead (waiting for spawn)

**Source:**

- LUA script TAB Field 24: `time_dead_ratio` (percentage 0-100)
- LUA script TAB Field 25: `time_dead_minutes` (absolute minutes)

**Calculation (in lua c0rnp0rn.lua line 258-260):**

```lua
-- time_dead_ratio = (death_time_total / total_play_time) * 100
if (death_time_total[i] / tp) * 100 > 0 then
    topshots[i][14] = roundNum((death_time_total[i] / tp) * 100, 1)
end

-- time_dead_minutes = death_time_total / 60000 (milliseconds to minutes)
roundNum((death_time_total[i] / 60000), 1)
```text

**Stored In:**

- `player_comprehensive_stats` table: `time_dead_minutes` (REAL)
- `player_comprehensive_stats` table: `time_dead_ratio` (REAL, 0-100)

**Example (Round 7483, 278 seconds total):**

```text

Player          Dead Minutes    Dead Ratio
bronze.         1.40            ?%
Cru3lzor.       0.95            ?%
vid             0.18            ?% (died least)

```yaml

**Used For:**

- Spawn efficiency analysis
- Time lost to deaths
- Comparing player survivability

**Key Insight:** This varies per player! Even though everyone plays the same total time, they die at different times and wait different durations for spawns.

---

### 4. **Map Time** (total for both rounds)

**What:** Total time spent playing a specific map (R1 + R2)

**Calculation:**

```text

Map Time = Round 1 actual_time + Round 2 actual_time

```text

**Example:**

```text

etl_frostbite:
  Round 1: 9:09 (549 seconds)
  Round 2: 4:38 (278 seconds)
  Map Time: 13:47 (827 seconds)

```sql

**Stored:** Not directly stored, calculated on-demand by summing `actual_time` from both rounds

**Used For:**

- Session summaries
- "Time played on this map" stats
- Map duration analysis

---

### 5. **Time Limit** (server setting)

**What:** Server's configured maximum round time

**Source:**

- Header Field 6: `map_time` (format: "MM:SS")

**Stored In:**

- `sessions` table: `time_limit` (TEXT, "MM:SS" format)

**Example:**

- `time_limit = "20:00"` → Server allows up to 20 minutes

**Used For:**

- Determining fullhold (did attackers complete objectives before time limit?)
- Round outcome calculation

---

### 6. **Denied Playtime** (advanced metric)

**What:** How long enemies were dead due to YOUR damage

**Source:**

- LUA script TAB Field 28: `denied_playtime` (seconds, originally milliseconds)

**Calculation (in lua c0rnp0rn.lua):**

- Tracks when enemy dies from your damage
- Measures time until they respawn
- Accumulates total "time denied"

**Stored In:**

- `player_comprehensive_stats` table: `denied_playtime` (INTEGER, seconds)

**Example:**

- Player kills 5 enemies
- Each waits ~10 seconds to respawn
- Denied playtime ≈ 50 seconds

**Used For:**

- Impact metric (how much did you slow down enemy team?)
- Spawn timing analysis
- Advanced performance metrics

---

## 📊 Time Relationships in Stopwatch

### For Each Player

```text

Total Round Time = time_played_seconds (same for everyone)
   ├─ Time Alive = time_played_seconds - (time_dead_minutes *60)
   └─ Time Dead = time_dead_minutes* 60 seconds

```text

### Example Math

```text

Round 2 (278 seconds):
Player "vid":

- Total time: 278 seconds (same as everyone)
- Dead time: 0.18 minutes = 10.8 seconds
- Alive time: 278 - 10.8 = 267.2 seconds
- Dead ratio: (10.8 / 278) * 100 = 3.9%

Player "bronze":

- Total time: 278 seconds (same as everyone)
- Dead time: 1.40 minutes = 84 seconds
- Alive time: 278 - 84 = 194 seconds
- Dead ratio: (84 / 278) * 100 = 30.2%

```yaml

**Key Insight:** "vid" was alive 96% of round, "bronze" only 70%! This affects their DPM, kills per minute, etc.

---

## 🔄 Round 2 Differential Time

**Challenge:** ET:Legacy shows **cumulative stats** in Round 2 (R1 + R2 combined)

**Solution:** Calculate differential (R2-only stats)

### Time Differential

```python
# From parser (lines 488-514)
r2_time_cumulative = 13.8 minutes  # TAB field 22 from R2 file
r1_time = 9.2 minutes              # TAB field 22 from R1 file
r2_only_time = 13.8 - 9.2 = 4.6 minutes ✅
```sql

**Note:** In stopwatch, R1 time from TAB field 22 is often 0.0 (timing issue with lua script). Parser falls back to R1 round duration, which is correct since everyone plays full duration.

---

## ⚠️ TAB Field 22 Quirk

**LUA Output (TAB Field 22):**

```lua
-- Line 270: roundNum((tp/1000)/60, 1)
-- where tp = timeAxis + timeAllies (milliseconds)
```yaml

**Observed Behavior:**

- **Round 1:** All players show 0.0 minutes
- **Round 2:** All players show same cumulative time (e.g., 13.8 min)

**Why?**

- `sess.time_axis` and `sess.time_allies` might not be populated yet when lua runs at R1 intermission
- By R2, values are accumulated (cumulative)
- In stopwatch, everyone has same time anyway, so this is not a problem

**Parser Handling:**

- If TAB field 22 is 0.0 or missing → Use round duration ✅ CORRECT
- If TAB field 22 has value → Use that value (will be same for everyone in stopwatch)

---

## 💡 DPM (Damage Per Minute) Calculation

**Formula:**

```text

DPM = (damage_given * 60) / time_played_seconds

```text

**Example:**

```text

Player "vid" in Round 2:

- Damage given: 4651
- Time played: 278 seconds
- DPM = (4651 * 60) / 278 = 1003.8

Player "bronze" in Round 2:

- Damage given: 4758
- Time played: 278 seconds
- DPM = (4758 * 60) / 278 = 1026.9

```yaml

**Why same time divisor is correct:**

- Everyone played the same 278 seconds
- Dead time doesn't reduce "time_played_seconds"
- DPM is "damage per minute of match time", not "per minute alive"

**If we used "time alive" instead:**

- "vid" alive: 267 seconds → DPM = (4651 * 60) / 267 = 1045.2
- "bronze" alive: 194 seconds → DPM = (4758 * 60) / 194 = 1472.8

But we DON'T do this because:

1. Dead time is part of the game (spawn waves)
2. Dying has a tactical cost (time penalty)
3. Standard ET stats use total round time

---

## 📈 Session Time

**What:** Total time across all rounds in a gaming session

**Calculation:**

```sql
SELECT SUM(
    CASE
        WHEN actual_time LIKE '%:%' THEN
            CAST(SPLIT_PART(actual_time, ':', 1) AS INTEGER) * 60 +
            CAST(SPLIT_PART(actual_time, ':', 2) AS INTEGER)
        ELSE
            CAST(actual_time AS INTEGER)
    END
) as total_seconds
FROM sessions
WHERE session_id = X
```sql

**Used For:**

- `/last_session` summary
- "Total time played tonight" stats

---

## ✅ Summary: All Time Metrics

| Metric | Scope | Same for All? | Source | Used For |
|--------|-------|---------------|--------|----------|
| **Round Time** | Per round | Yes | Header field 7/9 | Base time reference |
| **Play Time** | Per player/round | Yes (stopwatch) | = Round time | DPM, per-min stats |
| **Dead Time** | Per player/round | **No** ✅ | TAB fields 24/25 | Spawn efficiency |
| **Map Time** | Per map | Yes | Sum of round times | Session stats |
| **Time Limit** | Per round | Yes | Header field 6 | Fullhold detection |
| **Denied Time** | Per player/round | **No** ✅ | TAB field 28 | Impact metric |

**In Stopwatch:**

- Everyone has same **Play Time** (round duration) ✅ CORRECT
- Everyone has different **Dead Time** ✅ CORRECT
- Everyone has different **Denied Time** ✅ CORRECT

---

## 🎯 Comparison with Other Stats Systems

**Our Approach:**

- `time_played_seconds` = Round duration (for all players in stopwatch)
- Dead time tracked separately
- DPM uses total round time as divisor

**Alternative Approaches (some other stats mods):**

- Use "time alive" for DPM (we don't do this)
- Track "spectator time" separately (not applicable in stopwatch)
- Use "session time" from game engine (we use round duration)

**Our approach is STANDARD** for competitive ET stopwatch stats.

---

## 📝 Validation

### Expected Behavior

✅ All players have same `time_played_seconds` in stopwatch (teams locked)
✅ Players have different `time_dead_minutes` (die at different times)
✅ DPM varies based on damage, not time (everyone has same time)
✅ Round time + dead time relationships are correct

### Evidence from Database

```sql
-- Round 7483 (278 seconds)
All players: time_played_seconds = 278 ✅
Different: time_dead_minutes = 0.18 to 1.40 ✅
```

**Conclusion:** Time tracking is working **CORRECTLY** for stopwatch mode! ✅

---

## 🚀 No Changes Needed

The pipeline is already tracking time correctly for stopwatch mode:

- ✅ Everyone has same play time (correct for locked teams)
- ✅ Dead time varies per player (correct - people die differently)
- ✅ DPM uses round duration (correct - standard approach)
- ✅ Differential calculation works (R2 - R1 stats)

**Status:** No bugs found, all working as intended for competitive stopwatch! 🎉
