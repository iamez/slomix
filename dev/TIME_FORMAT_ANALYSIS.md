# Time Format Analysis - c0rnp0rn3.lua Stats Files

**Date:** October 3, 2025  
**Status:** Working Theory - Implemented but needs validation

## Header Format

```
servername\mapname\config\round\defenderteam\winnerteam\timelimit\nextTimeLimit
```

## Field Meanings

### Round 1 Files
- **Field 7 (timelimit)**: Original map time limit (e.g., `12:00`)
- **Field 8 (nextTimeLimit)**: Actual completion time OR fullhold time
  - If attackers win: Time they took (e.g., `5:30`)
  - If defenders fullhold: Same as timelimit (e.g., `12:00`)
  - This becomes Round 2's time limit in stopwatch mode

### Round 2 Files
- **Field 7 (timelimit)**: The time limit for this round (inherited from Round 1 result)
- **Field 8 (nextTimeLimit)**: Value of `g_nextTimeLimit` cvar at intermission
  - Often shows `0:00` (19.6% of all Round 2 files - 314 out of 1,604)
  - Possibly indicates no next round OR defenders held successfully
  - **NOT the actual round duration**

## The `0:00` Mystery

### Statistics
- **Round 1 files with `0:00`**: 0 out of 1,614 (0%)
- **Round 2 files with `0:00`**: 314 out of 1,604 (19.6%)

### Theory
When Round 2 ends, the game server's `g_nextTimeLimit` cvar is:
1. Reset to 0 (no next round coming)
2. Not set properly (because map is ending)
3. Indicates defenders held successfully (no completion time recorded)

### Examples

**Example 1: Fullhold in Round 1**
```
Round 1: \10:00\10:00 (defenders held for full 10 minutes)
Round 2: \10:00\0:00   (time limit is 10:00, nextTimeLimit shows 0:00)
```

**Example 2: Attackers win Round 1**
```
Round 1: \12:00\3:30 (attackers won in 3:30)
Round 2: \3:30\0:00  (time limit is now 3:30, nextTimeLimit shows 0:00)
```

**Example 3: Normal completion (no 0:00)**
```
Round 1: \12:00\5:01 (attackers won in 5:01)
Round 2: \10:00\5:01 (time limit changed, nextTimeLimit preserved)
```

## Parser Implementation

### Current Approach (as of Oct 3, 2025)
- **Round 1**: 
  - `time_limit` = Field 7
  - `actual_time` = Field 8
- **Round 2**: 
  - `time_limit` = Field 7
  - `actual_time` = Field 8 (even if `0:00`)
  - Note: When Field 8 is `0:00`, we store it as-is for data integrity

### Round Outcome Logic
The parser's `determine_round_outcome()` function should handle:
- If `actual_time == "0:00"` in Round 2: Mark as "defenders_hold" or similar
- If `actual_time == time_limit`: Fullhold
- If `actual_time < time_limit`: Attackers won

## Data Integrity Note

We're storing the `0:00` values as-is in the database to preserve the original data. This allows us to:
1. Analyze patterns later if needed
2. Correct interpretation if we discover the true meaning
3. Maintain audit trail of raw data

## Source Code Reference

From `c0rnp0rn3.lua` lines 284-290:
```lua
local servername    = et.trap_Cvar_Get("sv_hostname")
local config        = et.trap_Cvar_Get("g_customConfig")
local defenderteam  = tonumber(isEmpty(et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_MULTI_INFO), "d"))) + 1
local winnerteam    = tonumber(isEmpty(et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_MULTI_MAPWINNER), "w"))) + 1
local timelimit     = ConvertTimelimit(et.trap_Cvar_Get("timelimit"))
local nextTimeLimit = ConvertTimelimit(et.trap_Cvar_Get("g_nextTimeLimit"))
local header        = string.format("%s\\%s\\%s\\%d\\%d\\%d\\%s\\%s\n", servername, mapname, config, round, defenderteam, winnerteam, timelimit, nextTimeLimit)
```

## Next Steps

If we need to investigate further:
1. Check ET:Legacy source code for `g_nextTimeLimit` handling
2. Contact server admins for game server logs
3. Analyze correlation between `0:00` and round outcomes (winner field)
4. Test on live server to see when `0:00` appears

## Related Files
- `bot/community_stats_parser.py` - Parser implementation
- `dev/bulk_import_stats.py` - Import tool
- `dev/check_zero_times.py` - Analysis script
