# Proximity Redesign — Part B-2 Report (2026-05-16)

Branch: `feat/proximity-ia-part-b-2` (off `origin/main` @ `60d936d`, post-#332).
Scope: the **verifiable** remainder of Phase 4 Part B + the last open audit NIT.
Correctness truth per the master plan = legacy JS render + `node --check` +
`html.parser` balance + curl smoke on `:8000` + `pytest -k proximity`. React
`tsc`/build is **not** a correctness gate (and deps are not installed in the
isolated worktree).

## Changes (4 stacked commits, pure DOM/copy + config — no Python/test/data-path)

| Commit | Summary |
|---|---|
| `e136f1a` | **A8** — explicit `etl_frostbite` key in `map_transforms.json` + `objective_zones.json` (mirrors `frostbite`; DB stores `etl_frostbite` exclusively). |
| `e7ac566` | **8→5 KPI** — Player Story to 5 narrative tiles; Hot Zones / Avg Duration / Avg Sprint cut; `renderSummary` derivations dropped in lockstep. |
| `f307891` | **7→3 leaderboards** — 10 ranked lists → 3 contextual panels + Class Signals; Sprint / Dodge / Support-Reaction cut; React `LEADERBOARD_TABS` 8→3. |
| `0facdb0` | **Section framing** — ④ Roles & Classes + ⑤ Engagements & Trades dividers (mirror ①②③); ⑥ = unchanged route targets. |

`git diff --stat origin/main...HEAD`: 5 files, +234 / −108 — `html js json tsx`
only (no `.py`, no tests, no migrations).

## A8 detail

`normalizeMapKey()` strips only ET color codes (not the `etl_` prefix), and
`getMapTransformEntry` does `maps[key] || maps[rawName]` with no alias
resolution. DB `map_name` is `etl_frostbite` in both `proximity_combat_position`
(596 rows) and `player_track`; configs only had `frostbite` → calibrated
background silently degraded to the relative-grid fallback on that map. The
dormant `aliases` field is dead metadata (consumed nowhere; all self-refs), so
an explicit per-version key was added — consistent with the existing
`adlernest` / `etl_adlernest` split. `objectives` parity (9) and `worldBounds`
parity asserted programmatically.

## Verification matrix (all green)

| Gate | Result |
|---|---|
| `git diff` scope | html/js/json/tsx only; no Python/test/migration |
| JSON validity | `map_transforms.json` + `objective_zones.json` parse OK |
| `node --check website/js/proximity.js` | OK |
| `html.parser` balance (`website/index.html`) | balanced — 0 unclosed, 0 mismatch |
| Section glyph sequence | `① ② ③ ④ ⑤` sequential + unique inside `#view-proximity` |
| KPI ids | 5 kept each ×1; `hotzones`/`avg-duration`/`avg-sprint` absent |
| Leaderboard ids | 7 kept each ×1; `sprint`/`dodge`/`support-reaction` absent in HTML **and** JS |
| React trim | `LEADERBOARD_TABS` = `[crossfire, survivors, movement]`; default `activeTab` valid |
| curl `:8000` | `/proximity/players`, `/proximity/player-heatmap?map_name=etl_frostbite`, `/proximity/combat-positions/heatmap?map_name=etl_frostbite` → all **200** |
| `pytest tests/unit -k proximity` | **61 passed, 14 skipped (pre-existing Lua guards), 0 failed** |

Note: `:8000` serves `/home/samba/share/slomix_discord` (merged #332), not this
worktree — the curl run confirms the A8 *data path* (endpoints serve
`etl_frostbite`); the calibration JSON takes effect once this branch is
deployed.

## Deferred (owner-visual — needs a browser walkthrough, per blueprint)

- Physical block reorder to the master-plan ideal order (④ Engagements
  **before** ⑤ Roles). Dividers are numbered to honest current DOM order; a
  large headless cut-paste is not visually verifiable.
- Dedup the separate v5.2 `#leaderboard-tabs` widget vs. the new contextual
  panels; fold the trailing v5.2 analytics tail (danger zones, combat heatmap,
  weapon accuracy, revives) into the 6-section frame.
- Full React glyph-section recompose (different component architecture; deps
  not installed; React is not the correctness gate).

All deferred items are pure DOM/copy with **no data-path risk**.
