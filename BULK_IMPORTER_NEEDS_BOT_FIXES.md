# BULK IMPORTER FIELD MAPPING FIXES NEEDED

**Date:** November 3, 2025  
**Problem:** `dev/bulk_import_stats.py` has OLD BUGS that were already fixed in `bot/ultimate_bot.py` on Nov 2, 2025

---

## 📋 What We Know

### ✅ Bot is CORRECT (ultimate_bot.py)
- Fixed on November 2, 2025 (see BUGFIX_DATABASE_INSERTION.md)
- Uses `obj_stats.get("headshot_kills", 0)` - CORRECT
- Uses `obj_stats.get("useful_kills", 0)` - CORRECT  
- Uses `obj_stats.get("multikill_2x", 0)` - CORRECT
- Inserts ALL 51 fields correctly

### ❌ Bulk Importer is BROKEN (dev/bulk_import_stats.py)
- Still has OLD bugs from before Nov 2 fix
- Uses `player.get('headshots', 0)` - WRONG (line 390)
- Only inserts 28 fields instead of 51
- Missing 23+ fields entirely

---

## 🐛 Bugs in dev/bulk_import_stats.py

### Bug #1: headshot_kills uses WRONG source (Line 390)
```python
# CURRENT (WRONG):
headshot_kills = player.get('headshots', 0)

# SHOULD BE:
headshot_kills = objective_stats.get('headshot_kills', 0)
```

**Impact:** File shows 1 headshot_kill, DB shows 6 (using weapon headshots total instead)

---

### Bug #2: Only 28 fields inserted (Lines 448-456)

**Current INSERT has only 28 values:**
```python
INSERT INTO player_comprehensive_stats (
    round_id, round_date, map_name, round_number,
    player_guid, player_name, clean_name, team,
    kills, deaths, damage_given, damage_received,
    team_damage_given, team_damage_received,
    gibs, self_kills, team_kills, team_gibs, headshot_kills,
    time_played_seconds, time_played_minutes,
    xp, kd_ratio, dpm, efficiency,
    kill_assists, killing_spree_best, death_spree_worst
)
```

**Bot INSERT has 51 values** (lines 3790-3870 in ultimate_bot.py)

---

### Bug #3: Missing field extractions

These fields are NOT EVEN EXTRACTED from objective_stats:

❌ `bullets_fired` - Exists in objective_stats, not extracted
❌ `time_dead_minutes` - Exists in objective_stats, not extracted
❌ `time_dead_ratio` - Exists in objective_stats, not extracted
❌ `denied_playtime` - Exists in objective_stats, not extracted
❌ `tank_meatshield` - Exists in objective_stats, not extracted
❌ `useful_kills` - Exists in objective_stats, not extracted
❌ `useless_kills` - Exists in objective_stats, not extracted
❌ `multikill_2x` through `multikill_6x` - All missing
❌ `repairs_constructions` - Exists in objective_stats, not extracted
❌ `revives_given` - Exists in objective_stats, not extracted
❌ `accuracy` - Player dict has this, not extracted

**Result:** All these fields store 0 in database despite having values in raw files

---

### Bug #4: Fields extracted but NOT inserted

These are extracted but NOT in the INSERT statement:

✅ Extracted: `objectives_stolen` (line 427)
❌ Not inserted!

✅ Extracted: `objectives_returned` (line 428)
❌ Not inserted!

✅ Extracted: `dynamites_planted` (line 429)  
❌ Not inserted!

✅ Extracted: `dynamites_defused` (line 430)
❌ Not inserted!

✅ Extracted: `times_revived` (line 431)
❌ Not inserted!

---

## 📊 Evidence from HTML Analysis

From `interactive_field_mapping.html` (Oct 28 & 30 analysis):

**Total mismatches:** 3,972  
**Unique fields with mismatches:** 29

**Top mismatched fields:**
1. `dpm`: 324 mismatches (expected - DB recalculates)
2. `headshot_kills`: 308 mismatches ← BUG #1
3. `useful_kills`: 297 mismatches ← BUG #3
4. `team_damage_given`: 251 mismatches ← BUG #4
5. `team_damage_received`: 248 mismatches ← BUG #4
6. `multikill_2x`: 126 mismatches ← BUG #3

**Fields where DB is ALWAYS 0 (but file has values):**
- multikill_2x, multikill_3x
- repairs_constructions
- tank_meatshield
- team_damage_given, team_damage_received
- useful_kills

All because they're not extracted or not inserted!

---

## ✅ Solution: Copy Bot's Implementation

The bot's implementation (ultimate_bot.py lines 3790-3870) is CORRECT and TESTED.

### What to do:

1. **Copy the bot's field extraction logic**
   - Lines 3738-3788 in ultimate_bot.py
   - Extract ALL fields from objective_stats
   - Calculate time_dead_minutes, bullets_fired, etc.

2. **Copy the bot's INSERT statement**
   - Lines 3854-3895 in ultimate_bot.py  
   - ALL 51 columns listed
   - ALL 51 values provided

3. **Use bot's field name mappings**
   - `obj_stats.get("headshot_kills", 0)` not `player.get("headshots")`
   - `obj_stats.get("useful_kills", 0)` not `obj_stats.get("most_useful_kills")`
   - `obj_stats.get("multikill_2x", 0)` not `obj_stats.get("double_kills")`
   - `obj_stats.get("repairs_constructions", 0)` not `0`

---

## 📚 Related Documentation

1. **BUGFIX_DATABASE_INSERTION.md** - Bot fixes applied Nov 2, 2025
2. **PARSER_FIX_FIELD_COUNT.md** - Parser field mapping (36 TAB fields)
3. **BULK_IMPORT_FIX_COMPLETE.md** - Oct 4 bulk import fixes (partial)
4. **BOT_FIXES_COMPLETE_SUMMARY.md** - Oct 4 bot fixes (before Nov 2 field fix)
5. **interactive_field_mapping.html** - Oct 28 & 30 analysis showing mismatches

---

## 🎯 Implementation Plan

1. ✅ Read all docs (DONE - we found the issue!)
2. ⏳ Read bot's CORRECT implementation (ultimate_bot.py lines 3738-3895)
3. ⏳ Update bulk_import_stats.py to match bot exactly
4. ⏳ Test with ONE file to verify all fields populate correctly
5. ⏳ Re-import full database
6. ⏳ Verify with validator script (compare file vs DB)

---

## ⚠️ Critical Notes

- **DO NOT** invent new field mappings - copy from bot EXACTLY
- **DO NOT** skip fields thinking they're optional - user said "no stats are optional"
- **DO NOT** assume 0 is okay - if file has value, DB must have value
- **DO NOT** test without verification - always validate fields match

---

**Next Step:** Read bot/ultimate_bot.py lines 3738-3895 to see EXACT implementation
