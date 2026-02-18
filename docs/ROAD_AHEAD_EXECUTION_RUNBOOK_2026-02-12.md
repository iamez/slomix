# Road Ahead Execution Runbook (2026-02-12)
Status: Active  
Scope: Clear implementation order, gates, validation, and rollback plan.

## Purpose
Convert planning docs into an execution-ready path with one critical principle:
1. Restore data truth first.
2. Improve display layers only after data truth gates pass.

This runbook is the operational companion to:
1. `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md`
2. `docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md`
3. `docs/SESSION_2026-02-12_WEBHOOK_PROXIMITY_GREATSHOT_INVESTIGATION.md`

## Current Baseline (As of 2026-02-16)
1. STATS_READY webhook intake is alive (accepted in logs for real rounds).
2. `lua_round_teams` persistence: **R1 inserts work, R2 inserts were broken.**
   - Original error (fixed 2026-02-12): `the server expects 24 arguments for this query, 3 were passed`
   - Second bug found 2026-02-16: R2 webhook data silently rejected because `round_number=0` was treated as invalid. In ET:Legacy stopwatch mode, `g_currentRound=0` means R2, so `round_number=0` is valid. **FIX APPLIED** (`bot/ultimate_bot.py:3637`): changed `round_metadata.get("round_number", 0) == 0` to `round_metadata.get("round_number", -1) < 0`.
   - Also fixed `bot/ultimate_bot.py:1459`: `round_time_seconds` -> `actual_duration_seconds`, `time_limit_seconds` -> `time_limit` (non-existent columns).
   - **Status**: Fix applied, awaiting bot restart + validation on 2 fresh rounds (R1+R2).
3. DB state snapshot (2026-02-16):
   - `lua_round_teams=13` (was 1 on 2026-02-12; 11 R1 rows, 0 R2 rows — confirms R2 rejection bug)
   - `lua_spawn_stats=78` (fresh)
   - `combat_engagement=3506` on 2026-02-11
   - `player_track=1525` on 2026-02-11
   - `proximity_trade_event=1647` on 2026-02-11
   - `proximity_support_summary=13` on 2026-02-11
   - Today's evidence: Round 9855 (adlernest R1) has lua data; Round 9857 (adlernest R0/R2) does not.
4. Reconnect undercount confirmed:
   - `round_id=9825` has `time_played=0`, `damage=0` for reconnect player while raw round data exists.
5. Greatshot cross-reference has a likely type bug path:
   - `website/backend/services/greatshot_crossref.py` uses `db_winner.lower()` on numeric winner values.

## Hard Execution Rules
1. No Lua file edits.
2. No destructive DB actions.
3. Every task closes with:
   - code/config change,
   - runtime proof (log + DB/API),
   - tracker/doc update.
4. WS2/WS3 cannot close before WS1 gate is passed.
5. **Do NOT delete these execution-tracking docs during cleanup:**
   - `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md`
   - `docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md`
   These were accidentally deleted in commit `1c0ab8e` (2026-02-15 cleanup) and had to be recovered from git history on 2026-02-16. They contain active sprint tracking state that is not duplicated elsewhere.

## Critical Path (Order You Should Execute)
1. WS1-006: Fix `_store_lua_round_teams` parameter packing.
2. WS1-007: Revalidate on two fresh rounds (R1/R2) and clear `NO LUA DATA`.
3. WS0-007: Fix reconnect-safe differential logic (R2 counter resets).
4. WS1C-003: Clean duplicate legacy unique constraints causing repeated proximity import failures.
5. WS1C-004: Fix sprint pipeline so `sprint_percentage` is meaningful.
6. WS6-001: Fix Greatshot cross-reference HTTP 500.
7. WS2/WS3: Timing join + team display improvements (only after WS1 gate).

---

## WS1-006 Runbook (Immediate P0)
Goal: make `lua_round_teams` inserts succeed again.

### Target Files
1. `bot/ultimate_bot.py` (`_store_lua_round_teams`)

### Implementation Checklist
1. Align query placeholders and tuple parameter assembly for both branches:
   - branch with `round_id` column present,
   - branch without `round_id`.
2. Ensure only one flat tuple is passed to `db_adapter.execute`.
3. Confirm placeholder count equals tuple length in each branch.
4. Keep `lua_spawn_stats` path untouched.

### Validation (Must Pass)
1. Trigger at least one real round end and confirm logs:
   - STATS_READY accepted
   - no `24 args expected, 3 passed` warning
   - success log for Lua round data stored
2. DB count check:
   - `lua_round_teams` increases from baseline `1`.
3. Timing output check:
   - affected round no longer shows `NO LUA DATA`.

### Rollback
1. Revert only the `_store_lua_round_teams` edit.
2. Restart bot.
3. Confirm webhook intake still functioning.

### Done Criteria
1. Two fresh successful inserts (R1 + R2).
2. No argument-count warnings for those rounds.
3. Tracker updated (`WS1-006` -> done, `WS1-007` in progress/done).

---

## WS1-007 Runbook (Gate Validation)
Goal: prove WS1 is genuinely healthy beyond a single round.

### Checklist
1. Capture two-round evidence bundle:
   - server Lua log lines (send),
   - bot webhook acceptance + store success,
   - DB before/after counts.
2. Check `/diagnostics/lua-webhook` freshness.
3. Confirm timing services consume new Lua rows.

### Done Criteria
1. WS1 gate is marked passed in tracker.
2. WS2/WS3 can now proceed from blocked to active.

---

## WS0-007 Runbook (Reconnect Data Loss)
Goal: prevent false zero time/damage when a single player reconnects.

### Target Files
1. `bot/community_stats_parser.py` differential section.

### Required Behavior
1. Detect per-player non-cumulative R2 counters.
2. If reset is detected for a player:
   - use safe fallback instead of `max(0, R2 - R1)` blind subtraction for that player.
3. Emit structured telemetry for each fallback decision.

### Validation
1. Replay known failing pattern (`round_id=9825` style case).
2. Confirm player no longer gets zero time/damage when raw R2 stats exist.
3. Confirm non-reconnect players remain unchanged.

---

## WS1C-003 Runbook (Proximity Duplicate Constraint Cleanup)
Goal: stop repeated duplicate-key import spam from legacy/new unique key overlap.

### Target Objects
1. `player_track` unique constraints (legacy + round_start variant)
2. `proximity_objective_focus` unique constraints (legacy + round_start variant)

### Strategy
1. Inventory current unique constraints.
2. Keep canonical keys aligned with parser `ON CONFLICT` targets.
3. Remove or migrate conflicting legacy uniqueness definitions safely.

### Validation
1. Re-run proximity scan/import loop.
2. Confirm repeated errors for same files stop.
3. Verify no data regression in proximity table counts.

---

## WS1C-004 Runbook (Sprint Metric Fix)
Goal: make sprint leaderboards meaningful.

### Hypothesis
1. Parser currently receives sprint field but ingested values are all zero.
2. Could be source formatting, parse mapping, or value normalization.

### Checklist
1. Inspect raw engagement file sample lines for sprint bit values.
2. Trace parse -> derived `sprint_percentage` computation -> DB insert.
3. Validate with fresh round imports.

### Done Criteria
1. `player_track.sprint_percentage` has non-zero distribution on fresh data.
2. UI no longer shows flat-zero top sprint list.

---

## WS6-001 Runbook (Greatshot Crossref 500)
Goal: eliminate `Database Cross-Reference` HTTP 500.

### Target Files
1. `website/backend/services/greatshot_crossref.py`
2. `website/backend/routers/greatshot.py` (if guard needed)

### Checklist
1. Normalize winner comparison logic for mixed types (`int`/`str`/`None`).
2. Keep matching confidence logic unchanged except type safety.
3. Return controlled non-match instead of raising runtime error.

### Validation
1. Hit `/greatshot/{demo_id}/crossref` for recent demos.
2. Confirm no 500s.
3. Confirm frontend no longer shows `Cross-reference failed: HTTP 500`.

---

## WS2 + WS3 (After WS1 Gate)
Only start after WS1 pass:
1. WS2: timing join hardening and linker reason telemetry.
2. WS3: team-aware display upgrades in timing and round publisher.

These are important, but non-gating while core Lua row persistence is broken.

## Daily Execution Cadence (Practical)
1. Start-of-day:
   - check WS1 health signals first (logs + DB counts).
2. During changes:
   - one small unit at a time,
   - validate immediately on real data.
3. End-of-day:
   - update tracker status rows,
   - add one evidence note doc for what passed/failed.

## Final Acceptance For This Road-Ahead Slice
1. `lua_round_teams` grows on live rounds.
2. Reconnect players no longer lose round time/damage due to differential reset artifact.
3. Proximity ingestion runs without repeated duplicate-key spam.
4. Greatshot cross-reference endpoint is stable (no 500).
5. Only then proceed to polish-heavy timing/team display improvements.
