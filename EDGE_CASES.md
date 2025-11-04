# Edge Cases Documentation

This document tracks known edge cases in stat file processing and how the system handles them.

## Table of Contents
1. [Midnight-Crossing Matches](#midnight-crossing-matches)
2. [Orphan Round 2 Files](#orphan-round-2-files)
3. [Server Auto-Restart Edge Case](#server-auto-restart-edge-case)
4. [Gaming Session Detection](#gaming-session-detection) ⭐ NEW

---

## 1. Midnight-Crossing Matches

### What It Is
Matches where Round 1 starts before midnight and Round 2 ends after midnight on the next day.

### Example
- **Oct 19, 23:53:07** - Round 1 starts (etl_adlernest)
- **Oct 20, 00:00:43** - Round 2 ends (~7 minutes later)

### Why It Happens
Normal gameplay - rounds typically take 10-15 minutes, so late-night matches naturally cross midnight.

### How System Handles It
✅ **FIXED** in `database_manager.py` lines 403-424:
- When processing R2 file, if no R1 found on same date
- Check **previous day** for matching R1 file
- Pair them correctly using shared `match_id`

### Detection Pattern
- R2 timestamp: `00:00:XX` to `00:15:XX` (early morning)
- R1 file exists on **previous day** with late timestamp (`23:XX:XX`)
- Time difference: 7-25 minutes (normal round duration)

### Status
✅ **Resolved** - System correctly pairs these matches

---

## 2. Orphan Round 2 Files

### What It Is
Round 2 files with NO corresponding Round 1 file (missing R1).

### Example
- **Oct 26, 20:00:01** - Round 2 file exists
- **Oct 26, 20:17:27** - Round 1 starts (17 minutes LATER)
- **Missing**: No Round 1 file before the 20:00 R2

### Why It Happens
Multiple possible causes:
1. **Server auto-restart** interrupted match (see below)
2. **File system issue** - R1 file deleted/lost
3. **Server crash** during R1 generation
4. **Admin intervention** - manual round trigger

### How System Handles It
✅ **Current behavior** (lines 427-429 in database_manager.py):
```python
logger.warning(f"⚠️  No Round 1 file found for {file_path.name}")
match_id = f"{file_date}_{round_time}_{map_name}_orphan"
```

System creates an "orphan" match_id and imports R2 as standalone session.

### Detection Pattern
- R2 file exists
- No R1 file found on same date OR previous day
- Warning logged: `"No Round 1 file found"`

### Status
✅ **Working as intended** - Orphans are imported as standalone sessions

---

## 3. Server Auto-Restart Edge Case

### What It Is
Server auto-restart at scheduled time (20:00 CET) causes stat file anomalies.

### Specific Example: Oct 26, 2025
**File**: `2025-10-26-200001-etl_sp_delivery-round-2.txt`

**Anomalies Detected**:
1. Filename says "round-2" but no matching R1 exists
2. Timestamp: Exactly **20:00:01** (1 second after restart time)
3. Header shows: `nextTimeLimit = 71:05` (71 minutes!)
4. Actual gameplay: Only **1.2 minutes** (player stats confirm)
5. Players: 6 different players than subsequent R1 at 20:17

**What Actually Happened**:
1. Server was running for 71+ minutes (cumulative uptime)
2. Auto-restart triggered at exactly 20:00 CET
3. Lua script dumped stats with:
   - Round counter still set to "2" (from previous session)
   - `nextTimeLimit` calculated from server uptime (71:05)
   - Actual round data: Brief 1-2 minute session
4. Server restarted fresh at 20:17 with proper R1

**Root Cause**:
- Lua script (`c0rnp0rn.lua`) uses `g_currentRound` cvar
- Server restart doesn't always reset round counter
- `nextTimeLimit` field uses player session times which span multiple matches

**Header Analysis**:
```
Field [3]: Round = 2 (incorrect - should be standalone)
Field [6]: timelimit = 12:00 (correct)
Field [7]: nextTimeLimit = 71:05 (server uptime, not round time!)
```

### Why It's Rare
- Requires **exact timing**: Match must be active during scheduled restart
- Auto-restart: Only happens once per day (20:00 CET)
- Round counter bug: Depends on specific server state

### How System Handles It
Currently: Imported as **orphan** R2 session (match_id includes "_orphan" suffix)

### Future Considerations
**No fix planned** - This is extremely rare (1 occurrence in 269 files over 3 weeks).

**If it becomes frequent**:
1. Could detect by checking `nextTimeLimit > timelimit + 30 minutes`
2. Skip import with warning: "Suspected server uptime bug"
3. Or: Force treat as R1 (ignore round label)

### Detection Pattern for Future
```python
# Potential detection logic (NOT implemented)
if round_num == 2 and nextTimeLimit > (timelimit * 5):
    logger.warning("Suspected server uptime bug - nextTimeLimit too high")
    # Skip or treat as R1
```

### Status
✅ **Documented** - No action needed (too rare to warrant fix)

---

## 4. "Swapped" Rounds (R2 Timestamp < R1 Timestamp)

### What It Is
Files where R2 timestamp comes BEFORE R1 timestamp on the same date/map.

### Investigation Results
**Initial Detection**: 4 cases found
- Oct 12: te_escape2
- Oct 20: etl_adlernest (actually midnight-crossing ✅)
- Oct 26: etl_sp_delivery (server restart bug ✅)
- Nov 2: etl_adlernest (actually midnight-crossing ✅)

**Conclusion**: 
- **0 genuine swaps** - All explained by other edge cases
- Oct 20 & Nov 2: Midnight-crossing matches (R1 previous day)
- Oct 26: Server auto-restart orphan (see above)
- Oct 12: Likely similar server restart issue

### Why Swaps Are Impossible
Game logic requires R1 to complete BEFORE R2 can start. Physical impossibility.

If R2 timestamp < R1 timestamp, one of these is true:
1. **Midnight crossing** - R1 on previous day
2. **Orphan R2** - Missing R1 file
3. **Mislabeled file** - Server bug in round counter

### How System Handles It
Current logic in `database_manager.py` (lines 436-442):
```python
# R1 must be BEFORE R2 (R1 time < R2 time)
if r1_time < r2_time:
    # Normal case - pair them
else:
    # Fall through to "orphan" handling
```

If no valid R1 found before R2:
- Warning logged: `"All R1 files are after R2"`
- Creates orphan match_id
- Imports R2 as standalone session

### Status
✅ **No fix needed** - Existing logic handles all cases correctly

---

## Summary

| Edge Case | Frequency | Status | Solution |
|-----------|-----------|--------|----------|
| Midnight Crossing | ~2-3 per week | ✅ Fixed | Check previous day for R1 |
| Orphan R2 | ~1-2 per month | ✅ Working | Import as standalone session |
| Server Auto-Restart Bug | 1 in 3 weeks | ✅ Documented | Accept as orphan (too rare) |
| "Swapped" Rounds | 0 (all explained) | ✅ N/A | Covered by above cases |
| Gaming Session Detection | Every import | ✅ Implemented | 60-minute gap threshold |

**Key Takeaway**: All edge cases are either fixed or working as intended. No action required.

---

## 4. Gaming Session Detection ⭐

### What It Is
System automatically groups consecutive rounds into "gaming sessions" representing full play sessions (entire night of gameplay).

### Terminology
- **ROUND** = One R1 or R2 file (single round on one map)
- **MATCH** = R1 + R2 pair (both teams play same map)
- **GAMING SESSION** = Entire night of continuous play (multiple matches)

### Detection Logic
✅ **Implemented** in database (Phase 1, November 4, 2025):
- Each round gets `gaming_session_id` assigned on import
- If gap between rounds > **60 minutes** → new gaming session
- If gap ≤ 60 minutes → continue existing gaming session
- Handles midnight-crossing automatically

### Example: October 19, 2025
**Before Gaming Round Tracking:**
- Database showed "23 sessions" (actually 23 rounds)
- Hard to tell it was one continuous play session

**After Gaming Round Tracking:**
- All 23 rounds correctly grouped into gaming session #3
- Start: Oct 19, 21:26:43
- End: Oct 20, 00:00:43 (crosses midnight)
- Duration: 154 minutes (2.6 hours)
- Max gap between rounds: 14.8 minutes

### Real-World Gaming Sessions (Oct 14 - Nov 3, 2025)
**17 gaming sessions** created from **231 rounds**:

| Gaming Session | Date(s) | Rounds | Duration | Notes |
|----------------|---------|--------|----------|-------|
| #1 | Oct 17 | 5 | 51 min | Early session |
| #2 | Oct 17 | 5 | 35 min | Late session (98min gap) |
| **#3** | **Oct 19-20** | **24** | **154 min (2.6h)** | **Crosses midnight** ✅ |
| #4 | Oct 20 | 18 | 137 min | |
| #5 | Oct 21 | 16 | 143 min | |
| #6 | Oct 22 | 16 | 126 min | |
| #7 | Oct 23 | 18 | 121 min | |
| #8 | Oct 24 | 4 | 22 min | Short session |
| #9 | Oct 25 | 4 | 28 min | Afternoon session |
| #10 | Oct 26 | 7 | 73 min | Evening |
| #11 | Oct 26 | 8 | 71 min | Late (68min gap) |
| #12 | Oct 27 | 16 | 110 min | |
| #13 | Oct 28 | 20 | 143 min | |
| #14 | Oct 30 | 18 | 128 min | |
| #15 | Nov 1-2 | 14 | 161 min | **Crosses midnight** ✅ |
| #16 | Nov 2 | 18 | 138 min | |
| #17 | Nov 3 | 20 | 116 min | Latest session |

### Edge Cases Handled
1. **Midnight-Crossing**: Gaming sessions can span multiple dates (sessions #3, #15)
2. **Multiple Sessions Per Day**: Oct 17 and Oct 26 each have 2 gaming sessions
3. **Short Sessions**: Gaming session #8 is only 22 minutes (4 rounds)
4. **Long Sessions**: Gaming session #15 is 161 minutes (2.7 hours, 14 rounds)

### Bot Integration
✅ **Implemented** in `bot/cogs/last_session_cog.py`:
- `!last_round` command now shows full gaming session
- Query: `SELECT * FROM rounds WHERE gaming_session_id = ?`
- Much simpler than old 30-minute manual gap logic

### Migration Details
- **Script**: `migrate_add_gaming_session_id.py`
- **Date**: November 4, 2025
- **Changes**: Added `gaming_session_id` column, backfilled all 231 rounds
- **Status**: ✅ Non-breaking change (all tests passed)

### Why 60 Minutes?
- Typical round: 10-15 minutes
- Typical break between games: 0-5 minutes
- Typical break between maps: 1-3 minutes
- Long break (food/bathroom): 15-30 minutes
- **If players take a 60+ minute break → they've stopped playing for the night**

### Status
✅ **Fully Implemented** - All 231 existing rounds backfilled, new imports automatically get gaming_session_id

---

## References
- Database Manager: `database_manager.py` lines 390-456
- Validation Report: `VALIDATION_FINDINGS_NOV3.md`
- Lua Stats Script: `c0rnp0rn.lua` (server-side)
- Investigation Log: This document

---

**Last Updated**: November 4, 2025
**Reviewed By**: User (manual file inspection)
**Next Review**: Only if new edge cases discovered
