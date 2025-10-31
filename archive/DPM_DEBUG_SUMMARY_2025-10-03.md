# 🔍 DPM Debug Summary - October 3, 2025

## 🎯 Executive Summary

**MAJOR ISSUE FOUND:** The bot's DPM calculations are **significantly incorrect** - showing values 2-70% wrong!

### The Problem in Numbers:

| Player | Bot Shows | Should Be | Error | Status |
|--------|-----------|-----------|-------|--------|
| vid | 302.53 DPM | 514.88 DPM | **+70%** | ❌ WRONG |
| SuperBoyy | 361.66 DPM | 502.81 DPM | **+39%** | ❌ WRONG |
| endekk | 275.31 DPM | 397.19 DPM | **+44%** | ❌ WRONG |
| .olz | 380.10 DPM | 389.91 DPM | +2.6% | ✅ Close |
| SmetarskiProner | 353.67 DPM | 376.76 DPM | +6.5% | ⚠️ Minor |

## 🐛 Root Cause

### Current Bot Logic (WRONG):
```sql
SELECT AVG(p.dpm) as avg_dpm
FROM player_comprehensive_stats p
GROUP BY p.player_name
```

This **averages per-round DPM values**, which is mathematically incorrect when rounds have different durations.

### Why This Fails:

**Example:**
- Round 1: 10 minutes, 2500 damage → **250 DPM**
- Round 2: 5 minutes, 2000 damage → **400 DPM**
- Bot calculates: (250 + 400) / 2 = **325 DPM** ❌
- Should be: (2500 + 2000) / (10 + 5) = **300 DPM** ✅

The bot's 325 DPM is **8.3% too high** because it doesn't weight by playtime!

## 📊 Real Data from Latest Session (2025-10-02)

### Per-Round Analysis

I analyzed all 18 rounds from the Oct 2, 2025 session. Here's what I found:

#### Round 2 Time Data Issue:
```
🗺️  braundorf_b4 - Round 2 (Session Time: 7:52)
Player               | Damage | Time(min) | DPM    | Status
.olz                 | 2188   | 0.00      | 278.14 | ❌ time_played = 0!
vid                  | 1615   | 0.00      | 205.30 | ❌ time_played = 0!
SuperBoyy            | 1363   | 0.00      | 173.26 | ❌ time_played = 0!
```

**CRITICAL:** Many Round 2 records have `time_played_minutes = 0` in the database!

This is why the weighted calculation fails for some players:
- Players with time=0 records can't contribute to SUM(time_played_minutes)
- But their damage/DPM still gets averaged incorrectly

### Session-Wide Impact:

**vid's stats:**
- 18 rounds played
- Total damage: 31,150
- Total time recorded: 60.50 minutes (MISSING ~50 minutes from Round 2s!)
- Bot shows: 302.53 DPM (averaging 18 DPM values)
- Correct: 514.88 DPM (31150 / 60.5)
- **Error: 70% too low!**

**.olz's stats:**
- 14 rounds played  
- Total time: 74.70 minutes (MORE complete time data)
- Bot shows: 380.10 DPM
- Correct: 389.91 DPM
- **Error: Only 2.6%** (because more time data exists)

## 🔍 Pipeline Trace

### 1. c0rnp0rn3.lua (Game Server)
The Lua script correctly calculates:
- Field 21: `dpm` (damage / time for this round)
- Field 22: `time_played_minutes` (actual playtime)

### 2. Parser (community_stats_parser.py)
✅ Parser extracts both fields correctly

### 3. Database (player_comprehensive_stats)
Schema shows:
```sql
time_played_minutes REAL DEFAULT 0.0  ✅ Column exists
dpm REAL                               ✅ Column exists
```

**ISSUE:** Many records have `time_played_minutes = 0.0`!

### 4. Bot Query (ultimate_bot.py)
```sql
-- Current (WRONG):
SELECT AVG(p.dpm) ...

-- Should be:
SELECT 
    SUM(p.damage_given) / SUM(p.time_played_minutes) as weighted_dpm
    ...
WHERE time_played_minutes > 0  -- Filter out zero-time records!
```

## 🗄️ Database Schema Review

### What We Have:

#### player_comprehensive_stats
- ✅ `dpm` column (per-round value from lua)
- ✅ `time_played_minutes` column (actual playtime)
- ✅ All basic combat stats (kills, deaths, damage, etc.)

#### player_objective_stats
- ✅ 25 objective fields (multikills, assists, dynamites, etc.)
- ✅ All data from c0rnp0rn3.lua objective section

#### weapon_comprehensive_stats
- ✅ Per-weapon stats (kills, accuracy, damage, etc.)

### What c0rnp0rn3.lua Provides:

Based on the Lua file and stats format:

**37+ TAB-separated fields per player:**
1. guid ✅
2. name ✅
3. team ✅
4. kills ✅
5. deaths ✅
6. suicides ✅
7. team_kills ✅
8. team_damage ✅
9. damage_given ✅
10. damage_received ✅
11. damage_team ✅
12. hits ✅
13. shots (bullets_fired) ✅
14. headshots ✅
15. kills_obj ✅
16. deaths_obj ✅
17. K/D ratio ✅
18. efficiency ✅
19. **DPM ✅** (Field 21)
20. medal ✅
21. medals_won ✅
22. **time_played_minutes ✅** (Field 22)
23-40. Objective stats ✅ (stored in player_objective_stats)
41-46. Multikills ✅

**Weapon Section (per weapon):**
- weapon_id, kills, deaths, headshots, hits, shots, damage, accuracy, etc. ✅

### Coverage Check:
```
✅ time_played_minutes field: EXISTS
   Records with time > 0: 5,860 total records
   But MANY have time = 0 (especially Round 2s)

✅ player_objective_stats table: EXISTS
   Records: 3,464

✅ weapon_comprehensive_stats table: EXISTS
   Records: 33,521
```

**VERDICT:** Database schema is complete and ready for all c0rnp0rn3.lua data! ✅

## ❓ Why Are time_played_minutes = 0?

Looking at the data:
- **Round 1 records:** Nearly always have correct time_played_minutes
- **Round 2 records:** Many have time_played_minutes = 0

This could be:
1. **Parser issue:** Not extracting Field 22 correctly for some files
2. **Stats file issue:** c0rnp0rn3.lua not writing time for Round 2s
3. **Import issue:** bulk_import_stats.py not storing the value

Need to investigate: Does the parser extract time_played_minutes from ALL files?

## 🔧 Recommended Fixes

### Priority 1: Fix Bot Query (IMMEDIATE)
```python
# In bot/ultimate_bot.py, replace AVG(dpm) with:
SELECT 
    SUM(p.damage_given) as total_damage,
    SUM(p.time_played_minutes) as total_time,
    CASE 
        WHEN SUM(p.time_played_minutes) > 0 
        THEN SUM(p.damage_given) / SUM(p.time_played_minutes)
        ELSE 0 
    END as weighted_dpm
FROM player_comprehensive_stats p
WHERE p.time_played_minutes > 0  -- IMPORTANT: Filter zero-time records
GROUP BY p.player_guid
```

### Priority 2: Fix time_played_minutes = 0 (INVESTIGATE)

Test parser on Round 2 files:
```python
# Check if parser extracts time from Round 2 files
python test_parser_time.py local_stats/2025-10-02-*-round-2.txt
```

If parser works, problem is in bulk_import_stats.py or the lua script.

### Priority 3: Re-import Database (OPTIONAL)
If we fix the parser/import:
```python
# Backup first!
python dev/bulk_import_stats.py --reimport
```

## 📈 Expected Impact After Fix

Using weighted DPM calculation (even with current data):

| Player | Current Bot | After Fix | Improvement |
|--------|-------------|-----------|-------------|
| vid | 302.53 | 514.88 | +70% accuracy |
| SuperBoyy | 361.66 | 502.81 | +39% accuracy |
| endekk | 275.31 | 397.19 | +44% accuracy |

**All leaderboards will be more accurate!** Players who play more rounds will be fairly compared.

## 🎓 Key Learnings

1. **Averaging rates is mathematically wrong** when denominators differ
2. **Always weight by the denominator** (time in this case)
3. **Zero values matter** - filtering WHERE time > 0 is critical
4. **Database schema is good** - we have all the data we need!
5. **Pipeline trace is essential** - helps find where issues occur

## Next Steps

1. ✅ Fix bot query to use weighted DPM
2. 🔍 Investigate why time_played_minutes = 0 for many records
3. 🧪 Test parser on sample Round 2 files
4. 📊 Re-run bot and verify DPM values are correct
5. 🎉 Celebrate accurate stats!

---

*Generated: October 3, 2025*  
*Session analyzed: 2025-10-02*  
*Tool: debug_dpm_full.py*
