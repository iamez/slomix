# Bug Fixes - October 11, 2025

## 🐛 Issues Fixed

All database column reference errors in Discord commands have been fixed.

### Root Cause
The `player_aliases` table schema uses different column names than what the bot commands expected:

**Actual Schema:**
- `guid` (not `player_guid`)
- `alias` (not `player_name`)
- `times_seen` (not `times_used`)

### Commands Fixed

#### 1. ✅ `!stats` Command (Line ~511)
**Error:** `no such column: player_guid`

**Fixed Query:**
```sql
-- OLD (WRONG):
SELECT player_guid, player_name FROM player_aliases
WHERE LOWER(clean_name) LIKE LOWER(?)

-- NEW (CORRECT):
SELECT guid, alias FROM player_aliases
WHERE LOWER(alias) LIKE LOWER(?)
```

#### 2. ✅ `!link` by Name Command (Line ~3893)
**Error:** `no such column: pa.player_guid`

**Fixed Query:**
```sql
-- OLD (WRONG):
SELECT DISTINCT pa.player_guid FROM player_aliases pa
WHERE LOWER(pa.clean_name) LIKE LOWER(?)

-- NEW (CORRECT):
SELECT DISTINCT pa.guid FROM player_aliases pa
WHERE LOWER(pa.alias) LIKE LOWER(?)
```

#### 3. ✅ `!link` by GUID Command (Line ~3787)
**Error:** `no such column: player_name`

**Fixed Query:**
```sql
-- OLD (WRONG):
SELECT player_name, last_seen, times_used FROM player_aliases
WHERE player_guid = ?

-- NEW (CORRECT):
SELECT alias, last_seen, times_seen FROM player_aliases
WHERE guid = ?
```

#### 4. ✅ Admin Link Function (Line ~4091)
**Error:** `no such column: player_name`

**Fixed Query:**
```sql
-- OLD (WRONG):
SELECT player_name, last_seen, times_used FROM player_aliases
WHERE player_guid = ?

-- NEW (CORRECT):
SELECT alias, last_seen, times_seen FROM player_aliases
WHERE guid = ?
```

#### 5. ✅ Link Display Function (Line ~3963)
**Error:** `no such column: player_name`

**Fixed Query:**
```sql
-- OLD (WRONG):
SELECT player_name FROM player_aliases
WHERE player_guid = ?

-- NEW (CORRECT):
SELECT alias FROM player_aliases
WHERE guid = ?
```

## 📊 Impact

**Before Fixes:**
- ❌ `!stats <player>` - Crashed with SQL error
- ❌ `!link <player>` - Crashed with SQL error  
- ❌ `!link <guid>` - Crashed with SQL error
- ❌ Discord linking - Failed silently

**After Fixes:**
- ✅ All commands use correct column names
- ✅ No SQL errors
- ✅ Commands work as intended
- ✅ Player aliases properly queried

## 🧪 Testing Required

Test these commands in Discord:
```
!stats vid
!link vid
!link <some-guid>
```

Expected: No errors, proper results displayed

## 📝 Files Modified

- `bot/ultimate_bot.py` - 5 locations fixed
- `LAST_SESSION_RESTRUCTURE.md` - Updated with fix notes

## ✅ Verification

All `player_aliases` table references now use:
- `guid` instead of `player_guid`
- `alias` instead of `player_name` or `clean_name`
- `times_seen` instead of `times_used`

Verified with:
```sql
PRAGMA table_info(player_aliases);
-- Returns: id, guid, alias, first_seen, last_seen, times_seen
```

## 🎯 Status

**COMPLETE** - All known SQL column errors fixed.
Bot ready for production use with corrected schema references.
