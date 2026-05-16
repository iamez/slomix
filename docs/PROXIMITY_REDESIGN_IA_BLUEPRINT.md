# Proximity Redesign — Phase 4: Map-First IA Blueprint

**Date:** 2026-05-16 · **Branch:** `feat/proximity-redesign`

Phase 4 has two parts. **Part A (shipped & verified in this branch)** is the
concrete, testable core. **Part B (this blueprint)** is the executable visual
recompose whose acceptance is, by the master plan's own definition,
*human-visual* ("legacy manual walkthrough — 6 sections render, player
cascade, no console errors") and is therefore staged here for owner manual
validation rather than blind-applied to the production page without a way to
verify it headlessly.

---

## Part A — shipped in Phase 4 (verifiable, done)

**A1 + A6 closed — the global heatmap was dead on all 20 calibrated maps.**

Root cause (from `docs/PROXIMITY_REDESIGN_AUDIT_2026-05-16.md`): `/proximity/
hotzones` (`proximity_combat.py`, source `combat_engagement`) bucketed at
`/256.0` and the dict was keyed `x,y`; `renderHeatmap` read `zone.grid_x/
grid_y` (undefined → NaN → skip-all → blank on calibrated maps) and
reconstructed world coords at `512`.

Fix:
- `website/backend/routers/proximity_combat.py`: `FLOOR(... / 256.0)` →
  `FLOOR(... / 512.0)`; response now carries `"grid_size": 512` (unifies the
  whole page on the 512 world-grid the rest of the stack already uses).
- `website/js/proximity.js` `renderHeatmap`: reads `zone.x/zone.y` (the keys
  the endpoint actually emits) and the fallback reads `h.x/h.y`; world
  reconstruction + `cellRadius` use `payload.grid_size || PROXIMITY_GRID_SIZE`.

Verified (uvicorn :8100 + served-asset grep):
- `GET /proximity/hotzones?map_name=te_escape2` → `status ok`, `grid_size
  512`, 50 zones, sample `{x:-10,y:4,count:263,kills:169,deaths:94}`, every
  zone has `x/y` and no `grid_x`.
- `GET /proximity/hotzones` (no map) still auto-selects the busiest map
  (`te_escape2`) → global-capable path intact.
- Served `js/proximity.js`: **0** `zone.grid_x`/`h.grid_x` references
  (the bug), `Number(zone.x)` + `payload?.grid_size` present.

This also closes audit item **A6** (256-vs-512) and the global half of **A1**;
the per-player flagship already sidestepped A1 in Phase 3 by consuming the
`{x,y,count}`/512 contract.

---

## Part B — 6-section map-first IA (executable blueprint, owner-validated)

Player selector is a **page-level** control feeding the Hero + Story Strip +
Map Context (shared selected-player + selected-map state).

| # | Section | Legacy DOM block (`index.html` `#view-proximity`) | React (`Proximity.tsx`) | Endpoint(s) reused | Framing (numbers **with** narrative, no verdict) |
|---|---------|---------------------------------------------------|-------------------------|--------------------|-------------------------------------------------|
| 1 | **HERO — Player Combat Map** | the new `Player Combat Map` panel (added Phase 3) — **move to top of `#view-proximity`, full-bleed**, promote the player/map selector to page-level | `<PlayerHeatmapPanel/>` — move above all panels in `Proximity()` render; lift map/guid to a page context | `/proximity/player-heatmap` (4 modes) | "Where {player} fights on {map}" — 4 lenses, no good/bad |
| 2 | **Player Story Strip** | compress the 8 KPI tiles → 5; one sentence each | KPI row → 5; pull copy from a glossary const (reuse `InfoTip`/`stripColors`) | `/storytelling/player-narratives`, `/proximity/player/{guid}/radar`, `/storytelling/{gravity,space-created,enabler,lurker-profile}` | "pulls 2.3 enemies of attention — top 15%" |
| 3 | **Map Context** | the (now-fixed) global heatmap panel + danger-zones + objective zones | global `<HeatmapCanvas/>` mount + `<DangerZonesPanel/>` | `/proximity/hotzones` (**fixed**, 512/`{x,y,count}`), `/proximity/combat-positions/danger-zones`, `objective_zones.json` | "this map's blood & objective pull" |
| 4 | **Engagements & Trades** | Combat Events + Trades panels + event-detail canvas | `<CombatHeatmapPanel/>` (kill-lines) + trades panels | `/proximity/trades`, `/proximity/events`, `/proximity/combat-positions/kill-lines` | narrative trade timeline |
| 5 | **Roles & Classes** | Class Summary + collapse 7 leaderboard tabs → 3 contextual | leaderboard tabs → 3 | `/proximity/leaderboards`, storytelling synergy | "who creates space, who finishes" |
| 6 | **Round Replay / Teams** | unchanged — keep `#/proximity/round/{id}` & `/teams` route targets | leave `ProximityPlayer/Teams/Replay.tsx` intact | existing | deep-dive, unchanged |
| — | **CUT** | timeline sparkline; metric-guide modal (→ inline `InfoTip`s); 4 redundant KPI tiles; 4 redundant leaderboard tabs | same | — | reduce prototype noise |

### Apply order (low-risk → high-risk)
1. **(done)** A1/A6 backend+renderer fix — Section 3 now actually renders.
2. Promote the Phase-3 Player Combat Map to the top of `#view-proximity`
   (single DOM block move; `bindV52PanelEvents` wiring is id-based so it
   survives relocation) + React `<PlayerHeatmapPanel/>` to render top.
3. Re-label/re-order the remaining panels into the 6 groups (no logic
   change — purely section headers + DOM order in `loadProximityView`'s
   render sequence / `Proximity()` JSX order).
4. CUT list (delete the sparkline + modal + redundant tiles/tabs).
5. Glossary-driven one-liner captions per KPI.

Steps 2–5 are **DOM/copy reordering only** — no endpoint or data-path change
(every endpoint in the table is already live and cur-verified). They are
deferred to an owner-validated pass because their acceptance criterion in the
master plan is a human browser walkthrough ("6 sections render, player
cascade, no console errors"), which cannot be discharged headlessly in this
environment. This matches Phase 6 item 6 (live-session / owner validation).

### Verification when Part B is applied
- `node --check website/js/proximity.js`; backend import; curl every endpoint
  in the table (all already green).
- Owner manual walkthrough on `/#/proximity`: 6 sections in order, page-level
  player/map cascade feeds Hero+Strip+Context, no console errors, calibrated
  background on the Hero + Map Context canvases.
- React: `tsc --noEmit` (typecheck only — NOT correctness proof).

---

## Status

- **Part A: COMPLETE & verified** (A1+A6 closed; global heatmap renders).
- **Part B: BLUEPRINT READY** — DOM/copy-only recompose, no data-path risk;
  flagged for owner manual validation per the plan's human-visual acceptance.
