# Evidence: WS5-001 Feb 5-7 Open-Loop Next Checks
Date: 2026-02-12  
Workstream: WS5 (Documentation Closure)  
Task: `WS5-001`  
Status: `done`

## Goal
Close the Feb 5-7 “next checks” loop by assigning a dated pass/fail outcome to each pending check.

## Outcome Matrix (Dated)
1. Source: `docs/SESSION_2026-02-05_AWARDS_GUID_ENRICHMENT.md`
   - Check: restart web + re-run awards endpoints.
   - Outcome (2026-02-12): `FAIL (runtime evidence missing in this session)`.
   - Note: code paths remain present (`/rounds/{round_id}/awards`, `/awards/leaderboard`).
2. Source: `docs/SESSION_2026-02-05_AWARDS_GUID_ENRICHMENT_V2.md`
   - Check: re-run `/api/awards/leaderboard`.
   - Outcome (2026-02-12): `FAIL (runtime curl output not captured in this session)`.
   - Note: GUID enrichment code remains present.
3. Source: `docs/SESSION_2026-02-05_ALIAS_UNIFICATION_AWARDS_COMPARE.md`
   - Check: spot-check awards/vs/compare endpoints after restart.
   - Outcome (2026-02-12): `PARTIAL PASS (static code verification)`.
   - Evidence: routes still present (`/stats/compare`, awards routes), runtime proof pending.
4. Source: `docs/SESSION_2026-02-05_ALIAS_SEARCH_AND_LEADERBOARD_UNITS.md`
   - Check: extend GUID unification to other lists if duplicates remain.
   - Outcome (2026-02-12): `PASS (code-level)`.
   - Evidence: awards and compare routes are GUID-aware in current API code.
5. Source: `docs/SESSION_2026-02-05_DATE_CAST_HARDENING.md`
   - Check: re-check overview/quick-leaders/season summary endpoints.
   - Outcome (2026-02-12): `PARTIAL PASS (static code verification)`.
   - Evidence: widespread `SUBSTR(CAST(... AS TEXT), 1, 10)` hardening remains in `website/backend/routers/api.py`.
6. Source: `docs/SESSION_2026-02-05_MONITORING_STATUS_AND_LEADERBOARD_FIX.md`
   - Check: verify monitoring history via UI or `/api/monitoring/status`.
   - Outcome (2026-02-12): `PASS (historical + static)`.
   - Evidence: endpoint still present; Feb 5 postmortem contains successful sample counts.
7. Source: `docs/SESSION_2026-02-05_TIME_DEAD_DENIED_PIPELINE.md`
   - Check: live-round diagnostics and 3-way timing validation.
   - Outcome (2026-02-12): `PARTIAL PASS`.
   - Evidence: diagnostic endpoints (`/diagnostics/time-audit`, `/diagnostics/spawn-audit`) exist; live-round closure still gated by WS1.
8. Source: `docs/SESSION_2026-02-06_LUA_SPAWN_GAMETIMES_DEBUG.md`
   - Check: live round should write gametimes + spawn stats and compare dead-time deltas.
   - Outcome (2026-02-12): `FAIL (runtime-gated)`.
   - Note: code/migration paths exist; fresh live-round evidence remains blocked by WS1 gate.
9. Source: `docs/SESSION_2026-02-07_PROXIMITY_TRADE_SUPPORT.md`
   - Check: add confidence tiers/objective exceptions/detail drill-down/team breakdown.
   - Outcome (2026-02-12): `FAIL (open feature backlog)`.
   - Note: these are enhancement tasks not yet implemented in this cycle.

## Summary
1. Open-loop checks are now explicitly closed with dated outcomes.
2. Runtime-blocked items are documented as fails/deferred, not left implicit.
3. Remaining fails map cleanly to active blockers (`WS1` gate) or backlog enhancements.
