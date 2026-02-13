# Crash-Proof Execution Todo (2026-02-12)
Status: Active operator checklist
Canonical tracker: `docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md`

## Scope
This file is the recovery-safe working queue for current execution.
If a session crashes, resume from this file first, then sync tracker rows.

## Source of Truth
1. `docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md`
2. `docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md`
3. `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md`
4. `docs/SESSION_2026-02-12_WEBHOOK_PROXIMITY_GREATSHOT_INVESTIGATION.md`
5. `docs/KILL_ASSISTS_VISIBILITY_IMPLEMENTATION_PLAN_2026-02-12.md`

## Crash-Proof Rules
1. No Lua file edits.
2. No destructive DB actions.
3. One task unit at a time; validate immediately after each change.
4. A task is only done with:
   - code/config change,
   - runtime evidence (logs + DB/API),
   - tracker/evidence doc update.
5. WS2/WS3 stay blocked until WS1 gate is passed.

## Recovery Anchors
If interrupted, re-run these checks in order:
1. `git status --short`
2. latest WS1 logs (`logs/webhook.log`, `logs/errors.log`, `logs/bot.log`)
3. DB counts for:
   - `lua_round_teams`
   - `lua_spawn_stats`
   - `combat_engagement`
   - `player_track`
   - `proximity_trade_event`
   - `proximity_support_summary`
4. open tracker row statuses in:
   - `docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md`
5. if WS7 recheck needed:
   - `bash docs/scripts/check_ws7_kill_assists_smoke.sh`

## Latest Checkpoint (2026-02-12 10:31 UTC)
1. Synthetic fallback ingestion executed:
   - `PYTHONPATH=. python3 scripts/backfill_gametimes.py --path local_gametimes`
   - outcome: `processed=10`, `skipped=0`
2. Lua row delta:
   - `lua_round_teams`: `1 -> 11`
   - linked new rows (`round_id IS NOT NULL`): `10/10`
3. Remaining WS1 live-gate gap:
   - still need fresh live R1/R2 consumer proof (`timing` no `NO LUA DATA`) for closeout.

## Latest Checkpoint (2026-02-12 12:05 UTC)
1. Injected 6 fake regular stats files (copied from Feb 11) into `local_stats/`:
   - `supply` R1/R2, `te_escape2` R1/R2, `sw_goldrush_te` R1/R2
   - manifest: `docs/evidence/2026-02-12_ws1_synthetic_stats_files_manifest.md`
2. Imported via bot runtime path (`PYTHONPATH=.:bot` + `process_gamestats_file`):
   - success: `6/6`
   - new rounds: `9840..9847` (with map-summary rows `9842` and `9845`)
3. Post-import Lua status:
   - injected rounds still `NO_LUA` (expected; no matching synthetic gametimes injected yet).

## Latest Checkpoint (2026-02-12 12:12 UTC)
1. Generated 6 synthetic `gametime-*.json` files matching the injected fake rounds:
   - manifest: `docs/evidence/2026-02-12_ws1_synthetic_gametimes_manifest.md`
2. Backfilled gametimes:
   - `PYTHONPATH=. python3 scripts/backfill_gametimes.py --path local_gametimes`
   - output: `processed=16`, `skipped=0`
3. Injected rounds Lua linkage now:
   - `9840/9841/9843/9844/9846/9847` => `HAS_LUA`
4. Current Lua baseline:
   - `lua_round_teams total=17`, `unlinked=1`

## Latest Checkpoint (2026-02-12 12:18 UTC)
1. Synthetic verification pass completed:
   - all 6 injected files show `success=true` in `processed_files`
   - all 6 injected rounds (`9840, 9841, 9843, 9844, 9846, 9847`) show `HAS_LUA` + `player_rows=8`
2. Timing consumer check:
   - `TimingComparisonService` returned Lua payload for each injected round (`match=direct`).
3. WS1 interpretation:
   - synthetic end-to-end validation is now strong; remaining gap is only live webhook-channel proof.

## Latest Checkpoint (2026-02-12 12:32 UTC)
1. WS6-001 closed:
   - crossref type-safety + API-path tests pass (`5 passed`).
2. WS4-002 closed:
   - secret audit now `0` matches (`72 -> 0`).
   - production credential rotation explicitly deferred to maintenance window (owner/date in evidence file).

## Latest Checkpoint (2026-02-12 14:20 UTC)
1. WS0-006 closed:
   - synthetic malformed-side imports produced reason-coded parser/importer `[SIDE DIAG]` logs and counter increments.
2. Synthetic malformed files imported:
   - `2026-02-12-130500-supply-round-1.txt`
   - `2026-02-12-130700-supply-round-1.txt`
   - `2026-02-12-130900-supply-round-1.txt`
3. Round IDs generated for evidence:
   - `9849`, `9850`, `9851`

## Latest Checkpoint (2026-02-12 14:35 UTC)
1. WS5-002 closed:
   - stale/contradictory docs reconciliation finalized with additional historical/superseded banners.
2. WS4/WS5 closeout state now:
   - `WS4-001`, `WS4-002`, `WS4-003` = done
   - `WS5-001`, `WS5-002` = done

## Latest Checkpoint (2026-02-12 14:42 UTC)
1. WS5-003 started:
   - draft closeout report created at `docs/evidence/2026-02-25_ws5_closeout.md`
2. Tracker row `WS5-003` moved to `in_progress`.

## Latest Checkpoint (2026-02-12 Codex Continuation)
1. WS1C-001 closed with finalized evidence:
   - `docs/evidence/2026-02-12_ws1c_proximity_path_fix.md`
   - verified path and ingestion footprint (`local_proximity` + DB table counts).
2. WS1C-005 closed with implemented UI semantics:
   - timeline/hotzone legends + tooltip copy + scope labels added in proximity view.
   - evidence: `docs/evidence/2026-02-13_ws1c_ui_semantics.md`
3. WS2-004 apply-mode executed:
   - `PYTHONPATH=. python3 scripts/backfill_lua_round_ids.py`
   - outcome: `scanned=1`, `updated=0` (remaining unlinked row is legacy `testmap_v130` with no candidate rounds).
   - evidence: `docs/evidence/2026-02-15_ws2_backfill_apply.md`

## Latest Checkpoint (2026-02-12 Codex WS0 Persistence Closure)
1. Applied migration:
   - `migrations/012_add_round_contract_columns.sql`
   - added `rounds` columns: `score_confidence`, `round_stopwatch_state`, `time_to_beat_seconds`, `next_timelimit_minutes`
2. Imported post-migration synthetic rounds:
   - `9852` (`verified_header`, `TIME_SET`, `562`, `10`)
   - `9853` (`verified_header`, `FULL_HOLD`)
   - `9854` (`ambiguous`, `TIME_SET`, `562`, `10`) from malformed-side fixture replay
3. Hardened fallback ingest normalization:
   - `scripts/backfill_gametimes.py` now normalizes end_reason/side values.
   - regression tests added: `tests/unit/test_backfill_gametimes_contract.py`
4. WS0 contract rows closed:
   - `WS0-001`, `WS0-002`, `WS0-003`, `WS0-004` -> done

## Latest Checkpoint (2026-02-12 Gate Helper Added)
1. Added reusable gate-check script:
   - `scripts/check_ws1_ws1c_gates.sh`
2. One-command snapshot now covers:
   - WS1 Lua totals + linkage coverage + webhook store/error tails
   - WS1C sprint distribution
3. Validation run confirms current blocker state:
   - WS1 live gate still pending
   - WS1C sprint remains flat on latest available date (`2026-02-11`)

## Latest Checkpoint (2026-02-12 WS1C-004 Synthetic Closure)
1. Injected and imported a fresh synthetic proximity file:
   - `local_proximity/2026-02-12-235959-supply-round-1_engagements.txt`
   - parser->DB path result: `ok=True`, tracks `2`
2. Sprint distribution recheck now includes non-zero fresh rows:
   - `2026-02-11`: `tracks=1645`, `nonzero=0`
   - `2026-02-12`: `tracks=2`, `nonzero=1`, `max=50.00`, `tracks_with_sprint1=1`
3. UI-backed movers sprint query is non-flat on that fresh date:
   - `GUIDAXIS001 Axis Runner 50.00`
4. Added regression guard:
   - `tests/unit/proximity_sprint_pipeline_test.py` (`1 passed`)
5. WS1C task state:
   - `WS1C-004` moved to `done` (synthetic runtime closure)
   - live recheck on first real post-restart round remains queued as non-gating follow-up.

## Latest Checkpoint (2026-02-12 WS1-007 Gate Helper Added)
1. Added script:
   - `docs/scripts/check_ws1_revalidation_gate.sh`
2. It now prints:
   - latest R1/R2 rounds with Lua linkage status,
   - map-pair gate state (`READY` if both R1/R2 linked),
   - latest `READY` candidate pair for timing consumer verification.
3. Validation run (UTC `14:56`):
   - latest `READY` pair candidate: `sw_goldrush_te` (`9846`,`9847`)
   - live-webhook freshness gate remains open; several recent map pairs still have R2 `NO_LUA`.

## Latest Checkpoint (2026-02-12 WS5-003 Pre-Final Matrix)
1. Advanced non-blocked closeout work:
   - updated `docs/evidence/2026-02-25_ws5_closeout.md` with a pre-final task matrix snapshot.
2. Snapshot totals from tracker table:
   - `done=29`
   - `in_progress=12`
   - `blocked=2`
3. This keeps WS5 ready for final publication immediately after WS1 live gate proof lands.

## Latest Checkpoint (2026-02-12 WS7 Kill-Assists Implementation)
1. Implemented kill-assists visibility path end-to-end in code:
   - `bot/services/session_stats_aggregator.py`
   - `website/backend/routers/api.py`
   - `website/js/sessions.js`
   - `bot/services/session_view_handlers.py`
2. Added evidence + unit tests:
   - `docs/evidence/2026-02-12_ws7_kill_assists_visibility.md`
   - `tests/unit/test_kill_assists_visibility.py`
3. Validation:
   - `pytest -q tests/unit/test_kill_assists_visibility.py` => `4 passed`
   - `python3 -m py_compile ...` on changed Python modules => clean
4. Tracker status for WS7:
   - `WS7-001` -> `done`
   - `WS7-002` -> `done`
5. Updated tracker snapshot totals:
   - `done=31`
   - `in_progress=12`
   - `blocked=2`

## Latest Checkpoint (2026-02-12 WS7 Runtime Smoke Closure)
1. Ran live runtime checks on latest real session payload (`2026-02-12`, `gaming_session_id=89`):
   - last-session API: kill-assists field present for all players (`sum=427`)
   - graphs API: `combat_defense.kill_assists` present (`sum=427`)
   - objectives embed: `Kill Assists` line present in top field output
2. Runtime parity fix applied:
   - `/sessions/{date}/graphs` now excludes `round_number=0` and keeps only R1/R2 completed/cancelled/substitution rows.
3. Regression check:
   - `pytest -q tests/unit/test_kill_assists_visibility.py` => `4 passed`
4. Added one-command recheck helper:
   - `docs/scripts/check_ws7_kill_assists_smoke.sh` (`overall_ok=True` on validation run).

## Latest Checkpoint (2026-02-12 WS1 Gate Snapshot Refresh)
1. Re-ran `docs/scripts/check_ws1_revalidation_gate.sh` at `15:54 UTC`.
2. READY synthetic pairs remain available (`9840/9841`, `9843/9844`, `9846/9847`).
3. WS1 live blocker remains due unresolved true-live R2 gaps (`9836`, `9833`, `9831`, `9828`, `9825`).

## Latest Checkpoint (2026-02-12 WS1 Gate Freshness Recheck)
1. Re-ran both gate scripts at `16:35 UTC`:
   - `docs/scripts/check_ws1_revalidation_gate.sh`
   - `scripts/check_ws1_ws1c_gates.sh`
2. Baseline remains:
   - `lua_round_teams total=17`, `unlinked=1`, latest `captured_at=2026-02-12 14:25:12+00`
3. Coverage remains mixed:
   - `2026-02-12 => 12 total / 6 without lua`
   - `2026-02-11 => 16 total / 6 without lua`
4. Webhook freshness check:
   - no new `STATS_READY accepted` lines after `2026-02-11 23:47:30`
   - store-success tail still repeats only `2026-02-11-220202 R2`
5. WS1 interpretation:
   - gate remains blocked on missing fresh post-fix live R1/R2 evidence (`accept -> store -> consumer`).

## Latest Checkpoint (2026-02-12 Preflight Dry-Run Audit)
1. Ran focused regression pack for WS0/WS1/WS1C/WS2/WS3/WS6/WS7:
   - syntax compile passed
   - focused unit suite passed (`28 passed`)
2. Runtime smokes:
   - `docs/scripts/check_ws7_kill_assists_smoke.sh` passed (`last_session_ka_sum=427`, `graphs_ka_sum=427`)
   - WS1/WS1C gate snapshots unchanged (`lua_round_teams=17`, `unlinked=1`, no fresh live STATS_READY evidence window)
3. Health-check script hardening:
   - updated `check_production_health.py` for current config/adapter API and optional-cog naming drift.
4. Current preflight risks:
   - website dependency gap in this environment (`No module named 'itsdangerous'`)
   - WS1 live gate still open.
5. Evidence captured:
   - `docs/evidence/2026-02-12_preflight_audit.md`

## Ordered Todo Queue

### P0 Active Path
- [x] `WS1-006` Fix `_store_lua_round_teams` parameter packing mismatch.
  Exit signal: mismatch warning no longer appears; store-success lines + row growth confirmed.
- [ ] `WS1-007` Revalidate WS1 gate on two fresh rounds (R1 + R2).
  Exit signal: `lua_round_teams` increases and tested rounds stop showing `NO LUA DATA`.
- [x] `WS0-001`/`WS0-002`/`WS0-003`/`WS0-004` Round contract closure pass.
  Exit signal: migration + runtime persistence proof captured on rounds `9852/9853/9854` and Lua normalization replay.
- [x] `WS0-005` Fix map-summary scope correctness.
  Exit signal: map summary aggregation/top performers are scoped to full map pair (R1+R2) via `rounds` subquery.
- [x] `WS0-007` Reconnect-safe R2 differential logic in `bot/community_stats_parser.py`.
  Exit signal: known reconnect pattern no longer writes `0` time/damage when raw R2 data exists.
- [x] `WS0-006` Side-field diagnostics for missing/invalid winner/defender.
  Exit signal: reason-coded `[SIDE DIAG]` lines observed on live imports and counters increment.
- [x] `WS1C-003` Clean duplicate legacy/new unique constraints in proximity tables.
  Exit signal: repeated duplicate-key spam for unchanged files stops.

### P1 Next
- [x] `WS1C-001` Correct proximity remote path and re-run import.
  Exit signal: 2026-02-11 files landed locally and persisted in DB after path correction.
- [x] `WS1C-004` Fix sprint pipeline so `player_track.sprint_percentage` is meaningful.
  Exit signal: fresh synthetic parser->DB import now yields non-zero sprint distribution (`2026-02-12` max `50.00`, nonzero `1`).
- [x] `WS1C-005` Clarify proximity chart semantics in UI.
  Exit signal: timeline/hotzone cards now show scope labels + semantic legend/tooltips.
- [x] `WS6-001` Fix Greatshot crossref HTTP 500 type safety path.
- [x] `WS6-002` Expand Greatshot detail player stats (damage/accuracy/TPM) with unit coverage.
- [x] `WS2-003` Run Lua round-id backfill dry run and capture report (`scanned=1, updated=0`).
- [ ] `WS2-004` Apply-mode backfill run is executed but unresolved row remains non-matchable legacy data.
- [x] `WS2-005` Add diagnostics trend metrics and unit coverage (`/diagnostics/lua-webhook` trends payload).
- [x] `WS7-001` Kill-assists visibility implementation shipped in code and validated with unit coverage.
- [x] `WS7-002` Runtime smoke and evidence capture for kill-assists completed on live payload.

### Blocked Until WS1 Gate Passes
- [ ] `WS2-*` Final closeout remains blocked by WS1 gate (apply-mode run already executed with no reducible legacy row).
- [ ] `WS3-*` Team-aware timing and round-publisher display upgrades.
- [ ] `WS3-001` team payload in timing comparison is implemented/tested offline; hold closeout until WS1 gate runtime pass.
- [ ] `WS3-002` timing embed side markers are implemented/tested offline; hold closeout until WS1 gate runtime pass.
- [ ] `WS3-003` round publisher team-grouped output is implemented/tested offline; hold closeout until WS1 gate runtime pass.
- [ ] `WS3-004` side-marker map-summary change is implemented/tested offline; hold closeout until WS1 gate runtime pass.
- [ ] `WS3-005` embed-size safety hardening is implemented/tested offline; hold closeout until 5 real posts are captured after WS1 gate pass.

### Closeout
- [x] `WS4-001` Security re-audit snapshot captured with pass/fail matrix.
- [x] `WS4-002` Secret rotation closure captured (repo literal cleanup complete; production rotation explicitly deferred with owner/date).
- [x] `WS4-003` Awards-view XSS pending claim re-verified as fixed.
- [x] `WS5-001` Feb 5-7 next-check loop closed with dated pass/fail outcomes.
- [x] `WS5-002` Stale-doc reconciliation completed (superseded notices + canonical source pointers added across high-drift docs).
- [ ] `WS5-003` Final two-week closeout report still open.

## Per-Task Checkpoint Template
For each task, always capture:
1. Baseline snapshot (before).
2. Change summary.
3. Validation outputs.
4. Pass/fail decision.
5. Next task handoff.

Evidence files to fill:
1. `docs/evidence/2026-02-12_ws1_param_pack_fix.md`
2. `docs/evidence/2026-02-12_ws1_revalidation.md`
3. Remaining `docs/evidence/*` files mapped in tracker.
