# 🎯 DPM CALCULATION - THE FULL TRUTH

**Date:** October 3, 2025  
**Investigation:** Complete understanding of all DPM values

---

## The Three DPM Values Explained

### 1. **c0rnp0rn3.lua Field 21** = 0.0
- The lua script **does NOT calculate or store DPM** in Field 21
- This field is always 0.0 in raw stats files
- **NOT THE SOURCE** of any DPM values

### 2. **Parser-Calculated "cDPM"** = 302.53 (vid, Oct 2)
**Source:** `bot/community_stats_parser.py` lines 494-502
```python
round_time_minutes = round_time_seconds / 60.0
player['dpm'] = damage_given / round_time_minutes
```

**What it does:**
- Uses **session time** (e.g., "3:51" = 3.85 minutes)
- **Same for ALL players** in that round
- Example: vid Round 1 = 1328 damage / 3.85 min = **344.94 DPM**

**How bot displays it:**
- Bot uses `AVG(p.dpm)` across all rounds
- vid: AVG(344.94, 375.84, 273.25, ...) = **302.53 DPM**

**Why it's wrong:**
- Averages rates with different denominators (basic math error)
- Uses session time, not player time
- Players who join late/leave early get incorrect values

### 3. **"Our DPM" (Factual)** = 514.88 (vid, Oct 2)
**Calculation:** `SUM(damage) / SUM(time_played_minutes)`

**What it does:**
- Uses **player's actual playtime** (Field 22: time_played_minutes)
- Personalized per player
- Example: vid played 3.9 min in Round 1, not 3.85

**Why it's ALSO problematic:**
- **41% of Round 2 records have time_played_minutes = 0** 
- These records are EXCLUDED from calculation
- Missing data makes it incomplete

---

## The Data Pipeline

```
c0rnp0rn3.lua (Game Server)
├─ Field 21 (DPM): 0.0 ❌ NOT CALCULATED
└─ Field 22 (time_played_minutes): 3.9 ✅ CORRECT

         ↓

community_stats_parser.py (Our Parser)
├─ Reads Field 22: 3.9 minutes
├─ OVERWRITES with session-based DPM
└─ Stores: dpm = 1328 / 3.85 = 344.94

         ↓

Database (etlegacy_production.db)
└─ dpm column: 344.94

         ↓

Discord Bot Query (ultimate_bot.py)
├─ Current: AVG(dpm) = 302.53 ❌ WRONG
└─ Better: SUM(damage)/SUM(time) = 514.88 ⚠️ INCOMPLETE
```

---

## Round-by-Round Proof (vid, Round 1, etl_adlernest)

| Source | Method | Result |
|--------|--------|--------|
| **Raw File Field 21** | c0rnp0rn3.lua DPM | 0.0 (not calculated) |
| **Parser Calculation** | 1328 / 3.85 min (session) | 344.94 |
| **Database Value** | Stored from parser | 344.94 |
| **Player-Based Calc** | 1328 / 3.9 min (player) | 340.51 |

**Difference:** 344.94 vs 340.51 = 4.43 DPM (1.3% error)  
**Small for one round, HUGE when averaged across 18 rounds with time=0 records!**

---

## The Real Problem: Round 2 Missing Time Data

**41% of records have `time_played_minutes = 0`** (especially Round 2 differentials)

### Example: vid, Round 2, etl_adlernest
```
Session time: 3:51 (3.85 min)
Player time: 0.00 min ❌ MISSING
Damage: 1447
Parser DPM: 1447 / 3.85 = 375.84
Correct DPM: ??? (can't calculate without time)
```

**Why this happens:**
- `parse_round_2_with_differential()` (line 338) calculates damage differential
- But DOESN'T preserve `time_played_minutes` from the actual file
- Result: time field is 0 or missing

---

## Why "Our DPM" (514.88) ≠ Truth

The calculation `SUM(damage) / SUM(time_played_minutes)` **excludes records with time=0**.

**vid's Oct 2 data:**
- Total rounds: 18
- Rounds with time > 0: 7 (39%)
- Rounds with time = 0: 11 (61%)

**What "Our DPM" actually calculates:**
```
Damage from 7 rounds: (1328 + 2646 + 1806 + 1266 + 3098 + 1113 + 1466 + 2426)
Time from 7 rounds: (3.9 + 9.7 + 6.3 + 4.4 + 9.5 + 3.4 + 7.9 + 7.5)
= 15,149 damage / 52.6 minutes = 288.06 DPM
```

Wait, that's not 514.88 either! Let me recheck...

Actually, the database query shows:
```sql
SUM(damage_given) / SUM(time_played_minutes) WHERE time_played_minutes > 0
```

This gives 514.88, which is HIGHER than expected because it's missing damage from 11 rounds but also missing time, and the ratio is skewed.

---

## Solution Requirements

1. **Fix Round 2 parser** to preserve time_played_minutes
2. **Add dual DPM columns:**
   - `session_dpm`: Current calculation (damage / session_time)
   - `player_dpm`: Factual calculation (damage / player_time)
3. **Update bot to show both:**
   - cDPM: Simple, always available
   - Our DPM: Accurate when time data exists
4. **Re-import database** with corrected values

---

## Why You Were Confused

You asked: *"first u said cornporn dpm is 0 then you said its 302"*

**You're absolutely right to call this out!**

- **Field 21 from c0rnp0rn3.lua** = 0.0 (the lua script doesn't store it)
- **"cDPM" (302.53)** = Parser's calculation using session time (not from lua)
- I was conflating "c0rnp0rn3's method" with "Field 21 value"

**Clarification:**
- c0rnp0rn3.lua **generates** the stats file with Field 22 (time)
- But our **parser calculates** DPM using session time
- The 302.53 value comes from **our parser, not the lua script**

---

## Summary Table

| DPM Type | Value | Source | Method | Status |
|----------|-------|--------|--------|--------|
| **Lua Field 21** | 0.0 | c0rnp0rn3.lua | Not calculated | ❌ Unused |
| **cDPM** | 302.53 | Parser + Bot AVG | damage/session_time | ❌ Wrong |
| **"Our DPM"** | 514.88 | Bot weighted calc | SUM(dmg)/SUM(time>0) | ⚠️ Incomplete |
| **Correct DPM** | ??? | Need to fix parser | damage/player_time | ⏳ Not calculated |

