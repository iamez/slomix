# WS1C-002 Proximity Round-Number Semantics Validation

Date: 2026-02-12
Owner: Codex execution
Status: done

## Scope
Validate whether proximity file/header round metadata can represent round 2 correctly and, if not, normalize before import.

## Findings
1. Raw proximity headers can report `# round=1` even when Lua gametimes identifies the round as `R2`.
2. Concrete mismatches found in local data:
   - `2026-02-11-220202-supply-round-1_engagements.txt`
     - proximity header: `round=1`
     - matching gametime file by `map + round_end_unix`: `gametime-supply-R2-1770843722.json`
   - `2026-02-11-234730-sw_goldrush_te-round-1_engagements.txt`
     - proximity header: `round=1`
     - matching gametime file: `gametime-sw_goldrush_te-R2-1770850050.json`

## Implementation
Updated `proximity/parser/parser.py`:
1. Added round normalization step after parsing header metadata.
2. Normalization precedence:
   - `gametime` file match on `map_name + round_end_unix` (authoritative when available)
   - filename fallback (`-round-N_engagements.txt`)
   - header value fallback
   - default `1` if unset/invalid
3. Added `round_num_source` metadata marker (`gametime`, `filename`, `header`, `default`).
4. Reset parser metadata per file to avoid stale values carrying across imports.
5. Updated `bot/cogs/proximity_cog.py` to pass configured `gametimes_local_path` into parser (`gametimes_dir=...`) instead of assuming the default path.

## Tests
Added `tests/unit/test_proximity_round_number_normalization.py`:
1. `test_round_normalization_prefers_matching_gametime_round`
2. `test_round_normalization_falls_back_to_filename_when_gametime_missing`

Validation run:
1. `pytest -q tests/unit/test_proximity_round_number_normalization.py tests/unit/test_proximity_parser_objective_conflict.py`
2. Result: `3 passed`

## Outcome
WS1C-002 done: R2 semantic mismatch is confirmed and normalized before analytics/import writes.
