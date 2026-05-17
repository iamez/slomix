# Proximity Redesign — Final Report (2026-05-17)

Authoritative end-state for the proximity page major redesign master plan
(`docs/PROXIMITY_REDESIGN_MASTER_PLAN.md`). Supersedes the interim P6 /
Part B-2 / owner-visual reports for status purposes; those remain for detail.

## Outcome: all verifiable phases COMPLETE & merged

| Phase | Scope | Status |
|---|---|---|
| 1 | Audit / bugfix / review | ✅ merged — `docs/PROXIMITY_REDESIGN_AUDIT_2026-05-16.md` |
| 2 | Backend `/proximity/player-heatmap` + `/proximity/players` | ✅ merged (#328) |
| 3 | Per-player multi-perspective heatmap (legacy + React) | ✅ merged (#328/#330/#332) |
| 4 | Full visual redesign / 6-section map-first IA | ✅ merged (#330/#332/#334/#336) |
| 5.0 | Lua live-vs-repo drift | ✅ no drift (live == repo v6.01, SHA-256 match) |
| 5.1/5.2 | Lua v9 true-aim — local design + parser + schema + migration | ✅ merged, **dormant** (`features.shot_fired=false`), backward-compatible |
| 5.3 | Lua v9 **deploy** (server + prod DB) | ⛔ **GATED — not executed.** Runbook: `docs/PROXIMITY_LUA_V9_DEPLOY_RUNBOOK.md` |
| 6 | End-to-end verification | ✅ this report |

## PR ledger

| PR | Date | Content |
|---|---|---|
| #328 | 05-16 | Page redesign — per-player heatmap endpoint, A1/A6 fix, map-first IA base; Lua v9 local (dormant) folded in |
| #330 | 05-16 | Part B safe subset — cuts, hero promotion, ①②③ dividers |
| #332 | 05-16 | Player dropdown (replaces GUID text entry) + Part B continuation |
| #334 | 05-16 | Part B-2 — A8 `etl_frostbite` fix, 8→5 KPI, 7→3 leaderboards, ④⑤ dividers |
| #336 | 05-17 | Part B owner-visual — ④-before-⑤ physical reorder, v5.2 fold/dedup, React ①..⑤ framing |

## Audit closure (A1–A8)

- **A1/A6** ✅ global heatmap renders on all 20 calibrated maps (renderer
  reads `{x,y,count}` + `payload.grid_size`; backend standardized on
  `proximity_combat_position` / 512).
- **A2** ✅ per-player filter — new `/proximity/player-heatmap` passes
  `player_guid`/`player_guid_columns` through `_build_proximity_where_clause`.
- **A3** ✅ documented — `proximity_kill_outcome` has no death position;
  `player_dies` uses `proximity_combat_position.victim_*` (`coverage:
  kills_only`, captioned). Full coverage needs Lua v9 (gated).
- **A4** ✅ React `HeatmapCanvas` dead `p.team` branch removed.
- **A5** ✅ logging added for the silent zero/table-count path.
- **A7** ✅ parser confirmed the real `ProximityParserV4`.
- **A8** ✅ explicit `etl_frostbite` calibration key (DB stores it
  exclusively; only `frostbite` existed) in `map_transforms.json` +
  `objective_zones.json`.

## Final IA (legacy `#view-proximity`, production truth)

`① Player Combat Map` (hero, per-player, 5 modes incl. dormant `aim`) →
`② Player Story` (5 narrative KPIs) → `③ Map Context` (global heatmap +
Top Synergy Duos + Danger Zones + Combat Heatmap) → `④ Engagements &
Trades` → `⑤ Roles & Classes` (3 contextual leaderboards + Class Signals +
Weapon Accuracy + Revives + collapsible "All Categories (advanced)"
explorer) → `⑥` Round Replay / Teams (unchanged route targets).
React mirrors the ①..⑤ framing (`SectionHeader`).

## Verification matrix (correctness truth = legacy + import + curl + psql)

- Legacy `index.html`: `html.parser` balanced; id multiset identical
  before/after the reorder (490/490, no id lost/dup) — no JS binding or
  data-path touched; glyph sequence ①②③④⑤ unique.
- `node --check website/js/proximity.js` OK.
- `pytest tests/unit -k proximity` → 61 passed, 14 pre-existing skips, 0 fail.
- curl `:8000` `/proximity/{players,player-heatmap,leaderboards,
  combat-positions/{heatmap,danger-zones}}` incl. `etl_frostbite` → all 200.
- React: CI `Docker Build` (incl. tsc) SUCCESS on every PR; #336 CI 9/9
  SUCCESS (Codacy 0 issues after the object-injection-sink fix).
- Lua v6.02 in `main` is **dormant** (`shot_fired=false`); parser reads
  v6.01 and v6.02; migration 055 idempotent + schema mirrored.

## Remaining — requires the awake owner (NOT autonomous)

1. **Owner browser walkthrough** of `:8000/#/proximity` (hard-refresh) —
   final visual acceptance of the 6-section IA. Headless gates prove
   structure / no-regression, not visual correctness.
2. **Phase 5.3 (HARD STOP)** — Lua 6.02 deploy + prod migration 055 +
   enabling `features.shot_fired`, incl. runtime-validating `ps.viewangles`.
   Gated on explicit, awake, step-by-step approval. See the runbook.
3. **Live-session narrative validation** — owner confirms the storytelling
   framing against a known real session/player.

Nothing in (1)–(3) was performed autonomously. Everything else is shipped.
