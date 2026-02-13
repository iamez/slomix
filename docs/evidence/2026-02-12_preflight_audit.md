# Evidence: Preflight Dry-Run Audit
Date: 2026-02-12  
Purpose: Catch likely runtime failures before deployment/runtime windows.

## Scope
Ran focused regression checks for recently implemented WS0/WS1/WS1C/WS2/WS3/WS6/WS7 paths plus runtime smoke scripts.

## Commands Run
1. Python syntax compile:
```bash
python3 -m py_compile bot/ultimate_bot.py bot/community_stats_parser.py bot/core/round_linker.py bot/core/round_contract.py bot/services/timing_debug_service.py bot/services/timing_comparison_service.py bot/services/round_publisher_service.py bot/services/session_stats_aggregator.py bot/services/session_view_handlers.py website/backend/routers/api.py website/backend/services/greatshot_crossref.py postgresql_database_manager.py
```
2. Focused unit tests:
```bash
pytest -q tests/unit/test_lua_round_teams_param_packing.py tests/unit/test_gametime_synthetic_round.py tests/unit/test_round_linker_reasons.py tests/unit/test_timing_debug_service_session_join.py tests/unit/test_timing_comparison_service_side_markers.py tests/unit/test_round_publisher_team_grouping.py tests/unit/test_backfill_gametimes_contract.py tests/unit/proximity_sprint_pipeline_test.py tests/unit/test_greatshot_crossref.py tests/unit/test_greatshot_router_crossref.py tests/unit/test_greatshot_player_stats_enrichment.py tests/unit/test_kill_assists_visibility.py
```
3. WS7 runtime smoke:
```bash
bash docs/scripts/check_ws7_kill_assists_smoke.sh
```
4. WS1 gate snapshots:
```bash
bash docs/scripts/check_ws1_revalidation_gate.sh
PGPASSWORD='***' bash scripts/check_ws1_ws1c_gates.sh
```
5. Full production health script:
```bash
python3 check_production_health.py
```

## Results
1. Syntax compile: PASS
2. Focused unit tests: PASS (`28 passed`)
3. WS7 smoke: PASS
   - `last_session_ka_sum=427`
   - `graphs_ka_sum=427`
   - objectives embed contains `Kill Assists`
4. WS1/WS1C gate snapshot: PARTIAL
   - `lua_round_teams=17`, `unlinked=1`
   - coverage: `2026-02-12 => 12/6`, `2026-02-11 => 16/6` (total/without_lua)
   - no fresh live STATS_READY window for WS1 closure evidence
5. Production health script: PARTIAL (`5/6 passed`)
   - DB connection path now works in script
   - remaining hard fail: website import dependency (`No module named 'itsdangerous'`)
   - warnings: missing `gaming_sessions` table, website log file missing

## Checker Maintenance Patch Applied
Updated `check_production_health.py` to match current architecture:
1. Use `load_config()` + `create_adapter(...)` instead of removed `BOT_CONFIG`.
2. Open/close DB adapter correctly in health check.
3. Optional cog check fixed for renamed class (`SynergyAnalytics`) and non-fatal optional failures.

## Predicted Failure Risks (Current)
1. Website startup/import may fail in environments missing `itsdangerous`.
2. WS1 live gate remains at risk until fresh real R1/R2 webhook evidence is captured.
3. `gaming_sessions` table expectation in health check indicates schema drift or stale expectation and should be verified intentionally.

## Safe Mitigation Patch Applied
1. Added `itsdangerous>=2.2.0` to `requirements.txt` (tracked dependency source).
2. Updated `docs/LINUX_DEPLOYMENT_GUIDE.md` Step 6 to use `pip install -r requirements.txt` (prevents manual package drift).
3. No bot or website runtime logic was changed in this mitigation patch.

## Recommended Preflight Command (Repeatable)
```bash
pytest -q tests/unit/test_lua_round_teams_param_packing.py tests/unit/test_gametime_synthetic_round.py tests/unit/test_round_linker_reasons.py tests/unit/test_timing_debug_service_session_join.py tests/unit/test_timing_comparison_service_side_markers.py tests/unit/test_round_publisher_team_grouping.py tests/unit/test_backfill_gametimes_contract.py tests/unit/proximity_sprint_pipeline_test.py tests/unit/test_greatshot_crossref.py tests/unit/test_greatshot_router_crossref.py tests/unit/test_greatshot_player_stats_enrichment.py tests/unit/test_kill_assists_visibility.py && bash docs/scripts/check_ws7_kill_assists_smoke.sh && bash docs/scripts/check_ws1_revalidation_gate.sh && PGPASSWORD='***' bash scripts/check_ws1_ws1c_gates.sh && python3 check_production_health.py
```
