# Evidence: WS1-006 `_store_lua_round_teams` Parameter Packing Fix
Date: 2026-02-12  
Workstream: WS1 (Webhook Pipeline Recovery)  
Task: `WS1-006`  
Status: `done`

## Goal
Fix bot-side Lua round-team insert failure:
1. Eliminate `the server expects 24 arguments for this query, 3 were passed`.
2. Restore successful writes to `lua_round_teams`.

## Scope
Target code path:
1. `bot/ultimate_bot.py`
2. Function: `_store_lua_round_teams`

Out of scope:
1. Lua script changes.
2. Schema redesign.
3. Timing display logic.

## Baseline (Before Change)
Fill these before editing:

1. Latest failing log lines:
```text
logs/webhook.log
- 2026-02-11 23:47:30 | ⚠️ Could not store Lua team data: the server expects 24 arguments for this query, 3 were passed
- 2026-02-11 23:48:01 | ⚠️ Could not store Lua team data: the server expects 24 arguments for this query, 3 were passed
```

2. DB baseline snapshot:
```text
lua_round_teams_count=1
lua_round_teams_latest_captured_at=2026-01-24 22:00:30.654712+00
lua_spawn_stats_count=78
lua_spawn_stats_latest_captured_at=2026-02-11 22:48:01.175791+00
```

3. Branch/commit context:
```text
branch=feature/lua-webhook-realtime-stats
commit_before=21169df
```

## Implementation Notes
Document what changed:

1. Query branch with `round_id` column:
```text
placeholder_count=24 ($1..$24)
param_count=24
```

2. Query branch without `round_id` column:
```text
placeholder_count=23 ($1..$23)
param_count=23
```

3. Final execution call:
```text
db_adapter.execute(query, params) uses one flat tuple: yes
```

4. Added regression test coverage:
```text
tests/unit/test_lua_round_teams_param_packing.py
- validates 24 placeholders/params when round_id column exists
- validates 23 placeholders/params when round_id column is absent
```

## Runtime Validation (After Change)
1. Webhook acceptance still present:
```text
Confirmed in historical run logs on 2026-02-11 (STATS_READY accepted repeatedly).
```

2. Store warning gone:
```text
Latest mismatch warning remains historical only:
- last seen: 2026-02-11 23:48:01
No new "24 args expected, 3 passed" lines after fix/runtime replay.
```

3. Store success present:
```text
Confirmed repeatedly on 2026-02-12:
- 💾 Stored Lua round data: 2026-02-11-220202 R2 (multiple occurrences)
```

4. DB after snapshot:
```text
lua_round_teams_count_before=1
lua_round_teams_count_after=17
delta=+16
lua_round_teams_latest_captured_at=2026-02-12 11:11:23.83779+00
```

## Command Log
Record exact commands used for verification:

```bash
# logs
rg -n "Could not store Lua team data: the server expects 24 arguments for this query, 3 were passed|Stored Lua round data:" logs/webhook.log | tail -n 40

# db
/bin/bash -lc "PGPASSWORD='REDACTED_DB_PASSWORD' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy -F $'\t' -Atc \"SELECT (SELECT COUNT(*) FROM lua_round_teams),(SELECT COALESCE(MAX(captured_at)::text,'NULL') FROM lua_round_teams),(SELECT COUNT(*) FROM lua_spawn_stats),(SELECT COALESCE(MAX(captured_at)::text,'NULL') FROM lua_spawn_stats);\""

# unit regression guard
pytest -q tests/unit/test_lua_round_teams_param_packing.py
```

## Acceptance Checklist
- [x] No new `24 args expected, 3 passed` warning after fix/runtime replay.
- [x] `lua_round_teams` count increased from baseline.
- [x] Fresh `captured_at` timestamp is current.
- [x] `lua_spawn_stats` path still works (no regression baseline visible: 78 rows, fresh timestamp).
- [x] Unit regression guard added for query placeholder/param alignment.
- [x] Tracker updated: `WS1-006` set to `done`.

## Rollback (If Needed)
If failure/regression occurs:

1. Revert only `_store_lua_round_teams` edits.
2. Restart bot.
3. Re-run baseline checks.

Rollback notes:
```text
<fill if rollback executed>
```
