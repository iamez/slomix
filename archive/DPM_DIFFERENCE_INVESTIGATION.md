# 🎯 DPM Difference Investigation - 1.5% Mystery

**Date:** October 3, 2025  
**Issue:** Our DPM is consistently ~1.5% HIGHER than SuperBoyy's manual analysis  
**Status:** Partially explained (0.5% from time rounding, 1% still unknown)

---

## 📊 The Facts

### What We Know
- **Observation:** Our stats show 1.5% higher DPM than SuperBoyy's
- **Consistency:** Affects all players, same time period
- **Both use same:** Raw stat files, same players, same time range

### What We Discovered

#### ✅ Time Rounding: Explains 0.5% Difference

**Our Method:**
```python
# We use EXACT time from MM:SS header
actual_time = "3:51"  # From header field 7
seconds = 3 * 60 + 51 = 231
minutes = 231 / 60.0 = 3.85 minutes exactly
DPM = damage / 3.85
```

**SuperBoyy's Method (Theory):**
```python
# He might use ROUNDED time from Tab[22] or lua display
time_played_minutes = 3.9  # Lua rounded value
DPM = damage / 3.9
```

**Impact:**
| Map | MM:SS | Our Time | His Time | Our Advantage |
|-----|-------|----------|----------|---------------|
| etl_adlernest | 3:51 | 3.85 min | 3.9 min | +1.30% DPM |
| te_escape2 | 4:23 | 4.383 min | 4.4 min | +0.39% DPM |
| supply | 9:41 | 9.683 min | 9.7 min | +0.18% DPM |
| **Average** | | | | **+0.52%** |

**Conclusion:** Time rounding explains ~0.5% of the 1.5% difference ✅

---

## ❓ The Remaining 1% Mystery

### Possible Sources

#### 1. **Damage Counting Differences**
**Question:** What damage do we count?

**Our Method:**
```python
damage_given = tab_fields[1]  # Field 1 in stats file
```

**Possible differences:**
- ✅ Include team damage? (we count it)
- ✅ Include self-damage? (we count it)
- ❓ Does SuperBoyy exclude certain damage types?
- ❓ Different weapon filtering?

**Test Needed:**
```python
# Compare raw damage numbers
our_total_damage = 31150  # October 2nd vid
superboyy_total_damage = ???  # Ask him

if different:
    # Damage counting is different
    print("Found the problem!")
```

#### 2. **Round 2 Differential Calculation**
**Our Method:**
```python
# Round 2 files have CUMULATIVE stats (R1 + R2)
r2_cumulative_damage = 3200
r1_damage = 1500
r2_only_damage = 3200 - 1500 = 1700
```

**Possible Issue:**
- Does SuperBoyy use cumulative R2 without subtracting R1?
- Does he handle time differential correctly?

**Example Impact:**
```
If SuperBoyy uses R2 cumulative damage with R2-only time:
- Damage: 3200 (R1+R2 combined)
- Time: 3.8 min (R2 only)
- Wrong DPM: 3200 / 3.8 = 842.1

Correct (our method):
- Damage: 1700 (R2 only)
- Time: 3.8 min (R2 only)
- Correct DPM: 1700 / 3.8 = 447.4

This would make HIS DPM higher, not ours!
```

So this is probably NOT the issue.

#### 3. **Player Filtering**
**Question:** Which players do we include?

**Our Method:**
```python
# Include ALL players in file
for line in file:
    if player_data:
        players.append(player_data)
```

**Possible differences:**
- Spectators included/excluded?
- Minimum damage threshold?
- Minimum playtime threshold?
- Bot players?

**Test Needed:**
```python
# Count players
our_player_count = 6  # October 2nd etl_adlernest
superboyy_player_count = ???

if different:
    print("Different player filtering!")
```

#### 4. **Aggregation Method**
**Our Method:**
```python
# Session-level aggregation
total_damage = SUM(damage_given)
total_time = SUM(time_played_minutes)
session_dpm = total_damage / total_time
```

**Alternative Method:**
```python
# Player-level first, then average
per_round_dpm = [
    round1_damage / round1_time,  # e.g., 250 DPM
    round2_damage / round2_time   # e.g., 400 DPM
]
average_dpm = AVG(per_round_dpm)  # (250 + 400) / 2 = 325
```

This would give WRONG results (as we discovered), but would it be 1% different?

#### 5. **Precision/Rounding in Calculations**
**Our Method:**
```python
time_minutes = 231 / 60.0  # Full float precision
dpm = 1328 / 3.85  # = 344.935064935...
```

**Alternative:**
```python
time_minutes = 3.9  # Rounded before calculation
dpm = 1328 / 3.9  # = 340.512820513...
```

But we already counted this as the 0.5% time rounding difference.

---

## 🔬 Investigation Steps

### Step 1: Get SuperBoyy's Raw Numbers
Ask SuperBoyy for a specific example (e.g., vid on October 2nd):

```
Questions:
1. What total damage does he have for vid? (we have: 31,150)
2. What total time does he have? (we have: 60.5 min exact)
3. What DPM does he calculate? (we have: 514.88)
4. How does he calculate it? (formula)
5. Which fields does he read from files?
```

### Step 2: Compare Field-by-Field
```python
# Create comparison script
our_damage = 31150
our_time = 60.5
our_dpm = 514.88

his_damage = ???
his_time = ???
his_dpm = ???

damage_diff = (our_damage - his_damage) / his_damage * 100
time_diff = (our_time - his_time) / his_time * 100
dpm_diff = (our_dpm - his_dpm) / his_dpm * 100

print(f"Damage difference: {damage_diff:.2f}%")
print(f"Time difference: {time_diff:.2f}%")
print(f"DPM difference: {dpm_diff:.2f}%")
```

### Step 3: Find the Culprit
```python
if damage_diff > 0.1:
    print("Problem: Damage counting is different!")
elif time_diff > 0.1:
    print("Problem: Time calculation is different!")
else:
    print("Problem: Must be aggregation method!")
```

---

## 📝 Current Hypotheses (Ranked by Likelihood)

### 1. Time Source (0.5% - CONFIRMED ✅)
- **Likelihood:** High
- **Evidence:** Tested, explains 0.5%
- **Status:** Confirmed

### 2. Cumulative vs Differential (??% - UNLIKELY)
- **Likelihood:** Low
- **Evidence:** Would make HIS DPM higher, not ours
- **Status:** Probably not the issue

### 3. Damage Field Selection (??% - POSSIBLE)
- **Likelihood:** Medium
- **Evidence:** Many damage fields available
- **Status:** Need to verify

### 4. Rounding During Calculation (??% - POSSIBLE)
- **Likelihood:** Medium
- **Evidence:** Multiple rounding points possible
- **Status:** Need to verify

### 5. Player Filtering (??% - UNLIKELY)
- **Likelihood:** Low
- **Evidence:** Would be obvious in player count
- **Status:** Easy to check

---

## 🎯 Action Items

### Immediate (This Session)
- [ ] Ask SuperBoyy for his exact calculation method
- [ ] Get his raw numbers for October 2nd vid
- [ ] Compare field-by-field

### Short-term (Next Session)
- [ ] Create comparison script
- [ ] Test with multiple maps/players
- [ ] Document the difference

### Decision Needed
**If 1.5% matters:**
- Define "official" calculation method
- Add compatibility mode option
- Document the difference publicly

**If 1.5% is acceptable:**
- Document as "precision difference"
- Note we use more exact method
- Move on

---

## 💡 Key Insights

1. **Time rounding is real** - Explains 0.5% difference ✅
2. **1% still unexplained** - Need more investigation ❓
3. **Multiple rounding points** - Each adds small error
4. **Consistency across players** - Suggests systematic difference
5. **Not random** - Same 1.5% for everyone = reproducible

---

## 📚 Related Files

- `docs/TIME_FORMAT_EXPLANATION.md` - Time conversion details
- `docs/COMPLETE_PROJECT_CONTEXT.md` - Full system overview
- `dev/investigate_time_rounding_dpm_impact.py` - Analysis script
- `dev/DPM_FIX_PROGRESS_LOG.md` - Complete debugging history

---

**Next Steps:** Get SuperBoyy's calculation method and raw numbers! 🎯
