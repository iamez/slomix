# Timing Shadow Handoff - 2026-02-18

## Objective
Fix incorrect/corrupt `time_dead` and `time_denied` in:
1. `!last_session`
2. `!last_session time`
3. `!last_session graphs`

Strategy shipped: OLD and NEW timing run in parallel behind `SHOW_TIMING_DUAL`, with dual display enabled in production for the test window.

## Mandatory Docs Sync Completed
Reviewed before implementation:
1. `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md`
2. `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md`

Referenced-doc rename/successor notes captured in:
1. `docs/reports/TIMING_SHADOW_INVESTIGATION_2026-02-18.md`

## What Was Implemented

### 1) New timing shadow computation service
Added:
1. `bot/services/session_timing_shadow_service.py`

Key behavior:
1. Computes OLD and NEW per-player/per-round timing in one pass.
2. `new_dead` uses `lua_spawn_stats.dead_seconds` joined by `(round_id, guid_prefix[:8])`.
3. `new_denied` is a deterministic projection from old denied-rate onto new active time.
4. Invariants enforced:
   - non-negative values
   - capped to plausible bounds
   - explicit fallback path when Lua telemetry is missing
5. Structured logs emitted with coverage/fallback metadata.
6. CSV debug artifacts written to `logs/timing_shadow/`.

### 2) Dual-output feature flag wiring
Flag:
1. `SHOW_TIMING_DUAL` in `bot/config.py` (`show_timing_dual`)

Dual display integrated into:
1. `bot/services/session_embed_builder.py` (`!last_session` overview)
2. `bot/services/session_view_handlers.py` (`!last_session time`)
3. `bot/services/session_graph_generator.py` (`!last_session graphs`)
4. `bot/cogs/last_session_cog.py` and `bot/cogs/session_cog.py` (service wiring)

### 3) Admin debug command
Added:
1. `!last_session_debug` (aliases: `last_debug`, `ls_debug`) in `bot/cogs/last_session_cog.py`

Purpose:
1. Admin-only compact diff summary for top OLD vs NEW timing deltas.

## Old vs New Data Sources

### OLD path (legacy)
1. `player_comprehensive_stats.time_dead_minutes` (converted/capped)
2. `player_comprehensive_stats.denied_playtime`

### NEW shadow path
1. `lua_spawn_stats.dead_seconds`
2. `lua_round_teams.actual_duration_seconds` for plausibility capping
3. Existing round/session joins for correlation context

## Root Cause Summary
Timing corruption exposure came from combined factors:
1. Legacy persisted timing fields with known parser/round-transition edge cases.
2. Partial Lua telemetry coverage in historical windows forcing fallback onto legacy values.
3. Direct display of legacy fields without side-by-side validation.

Full investigation details are in:
1. `docs/reports/TIMING_SHADOW_INVESTIGATION_2026-02-18.md`

## Production Enablement Status

### Flag state
1. `.env:139` contains `SHOW_TIMING_DUAL=true`

### Service runtime
Checked via:
1. `systemctl status etlegacy-bot --no-pager`

Observed:
1. `etlegacy-bot.service` is `active (running)`
2. Active since `Wed 2026-02-18 21:37:07 CET`
3. Main process: `/home/samba/share/slomix_discord/venv/bin/python3 bot/ultimate_bot.py`

Operator note:
1. Service restart was performed manually after flag enable.

## Evidence Bundle (Code + Logs + DB/API)

### Runtime/DB comparison artifacts
Generated CSV artifacts:
1. `logs/timing_shadow/timing_shadow_9855_9871_12r_20260218_203123.csv` (session 89)
2. `logs/timing_shadow/timing_shadow_9818_9838_16r_20260218_203123.csv` (session 88)
3. `logs/timing_shadow/timing_shadow_9805_9812_5r_20260218_203123.csv` (session 84; fallback coverage test)

### Test verification (latest local run)
Command run:
1. `pytest -q tests/unit/test_session_timing_shadow_service.py tests/unit/test_session_embed_builder_timing_dual.py tests/unit/test_timing_comparison_service_side_markers.py tests/unit/test_timing_debug_service_session_join.py`

Result:
1. `6 passed in 71.01s` (2026-02-18 run)

## Rollback / Safety
No destructive migration was performed; old path remains intact.

Fast rollback to old-only display:
1. Set `SHOW_TIMING_DUAL=false` in `.env`
2. Restart `etlegacy-bot.service`

Data safety:
1. Raw Lua telemetry sources are not deleted/overwritten by this change.

## Next-Shift Checklist (During Live Rounds)
1. Watch logs for `SessionTimingShadowService` coverage/fallback signals.
2. Use `!last_session_debug` on fresh sessions to inspect top deltas.
3. Confirm `!last_session` and graphs render OLD/NEW values without formatting regressions.
4. Track Lua coverage rate over next few sessions; if sustained and stable, prepare NEW-only cutover.

## Planned Cleanup (Flag Debt)
1. Keep dual mode for ~2 weeks.
2. Switch default presentation to NEW-only after stability gate passes.
3. Remove OLD display branch and `SHOW_TIMING_DUAL` in a follow-up cleanup PR.
