# 🔍 STATS BUG DIAGNOSTIC REPORT

**Date**: 2025-10-30  
**Issue**: Bot producing wrong stats after recent changes  
**Working Version**: Check last chat - https://claude.ai/chat/730f738f-6f5f-4476-86c2-1b4b11e216bc

---

## 📋 SUMMARY

Your Discord bot was working correctly for multi-column game statistics visualization, but after recent changes it's now showing wrong stats. The field mapping checks show no obvious issues, so the problem is likely in:

1. **SQL queries** in display commands
2. **Field calculations** (DPM, accuracy, efficiency)  
3. **Database vs. Parser** field name mismatches
4. **Recent code changes** not properly tested

---

## 🔧 DIAGNOSTIC STEPS

### Step 1: Test the Parser Directly

Run this command to see if the parser is working correctly:

```bash
python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt
```

**What to look for:**
- ✅ Does `objective_stats` exist for each player?
- ✅ Are gibs, kills, deaths, DPM showing correct values?
- ✅ Are weapon stats present?
- ❌ Any fields showing as MISSING?

### Step 2: Check Database Insertion

The bot inserts stats in `_insert_player_stats()` (lines 9626-9790). Key areas to check:

**Potential Issues:**

1. **DPM Calculation** (line 9637):
   ```python
   dpm = player.get("dpm", 0.0)
   ```
   - Is the parser calculating DPM correctly?
   - Should it be recalculated from damage_given / time?

2. **Time Fields** (lines 9633-9634):
   ```python
   time_seconds = player.get("time_played_seconds", 0)
   time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0
   ```
   - Are these coming from the right place?
   - Check if parser returns these fields

3. **Efficiency** (lines 9644-9646):
   ```python
   bullets_fired = obj_stats.get("bullets_fired", 0)
   accuracy = (kills / bullets_fired * 100) if bullets_fired > 0 else 0.0
   ```
   - This doesn't look right! Accuracy should be hits/shots, not kills/bullets
   - This might be the bug!

4. **Objective Stats** (lines 9667-9703):
   - All pulling from `obj_stats.get(...)`
   - If `objective_stats` is empty, all these will be 0

### Step 3: Check Display Commands

The issue might not be in parsing but in **how stats are displayed**. Check these commands:

1. `!stats <player>` - Shows player statistics
2. `!last_session` - Shows session summary
3. `!leaderboard` - Shows top players

**Common display issues:**
- SQL queries selecting wrong columns
- Field names don't match database column names
- Calculations done incorrectly in display code

---

## 🎯 MOST LIKELY CAUSES

### Cause #1: Efficiency Calculation Bug (HIGH PRIORITY)

**Location**: `ultimate_bot.py` line 9646

```python
# WRONG:
accuracy = (kills / bullets_fired * 100) if bullets_fired > 0 else 0.0
```

Should probably be:

```python
# CORRECT:
accuracy = (hits_total / shots_total * 100) if shots_total > 0 else 0.0
```

Or if you want efficiency:

```python
efficiency = (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0
```

### Cause #2: DPM Not Being Calculated

**Location**: `ultimate_bot.py` line 9637

The bot just takes DPM from the parser:

```python
dpm = player.get("dpm", 0.0)
```

But what if the parser isn't calculating it correctly? Try:

```python
# Recalculate DPM from raw data
time_seconds = player.get("time_played_seconds", 0)
damage_given = player.get("damage_given", 0)
if time_seconds > 0:
    dpm = (damage_given * 60) / time_seconds
else:
    dpm = 0.0
```

### Cause #3: Parser Field Structure Changed

The parser might have changed from:

```python
# OLD:
player = {
    'gibs': 5,
    'kills': 10,
    'deaths': 3
}
```

To:

```python
# NEW:
player = {
    'objective_stats': {
        'gibs': 5
    },
    'kills': 10,
    'deaths': 3
}
```

If this happened, the bot code needs to be updated to match.

---

## 🚀 ACTION PLAN FOR AI AGENT

### Priority 1: Fix Efficiency Calculation

**File**: `ultimate_bot.py`  
**Lines**: 9644-9646

**Current code:**
```python
bullets_fired = obj_stats.get("bullets_fired", 0)
accuracy = (kills / bullets_fired * 100) if bullets_fired > 0 else 0.0
```

**Should be:**
```python
# Use actual accuracy from parser or calculate correctly
accuracy = player.get('accuracy', 0.0)  # Trust the parser
# OR calculate efficiency if that's what you want:
efficiency = (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0
```

### Priority 2: Verify DPM Calculation

**File**: `ultimate_bot.py`  
**Line**: 9637

**Add logging to verify:**
```python
dpm_from_parser = player.get("dpm", 0.0)
time_seconds = player.get("time_played_seconds", 0)
damage_given = player.get("damage_given", 0)

# Recalculate to verify
if time_seconds > 0:
    dpm_calculated = (damage_given * 60) / time_seconds
else:
    dpm_calculated = 0.0

# Log if they don't match
if abs(dpm_from_parser - dpm_calculated) > 0.1:
    logger.warning(f"DPM mismatch for {player.get('name')}: "
                   f"parser={dpm_from_parser}, calculated={dpm_calculated}")

dpm = dpm_calculated  # Use calculated value
```

### Priority 3: Check Display Commands

Search for these commands and verify their SQL queries:

```bash
grep -n "def.*stats.*command" ultimate_bot.py
grep -n "SELECT.*FROM player_comprehensive_stats" ultimate_bot.py
```

Make sure column names match what's in the database.

---

## 📊 TESTING CHECKLIST

After making changes, test:

- [ ] `!stats <player>` - Shows correct K/D, DPM, gibs
- [ ] `!last_session` - Shows correct round stats
- [ ] `!leaderboard` - Shows correct rankings
- [ ] `!session_summary` - Shows correct aggregated stats
- [ ] Graphs show correct data

---

## 🔗 COMPARISON WITH WORKING VERSION

To compare with the working version:

1. Get the working `ultimate_bot.py` from last chat
2. Run diff between versions:
   ```bash
   diff -u working_bot.py current_bot.py > changes.diff
   ```
3. Look for changes in:
   - `_insert_player_stats`
   - `_import_stats_to_db`  
   - Any `!stats` or `!leaderboard` commands
   - Any SQL queries

---

## 📝 NOTES FOR AI AGENT

When fixing this issue:

1. **Don't guess** - Use the debug_stats.py script first to see actual data
2. **Compare versions** - Find what changed since it was working
3. **Check calculations** - Efficiency calculation looks wrong (line 9646)
4. **Test thoroughly** - One field bug can cascade to other stats
5. **Add logging** - Log DPM, efficiency calculations to verify

**Most likely fixes needed:**
- Fix efficiency calculation (line 9646)
- Verify DPM is calculated correctly (line 9637)
- Check if parser structure changed
- Verify SQL queries match database columns

---

## 🛠️ DEBUGGING COMMANDS

Run these to diagnose:

```bash
# 1. Test parser output
python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt

# 2. Check field mappings
python check_fields.py

# 3. Find insert function
grep -n "_insert_player_stats" ultimate_bot.py

# 4. Find display commands
grep -n "def.*stats" ultimate_bot.py

# 5. Check SQL queries
grep -n "SELECT.*player_comprehensive_stats" ultimate_bot.py | head -10
```

---

## ✅ SUCCESS CRITERIA

After fixing, verify:

1. DPM values match manual calculation: `(damage * 60) / seconds`
2. Efficiency = `kills / (kills + deaths) * 100`
3. Gibs, revives, objective stats all show correct values
4. Graphs display correct data
5. Rankings are logical (top players have best stats)

---

**Report generated**: 2025-10-30  
**Status**: Ready for AI agent review  
**Files to check**: `ultimate_bot.py`, `community_stats_parser.py`
