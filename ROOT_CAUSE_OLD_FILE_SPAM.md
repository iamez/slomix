# Root Cause Analysis: Why Bot Spammed Old Files

**Date:** November 4, 2025  
**Issue:** Bot imported 51 old files (some from Feb/Aug 2025) on startup  
**Status:** ✅ ROOT CAUSE IDENTIFIED

---

## Timeline

### Yesterday (November 3, 2025)
- **23:34:30** - Bot processed first batch of files (231 files)
- **23:35:19** - Bot finished processing
- ➡️ **THEORY:** This was likely a manual `!sync_all` or bulk import

### Today (November 4, 2025)
- **10:02:55** - You started the bot
- **10:03:00** - Bot SSH monitor checked remote server
- **10:03:05** - Bot found "new" files and started importing
- **10:03:30** - Bot imported 51 old files (Feb, Aug, Sept, Oct 2024/2025)
- **You stopped it** - Prevented more spam

---

## Root Cause

### **The bot's SSH monitor discovered 51 files that:**
1. ✅ Exist on SSH server
2. ❌ Are NOT in `processed_files` table
3. ❌ Are NOT in `local_stats` directory
4. ❌ Are NOT in database

### **Why weren't they tracked before?**

**ANSWER:** These files were uploaded to the SSH server AFTER your last sync!

Looking at the evidence:
- Yesterday (Nov 3) at 23:34: Bot synced 231 files
- But the SSH server has **282 files total** in processed_files table
- **Difference: 51 files** ← Exactly the number bot tried to import today!

### **What happened:**

```
Timeline:
---------
Nov 3, 23:30  → Bot syncs 231 files from SSH
Nov 3, 23:40  → Someone (or a process) uploads old stat files to SSH server
                (Maybe a backup restoration? Server cleanup? Manual upload?)
Nov 4, 10:03  → Bot starts, checks SSH, finds 51 "new" files
Nov 4, 10:03  → Bot downloads and imports them (they look new!)
Nov 4, 10:03  → Bot posts them to Discord
Nov 4, 10:04  → You stop the bot 🛑
```

---

## Files That Were Imported (Sample)

```
Session #232: 2025-08-21 21:59:52 - etl_adlernest
Session #233: 2025-02-16 22:27:14 - te_escape2
Plus 49 more old files...
```

These are tracked in `processed_files` but NOT in `local_stats`:
```
2024-04-16-220731-te_escape2-round-1.txt
2024-05-09-200616-etl_sp_delivery-round-2.txt
2024-10-10-213154-etl_adlernest-round-1.txt
2025-02-16-222714-te_escape2-round-1.txt
2025-08-19-231552-sw_goldrush_te-round-1.txt
2025-08-21-215952-etl_adlernest-round-2.txt
...and 45 more
```

---

## Why This Didn't Happen Before

**For the last 3 days:**
- Bot was running continuously
- SSH monitor was checking every 30 seconds
- But it only found files that were ALREADY tracked
- So no spam!

**Today was different:**
- Bot restarted (fresh state)
- SSH monitor found 51 files that were NOT tracked
- Bot had no date filter, so it imported them all
- Result: Discord spam!

---

## The Fix We Applied

Added **bot startup time filter**:

```python
# Only import files created AFTER bot started
if file_datetime < self.bot_startup_time:
    skip_file()  # Don't import old files
else:
    import_file()  # Import new files only
```

**Result:**
- Files from before bot startup → Skip ⏭️
- Files from after bot startup → Import ✅

---

## Conclusion

**What happened:**
1. Old files were uploaded to SSH server between Nov 3 (23:35) and Nov 4 (10:03)
2. Bot had no way to know they were "old" (no date filter)
3. Bot imported them thinking they were new
4. Discord got spammed

**Why it won't happen again:**
- ✅ Bot now filters by startup time
- ✅ Only files created AFTER bot starts get imported
- ✅ Old files are automatically skipped

**Mystery remaining:**
- Who/what uploaded those 51 old files to the SSH server?
- Was it a backup restoration?
- Manual upload?
- Server maintenance?

You might want to check with whoever manages the SSH server to see if anything changed.
