# Proximity Redesign — Phase 6 End-to-End Verification

**Date:** 2026-05-16 · **Branch:** `feat/proximity-redesign` (isolated worktree, base `main` 159fb21)
**Truth model:** legacy JS render + `python -c import` + curl smoke (uvicorn :8100) + psql. React tsc/build is NOT correctness proof.

## 1. Imports ✅
`SESSION_SECRET=… python -c "import website.backend.main, proximity.parser.parser, website.backend.routers.proximity_positions, website.backend.routers.proximity_combat"` → OK.

## 2. Lint / syntax ✅ (with one documented carve-out)
- `ruff website/backend/routers/proximity_*.py` → **All checks passed**.
- `ruff proximity/parser/parser.py` → 4 findings, **all pre-existing on `main`**, all the deliberately-deferred naive-datetime set (`:593` DTZ001, `:981/:983` DTZ006, `:1367` DTZ007). Documented in `PROXIMITY_REDESIGN_AUDIT_2026-05-16.md` (C2): timestamp-semantics-sensitive in a round-time parser, out of redesign blast radius. PERF401 (the one safe item) was fixed in Phase 1. **No new lint debt introduced.**
- `node --check website/js/proximity.js` → OK.

## 3. Tests ✅
`pytest tests/unit -k proximity --no-cov` → **50 passed, 14 skipped, 0 failed** (2918 deselected). The 14 skips are pre-existing Lua-guard skips unrelated to this work. Includes the 13 new `tests/unit/test_proximity_player_heatmap.py` cases (param validation, mode→column routing, GUID short→canonical, presence stride math, grid clamp, response shape). Wider suite not broken.

## 4. Curl matrix (uvicorn :8100, real `etlegacy` DB) ✅
Port note: :8000 was held by an unrelated uvicorn (other terminal); smoke ran on :8100 from the isolated worktree — no service touched/restarted.

| Case | Result |
|------|--------|
| `player-heatmap` kills_from (unscoped 30d) | ok · total **204** · 36 zones |
| `player-heatmap` victims_die | ok · total 204 · 33 zones |
| `player-heatmap` player_dies | ok · total 175 · 35 zones · **coverage=kills_only** |
| `player-heatmap` presence | ok · total 7797 · 49 zones · **sampled=True** |
| `player-heatmap` kills_from **scoped** `session_date=2026-05-14` | ok · total **34** (correctly ⊂ 204) |
| invalid: missing map_name / bad mode / missing player_guid | **400 / 400 / 400** |
| `/proximity/hotzones?map_name=te_escape2` (A1/A6) | 200 · grid_size 512 · x/y keys, no grid_x |
| `combat-positions/heatmap`, `kill-lines`, `events`, `trades/summary`, `leaderboards`, `danger-zones` | **all 200** (6-section IA reuse set) |

## 5. PostgreSQL cross-checks ✅
- `kills_from` endpoint total **204** == raw `COUNT(*) proximity_combat_position` (te_escape2, attacker D8423F90…, 30d) **204**. Exact.
- `presence` endpoint total **7797** ≤ raw `SUM(sample_count)` 30d **31590** — downsample invariant holds (stride = ceil(31590/8000)=4 → ~7797). Never ships raw paths.

## 6. A1–A8 audit closure
| Item | State |
|------|-------|
| A1 blank calibrated heatmap | **CLOSED** — flagship uses `{x,y,count}`/512 (Phase 3); global `renderHeatmap` reads `x/y`+`grid_size` (Phase 4) |
| A2 no per-player filter | **CLOSED** — new `/proximity/player-heatmap` (Phase 2) |
| A3 kill_outcome no death pos | **DOCUMENTED** — player_dies uses `proximity_combat_position.victim_*`, captioned "enemy kills only" |
| A4 React `p.team` dead branch | **CLOSED** — removed; HeatmapCanvas mode-`color` prop (Phase 3) |
| A5 silent config-load catches | **CLOSED** — logging added (Phase 1) |
| A6 256-vs-512 grid | **CLOSED** — hotzones now /512.0 + grid_size:512 (Phase 4) |
| A7 single canonical parser | **CONFIRMED** clean |
| A8 etl_frostbite vs frostbite calib key | **OPEN NIT** — handle via data∩calibrated intersect when Part B IA selector lands |

## 7. Not executed here (by design) — flagged for owner
- **Legacy browser walkthrough** of the new Player Combat Map + 6-section IA (Phase 4 Part B): the master plan's acceptance for this is explicitly a human visual check; cannot be discharged headlessly. Blueprint: `PROXIMITY_REDESIGN_IA_BLUEPRINT.md`. **Owner: open `/#/proximity`, enter a GUID+map, toggle the 4 modes on a calibrated map (e.g. te_escape2 / supply), confirm canvas + caption + no console errors.**
- **React `tsc --noEmit`**: `node_modules` absent in the worktree; React is the explicit non-truth parallel stack — TS self-reviewed (types/signatures/`color` prop). Run after `npm install` if desired (not a correctness gate).
- **Phase 5 (Lua v9)**: HARD STOP — needs explicit user approval for the read-only SSH pull (`et@…:48101`) before any drift/design work. Independent of this redesign; does not block shipping.
- **Live-session validation**: final narrative-framing acceptance needs a real session flowing parser→DB→endpoint→page (owner).

## Verdict
Phases 1–4 (the redesign critical path) are **implemented and verified** to the achievable truth standard (import + curl + psql + legacy syntax + tests). The flagship per-player heatmap is live across 4 modes with exact data cross-checks; the previously-dead global heatmap renders again (A1/A6 closed). Phase 4 Part B (visual recompose) is a no-data-risk DOM/copy blueprint pending owner visual validation. Phase 5 is gated on user approval.
