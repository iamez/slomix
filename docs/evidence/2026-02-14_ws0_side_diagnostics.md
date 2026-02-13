# Evidence: WS0-006 Side-Field Diagnostics
Date: 2026-02-12  
Workstream: WS0 (Data Contract and Timing Correctness)  
Task: `WS0-006`  
Status: `done`

## Goal
Emit explicit diagnostics when `defender_team` / `winner_team` values are missing or malformed at import time.

## Code Changes
Files:
1. `bot/community_stats_parser.py`
2. `bot/ultimate_bot.py`

What changed:
1. Added `_parse_side_fields(header_parts)` helper in parser.
2. Parser now returns `side_parse_diagnostics` in parsed payload with:
   - `header_field_count`
   - `defender_team_raw`
   - `winner_team_raw`
   - `reasons` list
3. Parser emits `[SIDE DIAG]` warning lines when side fields are missing/invalid.
4. Import path (`_import_stats_to_database`) now:
   - consumes `side_parse_diagnostics`
   - tracks reason counters in `_side_diag_reason_counts`
   - emits importer-level `[SIDE DIAG]` warning with file/map/round/raw/final values and cumulative counts
   - records fallback reasons when R2 inherits missing sides from R1.

Reason codes currently emitted:
1. `defender_missing`
2. `defender_non_numeric`
3. `defender_out_of_range`
4. `winner_missing`
5. `winner_non_numeric`
6. `winner_out_of_range`
7. `defender_fallback_from_round1`
8. `winner_fallback_from_round1`
9. `defender_zero_final`
10. `winner_zero_final`

## Test Coverage
File:
1. `tests/unit/test_stats_parser.py`

Added tests:
1. `test_parse_side_fields_valid_values`
2. `test_parse_side_fields_missing_and_invalid`
3. `test_parse_side_fields_out_of_range`
4. `test_parse_regular_file_includes_side_diagnostics`

Validation command:
```bash
pytest -q tests/unit/test_stats_parser.py
```

Result:
1. `22 passed`

Extended regression:
```bash
pytest -q \
  tests/unit/test_stats_parser.py \
  tests/unit/test_lua_webhook_diagnostics.py \
  tests/unit/test_round_linker_reasons.py \
  tests/unit/test_timing_debug_service_session_join.py
```

Result:
1. `30 passed`

## Runtime Validation (Synthetic Malformed Headers)
1. Generated and imported three synthetic malformed-side files through normal import path:
   - `2026-02-12-130500-supply-round-1.txt` (missing defender/winner)
   - `2026-02-12-130700-supply-round-1.txt` (non-numeric defender/winner)
   - `2026-02-12-130900-supply-round-1.txt` (out-of-range defender + winner zero)
2. Parser-level warning evidence:
   - `[SIDE DIAG] ... reasons=defender_missing,winner_missing`
   - `[SIDE DIAG] ... reasons=defender_non_numeric,winner_non_numeric`
   - `[SIDE DIAG] ... reasons=defender_out_of_range`
3. Importer-level warning evidence with counters:
   - file `130500`: `counts={'defender_missing': 1, 'winner_missing': 1, 'winner_zero_final': 1}`
   - file `130700`: `counts={..., 'defender_non_numeric': 1, 'winner_non_numeric': 1}`
   - file `130900`: `counts={..., 'defender_out_of_range': 1}`
4. Persisted DB side values for injected rounds:
```text
9849 supply R1 defender=1 winner=0
9850 supply R1 defender=1 winner=0
9851 supply R1 defender=9 winner=0
```

## Closure Decision
1. Runtime logs now show explicit reason codes and cumulative counters for malformed side data.
2. WS0-006 is closed.
