# Evidence: WS2-003 Lua Round-ID Backfill Dry Run
Date: 2026-02-12  
Workstream: WS2 (Timing Service Robustness)  
Task: `WS2-003`  
Status: `in_progress` (offline-executed, WS2 still gated by WS1 live source-health)

## Goal
Run and review a non-mutating backfill pass for `lua_round_teams.round_id` so linker health is known before apply mode.

## Command Run
```bash
PYTHONPATH=. python3 scripts/backfill_lua_round_ids.py --dry-run
```

Output:
```text
Backfill lua_round_teams.round_id done. scanned=1, updated=0, dry_run=True
```

## Baseline DB Snapshot (for dry-run interpretation)
Command:
```bash
psql ... -Atc "SELECT COUNT(*), COUNT(*) FILTER (WHERE round_id IS NULL), MAX(captured_at) FROM lua_round_teams;"
```

Result:
```text
1    1    2026-01-24 22:00:30.654712+00
```

Observed trend query (`last 14 days`):
1. `lua_round_teams` daily rows: empty result set.
2. `rounds_without_lua_by_day`:
   - `2026-02-11`: `16/16` missing Lua linkage
   - `2026-02-06`: `11/11`
   - `2026-02-04`: `1/1`
   - `2026-02-03`: `5/5`
   - `2026-02-02`: `22/22`

## Review Outcome
1. Dry run is safe and operational in current env.
2. Current candidate set is minimal and stale (`1` unlinked row, captured in January), so no updates were proposed.
3. Apply mode is intentionally deferred until fresh WS1 Lua ingestion exists or a controlled gametime backfill is approved.

## Next Step
1. Keep `WS2-004` pending.
2. Re-run this dry run immediately after first fresh `lua_round_teams` growth event.
