# Monitoring History Fix — Postmortem
Date: 2026-02-05

## TL;DR
Monitoring history was failing silently because the bot’s DB adapter `execute()` only accepted a single params tuple, but the monitoring service passed positional params. This broke **both** server and voice history writes. We fixed the adapter to accept either style, restarted the bot, and confirmed inserts. We also added an API endpoint to verify history counts and last samples.

## Symptoms (What We Saw)
- Home page activity widgets showed **no historical data**.
- `/api/diagnostics` showed:
  - `server_status_history`: rows existed but old (stuck at Jan 6)
  - `voice_status_history`: always **0 rows**
- Bot logs showed repeated errors:
  - `Failed to record voice status: PostgreSQLAdapter.execute() takes from 2 to 3 positional arguments but 8 were given`
  - Same error for server inserts (9 params)

## Root Cause
`MonitoringService` called `db.execute(query, param1, param2, ...)`, but `PostgreSQLAdapter.execute()` only accepted `execute(query, params_tuple)`.

That mismatch caused asyncpg to receive **too many positional arguments**, so inserts never happened.

## Fixes Applied
1. **Database adapter now accepts both param styles**
   - Updated `PostgreSQLAdapter.execute()` to normalize positional parameters into a tuple.
   - Also handles scalar param passed without tuple.

2. **New monitoring status API**
   - Added `/api/monitoring/status` to show counts + last sample timestamps.
   - Extended `/api/diagnostics` to include monitoring summary.

3. **UI feedback updated**
   - Server/voice history widgets show “last sample X ago” when data exists.
   - If empty, they show “no samples yet / unavailable”.

## Verification
After bot restart, the following showed fresh data:

```
GET /api/monitoring/status
server.count: 301
server.last_recorded_at: 2026-02-05T20:53:58Z
voice.count: 4
voice.last_recorded_at: 2026-02-05T20:56:03Z
```

## Why It Took So Long
- The failure looked like “no data” rather than a crash, so it blended in with other “empty data” issues.
- Logs from January contained the exact error, but recent logs didn’t show it because the service wasn’t restarted after code changes.
- The adapter signature mismatch was hidden because most other code **passes tuples** correctly; monitoring was the outlier.

## Lessons / Guardrails
- Treat “no data” as an error condition when monitoring is expected to run.
- Always log when a periodic task fails to insert (and surface it in diagnostics).
- Prefer a single calling convention for DB adapters, or enforce it with type checks/tests.

## Files Touched
- `bot/core/database_adapter.py`
- `bot/services/monitoring_service.py` (previously)
- `website/backend/routers/api.py`
- `website/js/live-status.js`
- `website/js/leaderboard.js`
- `website/js/app.js`

