# Session Notes: 2026-01-15 - Endstats Processing Fixes

## Overview

This session addressed multiple issues preventing endstats files from being processed and posted to Discord after game rounds.

---

## Issue 1: Endstats Files Routed to Wrong Parser

### Symptom

```
2026-01-15 20:29:31 | ERROR | bot.core | ❌ Processing failed for 2026-01-15-212914-etl_adlernest-round-1-endstats.txt: Parser error: invalid header format
```

### Root Cause

The SSH monitoring task (`endstats_monitor`) in `bot/ultimate_bot.py` was sending ALL downloaded files to `process_gamestats_file()`, which uses `community_stats_parser.py`.

**The problem**: `community_stats_parser.py` expects regular stats files with backslash-delimited (`\`) headers containing 8+ fields:

```
timestamp\mapname\gamemode\round\duration\axis_score\allies_score\...
```

But endstats files (`*-endstats.txt`) have a completely different format - tab-separated awards and VS stats:

```
Most damage given	PlayerName	3214
Most kills per minute	PlayerName	1.78
```

The webhook handler at lines 2270-2285 already had correct routing logic:

```python
is_endstats = filename.endswith('-endstats.txt')
if is_endstats:
    asyncio.create_task(self._process_webhook_triggered_endstats(filename, message))
else:
    asyncio.create_task(self._process_webhook_triggered_file(filename, message))
```

But the SSH monitor path at line 1749 bypassed this entirely:

```python
# Old code - sent ALL files to wrong parser
result = await self.process_gamestats_file(local_path, filename)
```

### Fix Applied

**File**: `bot/ultimate_bot.py` (lines 1750-1771)

Added endstats file detection before processing:

```python
# Route endstats files to dedicated processor
if filename.endswith('-endstats.txt'):
    logger.info(f"🏆 Detected endstats file, using endstats processor")
    await self._process_endstats_file(local_path, filename)
else:
    # Regular stats file processing
    result = await self.process_gamestats_file(local_path, filename)
```

Also created new method `_process_endstats_file()` (lines 2388-2518) that:
- Parses with `endstats_parser.py` (correct parser)
- Stores awards and VS stats in database
- Posts endstats embed to Discord
- Marks file as processed in `processed_endstats_files` table

### Why This Fix Works

The fix ensures both code paths (webhook and SSH monitor) route endstats files to the dedicated `endstats_parser.py` which understands the tab-separated awards format.

---

## Issue 2: PostgreSQL Adapter API Mismatch

### Symptom

```
2026-01-15 20:30:55 | ERROR | MonitoringService | Failed to record server status: PostgreSQLAdapter.execute() takes from 2 to 3 positional arguments but 9 were given
2026-01-15 20:30:55 | ERROR | MonitoringService | Failed to record voice status: PostgreSQLAdapter.execute() takes from 2 to 3 positional arguments but 8 were given
```

### Root Cause

The `MonitoringService` in `bot/services/monitoring_service.py` was calling the database adapter incorrectly.

**The problem**: `PostgreSQLAdapter.execute()` method signature is:

```python
async def execute(self, query: str, params: Optional[Tuple] = None)
```

But the monitoring service was passing parameters as individual positional arguments:

```python
# Old code - WRONG
await self.db.execute(
    """INSERT INTO server_status_history...""",
    status.player_count,      # arg 3
    status.max_players,       # arg 4
    status.map_name,          # arg 5
    status.clean_hostname,    # arg 6
    json.dumps([...]),        # arg 7
    status.ping_ms,           # arg 8
    status.online,            # arg 9
)
```

This resulted in 9 positional arguments when the method only accepts 2-3.

### Fix Applied

**File**: `bot/services/monitoring_service.py` (lines 97-117, 161-176)

Wrapped parameters in tuples:

```python
# New code - CORRECT
await self.db.execute(
    """INSERT INTO server_status_history...""",
    (  # Parameters wrapped in tuple
        status.player_count,
        status.max_players,
        status.map_name,
        status.clean_hostname,
        json.dumps([...]),
        status.ping_ms,
        status.online,
    ),
)
```

Same fix applied to `_record_voice_status()` method.

### Why This Fix Works

The `PostgreSQLAdapter.execute()` method unpacks the tuple internally:

```python
async def execute(self, query: str, params: Optional[Tuple] = None):
    async with self.connection() as conn:
        await conn.execute(query, *(params or ()))  # Unpacks tuple here
```

Passing params as a tuple matches the expected signature and allows proper unpacking.

---

## Issue 3: Endstats Round Lookup Timestamp Mismatch

### Symptom

```
2026-01-15 20:46:45 | WARNING | bot.webhook | ⏳ Round not found yet for endstats 2026-01-15-214640-supply-round-1-endstats.txt. Main stats file may not be processed yet.
```

This warning appeared even AFTER the main stats file was successfully processed.

### Root Cause

The endstats and main stats files have slightly different timestamps:

```
Endstats: 2026-01-15-214640-supply-round-1-endstats.txt  (timestamp: 21:46:40)
Main:     2026-01-15-214641-supply-round-1.txt          (timestamp: 21:46:41)
```

The Lua scripts write files approximately 1 second apart. The endstats file is written first.

**The problem**: The round lookup query used exact `match_id` prefix matching:

```python
# Old query - TOO STRICT
round_query = """
    SELECT id, round_date, map_name FROM rounds
    WHERE match_id LIKE $1 AND round_number = $2
    ORDER BY created_at DESC LIMIT 1
"""
round_result = await self.db_adapter.fetch_one(
    round_query, (f"{match_id_prefix}%", round_number)
)
# Searched for: '2026-01-15-214640-supply%'
# But round was created with: '2026-01-15-214641-supply-round-1'
# LIKE query fails because 214640 != 214641
```

### Fix Applied

**File**: `bot/ultimate_bot.py`

Updated both `_process_endstats_file()` (lines 2424-2440) and `_process_webhook_triggered_endstats()` (lines 2598-2614) to use flexible lookup:

```python
# New query - FLEXIBLE
# Use date + map + round_number instead of exact timestamp
round_date = metadata['date']      # "2026-01-15"
map_name = metadata['map_name']    # "supply"
round_number = metadata['round_number']  # 1

round_query = """
    SELECT id, round_date, map_name FROM rounds
    WHERE round_date = $1
      AND map_name = $2
      AND round_number = $3
    ORDER BY created_at DESC LIMIT 1
"""
round_result = await self.db_adapter.fetch_one(
    round_query, (round_date, map_name, round_number)
)
```

### Why This Fix Works

The new query matches rounds by:
- **Same date** (2026-01-15)
- **Same map name** (supply)
- **Same round number** (1)
- **Most recent** (ORDER BY created_at DESC LIMIT 1)

This ignores the exact timestamp which can vary by 1-2 seconds between the two Lua scripts. The combination of date + map + round_number is sufficient to uniquely identify a round within a gaming session.

---

## Files Modified

| File | Changes |
|------|---------|
| `bot/ultimate_bot.py` | Added endstats routing in SSH monitor, created `_process_endstats_file()`, updated round lookup queries |
| `bot/services/monitoring_service.py` | Wrapped db.execute() params in tuples |

---

## Verification

After applying fixes:

1. **Endstats routing**: Look for `🏆 Detected endstats file, using endstats processor` in logs
2. **Monitoring service**: Check for `📊 Server recorded:` and `📊 Voice recorded:` without errors
3. **Round lookup**: Look for `✅ Linked to round_id=XXXX` instead of `⏳ Round not found`

---

## Related Documentation

- `/docs/SESSION_2026-01-14_ENDSTATS_FEATURE.md` - Original endstats feature implementation
- `/docs/TIME_DEAD_BUG_FIX_2025-12-15.md` - Time tracking bug fixes
- `/bot/endstats_parser.py` - Endstats file parser implementation

---

## Session Timeline

- **20:29** - First error observed: endstats routed to wrong parser
- **20:30** - PostgreSQL adapter errors observed
- **20:46** - After first fix deployed, timestamp mismatch issue discovered
- **21:00** - All three fixes implemented and deployed
