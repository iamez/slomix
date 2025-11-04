# FIELD MAPPING BUGS FOUND - November 3, 2025

## Executive Summary
Analysis of Oct 28 & 30 data revealed **65.9% accuracy rate** (34% of fields mismatched).
- **324 players analyzed**
- **38 sessions verified**
- **11,664 fields checked**
- **5 mismatched fields** requiring fixes

---

## Critical Bugs Found

### 1. **headshot_kills** - WRONG SOURCE FIELD
**Status**: ❌ Mismatch in R1 and R2

**Problem**:
- Importer uses: `player.get('headshots', 0)` ← WRONG
- Should use: `objective_stats.get('headshot_kills', 0)` ← CORRECT

**Evidence**:
```
File (endekk, etl_adlernest R1):
  objective_stats['headshot_kills'] = 2  ← Actual headshot KILLS
  player['headshots'] = 12              ← Total headshot HITS (all weapons)
  
Database stored: 12  ← WRONG! Stored weapon headshots instead of kill count

Example from parser test:
  player['headshots'] = 32              (sum of weapon headshots)
  objective_stats['headshot_kills'] = 6  (actual kills from headshots)
  → These are DIFFERENT stats!
```

**What they mean**:
- `player['headshots']`: Total hits to the head (doesn't mean kill)
- `objective_stats['headshot_kills']`: Kills that were caused by headshots

**Fix Location**: `dev/bulk_import_stats.py` line 390

---

### 2. **team_damage_received** - MISSING IN ROUND 2
**Status**: ✅ R1 works | ❌ R2 stores 0

**Problem**:
- Round 1: Correctly inserts from `objective_stats['team_damage_received']`
- Round 2: Database shows 0 when file has value

**Evidence**:
```
File (endekk, etl_adlernest):
  R1: team_damage_received = 0     → DB: 0     ✅ Match
  R2: team_damage_received = 53    → DB: 0     ❌ Mismatch!
```

**Hypothesis**: Round 2 differential calculation might be zeroing this field OR insert is failing silently

---

### 3. **time_dead_minutes** - MISSING IN ROUND 2
**Status**: ✅ R1 works | ❌ R2 stores 0.0

**Problem**:
- Round 1: Correctly inserts calculated time_dead_minutes
- Round 2: Database shows 0.0 when file has differential value

**Evidence**:
```
File (endekk, etl_adlernest):
  R1: time_dead_minutes = 1.8      → DB: 1.825   ✅ Match
  R2: time_dead_minutes = 0.7      → DB: 0.0     ❌ Mismatch!
       (cumulative 2.5, diff = 0.7)
```

**Hypothesis**: Round 2 differential may not be calculating time fields correctly

---

### 4. **kd_ratio** - WRONG IN ROUND 2
**Status**: ✅ R1 works | ❌ R2 mismatch

**Problem**:
- Round 1: kd_ratio matches
- Round 2: Database recalculates differently than file

**Evidence**:
```
File (endekk, etl_adlernest):
  R1: kd_ratio = 1.2     → DB: 1.2    ✅ Match
  R2: kd_ratio = 1.2     → DB: 1.25   ❌ Mismatch
       (cumulative shows 1.2, diff calculated as 0)
```

**Note**: DB recalculates as `kills / deaths`. Need to verify if parser's R2 differential is correct.

---

### 5. **dpm** (Damage Per Minute) - EXPECTED MISMATCH
**Status**: ⚠️ Recalculated field (not a bug)

**Problem**: File shows 0.0, DB calculates from `(damage_given * 60) / time_played_seconds`

**Evidence**:
```
File (endekk, etl_adlernest):
  R1: dpm = 0.0          → DB: 373.65   (calculated)
  R2: dpm = 0.0          → DB: 279.73   (calculated)
```

**Conclusion**: This is EXPECTED BEHAVIOR - parser doesn't calculate DPM, database does.

---

## Pattern Analysis

### Round 1 Issues (3-6 mismatches per player):
- ❌ **headshot_kills** using wrong source field
- ⚠️ **dpm** recalculated (expected)
- Minor rounding differences in calculated fields

### Round 2 Issues (14-23 mismatches per player):
- ❌ **headshot_kills** using wrong source field
- ❌ **team_damage_received** = 0 (should have value)
- ❌ **time_dead_minutes** = 0.0 (should have value)  
- ❌ **kd_ratio** calculated differently
- ⚠️ **dpm** recalculated (expected)
- **Many more fields likely affected by R2 differential calculation**

**Root Cause**: Round 2 differential calculation is failing to preserve/calculate certain fields correctly.

---

## Fields Marked as "missing_in_db" (11 fields)

These fields exist in parser output but NOT in database schema:
1. death_spree
2. denied_playtime (R2 shows 0 even though R1 had value)
3. full_selfkills
4. time_axis
5. (and 7 more)

**Note**: These may be intentionally excluded or pending schema additions.

---

## Recommended Actions

### Priority 1 - CRITICAL FIX:
1. **Fix headshot_kills source**
   - Change: `player.get('headshots', 0)`
   - To: `objective_stats.get('headshot_kills', 0)`
   - Location: `dev/bulk_import_stats.py` line 390

### Priority 2 - INVESTIGATE:
2. **Debug Round 2 differential calculation**
   - Check: `bot/community_stats_parser.py` Round 2 logic
   - Test: Does it preserve all objective_stats fields?
   - Verify: time_dead_minutes calculation
   - Verify: team_damage_received preservation

3. **Verify kd_ratio calculation**
   - File shows differential as 0
   - DB recalculates and gets different value
   - Which one is correct?

### Priority 3 - VALIDATE:
4. **Run comprehensive validator**
   - Test BEFORE fixing
   - Test AFTER fixing
   - Compare: Old DB vs New DB vs Raw files
   - Document: Which fields now match 100%

---

## Testing Strategy

1. **Create test script**: Compare ONE file (R1 + R2) against database
2. **Document current state**: All mismatches with specific values
3. **Apply fixes ONE AT A TIME**
4. **Re-test after each fix**
5. **Document improvements**

**DO NOT** change multiple fields at once - we need to track which fix resolves which mismatch.

---

## Bot Reference (CORRECT Implementation)

The bot's `ultimate_bot.py` line 3809 shows the CORRECT way:
```python
obj_stats.get("headshot_kills", 0),  # ✅ FIX: was player.get("headshots")
```

The bot even has a comment saying it was PREVIOUSLY WRONG and got fixed!
But `dev/bulk_import_stats.py` still has the OLD BUG.

---

## Questions to Answer Before Fixing

1. **headshot_kills**: Confirmed different stats - fix is clear ✅
2. **team_damage_received**: Why is R2 showing 0? Parser bug or insert bug?
3. **time_dead_minutes**: Why is R2 showing 0? Calculation or insert?
4. **kd_ratio**: Should we trust parser's differential or DB's recalculation?
5. **Round 2 pattern**: Are there OTHER fields silently failing in R2?

---

## Data Integrity Impact

**Current state**: ~34% of fields don't match raw files
- Wrong stats displayed in bot commands
- Leaderboards showing inflated headshot counts
- Round 2 data particularly unreliable
- User trust in stats accuracy compromised

**After fixes**: Should achieve 90%+ accuracy (remaining 10% being expected recalculations like DPM)

---

Generated: 2025-11-03
Source: field_analysis_log.json (Oct 28 & 30 data)
Analysis: complete_field_mapping_presentation.html
