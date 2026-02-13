# Technical Debt Audit (Docs Window: 2026-02-05 to 2026-02-11)
Date: 2026-02-11  
Mode: Documentation audit only (no runtime code edits).

## Superseded Notice (2026-02-12)
This file is a historical audit snapshot. Point-in-time counts here may be outdated.
For current execution truth, use:
1. `docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md`
2. `docs/evidence/2026-02-18_ws4_reaudit.md`
3. `docs/evidence/2026-02-19_ws4_secret_rotation.md`

## Scope Audited
Date-stamped docs and active planning docs:
- `docs/SESSION_2026-02-05_*.md`
- `docs/SESSION_2026-02-06_*.md`
- `docs/SESSION_2026-02-07_PROXIMITY_TRADE_SUPPORT.md`
- `docs/PROXIMITY_*_2026-02-07.md`
- `docs/SECURITY_FIXES_2026-02-08.md`
- `docs/LUA_ERROR_LOGS_FROM_USER_2026-02-06.txt`
- `docs/time_audit_report_2026-02-05.json`
- `docs/time_audit_report_2026-02-06.json`
- `docs/DEEP_TIMING_DATA_COMPARISON_AUDIT_AND_FIX_PLAN.md`
- `docs/LUA_TIMING_AND_TEAM_DISPLAY_IMPLEMENTATION_PLAN.md`
- `docs/TODO_LUA_TIMING_VALIDATION.md`
- `docs/TODO_MASTER_2026-02-04.md` (referenced by multiple docs in scope)

## Executive Result
You did not miss implementation effort.  
You did miss closure loops: validation, rollout confirmation, and stale-doc cleanup.

Highest-risk debt is operational, not coding:
1. Score truth chain is not reliable enough (round winner -> map winner -> session score can diverge).
2. Lua webhook timing pipeline still not producing current data.
3. Security hardcoded secret rotation remains pending.
4. Large timing anomaly backlog remains unclosed historically.

## Evidence Snapshot (Current)
- `lua_round_teams` rows: `1` (latest `2026-01-24`).
- `lua_spawn_stats` rows: `0`.
- `proximity_trade_event` rows: `575` (latest `2026-02-07`).
- `proximity_support_summary` rows: `5` (latest round end `2026-02-06`).
- Hardcoded `REDACTED_DB_PASSWORD` occurrences in repo: `64`.

This means proximity work is live in DB, while Lua timing webhook work is not.

## Missed / Deferred Items

## P0 (Do First)
1. **Score truth chain closure is still open**
- Risk: map/session/live score can be shown with weak or missing winner-side evidence.
- Code-verified gap: map summary "all rounds" queries currently filter by a single `round_id`, so map-level aggregation can be misleading.
- Current DB indicator (30-day R1/R2 sample): `136` total, `109` missing `winner_team`, `109` missing `defender_team`.
- Debt: no hard gate that blocks score publication when side data is missing/ambiguous.

2. **Webhook pipeline closure is still open**
- Source docs: `docs/TODO_LUA_TIMING_VALIDATION.md`, `docs/SESSION_2026-02-06_LUA_SPAWN_GAMETIMES_DEBUG.md`, `docs/SESSION_2026-02-06_AI_SESSION_REPORT.md`.
- Missed outcome: post-deploy validation was never closed with proof of fresh STATS_READY ingestion.
- Current indicator: no recent Lua rows, no spawn rows.

3. **Gametime fallback is not proving anything yet**
- Source docs expected gametime file generation and fallback ingestion.
- Current indicator: server gametimes directory exists but empty in current checks.
- Debt: fallback path is configured but unverified in real rounds.

4. **Ingestion contract fragmentation is still open**
- Current behavior relies on separate "new data" paths (`stats_webhook_notify.py`, STATS_READY webhook, proximity importer, gametime fallback) with no single documented round identity contract.
- Risk: score/timing/proximity can each appear "working" but still refer to different effective rounds.
- Debt: universal ingestion contract (source + round fingerprint + link status + confidence) was not yet closed as a mandatory cross-service requirement in this audit window.

## P1 (High)
1. **Hardcoded DB password rotation not executed**
- Source doc: `docs/SECURITY_FIXES_2026-02-08.md` (explicitly pending).
- Current indicator: many literal password occurrences still present.
- Debt: security tooling exists but no operational rotation/removal done.

2. **Security rollout checklist not closed**
- Same doc contains unchecked deployment/test checklist.
- Debt: fixes may exist in repo but are not documented as validated in production.

3. **Timing service hardening plan not yet executed**
- Source docs: `docs/DEEP_TIMING_DATA_COMPARISON_AUDIT_AND_FIX_PLAN.md`, `docs/LUA_TIMING_AND_TEAM_DISPLAY_IMPLEMENTATION_PLAN.md`.
- Missed items:
  - session join fix (`round_id` join),
  - linker failure reason codes,
  - backfill operational runbook usage,
  - website timing panel/resolver rollout.

## P2 (Medium)
1. **Historical time data quality backlog remains large**
- Source reports: `docs/time_audit_report_2026-02-05.json`, `docs/time_audit_report_2026-02-06.json`.
- Notable unresolved counts in reports:
  - high `ratio_diff`,
  - `dead_gt_played`,
  - `denied_gt_played`.
- Debt: old corrupted/biased rows still need either backfill/annotation strategy.

2. **Homepage fallback edge-case still open**
- Source: `docs/TODO_MASTER_2026-02-04.md` unchecked item:
  - overview fallback when `rounds` is empty and only session data exists.

3. **Feb-05 “next checks” often not closed in docs**
- Alias/awards/date-cast docs request restart + endpoint verification.
- Debt: unclear closure evidence for operational verification.

## P3 (Medium-Low)
1. **Proximity roadmap consistency debt**
- `docs/PROXIMITY_ANALYTICS_BACKLOG_2026-02-07.md` says support uptime/isolation as next steps.
- `docs/SESSION_2026-02-07_PROXIMITY_TRADE_SUPPORT.md` says those are delivered.
- Debt: backlog doc stale and contradictory to later session report.

2. **Proximity advanced features explicitly deferred**
- confidence tiers,
- objective exceptions,
- event drill-down,
- map overlay/calibration (`docs/PROXIMITY_MAP_OVERLAY_PLAN_2026-02-07.md`).

## P4 (Documentation Hygiene)
1. **Status drift between docs**
- Security doc says XSS task pending, but current `website/js/awards.js` already uses `escapeJsString()` at the cited onclick row.
- Debt: docs no longer mirror current state.

2. **No single “closed-loop” tracker for Feb 5+ work**
- Many session docs have “Next checks” sections.
- No consolidated closeout record marking pass/fail with date.

## Likely False Positives (Do Not Chase Immediately)
1. **Proximity migrations not applied**
- This appears already resolved (`proximity_trade_event` and `proximity_support_summary` have data).

2. **Awards onclick XSS at cited line**
- Likely already addressed in current file state.
- Keep as quick re-audit item, not top-priority blocker.

## Recommended Closure Sequence
1. Run `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md` during one live round and record outcome.
2. Update `docs/TODO_LUA_TIMING_VALIDATION.md` with explicit pass/fail for each step.
3. Execute security secret rotation plan and remove hardcoded password usage.
4. Decide policy for historical timing anomalies:
   - backfill,
   - quarantine flag,
   - or documented “pre-fix unreliable window.”
5. Merge stale docs:
   - proximity backlog vs delivered,
   - security pending vs current code,
   - add one “Feb closure” report.

## Suggested “Done Definition” for Future Tasks
A task is only complete when all three are present:
1. Code/config change landed.
2. Runtime evidence captured (logs/API/DB).
3. One doc updated from “next step” to “verified on <date>”.
