# Bot Fix: Startup Time Auto-Import Filter

**Date:** November 4, 2025  
**Issue:** Bot was auto-importing old files (from February/August 2025) and spamming Discord  
**Fix:** Added bot startup time filter to SSH auto-import

---

## Problem

When the bot started, it detected old stat files on the SSH server that were never imported:
- `2025-08-21-215952-etl_adlernest-round-2.txt` (75 days old)
- `2025-02-16-222714-te_escape2-round-1.txt` (261 days old)

These files triggered the auto-import and posted to Discord, which is not desired for old games.

---

## Solution

Added bot startup time tracking and filtering to `bot/ultimate_bot.py`:

**1. Track bot startup time in `__init__`:**
```python
# 🎮 Bot State
self.bot_startup_time = datetime.now()  # Track when bot started
```

**2. Filter based on startup time in `should_process_file()`:**
```python
# 1. Check file age - only import files created AFTER bot startup
try:
    # Parse datetime from filename: YYYY-MM-DD-HHMMSS-...
    datetime_str = filename[:17]  # Get YYYY-MM-DD-HHMMSS
    file_datetime = datetime.strptime(datetime_str, "%Y-%m-%d-%H%M%S")
    
    # Skip files created before bot started
    if file_datetime < self.bot_startup_time:
        logger.debug(f"⏭️ {filename} created before bot startup (skip old files)")
        self.processed_files.add(filename)
        await self._mark_file_processed(filename, success=True)
        return False
    else:
        logger.debug(f"✅ {filename} created after bot startup (process as new file)")
except ValueError:
    logger.warning(f"⚠️ Could not parse datetime from filename: {filename}")
```

---

## Behavior

### Files Created AFTER Bot Startup ✅
- **Action:** Download, import to database, post to Discord
- **Use Case:** Live updates for games happening RIGHT NOW
- **Example:** Bot starts at 10:00, game at 10:15 → Auto-import ✅

### Files Created BEFORE Bot Startup ⏭️
- **Action:** Skip (mark as processed in database)
- **Reason:** Old games should not spam Discord on bot restart
- **Example:** Bot starts at 10:00, game file from 09:30 → Skip ⏭️
- **Note:** Files are still available on SSH server for manual bulk import via `!sync` commands

---

## Testing

Created `test_date_filter.py` to verify the logic:

```
Bot Startup Time: 2025-11-04 10:19:46

File Datetime             Relative Time   Process?     Status
---------------------------------------------------------------------------
2025-11-04 10:20:46       +1 minute       YES          ✅ PASS
2025-11-04 10:24:46       +5 minutes      YES          ✅ PASS
2025-11-04 11:19:46       +1 hour         YES          ✅ PASS
2025-11-04 10:18:46       -1 minute       NO           ✅ PASS
2025-11-04 09:49:46       -30 minutes     NO           ✅ PASS
2025-11-04 09:19:46       -1 hour         NO           ✅ PASS
2025-11-03 10:19:46       -1 day          NO           ✅ PASS
2025-10-05 10:19:46       -30 days        NO           ✅ PASS

✅ ALL TESTS PASSED
```

---

## Manual Import for Old Files

If you want to import old files without posting to Discord:

```bash
# Use the sync commands (they don't auto-post)
!sync_all          # Sync all files
!sync_month        # Sync specific month
!sync_week         # Sync specific week
!sync_today        # Sync today only
```

Or use manual bulk import scripts:
```bash
python tools/simple_bulk_import.py
```

---

## Files Modified

1. **bot/ultimate_bot.py** - Added `bot_startup_time` tracking and startup time filter
   - Line ~2559: Added `self.bot_startup_time = datetime.now()`
   - Line ~4120: Updated `should_process_file()` with startup time logic
2. **test_date_filter.py** (NEW) - Test suite for startup time filtering
3. **BOT_FIX_7DAY_FILTER.md** (this file) - Documentation

---

## Next Steps

✅ **Ready to test bot again!**

The bot will now:
1. Only auto-import files created AFTER it starts
2. Skip old files (mark them as processed to prevent re-checking)
3. Prevent Discord spam from historical games on bot restart

### How It Works

**Scenario 1: Bot restarts at 10:00 AM**
- Files from 09:00, 08:00, yesterday → **Skip** ⏭️
- New game at 10:15 → **Auto-import** ✅
- New game at 10:45 → **Auto-import** ✅

**Scenario 2: Bot runs continuously**
- All new games → **Auto-import** ✅ (because they're all created after startup)

**Scenario 3: Want to import old files?**
- Use manual commands: `!sync_all`, `!sync_week`, `!sync_month` 
- Or bulk import scripts (no auto-posting to Discord)
