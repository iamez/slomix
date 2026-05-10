# Mega Audit v6 — Mandelbrot RCA v2.0 Full Codebase Sweep

**Date:** 2026-05-10
**Branch:** `feat/mega-audit-v6`
**Framework:** Mandelbrot RCA v2.0 (6-phase: Discovery → Dependency → Contracts → 12-point zoom → 5-Whys/Ishikawa/Fault Tree → Fix+Verify)
**Scope:** Whole repo (`bot/`, `website/backend/`, `website/frontend/`, `proximity/`, `tools/`, `migrations/`, Lua)
**Methodology:** 6 parallel Explore agents, one per axis, each with strict citation + verification protocol.

---

## Executive Summary

**Total findings:** 54 across 6 axes
- 🔴 **CRITICAL** (data corruption / crash / security): **5**
- 🟠 **HIGH** (user-visible bugs / perf): **8**
- 🟡 **MEDIUM** (correctness / cleanup): **17**
- 🟢 **LOW** / NIT: **12**
- 🔵 **DEFER** (separate plan, larger refactor): **6**

**Recurring root-cause patterns** (Mandelbrot zoom):
1. **Optimistic NULL handling** in metric services — 5 instances of `.get(key)` returning `None` to a downstream expression that assumes int/str. Same anti-pattern across `advanced_metrics.py`, `kis.py`, frontend hooks.
2. **Lock scope too narrow** — pipeline service locks acquired around mutation but not around find→mutate sequence. Causes duplicate inserts/correlations.
3. **Two-source-of-truth divergence** — schema dump vs migrations, Round Linker vs Correlation Service, datetime.now() vs utcnow(). Each pair has one canonical source nominally, but enforcement is by convention only.
4. **Silent fallback masking errors** — bare excepts + `.get(default)` swallow real errors as graceful degradation. Production logs lose root cause.

**Quantitative metrics (Mandelbrot v2 targets):**
- God files >1500 lines: **4** (target: 0) → `proximity/parser/parser.py` (3679), `availability.py` (1667), `session_view_handlers.py` (1651), `endstats_pipeline_mixin.py` (1533)
- Silent exceptions in critical path: **3** new (`webhook_event_queue.stop`, gametimes index, _safe_create_task)
- Schema drift between `schema_postgresql.sql` and `migrations/`: **6 missing tables/columns** (one is critical)
- Composite indexes missing on hot query paths: **3** (proximity_combat_position, proximity_kill_outcome, proximity_spawn_timing)
- Frontend hook race conditions on null state: **2** (Story.tsx)
- Test coverage: ~476 tests, baseline maintained

---

## Critical Findings (🔴)

### C-5: `compute_gravity` crashes on untracked players
- **File:line:** `website/backend/services/storytelling/advanced_metrics.py:56`
- **Root cause (5-Whys):**
  1. Why crash? `max(None, 1)` raises TypeError.
  2. Why None? `alive_map.get(guid)` returns None when `player_track` has no row for that guid.
  3. Why missing track? Combat engagement table can have target rows for players whose movement track wasn't logged (bot, early-leaver, partial data).
  4. Why no guard? Defensive default never added; sibling functions `compute_enabler` (just patched in PR #208) AND `compute_space_created` already use the skip-if-missing pattern.
  5. Root: copy-paste of metric loop without inheriting the skip pattern → drift.
- **Contract:** `alive_ms = alive_map.get(guid)` MUST be checked for None before use as denominator.
- **Fix:** `alive_ms = alive_map.get(guid); if not alive_ms: continue` (matches `compute_enabler` post-PR#208).
- **Risk if ignored:** /storytelling/gravity returns 500; Story page shows error panel.
- **Effort:** XS

### F-1: Webhook+SSH dual-trigger race on metadata queue
- **File:line:** `bot/services/webhook_event_queue.py:116-143`, `bot/services/stats_ready_mixin.py:99-106`, `bot/services/monitor_tasks_mixin.py:246`
- **Root cause:**
  1. Both Lua webhook receive AND SSH endstats_monitor can call `_queue_pending_metadata()` for the same logical round within the dedup TTL window.
  2. `_queue_pending_metadata` does NOT acquire `_correlation_lock`; only `_pop_pending_metadata` does.
  3. Two simultaneous queue calls produce two metadata entries with slightly different timestamps; `_pop_pending_metadata` later picks one or the other depending on filename timestamp proximity.
  4. Downstream import path may apply the wrong metadata (e.g., wrong surrender flag).
  5. Root: lock was added to dequeue side only because the original race scenario was about consumer-consumer collision; producer-producer race surfaced later.
- **Contract:** Producer + consumer of `_pending_round_metadata` must serialize on same lock.
- **Fix:** Acquire `self._correlation_lock` in `_queue_pending_metadata()`. Trivial scope expansion.
- **Risk if ignored:** Conflicting Lua metadata applied to round; correlation row may carry wrong team/surrender data.
- **Effort:** S

### F-2: Correlation lock does not span find→upsert sequence
- **File:line:** `bot/services/round_correlation_service.py:216-229, 568-598`
- **Root cause:**
  1. Two coroutines can both observe `_find_nearby_correlation_id() = None` then both call `_upsert_correlation()` with the same constructed `correlation_id`.
  2. `ON CONFLICT DO NOTHING` masks the second insert silently.
  3. Subsequent UPDATE then writes against a row whose state was set by the first insert, possibly with mismatched fields.
  4. Migration 040 had to clean up 84 such duplicates historically.
  5. Root: lock acquisition placed inside upsert helper instead of around the entire `find → resolve → upsert` block.
- **Contract:** Lock must be held from before `_find_nearby_correlation_id` until after `_upsert_correlation` returns.
- **Fix:** Move `async with self._correlation_lock:` to wrap the `find → resolve → upsert` block in `on_round_imported`. Optional follow-up: per-correlation-id BoundedLockDict to reduce global contention.
- **Risk if ignored:** Periodic cleanup migration required; data inconsistency in correlation rows.
- **Effort:** M

### E-1: Schema drift — `proximity_combat_position` missing from `schema_postgresql.sql`
- **File:line:** `tools/schema_postgresql.sql` (table absent), `migrations/026_add_proximity_combat_position.sql` (canonical source)
- **Root cause:**
  1. Schema dump dated 2026-02-08; table created 2026-03-24 in migration 026.
  2. No CI gate or post-migration script regenerates the dump.
  3. Schema dump treated as documentation, migrations as authoritative — convention not enforced.
  4. Disaster recovery using schema dump alone would lose the table entirely; migrations sequence does NOT depend on the dump (it's regenerated from real schema).
  5. Root: dual source of truth without sync mechanism.
- **Contract:** `schema_postgresql.sql` must reflect HEAD of `migrations/`.
- **Fix:** Regenerate dump (`pg_dump -s`), append timestamp to header. Add CI check (separate PR).
- **Risk if ignored:** Disaster recovery / fresh-env setup loses tables.
- **Effort:** S

### B-1: Admin commands missing channel/owner checks
- **File:line:** `bot/cogs/sync_cog.py:97` (and other commands), `bot/cogs/admin_cog.py:41` (`cache_clear`)
- **Root cause:**
  1. Decorators `@is_admin_channel()` / `@is_owner()` not applied to sync commands or `cache_clear`.
  2. Bot relies on `bot_check()` global filter to gate by channel.
  3. If `all_allowed_channels` is misconfigured/empty, commands fall through.
  4. No per-command defense in depth.
  5. Root: convention drift — newer cogs (sync) added without copying decorator pattern from `admin_cog.reload`.
- **Contract:** Any command that mutates DB state or expensive operations must declare permission decorator.
- **Fix:** Add `@checks.is_owner()` or `@checks.is_admin_channel()` to all sync commands + `cache_clear`.
- **Risk if ignored:** Unauthorized users can trigger `sync_today`, `cache_clear`, etc.
- **Effort:** XS

---

## High Findings (🟠)

### D-1: Story.tsx incomplete optional chaining on `maps`
- **File:line:** `website/frontend/src/pages/Story.tsx:109`
- **Symptom:** `currentSession?.maps.map(...)` — `?.` propagates only past `currentSession`, not `maps`.
- **Fix:** `currentSession?.maps?.map(...) ?? []`.
- **Effort:** XS

### D-3: Story.tsx hooks fire with null sessionDate
- **File:line:** `website/frontend/src/pages/Story.tsx:82-98`
- **Symptom:** 12 useQuery hooks instantiated unconditionally; some have `enabled: !!sessionDate`, but the auto-select effect runs after first render so initial pass fires with null.
- **Fix:** Render skeleton early-return if `!sessionDate`, OR ensure ALL story hooks have explicit `enabled: !!sessionDate`.
- **Effort:** S

### E-2/E-3/E-8: Missing composite indexes for `(session_date, *_guid_canonical)`
- **Files:** `proximity_combat_position`, `proximity_kill_outcome`, `proximity_spawn_timing`
- **Symptom:** Skill rating per-session queries must combine two single-column indexes via bitmap AND.
- **Fix:** New migration 052 with three `CREATE INDEX IF NOT EXISTS` statements.
- **Effort:** S

### C-3: `compute_useless_defense_deaths` join silently drops NULL victim_guid
- **File:line:** `website/backend/services/storytelling/advanced_metrics.py:560`
- **Symptom:** `LEFT(NULL, 8) = NULL`, NULL ≠ NULL in SQL → row dropped from join silently.
- **Fix:** `AND ski.victim_guid IS NOT NULL` predicate (defense in depth).
- **Effort:** XS

### C-6: Date-type mismatch in same query
- **File:line:** `advanced_metrics.py:556`
- **Symptom:** `dp.round_date_d` (TEXT YYYY-MM-DD) compared to `ski.session_date` (DATE). Postgres implicit-casts; brittle.
- **Fix:** Explicit `::date` cast; pin in test.
- **Effort:** XS

### C-7: NULL `round_start_unix` in `compute_space_created`
- **File:line:** `advanced_metrics.py:116`
- **Symptom:** `int(r[4] or 0)` collapses all NULL round_starts to bucket `0`, breaking temporal grouping for trade analysis.
- **Fix:** Filter `WHERE round_start_unix IS NOT NULL` in source query OR explicit skip-if-zero with warning.
- **Effort:** XS

### F-3: Pending metadata TTL freshness inversion
- **File:line:** `bot/services/webhook_metadata_mixin.py:84-172`
- **Symptom:** Stale entry can win against fresh entry if its timestamp is closer to filename timestamp.
- **Fix:** Tie-break by `received_unix DESC` after timestamp-proximity selection.
- **Effort:** S

### F-4: `WEBHOOK_TRIGGER_MODE` mismatch is warning-only
- **File:line:** `bot/config.py:453-465`, `bot/ultimate_bot.py:248-254`
- **Fix:** Make `(webhook_trigger_mode != 'stats_ready_only' AND ws_enabled)` a fatal config error at boot.
- **Effort:** S

---

## Medium Findings (🟡)

| # | File:line | Symptom | Fix |
|---|---|---|---|
| **B-2** | `bot/services/voice_session_service.py:187-193` | Timer cancel without `.done()` check or lock | Guard + `not done()` check; trivial S |
| **B-4** | `bot/services/webhook_event_queue.py:192` | Bare `except: pass` swallows worker exception during stop | `logger.exception(...)` XS |
| **B-7** | `bot/ultimate_bot.py:475` | Gametime index load failure logged at DEBUG | Promote to WARNING XS |
| **B-8** | `bot/ultimate_bot.py:133-145` | `t.exception()` may raise `InvalidStateError` | try/except S |
| **B-10** | `bot/ultimate_bot.py:531-541` | `correlation_service.initialize()` no try/except in setup_hook | Wrap try/except S |
| **D-2** | `Proximity.tsx:212, 408, 620` | `key={i}` in 3 list renders | Stable keys S |
| **D-4** | `Proximity.tsx:44-60` | `formatLeaderDetail` switch returns `''` on unknown category | console.warn + return `''` XS |
| **F-5** | `bot/core/round_linker.py:120-121` | Tz normalization defensive, not enforced | Type hint + assert S |
| **F-6** | `bot/automation/file_tracker.py:150` | Cannot recover after `success=FALSE` even if file fixed | Filter by success+age S |
| **E-4** | `website/backend/init_db.py` | Dead SQLite cruft (300 LOC) | Delete XS |
| **F (dup)** | `ultimate_bot.py:82` + `session_cog.py:46` | `_split_chunks()` duplicated | Move to `bot/core/utils.py` XS |
| **F (dead)** | `bot/core/utils.py:120-139` | `send_safe_error()` 0 callers | Delete XS |

---

## Low Findings (🟢) — included if cheap, deferred otherwise

| # | File:line | Notes |
|---|---|---|
| C-1 | `kis.py:295` | Soft cap docstring imprecise (no real bug) — comment fix |
| C-2 | `momentum.py:198-199` | Edge-case test missing (no real bug) |
| C-9 | `kis.py:228` | CLASS_WEIGHTS unknown class silent default |
| C-10 | `narrative.py:278-287` | Variant seed fallback shares date — minor prose repetition |
| D-6 | Awards.tsx, Leaderboards.tsx, etc. | Empty alt text on data-bearing icons (a11y) |
| D-10 | `Proximity.tsx:10` | Unused `useCombatHeatmap` import |
| E-5 | `map_kill_heatmap`, `map_movement_heatmap` | Unused tables — document as reserved or drop in future cleanup |
| E-6 | `tools/schema_postgresql.sql` | Header date stale (will be addressed by E-1) |
| E-7 | CI | No schema-drift validation gate |

---

## Deferred (🔵) — separate plan needed, NOT in this PR

| # | Reason for deferral |
|---|---|
| **B-3** datetime.now() vs utcnow() — 180 sites | Codebase-wide refactor + lint rule; separate sprint |
| **B-9** Missing `defer()` on slow commands | UX improvement, separate ticket per command |
| **F (parser)** `proximity/parser/parser.py` 3679-LOC split | Production-critical; needs fixture comparison test before split |
| **F (handler)** `session_view_handlers.py` 1651-LOC split | Discord embed regression risk |
| **F (mixin)** `endstats_pipeline_mixin.py` 1533-LOC split | Multi-service decomposition; separate PR |
| **F (linker merge)** Round Linker + Correlation Service consolidation | Architectural change; design doc required |

---

## Cross-cutting observations

1. **PR #208 fix pattern (`compute_enabler`) is the canonical "skip-on-missing" template** for `compute_gravity`, `compute_useless_defense_deaths`, `compute_space_created`. Adopting consistently prevents future regressions.

2. **Lock scope contract** for `round_correlation_service` should be documented as "lock spans entire find→upsert atomic block." Same contract applies to `_pending_round_metadata` queue.

3. **Schema dump regeneration** should be a release-please trigger or pre-commit hook (deferred to separate infra PR).

4. **Silent error masking** is the second-most-common defect class (after NULL handling). Bare `except: pass` and `.get(default)` are both legal Python but actively hostile to debugging.

---

## Verification plan (per fix)

Each fix carries a verification step:
- **Math fixes (C-3, C-5, C-6, C-7):** Add unit test exercising the NULL/missing case. Hit /storytelling/* endpoints with synthetic data missing the relevant field.
- **Race fixes (F-1, F-2, F-3):** Synthetic load test — 100 parallel `_queue_pending_metadata` + `on_round_imported` calls; final state must be deterministic (1 correlation per logical round).
- **Frontend (D-1, D-3):** Manual test with empty sessions + null sessionDate render path.
- **Schema (E-1, E-2, E-3, E-8):** Run migration on local DB, verify `\d+ proximity_combat_position` shows new indexes; query plan via `EXPLAIN ANALYZE`.
- **Bot (B-1, B-4, B-7, B-8, B-10):** Manual smoke (sync from disallowed channel must reject); pytest baseline (508+ tests green).

---

## Bundling decision

Per user feedback (`feedback_single_pr_when_possible.md`): **single PR** containing all CRITICAL + HIGH + MEDIUM + cheap LOW fixes. Deferred items remain on separate plan.

PR title: `fix: mega audit v6 — 30+ fixes across pipeline races, math NULLs, schema drift, frontend bugs`

PR body: structured by cluster (Race, Math, Schema, Frontend, Cleanup), each with file:line + before/after.
