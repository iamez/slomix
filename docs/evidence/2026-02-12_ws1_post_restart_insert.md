# Evidence: WS1-005 Post-Restart Insert Path
Date: 2026-02-12  
Workstream: WS1 (Webhook Pipeline Recovery)  
Task: `WS1-005`  
Status: `done` (insert path verified on post-fix runtime replay + synthetic end-to-end flow)

## Goal
Verify Lua round rows are inserted after restart and linked to `rounds`.

## Baseline (Before)
```text
lua_round_teams_total=1
lua_round_teams_unlinked=1
latest_captured_at=2026-01-24 22:00:30.654712+00
```

## Action
1. Executed synthetic fallback ingestion using existing local payloads:
   - `PYTHONPATH=. python3 scripts/backfill_gametimes.py --path local_gametimes`
2. Script result:
```text
[backfill] Done. processed=10 skipped=0
```

## Validation (After)
```text
lua_round_teams_total=11
lua_round_teams_unlinked=1
latest_captured_at=2026-02-12 10:31:26.769391+00
```

Recent inserted rows (sample):
```text
te_escape2 R1 -> round_id=9830
te_escape2 R1 -> round_id=9827
sw_goldrush_te R2 -> round_id=9838
sw_goldrush_te R1 -> round_id=9837
supply R2 -> round_id=9822
supply R1 -> round_id=9835
supply R1 -> round_id=9821
etl_sp_delivery R1 -> round_id=9824
etl_adlernest R1 -> round_id=9818
et_brewdog R1 -> round_id=9832
```

7-day linkage check:
```text
2026-02-12    rows=10    linked=10
```

2026-02-11 coverage check:
```text
rounds_total=16
rounds_without_lua=6
```

## Decision
1. Insert path and linking are now proven on synthetic/local gametime replay.
2. Additional runtime evidence shows repeated successful store logs after fix (`💾 Stored Lua round data` on 2026-02-12).
3. WS1-005 closure is accepted because definition-of-done is met (`count` growth from `1` and fresh `captured_at` >= `2026-02-11`).
4. Remaining live-round gap is tracked under `WS1-007`, not this row.
