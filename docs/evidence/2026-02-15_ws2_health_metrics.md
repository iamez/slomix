# Evidence: WS2-005 Timing Diagnostics Health Metrics
Date: 2026-02-12  
Workstream: WS2 (Timing Service Robustness)  
Task: `WS2-005`  
Status: `in_progress` (offline-staged, WS2 closeout gated by WS1 live source-health)

## Goal
Expose daily trend metrics so Lua linkage health is visible without log scraping.

## Implementation
File:
1. `website/backend/routers/api.py`

Endpoint:
1. `GET /api/diagnostics/lua-webhook`

Added payload section:
1. `trends.lua_rows_by_day`
2. `trends.rounds_without_lua_by_day`

Query behavior:
1. `lua_rows_by_day`: daily count of `lua_round_teams` rows + unlinked subset for last 14 days.
2. `rounds_without_lua_by_day`: daily `rounds` totals vs missing `lua_round_teams` linkage via `l.round_id = r.id`.

## Test Coverage
File:
1. `tests/unit/test_lua_webhook_diagnostics.py`

Validation command:
```bash
pytest -q tests/unit/test_lua_webhook_diagnostics.py
```

Result:
1. `1 passed`

Additional regression batch also green:
```bash
pytest -q tests/unit/test_round_linker_reasons.py tests/unit/test_timing_debug_service_session_join.py
```

Result:
1. `7 passed`

## Runtime Snapshot (DB)
Observed `rounds_without_lua_by_day` values:
1. `2026-02-11`: `16` total, `16` without Lua.
2. `2026-02-06`: `11` total, `11` without Lua.
3. `2026-02-04`: `1` total, `1` without Lua.
4. `2026-02-03`: `5` total, `5` without Lua.
5. `2026-02-02`: `22` total, `22` without Lua.

Observed `lua_rows_by_day` values:
1. empty for last 14 days (consistent with stale `lua_round_teams`).

## Outcome
1. Health metrics are now available in diagnostics payload shape.
2. Current trend data clearly surfaces WS1 ingestion staleness.
