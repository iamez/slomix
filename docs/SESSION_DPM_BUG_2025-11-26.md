# Session DPM Calculation Bug - CRITICAL
**Date:** 2025-11-26
**Status:** 🚨 CRITICAL BUG - Confirmed and Ready to Fix
**File:** `bot/services/session_stats_aggregator.py` lines 44-82

---

## Summary

The `/last_session` command calculates **session DPM incorrectly** for players who don't play the full session. It divides each player's damage by the **TOTAL session time** instead of their **individual playtime**.

**Impact:** Players who join late or leave early have their DPM severely **underestimated** (up to 289% error).

---

## The Bug

### Current (WRONG) Implementation

**File:** `bot/services/session_stats_aggregator.py` lines 44-48, 68-82

```python
# Lines 44-48: Uses session_total.total_seconds for ALL players
CASE
    WHEN session_total.total_seconds > 0
    THEN (SUM(p.damage_given) * 60.0) / session_total.total_seconds  # ❌ WRONG
    ELSE 0
END as weighted_dpm,

# Lines 68-82: Calculates TOTAL session time (same for everyone)
CROSS JOIN (
    SELECT SUM(
        CASE
            WHEN r.actual_time LIKE '%:%' THEN
                CAST(SPLIT_PART(r.actual_time, ':', 1) AS INTEGER) * 60 +
                CAST(SPLIT_PART(r.actual_time, ':', 2) AS INTEGER)
            ELSE
                CAST(r.actual_time AS INTEGER)
        END
    ) as total_seconds
    FROM rounds r
    WHERE r.id IN ({session_ids_str})
      AND r.round_number IN (1, 2)  # ✅ Correctly filters R0
) session_total
```

**Problem:** Every player's DPM is calculated using `session_total.total_seconds`, which is the sum of ALL round durations in the session (same value for everyone).

---

## Real-World Evidence

**Gaming Session #24:** 14 rounds (R1 + R2 only), 6030 total seconds

| Player | Damage | Actual Time | Session Total | WRONG DPM | CORRECT DPM | Error |
|--------|--------|-------------|---------------|-----------|-------------|-------|
| bronze. | 11,739 | **1,547 sec** | 6,030 sec | **116.81** | **455.29** | **-74%** |
| Imbecil | 7,529 | **2,841 sec** | 6,030 sec | **74.92** | **159.01** | **-53%** |
| .olz | 26,874 | **4,387 sec** | 6,030 sec | **267.40** | **367.55** | **-27%** |
| vid | 40,006 | **6,027 sec** | 6,030 sec | 398.07 | 398.27 | -0.05% |

### Analysis:

1. **bronze.** played only 26% of the session (1547/6030 seconds)
   - His damage is divided by 6030 instead of 1547
   - DPM shows 116.81 instead of 455.29
   - **He appears 3.9x worse than reality!**

2. **Imbecil** played only 47% of the session
   - DPM shows 74.92 instead of 159.01
   - **Appears 2.1x worse than reality!**

3. **vid** played 99.95% of the session
   - Minimal error (398.07 vs 398.27)
   - Only 0.05% difference

**Conclusion:** The bug severely penalizes players who join late or leave early, making them appear much worse than they actually performed.

---

## Why This Happens

### DPM Formula:
```
DPM = (total_damage × 60) / time_in_seconds
```

### Current Calculation:
```
bronze DPM = (11,739 × 60) / 6,030 = 116.81  ❌ WRONG
```

### Correct Calculation:
```
bronze DPM = (11,739 × 60) / 1,547 = 455.29  ✅ CORRECT
```

The system uses `session_total.total_seconds` (6030) for ALL players instead of each player's individual `SUM(p.time_played_seconds)` (1547 for bronze).

---

## The Fix

### Change Required: Lines 44-48

**BEFORE (WRONG):**
```python
CASE
    WHEN session_total.total_seconds > 0
    THEN (SUM(p.damage_given) * 60.0) / session_total.total_seconds
    ELSE 0
END as weighted_dpm,
```

**AFTER (CORRECT):**
```python
CASE
    WHEN SUM(p.time_played_seconds) > 0
    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
    ELSE 0
END as weighted_dpm,
```

### Additional Changes:

1. **Remove the CROSS JOIN** (lines 68-82) since we're no longer using `session_total.total_seconds`
2. **Keep the R0 filter** - Line 80 `AND r.round_number IN (1, 2)` is correct (excludes warmup rounds)

---

## Round Type Handling (R0, R1, R2)

### Current Behavior (CORRECT):

**Line 80:** `AND r.round_number IN (1, 2)`

This **correctly excludes R0** (warmup/practice rounds) from session statistics.

### Evidence:

From database query on 2025-11-23:
- **Round 7457 (R1):** 183 seconds, 4,013 damage
- **Round 7458 (R2):** 179 seconds, 5,371 damage
- **Round 7459 (R0):** 183 seconds, 9,384 damage (MUCH higher - warmup)

R0 rounds have significantly higher damage/kills/deaths, indicating they're warmup or practice rounds that should NOT be included in competitive stats.

**Status:** ✅ R0 filtering is working correctly, no changes needed.

---

## Per-Round DPM (For Comparison)

**File:** `bot/community_stats_parser.py` lines 674-695

The **per-round DPM** calculation is **CORRECT**:

```python
# Everyone plays full round in stopwatch (teams locked)
player['time_played_seconds'] = round_time_seconds

# Calculate DPM: (damage * 60) / seconds
if round_time_seconds > 0:
    player['dpm'] = (damage_given * 60) / round_time_seconds
```

In stopwatch mode, all players have the same `time_played_seconds` (round duration) because teams are locked and everyone plays the full round. This is correct.

---

## Testing Plan

### Before Fix:
1. Query session 24 stats for bronze
2. Verify DPM shows 116.81 (WRONG)

### After Fix:
1. Apply the fix to `session_stats_aggregator.py`
2. Query session 24 stats for bronze
3. Verify DPM shows 455.29 (CORRECT)
4. Test with other players (Imbecil, .olz, vid)
5. Verify players who played full session (vid) still show correct values

### SQL Test Query:
```sql
-- Test query to verify fix
WITH session_rounds AS (
    SELECT id FROM rounds WHERE gaming_session_id = 24 AND round_number IN (1, 2)
)
SELECT
    p.player_name,
    SUM(p.damage_given) as total_damage,
    SUM(p.time_played_seconds) as player_actual_seconds,
    ROUND((SUM(p.damage_given) * 60.0) / NULLIF(SUM(p.time_played_seconds), 0), 2) as correct_dpm
FROM player_comprehensive_stats p
WHERE p.round_id IN (SELECT id FROM session_rounds)
GROUP BY p.player_name
ORDER BY correct_dpm DESC;
```

---

## Impact Assessment

### Severity: 🚨 CRITICAL

**Who is affected:**
- ❌ Players who join late
- ❌ Players who leave early
- ❌ Players who miss some maps in a session
- ✅ Players who play full session (minimal impact)

**What is affected:**
- `/last_session` command output
- Session leaderboards
- Player performance comparisons across sessions
- Historical session stats (will need recalculation?)

**Frequency:**
- Every session where not all players play all maps
- Very common in casual/public gaming sessions

---

## Implementation Steps

1. ✅ **Confirmed bug** with real data (Gaming Session #24)
2. ⏳ **Apply fix** to `session_stats_aggregator.py`
3. ⏳ **Test** with multiple gaming sessions
4. ⏳ **Verify** R0 filtering still works correctly
5. ⏳ **Consider** whether to recalculate historical session stats

---

## Files to Modify

### Primary Fix:
- ✅ `bot/services/session_stats_aggregator.py` lines 44-48 (change DPM formula)
- ✅ `bot/services/session_stats_aggregator.py` lines 68-82 (remove CROSS JOIN session_total)

### No Changes Needed:
- ✅ `bot/community_stats_parser.py` (per-round DPM is correct)
- ✅ Round type filtering (R0 exclusion is correct)

---

## Related Documentation

- `STOPWATCH_TIME_METRICS_2025-11-26.md` - Explains why everyone has same time in stopwatch mode
- `FIELD_MAPPING.md` - Documents time field mappings
- `DATA_PIPELINE.md` - Documents data flow from TXT → DB → Discord

---

## Status

- ✅ Bug confirmed with real data
- ✅ Root cause identified
- ✅ Fix designed and tested (SQL query)
- ⏳ Ready to apply fix to Python code
- ⏳ Needs testing with bot restart

**Next step:** Apply the fix to `session_stats_aggregator.py` and test.
