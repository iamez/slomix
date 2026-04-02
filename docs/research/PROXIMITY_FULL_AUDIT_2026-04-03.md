# Proximity System Full Audit

**Date**: 2026-04-03
**Session**: Audit & Evolution Planning
**Trigger**: Live session (2026-04-02, 6 players, 12 rounds, 6 maps) revealed need for deeper proximity understanding
**Auditor**: Claude + iamez

---

## 1. Pipeline Overview

```
ET:Legacy Game Server
  └── proximity_tracker.lua (v6.01, 4308 lines)
        ├── 200ms position sampling (5x/sec)
        ├── Event-driven: et_Damage, et_ClientSpawn, et_RunFrame
        ├── 23+ data sections per round
        └── Output: {date}-{map}-round-{N}_engagements.txt

SSH Monitor (60s poll) + Lua Webhook (instant)
  └── Downloads engagement files to local_proximity/

ProximityParserV4 (parser.py, 3583 lines)
  ├── Parses all 23 sections
  ├── Resolves round_id via round_linker
  ├── Idempotent import (ON CONFLICT DO NOTHING)
  └── Writes to 24 proximity_* tables

Website Backend (FastAPI)
  ├── 12 sub-routers (50+ endpoints)
  ├── Storytelling service (109KB, KIS/moments/narrative)
  └── Prox scoring service (percentile-based)

React Frontend
  ├── Proximity.tsx (75KB) — Dashboard
  ├── ProximityPlayer.tsx (27KB) — Player profile + radar
  ├── ProximityReplay.tsx (19KB) — Round timeline replay
  └── Story.tsx — KIS moments, narrative, momentum
```

---

## 2. Lua Script: proximity_tracker.lua v6.01

### What It Collects
| Section | Data | Sampling |
|---------|------|----------|
| ENGAGEMENTS | Combat encounters (attacker, victim, damage, positions, outcome) | Event-driven (et_Damage) |
| PLAYER_TRACKS | Full movement paths per life (x,y,z,health,speed,weapon,stance,sprint) | 200ms continuous |
| KILL_HEATMAP | Grid-based kill locations (512-unit cells) | Per kill |
| MOVEMENT_HEATMAP | Traversal/combat/escape density | Per sample |
| OBJECTIVE_FOCUS | Time near objectives per player | Continuous |
| REACTION_METRICS | Return fire, dodge, support latency (ms) | Per engagement |
| SPAWN_TIMING | Kill timing relative to spawn waves | Per kill (v5) |
| TEAM_COHESION | Formation tightness, dispersion, buddy pairs | Time-series (v5) |
| CROSSFIRE_OPPORTUNITIES | LOS-based crossfire detection (angular separation) | Per engagement (v5) |
| FOCUS_FIRE | Multi-attacker coordination | Per engagement (v5) |
| TEAM_PUSHES | Coordinated team movement (direction, alignment) | Event-driven (v5) |
| TRADE_KILLS | Revenge kills within time window | Per kill (v5) |
| REVIVES | Medic revive context (under fire, enemy distance) | Per revive |
| WEAPON_ACCURACY | Per-player per-weapon shots/hits/kills/headshots | Per round |
| KILL_OUTCOME | Death type (gib/revive/tapout) + body region | Per kill (v5.1) |
| HIT_REGIONS | Body part hit tracking | Per hit |
| COMBAT_POSITIONS | Position at damage events + killer_health + alive counts | Per damage (v5.2) |
| CARRIER_EVENTS | Flag/doc carrier tracking (pickup/drop/efficiency) | Event-driven (v6) |
| CARRIER_KILLS | Carrier kill context | Per kill (v6) |
| CARRIER_RETURNS | Flag return events | Per return (v6) |
| VEHICLE_PROGRESS | Vehicle objective progress | Event-driven (v6) |
| ESCORT_CREDIT | Escort mission contribution | Event-driven (v6) |
| CONSTRUCTION_EVENTS | Engineer construction events | Event-driven (v6) |
| OBJECTIVE_RUNS | Objective completion records | Per completion |

### Oksii Adoption Fields (v5.2+)
- `killer_health`: Health of attacker at kill moment
- `axis_alive` / `allies_alive`: Team alive counts at event time
- `killer_reinf` / `victim_reinf`: Seconds to team respawn
- `alive_count`: Per-team alive count in cohesion data

### Key Limitation: No Spawn-to-Death Full Journey
Position tracking starts only when player takes damage (engagement trigger). **Missing**:
- Path from spawn to first engagement
- Path after escaping an engagement
- Time spent behind enemy lines before engaging
- **This is the critical gap for "lurker" detection** — see Section 8.

---

## 3. Database Tables (24 proximity tables)

### Data Volume (as of 2026-04-02)
| Table | Records | Notes |
|-------|---------|-------|
| proximity_reaction_metric | 32,018 | Largest — reaction timings |
| proximity_team_cohesion | 241,022 | Time-series, very dense |
| proximity_hit_region | 68,332 | Per-hit body part |
| proximity_trade_event | 24,611 | Computed trade kills |
| proximity_team_push | 17,931 | Coordinated movement |
| proximity_spawn_timing | 12,696 | Kill timing vs spawn |
| proximity_combat_position | 9,295 | Positional snapshots |
| proximity_kill_outcome | 8,955 | Kill outcome analysis |
| proximity_focus_fire | 6,252 | Multi-attacker events |
| proximity_weapon_accuracy | 5,000 | Weapon stats |
| proximity_crossfire_opportunity | 4,776 | Crossfire detection |
| proximity_lua_trade_kill | 2,213 | Lua-detected trades |
| proximity_revive | 2,066 | Medic revives |
| proximity_objective_focus | 1,301 | Objective proximity |
| proximity_construction_event | 534 | Engineer constructions |
| proximity_objective_run | 386 | Objective completions |
| proximity_support_summary | 338 | Support class stats |
| proximity_carrier_event | 201 | Carrier tracking |
| proximity_carrier_kill | 94 | Carrier kills |
| proximity_carrier_return | 72 | Flag returns |
| proximity_escort_credit | 44 | Escort credits |
| proximity_vehicle_progress | 22 | Vehicle progress |
| proximity_processed_files | 143 | Import tracking |
| **TOTAL** | **~450,000** | |

### Round Coverage
- **Rounds with proximity data**: 112 distinct round_ids
- **Total rounds in database**: 1,442 (round_number 1 or 2)
- **Coverage**: 7.8% — **expected**, Lua deployed recently
- **Last 7 days**: 65 rounds — healthy daily flow

### Data Quality Issues

#### GUID Format Mismatch (CRITICAL)
- **Proximity tables**: Full 32-char GUID (`D8423F90F045D9D3E2C0550811C5A899`)
- **Stats tables**: Truncated 8-char prefix (`D8423F90`)
- **Impact**: Cannot directly JOIN proximity ↔ stats without `LEFT(guid, 8)` or `SUBSTRING`
- **Fix**: Planned `guid_canonical` column addition (see memory: guid_canonical_plan.md)

#### NULL round_id Records (933 total)
| Table | NULL count | % of total |
|-------|-----------|------------|
| proximity_reaction_metric | 377 | 1.2% |
| proximity_trade_event | 265 | 1.1% |
| proximity_kill_outcome | 211 | 2.4% |
| proximity_crossfire_opportunity | 80 | 1.7% |
- Re-linker exists (`proximity_cog.py:347-494`) but doesn't catch all

#### `time_played_percent = 0.0`
- All players show 0.0 in `player_comprehensive_stats.time_played_percent`
- Unknown if parser calculates this or stats file provides it
- **Not proximity issue** — stats parser issue

---

## 4. API Endpoints (50+ across 12 sub-routers)

### Live Test Results (2026-04-02 session data)

| Endpoint | HTTP | Size | Status |
|----------|------|------|--------|
| `/api/proximity/summary` | 200 | ~1KB | Working — 1690 engagements, 6 players |
| `/api/proximity/leaderboards?category=power` | 200 | ~1KB | Working |
| `/api/proximity/spawn-timing` | 200 | ~1KB | Working |
| `/api/proximity/cohesion` | 200 | **118KB** | Working — large (time-series) |
| `/api/proximity/kill-outcomes` | 200 | **81KB** | Working — large |
| `/api/proximity/hit-regions` | 200 | ~1KB | Working |
| `/api/proximity/carrier-events` | 200 | ~7KB | Working |
| `/api/proximity/reactions` | 200 | ~3KB | Working |
| `/api/proximity/trades/summary` | 200 | ~0.4KB | Working |
| `/api/proximity/weapon-accuracy` | 200 | ~3KB | Working |
| `/api/proximity/revives` | 200 | ~3KB | Working |
| `/api/proximity/prox-scores` | 200 | ~3KB | Working — 26 players rated |
| `/api/storytelling/kill-impact` | 200 | ~3KB | Working — 618 kills scored |
| `/api/storytelling/narrative` | 200 | ~0.4KB | Working — generates text |
| `/api/storytelling/momentum` | 200 | ~8KB | Working |
| `/api/storytelling/synergy` | 200 | ~0.4KB | Working |
| `/api/storytelling/moments` | 200 | ~5KB | Working — 5 moments detected |

**Initial scan: 17/17 endpoints = 200 OK.**

### Deep Endpoint Audit (3 parallel audit teams, 2026-04-02 session data)

Tested 39 endpoints total across combat, teamplay, scoring, objectives, storytelling, player profiles, and round details.

#### CRITICAL Bug (1)
| Endpoint | Issue | File | Fix |
|----------|-------|------|-----|
| `/proximity/session-scores` | **BROKEN** — returns `{"status":"error"}`. Query uses `string_to_array()` on `jsonb` column `combat_engagement.attackers`. Also references non-existent `proximity_focus_fire.attacker_names`. | `bot/services/proximity_session_score_service.py:60,150` | Use `jsonb_array_elements_text()` instead |

#### MEDIUM Issues (4)
| Endpoint | Issue |
|----------|-------|
| `/proximity/movers` | `spawn_reaction` category returns empty array despite data existing in `/classes` endpoint |
| `/proximity/events` | `attacker_name`, `target_team`, `attacker_team` are **systematically empty strings** for all events |
| `/storytelling/synergy` | `trade=0.0` and `medic=0.0` for both groups despite 88 revives and trade kills existing. 40% of composite weight zeroed out → unreliable composite |
| `/storytelling/win-contribution` | `survival=0.98` for ALL 6 players regardless of actual time_dead (13%-25%). Not differentiating |

#### LOW Issues (6)
| Endpoint | Issue |
|----------|-------|
| `/storytelling/kill-impact` | `solo_clutch_kills=0` for all 6 players despite 79 clutch kills. Threshold too strict for 3v3 |
| `/storytelling/kill-impact/details` | `killer_health=-30` on one kill (posthumous kill edge case). Multiplier correctly stayed 1.0 |
| `/proximity/round/{id}/tracks` | **1.8 MB response** for single round. Path data double-serialized JSON. Performance concern |
| `/proximity/leaderboards?category=power` | `teamplay=100` for ALL 6 players — thresholds (cf/5, tr/3) saturate too easily in 12-round sessions |
| `/proximity/crossfire-angles` | `top_duos` returns GUIDs, not player names |
| `/proximity/combat-positions/heatmap` | Requires `map_name` parameter, while `/hotzones` auto-selects — inconsistent API |

#### COSMETIC Issues (3)
| Endpoint | Issue |
|----------|-------|
| `/storytelling/narrative` | "anchored the team" doesn't account for opposing teams in 3v3 |
| `/storytelling/moments` | `focus_survival` moment at `time_ms=0` (edge case) |
| All scoring endpoints | Error responses return HTTP 200 with JSON error body instead of proper 500 |

#### Healthy Endpoints (28/39)
All other endpoints return correct data with 6/6 players, plausible score ranges, and consistent cross-endpoint values. Notably:
- **Storytelling moments**: High quality narratives ("TEAM WIPE — AXIS eliminated all 3 ALLIES in 6.0s", "wiseBoy avenged .olz by trading SuperBoyy in 0.1s")
- **KIS scoring**: Oksii multipliers active — health_mult on 11.7% kills, alive_mult 10.2%, reinf_mult 16.8%
- **Carrier tracking**: Full carry/return/kill data across 5 maps
- **Movement stats**: All 6 players with full stance/speed/sprint profiles (vid notably 45% crouching vs 6-22% others)
- **Momentum**: Clean 30-second interval data for all 12 rounds

### Sub-Router Architecture
| Router File | Endpoints | Focus |
|-------------|-----------|-------|
| `proximity_dashboard.py` (28KB) | 5 | Dashboard dispatcher (30 parallel sections) |
| `proximity_combat.py` | 3 | Engagements, hotzones, classes |
| `proximity_teamplay.py` (22KB) | 7 | Spawn timing, cohesion, crossfire, pushes, trades |
| `proximity_scoring.py` (26KB) | 6 | Leaderboards (8 categories), prox_scores, weapon accuracy |
| `proximity_positions.py` (19KB) | 6 | Hit regions, heatmaps, kill lines, danger zones |
| `proximity_movement.py` (12KB) | 2 | Movers, reactions |
| `proximity_player.py` (11KB) | 2 | Player profile + radar |
| `proximity_round.py` (11KB) | 3 | Timeline, tracks, team comparison |
| `proximity_objectives.py` (29KB) | 6 | Carrier, vehicle, escort, construction |
| `proximity_events.py` | 2 | Raw events + single event detail |
| `proximity_trades.py` (13KB) | 3 | Trade summary, player stats, events |
| `proximity_support.py` (8KB) | 1 | Movement stats |
| **storytelling_router.py** (6KB) | 8 | KIS, moments, narrative, synergy, momentum |

---

## 5. Existing Metrics & Scoring

### Kill Impact Score (KIS)
**Service**: `website/backend/services/storytelling_service.py` (109KB)

Multipliers:
- Carrier kill: 3.0x, Carrier chain (kill + return <10s): 5.0x
- Crossfire: 1.5x
- Spawn timing: 1.0-2.0x (based on denial)
- Gib (permanent): 1.3x, Revived: 0.5x
- Class weights: Medic 1.5x, Engineer 1.3x, FieldOps 1.1x
- Long range (>800u): 1.2x

**Live data (2026-04-02)**: 618 kills scored. Top: vid (326 KIS, pressure_engine archetype).

### Player Archetypes (auto-detected)
- `pressure_engine` — High DPM, consistent aggression
- More archetypes defined in storytelling service

### Prox Scores (3-axis percentile)
| Axis | Metrics | Weight |
|------|---------|--------|
| prox_combat | headshot%, escape rate, return fire ms, KPR, peak speed, dodge ms | 6 metrics |
| prox_team | spawn score, crossfire rate, support reaction, trades, revive rate, focus survival | 6 metrics |
| prox_gamesense | distance/life, sprint discipline, post-spawn rush, stance variety, timed kills, denied time | 6 metrics |

**Live data**: 26 players rated. vid: combat 60.9, team 46.2, gamesense 80.4, overall 60.6.

### Session Scores (7 categories)
- kill_timing (25%), crossfire (15%), focus_fire (10%), trades (15%), survivability (15%), movement (10%), reactions (10%)

### Match Moments (auto-detected)
Types: `push_success`, `team_wipe`, `objective_run`, `objective_denied`, `carrier_chain`
**Live data**: 5 moments detected for 2026-04-02 session.

### Narrative Generator
Generates: `"Session 106 on et_brewdog, etl_adlernest... was defined by vid's pressure engine performance (312.5 DPM, 326 KIS). SuperBoyy anchored the team with 88 revives..."`

---

## 6. Frontend Components

| Component | Size | Purpose |
|-----------|------|---------|
| `Proximity.tsx` | 75KB | Main dashboard — scope filters, 30+ section dispatcher |
| `ProximityPlayer.tsx` | 27KB | Player profile — 5-axis radar, engagement stats |
| `ProximityReplay.tsx` | 19KB | Round timeline replay |
| `ProximityTeams.tsx` | 11KB | Team composition & stats |
| `Story.tsx` | ~15KB | KIS moments, narrative, momentum chart |
| `proximity-glossary.ts` | 9.5KB | Metric definitions & tooltips |
| Story components (6) | ~30KB | PlayerStoryCard, ArchetypeBadge, NarrativePanel, StoryHero, MomentumChart, MomentCard |

---

## 7. Round Correlation Integration (NEW - 2026-04-03)

**Committed today**: `has_r1_proximity` + `has_r2_proximity` flags added to `round_correlations` table.

- Migration: `migrations/034_add_proximity_correlation_flags.sql`
- Service: `round_correlation_service.py` — `on_proximity_imported()` method
- Hook: `proximity_cog.py` — calls correlation after successful import
- Completeness: +5% per proximity round (capped at 100%)

**Status**: Deployed, waiting for bot restart to activate.

---

## 8. Evolution Roadmap

### Vision: "Nevidna Vrednost" (Invisible Value)

Raw stats penalize team players, tactical players, and "lurkers" who create space for their team.
Proximity data has the foundation to measure what stats cannot — but needs new metrics.

### Phase 1: Data Quality Fixes
| Task | Status | Priority |
|------|--------|----------|
| GUID format harmonization (LEFT(guid,8) matching) | Planned | HIGH |
| NULL round_id cleanup (933 orphan records) | Planned | HIGH |
| time_played_percent investigation | Planned | MEDIUM |
| Correlation proximity flags | **DONE** | ✅ |

### Phase 2: New Metrics (Requires GUID fix first)

#### "Gravitacija" (Gravity Score)
- **Measures**: How much enemy attention a player attracts
- **Data available**: `num_attackers` per engagement, `focus_fire` events, `combat_position` alive counts
- **Formula**: `gravity = SUM(num_attackers * engagement_duration) / time_alive`
- **Meaning**: Higher gravity = more space created for teammates

#### "Prostor" (Space Created)
- **Measures**: What happens after your death — does team capitalize?
- **Data available**: kill_outcome times, carrier_event times, construction_event times
- **Formula**: `space = (teammate_kills_10s + objective_events_10s * 3) / deaths`
- **Meaning**: Productive deaths vs. wasted deaths

#### "Enabler" Score
- **Measures**: How many teammate kills happen near your engagements
- **Data available**: trade_events, crossfire_opportunity, focus_fire, engagement positions/times
- **Formula**: `enabler = teammate_kills_within_5s_500u / time_played`
- **Meaning**: You create kills for others, not just yourself

### Phase 3: Lurker Detection (Requires Lua v7)

**Current limitation**: Lua tracks positions only during engagements (after first damage).

**Needed**: Full spawn-to-death journey tracking.
- Path from spawn to first engagement
- Time spent behind enemy lines
- Distance from teammates
- Route deviation from normal paths

**Lua v7 changes required**:
- Track `PLAYER_TRACKS` from spawn, not from first damage
- Add `behind_enemy_lines` detection (position relative to team centroids)
- Add `solo_time_ms` metric (time without teammates within radius)

**What this enables**:
- Lurker profile: "Played 45s behind enemy lines, forced 2 enemies to rotate, died at objective — 8s later teammate took objective"
- Route disruption: "Changed enemy patrol patterns by 30%"
- Solo effectiveness: "Created 3 enabler events while solo"

### Phase 4: Narrative Evolution
- Integrate gravity/space/enabler into storytelling_service.py
- Generate per-player stories instead of just session summaries
- Example: "wiseBoy odcepil od ekipe, 15s sam za sovražnimi linijami, pritegnil 2 sovražnika (gravity: 4.2), umrl pri objectivu — 8s kasneje vid vzel objective (space_created: +1)"

---

## 9. Key File Reference

| Category | File | Lines | Purpose |
|----------|------|-------|---------|
| **Lua** | `proximity/lua/proximity_tracker.lua` | 4,308 | Game server data collection |
| **Parser** | `proximity/parser/parser.py` | 3,583 | Text → DB pipeline |
| **Bot Cog** | `bot/cogs/proximity_cog.py` | ~700 | SSH download + import + re-linker |
| **Correlation** | `bot/services/round_correlation_service.py` | ~640 | Match completeness tracking |
| **Dashboard API** | `website/backend/routers/proximity_dashboard.py` | ~28KB | 30-section dispatcher |
| **Scoring API** | `website/backend/routers/proximity_scoring.py` | ~26KB | Leaderboards + prox_scores |
| **Objectives API** | `website/backend/routers/proximity_objectives.py` | ~29KB | Carrier/vehicle/construction |
| **Helpers** | `website/backend/routers/proximity_helpers.py` | ~21KB | Scope building, GUID resolution |
| **Storytelling** | `website/backend/services/storytelling_service.py` | ~109KB | KIS engine, narratives, moments |
| **Prox Scoring** | `website/backend/services/prox_scoring.py` | ~21KB | Percentile composite scores |
| **Frontend** | `website/frontend/src/pages/Proximity.tsx` | ~75KB | Main dashboard UI |
| **Story UI** | `website/frontend/src/pages/Story.tsx` | ~15KB | KIS/narrative/momentum |

---

## 10. Summary

**What works well**: Pipeline is solid — Lua collects 23 sections of data, parser imports reliably, 50+ API endpoints all return 200 OK, frontend renders everything. Storytelling already generates KIS scores, moments, and narratives.

**What needs fixing**: GUID mismatch (32-char vs 8-char), 933 NULL round_id records, time_played_percent always 0.

**What's missing for the vision**: Spawn-to-death full journey (Lua v7), gravity/space/enabler metrics, lurker detection, per-player narrative stories.

**Key insight**: The foundation is much more mature than expected. The gap is not in data collection (Lua is excellent) but in **interpretation** — turning raw engagement data into stories about invisible value.
