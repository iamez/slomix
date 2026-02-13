# Deep Dive: Timing Data Comparison Services Audit & Fix Plan

Date: 2026-02-11  
Mode: Planning only (no runtime code edits in this task)

## Superseded Notice (2026-02-11)
This document remains valid as detailed reference, but execution should follow:
- `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md`

Use this file for deep context and implementation specifics.  
Use the two-week plan as the active checklist, sequencing source, and closeout tracker.

## Review Integration Notes (2026-02-11)
This plan has been cross-checked against an external review. Incorporated clarifications:
1. `scripts/backfill_lua_round_ids.py` is present in this repo and can be operationalized (not a missing file).
2. Resolver language is adjusted to avoid implying a single "truth" source; output should always include source attribution + divergence state.
3. `rounds` contains Lua timing mirror columns (`actual_duration_seconds`, `total_pause_seconds`, `pause_count`, `end_reason`), but `lua_round_teams` remains the authoritative raw webhook capture table.
4. Stopwatch-specific state must be explicit in models/displays (`time_to_beat_seconds`, `next_timelimit_minutes`, `FULL_HOLD` vs `TIME_SET`).
5. Termination reasons must use explicit enum policy (`NORMAL`, `SURRENDER`, `MAP_CHANGE`, `MAP_RESTART`, `SERVER_RESTART`) with derived display classifications.

## Objective
Make timing comparison robust and observable across all three sources:
1. Stats file timing (`rounds.actual_time`)
2. Lua webhook timing (`lua_round_teams.actual_duration_seconds`)
3. Filename timestamp timing (`rounds.round_date` + `rounds.round_time`)

The end goal is side-by-side comparison for every round in Discord and website views, with clear diagnostics when sources diverge.

## Hard Rules Confirmed
1. Do not modify Lua files (`c0rnp0rn7.lua`, `endstats.lua`, `stats_discord_webhook.lua`).
2. Do not overwrite/discard raw timing sources.
3. Do not remove existing timing services.
4. Do not assume c0rnp0rn timing is buggy based on Feb 6 alone.
5. Preserve `_pending_round_metadata` handoff in `bot/ultimate_bot.py`.

## Mandatory Source-Health Gate (Before Closure)
Before Phase 2/3/4 can be marked complete:
1. At least two fresh rounds (R1/R2) must persist into `lua_round_teams` after plan start.
2. `/diagnostics/lua-webhook` must show fresh ingestion timestamp growth and non-stale counts.
3. Logs must show accepted STATS_READY and successful store events for those rounds.
4. If this gate is not met, timing-linkage/display tasks may proceed in draft mode but cannot be closed as "done."

## Unified Ingestion Contract Alignment (WS1B)
This timing plan now assumes one universal ingestion contract (see `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md`, WS1B), not isolated per-service triggers.

Current live ingress paths that must be correlated to one round identity:
1. Filename trigger path (`stats_webhook_notify.py` -> trigger channel -> bot file fetch/import).
2. STATS_READY metadata path (`stats_discord_webhook.lua` -> bot webhook handler -> `lua_round_teams`).
3. Proximity import path (`ProximityCog` scanning/downloading `*_engagements.txt`).
4. Gametime fallback path (`gametimes/*.json` when Discord metadata path fails).

Timing tasks in this document must emit/use shared contract fields:
1. `source`
2. `round_fingerprint`
3. `link_status`
4. `confidence`

Round fingerprint precedence for timing/linkage:
1. `map_name + round_number + round_start_unix` (preferred)
2. `map_name + round_number + round_end_unix`
3. `map_name + round_number + round_date + round_time`

## Files Audited
- `bot/services/timing_debug_service.py`
- `bot/services/timing_comparison_service.py`
- `bot/core/round_linker.py`
- `bot/ultimate_bot.py`
- `bot/services/round_publisher_service.py`
- `postgresql_database_manager.py`
- `website/backend/routers/api.py`
- `website/js/matches.js`
- `scripts/backfill_lua_round_ids.py`
- `docs/TIMING_BUG_ANALYSIS.md` (context only)

## Live Retest Addendum (2026-02-11 Session, Logged 2026-02-12)
This addendum supersedes the earlier "no fresh STATS_READY" assumption in this file.

1. STATS_READY is actively arriving for real rounds:
   - accepted repeatedly in `logs/webhook.log` on `2026-02-11`.
2. The blocking failure is bot-side storage, not webhook transport:
   - every event hit `Could not store Lua team data: the server expects 24 arguments for this query, 3 were passed`.
3. Current state split:
   - `lua_round_teams` remains stale at `1` row.
   - `lua_spawn_stats` is fresh (`78` rows, latest on `2026-02-11`).
4. Updated diagnosis for `NO LUA DATA`:
   - primary cause is failed insert in `_store_lua_round_teams`, not missing STATS_READY sends.
5. Practical sequencing impact:
   - WS1 must first restore `lua_round_teams` writes before WS2/WS3 timing display improvements can be validated.

## Phase 1 Audit Findings (Completed)

## A) Code-level findings

1. `post_session_timing_comparison()` still uses a fragile join:
   - `bot/services/timing_debug_service.py:542`
   - `LEFT JOIN lua_round_teams l ON r.match_id = l.match_id AND r.round_number = l.round_number`
   - This is unsafe because `match_id` semantics are not consistently per-round across ingestion paths (especially R2 handling).

2. Per-round timing debug path is better:
   - `bot/services/timing_debug_service.py:341`
   - It fetches round by `round_id` then calls `_fetch_lua_data(round_id, ...)`, which first attempts direct `WHERE round_id = $1`.

3. `timing_comparison_service` also uses direct `round_id` then fuzzy fallback:
   - direct: `bot/services/timing_comparison_service.py:185`
   - fuzzy window: `bot/services/timing_comparison_service.py:238` onward.

4. Placeholder style inconsistency is cosmetic, not a functional bug:
   - `timing_comparison_service.py` uses `?` placeholders.
   - Adapter auto-translates for PostgreSQL in `bot/core/database_adapter.py:239`.

5. Time parsing is duplicated:
   - `TimingDebugService._parse_time_to_seconds()` at `bot/services/timing_debug_service.py:53`
   - `TimingComparisonService._parse_time_to_seconds()` at `bot/services/timing_comparison_service.py:525`

6. Session timing debug service is actively called from graph generation:
   - `bot/services/session_graph_generator.py:647`

7. Timing services are initialized and called as expected:
   - init: `bot/ultimate_bot.py:229`, `bot/ultimate_bot.py:232`
   - round publish calls: `bot/services/round_publisher_service.py:414`, `bot/services/round_publisher_service.py:423`

8. Website match details currently expose only stats-file duration:
   - API reads `actual_time` from `rounds`: `website/backend/routers/api.py:4014`
   - response returns `"duration": actual_time`: `website/backend/routers/api.py:4173`
   - frontend modal displays `m.duration`: `website/js/matches.js:553`

9. Existing diagnostics already available:
   - `/diagnostics/lua-webhook`: `website/backend/routers/api.py:511`
   - reports total/unlinked/latest/recent Lua rows.

10. Backfill mechanism already exists:
    - `scripts/backfill_lua_round_ids.py`
    - Uses `resolve_round_id()` and updates `lua_round_teams.round_id`.

11. `rounds` table also stores Lua timing mirror fields:
    - `actual_duration_seconds`, `total_pause_seconds`, `pause_count`, `end_reason`.
    - Source schema: `postgresql_database_manager.py:375` onwards.
    - These are useful for convenience reads, but can be `NULL` whenever webhook->round linkage/import path did not populate them.

## B) Production DB findings (read-only queries)

Snapshot taken 2026-02-11.

1. Coverage summary:
   - `lua_round_teams total`: 1
   - `lua_round_teams round_id IS NULL`: 1
   - `lua_round_teams unlinked in last 30d`: 1
   - `rounds (R1/R2) in last 30d`: 136
   - `rounds (R1/R2) in last 30d with no linked lua row by round_id`: 136
   - `rounds since 2026-02-10`: 0
   - `rounds since 2026-02-10 with no linked lua row`: 0

2. Latest round activity in DB:
   - `MAX(round_date)` for R1/R2 = `2026-02-06`
   - `MAX(created_at)` = `2026-02-07 10:03:28`

3. Latest Lua webhook activity in DB:
   - `MAX(captured_at)` in `lua_round_teams` = `2026-01-24 22:00:30+00`
   - Only one row exists, unlinked.

4. Feb 6 target rounds (9806, 9807, 9809, 9811, 9812, 9814, 9815, 9817):
   - All exist in `rounds`.
   - None have linked `lua_round_teams` by `round_id`.

5. Long-duration outliers (>= 30 minutes) in DB:
   - 6 rounds, all without linked Lua row.
   - IDs: `9804`, `9807`, `9809`, `9811`, `9815`, `9817`.

6. `rounds.match_id` behavior for R2 is mixed:
   - last-30d R2 totals: 69
   - R2 where `match_id == (round_date + round_time)`: 11
   - R2 where `match_id != (round_date + round_time)`: 58
   - This confirms `match_id` is not a safe universal key for session timing joins.

7. Fuzzy candidate check for missing linked rounds:
   - Last 30d rounds missing direct `round_id` link: 136
   - Of those with Lua candidate in +/-30m by map+round: 0
   - Current blocker is not fuzzy-window tuning; it is absent Lua ingestion.

## C) Log findings

1. STATS_READY ingestion evidence:
   - Historical snapshot (taken before live retest) had only Jan 24 events.
   - Retest addendum above confirms many fresh STATS_READY events on Feb 11.
   - Fresh failures are now in store stage (`24 args expected, 3 passed`), not send stage.

2. Timing comparison service fire evidence:
   - Multiple successful posts logged, including Feb 7 rounds:
   - e.g. `Posted timing comparison for round 9806...9817`.

3. Timing debug service evidence:
   - Session-level posts logged (`Posted session timing debug...`).
   - Per-round post log is `debug` level (`timing_debug_service.py:497`), so operational visibility is weaker.

## Interpretation

Primary current issue is **data absence at source ingestion** for Lua timing (in this DB snapshot), not only linkage.

- `NO LUA DATA` messages are expected with `lua_round_teams` nearly empty.
- Fixing the session JOIN is still necessary, but it will not restore missing Lua values if rows do not exist.
- There is no post-2026-02-10 round data in this DB to validate “stable server” behavior yet.

Updated interpretation after retest:
- Source ingestion transport is alive (STATS_READY accepted).
- Source persistence for `lua_round_teams` is broken by insert parameter packing.
- The immediate P0 task is to restore successful `lua_round_teams` writes, then re-run this plan's linkage/display phases.

## Phase 2: Fix Linkage + Session Comparison (Implementation Plan)

## Priority 1: Fix session timing JOIN
Update `bot/services/timing_debug_service.py` session query:

- Replace:
```sql
LEFT JOIN lua_round_teams l
  ON r.match_id = l.match_id
 AND r.round_number = l.round_number
```

- With:
```sql
LEFT JOIN lua_round_teams l
  ON l.round_id = r.id
```

Fallback option for unlinked Lua rows (optional second pass):
- LATERAL nearest-match by map/round/time-window when `l.round_id IS NULL`.

## Priority 2: Add explicit linker failure reasons
In `bot/core/round_linker.py` and caller `bot/ultimate_bot.py:_resolve_round_id_for_metadata`:
- Emit structured reason codes:
  - `no_rows_for_map_round`
  - `date_filter_excluded_rows`
  - `time_parse_failed`
  - `all_candidates_outside_window`
  - `resolved`
- Include map, round, target timestamp, candidate count, best diff.

## Priority 3: Promote/operationalize existing backfill
Use existing script `scripts/backfill_lua_round_ids.py`:
- Add runbook entry for safe dry-run then apply.
- Add optional cron/command guard for “new unlinked rows in last 24h > 0”.

## Priority 4: Improve observability
1. Add info-level summary in per-round timing debug post path:
   - include round_id, map, stats_secs, lua_secs, diff, confidence.
2. Add warning-level logs when Lua row missing for round publish.
3. Add health metric endpoint fields:
   - Lua rows per day
   - unlinked Lua rows per day
   - rounds without Lua per day.

## Phase 3: Website Timing Display (Implementation Plan)

## API changes
Extend `GET /stats/matches/{match_id}` in `website/backend/routers/api.py`:
- Keep existing `match.duration`.
- Keep source-of-truth separation explicit:
  - prefer reading Lua timing from `lua_round_teams` (authoritative webhook table),
  - optionally include mirrored `rounds.*` Lua timing fields for debugging visibility.
- Add new object, e.g.:

```json
"timing": {
  "stats_file": {"raw": "MM:SS", "seconds": 0},
  "lua_webhook": {
    "available": false,
    "duration_seconds": null,
    "pause_seconds": null,
    "pause_count": null,
    "warmup_seconds": null,
    "end_reason": null,
    "next_timelimit_minutes": null,
    "captured_at": null,
    "match_confidence": null
  },
  "stopwatch": {
    "time_to_beat_seconds": null,
    "round_stopwatch_state": null
  },
  "filename_timestamp": {"round_date": "YYYY-MM-DD", "round_time": "HHMMSS", "unix": 0},
  "comparisons": {
    "stats_minus_lua_seconds": null,
    "file_vs_lua_end_seconds": null
  }
}
```

## Frontend changes
Update `website/js/matches.js` modal render near current duration block (`website/js/matches.js:553`):
- Add “Timing Sources” panel with 3 cards:
  - Stats file
  - Lua webhook
  - Filename timestamp
- Add divergence badges:
  - aligned / minor diff / high diff / no lua data.
- Keep current layout backward-compatible if new fields absent.

## Phase 4: Unified Timing Resolver (Implementation Plan)

Introduce one resolver used by bot and website (shared logic, raw fields preserved):

Proposed output model:
```python
{
  "display_seconds": int | None,
  "display_source": "lua_webhook" | "stats_file" | "none",
  "confidence": "high" | "medium" | "low",
  "divergence": "aligned" | "minor_diff" | "major_diff" | "insufficient_data",
  "end_reason_normalized": "NORMAL" | "SURRENDER" | "MAP_CHANGE" | "MAP_RESTART" | "SERVER_RESTART" | None,
  "round_outcome_classification": "FULL_HOLD" | "TIME_SET" | "SURRENDER_END" | "MAP_CHANGE_END" | "MAP_RESTART_END" | "SERVER_RESTART_END" | None,
  "reason": str,
  "stats_seconds": int | None,
  "lua_seconds": int | None,
  "filename_unix": int | None
}
```

Resolution policy:
1. Pick a display source deterministically, but always include all raw source values.
2. When stats and Lua both exist and differ above threshold, mark `divergence` rather than silently implying one source is "correct."
3. If Lua missing, use stats-file parsed duration as display fallback.
3. Never overwrite raw DB source columns.
4. Always expose source + confidence + reason.
5. Normalize `end_reason` with strict enum policy (no free-text persisted values).

Note: this resolver is for display/aggregation behavior and anomaly visibility, not truth declaration about Lua vs stats-file correctness.

## End-Reason Enum Policy (Implementation Contract)
Persisted `end_reason` values:
- `NORMAL`
- `SURRENDER`
- `MAP_CHANGE`
- `MAP_RESTART`
- `SERVER_RESTART`

Derived display/event classification:
- `FULL_HOLD`
- `TIME_SET`
- `SURRENDER_END`
- `MAP_CHANGE_END`
- `MAP_RESTART_END`
- `SERVER_RESTART_END`

Notes:
- Persist enum values only; never persist free-text termination reasons.
- Derive classification from persisted `end_reason` + stopwatch timing context (e.g., whether a time was set).

## Phase 5: Validation & Rollout

## Pre-deploy checks
1. Unit test time parser variants (`MM:SS`, `HH:MM:SS`, numeric, float).
2. Unit test session timing query with:
   - linked Lua row,
   - unlinked row,
   - no Lua row.
3. API contract test for new `timing` payload.

## Post-deploy operational checks
1. `lua_round_teams` daily ingestion > 0 after real matches.
2. `rounds` with missing Lua linkage trend visible and actionable.
3. Discord timing embeds include all 3 sources.
4. Website match modal shows timing panel consistently.

## Acceptance criteria
1. Session timing debug no longer relies on `match_id` join.
2. Every timing view can show all available sources with source attribution.
3. Historical timing comparison is available in website modal/API (not only Discord transient embed).
4. Linkage failures are diagnosable from logs without manual code tracing.
5. API payload exposes stopwatch-oriented fields (`time_to_beat_seconds`, `next_timelimit_minutes`, classification).
6. WS2/WS3 closure is blocked until the source-health gate is satisfied.

## Immediate Risk Callout
As of 2026-02-11, this DB snapshot cannot validate post-2026-02-10 behavior because:
- there are no rounds after 2026-02-06 in `rounds`,
- and `lua_round_teams` ingestion is effectively absent (1 old test row).

So Phase 2+ should proceed, but final validation requires new live rounds.

## Suggested Fix Order
1. Session JOIN fix (`timing_debug_service.py`).
2. Linker reason logging (`round_linker.py` + caller).
3. Run/automate existing backfill script for unlinked Lua rows.
4. API timing payload expansion.
5. Frontend match modal timing panel.
6. Unified resolver rollout into bot + website consumers.

## Appendix: Audit SQL used (read-only)

1. Coverage counts across `rounds` and `lua_round_teams`.
2. Feb 6 target rounds linkage check.
3. Recent rounds direct `round_id` linkage sample.
4. Unlinked Lua rows list.
5. R2 `match_id` vs filename timestamp consistency.
6. Long-duration round detection and Lua linkage status.
7. Latest `rounds` and `lua_round_teams` timestamps.
