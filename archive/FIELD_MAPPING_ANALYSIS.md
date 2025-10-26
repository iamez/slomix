# Field Mapping Analysis - Database vs Parser vs Importer

**Date:** October 4, 2025  
**Issue:** Bulk import failing because fields don't match between parser output and database schema

---

## 🔍 ACTUAL DATABASE SCHEMA

### `player_comprehensive_stats` TABLE (35 columns):
```
0: id (INTEGER) - Primary key
1: session_id (INTEGER) - FK to sessions
2: player_guid (TEXT)
3: player_name (TEXT)
4: clean_name (TEXT)
5: team (INTEGER)
6: kills (INTEGER)
7: deaths (INTEGER)
8: damage_given (INTEGER)
9: damage_received (INTEGER)
10: team_damage_given (INTEGER)
11: team_damage_received (INTEGER)
12: gibs (INTEGER)
13: self_kills (INTEGER)
14: team_kills (INTEGER)
15: team_gibs (INTEGER)
16: time_axis (INTEGER)
17: time_allies (INTEGER)
18: time_played_seconds (INTEGER) ⭐
19: time_played_minutes (REAL)
20: xp (INTEGER)
21: killing_spree_best (INTEGER)
22: death_spree_worst (INTEGER)
23: kill_assists (INTEGER)
24: headshot_kills (INTEGER)
25: revives (INTEGER)
26: ammopacks (INTEGER)
27: healthpacks (INTEGER)
28: dpm (REAL)
29: kd_ratio (REAL)
30: efficiency (REAL)
31: award_accuracy (INTEGER)
32: award_damage (INTEGER)
33: award_kills (INTEGER)
34: award_experience (INTEGER)
```

### `player_objective_stats` TABLE (26 columns):
```
0: id (INTEGER)
1: session_id (INTEGER)
2: player_guid (TEXT)
3: objectives_completed (INTEGER)
4: objectives_destroyed (INTEGER)
5: objectives_captured (INTEGER)
6: objectives_defended (INTEGER)
7: objectives_stolen (INTEGER)
8: objectives_returned (INTEGER)
9: dynamites_planted (INTEGER)
10: dynamites_defused (INTEGER)
11: landmines_planted (INTEGER)
12: landmines_spotted (INTEGER)
13: revives (INTEGER) ⚠️ Duplicate with comprehensive_stats
14: ammopacks (INTEGER) ⚠️ Duplicate
15: healthpacks (INTEGER) ⚠️ Duplicate
16: times_revived (INTEGER)
17: kill_assists (INTEGER) ⚠️ Duplicate
18: constructions_built (INTEGER)
19: constructions_destroyed (INTEGER)
20: killing_spree_best (INTEGER) ⚠️ Duplicate
21: death_spree_worst (INTEGER) ⚠️ Duplicate
22: kill_steals (INTEGER)
23: most_useful_kills (INTEGER)
24: useless_kills (INTEGER)
25: denied_playtime (INTEGER)
26: tank_meatshield (REAL)
```

---

## 📊 PARSER OUTPUT (from community_stats_parser.py)

### What `objective_stats` dictionary contains (38 fields):
```python
objective_stats = {
    # Fields 0-8: damage/gibs/team stats
    'damage_given': int,
    'damage_received': int,
    'team_damage_given': int,
    'team_damage_received': int,
    'gibs': int,
    'self_kills': int,
    'team_kills': int,
    'team_gibs': int,
    'time_played_percent': float,
    
    # Fields 9-19: XP, assists, objectives, dynamites, revives
    'xp': int,
    'killing_spree': int,
    'death_spree': int,
    'kill_assists': int,
    'kill_steals': int,
    'headshot_kills': int,
    'objectives_stolen': int,
    'objectives_returned': int,
    'dynamites_planted': int,
    'dynamites_defused': int,
    'times_revived': int,
    
    # Fields 20-36: bullets, DPM, time, K/D, multikills
    'bullets_fired': int,
    'dpm': float,
    'time_played_minutes': float,
    'tank_meatshield': float,
    'time_dead_ratio': float,
    'time_dead_minutes': float,
    'kd_ratio': float,
    'useful_kills': int,
    'denied_playtime': int,
    'multikill_2x': int,
    'multikill_3x': int,
    'multikill_4x': int,
    'multikill_5x': int,
    'multikill_6x': int,
    'useless_kills': int,
    'full_selfkills': int,
    
    # NEW fields (backwards compatible):
    'repairs_constructions': int,
    'revives_given': int,
}
```

---

## ❌ CURRENT BULK_IMPORT (BROKEN)

### What it tries to INSERT into `player_comprehensive_stats`:
```python
INSERT INTO player_comprehensive_stats (
    session_id, player_guid, player_name, clean_name, team,
    kills, deaths, damage_given, damage_received,
    headshot_kills, kd_ratio, dpm, time_played_minutes
)
```

### What it tries to INSERT into `player_objective_stats`:
```python
INSERT INTO player_objective_stats (
    session_id, player_guid,
    killing_spree_best, death_spree_worst,
    kill_assists, kill_steals,
    objectives_stolen, objectives_returned,
    dynamites_planted, dynamites_defused,
    times_revived, 
    tank_meatshield,
    most_useful_kills, useless_kills, denied_playtime,
    constructions_built, constructions_destroyed,
    revives, ammopacks, healthpacks,
    landmines_planted, landmines_spotted
)
```

---

## ⚠️ MISSING FIELDS

### Missing from `player_comprehensive_stats` INSERT:
- ❌ `team_damage_given`
- ❌ `team_damage_received`
- ❌ `gibs`
- ❌ `self_kills`
- ❌ `team_kills`
- ❌ `team_gibs`
- ❌ `time_axis`
- ❌ `time_allies`
- ❌ `time_played_seconds` ⚠️ **CRITICAL - This is the source of truth!**
- ❌ `xp`
- ❌ `killing_spree_best`
- ❌ `death_spree_worst`
- ❌ `kill_assists`
- ❌ `revives`
- ❌ `ammopacks`
- ❌ `healthpacks`
- ❌ `efficiency`
- ❌ All `award_*` fields

### Fields that DON'T exist in database but parser provides:
- `bullets_fired` - Parser provides, but NOT in any table!
- `time_dead_ratio` - Parser provides, but NOT in any table!
- `time_dead_minutes` - Parser provides, but NOT in any table!
- `multikill_*` fields - Parser provides, but NOT in any table!
- `full_selfkills` - Parser provides, but NOT in any table!
- `repairs_constructions` - Parser provides, but NOT in any table!
- `revives_given` - Parser provides, but NOT in any table!

---

## ✅ CORRECT MAPPING NEEDED

### For `player_comprehensive_stats` INSERT:
```python
INSERT INTO player_comprehensive_stats (
    session_id, player_guid, player_name, clean_name, team,
    kills, deaths,
    damage_given, damage_received,
    team_damage_given, team_damage_received,
    gibs, self_kills, team_kills, team_gibs,
    time_axis, time_allies,
    time_played_seconds,  # ⭐ CRITICAL - INTEGER from seconds conversion
    time_played_minutes,  # For backward compat
    xp,
    killing_spree_best, death_spree_worst,
    kill_assists,
    headshot_kills,
    revives, ammopacks, healthpacks,  # ⚠️ Parser doesn't provide these!
    dpm, kd_ratio,
    efficiency,  # ⚠️ Parser doesn't calculate this!
    award_accuracy, award_damage, award_kills, award_experience  # ⚠️ Not in parser!
)
```

### For `player_objective_stats` INSERT:
```python
INSERT INTO player_objective_stats (
    session_id, player_guid,
    objectives_completed,  # ⚠️ Parser doesn't provide!
    objectives_destroyed,  # ⚠️ Parser doesn't provide!
    objectives_captured,   # ⚠️ Parser doesn't provide!
    objectives_defended,   # ⚠️ Parser doesn't provide!
    objectives_stolen,     # ✅ Parser has this
    objectives_returned,   # ✅ Parser has this
    dynamites_planted,     # ✅ Parser has this
    dynamites_defused,     # ✅ Parser has this
    landmines_planted,     # ⚠️ Parser doesn't provide!
    landmines_spotted,     # ⚠️ Parser doesn't provide!
    revives,               # ⚠️ Parser has 'revives_given', not 'revives'
    ammopacks,             # ⚠️ Parser doesn't provide!
    healthpacks,           # ⚠️ Parser doesn't provide!
    times_revived,         # ✅ Parser has this
    kill_assists,          # ✅ Parser has this (duplicate)
    constructions_built,   # ⚠️ Parser has 'repairs_constructions'?
    constructions_destroyed, # ⚠️ Parser doesn't provide!
    killing_spree_best,    # ✅ Parser has this (duplicate)
    death_spree_worst,     # ✅ Parser has this (duplicate)
    kill_steals,           # ✅ Parser has this
    most_useful_kills,     # ✅ Parser has 'useful_kills'
    useless_kills,         # ✅ Parser has this
    denied_playtime,       # ✅ Parser has this
    tank_meatshield        # ✅ Parser has this
)
```

---

## 🚨 CRITICAL ISSUES

1. **Database schema has fields parser doesn't provide:**
   - `objectives_completed`, `objectives_destroyed`, `objectives_captured`, `objectives_defended`
   - `landmines_planted`, `landmines_spotted`
   - `ammopacks`, `healthpacks`, `revives` (medic stats)
   - `constructions_destroyed`
   - `efficiency`, `award_*` fields

2. **Parser provides fields database doesn't have:**
   - `bullets_fired` ⚠️ **This is being inserted into player_objective_stats causing the ERROR!**
   - `time_dead_ratio`, `time_dead_minutes`
   - `multikill_2x`, `multikill_3x`, `multikill_4x`, `multikill_5x`, `multikill_6x`
   - `full_selfkills`

3. **Duplicate fields across tables:**
   - `revives`, `ammopacks`, `healthpacks` in BOTH tables
   - `kill_assists` in BOTH tables
   - `killing_spree_best`, `death_spree_worst` in BOTH tables

---

## 💡 SOLUTION

**Option 1:** Add missing columns to database tables (bullets_fired, multikills, time_dead_*, etc.)  
**Option 2:** Only insert fields that exist in current schema (quick fix)  
**Option 3:** Review what c0rnp0rn3.lua ACTUALLY provides and rebuild schema to match

**Recommendation:** Check what fields c0rnp0rn3.lua ACTUALLY writes (line 273 in the Lua code) and match database 1:1.
