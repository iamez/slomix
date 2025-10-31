# 🔧 Quick Fix - Time Dead Column Issue

**Date:** October 4, 2025  
**Issue:** `sqlite3.OperationalError: no such column: p.time_dead_minutes`

## Problem

The bot was trying to query `time_dead_minutes` column which doesn't exist in the database.

## Root Cause

The database schema only has `time_dead_ratio` (a percentage), not `time_dead_minutes` or `time_dead_seconds`.

## Solution

Changed the SQL query to calculate time dead from the ratio:

**Before (broken):**
```sql
SUM(p.time_dead_minutes) * 60 as total_time_dead
```

**After (working):**
```sql
CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as total_time_dead
```

## How It Works

1. `time_played_seconds` = Total time alive (e.g., 686 seconds)
2. `time_dead_ratio` = Percentage of time dead (e.g., 15.5%)
3. `time_played_seconds * time_dead_ratio / 100.0` = Time dead in seconds
4. Example: 686 seconds * 15.5 / 100 = 106.33 seconds ≈ 106 seconds (1:46)

## Testing

The bot should now work correctly. Test with:

```powershell
python bot/ultimate_bot.py
```

Then in Discord:
```
!last_session
```

You should see time dead displayed as: `💀 1:46` or similar.

## Status

✅ **Fixed and Ready to Use**
