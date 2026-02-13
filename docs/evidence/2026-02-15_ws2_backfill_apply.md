# Evidence: WS2-004 Lua Round-ID Backfill Apply
Date: 2026-02-12  
Workstream: WS2 (Timing Linkage Hardening)  
Task: `WS2-004`  
Status: `in_progress` (apply executed; no reducible matches in current unlinked set)

## Goal
Run apply-mode backfill for `lua_round_teams.round_id` and reduce unlinked rows with auditable before/after evidence.

## Baseline (Before Apply)
```text
lua_round_teams_total=17
lua_round_teams_unlinked=1
latest_captured_at=2026-02-12 11:11:23.83779+00
```

Remaining unlinked row:
```text
id=2
map_name=testmap_v130
round_number=1
round_start_unix=1737752000
round_end_unix=1737752480
captured_at=2026-01-24 22:00:30.654712+00
```

## Apply Execution
Command:
```bash
PYTHONPATH=. python3 scripts/backfill_lua_round_ids.py
```

Output:
```text
Backfill lua_round_teams.round_id done. scanned=1, updated=0, dry_run=False
```

## Post-Apply Validation
```text
lua_round_teams_total=17
lua_round_teams_unlinked=1
latest_captured_at=2026-02-12 11:11:23.83779+00
```

Candidate check:
```text
rounds WHERE map_name='testmap_v130' => 0 rows
```

## Interpretation
1. Apply-mode job executed successfully.
2. No rows were updated because the only unlinked record has no candidate round in `rounds`.
3. Current unlinked row appears to be legacy test data and is not resolvable via automated linker rules.

## Command Log
```bash
/bin/bash -lc "PGPASSWORD='REDACTED_DB_PASSWORD' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy -F $'\t' -Atc \"SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE round_id IS NULL) AS unlinked, COALESCE(MAX(captured_at)::text,'NULL') AS latest FROM lua_round_teams;\""
/bin/bash -lc "PGPASSWORD='REDACTED_DB_PASSWORD' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy -F $'\t' -Atc \"SELECT id, map_name, round_number, round_start_unix, round_end_unix, captured_at FROM lua_round_teams WHERE round_id IS NULL ORDER BY id DESC LIMIT 10;\""
PYTHONPATH=. python3 scripts/backfill_lua_round_ids.py
/bin/bash -lc "PGPASSWORD='REDACTED_DB_PASSWORD' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy -F $'\t' -Atc \"SELECT COUNT(*) FROM rounds WHERE map_name='testmap_v130';\""
```

## Next Step
1. Keep `WS2-004` open until WS1 live gate passes and new unlinked rows (if any) can be evaluated in a real-round window.
