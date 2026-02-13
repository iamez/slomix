# Evidence: WS0-005 Map Summary Scope Correctness
Date: 2026-02-12  
Workstream: WS0 (Score Truth Chain)  
Task: `WS0-005`  
Status: `done`

## Goal
Ensure map-summary "all rounds" aggregation uses the full map pair scope (R1+R2 in the same `gaming_session_id`), not a single `round_id`.

## Code Changes
File:
1. `bot/services/round_publisher_service.py`

What changed:
1. `_check_and_post_map_completion(...)` now checks completion using `rounds` scoped by:
   - `gaming_session_id` from anchor `round_id`
   - same `map_name`
   - `round_number IN (1, 2)`
2. `_post_map_summary(...)` now resolves `gaming_session_id` first and aggregates from `player_comprehensive_stats` using:
   - `round_id IN (SELECT id FROM rounds ... gaming_session_id/map_name/round_number IN (1,2))`
3. Top-performer query uses the same scope, removing single-round drift.

## Test Coverage
File:
1. `tests/unit/test_round_publisher_map_scope.py`

Coverage points:
1. Completion check query uses `rounds` + `gaming_session_id` scope.
2. Aggregate query uses `round_id IN (subquery)` map-pair scope.
3. Top-performer query uses the same map-pair scope.

Validation commands:
```bash
pytest -q tests/unit/test_round_publisher_map_scope.py
```

```bash
pytest -q \
  tests/unit/test_round_publisher_map_scope.py \
  tests/unit/test_round_contract.py \
  tests/unit/test_stats_parser.py \
  tests/unit/test_gametime_synthetic_round.py \
  tests/unit/test_lua_round_teams_param_packing.py \
  tests/unit/test_timing_debug_service_session_join.py \
  tests/unit/test_lua_webhook_diagnostics.py \
  tests/unit/test_greatshot_crossref.py \
  tests/unit/test_greatshot_player_stats_enrichment.py
```

Results:
1. Focused map-scope tests: `3 passed`
2. Combined regression batch: `40 passed`
