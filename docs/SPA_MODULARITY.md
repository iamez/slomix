# SPA modularity — measured state, remediation plan, rules (2026-09-07)

Owner's question (2026-09-07): *the new site will change a lot; I like the colours
and the theme, but the way text/data is shown on some pages and its visibility
must change, and proximity/telemetry feels minimal. Is the site built so that
such changes are quick and simple? If not, plan the fix and set rules.*

Answer, measured (read-only audit of `website/frontend/src/app` at main
`7ced9435`; every count has its command; two counts were re-measured by a
second person and agree within counting method):

| dimension | verdict | number |
|---|---|---|
| tokens (type, colour, space) | **good** | 652 of 654 `fontSize` uses are `var(--fs-*)`; 30 hex literals vs 2,086 `var(--)`; raw-size ratchet at 26 (from 1,010) |
| empty / error / pending vocabulary | **good** | `Pending`/`Unavailable`/`Absent` in 31–34 of 38 pages; grey-note ratchet at 41 (from 66) |
| proximity / telemetry coverage | **good** | 66 of 67 proximity endpoints consumed (only `/proximity/dashboard` unused); 53 `ProxPanel`s; 92/92 inventory rows covered |
| primitives reuse (layout) | **partial** | 44 hand-built `gridTemplateColumns` layouts vs 2 `DataTable` uses; 1,412 inline `style={{}}` in 38/38 pages; 9 of 16 doc-11 §A units and 1 of 14 §B patterns exist |
| declarative page config | **weak** | 1 page of 38 defines columns as data; `dataset_registry` (34 descriptors, `GET /api/datasets`) drives **zero pixels**; 169 of 179 rendered `data-parity` panels are unknown to it |

**So:** "make this text bigger / this colour stronger" is one line in
`src/app/tokens.css` (e.g. `--fs-caption` reaches 260 sites). "Change how a panel
looks or which panels a page shows" is not: a panel is not a component, it is
`SectionHead` + a hand-built grid + inline styles, repeated per page. The
loading/error/empty/failure four-way branch is hand-rolled 58–62 times (by counting
method) outside proximity, while `ProxPanel` (`pages/proximityShared.tsx`) already
solves it in one place — for proximity only. Telemetry is the opposite of minimal;
what it lacks is *depth* (spider-web layer 3 not drawn, layer 4 not started,
`/api/replay/round/{id}/positions|paths` unused), not endpoints.

## Remediation plan — eight slices, one PR each, in this order

Each slice: branch + PR ≤ 25 files, a ratchet seeded at the measured value and
lowered in the same commit, mutation seen failing, `npm run typecheck && npm run
test` (never `npx`), and no visual change unless the slice says so.

1. **Promote `ProxPanel` to `components/Panel.tsx`** (re-export from
   `proximityShared` so proximity does not move). Ratchet: count of
   `isPending && <Pending` in `pages/` (58 on 2026-09-07 by `grep -o`, test files
   excluded), budget = measured, must only fall.
2. **Convert the five heaviest hand-rolled triads to `<Panel>`**: Story (9), Home
   (7), SessionDetail (5), AvailabilityPage (5), SkillRating (4). Ratchet from
   slice 1 drops by ≈30. Playwright parity inventory unchanged (same `data-parity`).
3. **`components/GridRow.tsx`** (`cols`, `divided`, `align`) for the 44
   `gridTemplateColumns`; convert Home (7) and About (7) first. Ratchet on
   `gridTemplateColumns` in `pages/`, seed 44.
4. **`lib/format.ts`**: `mmss` (move from RoundsTable), `pct`, `num`, `dateShort`.
   Ratchet on `.toFixed(` + `toLocaleString(` + `slice(0, 10)` in `pages/`, seed 188.
5. **Adopt `DataTable` on Leaderboards and MapsPage** (both hand-sort today).
   `DataColumn<` declarations 4 → 6 files; sort round-trip asserted in
   `DataTable.test.tsx`.
6. **Grow the dataset register to the 53 proximity panels** (they already carry
   `parity_key`-shaped `data-parity`). Reverse assertion: every rendered
   `data-parity` panel has a descriptor, with `tests/data/unregistered_panels.txt`
   seeded at 169 and ratcheted down.
7. **Add `Hidden` as a fourth state in `ui.tsx`** (a `ui.tsx`-only PR, no backend,
   no table). Doc 19 §5: hiding is a decision taken *before* the request, absence is
   a fact about the data — reusing `Absent` would be one name for two measurements.
   A hidden panel sends no query and leaves a low-contrast trace, never a silent
   hole. Proof: `components.test.tsx` case that `Hidden` renders a trace rather than
   nothing, and a `vocabulary.test.ts` pin that `Hidden` and `Absent` cannot share a
   colour (same shape as the existing `Absent`/`Unavailable` pin). Contract, shared
   with the doc 19 slice 3 line in `HANDOFF-astra-inventory.md`: the hidden panel's
   `data-parity` node is absent and no query is sent; only the trace remains. This is the
   smallest piece of doc 19 §9 slice 3 with no schema risk; the column picker on
   the basics table (doc 19 §9 slice 2: `user_page_layouts` migration with the
   `website_app` GRANT in the same file, `GET/PATCH /api/preferences/session-detail`)
   follows once the owner answers doc 19 §10 (#3 admin UI vs config, #5 position in
   the Stats 2.0 lane). Slice 5 (`DataTable` adoption) is the enabler for that
   picker, not cosmetic cleanup.
8. **Hex/rgba sweep**: 30 hex + 17 rgba literals in pages → two missing tokens
   (`#151a1e` active-chip bg, `#33322e`) added to `tokens.css`; ratchet in
   `tokens.test.ts` counting colour literals with comments stripped (a naive
   `#[0-9a-f]{3,}` grep scores 161 because it eats `#813` PR references — the
   honest number is 30).

After 1–8 a per-page display change is: edit one token (text/colour), one
`Panel` prop (chrome), one column list (what a table shows), or, once doc 19 §9
slices 2–3 land, one preference row (whether a panel shows). Slices 1–4 and 8 are safe for any agent
now; 5–7 touch behaviour and go through the owner's DA per PR as usual.

## Status

- 2026-09-07: slice 1 (`components/Panel.tsx` + `panels.test.ts`, seed 61) in PR #970; slice 2
  converted twelve panels (SkillRating rated players; Home challenge, predictions;
  Story escorts, momentum, kill impact, synergy, composite, players; SessionDetail
  top dpm; Availability week, tonight) — ratchet 61 → 49, vocabulary 41 → 40.
  Panel gained `gap`, `parity`, a JSX `aside` and an `empty(data)` function so a
  conversion is not a visual change. Left hand-rolled on purpose: panels with no
  head (`Lbl` instead of `SectionHead`, or none), gated formula reveals, and the
  market panel with admin controls beside its body — each is a design decision,
  not a mechanical edit.

## Guards that already exist (11) — extend, do not duplicate

| guard | value (2026-09-07) | what it pins |
|---|---|---|
| `tests/data/endpoint_gap.txt` | 13 | legacy-called paths the SPA does not cover (fails in both directions) |
| `tests/data/endpoint_required_extra.txt` | 4 | paths required without a legacy grep hit |
| `tests/data/response_model_gap.txt` | 217 / 263 | routes without `response_model=` |
| `tests/data/manual_type_drift.txt` | 0 (`COMPARED_FLOOR = 36`) | hand-written TS types vs OpenAPI; the compared set cannot shrink |
| `src/app/tokens.test.ts` `BUDGET` | 26 (from 1,010) | raw sizes in style props; ramps monotonic; `@theme static`; `--layout-max` ×4 |
| `src/app/vocabulary.test.ts` `BUDGET` | 41 (from 66) | grey notes outside `<Absent reason=>`/`<Meta>`; `Absent`≠`Unavailable` colours; `reason` required (type-level) |
| `src/app/lib/fixturesCoverage.test.ts` | 214 fixtures | every called endpoint has a recorded fixture |
| `tests/unit/test_proximity_inventory.py` | `PENDING_BUDGET = 0` | 92/92 proximity rows covered; ten tab names |
| `tests/unit/test_parity_keymap.py` | `UNMAPPED_BUDGET = 2` | Map Distribution (home), Charts (session-detail) |
| `tests/unit/test_dataset_registry.py` | 34 descriptors, asserted only as `len(DATASETS) >= 30` (not a ratchet; slice 6 adds the exact baseline) | every `parity_key` renders; heavy sections from measured cost |
| `tests/unit/test_status_vocabulary_crosses_the_language_boundary.py` | 22 statuses | Python and TS classify the same set |

Both frontend budgets glob only `src/app`; `test_endpoint_gap.py` carries
`test_the_other_react_tree_does_not_count_as_migrated`. The old React tree
(`src/pages` 11,472 LOC, `src/api` 20,313 LOC) still ships beside `src/app`
(32,791 LOC) and is scheduled for deletion at switchover; no ratchet covers it, by
design. Guard code reads source through `src/app/testing/sourceText.ts`
(`stripComments`), never prose — a naive hex grep counts `#813` PR references.

No guard exists yet for: hand-rolled triads, hand-rolled grids, colour literals,
number/date formatting, panels absent from the register. Slices 1, 3, 4, 6 and 8
each add one.

## What this plan does NOT do

- It does not change the look. The owner's per-page dislikes are collected in
  `docs/DESIGN_PUNCHLIST.md` and fixed *after* the panel exists, one token or one
  prop at a time, so a fix on one page reaches every page that shares the unit.
- It does not build spider-web layers 3–4 (owner-ordered, `docs/SPIDERWEB_STATUS.md`).
- It does not add `user_page_layouts` (doc 19 r. 2, owner decision).

## Rules for every new page or panel from now on (also in `website/frontend/AGENTS.md`)

1. A panel is `<Panel>` (after slice 1: `<ProxPanel>` until then). Never write
   `isPending && <Pending/>` by hand.
2. A list of rows is `<DataTable>` with a `DataColumn<Row>[]` declared as data, or
   `<GridRow>` for non-sortable rows. No new `gridTemplateColumns` in `pages/`.
3. Numbers and dates go through `lib/format.ts`. No `.toFixed(` in `pages/`.
4. Sizes and colours are tokens: `var(--fs-*)`, `var(--space-*)`, `var(--color-*)` (49 colour tokens in `tokens.css`; there is no `--c-*`).
   No hex, rgb() or raw px except the 1px hairline.
5. Every section carries `data-parity="page.panel"` and, once slice 6 lands, a
   descriptor in `dataset_registry.py`.
6. Each rule is a ratchet in `src/app/*.test.ts` or `tests/data/*.txt`: the budget
   only falls, and it falls in the same commit that earns it.
