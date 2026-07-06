# All-Seeing Eye — Situational Competitive Skill (design, 2026-07-06)

> **Owner vision:** proximity was always meant to measure TRUE competitive FPS skill —
> K/D tells us little. The all-seeing eye watches map movement AND how players REACT
> to it: action → reaction → points. This doc turns that into detectors and formulas
> built on what our Lua actually captures.
>
> **Golden test:** SuperBoyy, last alive on te_escape2 final room; 3 allies arrive
> CARRYING THE DOCS (winning the map); he kills all 3, returns the docs, resets the
> timeline. Deserved credit: multikill + defensive position + objective defense +
> objective return + 1v3 clutch with the map at stake. The system must find moments
> like this and rank them at the top.

## 0. Hard constraints (verified 2026-07-06)

1. **Situational context exists only from ~2026-04** (Oksii Lua rollout):
   `axis_alive/allies_alive/killer_health` are 0/NULL before (Mar 45%, earlier 0%).
   → the system is FORWARD-LOOKING; the original March SuperBoyy moment cannot be
   reconstructed. Closest verified real golden: **qmr, 2026-04-07 R2 escape2 —
   3 kills in 13.25s as last man alive**.
2. `proximity_combat_position` streams ONLY kill events — "3 enemies entered the
   room" requires `player_track.path` replay (200ms) + geo-test against the Lua's
   hardcoded objective coords (escape2 documents @ -676,672,108, r=500).
3. Engine limits (koš D): no fireteam API, partial comms; crosshair-target trace
   unverified. v7 `spawn_select/skill_snapshot/comm_events` dormant. `aim_lock` IS
   live (since 06-22) but is NOT linked to kill events yet → reflex-TTK is a gap.
4. Hardware latency ≈50ms swings → reflex metrics are RELATIVE within our group,
   never absolute; and decision quality > raw speed below elite (research: pros
   140–180ms; consistency beats peak).
5. **200ms sampling quantization (owner call-out):** `player_track.path` and every
   metric derived from it (dodge_reaction_ms via ≥45° direction change,
   time_to_first_move_ms, any path-replay area-entry) tick at the Lua's 200ms
   `et_RunFrame` sampler → ±200ms resolution. Kill/damage/spawn events
   (et_Obituary/et_Damage/et_ClientSpawn) are event-driven and exact.
   Consequences: (a) never rank reflexes on differences <200ms — use buckets or
   medians over many samples; (b) return_fire_ms (damage-event based) is finer
   than dodge_reaction_ms (path based) — don't mix them in one number;
   (c) time-joins between event tables and path data need ≥±200ms tolerance
   (our kill_impact↔combat_position join uses ±300ms for this reason).

## 1. What already exists (extend, don't rebuild)

| Building block | Where | State |
|---|---|---|
| **1vN clutch detector** (fight-scoped: death leaves 1 vs ≥2, friendly wave ≥5s away; won = survive/trade-up) | `website/backend/routers/proximity_competitive.py:535 _detect_clutches` + `GET /api/proximity/competitive/clutch` | HTTP-only, never persisted/aggregated |
| **Per-player situational card** (clutch+man-advantage+stagger+side-splits) | `website/backend/routers/proximity_competitive.py:877` (`GET /api/proximity/competitive/player-card`) | nascent "Comp Skill card", HTTP-only |
| **KIS v2** — per-kill contextual value (carrier 3.0 / chain 5.0, push, crossfire, spawn, outcome, class, health <30→1.3, alive 1v3+→2.0, 7-tier reinf) | `storytelling/kis.py:148`, constants `base.py:47-95` | shipped, persisted per kill with all sub-multipliers; `distance_multiplier` + `is_objective_area` slots STUBBED |
| **Doc return by player + timestamp** | `proximity_carrier_return` (419 rows; e.g. immoo 325ms after drop) | captured, unscored |
| **Combat reflex under fire** — `return_fire_ms`, `dodge_reaction_ms`, `support_reaction_ms`, `num_attackers`, outcome | `proximity_reaction_metric` (87k rows) | captured, scored NOWHERE |
| **Spawn reflex** — `time_to_first_move_ms` (real 125–150ms values) | `player_track` | captured, unscored |
| **Objective stake clock** — `time_to_beat_seconds`, `round_stopwatch_state` | `bot/core/round_contract.py:187` | derived, NEVER joined to kills — biggest gap |
| Kill permanence / denial | `kill_outcome.effective_denied_ms`, gib/revive | in KIS + ET Rating |
| ET Rating v2 (15 metrics, ~32% situational incl. crude clutch_factor) | `skill_rating_service.py:32` | global %ile rollup |
| Specs to lift: RoundState vector, xOV, Wave-Cycle Ledger, Player Fingerprint, Aim Truth | Good Night plan :865/:1080/:1275/:318/:442 | designed, unbuilt |

**Architecture decision (from inventory):** per-EVENT scoring extends **KIS**;
per-PLAYER aggregate extends **competitive player-card** and gets persisted
(mirror `player_skill_ratings`); ET Rating v2 gains ONE new weighted metric
(situational aggregate) instead of a parallel rating. No new EIS (KIS is its
shipped superset); don't touch frag_potential (volume-only).

## 2. Situation taxonomy → detectors

Each situation = (trigger, actors, reaction window, credit). All v0 detectors are
buildable TODAY for rounds ≥ 2026-04 unless marked GAP.

### S1 · Clutch 1vN (± objective stake) — the golden case
- **Detect:** promote `_detect_clutches` to canonical; extend with KIS: chain =
  killer's kills while own side alive==1 (combat_position join), window ≤20s.
- **Value:** `Σ KIS(total_impact of chain) × N_mult(1v2=1.3, 1v3=1.7, 1v4+=2.2) ×
  stake_mult × outcome_mult(won=1.5 / traded=1.0 / lost=0.6)`.
- **Stake_mult** (the missing objective awareness): 1.0 base; ×1.5 if any chain
  kill `is_carrier_kill` or victim within objective radius; ×(1 + pressure) where
  `pressure = clamp(1 − time_to_beat_remaining/120s, 0, 1)` on R2 chase — "they
  were 15s from winning" ≈ ×1.9.
- **Doc-return bonus:** `carrier_return` by the clutcher (or enabled by his
  carrier-kill) within 30s of chain end → +25% of chain value.

### S2 · Objective-stake awareness (docs taken → who reacts)
- **Detect:** `carrier_event` pickup → for each defender: time until (a) engagement
  with carrier (`carrier_kill`/combat_position vs carrier_guid) or (b) movement
  toward carrier (path-replay, phase 2).
- **Credit v0:** carrier_kill time-from-pickup percentile; return_delay_ms
  (carrier_return) as team recovery speed. Path-replay reaction = phase 2 (heavier).

### S3 · Reflex (ET:L-specific, relative percentiles)
- **combat reflex:** median `return_fire_ms` (aim under fire) + `dodge_reaction_ms`
  (evasion) from reaction_metric, split by `num_attackers` (1v1 vs focused).
- **spawn reflex:** median `time_to_first_move_ms` (player_track).
- **GAP (flag to owner):** true "first-sight→kill" TTK needs aim_lock↔kill linkage
  (Lua or post-hoc time-join ±window) — v1 candidate, not v0.

### S4 · Decision speed/quality
- **Trade decision:** existing kill_outcome traded window + `support_reaction_ms`
  (how fast teammates punish) — score the RESPONDER.
- **Engage-vs-reposition:** outcome-weighted `return_fire vs dodge first` choice by
  situation (num_attackers≥2 → dodge-first correlates with `escaped`?) — backtest
  will tell if the signal discriminates before we score it.

### S5 · Positioning correctness (defense)
- **v0 proxy:** share of defender's kills inside objective radius while defending
  (is_objective_area + defender side), weighted by stake clock.
- **Phase 2:** RoundState `frontline_distance_to_objective` per Good Night spec.

### S6 · Skill levels (pro / casual / comp-overthinker)
Not a metric — an OUTPUT view: percentile bands per component (clutch, reflex,
decision, positioning) form the **Player Comp Profile**; archetypes already
classify style, this classifies LEVEL per axis. Backtest evidence decides bands.

## 3. KIS v3 proposal (per-event core upgrade)
In `kis.py` extension slots (implementation AFTER owner reviews backtests):
1. **stake_multiplier** — join time_to_beat pressure (S1 formula) into per-kill KIS.
2. **clutch_chain_multiplier** — kill inside a detected S1 chain gets ×1.2–1.5.
3. **Non-kill KIS credits** (NEW event class, same scale): doc return (base 2.5 ×
   stake), dynamite defuse under fire (contested run_types), construction complete
   contested. Today KIS only sees kills — engineers/returners are invisible.
4. **reaction quality factor** — kill on a target who was mid-dodge / kill while
   returning fire under focus (reaction_metric join) — small ±10%.
Because KIS feeds Story, moments, ET-Rating impact and Form "impact", every surface
upgrades at once.

## 4. Situational Skill Rating v0 (per-player aggregate)
`situational = .35 clutch_value_rate + .20 reflex_pct + .20 decision_pct +
 .15 stake_participation + .10 permanence` — all group-relative percentiles,
min-events thresholds, persisted (player_situational_ratings, mirror of
player_skill_ratings), surfaced as "Comp Skill" leaderboard tab (KROGT pattern:
`proximity_scoring.py` category + `proximity.js` LB_TABS) + player-card fusion.
ET Rating v2 later adds it as one weighted metric.

## 5. Delivery order (backtest-first, owner review gates each)
1. **backtest_clutch_detector.py** — S1 on full history (≥2026-04): top-20 clutches
   with descriptions; golden check vs qmr 04-07; SuperBoyy expected high on recent data.
2. **backtest_reflex_decision.py** — S3+S4 percentiles per player; does it
   discriminate and stay stable across sessions?
3. Owner tone/sanity review of both ladders.
4. KIS v3 + persisted aggregate + Comp Skill tab (separate PRs).
5. Phase 2 (path-replay reactions, frontline distance, aim_lock↔kill link, v7 flips).

## 6. Open questions for owner
1. Clutch N_mult / stake weights — feel right vs your memory of big moments?
2. Non-kill KIS credits: agree engineers/doc-returners should earn KIS-scale value?
3. Reflex boards: public or profile-private? (hardware caveat text included either way)
4. aim_lock↔kill linkage: worth a Lua tweak, or post-hoc join first?
