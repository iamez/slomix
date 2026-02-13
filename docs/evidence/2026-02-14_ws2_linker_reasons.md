# Evidence: WS2-002 Round Linker Failure Reason Logs
Date: 2026-02-13  
Workstream: WS2 (Timing Service Robustness)  
Task: `WS2-002`  
Status: `in_progress`

## Goal
Emit structured reason codes when round linking fails so diagnosis is immediate and machine-readable.

## Code Changes
Files:
1. `bot/core/round_linker.py`
2. `bot/ultimate_bot.py`

What changed:
1. Added `resolve_round_id_with_reason(...)` in `bot/core/round_linker.py`.
2. Added diagnostics payload fields:
   - `reason_code`
   - `candidate_count`
   - `parsed_candidate_count`
   - `best_diff_seconds`
   - `map_name`, `round_number`, `round_date`, `round_time`, `window_minutes`
3. Preserved compatibility API:
   - `resolve_round_id(...)` now wraps `resolve_round_id_with_reason(...)`.
4. `_resolve_round_id_for_metadata(...)` now logs resolution outcome with reason code:
   - resolved path logs `round_id` + reason + candidate stats
   - unresolved path logs reason + candidate stats + time context

Implemented reason codes:
1. `resolved`
2. `invalid_input`
3. `no_rows_for_map_round`
4. `date_filter_excluded_rows`
5. `time_parse_failed`
6. `all_candidates_outside_window`

## Test Coverage Added
File:
1. `tests/unit/test_round_linker_reasons.py`

Tests:
1. resolved with near match
2. no rows
3. date filter excluded rows
4. candidates outside window
5. time parse failed
6. compatibility wrapper behavior

## Validation
Command:
```bash
pytest -q tests/unit/test_round_linker_reasons.py
```

Result:
1. `6 passed`

Extended batch run (with current related guards):
```bash
pytest -q \
  tests/unit/test_round_linker_reasons.py \
  tests/unit/test_gametime_synthetic_round.py \
  tests/unit/test_greatshot_player_stats_enrichment.py \
  tests/unit/test_greatshot_crossref.py \
  tests/unit/test_lua_round_teams_param_packing.py
```

Result:
1. `14 passed`

## Remaining Runtime Validation
1. Observe production logs during live ingestion and confirm unresolved cases include reason code lines.
2. Confirm WS2 dashboards/diagnostics consumers can leverage reason codes without further schema changes.
