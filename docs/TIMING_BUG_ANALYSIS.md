# Timing Bug Analysis - Insane Round Durations

**Date:** 2026-02-10
**Issue:** Round 2 stats showing impossible durations (78:25, 86:40, 90:00 minutes instead of ~10 minutes)

---

## Summary

**Root Cause:** Bug in c0rnp0rn7.lua's `nextTimeLimit` calculation (line 306-342)

**When it triggers:** Only on **Round 2** when `g_nextTimeLimit` cvar = "0:00"

**Affected dates:** Started Feb 4, 2026; frequent on Feb 6, 2026

**Status:** Bug exists in ALL c0rnp0rn versions (original x0rnn code)

---

## The Bug

**File:** `c0rnp0rn7.lua` (all versions)
**Lines:** 306-342

```lua
if round == 2 and nextTimeLimit == "0:00" then
    -- Get player time_played (PERCENTAGE 0-100)
    timePlayed = (100.0 * timePlayed / (timeAxis + timeAllies))

    -- BUG: Multiplies percentage by 60, treating it as MINUTES not percentage!
    table.insert(times, timePlayed * 60)

    -- Finds mode (most common), subtracts map time
    correctedSeconds = math.max(modeTime - mapSeconds, 0)
    nextTimeLimit = formatSecondsToTime(correctedSeconds)
end
```

**What goes wrong:**
- Player time_played = 86.67% (alive most of round)
- Bug calculates: `86.67 * 60 = 5200 seconds = 86:40 minutes`
- Should calculate: `(86.67% of actual_round_duration)`

---

## Evidence

### File Versions on Server

```
/home/et/etlegacy-v2.83.1-x86_64/legacy/
├── c0rnp0rn3.lua          26K  Oct 6   - Has bug
├── c0rnp0rn4.lua          28K  Oct 6   - Has bug
├── c0rnp0rn5.lua          26K  Oct 6   - Has bug
├── c0rnp0rn6.lua          26K  Oct 11  - Has bug
├── c0rnp0rn7.lua.old      26K  Oct 12  - Has bug (last before pause mods)
├── c0rnp0rn7.lua.claude   28K  Jan 6   - Has bug + pause tracking
├── c0rnp0rn7.lua          28K  Jan 13  - Has bug + pause tracking (ACTIVE)
└── endstats.lua           50K  Jan 13  - Separate stats display script
```

**All versions contain the `timePlayed * 60` bug!**

### Timeline

| Date | Event |
|------|-------|
| Oct 6-12, 2025 | c0rnp0rn3-7 versions created (bug present but dormant) |
| Jan 6, 2026 | Claude added pause tracking (c0rnp0rn7.lua.claude) |
| Jan 13, 2026 | c0rnp0rn7.lua + endstats.lua modified (pause tracking active) |
| Feb 4, 2026 | **First bad round appears** (81:40 on etl_adlernest) |
| Feb 6, 2026 | Multiple bad rounds (78:25, 86:40, 90:00, 79:20, 54:00) |

### Affected Rounds (Sample)

| Round ID | Date | Time | Map | R# | Duration | Status |
|----------|------|------|-----|----|---------:|--------|
| 9817 | 2026-02-06 | 21:34:24 | etl_adlernest | 2 | **78:25** | ❌ BAD |
| 9809 | 2026-02-06 | 21:40:11 | etl_adlernest | 2 | **86:40** | ❌ BAD |
| 9814 | 2026-02-06 | 21:48:04 | etl_adlernest | 1 | 5:54 | ✅ GOOD |
| 9806 | 2026-02-06 | 21:54:40 | etl_adlernest | 2 | 5:45 | ✅ GOOD |
| 9815 | 2026-02-06 | 21:56:58 | etl_adlernest | 2 | **90:00** | ❌ BAD |
| 9807 | 2026-02-06 | 21:59:45 | sw_goldrush_te | 2 | **79:20** | ❌ BAD |
| 9812 | 2026-02-06 | 22:24:13 | supply | 2 | 9:41 | ✅ GOOD |
| 9811 | 2026-02-06 | 22:50:35 | te_escape2 | 2 | **54:00** | ❌ BAD |

**Pattern:** Bad rounds are ALWAYS Round 2, suggesting `g_nextTimeLimit` cvar triggers bug

---

## Why Did It Start Appearing Now?

**Theory:** The bug was always present, but only triggers when:
1. Round 2 plays
2. Server cvar `g_nextTimeLimit` = "0:00"
3. Players have valid `sess.time_played` data

Possible reasons it started Feb 4:
- Server config change (g_nextTimeLimit cvar behavior)
- Map rotation change
- Something reset the cvar to "0:00" more often

---

## Modifications Made (Jan 13, 2026)

### c0rnp0rn7.lua Changes
Added **pause tracking** to exclude pause time from death time calculations:

```diff
+ paused = false
+ paused_death = {}

  if death_time[id] ~= 0 then
-   local diff = et.trap_Milliseconds() - death_time[id]
+   local diff = et.trap_Milliseconds() - death_time[id] - (paused_death[id][2] - paused_death[id][1])
    death_time_total[id] = death_time_total[id] + diff
  end
```

**These modifications did NOT introduce the timing bug.**
They track pause time, but don't affect the `nextTimeLimit` calculation.

### endstats.lua
- Separate script by x0rnn for end-game stats display
- Shows kill streaks, headshot accuracy, etc.
- Does NOT write stats files
- Modified same day (Jan 13) but unrelated to timing bug

---

## Why stats_discord_webhook.lua Isn't Firing

All problematic rounds show `lua_duration_seconds = NULL`, meaning the Slomix webhook didn't fire.

**Possible causes:**
1. Webhook script not loaded properly
2. Lua errors preventing execution
3. Discord webhook URL changed/invalid

**Check:**
```bash
# SSH to server
ssh et@puran.hehe.si -p 48101

# Check server console for errors
tail -100 /home/et/etlegacy-v2.83.1-x86_64/legacy/etconsole.log | grep -i "webhook\|discord\|lua\|error"
```

---

## Solutions

### Option 1: Fix the Bug in c0rnp0rn7.lua (RECOMMENDED)

**Problem:** Line 322 treats percentage as minutes

**Current (BROKEN):**
```lua
timePlayed = (100.0 * timePlayed / (timeAxis + timeAllies))  -- Percentage
table.insert(times, timePlayed * 60)  -- ❌ Treats as minutes!
```

**Fixed:**
```lua
timePlayed = (100.0 * timePlayed / (timeAxis + timeAllies))  -- Percentage
-- Use actual round duration instead of 60
local roundDuration = (timeAxis + timeAllies) / 1000  -- Convert ms to seconds
table.insert(times, (timePlayed / 100.0) * roundDuration)  -- ✅ Correct!
```

**Implementation:**
```bash
# Backup current version
ssh et@puran.hehe.si -p 48101
cd /home/et/etlegacy-v2.83.1-x86_64/legacy/
cp c0rnp0rn7.lua c0rnp0rn7.lua.backup_$(date +%Y%m%d)

# Edit the file
nano c0rnp0rn7.lua

# Find line 322 (around there):
# table.insert(times, timePlayed * 60)

# Replace with:
# local roundDuration = (timeAxis + timeAllies) / 1000
# table.insert(times, (timePlayed / 100.0) * roundDuration)

# Restart server to apply
```

### Option 2: Use stats_discord_webhook.lua for Timing

The Slomix webhook provides accurate timing via gamestate hooks, bypassing c0rnp0rn's buggy calculation.

**Fix webhook not firing:**
1. Check if script loads: Look for `[stats_discord_webhook] v1.6.0 loaded` in console
2. Check for Lua errors in server logs
3. Verify webhook URL is valid

**When working, bot uses:**
- `lua_round_teams.actual_duration_seconds` (accurate)
- Falls back to `rounds.actual_time` (buggy) only if webhook fails

### Option 3: Revert to Pre-Pause Version

If pause tracking isn't needed:
```bash
# Restore version from Oct 12 (before pause mods)
cp c0rnp0rn7.lua.old c0rnp0rn7.lua

# Restart server
```

**Note:** This still has the timing bug, but removes pause tracking complexity.

---

## Recommended Action Plan

1. **Immediate:** Fix stats_discord_webhook.lua so it fires correctly
   - Provides accurate timing for new rounds
   - Doesn't require modifying c0rnp0rn7.lua

2. **Short-term:** Apply the bug fix to c0rnp0rn7.lua
   - Fixes the root cause
   - Makes stats files accurate

3. **Long-term:** Consider upgrading to oksii's game-stats-web.lua
   - Modern JSON format
   - Better maintained
   - Located in `docs/reference/oksii-game-stats-web.lua`

---

## Testing the Fix

After applying fix, test with a Round 2 where `g_nextTimeLimit` would be "0:00":

1. Play a normal round
2. Check the stats file: `cat /path/to/stats/file.txt | head -1`
3. Verify the `nextTimeLimit` value is reasonable (under 15 minutes)

**Before fix:**
```
server\etl_adlernest\legacy3\2\1\1\10:00\86:40
                                          ^^^^^ BAD
```

**After fix:**
```
server\etl_adlernest\legacy3\2\1\1\10:00\9:23
                                          ^^^^ GOOD
```

---

## Files for Reference

**Downloaded from server:**
- `/tmp/c0rnp0rn7_ORIGINAL.lua` - Oct 12 version (has bug, no pause tracking)
- `/tmp/c0rnp0rn7_BROKEN.lua` - Jan 13 version (has bug + pause tracking)
- `/tmp/endstats_CURRENT.lua` - Jan 13 endstats script

**Diff between versions:**
```bash
diff -u /tmp/c0rnp0rn7_ORIGINAL.lua /tmp/c0rnp0rn7_BROKEN.lua > /tmp/c0rnp0rn7_changes.diff
```

---

## Related Issues

**Time Dead Anomalies:** The impossible time_dead percentages (1331%, 1210%, etc.) are a SEPARATE issue from the round duration bug, but both stem from timing calculations in c0rnp0rn7.lua.

See: `docs/CLAUDE.md` - Known Issues section

---

**Document Version:** 1.0
**Author:** Investigation by Claude Code
**Last Updated:** 2026-02-10
