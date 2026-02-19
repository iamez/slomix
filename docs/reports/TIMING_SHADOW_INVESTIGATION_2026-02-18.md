# Timing Shadow Investigation (2026-02-18)

## Scope
Fix incorrect/corrupt `time_dead` and `time_denied` in:
1. `!last_session` overview and `!last_session time`
2. `!last_session graphs`

Approach: run OLD vs NEW timing in parallel behind `SHOW_TIMING_DUAL`.

## Docs Context Sync
Required docs reviewed before code changes:
1. `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md`
2. `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md`

Referenced-doc successor mapping found during sync:
1. `docs/DEEP_TIMING_DATA_COMPARISON_AUDIT_AND_FIX_PLAN.md` -> `docs/PIPELINE_DEEP_DIVE_HANDOFF_2026-02-18.md`
2. `docs/TECHNICAL_DEBT_AUDIT_2026-02-05_to_2026-02-11.md` -> `docs/AUDIT_2026-02-15_DOCS_AND_DEBT.md`
3. `docs/SESSION_2026-02-12_WEBHOOK_PROXIMITY_GREATSHOT_INVESTIGATION.md` -> `docs/WS1_R2_MISSING_INVESTIGATION_2026-02-18.md`
4. `docs/SECURITY_FIXES_2026-02-08.md` -> `docs/SECRETS_MANAGEMENT.md` (and `docs/archive/SECURITY_FIXES.md`)

## Data Path Mapping
Command/data path verified:
1. `!last_session` -> `bot/cogs/last_session_cog.py` -> aggregators/services -> embed builders.
2. `!last_session time` -> `bot/services/session_view_handlers.py`.
3. `!last_session graphs` -> `bot/services/session_graph_generator.py`.
4. DB inputs previously came from `player_comprehensive_stats` (`time_dead_minutes`, `denied_playtime`) only.

## Old vs New Timing Sources
### Old timing (legacy display path)
1. `old_dead`: sum of `LEAST(time_dead_minutes * 60, time_played_seconds)` from `player_comprehensive_stats`.
2. `old_denied`: sum of `denied_playtime` from `player_comprehensive_stats`.

### New timing (shadow path)
1. `new_dead`: `lua_spawn_stats.dead_seconds` joined by `(round_id, guid_prefix[:8])`, bounded to plausible limits:
   - `>= 0`
   - `<= min(time_played_seconds, lua_round_teams.actual_duration_seconds if present)`
2. `new_denied`: deterministic projection using old denied-rate over active time:
   - `old_active = old_played - old_dead`
   - `denied_rate = old_denied / old_active` (when `old_active > 0`)
   - `new_denied = clamp(round(denied_rate * new_active), 0, new_active)` where `new_active = old_played - new_dead`
3. Missing telemetry fallback:
   - keep `new = old`
   - explicit fallback reason (`lua_missing_for_round`, `lua_missing_for_guid_prefix`, `lua_query_failed`)

## Root Cause (Where Corruption Happens)
Corruption is not a single point failure:
1. Historical parser/differential edge cases caused persisted legacy rows with bad timing relationships (notably R2/reset patterns documented in tracker).
2. WS1 ingestion coverage gaps leave many rounds without Lua telemetry (`lua_round_teams`/`lua_spawn_stats` missing), forcing legacy fallback.
3. Display code consumed legacy fields directly without side-by-side verification, so bad persisted values surfaced unchanged.

## Validation Evidence (Code + Logs + DB)
### DB/session evidence (read-only queries + service run)
New shadow service executed against production DB sessions:
1. Session `89`: rounds `12`, Lua-covered rounds `6/12`, player telemetry coverage `50.00%`.
   - Artifact: `logs/timing_shadow/timing_shadow_9855_9871_12r_20260218_203123.csv`
2. Session `88`: rounds `16`, Lua-covered rounds `8/16`, player telemetry coverage `51.61%`.
   - Artifact: `logs/timing_shadow/timing_shadow_9818_9838_16r_20260218_203123.csv`
3. Session `84`: rounds `5`, Lua-covered rounds `0/5`, player telemetry coverage `0.00%` (graceful fallback).
   - Artifact: `logs/timing_shadow/timing_shadow_9805_9812_5r_20260218_203123.csv`

### Runtime evidence now emitted
1. Structured per-player timing logs from `SessionTimingShadowService` include:
   - session scope, round id, player guid
   - old/new dead and denied
   - Lua row counts and coverage percent
   - fallback reason
2. CSV debug artifacts are written under `logs/timing_shadow/`.

### Test evidence
1. `tests/unit/test_session_timing_shadow_service.py`
   - invariants unit tests for cap/non-negative/fallback
   - integration-ish fake-DB aggregation test (stable output + artifact write)
2. `tests/unit/test_session_embed_builder_timing_dual.py`
   - formatting test for OLD/NEW dual timing rendering in overview embed

## Implementation Summary
1. Added `SHOW_TIMING_DUAL` config flag in `bot/config.py`.
2. Added `SessionTimingShadowService` in `bot/services/session_timing_shadow_service.py`.
3. Wired dual output into:
   - `!last_session` overview (`bot/services/session_embed_builder.py`)
   - `!last_session time` (`bot/services/session_view_handlers.py`)
   - `!last_session graphs` (`bot/services/session_graph_generator.py`)
4. Added admin debug command:
   - `!last_session_debug` in `bot/cogs/last_session_cog.py` (admin-only)

## Cleanup Plan (Flag Debt)
Recommended rollout/debt removal:
1. Week 0-2 (shadow period): keep `SHOW_TIMING_DUAL=true` in production and monitor artifacts/logs.
2. After 2 weeks: if telemetry coverage and diffs are stable, switch display default to NEW-only.
3. One release later: remove OLD display path and delete `SHOW_TIMING_DUAL` flag and compatibility branches.
