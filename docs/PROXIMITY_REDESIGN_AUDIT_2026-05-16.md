# Proximity Redesign — Phase 1 Audit (Mandelbrot RCA, 3-layer)

**Date:** 2026-05-16
**Branch:** `feat/proximity-redesign` (isolated worktree `/home/samba/share/slomix_prox_redesign`, base `159fb21` = `main`)
**Scope:** Gate for the Proximity page redesign (`docs/PROXIMITY_REDESIGN_MASTER_PLAN.md`).
**Structure:** Reuses the 3-layer Mandelbrot RCA from `docs/DEEP_RCA_PROXIMITY_REVIEW.md` — Layer A (FE↔API contract drift), Layer B (schema-drift / INSERT coverage), Layer C (code health).

---

## Top 3 (act on these first)

1. **A1 — global heatmap renders BLANK on all 20 calibrated maps (CRITICAL).** `renderHeatmap` (`website/js/proximity.js:952-954`) reads `zone.grid_x`/`zone.grid_y`; the `/proximity/hotzones` endpoint (`website/backend/routers/proximity_combat.py:166-172`) emits `x`/`y`/`count`/`kills` — no `grid_x`/`grid_y`. On calibrated maps `worldBounds` is truthy → every zone fails `Number.isFinite` → `continue` → loop ends → `return` at `proximity.js:971` with an empty canvas. The relative-grid fallback (`:974-996`) is never reached on calibrated maps, and *also* reads `h.grid_x` (still `undefined`), so it is broken too. **Net: the main heatmap is dead everywhere.** Closed by Phase 3/4 (flagship moves to the `{x,y,count}` / 512 contract).
2. **A2 — no per-player filter on the heatmap endpoint (CRITICAL, blocks the flagship feature).** `GET /proximity/combat-positions/heatmap` (`website/backend/routers/proximity_positions.py:188-259`) never passes `player_guid`/`player_guid_columns` to `_build_proximity_where_clause`, even though the helper already supports them (`proximity_helpers.py:143-144, 179-191`). The per-player heatmap therefore needs a **new** endpoint (Phase 2), not an overload of the existing one.
3. **A6 — two incompatible grid contracts (CRITICAL, root of A1's scale bug).** `/proximity/hotzones` buckets at **256** units (`proximity_combat.py:138-139`, `FLOOR(... / 256.0)`) while `/proximity/combat-positions/heatmap` buckets at **512** (`proximity_positions.py:239`) and the frontend constant is `PROXIMITY_GRID_SIZE = 512` (`proximity.js:13`). Even if A1's key mismatch were fixed in isolation, hotzones would render at 2× scale offset. Resolved by standardizing the flagship on `proximity_combat_position` / 512 / `{x,y,count}` (Phase 3/4).

---

## Findings table

| ID | Layer | Severity | Location | Finding | Disposition |
|----|-------|----------|----------|---------|-------------|
| A1 | A | **CRITICAL** | `proximity.js:952-954,971` ↔ `proximity_combat.py:166-172` | `grid_x`/`grid_y` consumed but never emitted → blank heatmap on all calibrated maps; broken fallback too | Fixed via Phase 3 (flagship → `{x,y,count}`/512) |
| A2 | A | **CRITICAL** | `proximity_positions.py:188-259` | No per-player GUID filter passed to `_build_proximity_where_clause` | Fixed via Phase 2 (NEW `/proximity/player-heatmap`) |
| A6 | A | **CRITICAL** | `proximity_combat.py:138-139` vs `proximity_positions.py:239` vs `proximity.js:13` | 256-unit vs 512-unit grid contracts diverge (2× scale) | Resolved by A1 fix (standardize on 512) |
| A3 | B | IMPORTANT | `tools/schema_postgresql.sql:2618-2645`, `parser.py:326-340,2134-2200` | `proximity_kill_outcome` stores **no** death position anywhere | Documented; "player_dies" must use `proximity_combat_position.victim_x/y` (Phase 2) |
| A4 | A | NIT | `Proximity.tsx:136` | React `HeatmapCanvas` reads `p.team`; combat-heatmap endpoint never returns `team` | Fixed via Phase 3 (drop/recolor `p.team` branch) |
| A5 | C | NIT | `proximity.js:89,100` | Config-load (`map_transforms.json` / `objective_zones.json`) failures silently `.catch(() => null)` → masks the *real* reason a calibrated heatmap is blank | **FIXED in Phase 1** (added `console.warn` diagnostics) |
| A7 | B | INFO | `parser.py:500` | `ProximityParserV4` is a single canonical class; no shadow/duplicate module | Confirmed clean (`git status` clean) |
| C1 | C | NIT | `parser.py:3348` PERF401 | `for … append` over a transformed list | **FIXED in Phase 1** (`list.extend` generator) |
| C2 | C | IMPORTANT | `parser.py:593` (DTZ001), `:981,:983` (DTZ006), `:1367` (DTZ007) | 4 naive-datetime violations under the **enforced** ruff config — `CLAUDE.md`'s "Ruff 0 errors" is drifted vs current `main` | **Flagged, DEFERRED** — timestamp-semantics-sensitive in a round-time parser; blind `tz=` injection risks shifting parsed `round_start_unix`/match times. Needs a dedicated tz-intent review, out of redesign scope. |
| C3 | C | NIT | `proximity_dashboard.py:428-435` | Original "V5 table-count silent-zero" (the RCA-doc "A5") — **already** wrapped in `try/except` with `logger.exception(...)`; the `int(cnt or 0)` only normalizes a NULL `COUNT(*)` | No action (false positive in current tree) |

Severity legend: CRITICAL = breaks rendering / blocks the feature; IMPORTANT = correctness or process risk; NIT = polish.

---

## Layer A — FE↔API contract drift

- **proximity.js fetch surface:** the page consumes scoped `/proximity/*` (hotzones, combat-positions/heatmap, kill-lines, events, trades, leaderboards, prox-scores, danger-zones, dashboard) and `/storytelling/*` endpoints via the `scopedUrl(...)` / `fetchJSON(...)` helpers (`proximity.js:~1605-1680`).
- **A1 confirmed by direct read** (`proximity.js:898-997`): line 942 `if (worldBounds)`; lines 952-953 read `Number(zone.grid_x)`/`Number(zone.grid_y)`; line 954 `if (!Number.isFinite(gx) || !Number.isFinite(gy)) continue;`; line 971 `return;` (post-loop, **before** the `:974` fallback). `/proximity/hotzones` output dict (`proximity_combat.py:166-172`) is `{x, y, count, kills, deaths}` — no `grid_x`/`grid_y`. SQL *aliases* them `grid_x`/`grid_y` (`:138-139`) but the dict is built positionally as `x`/`y`. Result: NaN → skip-all → blank on calibrated maps; the uncalibrated fallback also reads `h.grid_x` (`:975-987`) → still NaN.
- **A4 confirmed:** `Proximity.tsx:136` does `const team = String(p.team ?? '').toUpperCase();` then color-branches; the combat-heatmap endpoint returns only `{x,y,count}`, so all points fall to the cyan default. Cosmetic only (null-coalesced) → NIT.
- **A5 (silent config loads):** `ensureMapTransformConfig`/`ensureObjectiveZonesConfig` (`proximity.js:84-104`) swallowed fetch failure with `.catch(() => null)`. When the calibrated transform JSON fails to load, `worldBounds` becomes falsy and the heatmap silently degrades — masking the exact A1 class of failure during diagnosis. **Fixed:** both now `console.warn(...)` before returning `null`.

## Layer B — schema-drift / INSERT coverage

- **No dead proximity columns.** Every proximity-table column added by `migrations/*.sql` (009, 010, 013, 014, 019–030, 033, 035, 038) has a parser writer, either a direct `_import_*` INSERT or a runtime-guarded append (`_table_has_column` `parser.py:920`, `_append_round_link_columns` `:1069`, `_append_canonical_guid_columns` `:1047`). The `*_guid_canonical` regression class (migrations 035/036, commit `cdb7f51`) remains closed.
- **A3 verdict (formal):** `proximity_kill_outcome` has **no** x/y/z or position column — not in `tools/schema_postgresql.sql:2618-2645`, not in the `KillOutcome` dataclass (`parser.py:326-340`), not parsed (`_parse_kill_outcome_line` `~:2134`), not inserted (`_import_kill_outcomes` `~:2159-2200`). By design: kill-outcome tracks *post-death* events (revive/gib/denied), not where death happened. Death position lives only in `proximity_combat_position.victim_x/y/z` (schema `:2271+`, parsed `:2261-2282`, written `_import_combat_positions` `:2459-2505`). **Consequence for Phase 2:** the `player_dies` mode must filter `proximity_combat_position` by `victim_guid` and is therefore *kills-by-enemy only* — world/suicide/explosive self-deaths are excluded and must be captioned in the UI. (A true all-deaths heatmap would require the gated Lua v9 workstream.)
- **A7:** `class ProximityParserV4` is defined once at `parser.py:500`; no shadow module. Worktree `git status` clean → the file under audit is the live parser.

## Layer C — code health

- **Routers ruff-clean:** `ruff check website/backend/routers/proximity_*.py` → *All checks passed* (project config, `pyproject.toml:76`).
- **parser.py:** 5 enforced-config findings on the `main` base → **4 after Phase 1** (PERF401 fixed). Remaining are 4 naive-datetime (DTZ001/DTZ006×2/DTZ007). They are pre-existing on `main`, not introduced by the redesign, but they *do* contradict `CLAUDE.md`'s "Ruff 0 errors" claim → the doc is drifted. Deferred deliberately: `parser.py:593/981/983/1367` convert epoch/round timestamps; injecting `tz=`/`%z` blindly can shift parsed match times and corrupt `round_start_unix` linkage. This needs a separate, tested tz-intent change — explicitly *out of the redesign blast radius*.
- **Silent catches:** only the two config-load `.catch(() => null)` (now logged) and `proximity.js:2861` `.catch(() => renderProxScores(d, null))` (graceful degrade — formula panel just renders without the formula; acceptable, left as-is) and `:2775` (shows a visible "Failed to load." message — acceptable).

---

## Phase 1 bugfixes applied (this commit)

| File | Change | Why |
|------|--------|-----|
| `website/js/proximity.js:87-89` | `.catch(() => null)` → `.catch((err) => { console.warn(...); return null; })` for map-transform config | A5 — surface the silent failure that masks blank calibrated heatmaps |
| `website/js/proximity.js:98-100` | same for objective-zones config | A5 — surface silent objective-overlay failure |
| `proximity/parser/parser.py:3346-3354` | `for … append` → `missed_candidates.extend(<genexpr>)` | C1 — close the one safe enforced-config ruff error before Phase 5 touches `parser.py` |

Semantics unchanged (verified: `node --check` on `proximity.js`, `ast.parse` on `parser.py`, ruff parser.py 5→4).

---

## DB gate (PostgreSQL `etlegacy`, run 2026-05-16)

| Metric | Last 30 days | All-time |
|--------|--------------|----------|
| `proximity_combat_position` rows | 5 347 | 17 456 |
| `proximity_combat_position` distinct `attacker_guid` | 9 | 25 |
| `proximity_combat_position` distinct `map_name` | 9 | 9 |
| `player_track` rows | 6 712 | 33 606 |
| `player_track` distinct `player_guid` | 9 | 29 |

`player_track` confirmed to carry `path jsonb`, `sample_count int`, `player_guid`, `map_name`, `session_date`, `round_start_unix/round_end_unix`, `round_id` → the Phase 2 `presence` mode (LATERAL `jsonb_array_elements` + stride downsample on `sample_count`) is feasible as planned.

**Maps with data (all-time, by row count):** `te_escape2` (4234), `supply` (2873), `sw_goldrush_te` (2841), `etl_adlernest` (2177), `etl_sp_delivery` (1955), `et_brewdog` (1253), `erdenberg_t2` (1010), `etl_frostbite` (596), `braundorf_b4` (517).

**Calibrated maps (20, `map_transforms.json`):** `adlernest, braundorf_b4, bremen_b3, decay_sw, erdenberg_t2, et_brewdog, etl_adlernest, etl_base, etl_beach, etl_braundorf, etl_ice, etl_sp_delivery, frostbite, missile_b3, missile_b4, supply, sw_battery, sw_goldrush_te, sw_oasis_b3, te_escape2`.

**Cross-check (NIT, A8):** 8 of the 9 data-maps are calibrated. **`etl_frostbite`** has 596 rows but only the key **`frostbite`** is calibrated — a name-key mismatch. The Phase 3 UX should *intersect* data-maps with calibrated keys for the map selector (so `etl_frostbite` either gets a calibrated alias or is shown uncalibrated with a caption), rather than silently degrading.

---

## Checklist (A1–A8)

| Item | Status |
|------|--------|
| A1 grid_x/grid_y blank heatmap | **Confirmed**; fix deferred to Phase 3 (flagship → `{x,y,count}`/512) |
| A2 no per-player filter on heatmap endpoint | **Confirmed**; fix = NEW endpoint, Phase 2 |
| A3 kill_outcome has no death position | **Confirmed & documented**; Phase 2 uses `victim_*` (kills-only, captioned) |
| A4 React `p.team` not returned | **Confirmed** (NIT); fix in Phase 3 |
| A5 silent config-load catches | **FIXED in Phase 1** (logging added) |
| A6 256-vs-512 grid contracts | **Confirmed** (`proximity_combat.py:138` vs `proximity_positions.py:239`); resolved by A1 fix |
| A7 real `ProximityParserV4`, no shadow | **Confirmed clean** (`parser.py:500`, worktree clean) |
| A8 `etl_frostbite` vs `frostbite` calibration key | **New NIT**; handle via data∩calibrated intersect in Phase 3 |

**Gate decision:** A1 and A2 root causes are confirmed by direct code read; this audit doc exists. ✅ **Phase 2 is unblocked.** Phase 5 (Lua) stays gated on explicit user approval (SSH pull) and is independent of this gate.
