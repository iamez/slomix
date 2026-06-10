# Proximity End-to-End Verification — 2026-06-10

**Scope:** Full pipeline trace (Lua dump → parser → PostgreSQL → API → legacy JS) on the most
recent live match: **etl_frostbite 2026-06-09**, R1 (`round_id=10707`, file
`local_proximity/2026-06-09-230750-etl_frostbite-round-1_engagements.txt`) and R2
(`round_id=10708`, file `...231225...round-2...`). Lua on server: v6.02 with `shot_fired=true`.

**Verdict: pipeline is healthy.** 100 % file↔DB fidelity, shared time base, sane endpoint
output. One real (low-severity) Lua bug found: `killer_reinf` ignores CS_REINFSEEDS offset
(see Finding F1).

---

## 1. File ↔ DB fidelity: 100 % match (20 sections × 2 rounds)

Data lines counted per `# SECTION` header in the raw dump vs `COUNT(*)` per `round_id`:

| Section | File R1 | DB R1 | File R2 | DB R2 | Table |
|---|---|---|---|---|---|
| ENGAGEMENTS | 90 | 90 | 69 | 69 | `combat_engagement` |
| PLAYER_TRACKS | 40 | 40 | 34 | 34 | `player_track` |
| REACTION_METRICS | 90 | 90 | 69 | 69 | `proximity_reaction_metric` |
| SPAWN_TIMING | 37 | 37 | 28 | 28 | `proximity_spawn_timing` |
| TEAM_COHESION | 862 | 862 | 815 | 815 | `proximity_team_cohesion` |
| CROSSFIRE_OPPORTUNITIES | 12 | 12 | 5 | 5 | `proximity_crossfire_opportunity` |
| FOCUS_FIRE | 20 | 20 | 12 | 12 | `proximity_focus_fire` |
| TEAM_PUSHES | 92 | 92 | 81 | 81 | `proximity_team_push` |
| TRADE_KILLS | 3 | 3 | 6 | 6 | `proximity_lua_trade_kill` |
| REVIVES | 13 | 13 | 7 | 7 | `proximity_revive` |
| WEAPON_ACCURACY | 42 | 42 | 34 | 34 | `proximity_weapon_accuracy` |
| KILL_OUTCOME | 37 | 37 | 28 | 28 | `proximity_kill_outcome` |
| HIT_REGIONS | 308 | 308 | 237 | 237 | `proximity_hit_region` |
| COMBAT_POSITIONS | 37 | 37 | 28 | 28 | `proximity_combat_position` |
| SHOT_FIRED | 1415 | 1415 | 955 | 955 | `proximity_shot_fired` |
| CARRIER_EVENTS | 2 | 2 | 6 | 6 | `proximity_carrier_event` |
| CARRIER_KILLS | — | 0 | 1 | 1 | `proximity_carrier_kill` |
| CARRIER_RETURNS | — | 0 | 1 | 1 | `proximity_carrier_return` |
| CONSTRUCTION_EVENTS | 5 | 5 | 3 | 3 | `proximity_construction_event` |
| OBJECTIVE_RUNS | 3 | 3 | 1 | 1 | `proximity_objective_run` |

KILL_HEATMAP / MOVEMENT_HEATMAP are aggregated into `map_kill_heatmap` /
`map_movement_heatmap` via `ON CONFLICT ... + EXCLUDED` (parser.py:1961+) — per-round counts
do not apply by design.

## 2. Time-base alignment: CONFIRMED (hard gate for Player Journey → OPEN)

All time columns for round 10707 share the same `gameTime()` ms-since-round-start origin
(round wall length = `round_end_unix − round_start_unix` = 256 s):

| Source | min (ms) | max (ms) |
|---|---|---|
| `player_track.path[].time` | 500 | 257 125 |
| `player_track.spawn_time_ms/death_time_ms` | 500 | 257 125 |
| `combat_engagement.start/end_time_ms` | 10 750 | 251 825 |
| `proximity_kill_outcome.kill_time` | 12 975 | 249 775 |
| `proximity_spawn_timing.kill_time` | 12 975 | 249 775 |
| `proximity_team_cohesion.sample_time` | 1 000 | 257 000 |
| `proximity_shot_fired.event_time` | 1 900 | 250 075 |

`kill_outcome` and `spawn_timing` ranges are identical (same kill set) — cross-table
correlation on a shared timeline is safe.

## 3. Spawn timing semantics (written down for the Journey view)

From `proximity_tracker.lua:1480-1546` (`calculateSpawnTimingScore`, `recordSpawnTiming`):

- `enemy_spawn_interval` — the **victim's** team spawn interval (ms): axis 30 000 / allies 25 000 on this round.
- `time_to_next_spawn` — ms until the victim's team's **next** spawn wave at the kill moment,
  i.e. how long the victim waits in limbo (= the denial). Uses the ET:Legacy
  `CG_CalculateReinfTime` formula including the per-team random 0-15 s `CS_REINFSEEDS` offset.
- `spawn_timing_score` = `time_to_next / interval`. **1.0 = killed right after the enemy wave
  (max wait/denial), 0.0 = killed right before it (instant respawn).** Higher = better timing.
- `victim_reinf` (s) — same as `time_to_next_spawn` in seconds.
- `killer_reinf` (s) — the killer's own team's time-to-next-wave (Oksii adoption field). **Buggy — see F1.**

**Numeric validation (round 10707):** solving the formula backwards per kill gives a constant
implied reinf offset per team across all 37 kills — ALLIES 14 000 ms, AXIS 6 000 ms. Constancy
proves the victim-side formula + offset handling are correct.

## 4. Findings

### F1 (bug, low severity): `killer_reinf` ignores the CS_REINFSEEDS offset

`proximity_tracker.lua:1528` reads `tracker.spawn.axis_offset` / `tracker.spawn.allies_offset`
— **fields that are never assigned** (the real fields are `axis_reinf_offset` /
`allies_reinf_offset`, set at lines 503-504/1472). `or 0` masks the nil → `killer_reinf` is
always computed with offset 0.

Numeric proof (round 10707): implied killer offset clusters at 0 ± 50 ms (rounding noise from
0.1 s storage) for **all** kills, while the true offsets that the victim side correctly uses
are 14 000 ms (ALLIES) and 6 000 ms (AXIS). `killer_reinf` is therefore wrong by the per-team
offset (mod interval) — up to 15 s.

**Blast radius: none today.** No Python consumer reads `killer_reinf` (KIS's
`_graduated_reinf_mult` uses `victim_reinf`, which is correct). Fix is a one-line field-name
correction in the repo Lua; live deploy is owner-gated as usual (full map load, never
`lua_restart`; check homepath overrides first).

### F2 (non-issue): lurker NULL-path silent skip

0 of 41 404 `player_track` rows have NULL/empty `path` — coverage is 100 %, the silent-skip
path in `advanced_metrics.py` never triggers in practice. A `coverage` meta field is still
worth adding for future-proofing (Phase 1a).

### F3 (display note): `gravity_score` unit is unintuitive

`/storytelling/gravity` returns attention-ms per minute alive (theoretical max 60 000;
observed ~37 263 for the top player on 2026-06-09). Correct math, but the Invisible Value
panel should display it normalized (e.g. % of alive time under enemy attention).

### F5 (bug, medium severity): space-created/enabler names depend on lazily-populated KIS table

`compute_space_created` and `compute_enabler` (`advanced_metrics.py:281-287/427-433`) resolve
player names **only** from `storytelling_kill_impact` — a cache table that is populated lazily,
the first time a KIS endpoint runs for that session. Until that happens, both endpoints return
`name: "#EDBB5DA9"` placeholders for every player.

Reproduced live on 2026-06-10: before any KIS call for session 2026-06-09 both endpoints
returned `#guid` names; the `player-narratives` call populated `storytelling_kill_impact`
(rows stamped 04:50:51 UTC) and the very next `space-created` call resolved every name
(SuperBoyy, wiseBoy, …). `gravity` and `lurker-profile` are unaffected (names come from
`combat_engagement` / `player_track`).

**Fix (Phase 1b of this sweep):** add a fallback name source (`combat_engagement`, the same
source `compute_gravity` uses) so names resolve even when KIS has not been computed yet.
This matters for the new Invisible Value panel, which calls these endpoints directly.

### F4 (capacity, informational): table growth is sustainable

| Table | Size | Rows | Bytes/row |
|---|---|---|---|
| `proximity_shot_fired` | 68 MB | 209 552 | ~340 |
| `player_track` | 159 MB | 41 404 | ~4 000 |
| `proximity_team_cohesion` | 196 MB | 607 370 | ~340 |

shot_fired adds ~2 100 rows/round (sample_rate=1). At the observed pace (~500 tracked
rounds/3 months → ~2 000 rounds/yr) that is ~4 M rows ≈ 1.4 GB/yr; cohesion grows similarly.
**Recommendation: keep as-is**; revisit (throttle `shot_fired_sample_rate` or partition) if
`proximity_shot_fired` passes ~2 M rows. No action needed now.

## 5. Stale audit claims — disposition

| Claim (older audits) | Verdict |
|---|---|
| `/proximity/events` ignores `limit` | **STALE** — `safe_limit` clamps it (`proximity_events.py:33`) |
| Heatmap blank on calibrated maps (A1) | **STALE/CLOSED** — `combat-positions/heatmap`, `player-heatmap` (all modes) and `player-aim` all return populated `hotzones` with grid coords for etl_frostbite R1 |
| No rate limiting on proximity endpoints | **PARTIALLY STALE** — `proximity_dashboard` 10/min, `proximity_scoring` 10-15/min, storytelling 5-10/min; cheap read endpoints remain unthrottled (accepted) |

## 6. API ↔ JS spot-checks (round-scoped, 2026-06-09 etl_frostbite R1)

- `/proximity/spawn-timing` → `total_events: 37` (= DB), leaders carry `avg_score`/`kills`/
  `avg_denial_ms` — exactly the fields `renderSpawnTimingLeaders` (proximity.js:1979) reads.
- `/proximity/cohesion` → samples 417 + 445 = 862 (= DB), dispersion ~520 world units (plausible).
- `/storytelling/gravity` + `/storytelling/lurker-profile` → live data for the session
  (lurker top: 46.6 % solo) — ready to be surfaced by the Invisible Value panel (Phase 1b).
- `/proximity/player-aim` → 161 shots for the scoped player/round, `sampled:false`.

---

*Read-only sweep; no code, schema, or service changes. Produced as Phase 0 of the
proximity-vision plan (verification → fixes + Invisible Value panel → Player Journey → Lua v7
research → esports benchmark).*
