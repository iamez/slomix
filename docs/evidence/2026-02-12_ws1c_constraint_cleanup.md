# Evidence: WS1C-003 Proximity Constraint Cleanup
Date: 2026-02-12  
Workstream: WS1C (Proximity Reliability)  
Task: `WS1C-003`  
Status: `done` (targeted validation complete)

## Goal
Stop repeated duplicate-key import failures caused by legacy + new UNIQUE constraint overlap.

## Read-Only DB Inventory
Unique constraints currently present:

1. `player_track`
   - legacy: `session_date,round_number,player_guid,spawn_time_ms`
   - new: `session_date,round_number,round_start_unix,player_guid,spawn_time_ms`
2. `proximity_objective_focus`
   - legacy: `session_date,round_number,player_guid`
   - new: `session_date,round_number,round_start_unix,player_guid`

Baseline row counts:
1. `player_track`: `1525` rows for `2026-02-11`, `2022` total.
2. `proximity_objective_focus`: `8` rows for `2026-02-11`, `14` total.

## Code + Schema Alignment Changes
1. `proximity/parser/parser.py`
   - Updated objective-focus insert path (round_start-supported branch) to:
     - `ON CONFLICT (session_date, round_number, round_start_unix, player_guid) DO UPDATE ...`
2. `proximity/schema/schema.sql`
   - Updated `proximity_objective_focus` table UNIQUE key to:
     - `UNIQUE(session_date, round_number, round_start_unix, player_guid)`
3. `proximity/schema/migrations/2026-02-12_ws1c_constraint_cleanup.sql`
   - Added idempotent migration to:
     - drop legacy unique keys by column signature,
     - ensure canonical round_start_unix unique keys exist for both tables.

## Test Coverage
Added:
1. `tests/unit/test_proximity_parser_objective_conflict.py`
   - verifies parser uses round_start_unix conflict target when schema supports it.

Validation command:
```bash
pytest -q tests/unit/test_stats_parser.py::TestRound2CounterResetFallback::test_uses_r2_raw_when_player_counters_drop tests/unit/test_greatshot_crossref.py tests/unit/test_proximity_parser_objective_conflict.py
```

Result:
1. `4 passed`.

## Remaining Steps
1. Apply `proximity/schema/migrations/2026-02-12_ws1c_constraint_cleanup.sql` on DB. ✅
2. Re-run proximity import scan loop. ✅ (targeted on previously failing files)
3. Confirm duplicate-key spam for unchanged files is gone. ✅

## Runtime Validation Details
Migration apply:
1. First run failed due PostgreSQL `name[]` vs `text[]` signature comparison.
2. Migration patched to cast `att.attname::text` in all constraint-signature checks.
3. Re-run succeeded (`DO` x4).

Post-migration constraint state:
1. `player_track`: only `session_date,round_number,round_start_unix,player_guid,spawn_time_ms`.
2. `proximity_objective_focus`: only `session_date,round_number,round_start_unix,player_guid`.

Targeted re-import of historically failing files:
1. `2026-02-11-224003-te_escape2-round-1_engagements.txt` → `True`
2. `2026-02-11-224530-te_escape2-round-1_engagements.txt` → `True`
3. `2026-02-11-225553-et_brewdog-round-1_engagements.txt` → `True`

Idempotency check (second pass on same files):
1. All three re-imports returned `True`.
2. Counts unchanged before/after second pass:
   - `combat_engagement=3506`
   - `player_track=1645`
   - `proximity_objective_focus=8`
   - `proximity_trade_event=1845`
   - `proximity_support_summary=16`
