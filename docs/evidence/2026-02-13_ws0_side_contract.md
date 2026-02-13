# Evidence: WS0-001 Canonical Side Contract
Date: 2026-02-12  
Workstream: WS0 (Score Truth Chain)  
Task: `WS0-001`  
Status: `done`

## Goal
Freeze one canonical side contract for all ingest and display layers.

## Canonical Side Values
1. `1` = Axis
2. `2` = Allies
3. `0` = Unknown/Draw

## Mapping Rules
Normalization helper:
1. `bot/core/round_contract.py::normalize_side_value`

Accepted aliases:
1. `axis`, `"1"` -> `1`
2. `allies`, `"2"` -> `2`
3. `draw`, `unknown`, `"0"` -> `0`

## Parser/Importer Mapping Points
Files:
1. `bot/community_stats_parser.py`
2. `bot/ultimate_bot.py`

Applied behavior:
1. Stats parser keeps raw header values for diagnostics and also exposes normalized side values.
2. Lua metadata ingest normalizes winner/defender before persistence into `lua_round_teams`.
3. Import path logs side diagnostics and computes confidence state from canonical values.

## Validation
Command:
```bash
pytest -q tests/unit/test_round_contract.py tests/unit/test_stats_parser.py
```

Result:
1. side normalization + parser integration tests passed.

## Notes
1. Historical rows may still contain pre-contract values; this contract is enforced on new ingestion paths in code.

## Runtime Proof (2026-02-12)
1. Added WS0 persistence migration:
   - `migrations/012_add_round_contract_columns.sql`
2. Imported fresh synthetic rounds after migration:
   - `2026-02-12-140101-supply-round-1.txt` -> `round_id=9852`
   - `2026-02-12-140901-supply-round-2.txt` -> `round_id=9853`
   - malformed-side fixture `2026-02-12-141501-supply-round-1.txt` -> `round_id=9854`
3. Persisted side values in `rounds`:
```text
9852 supply R1 defender=1 winner=2
9853 supply R2 defender=1 winner=1
9854 supply R1 defender=9 winner=0
```
4. Lua side range validation after normalization backfill:
```text
lua_round_teams bad_winner=0 bad_defender=0 total=17
```

## Decision
1. Canonical side contract is defined and active in parser/import/runtime paths.
2. New rows persist expected side mappings and diagnostics behavior.
3. `WS0-001` is closed.
