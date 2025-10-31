# 🔬 COMPREHENSIVE PIPELINE ANALYSIS - October 2, 2025
**Complete Time Data Tracking Across All Stages**

---

## 📊 EXECUTIVE SUMMARY

### What We Tracked
- **18 sessions** (9 maps × 2 rounds)
- **85 player records** across all sessions
- **6 top players** tracked individually
- **Every stage** of the data pipeline

### Critical Finding
```
✅ Round 1: 100% of records have time data (34/34)
❌ Round 2: Only 31.4% have time data (16/51)
          68.6% missing time data (35/51) - THE BUG!
```

---

## 🗺️ PER-MAP BREAKDOWN

| Map | R1 Players | R1 Time✅ | R2 Players | R2 Time✅ | R2 Time❌ | R2 Missing% |
|-----|-----------|----------|-----------|----------|----------|-------------|
| etl_adlernest | 2 | 2 | 5 | 3 | 2 | 40% |
| supply | 6 | 6 | 6 | 0 | 6 | **100%** |
| etl_sp_delivery | 4 | 4 | 6 | 2 | 4 | 67% |
| te_escape2 | 3 | 3 | 8 | 4 | 4 | 50% |
| sw_goldrush_te | 5 | 5 | 6 | 1 | 5 | 83% |
| et_brewdog | 3 | 3 | 4 | 1 | 3 | 75% |
| etl_frostbite | 2 | 2 | 5 | 3 | 2 | 40% |
| braundorf_b4 | 4 | 4 | 5 | 1 | 4 | 80% |
| erdenberg_t2 | 5 | 5 | 6 | 1 | 5 | 83% |
| **TOTALS** | **34** | **34** | **51** | **16** | **35** | **68.6%** |

### Key Observations
- **supply** map: 100% of Round 2 missing time (worst case!)
- **etl_adlernest**: Only 40% missing (best case)
- **Pattern:** Every map has Round 2 missing time
- **No exceptions:** Not a single Round 1 missing time

---

## 👤 TOP PLAYERS - TIME TRACKING

| Player | Total Rounds | Rounds with Time | Rounds Missing Time | Missing % | Status |
|--------|-------------|------------------|---------------------|-----------|---------|
| vid | 18 | 9 | 9 | 50.0% | ❌ |
| SuperBoyy | 14 | 8 | 6 | 42.9% | ❌ |
| SmetarskiProner | 14 | 9 | 5 | 35.7% | ❌ |
| .olz | 14 | 9 | 5 | 35.7% | ❌ |
| endekk | 14 | 8 | 6 | 42.9% | ❌ |
| qmr | 11 | 7 | 4 | 36.4% | ❌ |

### Impact on DPM Calculation
```
Example: vid
  Total Damage: 31,150
  Recorded Time: 60.5 min (only Round 1s!)
  Missing Time: ~46.4 min (estimated Round 2s)
  
  Current "Correct" DPM: 31,150 / 60.5 = 514.88 ❌ INFLATED
  Actual Expected DPM:   31,150 / 106.9 = ~291 ✅
  Bot's AVG DPM:         302.53 (actually pretty close!)
```

---

## 🔬 DETAILED PIPELINE TRACE: vid

### Complete Round-by-Round Tracking

| Time | Map | Rnd | Session Time | Player Time | Kills | Deaths | Damage | DPM | Status |
|------|-----|-----|-------------|-------------|-------|--------|--------|-----|---------|
| 21:18:08 | etl_adlernest | 1 | 3:51 | **3.9** | 9 | 3 | 1,328 | 344.94 | ✅ |
| 21:22:49 | etl_adlernest | 2 | 3:51 | **0.0** | 7 | 2 | 1,447 | 375.84 | ❌ |
| | supply | 1 | 9:41 | **9.7** | 20 | 12 | 2,646 | 273.25 | ✅ |
| | supply | 2 | 8:22 | **0.0** | 10 | 7 | 2,192 | 261.99 | ❌ |
| | etl_sp_delivery | 1 | 6:16 | **6.3** | 10 | 12 | 1,806 | 288.19 | ✅ |
| | etl_sp_delivery | 2 | 6:16 | **0.0** | 16 | 4 | 1,861 | 296.97 | ❌ |
| | te_escape2 | 1 | 4:23 | **4.4** | 7 | 5 | 1,266 | 288.82 | ✅ |
| | te_escape2 | 2 | 4:23 | **0.0** | 6 | 8 | 1,246 | 284.26 | ❌ |
| | te_escape2 | 2 | 4:23 | **0.0** | 9 | 3 | 1,164 | 294.68 | ❌ |
| | sw_goldrush_te | 1 | 9:28 | **9.5** | 12 | 13 | 3,098 | 327.25 | ✅ |
| | sw_goldrush_te | 2 | 8:40 | **0.0** | 15 | 11 | 2,687 | 310.04 | ❌ |
| | et_brewdog | 1 | 3:25 | **3.4** | 7 | 7 | 1,113 | 325.76 | ✅ |
| | et_brewdog | 2 | 3:25 | **0.0** | 6 | 3 | 1,163 | 340.39 | ❌ |
| | etl_frostbite | 2 | 3:27 | **7.9** | 8 | 10 | 1,491 | 432.17 | ✅ |
| | braundorf_b4 | 1 | 7:52 | **7.9** | 8 | 8 | 1,466 | 186.36 | ✅ |
| | braundorf_b4 | 2 | 7:52 | **0.0** | 12 | 3 | 1,615 | 205.30 | ❌ |
| | erdenberg_t2 | 1 | 7:27 | **7.5** | 11 | 6 | 2,426 | 325.64 | ✅ |
| | erdenberg_t2 | 2 | 4:00 | **0.0** | 5 | 6 | 1,135 | 283.75 | ❌ |

**Totals:**
- Rounds: 18 (counting te_escape2 twice)
- Recorded time: 60.5 min
- Missing time: 9 rounds × ~5.2 min avg = ~46.8 min
- Total expected: ~107.3 min

---

## 🎯 TIME CONSISTENCY CHECK

### Session Time vs Player Time Comparison

| Map | R1 Session | R2 Session | vid R1 Time | vid R2 Time | Match? |
|-----|-----------|-----------|-------------|-------------|---------|
| etl_adlernest | 3:51 | 3:51 | 3.9 min ✅ | 0.0 min ❌ | No |
| supply | 9:41 | 8:22 | 9.7 min ✅ | 0.0 min ❌ | No |
| etl_sp_delivery | 6:16 | 6:16 | 6.3 min ✅ | 0.0 min ❌ | No |
| te_escape2 | 4:23 | 4:23 | 4.4 min ✅ | 0.0 min ❌ | No |
| sw_goldrush_te | 9:28 | 8:40 | 9.5 min ✅ | 0.0 min ❌ | No |
| et_brewdog | 3:25 | 3:25 | 3.4 min ✅ | 0.0 min ❌ | No |
| etl_frostbite | 4:27 | 3:27 | 4.5 min (R1) | 7.9 min ✅ | Yes! |
| braundorf_b4 | 7:52 | 7:52 | 7.9 min ✅ | 0.0 min ❌ | No |
| erdenberg_t2 | 7:27 | 4:00 | 7.5 min ✅ | 0.0 min ❌ | No |

### Special Case: etl_frostbite Round 2
**ONLY Round 2 with time data preserved!**
- vid R2 time: 7.9 min ✅
- This proves the raw data DOES exist
- This is likely a non-differential file (regular Round 2, not cumulative)

---

## 📈 STATISTICAL ANALYSIS

### Round 1 vs Round 2 Distribution

```
Round 1 Statistics:
  Total records:    34
  With time:        34 (100.0%)
  Without time:     0  (0.0%)
  Average time:     7.1 min
  Min time:         3.4 min
  Max time:         9.7 min
  
Round 2 Statistics:
  Total records:    51
  With time:        16 (31.4%)
  Without time:     35 (68.6%)
  Average time:     9.9 min (for records with time)
  Min time:         6.9 min
  Max time:         18.2 min
```

### Pattern Recognition
```
✅ 100% of Round 1 files preserve time
❌ 68.6% of Round 2 files lose time
🔍 Pattern: Round 2 DIFFERENTIAL files lose time
✨ Exception: Non-differential R2 files keep time (etl_frostbite)
```

---

## 🔧 ROOT CAUSE CONFIRMATION

### The Bug: Round 2 Differential Calculation

**Location:** `bot/community_stats_parser.py` lines 386-398

**What Happens:**
```python
# Step 1: Parse Round 1 file
r1_player = {
    'name': 'vid',
    'damage_given': 1328,
    'time_played_minutes': 3.9,  # ✅ Preserved
    'objective_stats': {
        'time_played_minutes': 3.9  # ✅ Stored
    }
}

# Step 2: Parse Round 2 CUMULATIVE file
r2_player = {
    'name': 'vid',
    'damage_given': 2775,  # R1+R2 cumulative
    'time_played_minutes': 7.7,  # ✅ Cumulative R1+R2
    'objective_stats': {
        'time_played_minutes': 7.7  # ✅ Stored
    }
}

# Step 3: Calculate Round 2 ONLY (differential)
differential_player = {
    'name': 'vid',
    'damage_given': 1447,  # 2775 - 1328 ✅
    # ❌ BUG: objective_stats NOT created!
    # ❌ BUG: time_played_minutes lost!
}

# Should be:
differential_player = {
    'name': 'vid',
    'damage_given': 1447,
    'objective_stats': {
        'time_played_minutes': 3.8  # 7.7 - 3.9 ✅
    }
}
```

---

## ✅ THE FIX

### What We Changed

**Added to `calculate_round_2_differential()`:**
```python
differential_player = {
    'objective_stats': {}  # ← ADDED THIS!
}

# Loop through all objective stats
for key in r2_obj:
    if key == 'time_played_minutes':
        r2_time = r2_obj.get('time_played_minutes', 0)
        r1_time = r1_obj.get('time_played_minutes', 0)
        differential_player['objective_stats']['time_played_minutes'] = max(0, r2_time - r1_time)
```

### Expected Result After Fix

```
BEFORE:
Round 1: time_played_minutes = 3.9 ✅
Round 2: time_played_minutes = 0.0 ❌

AFTER:
Round 1: time_played_minutes = 3.9 ✅
Round 2: time_played_minutes = 3.8 ✅ (7.7 - 3.9)
```

---

## 🎯 VERIFICATION NEEDED

### To Verify the Fix Works:

1. **Re-import October 2 stats** with fixed parser
2. **Check Round 2 time data:**
   ```sql
   SELECT COUNT(*) 
   FROM player_comprehensive_stats p
   JOIN sessions s ON p.session_id = s.id
   WHERE s.session_date LIKE '2025-10-02%'
   AND s.round_number = 2
   AND p.time_played_minutes = 0;
   ```
   **Expected:** 0 records (was 35)

3. **Recalculate vid's DPM:**
   ```sql
   SELECT 
       SUM(damage_given) as total_damage,
       SUM(time_played_minutes) as total_time,
       SUM(damage_given) / SUM(time_played_minutes) as correct_dpm
   FROM player_comprehensive_stats p
   JOIN sessions s ON p.session_id = s.id
   WHERE s.session_date LIKE '2025-10-02%'
   AND p.player_name = 'vid';
   ```
   **Expected:** ~290-300 DPM (not 514.88!)

---

## 📊 IMPACT PROJECTION

### Before Fix
```
vid's October 2 Stats:
  Total rounds: 18
  Rounds with time: 9 (50%)
  Recorded time: 60.5 min
  Total damage: 31,150
  Calculated DPM: 514.88 ❌ INFLATED
```

### After Fix
```
vid's October 2 Stats:
  Total rounds: 18
  Rounds with time: 18 (100%) ✅
  Recorded time: ~107 min (estimated)
  Total damage: 31,150
  Calculated DPM: ~291 ✅ CORRECT
```

### DPM Comparison
```
Bot's AVG(dpm):        302.53
Current SUM/SUM:       514.88 ❌ (missing R2 times)
Expected after fix:    ~291   ✅
Difference from bot:   ~11.5 (3.8%)
```

**Conclusion:** Bot's current DPM (302.53) is actually very close to the correct value (~291)! The fix will prove our calculations are sound.

---

## 🚀 NEXT STEPS

1. ✅ **Parser fix applied** - time preservation in Round 2
2. ⏳ **Re-import October 2** - verify fix works
3. ⏳ **Validate DPM calculations** - should be ~290-300
4. ⏳ **Re-import full database** - apply fix to all 3,238 files
5. ⏳ **Update bot query** - consider using SUM/SUM instead of AVG

---

**Created:** October 3, 2025  
**Analysis Tool:** `dev/comprehensive_time_analysis.py`  
**Sessions Analyzed:** 18 from October 2, 2025  
**Player Records:** 85 total (34 R1, 51 R2)
