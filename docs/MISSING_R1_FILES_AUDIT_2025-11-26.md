# Missing Round-1 Files Audit
**Date:** 2025-11-26
**Status:** 🚨 CRITICAL DATA LOSS ISSUE
**Impact:** 141 matches with incomplete data

---

## Summary

**Problem:** The game server creates `round-2.txt` files, but many corresponding `round-1.txt` files are **MISSING** from local_stats directory.

**Result:** Parser imports R2 file → creates R0 + R2 in database, but R1 is never imported → **incomplete match data**.

---

## Statistics

- **Total missing R1 files:** 141
- **Date range:** March 2024 - November 2025
- **Recent impact:**
  - Nov 23: 8 out of 12 maps missing R1 (67% incomplete)
  - Nov 25: 4 out of 7 maps missing R1 (57% incomplete)

---

## Examples

### Nov 23, 2025 (Recent)
```
❌ MISSING: 2025-11-23-211849-etl_adlernest-round-1.txt
   EXISTS:  2025-11-23-211849-etl_adlernest-round-2.txt

❌ MISSING: 2025-11-23-214122-supply-round-1.txt
   EXISTS:  2025-11-23-214122-supply-round-2.txt

❌ MISSING: 2025-11-23-225436-etl_frostbite-round-1.txt
   EXISTS:  2025-11-23-225436-etl_frostbite-round-2.txt
```

### Database Impact
```sql
-- etl_frostbite 225436 example:
-- Has: R0 (id 7459) + R2 (id 7458)
-- Missing: R1
-- Round 7457 is from DIFFERENT timestamp (225050)
```

---

## Root Cause Analysis

### Possible Causes:

1. **Game Server Issue:**
   - Server doesn't generate R1 file
   - Server overwrites R1 file when R2 starts
   - File permissions prevent R1 creation

2. **File Transfer Issue:**
   - R1 files created but not transferred to local_stats
   - Transfer happens after R1 is deleted on server
   - Network/timing issue during file sync

3. **Bot Processing Issue:**
   - Bot processes R1 file then deletes it
   - Bot moves R1 to different directory
   - Race condition: R2 processed before R1 arrives

---

## Investigation Steps

### 1. Check Game Server Directory
```bash
# Where does the game server write stats files?
# Are R1 files being created on the server?
# Check game server logs for file creation
```

### 2. Check File Transfer Process
```bash
# How do files get from game server to local_stats?
# Is there a cron job? SCP? SMB mount?
# Check transfer logs
```

### 3. Check Bot Processing
```bash
# Does bot delete files after processing?
# Check bot logs for R1 file processing
# Look for file move/delete operations
```

---

## Impact Assessment

### Data Loss:
- **141 maps** have R1 data completely missing
- Cannot calculate:
  - R1-only player stats
  - R1-only team performance
  - Round 1 vs Round 2 comparison
  - Accurate differential for R2

### Affected Features:
- `/last_session` shows incomplete matches
- Session stats missing R1 data
- Map statistics skewed (more R2 data than R1)
- Player performance incomplete

---

## Workaround (Current)

Parser currently:
1. Tries to find R1 file matching R2 timestamp
2. Falls back to "same-day match" (finds closest R1 by time)
3. If no R1 found: imports only R0 + R2

This partially works but:
- May pair wrong R1 with R2
- Some R1 files from different matches get used
- R1 data often doesn't match R2 timestamp

---

## Recommended Solutions

### Short-term:
1. **Check game server** - verify R1 files are being created
2. **Add file monitoring** - log when files appear/disappear
3. **Preserve files** - don't delete after processing
4. **Add timestamps** - track file creation vs processing time

### Long-term:
1. **Fix root cause** on game server (if that's the issue)
2. **Improve file sync** process (if transfer is the issue)
3. **Add backup mechanism** - copy files before processing
4. **Alert system** - notify when R1 is missing

---

## Files to Investigate

### Bot Code:
- `bot/community_stats_parser.py` - File processing logic
- `bot/ultimate_bot.py` - File import trigger
- Check for file deletion/move operations

### Server/Transfer:
- Game server config - stats file generation
- Transfer scripts - how files get to local_stats
- File permissions - can bot read/write?

---

## Status

- ✅ **Issue identified** - 141 missing R1 files
- ✅ **DPM bug fixed** - separate issue, now resolved
- ⏳ **Root cause** - needs investigation
- ⏳ **Solution** - depends on root cause

**Next steps:**
1. Check where game server writes stats files
2. Verify R1 files are created on server
3. Check file transfer/sync mechanism
4. Determine why R1 files don't reach local_stats

---

## Related Issues

- This is why some database rounds have R0+R2 but no R1
- This is unrelated to the DPM calculation bug (which is now fixed)
- This explains why session stats feel "incomplete"
- This may explain why some player stats seem low (missing R1 data)
