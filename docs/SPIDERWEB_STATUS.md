# Spider web — status for reviewers (2026-09-06)

The "spider web" is the owner's name for the whole project's end state: every
statistic connected to every other through **position × time × player state ×
event**, so that a positional score can say not only *what* a player did but
*where, when and under what conditions*. Individual stats are threads; the
value appears when they are joined. This file is the one place that says how
far the web is built, what has been measured, and what has *not* been
validated. The design lives in `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md`
(the spec; §4–§8 are the layers and the validation protocol).

## Layers and their state

| layer | spec | state | where |
|---|---|---|---|
| 0 capture | §2 | live. Lua tracker v6.14 on the game server writes 200 ms samples, combat, engagements, vehicle progress (`proximity/lua/proximity_tracker.lua`); parser `proximity/parser/parser.py`; tables `proximity_*`, `player_track`, `combat_engagement`, `vehicle_progress` | PR #916 (v6.14), earlier v6.x |
| 1 the web (reconstruction of a round at one moment) | §4 | **built and merged** (#792, 2026-08-21; fixes #793). `GET /api/replay/round/{id}/web?t=<ms>` in `website/backend/routers/replay_router.py`, logic in `website/backend/services/round_web_service.py` | SPA page `SpiderWebPage.tsx` (`/spider-web/round/:roundId`, phase 5 slice SW-1, #880) |
| 2 the clock | §5 | built inside layer 1's response: clock quality is a server verdict (`validated`, `internally_consistent_unvalidated`, `validation_failed`, …, `round_web_service.py` ~858) and the page shows it as a badge; **withheld** is a separate axis, not a sixth state | same endpoint/page |
| 3 information state (what a team *could* know) | §6 | **computed and drawn** (#991 the belief tables, 2026-09-08; SW-2 the scene, 2026-09-09): per holder, the beliefs the server grants, counts and distances as intervals, and under a team or player point of view the belief REGIONS as dashed discs at the radius the server grew, opacity = confidence, past the published horizon named in words | `website/backend/services/information_state.py`; `website/frontend/src/app/pages/SpiderWebPage.tsx`, `components/SpiderWebScene.tsx`, `lib/spiderWeb.ts` |
| 4 movement quality | §7 | **the protocol is code, no signal ships** (SW-4, 2026-09-09): `services/layer4_family.py` is §8.6 — within-round median split, chronological 70/30 split of whole `gaming_session_id` blocks, block bootstrap with a max-T simultaneous interval, verdict rule, frozen family manifest with sha256; `scripts/spiderweb_layer4_family.py collect|analyse` walks every eligible round at a 5 s cadence through layers 1–3 and the W6 tracer and runs the protocol. The family and the verdicts are in `docs/spiderweb/layer4_family_manifest.json` and the table below. §7.5 stands: weights are choices, not facts, and nothing here has earned one | `docs/spiderweb/layer4_family_manifest.json` |
| validation W6 (offline trace vs engine) | §8, §10 C4 | **done, 2026-08-21/22**: 26,695 paired segments on all 8 project maps, agreement **99.92 %**, 0 hard errors; two maps at exactly 100 %; cost 9–13 µs per trace | `scripts/build_w6_trace_fixtures.py`, `scripts/compare_w6_engine_vs_offline.py`, `tests/unit/test_w6_control_expectations.py`; report is local (`docs/research/W6_OFFLINE_VS_ENGINE_2026-08-22.md`, not in the repo) |

## What was measured (numbers a reviewer can hold us to)

- **Layer 1 cost**: median 2.12 ms per snapshot at 7.5 players (tracks loaded
  once, slicing in memory). Three runs gave 2.12 / 2.34 / 2.12 — the middle one
  was noise, not a regression; do not claim a move from two measurements.
- **Overlapping lives**: 4,757 overlapping life pairs across 87 rounds. The
  old replay path returned the *earliest* overlapping life; layer 1 resolves
  by the sample's own life (§4.3). Disagreement between the two rules: 1.83 %
  on 25 random rounds, 43.96 % on the eight worst. The death boundary is
  half-open: at `t == death_time_ms` the sample is a corpse.
- **No positions from the future**: layer 1 uses floor + `stale_ms` (§4.4),
  checked on 320 snapshots: 0 future states. The replay slider's
  nearest-neighbour lookup can return a future sample; layer 1 must not.
- **Derived speed tolerance was measured, not chosen**: |derived − stored| /
  stored has p50 0.069, p90 0.596, p99 2.434 on 932 samples, because the stored
  speed is instantaneous and the derived one is an interval average. A guessed
  0.5 rejected 13.7 % of ordinary movement; 2.5 (p99) rejects 4.6 %.
- **Offline BSP tracer vs recorded kills** (2026-08-20, before W6): 38,327
  hitscan kills on 8 maps agree 90.4 % (splash control 26.0 %); the residual
  falls with distance and mostly clears when re-traced to the head, so the
  honest tracer error bound is ~4–6 %. W6 later explained the residual: 99.51 %
  of the "blocked" calls are confirmed blocked by the engine (the bullet passed
  because of `MASK_SHOT`, antilag `G_HistoricalTrace`, or entities).
- **Engine trace contract** (read in `etlegacy-source` and confirmed live):
  `et.trap_Trace` with `passEntityNum = -2` is a **world-only** trace
  (`sv_world.c:749`); `-1` clips runtime entities whose collision volumes are
  created by game code (e.g. `team_WOLF_checkpoint`, no brush model) and
  **cannot be reproduced offline**. W6 therefore compares `-2` against our
  world tracer; `-1` is diagnostics only.

## Layer 4 — the §8 table (2026-09-09, manifest `72bdfc31…`)

901 rounds, 57 gaming-session blocks (39 discovery / 18 confirmation, confirmation from
2026-07-16), 5,622 (player, round) rows at a 5 s cadence, 2,000 block resamples, seed 20260909.
Effect = mean over rounds of (win rate of the upper median half − lower half) within the round.
Full table with intervals: `docs/spiderweb/layer4_family_manifest.json`
(`docs/research/SPIDERWEB_LAYER4_FAMILY_2026-09-09.md` locally, with the dataset).

| candidate | kind | discovery | confirmation [simultaneous 95] | verdict |
|---|---|---|---|---|
| `dpm` | positive control | +0.059 | +0.053 [+0.015, +0.091] | control passes — the harness sees a known within-round signal |
| `noise` | negative control | −0.020 | −0.003 [−0.044, +0.037] | fails, as it must |
| `moving_share` | candidate | +0.034 | +0.108 [+0.047, +0.167] | passes the arithmetic; **not shipped** — a within-round split cannot separate "moved more" from "was on the attacking side", which shares the outcome (§7.4.1); needs the attacking side per round |
| `isolation_share` | oracle diagnostic | +0.081 | +0.032 | fails: wrong direction (the isolated win MORE — attackers spread out) |
| `blind_moving_share` | candidate | +0.010 | −0.007 | fails: no direction; median 0.89 — on captured evidence almost all movement is "blind" (§6.2 lower bound) |
| `exposure_share` | oracle diagnostic | −0.043 | −0.038 [−0.096, +0.019] | fails: simultaneous interval includes zero |
| `push_into_wave_share` | oracle diagnostic | −0.049 | −0.116 [−0.214, −0.018] | passes the arithmetic; oracle clock, does not ship (§6.4, P6); coverage 4,131/5,622 rows (validated enemy clock only) |

Nothing from layer 4 reaches a page. The two findings worth a follow-up are named, not scored:
moving-into-an-imminent-enemy-wave reads as costly on the oracle clock (the recipient-clock
version, §6.3, is what could ship), and "moving more" needs the attacking side per round to
mean anything about a player.

## What is explicitly NOT validated or not done

- `capture_policy.mode = "unknown"` is the truth for historical rounds:
  `capabilities` is NULL in all 828 rows measured on 2026-08-21 and capture
  cadence is stored nowhere; the page shows this as a three-state snapshot
  integrity, not as an error.
- Line of sight (SW-3, 2026-09-09) is published in the WORLD view only, as
  an oracle diagnostic: `edges[].line_of_sight` (eye-to-body availability
  both ways, W6-validated tracer, static geometry) and a `line_of_sight`
  block with the scope, the validation and per-player exposure (living
  enemies with a clear ray to them). A team or player view gets
  `available:false` with the reason. No metric eats it — §11 holds: a clear
  ray is necessary, not sufficient, for having seen someone, and it is never
  a belief source. Cost measured on dev: index scan 4.9 s once per process,
  BSP 0.3 s per map, 45–110 ms per snapshot off the event loop
  (`services/line_of_sight.py`). Maps without a BSP in the indexed etmain
  tree (`etl_supply`) answer "no geometry", not zero exposure.
- Layer 1 must not rank players (§4.6); the ceiling for all context is +2.51
  rating points.
- Objective pressure keeps the radius-500 sphere: replacing it with objective
  volumes was measured (containment 5.9 %, free path 48.1 %) and a random-
  direction control killed both instruments — on 3 of 4 maps the path to the
  objective is *clearer* than random. Only `etl_ice` is worse than random.
- SW-2 (2026-09-09) carried the legacy canvas whole into the SPA as SVG:
  the axonometric camera (drag turns, shift-drag pans, wheel zooms, plan
  view), the screen-space fit, floors by height band, the p90 error ring,
  labels that drop rather than nudge, belief regions under a team/player
  view, a 512-unit scale bar, per-player points of view and the moment in
  the URL. The legacy module's own tests travelled with it
  (`lib/spiderWeb.test.ts`, 48). Line of sight followed in SW-3 (below).
- Layer 4 has no code beyond the exposure diagnostic above; its harness is SW-4 (PLAN). The owner's positional score is a goal, not a
  deliverable: any new metric must say which threads it joins
  (`proximity_*` samples, `storytelling_kill_impact`, W6 LOS, spawn timing,
  reaction metrics) and follow the measurement discipline that already
  retired six proposed metrics (no artificial weighting; descriptive, not
  judging; control group before headline number).

## Review focus for this area

1. `round_web_service.py`: life resolution (§4.3) and staleness (§4.4) — the
   two rules the replay slider gets wrong; the `stale_ms` of a dead player
   must be measured from `t`, not from death time (review finding on #792).
2. `derive_velocity` and `build_edges`: both had `z = 0` assumptions once;
   the class was removed in both places — look for a third.
3. The empty-round shortcut must return every key (a KeyError arrived
   exactly on the thinnest data once).
4. Lua v6.14 `recordVehicleDamage`: the hook is at the top of `G_Damage`
   (fires for every entity incl. `script_mover`, before `targ->health -=
   take`), so vehicle health seen in the hook is *pre-hit*.
5. Validation scripts must not repeat the subject's self-assessment: the
   W6 comparison exits 1 on mismatch and compares independently.
