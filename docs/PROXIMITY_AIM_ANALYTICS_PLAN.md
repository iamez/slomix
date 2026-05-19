# Proximity Full Aim Analytics — Master Plan

> Branch: `feat/proximity-player-aim` (off `main`). ONE bundled PR, scope
> `proximity`. Legacy JS = production truth; React = parallel stack.
> Additive only — must NOT alter the shared `player-heatmap` contract.

## 0. Goal

Surface the v9 true-aim data (`proximity_shot_fired`: origin + `view_yaw`/
`view_pitch`) on the Player Combat Map as a 5th **Aim** lens with **full aim
analytics**: per-zone aim rose, pitch profile, circular spread metrics, and
narrative one-liners. Owner philosophy: storytelling **with** numbers,
"invisible value" — describe aim patterns, do not fabricate verdicts.

## 1. Real-world grounding (researched before designing)

- **Esports (Leetify/scope.gg):** the gold standard is *reconstruction-based,
  enemy-relative* (crosshair-to-enemy distance, time-to-damage). Raw angle
  distributions are a weaker signal. Aim is presented as actionable
  weakness-highlighting patterns (validates narrative framing).
- **Circular statistics:** arithmetic mean of angles is wrong (355°≈5°). Use
  circular mean, **mean resultant length R** for concentration, **von Mises**
  model, **Rayleigh test** for "directional vs uniform". Wind rose = canonical
  viz (circular histogram; spokes = direction frequency; colour = secondary
  variable).
- **Sports shot charts (NBA hexbin):** encode position + volume (size/alpha) +
  quality (colour) per bin; **filter bins below a minimum sample size**;
  colour relative to a baseline, not absolute.
- **Data/DB spatial:** server-side pre-aggregate into grid bins + downsample;
  square grid is fine for dense close points; hexbin is prettier but
  non-portable/non-hierarchical → keep the square grid for ecosystem
  consistency.

Sources: Leetify "Enemy (actually) spotted"; scope.gg; Wikipedia Circular
mean; CircStats MRL; NBA shot-chart analytics (Bredikhina); H3 hexbin
comparison.

## 2. Honest scope boundary

`proximity_shot_fired` has shot origin + yaw/pitch but **no enemy position at
shot time**. Therefore:

| | Phase 1 — NOW (data supports) | Phase 2 — FUTURE (needs enemy-relative) |
|---|---|---|
| What | Positional + directional aim patterns: where they shoot from, dominant look-angles, aim spread/concentration (R), pitch tendency, Rayleigh directional-vs-uniform | Leetify-grade: crosshair-to-enemy distance, pre-aim, time-to-damage |
| Source | existing `proximity_shot_fired` | join shot↔victim/engagement, or a Lua extension |

Phase 1 only. Phase 2 documented as an extensible future direction; the v1
response contract is shaped so enemy-relative fields can be added later
without breaking consumers.

## 3. Architecture (integration-safe)

- **NEW endpoint `GET /proximity/player-aim`** in
  `website/backend/routers/proximity_positions.py` (after
  `get_proximity_player_heatmap`). Do **NOT** modify `mode=aim` or the shared
  `player-heatmap` contract (3 consumers + ~30 tests). Strictly additive.
  Auto-wires via `proximity_router.py` (includes `positions_router` whole).
- Reuse existing infra verbatim: `_build_proximity_where_clause`
  (`player_guid` + `player_guid_columns=["guid"]` + scope), GUID resolvers
  (`_resolve_player_guid_canonical`, `_load_scoped_guid_name_map`,
  `_resolve_name_for_guid`), calibrated `map_transforms.json`, scoped-fetch.
  Zero new ecosystem patterns.
- **Circular stats in one extracted, unit-testable Python helper**
  `_circular_yaw_stats(...)`; include the **Rayleigh test** (R, Z = nR²,
  p ≈ exp(−Z)) as an honest gate for the "directional" narrative.
- **Square grid** (`FLOOR(x/g)`), 16×22.5° yaw buckets, 6×30° pitch buckets —
  consistent with the existing 4 lenses; deliberate (not hexbin).
- **Dual-stack:** legacy JS+HTML (truth) gets a `data-pmode="aim"` button +
  `renderPlayerAim()` (rose glyphs + pitch bars + spread chips + narrative);
  React parallels with `AimCanvas` + `PlayerAimPanel`.

### Response contract (`/proximity/player-aim`)

```jsonc
{
  "status": "ok", "map_name": "...", "player_guid": "<canonical>",
  "player_name": "...", "grid_size": 512, "total": <n>, "sampled": <bool>,
  "scope": { ... },
  "hotzones": [ { "x":int, "y":int, "count":int,
                  "rose":[16 ints], "mean_yaw":deg, "r":0..1 } ],
  "yaw_buckets": 16, "yaw_bucket_width_deg": 22.5,
  "pitch_hist": { "edges":[-90,-60,-30,0,30,60,90], "counts":[6 ints] },
  "circular": { "n":int, "mean_yaw_deg":deg, "resultant_length":0..1,
                "circular_std_deg":deg, "rayleigh_p":float,
                "pitch_mean_deg":deg, "pitch_std_deg":deg },
  "narrative": ["1,506 shots tracked", "Most shots aimed SW (28%)", ...]
}
```

SQL: 3 awaited queries sharing one `params` tuple — (1) per-cell yaw rose via
`FLOOR` grid + `width_bucket` on yaw shifted to `[0,360)`; (2) global pitch
`width_bucket` 6 bands; (3) circular aggregates `AVG(SIN/COS(RADIANS(yaw)))`,
`AVG/STDDEV_POP(pitch)`. Wrap-safe math (atan2, R, circ-std, Rayleigh) in the
Python helper — never arithmetic mean of yaw. Cap emitted rose cells at 120
by count (`sampled=true` if truncated); `min_cell` default 8.

Narrative rules (constants near handler; from real stats only):
sample-size line always; if `n≥40`: dominant sector (suppress < 22%),
horizontal spread tight<25°/moderate/wide>60° from circ-std, pitch
up/level/down (±8°), Rayleigh "directional (p<0.05)" vs "no dominant
direction". No fabricated "centre".

## 4. "Don't break anything / seamless" safeguards

1. New endpoint only; zero changes to existing endpoints/contracts/tests.
2. Branch from `main` (never the parallel `chore/omnibot-*` workstream).
3. Reuse existing helpers/patterns — no new ecosystem concepts.
4. Graceful empty/loading states like the existing lenses.
5. Gates: `python -c import` + new unit test + `pytest -k proximity` (existing
   stay green) + **psql cross-check of circular stats** (hard correctness
   gate) + curl matrix on :8000 + legacy manual render. React `tsc` only
   (NOT a correctness proof).
6. One feature branch, stacked commits, ONE PR, Conventional Commits scope
   `proximity`; autonomous merge after green CI + addressed review comments.
7. Pure website/repo work — no SSH, no prod DB, no live server.

## 5. Execution order

1. Backend: `/proximity/player-aim` + extracted `_circular_yaw_stats`
   (+ Rayleigh). 
2. `tests/unit/test_proximity_player_aim.py` (circular-mean correctness,
   rose bucketing, `min_cell`/cap, narrative rules, 400s, GUID resolve,
   shape, `total==circular.n`). Run `pytest -k proximity` green.
3. psql cross-check (endpoint vs manual circular SQL; show arithmetic mean
   differs) + curl matrix on running :8000.
4. Legacy JS + HTML (production truth): `PLAYER_HEATMAP_MODES` += `aim`,
   `data-pmode="aim"` button, `renderPlayerAim()` + `drawAimRose`/
   `drawPitchBars`, Aim DOM panel; wire into scoped refresh. Manual render
   check.
5. React parallel: `PlayerAimResponse` type, `getPlayerAim`, `usePlayerAim`,
   `AimCanvas` + `PlayerAimPanel`, glossary entries; `tsc --noEmit`.
6. Full verification pass → ONE PR.

## 6. Top risks

1. **Circular-statistics correctness (highest):** arithmetic mean of yaw is
   silently wrong. Mitigation: single extracted unit-tested helper + psql
   hard gate + explicit "yaw wraps, pitch does not" comment/test.
2. **Dual-stack canvas rose angle convention:** legacy `worldToCanvasPoint`
   Y-flip vs React naive projection — derive world-yaw→screen-angle per
   stack, visually verify one known cell (wrong sign mirrors every rose).
3. `width_bucket` 360° edge → `LEAST(yb,16)` + test.
4. Bot-only data today (`OMNIBOT*` GUIDs) — verify with a known bot GUID.
5. Must not regress the shared `player-heatmap` shape/tests.

## 7. Critical files

- `website/backend/routers/proximity_positions.py` — new handler;
  reuse GUID/scope sequence + weapon-extra from `get_proximity_player_heatmap`.
- `tests/unit/test_proximity_player_aim.py` — new (model on
  `test_proximity_player_heatmap.py`).
- `website/js/proximity.js` — `PLAYER_HEATMAP_MODES`, `renderPlayerAim`,
  rose/pitch canvas helpers, wire-in.
- `website/index.html` — `#view-proximity` Aim button + panel block.
- `website/frontend/src/{pages/Proximity.tsx, api/types.ts, api/client.ts,
  api/hooks.ts, pages/proximity-glossary.ts}` — React parallel.

---

**Status: APPROVED — Phase 1 in progress.** Phase 2 (enemy-relative,
Leetify-grade) is future scope, not built here.
