CRITICAL BUG REPORT: Round 2 Differential Calculation Issues
============================================================

Date: 2025-11-03
Status: 🚨 CRITICAL DATA ACCURACY ISSUE FOUND

## Issues Discovered

### 1. Headshot Discrepancies (Round 1)
**Status**: Consistently wrong across all sessions tested
**Severity**: HIGH - affects leaderboards and achievements

**Evidence**:
- Raw file: slomix.endekk has 32 headshots
- Database: shows only 6 headshots
- Ratio: Database shows ~1/4 to 1/5 of actual headshots

**Impact**: ALL Round 1 headshot data is incorrect (database shows 20-25% of actual value)

### 2. Round 2 Differential Calculation Confusion
**Status**: Parser behavior is inconsistent
**Severity**: CRITICAL - data integrity compromised

**Evidence from `check_r2_cumulative.py`**:
```
slomix.endekk: R1=31 kills, R2=16 kills → DIFFERENTIAL (R2 < R1) ❌
//^?/M.Demonslayer: R1=22 kills, R2=13 kills → DIFFERENTIAL (R2 < R1) ❌
slomix.carniee: R1=25 kills, R2=22 kills → DIFFERENTIAL (R2 < R1) ❌
//^?/M.rAzzdog: R1=7 kills, R2=10 kills → CUMULATIVE (R2 > R1) ✅
//^?/M.Gekku: R1=12 kills, R2=21 kills → CUMULATIVE (R2 > R1) ✅
slomix.Imbecil: R1=10 kills, R2=2 kills → DIFFERENTIAL (R2 < R1) ❌
```

**Analysis**:
- Parser logs show: "[OK] Successfully calculated Round 2-only stats"
- But results are INCONSISTENT (some players cumulative, some differential)
- This suggests parser's differential calculation is BROKEN

### 3. Database Differential Validation Failed
**Status**: Cumulative math doesn't add up
**Severity**: CRITICAL

**Evidence**:
```
❌ //^?/M.rAzzdog: Kills cumulative mismatch
   R1: 7 kills (raw)
   R2: 16 kills (DB differential)
   Expected: 7 + 16 = 23
   Actual R2 raw: 16 ← This should be 23+ if cumulative!
```

**Analysis**: The "R2 raw" value (16) is LESS than expected cumulative (23), meaning the parser ALREADY subtracted R1 when loading the R2 file, but did it WRONG!

## Root Cause Analysis

The parser (community_stats_parser.py) has a `calculate_round2_differential()` function that:
1. Detects when parsing a Round 2 file
2. Tries to find and subtract the corresponding Round 1 file
3. Returns "differential" stats (R2 only)

**Problems**:
1. Parser is doing differential calculation INCONSISTENTLY
2. Some players get correct differential, some get cumulative, some get incorrect values
3. Headshots are completely wrong even in Round 1 (separate bug)
4. Database insertion expects differential but receives mixed data

## Impact Assessment

### Affected Data:
- ✅ Round 1 kills, deaths, damage: CORRECT
- ❌ Round 1 headshots: WRONG (database shows ~20-25% of actual)
- ❌ Round 2 ALL STATS: INCONSISTENT/INCORRECT

### Affected Features:
- Leaderboards (headshots ranking incorrect)
- Achievements (headshot-based achievements broken)
- Round 2 statistics (all stats unreliable)
- Player comparisons involving Round 2 data
- Historical trends (Round 2 data corrupted)

## Recommended Fixes

### Priority 1: Disable Parser's Differential Calculation
**Action**: Remove or disable `calculate_round2_differential()` in parser
**Reason**: Parser should return RAW cumulative stats from .txt files
**Location**: `bot/community_stats_parser.py`, line ~370-420

### Priority 2: Fix Headshot Parsing
**Action**: Debug why headshots are consistently 4-5x too low
**Location**: Check `parse_stats_file()` headshot field extraction
**Test**: Manually verify headshot values in raw .txt vs parsed results

### Priority 3: Reliable Differential Calculator
**Action**: Use your `fixed_differential_calculator.py` AFTER parsing
**Reason**: Differential calculation should happen AFTER parsing, not during
**Process**:
1. Parse R1 file → get cumulative R1 stats
2. Parse R2 file → get cumulative (R1+R2) stats
3. Calculate differential: R2_diff = R2_cumulative - R1_cumulative

### Priority 4: Database Backfill
**Action**: Re-import all Round 2 data with corrected stats
**Scope**: All sessions since Nov 1 (at minimum)
**Test**: Validate cumulative math: R1 + R2_diff should equal R2_cumulative

## Testing Plan

1. **Fix parser headshots** → re-run Round 1 validation → should get 100% match
2. **Disable parser differential** → parse R2 files → should get cumulative stats
3. **Use fixed_differential_calculator** → calculate R2 diff → verify math
4. **Re-import data** → validate again → should get 100% match

## Validation Results

**Test Date**: 2025-11-03
**Test Set**: 3 gaming sessions from Nov 1, 2025
**Results**:
- Round 1 perfect matches: 0/3 (headshots wrong)
- Round 2 perfect matches: 0/3 (differential calculation broken)
- Total issues: 6 failed validations

**Conclusion**: Current database stats are NOT reliable for:
- Any headshot-based features
- Any Round 2 statistics

## Next Steps

1. Confirm headshot parsing bug location
2. Disable parser's differential calculation
3. Test with raw cumulative stats
4. Implement reliable differential calculator
5. Backfill database with corrected data
6. Re-run comprehensive validation
