# Evidence: WS0-002 Score Confidence Contract
Date: 2026-02-12  
Workstream: WS0 (Score Truth Chain)  
Task: `WS0-002`  
Status: `done`

## Goal
Define and consume explicit score confidence states.

## Contract States
Helper:
1. `bot/core/round_contract.py::score_confidence_state`

States:
1. `verified_header` - valid winner/defender values from direct parse with no parse anomalies.
2. `time_fallback` - values are valid but derived via fallback path (non-primary source).
3. `ambiguous` - malformed side fields (e.g., non-numeric/out-of-range) or conflicting parse evidence.
4. `missing` - unresolved winner/defender (unknown final side).

## Consumption Points
Files:
1. `bot/community_stats_parser.py`
2. `bot/ultimate_bot.py`
3. `bot/services/round_publisher_service.py`

Applied behavior:
1. Parser payload now includes `score_confidence`.
2. Importer recalculates final confidence after R2 fallback logic and emits `[SIDE DIAG]` logs.
3. Round publisher includes `Score Confidence` in post description when present.

## Validation
Commands:
```bash
pytest -q tests/unit/test_round_contract.py tests/unit/test_stats_parser.py
pytest -q tests/unit/test_lua_round_teams_param_packing.py tests/unit/test_lua_webhook_diagnostics.py
```

Result:
1. all targeted tests passed.

## Runtime Proof (2026-02-12)
1. Applied migration for persistence columns:
   - `migrations/012_add_round_contract_columns.sql`
2. Imported fresh synthetic rounds post-migration:
```text
9852 supply R1 score_confidence=verified_header
9853 supply R2 score_confidence=verified_header
9854 supply R1 score_confidence=ambiguous
```
3. Current DB distribution in `rounds`:
```text
ambiguous=1
verified_header=2
NULL=1691 (historical rows before migration)
```

## Decision
1. Confidence states are defined and consumed in parser/import/publisher paths.
2. Confidence is now persisted in `rounds` for new imports.
3. `WS0-002` is closed.
