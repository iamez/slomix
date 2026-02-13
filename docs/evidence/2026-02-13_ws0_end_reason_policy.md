# Evidence: WS0-004 End Reason Enum Policy
Date: 2026-02-12  
Workstream: WS0 (Score Truth Chain)  
Task: `WS0-004`  
Status: `done`

## Goal
Normalize raw end-reason values to strict enum policy and expose derived display classification.

## Persisted Enum Policy
Helper:
1. `bot/core/round_contract.py::normalize_end_reason`

Enum:
1. `NORMAL`
2. `SURRENDER`
3. `MAP_CHANGE`
4. `MAP_RESTART`
5. `SERVER_RESTART`

## Derived Display Classification
Helper:
1. `bot/core/round_contract.py::derive_end_reason_display`

Display classes:
1. `FULL_HOLD`
2. `TIME_SET`
3. `SURRENDER_END`
4. `MAP_CHANGE_END`
5. `MAP_RESTART_END`
6. `SERVER_RESTART_END`

## Applied Code Paths
Files:
1. `bot/ultimate_bot.py`:
   - Lua metadata build now stores normalized `end_reason`.
   - Stores `end_reason_raw` and derived `end_reason_display` in metadata payload.
   - `_store_lua_round_teams` normalizes end reason before DB write.
2. `bot/services/timing_debug_service.py`:
   - surrender-fix checks now use normalized end reason.
3. `bot/services/timing_comparison_service.py`:
   - end reason shown in embed is normalized enum value.

## Validation
Commands:
```bash
pytest -q tests/unit/test_round_contract.py tests/unit/test_gametime_synthetic_round.py
pytest -q tests/unit/test_timing_debug_service_session_join.py tests/unit/test_lua_webhook_diagnostics.py
```

Result:
1. normalization and comparison paths pass targeted tests.

## Runtime Proof (2026-02-12)
1. Hardened fallback ingest path to enforce same normalization as live bot path:
   - updated `scripts/backfill_gametimes.py` to apply:
     - `normalize_end_reason(...)`
     - `normalize_side_value(...)`
2. Added unit coverage:
   - `tests/unit/test_backfill_gametimes_contract.py` (`2 passed`)
3. Replayed fallback ingestion:
```text
PYTHONPATH=. python3 scripts/backfill_gametimes.py --path local_gametimes
[backfill] Done. processed=16 skipped=0
```
4. Post-run `lua_round_teams` distribution:
```text
NORMAL=15
SURRENDER=1
objective=1
```
5. Legacy residue check:
```text
Only non-normalized row is id=2, map_name=testmap_v130, captured_at=2026-01-24 (historical legacy test row).
```

## Decision
1. End-reason normalization policy is enforced on live and fallback ingest paths.
2. Remaining lowercase `objective` is isolated legacy data, not active-path behavior.
3. `WS0-004` is closed.
