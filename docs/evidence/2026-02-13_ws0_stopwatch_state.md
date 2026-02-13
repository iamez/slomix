# Evidence: WS0-003 Stopwatch Timing State Contract
Date: 2026-02-12  
Workstream: WS0 (Score Truth Chain)  
Task: `WS0-003`  
Status: `done`

## Goal
Define stopwatch contract fields so round timing semantics are explicit.

## Contract Fields
Helper:
1. `bot/core/round_contract.py::derive_stopwatch_contract`

Fields:
1. `round_stopwatch_state` (`FULL_HOLD` | `TIME_SET` | `None`)
2. `time_to_beat_seconds`
3. `next_timelimit_minutes`

## Current Rule Set
1. If `end_reason` is non-normal (`SURRENDER`, map/server interruptions), stopwatch state is not forced from timing.
2. For normal ends:
   - `FULL_HOLD` when actual duration is at/near timelimit.
   - `TIME_SET` when attackers complete significantly before timelimit.
3. For Round 1 `TIME_SET`, compute `time_to_beat_seconds` and `next_timelimit_minutes`.

## Consumption Points
Files:
1. `bot/community_stats_parser.py` (stats-file parse payloads)
2. `bot/ultimate_bot.py` (Lua metadata build + importer fallback fill)
3. `tests/unit/test_round_contract.py`

## Validation
Command:
```bash
pytest -q tests/unit/test_round_contract.py tests/unit/test_gametime_synthetic_round.py
```

Result:
1. stopwatch contract derivation paths passed.

## Runtime Proof (2026-02-12)
1. Added persistence columns to `rounds`:
   - `round_stopwatch_state`
   - `time_to_beat_seconds`
   - `next_timelimit_minutes`
   - via `migrations/012_add_round_contract_columns.sql`
2. Imported fresh synthetic rounds post-migration:
```text
9852 supply R1 state=TIME_SET  time_to_beat_seconds=562 next_timelimit_minutes=10
9853 supply R2 state=FULL_HOLD time_to_beat_seconds=NULL next_timelimit_minutes=NULL
9854 supply R1 state=TIME_SET  time_to_beat_seconds=562 next_timelimit_minutes=10
```
3. Current DB contract presence:
```text
round_stopwatch_state: FULL_HOLD=1, TIME_SET=2
time_to_beat_seconds non-null rows=2
next_timelimit_minutes non-null rows=2
```

## Decision
1. Stopwatch contract is defined, consumed, and persisted for new rounds.
2. `WS0-003` is closed.
