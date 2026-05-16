# Proximity Redesign — Part B Owner-Visual Remainder (Plan)

Status: **plan only — not executed.** Acceptance for every item below is a
human browser walkthrough on the `:8000` preview; none can be discharged
headlessly. Execution waits on (1) your visual verification of the current
post-#334 preview and (2) your approval of this plan + its decision points.
All items are **pure DOM/copy — no data-path, schema, or endpoint change.**

---

## Step 0 — your visual verification first (post-#334 preview)

Hard-refresh `http://<preview>:8000/#/proximity` (**Ctrl+Shift+R** to bypass
browser cache). Confirm:

- [ ] Section dividers read `① Player Combat Map · ② Player Story · ③ Map
      Context · ④ Roles & Classes · ⑤ Engagements & Trades`.
- [ ] ② Player Story shows **5** tiles (Engagements · Avg Distance · Crossfire
      · Escape Rate · Avg Attackers "Enemies drawn per duel") — no Hot Zones /
      Avg Duration / Avg Sprint.
- [ ] ④ shows **3** contextual panels (Space & Pressure / Finishers & Survival
      / Tempo & Movement) + Class Signals — no old Movement/Teamplay/Combat
      Reaction quad-panels.
- [ ] Pick a player + `etl_frostbite` map → the Player Combat Map renders on a
      **calibrated background image** (A8 fix), not a blank/relative grid.
- [ ] No console errors; player+map cascade still feeds Hero + Map Context.

If anything is off, that is feedback for *before* the items below.

---

## Item 1 — physical reorder: ④ Engagements before ⑤ Roles (HIGH value)

Master-plan ideal order is HERO → Story → Map Context → **Engagements &
Trades** → **Roles & Classes** → Replay. Current legacy DOM has the ranked
panels (Roles) physically before the engagement panels.

- **Exact blocks** (`website/index.html`):
  - ④ Roles block: divider `~2201` → end of Class Signals grid `~2301`.
  - ⑤ Engagements block: divider `~2302` → end of Engagement Inspector grid
    `~2602` (before `<!-- v5.2 Danger Zones -->` at `2603`).
- **Move**: relocate the Roles block (~100 lines) to *after* the Engagements
  block (~300 lines), then renumber the glyphs: Engagements becomes **④**,
  Roles becomes **⑤** (captions/accents follow).
- **Risk**: large headless block move. **Mitigation**: programmatic exact-range
  extraction + reinsert, then `html.parser` balance + glyph-sequence + id-count
  (kept ×1 / cut absent) + `node --check`. Visual layout (grid flow/spacing)
  still needs your browser confirm.

## Item 2 — dedup the v5.2 `#leaderboard-tabs` widget (DECISION NEEDED)

`website/index.html:2645` has a second leaderboard widget (`#leaderboard-tabs`
/ `#leaderboard-content`, range buttons `#lb-range-btns`) — the full 8-category
tabbed explorer, wired by `renderLeaderboardTabs()` (`proximity.js:2859`,
called `:3103`, click `:3105`, range `:3112`). The new ④ contextual panels are
curated; this widget is the only "all categories + range toggle" view.

**Decision (your call):**
- **2a — Reframe & relocate (recommended):** keep the widget but move it inside
  the Roles section as a collapsible "All Categories (advanced)" drill-down.
  Preserves the full explorer, removes the *duplication feel*. JS untouched.
- **2b — Remove:** delete the DOM block + the `renderLeaderboardTabs()` call +
  its two listeners (function itself null-guards, so dead-safe). Loses the
  all-category/range explorer entirely.

## Item 3 — fold the v5.2 tail into the 6-section frame (DECISION NEEDED)

After ⑤ today: **Danger Zones** (`:2603`), **Combat Heatmap** (`:2625`),
**Weapon Accuracy + Revives** (`:2661`). Proposed placement:
- Danger Zones + Combat Heatmap → **③ Map Context** (both are map-spatial;
  joins the Hot Zone heatmap thematically).
- Weapon Accuracy + Revives → **⑤ Roles & Classes** (per-player/role signals)
  *or* cut as prototype noise.
- **Decision:** (3a) fold both groups as above; (3b) fold map-spatial only,
  cut Weapon Accuracy/Revives; (3c) leave the tail as an explicit
  "Deep Analytics" appendix below ⑤ (no ⑥ — that stays route-targets).

## Item 4 — React glyph-section recompose (LOW priority)

`Proximity.tsx:1525` render order: scope/summary → `PlayerHeatmapPanel` →
heatmap → `TradesPanel` → `ProxScoresPanel` → KillOutcomes → HitRegions →
Movement → DangerZones → CombatHeatmap → SessionScore. Add lightweight
`<SectionHeader n="①".."⑤">` components mirroring legacy and reorder to match
Items 1/3. **Caveat:** React deps are **not installed** in the isolated
worktree and React is **not the correctness gate** (legacy is truth); this
ships behind merge-CI `tsc` only. Lowest priority; do after 1–3 are owner-OK.

---

## Sequencing & verification

1. You verify Step 0 on the preview.
2. You answer the Item 2 / Item 3 decision points.
3. I execute Items 1→3 on a fresh branch off updated `main`
   (`feat/proximity-ia-part-b-3`), stacked commits, one bundled PR.
4. Headless gates per item: `html.parser` balanced, glyph sequence
   `①②③④⑤` unique, KPI/leader ids (kept ×1 / cut absent in HTML+JS),
   `node --check`, curl `:8000` reused endpoints 200, `pytest -k proximity`.
5. Item 4 (React) last, flagged tsc-on-CI only.
6. **Final acceptance = your browser walkthrough** (the headless gates prove
   structure/no-regression, not visual correctness).

---

## Status — SHIPPED (2026-05-16, branch `feat/proximity-ia-part-b-3`)

Owner approved both decision points (Item 2 = reframe & relocate;
Item 3 = fold all). All four items executed:

- **Item 1** ✅ ④ Engagements & Trades now precedes ⑤ Roles & Classes
  (deterministic asserted block reassembly; glyphs/accents renumbered;
  obsolete "Phase 4 IA note" + "relocated" leftover comments dropped).
- **Item 2** ✅ v5.2 `#leaderboard-tabs` explorer relocated under ⑤ Roles
  inside a collapsible `<details>` "All Categories (advanced)"; JS/ids
  untouched.
- **Item 3** ✅ Danger Zones + Combat Heatmap folded into ③ Map Context
  (balanced pair moved as one unit); Weapon Accuracy + Revives under
  ⑤ Roles.
- **Item 4** ✅ React lightweight `SectionHeader` ①..⑤ framing at existing
  boundaries (no panel reorder — divergent render; CI tsc is the gate).

**Verification (all green):** legacy `index.html` id multiset **identical**
to `origin/main` (490/490, delta empty — no id lost/dup/added → no JS
binding or data-path touched), `html.parser` balanced, glyph sequence
`①②③④⑤` sequential+unique, `node --check` proximity.js OK,
`pytest -k proximity` 61 passed / 0 failed, curl `/proximity/{players,
leaderboards,player-heatmap?etl_frostbite,combat-positions/danger-zones}`
all 200. React: 5 well-formed self-closing `SectionHeader`, file brace
balance 0 (tsc deferred to CI — React not the correctness gate).

**Final acceptance remains the owner browser walkthrough** — the headless
gates prove structure / no-regression, not visual correctness.
