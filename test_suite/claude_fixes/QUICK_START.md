# 🚀 QUICK START: Fix Your Bot Stats

**Problem**: Bot showing wrong stats after recent changes  
**Solution**: Follow these 3 steps to diagnose and fix

---

## ⚡ STEP 1: Run Diagnostics (5 minutes)

```bash
# Test if parser is working correctly
python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt
```

**Look for:**
- ✅ Are kills/deaths/DPM showing reasonable numbers?
- ❌ Is `objective_stats` EMPTY or MISSING?
- ❌ Are any fields showing "MISSING"?

---

## ⚡ STEP 2: Check The Bug (2 minutes)

**Most likely bug location**: `ultimate_bot.py` line 9646

```python
# THIS IS WRONG:
accuracy = (kills / bullets_fired * 100) if bullets_fired > 0 else 0.0
```

**Should be:**

```python
# Option 1: Use parser's accuracy
accuracy = player.get('accuracy', 0.0)

# Option 2: Calculate correctly
hits = player.get('hits_total', 0)
shots = player.get('shots_total', 0)
accuracy = (hits / shots * 100) if shots > 0 else 0.0
```

**Also check DPM** (line 9637):

```python
# Instead of just taking from parser:
dpm = player.get("dpm", 0.0)

# Calculate it yourself to be sure:
time_seconds = player.get("time_played_seconds", 0)
damage_given = player.get("damage_given", 0)
dpm = (damage_given * 60) / time_seconds if time_seconds > 0 else 0.0
```

---

## ⚡ STEP 3: Feed To AI Agent (5 minutes)

Copy this prompt to your AI agent in VS Code:

```
CONTEXT:
My Discord bot for ET:Legacy stats was working yesterday, but now shows wrong statistics.
I've run diagnostics and found the issue is likely in the stats calculation/insertion.

FILES TO CHECK:
1. ultimate_bot.py (lines 9626-9790) - _insert_player_stats function
2. community_stats_parser.py - if it exists in my project

KNOWN ISSUES:
1. Line 9646: Efficiency calculation is wrong (kills/bullets instead of hits/shots)
2. Line 9637: DPM might not be calculated correctly
3. Need to verify parser field structure hasn't changed

TASKS:
1. Fix efficiency calculation at line 9646
2. Verify DPM calculation at line 9637  
3. Check if obj_stats.get() calls are finding the right fields
4. Test with: python debug_stats.py <stats_file>

EXPECTED BEHAVIOR:
- DPM = (damage_given * 60) / time_played_seconds
- Efficiency = kills / (kills + deaths) * 100
- Accuracy = hits / shots * 100
- All objective stats (gibs, revives, etc.) should show correct values

See DIAGNOSTIC_REPORT.md for full details.
```

---

## 📁 FILES PROVIDED

You have 3 files to help debug:

1. **`debug_stats.py`** - Tests parser output on a stats file
2. **`check_fields.py`** - Checks field mappings
3. **`DIAGNOSTIC_REPORT.md`** - Full diagnostic details (this file)

---

## 🎯 MOST LIKELY FIX

**90% chance the bug is here:**

**File**: `ultimate_bot.py`  
**Line**: ~9646

**Change from:**
```python
bullets_fired = obj_stats.get("bullets_fired", 0)
accuracy = (kills / bullets_fired * 100) if bullets_fired > 0 else 0.0
```

**To:**
```python
# Use parser's accuracy instead
accuracy = player.get('accuracy', 0.0)
```

**Or if you want efficiency:**
```python
efficiency = (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0
```

---

## ✅ TEST AFTER FIXING

```bash
# 1. Run parser test
python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt

# 2. Test bot commands
!stats <player_name>
!leaderboard
!last_session

# 3. Verify values make sense
- DPM should be 50-300 range typically
- Efficiency should be 30-70% range  
- Gibs should be small numbers (0-10)
- Kills/deaths should match what you remember
```

---

## 🔧 IF STILL BROKEN

1. Compare with working version from last chat:
   https://claude.ai/chat/730f738f-6f5f-4476-86c2-1b4b11e216bc

2. Check what changed:
   ```bash
   diff working_bot.py current_bot.py > changes.diff
   ```

3. Look for changes in:
   - `_insert_player_stats`
   - Any `!stats` commands
   - SQL queries

---

## 💡 PREVENTION

To avoid this in the future:

1. **Add tests** - Test stats calculations after every change
2. **Add logging** - Log calculated values to verify correctness  
3. **Version control** - Git commit before making changes
4. **Document formulas** - Comment what each calculation does

---

**Time to fix**: ~10-15 minutes  
**Difficulty**: Easy (if bug is where we think it is)  
**Impact**: HIGH (fixes all broken stats)

Good luck! 🚀
