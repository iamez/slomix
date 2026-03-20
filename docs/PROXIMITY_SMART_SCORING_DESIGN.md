# Proximity Smart Scoring System — Design Document

**Created**: 2026-03-20
**Status**: Design — ready for implementation
**Research basis**: CS2 HLTV 3.0, Valorant ACS, OW2 On-Fire/PBSR, R6 Siege KOST, Dota 2 STRATZ IMP, PandaSkill, ESEA RWS

---

## The Vision

Transform raw ET:Legacy stats into **contextual impact scores**. A kill is not just a kill — it has spawn timing, team state, target class, revive denial, and objective context. Our proximity system already collects the data; this design defines how to score it.

---

## Part 1: KROGT — ET:Legacy Consistency Metric

Inspired by **KAST** (CS2) and **KOST** (R6 Siege). Measures per-round consistency.

**KROGT** = % of rounds where player did at least one of:
- **K**ill — got a kill
- **R**evive — revived a teammate (Medic-specific, equivalent to OW2 Mercy rez)
- **O**bjective — dynamite plant/defuse, construct/destroy, flag capture
- **G**ib denial — gibbed an enemy body (prevented revive)
- **T**raded — died but teammate avenged within 5 seconds

**Benchmarks** (from CS2 KAST): 70%+ = consistently contributing, <50% = liability.

**Data sources**: All exist in current DB except gib denial (needs Lua v5.1).
- K: `proximity_spawn_timing` (has killer_guid per round)
- R: `proximity_revive` (has medic_guid per round) — needs Lua v5.1 REVIVE_CONTEXT for quality
- O: `player_comprehensive_stats` (constructions, destructions, objectives)
- G: Needs Lua v5.1 GIB_CONTEXT
- T: `proximity_lua_trade_kill` (has trader_guid per round)

---

## Part 2: Elimination Impact Score (EIS)

Inspired by **HLTV 3.0 Round Swing** + **Valorant ACS declining kill value**.

Each kill gets a contextual impact score (0-100):

```
kill_impact = (
    spawn_timing_weight     * 0.30    # 0-1: how long enemy is out (Round Swing analog)
  + team_alive_weight       * 0.20    # Valorant ACS: kill at 6v6=1.0, kill at 6v1=0.47
  + target_class_weight     * 0.15    # Medic kill during push > Soldier kill in stalemate
  + gib_denial_bonus        * 0.15    # Did you gib (prevent revive)? OW2 Mercy rez denial
  + isolation_penalty       * -0.10   # Isolated target who'd tapout anyway = less value
  + objective_proximity     * 0.10    # Kill near objective during push = high value
)
```

### Component Details

**spawn_timing_weight** (0-1): Already computed by Lua (`spawn_timing_score`).
Fix deployed today: correct cvars (`g_redlimbotime`/`g_bluelimbotime`) + reinforcement offset.

**team_alive_weight** (0.47-1.0): Valorant's 150/130/110/90/70 adapted:
```
weight = 0.47 + 0.53 * (enemies_alive - 1) / (max_enemies - 1)
```
Data: count alive enemies at kill time from `proximity_team_cohesion` samples (500ms resolution).

**target_class_weight** (0.8-1.5):
- Medic = 1.5 (highest — removing healer is devastating)
- Engineer = 1.3 (objective player during push)
- FieldOps = 1.1 (supplies/artillery)
- Soldier = 1.0 (baseline)
- CovertOps = 0.8-1.2 (depends on context)

Data: `proximity_reaction_metric.target_class` exists. For Lua v5.1: add `target_class` to spawn_timing.

**gib_denial_bonus** (0 or 1.0):
- 1.0 if kill was gibbed AND medic was within 500u (denied revive)
- 0.5 if kill was gibbed but no medic nearby
- 0.0 if not gibbed
Data: Needs Lua v5.1 GIB_CONTEXT section.

**isolation_penalty** (-1.0 to 0):
- -1.0 if target had no teammates within 800u (would tapout anyway)
- 0.0 if target was in tight formation (dispersion < 400)
Data: Cross-join with `proximity_team_cohesion.dispersion` at kill time.

**objective_proximity** (0-1.0):
- 1.0 if kill within 500u of active objective during push
- 0.0 if far from any objective
Data: `proximity_objective_focus` has per-player distances.

### Per-Player Session EIS
```
session_EIS = AVG(per_kill_impact) * min(kill_count / 5, 1.0)
```
Dampened for low sample sizes (< 5 kills).

---

## Part 3: Medic Efficiency Rating (MER)

Inspired by **OW2 Mercy rez quality** analysis + **Superboyy's useless revive** concept.

```
MER = (
    revive_utilization_avg      * 0.40   # % of spawn time saved per revive
  + clutch_revive_rate          * 0.25   # under_fire + enemy < 500u revives
  + (1 - useless_revive_rate)  * 0.20   # 1 - (revives with < 3s to spawn / total)
  + revive_survival_rate        * 0.15   # % of revived players who survived > 5s
)
```

### Component Details

**revive_utilization** (0-1): How much spawn time each revive saves.
```
utilization = (spawn_interval - spawn_timer_remaining) / spawn_interval
```
Revive at 25s remaining = 83% utilization. Revive at 2s remaining = 7% (useless).
Data: Needs Lua v5.1 REVIVE_CONTEXT with `spawn_timer_remaining`.

**clutch_revive_rate**: From existing `proximity_revive.under_fire` + `distance_to_enemy`.

**useless_revive_rate**: Revives where `spawn_timer_remaining < 3000ms`.
Data: Needs Lua v5.1 REVIVE_CONTEXT.

**revive_survival_rate**: Did the revived player survive > 5 seconds?
Data: Needs Lua v5.1 KILL_OUTCOME tracking (revive → re-death timing).

---

## Part 4: Kill Permanence Rate (KPR)

Inspired by **ESEA RWS** (only permanent impact counts) + **HLTV 3.0 trade denial**.

```
KPR = (gibs_confirmed + kills_not_revived) / total_kills
```

- `gibs_confirmed`: Enemy was gibbed (body destroyed, no revive possible)
- `kills_not_revived`: Enemy died and was NOT revived (tapped out or spawn wave)
- `total_kills`: All kills

**Benchmarks**: 0.7+ = most kills stick. < 0.3 = enemy medic is undoing your work.

Data: Needs Lua v5.1 KILL_OUTCOME section (kill → outcome tracking).

---

## Part 5: Team Denial Score (TDS)

Inspired by **ice hockey man-advantage time** + **OW2 stagger strategy**.

```
TDS = effective_denied_time / round_duration * 100
```

Where `effective_denied_time` accounts for revives:
```
per_kill_denial = MIN(time_to_revive, time_to_next_spawn)
# NOT the engine's broken denied_playtime which ignores revives
```

**Goal**: "What % of the round did the enemy team have fewer players?"

Data: Needs Lua v5.1 KILL_OUTCOME for `effective_denied_time` per kill.

---

## Part 6: Session Composite Score (updated formula)

Replaces current flat scoring with context-weighted version.

### Tier 1: Available Today (existing data)

| Category | Weight | Formula | Status |
|----------|--------|---------|--------|
| Kill Timing | 25% | `AVG(spawn_timing_score) * 100 * dampener` | Needs Lua fix deployed |
| Crossfire | 15% | `min(executed_count / 5, 1) * 100` | Working |
| Focus Fire | 10% | `AVG(focus_score) * 100 * dampener` | Working (pipeline just fixed) |
| Trades (weighted) | 15% | `quantity * 0.4 + quality * 0.6` | Implemented today |
| Survivability | 15% | `escape_rate * 100` | Working |
| Movement | 10% | `sprint * 0.6 + speed * 0.4` | Working |
| Reactions | 10% | `max(0, 100 - avg_rf_ms / 30)` | Working |

### Tier 2: After Lua v5.1 (new data sections)

| Category | Weight | Replaces | New data needed |
|----------|--------|----------|----------------|
| EIS (Elimination Impact) | 30% | Kill Timing + partial Survivability | GIB_CONTEXT, team_alive count |
| KROGT (Consistency) | 20% | — (new) | GIB_CONTEXT, REVIVE_CONTEXT |
| MER (Medic Efficiency) | 15% | — (class-specific) | REVIVE_CONTEXT |
| KPR (Kill Permanence) | 10% | — (new) | KILL_OUTCOME |
| Crossfire + Focus | 10% | Same | No change |
| Movement + Reactions | 10% | Same | No change |
| TDS (Team Denial) | 5% | — (team metric) | KILL_OUTCOME |

---

## Part 7: Lua v5.1 — Required New Sections

### Section A: KILL_OUTCOME (highest priority)

Tracks what happens AFTER each kill: revived, gibbed, or tapped out.

**State machine** (runs in `et_RunFrame`):
```
ALIVE → et_Obituary → DEAD{kill_time, killer_guid, MOD, pos}
  → et_ClientSpawn(revived=1) → outcome="revived", delta_ms
  → PMF_LIMBO + health ≤ -175 → outcome="gibbed", gibber info
  → PMF_LIMBO + health > -175 → outcome="tapped_out", delta_ms
```

**Detection methods** (confirmed from ET:Legacy source):
- `et_Obituary`: fires for initial kill only
- `et_Damage(PM_DEAD target)`: fires for body damage (gib attempts)
- `et_ClientSpawn(revived=1)`: fires for medic revive
- `et_RunFrame`: poll `PMF_LIMBO (16384)` flag for limbo transition
- `health ≤ -175 (GIB_HEALTH)`: distinguishes gib from tapout

**Output format** (14 fields):
```
# KILL_OUTCOME
# kill_time;victim_guid;victim_name;killer_guid;killer_name;kill_mod;
# outcome;outcome_time;delta_ms;effective_denied_ms;
# gibber_guid;gibber_name;reviver_guid;reviver_name
# outcome: gibbed|revived|tapped_out|expired
```

**Key insight from source**: Bullets/knives CANNOT gib corpses (damage clamped to GIB_HEALTH+1). Only explosives (grenades, panzer, dynamite, mortar, airstrike) can gib. This means gibbing is an INTENTIONAL action, not accidental.

### Section B: GIB_CONTEXT (medium priority)

Enriches gib events with tactical context. Subset of KILL_OUTCOME data + spatial context.

**Output format** (12 fields):
```
# GIB_CONTEXT
# gib_time;gibber_guid;gibber_name;victim_guid;victim_name;gib_mod;
# spawn_timing_score;nearest_medic_dist;team_dispersion;
# was_during_push;victim_class;body_damage_total
```

**Can derive from KILL_OUTCOME + existing data** (cross-join with team_cohesion, spawn_timing at gib time).

### Section C: REVIVE_CONTEXT (medium priority)

Enriches revive events with spawn timer context for MER calculation.

**Output format** (10 fields):
```
# REVIVE_CONTEXT
# revive_time;medic_guid;medic_name;revived_guid;revived_name;
# time_since_death;spawn_timer_remaining;revive_utilization_pct;
# distance_to_enemy;under_fire
```

**`spawn_timer_remaining`** = uses same spawn wave formula as spawn_timing:
```lua
local interval = victim_team == 1 and tracker.spawn.axis_interval or tracker.spawn.allies_interval
local reinf_offset = victim_team == 1 and tracker.spawn.axis_reinf_offset or tracker.spawn.allies_reinf_offset
local cycle_pos = (reinf_offset + gameTime()) % interval
local remaining = interval - cycle_pos
```

**`revive_utilization_pct`** = `(interval - remaining) / interval * 100`

---

## Part 8: Implementation Roadmap

### Phase 1: Deploy Current Fixes (immediate)
- [x] Spawn timing cvar fix (`g_redlimbotime`/`g_bluelimbotime`)
- [x] Spawn-timing-weighted trade scoring
- [x] Session score composite (7 categories)
- [ ] Deploy Lua v5.0.1 to game server (cvar fix)
- [ ] Verify spawn_timing_score > 0 after first game

### Phase 2: Lua v5.1 — KILL_OUTCOME (1-2 sessions)
- [ ] State machine: dead_players tracking
- [ ] et_Damage body damage logging
- [ ] PMF_LIMBO polling in et_RunFrame
- [ ] KILL_OUTCOME section output
- [ ] Parser: parse + import KILL_OUTCOME
- [ ] DB migration: `proximity_kill_outcome` table
- [ ] KPR + TDS calculations
- [ ] Update session score with KPR

### Phase 3: Lua v5.1 — REVIVE_CONTEXT (1 session)
- [ ] spawn_timer_remaining calculation at revive time
- [ ] REVIVE_CONTEXT section output
- [ ] Parser: parse + import
- [ ] DB migration: extend `proximity_revive` or new table
- [ ] MER calculation
- [ ] Useless revive detection

### Phase 4: Lua v5.1 — GIB_CONTEXT (1 session)
- [ ] Enrich KILL_OUTCOME gibs with medic proximity + team cohesion
- [ ] GIB_CONTEXT section output
- [ ] Parser: parse + import
- [ ] EIS formula with gib_denial_bonus
- [ ] KROGT consistency metric

### Phase 5: Tier 2 Composite (1-2 sessions)
- [ ] Replace Tier 1 session scoring with EIS + KROGT + MER + KPR
- [ ] Per-class percentile normalization (PandaSkill approach)
- [ ] Discord command: `!impact` or `!rating`
- [ ] Website: Smart Score dashboard
- [ ] Historical tracking: `player_proximity_rating_history` table

---

## Appendix: Key Constants

### ET:Legacy (from source code audit)
| Constant | Value | Source |
|----------|-------|--------|
| GIB_HEALTH | -175 | bg_public.h |
| FORCE_LIMBO_HEALTH | -113 | bg_public.h |
| BODY_TIME | 10000 ms | g_local.h |
| PM_DEAD | 3 | bg_public.h |
| PMF_LIMBO | 16384 (0x4000) | bg_public.h |
| PMF_SPRINT | 16384 | bg_public.h (same bit, different context) |

### Industry Standards (from research)
| Metric | Value | Source |
|--------|-------|--------|
| Trade kill window | 5 seconds | HLTV KAST |
| Kill value by enemies alive | 150/130/110/90/70 | Valorant ACS |
| Multi-kill squared weights | 1/4/9/16/25 | HLTV 1.0 |
| On-Fire decay | 5 pts/sec | OW2 |
| On-Fire threshold | 250 pts | OW2 |
| KAST benchmark | 70%+ = great | CS2 |
| Deaths vs kills weight | -0.53 vs +0.36 | HLTV 2.0 |
| Eco-adjusted kill range | 0.54x — 1.10x | HLTV 3.0 |
| RWS lost round value | 0 points | ESEA |
| Leetify credit: killer | 35% | Leetify |
| Leetify credit: damage dealers | 30% | Leetify |
| Leetify credit: traded death | 20% | Leetify |

### Open Source References
| Project | URL | Use |
|---------|-----|-----|
| PandaSkill | github.com/PandaScore/PandaSkill | Per-role XGBoost framework |
| OpenSkill | github.com/vivekjoshy/openskill.py | Bayesian rating backbone |
| HLTV 2.0 calc | github.com/mang0cs/hltv-rating-2.0 | Rating formula reference |
| cs-demo-manager | github.com/akiver/cs-demo-manager | HLTV + RWS implementation |

---

---

## Appendix B: Overwatch 2 Deep-Dive — Key Parallels

OW2 is the closest mainstream analog to ET:Legacy — both have wave respawns, escort modes,
high TTK, class roles, and revive mechanics.

### Stagger = ET Spawn Timing
OW2 Season 12+ uses wave respawns (12s base, 6s join window). Killing enemies at
staggered times prevents regrouping. ET's fixed spawn waves (20s/30s) make this even
MORE impactful — a kill right after spawn wave = max 28-29s denial.

### PIR (100 pts/min baseline per class)
OWL Player Impact Rating normalizes ALL heroes to 100 pts/min baseline.
A Mercy contributing through rez/heals = 100 = a Genji contributing through kills.
This is the production-proven approach for cross-class fairness.

### On-Fire System (mapped to ET)
| OW2 Action | Fire | ET Equivalent | Proposed Fire |
|------------|------|---------------|---------------|
| Kill (% HP dealt) | % of max HP | Kill | spawn_timing × 100 |
| Mercy Rez | 50 | Medic Revive | 50 × revive_utilization |
| Healing (5 HP) | 1 | Health pack | 1 per 5 HP |
| Damage blocked (25 dmg) | 1 | — | — |
| Payload escort (1s) | 10 | Objective proximity | 10 per second near obj |
| Capture point | 180 | Engineer construct | 100 |
| Decay | -5/sec | Decay | -5/sec |

### PBSR Failure — What NOT To Do
Comparing "Medic vs average Medic stats" leads to stat-padding and one-trick inflation.
Use win-probability models (STRATZ IMP) or outcome-tied metrics (KOST) instead.

### Mercy Rez Quality → Medic Revive Quality
OW2 community evaluates revives by:
- Did the rezzed player survive >5 seconds?
- Did the team win the fight after rez?
- Was the rez into enemy danger zone? ("throw rez")
Our KILL_OUTCOME tracks `delta_ms` (time dead) and `effective_denied_ms` which enables this.

---

## Appendix C: Implementation Status (2026-03-20)

### Completed Today
- [x] Lua: KILL_OUTCOME state machine (et_Obituary → et_Damage body tracking → PMF_LIMBO poll)
- [x] Parser: KillOutcome dataclass + section detection + import
- [x] DB: Migration 021 proximity_kill_outcome table
- [x] Lua: Spawn timer cvar fix (g_redlimbotime/g_bluelimbotime)
- [x] Lua: MOD_TO_WEAPON lookup (47 mappings)
- [x] Lua: Headshot detection via hitRegions delta
- [x] Lua: Spawn timing reinforcement offset (CS_REINFSEEDS)
- [x] Lua: LOS stance-based eye height
- [x] Parser: FOCUS_FIRE pipeline
- [x] Parser: Reimport idempotency guard
- [x] Service: ProximitySessionScoreService (7 categories)
- [x] Bot: !psession command
- [x] API: /proximity/session-scores
- [x] Frontend: Session Combat Score panel
- [x] Design doc: PROXIMITY_SMART_SCORING_DESIGN.md

### Next Steps
- [ ] Deploy Lua v5.1 to game server
- [ ] Verify spawn_timing_score > 0 + KILL_OUTCOME data after first game
- [ ] REVIVE_CONTEXT section (spawn_timer_remaining at revive time)
- [ ] GIB_CONTEXT section (medic proximity + team cohesion enrichment)
- [ ] KPR + TDS calculations in session score
- [ ] KROGT consistency metric
- [ ] Per-class percentile normalization (PandaSkill approach)

*Research covered CS2 HLTV 3.0, Valorant ACS, OW2 On-Fire/PIR/PBSR/stagger, R6 Siege KOST,
Dota 2 STRATZ IMP, Marvel Rivals, PandaSkill framework. ET:Legacy source code audited for
gib (GIB_HEALTH=-175), revive (BODY_TIME=10s), and spawn (PMF_LIMBO=16384) mechanics.*
