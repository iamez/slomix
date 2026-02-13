# Evidence: WS1-007 Revalidation After Param Pack Fix
Date: 2026-02-12  
Workstream: WS1 (Webhook Pipeline Recovery)  
Task: `WS1-007`  
Status: `in_progress` (synthetic backfill validated; live consumer proof still pending)

## Goal
Prove WS1 health gate is passed on real rounds after `WS1-006`:
1. Two fresh rounds persist to `lua_round_teams`.
2. Timing consumers stop reporting `NO LUA DATA` for those rounds.

## Preconditions
- [x] `WS1-006` code path updated.
- [x] Bot runtime is up and local gametime backlog is available.
- [ ] Live round traffic available.

## Test Window
```text
start_utc=2026-02-12 10:31
end_utc=2026-02-12 10:31
session_id=88 (coverage check)
maps_tested=etl_adlernest,supply,etl_sp_delivery,te_escape2,et_brewdog,sw_goldrush_te
```

## Round Evidence Matrix
Fill one row per validated round (minimum 2 rounds: R1 + R2).

| Round Label | Map | Round # | STATS_READY Accepted | Lua Store Success | lua_round_teams Row Present | Timing Output Has Lua Data |
|---|---|---|---|---|---|---|
| Round A |  |  | pending | pending | pending | pending |
| Round B |  |  | pending | pending | pending | pending |

## Log Evidence
1. Server-side send evidence:
```text
PENDING
```

2. Bot-side acceptance/store evidence:
```text
PENDING
```

3. Negative check (no legacy error):
```text
PENDING
```

## DB Evidence
Before:
```text
lua_round_teams_count_before=1
latest_captured_at_before=2026-01-24 22:00:30.654712+00
```

After:
```text
lua_round_teams_count_after=11
latest_captured_at_after=2026-02-12 10:31:26.769391+00
delta=+10
```

Sample row dump for tested rounds:
```text
te_escape2  R1  round_id=9830  round_end=2026-02-11 21:40:03+00
te_escape2  R1  round_id=9827  round_end=2026-02-11 21:28:24+00
sw_goldrush_te R2 round_id=9838 round_end=2026-02-11 22:47:30+00
sw_goldrush_te R1 round_id=9837 round_end=2026-02-11 22:35:37+00
supply R2 round_id=9822 round_end=2026-02-11 21:02:02+00
supply R1 round_id=9835 round_end=2026-02-11 22:07:07+00
```

## Diagnostics Endpoint Evidence
```text
endpoint=/diagnostics/lua-webhook
timestamp=PENDING
response_excerpt=PENDING
```

## Consumer Validation
Timing services for tested rounds:

1. Timing comparison embed status:
```text
PENDING
```

2. Timing debug/session output:
```text
PENDING
```

Pass condition:
1. Tested rounds no longer show `NO LUA DATA`.

## Synthetic Revalidation Snapshot (No Live Match Required)
1. Ran:
   - `PYTHONPATH=. python3 scripts/backfill_gametimes.py --path local_gametimes`
2. Result:
```text
[backfill] Done. processed=10 skipped=0
```
3. Linkage quality:
```text
captured_at_day=2026-02-12, rows=10, linked=10
```
4. Coverage impact on `2026-02-11` R1/R2 rounds:
```text
before: rounds_without_lua=16/16
after:  rounds_without_lua=6/16
```
5. Remaining missing rounds on `2026-02-11`:
```text
etl_adlernest R2 (9819)
etl_sp_delivery R2 (9825)
te_escape2 R2 (9828)
te_escape2 R2 (9831)
et_brewdog R2 (9833)
supply R2 (9836)
```

## Synthetic Stats-File Injection Snapshot (No Live Server Changes)
1. Generated fake regular stats files by copying Feb 11 source files and renaming timestamps to current-time values:
   - manifest: `docs/evidence/2026-02-12_ws1_synthetic_stats_files_manifest.md`
2. Imported through normal bot path (`process_gamestats_file`) with corrected env path:
   - command runtime: `PYTHONPATH=.:bot`
   - result: `6/6` files imported successfully.
3. Round IDs created:
```text
9840 supply R1
9841 supply R2
9843 te_escape2 R1
9844 te_escape2 R2
9846 sw_goldrush_te R1
9847 sw_goldrush_te R2
```
4. Current Lua linkage for these injected rounds:
```text
all injected rounds = NO_LUA
```
5. Interpretation:
   - stats-file ingestion and R1/R2 pairing path can be tested without live players.
   - WS1 gate still needs Lua-side data for those rounds (`lua_round_teams` linkage) to clear `NO_LUA`.

## Synthetic End-to-End Snapshot (Stats + Gametime, No Live Server Changes)
1. Generated synthetic gametime payloads matched to injected rounds:
   - manifest: `docs/evidence/2026-02-12_ws1_synthetic_gametimes_manifest.md`
2. Backfill run:
   - `PYTHONPATH=. python3 scripts/backfill_gametimes.py --path local_gametimes`
   - result: `processed=16`, `skipped=0`
3. Lua linkage validation for injected rounds:
```text
9840 supply R1 -> HAS_LUA
9841 supply R2 -> HAS_LUA
9843 te_escape2 R1 -> HAS_LUA
9844 te_escape2 R2 -> HAS_LUA
9846 sw_goldrush_te R1 -> HAS_LUA
9847 sw_goldrush_te R2 -> HAS_LUA
```
4. Note:
   - `round_number=0` map-summary rows (`9842`, `9845`) remain `NO_LUA` by design.
5. Updated Lua table baseline:
```text
lua_round_teams_total=17
unlinked=1
```

## Synthetic Verification Run (Operator Trigger)
1. `processed_files` confirms all injected files imported successfully:
```text
2026-02-12-115656-supply-round-1.txt         success=true
2026-02-12-120856-supply-round-2.txt         success=true
2026-02-12-122156-te_escape2-round-1.txt     success=true
2026-02-12-123356-te_escape2-round-2.txt     success=true
2026-02-12-124656-sw_goldrush_te-round-1.txt success=true
2026-02-12-125856-sw_goldrush_te-round-2.txt success=true
```
2. Round integrity check (`rounds + player_comprehensive_stats + lua_round_teams`):
```text
9840 supply R1          player_rows=8  lua=HAS_LUA  end_reason=normal  lua_duration=560
9841 supply R2          player_rows=8  lua=HAS_LUA  end_reason=normal  lua_duration=520
9843 te_escape2 R1      player_rows=8  lua=HAS_LUA  end_reason=normal  lua_duration=290
9844 te_escape2 R2      player_rows=8  lua=HAS_LUA  end_reason=normal  lua_duration=300
9846 sw_goldrush_te R1  player_rows=8  lua=HAS_LUA  end_reason=normal  lua_duration=720
9847 sw_goldrush_te R2  player_rows=8  lua=HAS_LUA  end_reason=normal  lua_duration=690
```
3. Timing consumer check using `TimingComparisonService` direct data path:
```text
9840 supply R1         stats=562 lua=560 match=direct markers=[AL],[AX]
9841 supply R2         stats=562 lua=520 match=direct markers=[AL],[AX]
9843 te_escape2 R1     stats=287 lua=290 match=direct markers=[AL],[AX]
9844 te_escape2 R2     stats=287 lua=300 match=direct markers=[AL],[AX]
9846 sw_goldrush_te R1 stats=720 lua=720 match=direct markers=[AL],[AX]
9847 sw_goldrush_te R2 stats=655 lua=690 match=direct markers=[AL],[AX]
```
4. Decision:
   - Synthetic operator-triggered validation passes for import, Lua linkage, and timing consumer read path.

## Latest Coverage Recheck (2026-02-12 13:42 UTC)
1. Current round-to-Lua coverage snapshot:
```text
2026-02-12  rounds_total=9   rounds_without_lua=3
2026-02-11  rounds_total=16  rounds_without_lua=6
```
2. Interpretation:
   - Lua linkage coverage improved versus baseline, including newly injected synthetic rounds.
   - WS1 gate still requires live webhook round-pair proof on fresh play traffic.

## Synthetic Coverage Added (No Live Round Dependency)
1. Added `tests/unit/test_gametime_synthetic_round.py` to validate fallback ingestion path with synthetic payload.
2. The synthetic test confirms:
   - gametime payload parsing to canonical metadata,
   - round metadata handoff storage call,
   - spawn-stats extraction/storage call,
   - `_pending_round_metadata` key creation.
3. This reduces regression risk while waiting for fresh live rounds, but does not replace live DB persistence proof.

## Gate Script Recheck (2026-02-12 15:54 UTC)
1. Ran:
   - `bash docs/scripts/check_ws1_revalidation_gate.sh`
2. Latest map-pair readiness output includes READY synthetic pairs:
```text
2026-02-12-124656 sw_goldrush_te 9846/9847 READY
2026-02-12-122156 te_escape2      9843/9844 READY
2026-02-12-115656 supply          9840/9841 READY
```
3. Still-open NOT_READY pairs include recent synthetic malformed-side rounds and older real R2 gaps:
```text
2026-02-12-140101 supply 9852/9853 NOT_READY
2026-02-11-230709 supply 9835/9836 NOT_READY
2026-02-11-225211 et_brewdog 9832/9833 NOT_READY
2026-02-11-224006 te_escape2 9830/9831 NOT_READY
2026-02-11-221100 etl_sp_delivery 9824/9825 NOT_READY
```
4. Interpretation:
   - Storage + linkage path works for synthetic pairs.
   - WS1 live gate remains open because newest true-live R1/R2 traffic still has unresolved R2 gaps.

## Gate + Webhook Freshness Recheck (2026-02-12 16:35 UTC)
1. Ran:
   - `bash docs/scripts/check_ws1_revalidation_gate.sh`
   - `bash scripts/check_ws1_ws1c_gates.sh`
2. WS1 baseline remains unchanged:
```text
lua_round_teams_total=17
unlinked=1
latest_captured_at=2026-02-12 14:25:12.491762+00
```
3. Round linkage coverage recheck:
```text
2026-02-12  rounds_total=12  rounds_without_lua=6
2026-02-11  rounds_total=16  rounds_without_lua=6
```
4. Ready/not-ready snapshot:
```text
READY:    9840/9841, 9843/9844, 9846/9847, 9837/9838, 9821/9822
NOT_READY: 9852/9853, 9835/9836, 9832/9833, 9830/9831, 9827/9828, 9824/9825, 9818/9819
```
5. Webhook freshness evidence:
```text
last STATS_READY accepted in logs: 2026-02-11 23:47:30 (sw_goldrush_te R2)
store-success tail still repeats only: 2026-02-11-220202 R2
```
6. Row-level capture-time evidence:
```text
recent linked real rows (9818..9838) and synthetic rows (9840..9847) all show captured_at around 2026-02-12 14:25:12+00
```
7. Interpretation:
   - No fresh post-fix live webhook round-pair evidence exists yet.
   - Existing `HAS_LUA` expansion is still dominated by synthetic/backfill recovery runs.
   - WS1 gate remains open until new real live R1/R2 rounds are observed with accept->store->consume proof.

## Gate Decision
- [ ] WS1 health gate PASS
- [x] WS1 health gate FAIL (currently cannot be passed without fresh post-fix round evidence)

Decision notes:
```text
Synthetic replay/backfill now proves storage and round linking for 10 rows, but live runtime proof is still missing for:
1) webhook accept->store logs on new rounds
2) timing consumer output for those same fresh rounds
```

## Follow-up
If pass:
1. Set `WS1-007` -> `done`.
2. Unblock WS2 and WS3 tasks.

If fail:
1. Open next blocker with exact stage (`send`, `accept`, `store`, `link`, `consume`).
2. Keep WS2/WS3 blocked.
