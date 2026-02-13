# Two-Week Closeout Plan (2026-02-11 to 2026-02-25)
Status: Planning document  
Mode: Execution-ready checklist with runtime validation gates

## Purpose
Close open score/timing/webhook/security debt with provable runtime evidence, not just code changes.

## Consolidated Inputs
This plan incorporates and supersedes day-to-day sequencing from:
1. `docs/DEEP_TIMING_DATA_COMPARISON_AUDIT_AND_FIX_PLAN.md`
2. `docs/LUA_TIMING_AND_TEAM_DISPLAY_IMPLEMENTATION_PLAN.md`
3. `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md`
4. `docs/TECHNICAL_DEBT_AUDIT_2026-02-05_to_2026-02-11.md`
5. `docs/SESSION_2026-02-12_WEBHOOK_PROXIMITY_GREATSHOT_INVESTIGATION.md`
6. `docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md`

Execution tracker:
1. `docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md`

## Ingestion Reality (Current)
The project currently has multiple independent "new round/data" paths:
1. Legacy filename trigger path:
   - `stats_webhook_notify.py` posts filename messages to Discord control channel.
   - Bot parses filename and fetches files via SSH.
2. Lua metadata path:
   - `stats_discord_webhook.lua` posts `STATS_READY` embeds with timing/winner/team metadata.
   - Bot stores Lua metadata in `lua_round_teams` / `lua_spawn_stats`.
3. Proximity analytics path:
   - `ProximityCog` scans/downloads `*_engagements.txt` and imports proximity tables.
4. Optional fallback:
   - `gametimes/*.json` ingestion when Discord metadata path fails.

These are operationally useful, but not yet documented as one universal event contract.
This plan adds that contract so score/timing/endstats/proximity all align to one round identity.

## Hard Constraints
1. Do not modify Lua files unless explicitly approved for that step.
2. Do not delete or overwrite raw timing sources.
3. Treat “done” as code + logs + DB/API evidence.
4. Keep rollback paths for each shipped unit.
5. Hard gate: WS2/WS3 cannot be marked done until WS1 proves live webhook->DB health on fresh rounds.

## Success Criteria (End of 2 Weeks)
1. Lua timing ingestion is alive on fresh rounds (`lua_round_teams` increases beyond historical baseline).
2. Round winner-side truth chain is reliable (round -> map -> session) with confidence state, not silent assumptions.
3. Session timing comparison uses robust round linkage (`round_id`), not fragile `match_id` assumptions.
4. Team side display upgrades are live in timing and round publisher outputs.
5. At least one historical debt report is closed with final status per item.
6. Security high-priority pending items are either fixed or explicitly deferred with owner/date.
7. Stopwatch state model is explicit and observable (`time_to_beat_seconds`, `next_timelimit_minutes`, full-hold vs time-set).
8. `end_reason` is normalized via strict enum policy across match state/timeline (no free-text reasons).
9. A universal round-ingestion contract exists and is used to correlate timing/score/endstats/proximity outputs.

## Workstreams

## WS0: Score Truth Chain (P0)
Goal: make round/map/session/live score trustworthy and auditable.

Current evidence (2026-02-11 read-only DB checks):
- Last 30 days R1/R2 rounds: `136`
- Missing winner side (`winner_team` NULL/0): `109`
- Missing defender side (`defender_team` NULL/0): `109`
- Known gap cluster: `2026-02-02` shows `22/22` rows missing both.

Checklist:
- [ ] Define canonical side contract and enforce it everywhere (`team`, `winner_team`, `defender_team`).
- [ ] Audit all score consumers (bot embeds, website API, session scoring, live score posting) for side-label consistency.
- [ ] Define Stopwatch timing contract fields: `time_to_beat_seconds`, `next_timelimit_minutes`, `round_stopwatch_state`.
- [ ] Define `round_stopwatch_state` values (`FULL_HOLD`, `TIME_SET`) and where each is computed.
- [ ] Define strict stored `end_reason` enum policy (`NORMAL`, `SURRENDER`, `MAP_CHANGE`, `MAP_RESTART`, `SERVER_RESTART`) and apply consistently.
- [ ] Define derived round outcome classifications for displays/events (`FULL_HOLD`, `TIME_SET`, `SURRENDER_END`, `MAP_CHANGE_END`, `MAP_RESTART_END`, `SERVER_RESTART_END`).
- [ ] Make warmup exclusion explicit and testable in score/timing calculations.
- [ ] Fix map summary scope so "all rounds" truly aggregates map pairs, not a single `round_id`.
- [ ] Introduce score confidence states (`verified_header`, `time_fallback`, `ambiguous`, `missing`) in payloads/displays.
- [ ] Add import-time diagnostics for missing/invalid winner and defender values.
- [ ] Prepare historical backfill runbook for rows with `winner_team=0` / `defender_team=0` (dry-run first).
- [ ] Add reconnect-resilient differential handling for per-player R2 counter resets (avoid false zero time/damage).

Exit gate:
- [ ] Two fresh maps validate round winner, map winner, and session score consistency end-to-end.
- [ ] Website and Discord agree on winner side labeling for the same rounds.
- [ ] No score output is shown without confidence state.
- [ ] At least one Stopwatch map pair validates `time_to_beat_seconds`, `next_timelimit_minutes`, and `FULL_HOLD` vs `TIME_SET`.

## WS1: Webhook Pipeline Recovery (P0)
Goal: prove STATS_READY -> bot -> DB works on real rounds.

Checklist:
- [ ] Run live-round triage from `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md`.
- [ ] Capture one full evidence bundle:
  - server Lua logs (round start/end + send),
  - bot webhook logs (accepted STATS_READY + store),
  - DB counts before/after.
- [ ] Fix store-stage blocker if present (`_store_lua_round_teams` parameter packing mismatch: `24 args expected, 3 passed`).
- [ ] Confirm fresh `lua_round_teams` rows are created.
- [ ] Confirm `/diagnostics/lua-webhook` reflects fresh ingestion timestamps and row growth.
- [ ] Confirm `NO LUA DATA` drops for rounds with Lua rows.
- [ ] If Discord leg fails, confirm whether gametime fallback writes and is ingested.

Exit gate:
- [ ] Two fresh rounds (R1/R2) with successful Lua data persistence.
- [ ] Health gate artifact captured (logs + DB + diagnostics) and linked in closeout notes.

## WS1C: Proximity Reliability (P0/P1)
Goal: keep proximity ingest healthy and interpretable during the same closeout window.

Checklist:
- [ ] Resolve duplicate legacy+new UNIQUE constraints causing repeat import failures (`player_track`, `proximity_objective_focus`).
- [ ] Confirm importer idempotency so failed files do not retry forever without state change.
- [ ] Validate sprint pipeline (`sprint_percentage`) on fresh rounds; all-zero data is not acceptable for leaderboards.
- [ ] Improve UI semantics for timeline/hotzone cards (legend/tooltips/clear labels).

Exit gate:
- [ ] No repeated duplicate-key spam for unchanged files during at least one full scan cycle.
- [ ] Sprint metric has non-zero distribution (or explicit "unavailable" state with reason).
- [ ] Proximity cards are self-explanatory to a first-time viewer.

## WS1B: Unified Ingestion Contract (P0)
Goal: make all round-related features speak one correlation language instead of per-service heuristics.

Checklist:
- [ ] Document canonical `round_event` envelope fields for all ingest paths:
  - source (`filename_trigger` | `stats_ready` | `proximity_file` | `gametime_fallback`)
  - map_name, round_number, round_start_unix, round_end_unix
  - round_date, round_time, filename, webhook_id, received_at
  - parse_status, link_status, confidence.
- [ ] Define deterministic `round_fingerprint` precedence:
  - `map_name + round_number + round_start_unix` (preferred),
  - fallback `map_name + round_number + round_end_unix`,
  - fallback `map_name + round_number + round_date + round_time`.
- [ ] Define idempotency/dedupe policy when the same round arrives from multiple sources.
- [ ] Define ingestion state machine:
  - `seen -> parsed -> linked_round_id -> enriched -> published`.
- [ ] Define proximity-attach policy using the same round fingerprint (`session_date + map + round + round_start_unix` when available).
- [ ] Define one cross-source health snapshot artifact (last 24h counts + latest timestamp per source).
- [ ] Ensure WS2/WS3/WS0 references use this contract terminology.

Exit gate:
- [ ] One fresh round has evidence that filename trigger, STATS_READY, and any proximity payload (if present) correlate to the same round identity.
- [ ] Round stats, endstats, timing views, and proximity APIs reference compatible round keys for that round.

## WS2: Timing Service Robustness (P1)
Goal: make comparison services reliable once data exists.

Checklist:
- [ ] Apply session timing join hardening from deep plan (`round_id` linkage).
- [ ] Add linker failure reason visibility (diagnostic logs).
- [ ] Run/validate backfill flow for unlinked Lua rows (dry-run then apply).
- [ ] Verify per-round and session timing debug both report expected source data.

Exit gate:
- [ ] Session timing output shows Lua fields when Lua rows exist.
- [ ] WS1 health gate completed before closing WS2.
- [ ] WS1B contract terms are used in timing diagnostics (`source`, `round_fingerprint`, `link_status`).

## WS3: Team Display Improvements (P1)
Goal: make timing/player output team-aware and easier to interpret.

Checklist:
- [ ] Add team side to timing comparison player payload/display.
- [ ] Group round publisher players by Axis/Allies with per-team ranking.
- [ ] Add side marker in map summary top performers (with ambiguity note kept).
- [ ] Verify Discord field limits and rendering on high-player rounds.

Exit gate:
- [ ] At least 5 real round posts render correctly without embed overflow/errors.
- [ ] WS1 health gate completed before closing WS3.
- [ ] WS1B contract verified for sample posts (display references a round key that can be traced to ingestion evidence).

## WS4: Security and Secrets Closure (P1)
Goal: close high-risk pending security debt from Feb 8 report.

Checklist:
- [ ] Re-audit unresolved items in `docs/SECURITY_FIXES_2026-02-08.md`.
- [ ] Resolve or explicitly defer:
  - hardcoded DB secret rotation,
  - remaining website XSS backlog claims.
- [ ] Run/record test pass for security-touched commands and startup.
- [ ] Update security status doc from “pending” to dated pass/fail.

Exit gate:
- [ ] Security doc reflects current truth (no stale pending claims).

## WS5: Documentation Closure (P2)
Goal: eliminate status drift and open-loop “next checks”.

Checklist:
- [ ] Close all Feb 5-7 “next checks” with dated outcomes.
- [ ] Mark stale contradictory backlog items as resolved/superseded.
- [ ] Keep one canonical closeout report for this 2-week window.

Exit gate:
- [ ] No open “next step” remains without owner/date or explicit defer.

## WS6: Greatshot Reliability (P1)
Goal: make demo cross-reference and player stat panels production-safe.

Checklist:
- [ ] Fix `/greatshot/{demo_id}/crossref` HTTP 500 path (winner comparison must handle numeric DB winner values).
- [ ] Expand Greatshot detail payload coverage for player stats (damage/accuracy/TPM where analysis data supports it).
- [ ] Add graceful fallback messaging when fields are genuinely unavailable in analysis artifacts.

Exit gate:
- [ ] Cross-reference endpoint returns stable 200 responses on recent demos.
- [ ] Greatshot player table shows enriched stats when present and clear unavailable-state when absent.

## Two-Week Timeline

## Week 1 (Stabilize + Prove)
Day 1:
- WS0 side-contract audit + score truth chain acceptance tests.
- WS1B universal ingestion contract draft (envelope + fingerprint + state machine).

Day 2:
- WS1 live triage run and evidence capture.

Day 3:
- WS1 branch resolution (if failure found) and second live validation.
- WS1B validate correlation evidence on at least one fresh round.
- WS1C proximity reliability fixes (constraint/idempotency/sprint validation).

Day 4:
- WS2 session join/linkage hardening.

Day 5:
- WS3 timing/team display changes + live validation.

## Week 2 (Close + Harden)
Day 6:
- WS0 backfill runbook dry-run + map/session score cross-checks.

Day 7:
- WS2 backfill + diagnostics pass.

Day 8:
- WS4 security pending resolution pass.
- WS6 Greatshot crossref reliability + enriched player stats.

Day 9:
- WS4 secret rotation execution plan and dry-run verification.

Day 10:
- WS5 doc reconciliation + final acceptance review against success criteria.

## Refactor Decision (Is It Sensible?)
Short answer: yes, but only targeted refactor during this window.

Recommended now:
1. Extract shared time parsing utility used by both timing services.
2. Introduce one shared timing resolver with source attribution/divergence states.
3. Standardize logging reason codes for round-linking failures.

Defer until after this 2-week plan:
1. Large architectural refactor of webhook/timing pipeline.
2. Any broad reorganization of `_pending_round_metadata` handoff.
3. Cross-cutting database schema redesign.

Rationale:
- Current blocker is operational reliability and data presence, not architecture elegance.
- Targeted refactor lowers bug surface immediately without destabilizing active flows.

## Risks and Mitigations
1. Risk: no live rounds available to validate.
Mitigation: keep tasks sequenced so WS2/WS3 can be staged, but final acceptance waits on runtime data.

2. Risk: doc-state drift returns.
Mitigation: require each task close with one evidence snippet and date stamp.

3. Risk: security work conflicts with timing priorities.
Mitigation: keep WS4 parallelizable and scoped to pending high-risk items only.

4. Risk: side encoding mismatch across bot and website (Axis/Allies inverted in one surface).
Mitigation: WS0 canonical contract test matrix must pass before score UI claims are treated as reliable.

## Final Deliverables
1. Verified score truth chain (round -> map -> session -> live) with confidence labels.
2. Updated timing services with verified Lua linkage behavior.
3. Team-aware timing and round publisher displays.
4. Security pending items reconciled.
5. One final closeout report with:
   - what shipped,
   - runtime evidence,
   - deferred backlog with owners/dates.
6. Stopwatch-aware match state signals in payloads/displays (`time_to_beat_seconds`, `next_timelimit_minutes`, normalized `end_reason`, outcome classification).
7. Universal round-ingestion contract reference with source matrix, round fingerprint rules, and evidence examples.
