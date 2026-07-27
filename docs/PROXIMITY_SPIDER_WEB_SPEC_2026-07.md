# Proximity Spider Web — implementation specification

**Status:** specification for delegation. No production code was written for it.
**Date:** 2026-07-27
**Every number in this document came from a query run against the dev database on that date.** Where a claim could not be verified, it says so.

---

## §0 Povzetek za ownerja (slovensko)

Cilj: proximity ne sme le vedeti, **kje** je igralec, ampak ali je njegov premik v tistem trenutku skladen s pozicijami soigralcev, z uro runde in s fazo respawn valov nasprotnika. Čas runde je tretji nasprotnik.

**Dobra novica iz raziskave:** podatke večinoma **že imamo**. `player_track.path` vsebuje 7.989.430 pozicijskih vzorcev na 200 ms in vsi igralci v rundi delijo isto časovno os — rundo lahko prerežemo v poljubnem trenutku in dobimo pozicijo vseh. Ta stolpec je bil stisnjen v `avg_speed`, `sprint_percentage` in `total_distance` — tri metrike, ki so v #556 izmerile kot šum. Signal nismo izgubili pri zajemu, ampak pri agregaciji.

**Druga dobra novica:** fazo respawn vala je mogoče rekonstruirati za **vso zgodovino** brez spremembe Lue. Formulo se da obrniti in offset izračunati nazaj iz obstoječih ubojev — deluje v 98,7 % primerov.

**Tretja dobra novica — popravek prve različice tega dokumenta:** prvotno je tu pisalo, da vidnosti (kdo koga dejansko vidi) za zgodovino ni mogoče izračunati. **To ni res.** Same mape v `/home/samba/share/etmain` nosijo `.bsp` s polno geometrijo (10 MB za Adlernest), plus `.objdata` z opisi objectivov in `.script` z logiko stopenj. Vidnost se torej **da** izračunati offline, za vso zgodovino, brez dotikanja igralnega strežnika — rabi pa BSP collision parser, kar je resno delo.

Napaka je nastala tako, da je Codexov review iskal po *repu*, kjer geometrije res ni, jaz pa sem njegov sklep prevzel, ne da bi odprl same mape. Owner je ves čas pravil, da ".pk3 ima koordinate objektivov in vsega" — imel je prav.

**Kar iz map dobimo poleg vidnosti:** spawn točke obeh ekip (42–159 na mapo), objective **volumne** namesto krogel s polmerom 500, ter vrata in premikala, ki med rundo spreminjajo poti. Spawn točke plus faza vala pomenijo, da lahko izračunamo, **kje bo nasprotnik po naslednjem valu** — to je "tretji nasprotnik" narejen konkretno.

**Kar ostaja resnično blokirano:** smer pogleda med gibanjem (zajemamo jo le ob strelu) rabi novo Lua verzijo in nove seje.

**Kaj je v tem dokumentu:** štirje sloji (mreža → ura → informacijsko stanje → kakovost giba), vsak s podatkovnim modelom, algoritmom, robnimi pogoji in merljivimi kriteriji sprejema. Plus BSP toolchain (§9), kopičenje čez seje (§14) in seznam pasti, ki so bile v prejšnjih poskusih dejansko izmerjene kot napačne.

**Železno pravilo:** nobena formula ne dobi uteži, dokler ne prestane merjenja iz #556.

---

## §1 Purpose and non-goals

### What the web is

A relational, per-moment reconstruction of a round: for any time `t`, the position and state of every player, the relationships between them, the phase of both teams' reinforcement cycles, and an estimate of what each team could plausibly have known at that moment.

### What it is explicitly not

- **Not a UI redesign.** The owner has ruled UI/UX out of scope repeatedly. Visualisation is Phase D and only after signal is demonstrated.
- **Not a new score.** Nothing derived here enters a leaderboard, a rating, or a composite until it has passed §8. This is not a preference; #556 retired 13 of 18 `prox_score` metrics that had been scoring players for months, two of them **backwards**.
- **Not a replacement for `replay_service.py`.** That service already slices a round at time `t`. The web extends it.
- **Not a claim to know what players saw or said.** See §6.

---

## §2 Verified data inventory

### 2.1 Volumes (dev database, 2026-07-27)

| Source | Rows | Carries |
|---|---:|---|
| `player_track.path` (JSONB) | **7,989,430 samples** across 57,311 lives | `x, y, z, time, event, speed, health, sprint, stance, weapon` |
| `proximity_shot_fired` | **648,214** | `event_time, origin_x/y/z, view_yaw, view_pitch, weapon_id, guid` |
| `proximity_team_cohesion` | **940,479** | `sample_time, team, alive_count, centroid_x/y, dispersion, max_spread, straggler_count, buddy_pair_guids, buddy_distance` |
| `combat_engagement` | **117,594** | `start_time_ms, end_time_ms, target_guid, outcome, attackers` (JSONB), `position_path` (JSONB), `is_crossfire`, `crossfire_delay_ms` |
| `proximity_kill_outcome` | **36,107** | `kill_time, victim_guid, killer_guid, kill_mod, outcome, outcome_time, delta_ms, effective_denied_ms` |
| `proximity_spawn_timing` | **39,895** | `kill_time, enemy_spawn_interval, time_to_next_spawn, spawn_timing_score, killer_reinf, victim_reinf` |
| `proximity_combat_position` | **36,494** | `attacker_x/y/z, victim_x/y/z` |
| `rounds` | **1,929** (R1/R2) | of which **720** have trajectories |
| `objective_zones.json` | 15 maps / 74 objectives | extracted from `.pk3` in `/home/samba/share/etmain` (22 pk3 present) |

Objective *coordinate* coverage is good: the 15 maps in `objective_zones.json` account for roughly **99% of rounds played**. Note this is not the same as **geometry** coverage, which is 91.6% — see §2.5.3, where `etl_frostbite` has coordinates but no BSP.

### 2.2 The shared clock — the single most important property

**All event sources share one time base within a round.** Verified on round 11042 (`etl_adlernest` R1):

| Source | min | max |
|---|---:|---:|
| `player_track.path[].time` | 500 | 423,175 |
| `player_track.spawn_time_ms` / `death_time_ms` | 500 | 423,175 |
| `proximity_shot_fired.event_time` | 5,125 | 423,125 |
| `combat_engagement.start_time_ms` / `end_time_ms` | 5,500 | 423,175 |

Times are round-relative milliseconds. **No offset correction is needed to merge these sources.** Verify this holds for any round you work on before trusting a merge; the check is one query per source.

### 2.3 Sample shape

`player_track.path` is a JSONB array, one row per **life** (not per round). Example element:

```json
{"x": -3772.0, "y": 1168.0, "z": 153.0, "time": 206352, "event": "spawn",
 "speed": 0.0, "health": 124, "sprint": 0, "stance": 2, "weapon": 8}
```

`event` values observed: `spawn`, `sample`, `killed`, `selfkill`, `teamkill`, `round_end`.
Sampling interval is declared in the raw file header as `position_sample_interval=200`.

`combat_engagement.position_path` is the same idea scoped to one engagement, with `event` in `start`, `hit`, `sample`, `death`, `escape`. Times are preserved: only **111 of 110,154** engagements with a path have all-zero times, so treat all-zero as a per-row defect, not the norm.

`combat_engagement.attackers` is JSONB:

```json
[{"guid": "...", "name": "...", "team": "AXIS", "damage": 54, "hits": 3,
  "weapons": {"3": 3}, "got_kill": false, "first_hit_ms": 0, "last_hit_ms": 0}]
```

`combat_engagement.outcome` values: `killed`, `escaped`, `selfkill`, `teamkill`, `fallen`, `round_end`, `disconnect`, `shutdown`, `timeout`.

### 2.4 Raw file sections (Lua tracker v6)

Header keys: `map`, `round`, `crossfire_window`, `escape_time`, `escape_distance`, `position_sample_interval`, `round_start_unix`, `round_end_unix`, `axis_spawn_interval`, `allies_spawn_interval`.

22 sections: `ENGAGEMENTS`, `PLAYER_TRACKS`, `KILL_HEATMAP`, `MOVEMENT_HEATMAP`, `OBJECTIVE_FOCUS`, `REACTION_METRICS`, `SPAWN_TIMING`, `TEAM_COHESION`, `CROSSFIRE_OPPORTUNITIES`, `FOCUS_FIRE`, `TEAM_PUSHES`, `TRADE_KILLS`, `REVIVES`, `WEAPON_ACCURACY`, `KILL_OUTCOME`, `HIT_REGIONS`, `COMBAT_POSITIONS`, `SHOT_FIRED`, `AIM_LOCK`, `CARRIER_EVENTS`, `CONSTRUCTION_EVENTS`, `OBJECTIVE_RUNS`.

**Note the header does NOT contain the reinforcement offset** — only the interval. See §5.

### 2.5 Map assets — the largest untapped source

`/home/samba/share/etmain` holds **22 `.pk3` archives**. Each is a zip; each map ships three files that matter here:

| File | Contents |
|---|---|
| `maps/<map>.bsp` | full geometry — `IBSP` **version 47** (RTCW/ET) |
| `maps/<map>.objdata` | objective descriptions per team, classified primary / secondary / additional |
| `maps/<map>.script` | stage logic: `wm_objective_status`, `trigger stolen`, `trigger dropped`, `wm_setwinner` |

**Consistency is total across every available map.** Checked on all 13 maps that both exist as pk3 and appear in our round data:

| map | BSP | ver | objdata | script | spawns | obj triggers | WOLF objectives |
|---|---|---:|---|---|---:|---:|---:|
| adlernest | IBSP | 47 | yes | yes | 45 | 6 | 3 |
| braundorf_b4 | IBSP | 47 | yes | yes | 61 | 7 | 4 |
| bremen_b3 | IBSP | 47 | yes | yes | 81 | 9 | 5 |
| decay_sw | IBSP | 47 | yes | yes | 119 | 10 | 5 |
| erdenberg_t2 | IBSP | 47 | yes | yes | 98 | 4 | 5 |
| et_brewdog | IBSP | 47 | yes | yes | 42 | 4 | 3 |
| etl_adlernest | IBSP | 47 | yes | yes | 97 | 6 | 3 |
| etl_ice | IBSP | 47 | yes | yes | 97 | 7 | 5 |
| etl_sp_delivery | IBSP | 47 | yes | yes | 97 | 5 | 3 |
| supply | IBSP | 47 | yes | yes | 159 | 9 | 4 |
| sw_goldrush_te | IBSP | 47 | yes | yes | 145 | 10 | 4 |
| sw_oasis_b3 | IBSP | 47 | yes | yes | 116 | 11 | 4 |
| te_escape2 | IBSP | 47 | yes | yes | 48 | 6 | 3 |

#### 2.5.1 BSP lumps (measured on `etl_adlernest.bsp`, 10.2 MB)

Everything a collision trace needs is present and populated:

| Lump | Size | Approx count |
|---|---:|---|
| `planes` | 1,512,544 B | ~63,000 |
| `brushes` | 130,404 B | ~8,150 |
| `brushsides` | 927,960 B | — |
| `nodes` / `leafs` / `leafbrushes` | 60,336 / 84,288 / 84,808 B | BSP tree for fast traversal |
| `entities` | 65,814 B | 540 entities, 34 classnames |

This is the standard Quake3-derived collision model. A ray-vs-brush trace against it is well-trodden work, not research.

#### 2.5.2 Entity classes that matter

From the entity lump of `etl_adlernest`:

| classname | count | why it matters |
|---|---:|---|
| `team_CTF_bluespawn` | 64 | Allied spawn points |
| `team_CTF_redspawn` | 32 | Axis spawn points |
| `trigger_objective_info` | 6 | objective **volumes**, not points |
| `team_WOLF_objective` | 3 | objective markers |
| `script_mover` | 28 | movers that change routes mid-round |
| `func_door_rotating` | 5 | doors that open/close routes |
| `trigger_hurt` / `trigger_heal` / `trigger_ammo` | 2 / 2 / 2 | hazards and supply |

**Spawn points plus wave phase (§5) give the reachable enemy set at any moment.** That is the concrete form of the "third opponent" and it is available today.

#### 2.5.3 Coverage and its limits

Measured across all 1,929 R1/R2 rounds: **1,767 rounds (91.6%) are on a map whose pk3 we hold.**

Missing, with round counts: **`etl_frostbite` (151)**, `et_beach` (4), `radar` (2), `sp_delivery_te` (2), `etl_supply` (2), `mp_sillyctf` (1).

`etl_frostbite` is the one that matters — 7.8% of all rounds, and it **does** have objective coordinates in `objective_zones.json` (from an earlier extraction) but **no BSP here**. Anything requiring geometry must return null for frostbite, not silently fall back to a sphere.

`te_escape2` is provided by three pk3s (`te_escape2_fixed`, `_fixed2`, `_fixed3`). Their BSPs are **byte-identical** (same sha256), so there is no version conflict today — but the toolchain must verify that rather than assume it, and must pick deterministically.

---

## §3 Hard constraints

These are not opinions. Each was checked, and each has killed a plausible-sounding design before.

### 3.1 Blockers — cannot be done with historical data at all

> **Correction to the first revision of this document.** B1 previously read *"Offline line-of-sight is impossible — a repo-wide search finds no BSP, AAS or navmesh asset."* **That was wrong**, and it was wrong in the most damaging direction: it closed off work that is in fact tractable.
>
> The repo-wide search was accurate as far as it went — there is no geometry *in the repository*. But the maps themselves sit in `/home/samba/share/etmain`, and every one of them ships a complete BSP (§2.5). The claim was inherited from the #551 review without opening a single pk3. The owner had been saying all along that ".pk3 ima koordinate objektivov in vsega"; he was right and the analysis was not.
>
> B1 is therefore **withdrawn** and replaced by the §9 workstream. B2 below stands.

**B2. There are no continuous view angles in trajectories.**
`view_yaw` / `view_pitch` exist only in `proximity_shot_fired` and the aim-lock log — i.e. **at the moment of firing**. Between shots, facing is unknown. Field-of-view exposure over time cannot be computed for history. This one genuinely does require §10.

Note the practical consequence of B2 surviving while B1 falls: with geometry we can answer *"was there an unobstructed line between A and B"*, which is a **necessary** condition for seeing. We still cannot answer *"was A looking that way"*, which is the **sufficient** one. Treat offline visibility as **line-of-sight availability**, never as "A saw B", and name it that way in every output.

**B3. Objective-run quality cannot be scored yet.**
`approach_killed` / `denied` rows number zero, so there is no failure class to contrast successful runs against. Any "was this run good" metric would be measuring successes against nothing.

**B4. `path_samples` is not a trajectory.**
Migration 028 defines it as an integer count. It is **not** `player_track.path`. Do not use it to derive nearby-enemy or teammate context for carrier events.

### 3.2 Prohibited proxies — measured wrong, do not reuse

**P1. Do not build danger features from `map_kill_heatmap`.**
It is an aggregate by (map, grid cell) with **no session or time dimension**. Scoring a round against it leaks that round's own outcome into its own input. Leave-one-round-out does **not** repair this, because later rounds still influence the aggregate. Any risk or danger baseline must be built **only from data that existed at scoring time**, which means a time-ordered aggregate, rebuilt per evaluation point.

**P2. `path_efficiency` is not decision quality.**
It is defined as a three-dimensional beeline ratio. On maps where the objective sits behind walls, elevation, sightlines, or a required flank, a high value is evidence of nothing. (The owner's own words: "path efficiency je samo generalno skalkulirana, nima neke duše, samo matematika.")

**P3. Traversal density is not a chokepoint.**
`map_movement_heatmap` counts traversals, combats and escapes by cell. A busy spawn exit and a genuine chokepoint are indistinguishable in that signal.

**P4. `gravity` is not proof of useful lurking.**
Measured at **r = 0.897** against engagement volume. It largely restates "this player was in a lot of fights".

**P5. `useless_defense` cannot supply "the team lost space".**
`compute_useless_defense_deaths` (`website/backend/services/storytelling/advanced_metrics.py:625`) only checks that the victim was defending, had at least the configured reinforcement delay remaining, and was killed. It says nothing about territory.

**P6. Never judge a decision using information the player did not have.**
Using an opponent's true telemetry position when that opponent was unseen and unrevealed retroactively condemns a rational choice. This is both the owner's explicit requirement and an independent finding in the #551 review. It is the reason §6 exists, and it applies to **every** metric in §7.

**P7. Never infer objective contribution from class.**
The owner raised this directly: *"ni samo inženir class tisti ki dela obj — medici tudi delajo objective, npr. prinesejo docse."* He is right, and the map files prove it structurally rather than anecdotally. From `etl_adlernest.objdata`:

```
wm_objective_allied_desc 1 "Primary Objective:**Steal the documents."
wm_objective_allied_desc 2 "Primary Objective:**Transmit the documents at the transmitter."
wm_objective_allied_desc 3 "Secondary Objective:**Construct the command post..."
wm_objective_allied_desc 4 "Secondary Objective:**Dynamite the door controls...
                            *Alternatively, a covert could infiltrate..."
```

Objectives 1 and 2 — the **primary** ones — are carrying tasks, open to any class. Only construction and dynamite are engineer-gated, and objective 4 explicitly offers a covert-ops alternative. A model that reads "engineer" as "the one who does objectives" gets the primary objective of the map backwards.

This has already produced a wrong number once in this project. A "medics do 69.4% of objective work" figure was reported; the real statement is that 69.4% of **carrier events** were medics. Of 4,588 objective events, 45.3% are carries, and medics account for **28.2% of objective work overall**. The denominator was the error, and the class framing is what invited it.

Rule: derive objective contribution from **what the player did** (carried, planted, defused, constructed, escorted), never from what class they were holding.

---

## §4 Layer 1 — the web

### 4.1 Build on what exists

`website/backend/services/replay_service.py` already provides:

| Function | Purpose |
|---|---|
| `get_player_positions(db, round_id, time_ms)` | state of every player at `t` |
| `get_player_paths(db, round_id, from_ms, to_ms)` | trajectories in a window |
| `get_round_timeline(db, round_id)` | all events merged chronologically |
| `_find_position_at_time(path, target_ms)` | bisect over one path |
| `_ensure_path_list(path)` | JSONB-or-text normalisation |
| `_TRACK_ROUND_JOIN` | correct track→round linkage (see §13.4) |

**The web extends this module or a sibling that imports it. Do not re-implement slicing.**

Measured cost of `get_player_positions` today: **27 ms** (round 11042, 6 players) and **51 ms** (round 10188, 8 players).

### 4.2 Data model

```
RoundTimeline
  round_id, map_name, round_number
  tick_ms            = 200
  t_start, t_end     (from min/max sample time)
  snapshots: list[Snapshot]

Snapshot
  t_ms
  players: dict[guid, PlayerState]
  edges:   list[Edge]
  clock:   ClockState        # §5
  info:    InformationState  # §6

PlayerState
  guid, name, team, player_class
  x, y, z, speed, health, sprint, stance, weapon
  alive: bool
  track_id: int              # which life row this came from
  stale_ms: int              # t_ms - sample.time; see 4.4

Edge
  a_guid, b_guid
  kind: "teammate" | "opponent"
  distance
  engaged: bool              # in a shared engagement at t
```

### 4.3 Resolving overlapping lives — mandatory

**3,674 pairs of same-GUID lives overlap in `[spawn_time_ms, death_time_ms]`, across 49 rounds; 2,925 of those pairs are human, not bot.** Slicing at `t` can therefore find more than one candidate life for one player. `get_player_positions` currently takes the first match it encounters (`break`), which is arbitrary and non-deterministic across query plans.

Required rule:

1. Candidates = lives where `spawn_time_ms <= t AND (death_time_ms IS NULL OR death_time_ms >= t)`.
2. Choose the candidate with the **greatest `spawn_time_ms`**; ties break on the **greatest `id`**.
3. When more than one candidate existed, set `PlayerState.overlap_conflict = True` and count it.
4. Expose the conflict count on the timeline. Do not hide it.

Rationale: the later spawn is the more recent state; determinism matters more than being right in an ambiguous case, and the count makes the ambiguity visible instead of silent.

### 4.4 Staleness, not interpolation

Do **not** interpolate positions. Take the last sample at or before `t` and record `stale_ms`. Consumers decide their own tolerance; a metric that silently invents a position between two samples 200 ms apart is inventing movement that may not have happened. Reject a `PlayerState` whose `stale_ms` exceeds a caller-supplied threshold (suggested default 400 ms — two intervals).

### 4.5 Edges

- **Distance edges:** pairwise 3D distance between alive players. For a 6v6 that is at most 66 pairs per tick; a 12-minute round at 200 ms is 3,600 ticks. Budget accordingly (§11).
- **Engagement edges:** an engagement in `combat_engagement` with `start_time_ms <= t <= end_time_ms` links its `target_guid` to every `attackers[].guid`. This is the answer to "is a teammate currently under attack".
- **Isolation:** a player's distance to their nearest living teammate. `proximity_team_cohesion` already computes a team-level `straggler_count` and one `buddy_pair`; the web supersedes it with per-player values but should be cross-checked against it (§11).

### 4.6 What Layer 1 must not do

No scoring. Layer 1 is reconstruction only. If it produces a number that ranks players, it is out of scope.

---

## §5 Layer 2 — the clock (the third opponent)

### 5.1 The unlock

ET:Legacy computes the next reinforcement wave as (from `CG_CalculateReinfTime`, mirrored in `proximity_tracker.lua`):

```
time_to_next = interval − ((reinf_offset + elapsed_time) mod interval)
```

`reinf_offset` is a per-team random 0–15 s value seeded at match start via `CS_REINFSEEDS` (configstring 31). **The Lua computes it but never writes it to the output file** — the header carries only `axis_spawn_interval` and `allies_spawn_interval`.

It does not need to. The relation inverts:

```
reinf_offset ≡ (interval − time_to_next_spawn − kill_time)   (mod interval)
```

Every row of `proximity_spawn_timing` supplies `kill_time`, `enemy_spawn_interval` and `time_to_next_spawn`, so **each kill independently determines the offset** for the victim's team in that round.

### 5.2 Measured reliability

Over groups of `(round_id, victim_team)` with at least 3 kills: **1,249 of 1,266 groups (98.7%) yield exactly one offset value.** The 17 inconsistent groups do **not** contain more than one `enemy_spawn_interval`, so a mid-round spawn-time change is not the explanation; the cause is unresolved.

**Consequence: Layer 2 works for all history with no Lua change.** The Phase C capture (§9) makes it exact and removes the inference, but is not a prerequisite.

### 5.3 Required algorithm

```
For each (round_id, team):
    candidates = [ (interval − ttn − kill_time) mod interval
                   for each spawn_timing row of that team
                   where interval > 0 and ttn is not null ]
    if len(candidates) < 3:            -> offset = None, confidence = "insufficient"
    elif all equal:                    -> offset = that value, confidence = "exact"
    else:                              -> offset = mode(candidates),
                                          confidence = "inferred",
                                          agreement = count(mode)/len(candidates)
```

Never average. An average of two valid-but-different offsets is a third value that is wrong for both.

Then for any `t`:

```
phase(team, t)        = ((offset + t) mod interval) / interval        ∈ [0, 1)
time_to_next(team, t) = interval − ((offset + t) mod interval)
```

`phase` near 0 means the wave has just fired (enemies are fresh and far); near 1 means it is about to fire.

### 5.4 Edge cases that must be handled explicitly

- `enemy_spawn_interval = 0` appears in the data. Treat as unknown, not as a valid interval — a modulus by zero, or a silent substitution, is worse than a null.
- `spawn_timing_score = 0` occurs in **1,494 of 39,895** rows. This is the Lua's `interval <= 0` sentinel, **not** a genuine score of zero. Filter it out; do not average over it.
- Rounds with no `proximity_spawn_timing` rows have no clock. `ClockState` must be nullable and consumers must handle null rather than defaulting to phase 0.

### 5.5 Round remaining

`rounds.round_start_unix` / `round_end_unix` give wall-clock bounds; sample times give in-round bounds. The **stopwatch time limit** (how long the attacking team has) is not currently stored. Until it is, express clock position as elapsed and as fraction of the round actually played, and label it as such. Do not present a fraction-of-limit that we cannot compute.

### 5.6 Reachability — what the clock is actually *for*

Wave phase on its own is a number between 0 and 1. It becomes tactical only when combined with **where the enemy respawns**, and §2.5.2 supplies exactly that: 42–159 spawn entities per map, tagged by team.

For any time `t`:

```
next_wave(team)      = t + time_to_next(team, t)                     # §5.3
reachable(team, T)   = { p : travel_time(spawn_point, p) <= T − next_wave(team) }
```

`travel_time` should be **learned from the 7.99 M trajectory samples**, not assumed from a constant speed: measure realistic point-to-point times per map from how players actually moved. A straight-line estimate reintroduces P2 through the back door.

Two things fall out of this that nothing in the current system can express:

- **"You are somewhere the next wave reaches before your team can support you."** That is the measurable form of the owner's *"če si na napačen čas na napačnih kordinatih, si izven pozicije."*
- **A position's value is a function of phase.** The same coordinates are strong just after a wave (enemies far, spawn drained) and weak just before it. Any space-control metric that ignores phase is averaging two opposite situations.

Spawn points are also **stage-dependent** — maps move forward spawns as objectives complete. Read the `spawnflags` on the spawn entities and cross-reference the stage logic in `.script` (§9); do not treat all spawn entities as simultaneously active.

Not yet verified: whether stage-to-spawn mapping can be resolved for every map from `.script` alone. Treat that as the first question the §9 workstream has to answer, and null the reachability model where it cannot.

---

## §6 Layer 3 — information state

This is the most original part of the design and the one most easily overclaimed. It answers: **what could this team plausibly have known at time `t`?**

### 6.1 What is genuinely knowable, and from what

| Channel | Source | Certainty |
|---|---|---|
| **Kill feed** | `proximity_kill_outcome.kill_time`, both guids | **High.** ET shows obituaries to everyone, so every kill is information to both teams. |
| **Gunfire** | `proximity_shot_fired` (648,214 rows, with `origin_x/y/z`) | Medium. A shot is audible within a radius; the radius is a modelling choice and must be a named parameter. |
| **Contact** | `combat_engagement` time ranges + `attackers` | High for the participants; medium for nearby teammates. |
| **Deaths** | `player_track` `death_time_ms` + position | High for the player who died. |
| **Voice macros** | `proximity_comm_event` | **Currently unusable:** feature flag `comm_events` is off, 96 rows total. |
| **Line-of-sight availability** | BSP trace (§9) | **Available offline** for 91.6% of rounds. See the caveat below. |

**On line-of-sight, precisely.** B1 is withdrawn (§3.1): geometry exists and a trace is implementable. But B2 stands, so what the trace yields is *"there was an unobstructed line between these two points"* — a **necessary, not sufficient** condition for having seen someone. Facing is unknown between shots.

Use it as an **upper bound on what could have been seen**, and combine it with what we do know about attention: a player who fired at time `t` was facing their target (`view_yaw`/`view_pitch` in `proximity_shot_fired`), so shots give occasional ground truth to calibrate against. Never label the output "saw"; label it "had line of sight".

### 6.2 What must be stated plainly in any output

- **Discord voice is not capturable, ever.** The players talk on Discord; that channel does not exist in any dataset and never will. The information state is therefore a **lower bound** on what the team knew.
- `COMM_EVENTS` captures only in-game `vsay` macros — the command type and macro id — not speech. Even switched on, it would not change the previous point.
- The model is an **estimate**, and every panel or metric built on it must be labelled as such.

### 6.3 Suggested model (parameters are choices, not facts)

Maintain, per team, a set of belief items:

```
BeliefItem
  x, y, z          # where the enemy was believed to be
  t_observed       # when the evidence arrived
  source           # "killfeed" | "gunfire" | "contact" | "death"
  subject_guid     # may be null for gunfire if the shooter is not resolvable
  confidence(t)    # decays from 1.0
```

Decay must be explicit and configurable, e.g. `confidence(t) = exp(−(t − t_observed) / τ)` with a separate `τ` per source. **Do not tune τ against the outcome you later test with** — that is the same leakage as P1. Pick τ from game reasoning (roughly: how long is a position worth acting on), fix it, then measure.

Derived per player, per tick:

- `known_enemy_count` — belief items above a confidence threshold
- `nearest_known_enemy_distance`
- `moved_into_unknown` — did the player move toward a region with no recent belief coverage
- `teammate_under_attack` — from engagement edges (§4.5); this is the owner's explicit request and it is **directly available**, no modelling needed

### 6.4 Acceptance for Layer 3

The belief model is only worth keeping if it **changes conclusions**. Required check: take one Layer 4 candidate metric, compute it (a) with true enemy positions and (b) with belief-restricted positions, and report how the ranking differs. If it does not differ, say so and drop the layer rather than carrying complexity that buys nothing.

---

## §7 Layer 4 — movement quality

### 7.1 Working definition

> A movement was good if the player went somewhere that — **given the clock, the wave phase, and what the team actually knew** — increased their team's control of the space that matters, at acceptable risk.

### 7.2 Transferable prior art

This is a solved genre in spatio-temporal sports analytics. Concepts that map directly:

- **Pitch control / space ownership** (Spearman 2018): probability each team controls each point, from positions *and velocities* — who would get there first and in what state. ET translation: who would win the fight for this corridor right now.
- **Voronoi / dominant region** (Taki & Hasegawa): territory partition weighted by movement capability.
- **Off-ball value / expected threat**: the value of *being somewhere* with no event attached. This is precisely the owner's "gib brez ubojа" — the movement that created an opportunity without generating a statistic.
- **Time-to-arrive surfaces**: what space is reachable in the next N seconds.
- **Synchronisation / relative phase**: are teammates moving in step.

### 7.3 The two ET-specific twists no football model has

1. **The reinforcement wave is a discrete clock that periodically resets the opponent's spatial distribution.** The same position is good at phase 0.1 and bad at phase 0.9. This is the owner's "third opponent" and it is the genuinely novel axis.
2. **Information is partial.** In football everyone sees the pitch. Here you know what you saw, heard, or were told. See §6 and P6.

### 7.4 Candidate signals

None of these are approved. Each is a hypothesis to be measured under §8.

| Candidate | Built from | Notes |
|---|---|---|
| Space control share | Layer 1 positions + velocities | Restrict to walkable space using BSP (§9); a naive Voronoi over the bounding box is dominated by solid rock |
| Reachability advantage | learned per-map speeds from the 7.99 M samples | Learn from data, do not assume a constant |
| **Stage-aware objective control** | control × distance to the **currently live** objective volume | See 7.4.1 — the space that matters moves during the round |
| Wave-phase alignment | Layer 2 + §5.6 | Was the player advancing when the enemy wave was furthest from reaching him |
| Isolation | Layer 1 edges | Distance to nearest living teammate; the honest version of "straggler" |
| Information-consistent movement | Layer 3 | Did the player move into space the team had no coverage of |
| Teammate-support presence | Layer 1 engagement edges | Was the player near a teammate who was under attack |
| **Sacrifice that opens space** | 7.4.2 | The owner's own playstyle, and the hardest thing in this list to measure |
| Exposure | BSP line-of-sight availability (§9) | How many enemy positions had a clear line to this player |

#### 7.4.1 Stage awareness is not optional

Stopwatch objectives are **sequential**. On Adlernest the Allies must first steal the documents, then transmit them; the door controls gate access before either. The space that matters at minute 2 is not the space that matters at minute 8.

A metric that scores "control near the objective" against a static point is therefore **systematically wrong for the later part of every round**, and wrong in a direction that rewards whoever camped the first objective longest.

Every candidate above that references "the objective" must resolve **which objective is live at time `t`** (§9 supplies the stage model) or explicitly restrict itself to the first stage and say so.

#### 7.4.2 Sacrifice that opens space

The owner describes himself as *"lurker/teamplayer, ki rad nastavlja ekipi priložnosti z svojim sacrificem"* — a player whose value shows up as opportunities for others, often at the cost of his own life. Under every current metric that behaviour reads as dying a lot.

This is the single clearest case of value that generates no statistic for the player who created it, and it is why "off-ball value" (§7.2) is in this document at all. It needs a named, measurable definition rather than a hope that some composite picks it up.

Proposed shape — **hypothesis, to be measured under §8, not to be shipped on plausibility**:

> In the window after player A dies, did A's team gain something A's death plausibly caused? Candidate consequences: enemies drawn away from the objective route, a teammate completing an objective action, or a net gain in team space control.

Required guards, or this metric becomes "dying is good":

1. **Attribution, not correlation.** The enemies who killed A must be the ones displaced. Use the engagement edges (§4.5), not a time window alone.
2. **Compare against the counterfactual class.** Deaths in the same map region, same stage, same wave phase, that produced *no* team gain. Without that denominator, every death looks productive some of the time.
3. **Leakage.** The baseline of "what usually happens after a death here" must not include the evaluated round (P1).
4. If the measurement says it does not predict round outcome, **it does not ship** — even though it is the owner's own playstyle. Especially then.

### 7.5 Weighting

Only demonstrated signals get weight. Weights are normalised so that **the published weight equals the one that scores** — `prox_score` v3.0 previously advertised a metric as 20% of a category while it was really 57%, because normalisation happened internally and publication did not.

---

## §8 Validation protocol — mandatory

This is the protocol that retired 13 of 18 `prox_score` metrics in #556, two of which were ranking players **backwards**. It is not optional and it is not negotiable per-metric.

### 8.1 Measure within round, never between

Compare a player only against **the other players in the same round**. Between-round comparison is confounded by round length, map, and opponent quality. Concretely: in the #556 pass, `distance_per_life` and `denied_time` looked strong between rounds purely because both accumulate with round duration; the within-round measurement is what separated real from artefact.

### 8.2 Bootstrap over rounds, not players

Teammates share an outcome, so per-player intervals are far too narrow. Resample **rounds** with replacement, 1000 times, and take the 2.5th and 97.5th percentiles.

### 8.3 Judge by the interval, not the point estimate

A metric is kept only if its 95% CI **excludes zero**. In the #556 pass, `kpr` had a spread of +0.028 and would have passed a naive threshold; its interval was [−0.009, +0.064] and it was retired.

### 8.4 Required output per phase

A table of every candidate with: n rounds, spread, 95% CI, verdict. This table is a deliverable, not a working note. Anything not in it does not ship.

### 8.5 Reference implementation

The #556 measurement is reproducible: build a per-(player, round) dataset joined to round outcome, group by round, split each round's players at the median of the metric, and compare win rates of the two halves. Watch for §13.3 (GUID length) when joining proximity to `player_comprehensive_stats`.

---

## §9 Workstream: the BSP toolchain

This section did not exist in the first revision, because the first revision believed map geometry was unavailable. It is the largest new piece of work and it unlocks the most.

**It touches no game server and requires no deploy.** It reads files that are already on the box and covers **91.6% of all rounds ever played** (§2.5.3).

### 9.1 Deliverables, in dependency order

**W1 — pk3 index.**
Walk `/home/samba/share/etmain`, map `map_name → (pk3, bsp)`. Record a sha256 per BSP. Handle one map being provided by several pk3s: today `te_escape2` comes from three and all three BSPs are byte-identical, so pick deterministically and **assert the hashes match** rather than assuming it. Emit an explicit "no geometry" result for the six maps we do not hold — `etl_frostbite` above all, at 151 rounds.

**W2 — BSP reader.**
`IBSP` v47. Read the header (17 lumps, each an `(offset, length)` int32 pair) and parse `planes`, `brushes`, `brushsides`, `nodes`, `leafs`, `leafbrushes`, `models`, `entities`. Refuse any file whose magic or version differs instead of guessing at the layout.

**W3 — entity extraction.**
From the entity lump: spawn points by team (`team_CTF_bluespawn`, `team_CTF_redspawn`) with their `spawnflags`; objective volumes (`trigger_objective_info`); objective markers (`team_WOLF_objective`); doors and movers. This supersedes the sphere-with-radius-500 approximation in `objective_zones.json` — keep that file as the fallback for maps without a pk3, and **label which source each zone came from** so a consumer can tell a measured volume from a guessed sphere.

**W4 — collision trace.**
Ray-vs-brush against solid brushes, using the BSP tree to avoid testing all ~8,150. Standard Quake3-derived model. The output is **line-of-sight availability**, never "saw" (§3.1 B2).

**W5 — stage model.**
Parse `.objdata` for the objective list per team with primary/secondary/additional classification, and `.script` for the stage logic (`wm_objective_status`, `trigger stolen`, `trigger dropped`, `wm_setwinner`). Produce, per map, an ordered stage model and the mapping from stage to active spawn points and live objective.

**This is the deliverable with the most unknowns.** Map scripts are hand-written and vary. The first job of W5 is to establish **for how many of the 13 maps a stage model can actually be derived**, and to return null for the rest rather than inventing one. Do not let §7.4.1 depend on a stage model that silently guesses.

**W6 — validation against live Lua.**
Once §10 C4 is available, compare offline traces against `et.trap_Trace` results on the same positions. This is the only way to know whether W4 is correct. Until then, treat every visibility number as unvalidated and say so in the output.

### 9.2 Risks

- **Brush-based collision is not the same as the engine's player trace.** The engine traces a bounding box, not a ray, and has its own edge behaviour. Expect disagreements at corners; W6 quantifies them.
- **Cost.** A trace per player-pair per 200 ms tick is 66 pairs × 3,600 ticks ≈ 238k traces for one 12-minute round. Measure before committing to a per-tick design; consider a coarser visibility cadence than the movement cadence.
- **`etl_frostbite`** is 151 rounds with objective coordinates but no BSP. Anything geometry-derived must be null there, not silently substituted.

---

## §10 Phase C — Lua v7 capture

Everything here requires a game-server deploy and is **owner-gated**.

### 10.1 Captures requested

| # | Capture | Why it cannot be done otherwise | Cost risk |
|---|---|---|---|
| C1 | `view_yaw` / `view_pitch` in the 200 ms position samples | **B2 — genuinely blocked offline.** Facing is known only at shot time, and geometry does not supply it | Low |
| C2 | `reinf_offset` in the file header, plus a wave timeline | §5 infers it at 98.7%; capture makes it exact and removes the inference | Very low |
| C3 | Objective state over time (dynamite planted, doors, checkpoints) | **Downgraded.** §9 W5 derives the *structure* offline; live *state* transitions are partly reconstructible from `proximity_carrier_event` and `proximity_construction_event`. Capture closes the remainder | Low–medium |
| C4 | Line-of-sight trace (`et.trap_Trace`) | **Reclassified.** No longer the only route — §9 W4 does this offline for 91.6% of rounds. C4's value is now as the **ground truth that validates W4** (W6) | **High, measure first** |
| C5 | Teammate engagement state (is this player under attack right now) | Partially derivable from `combat_engagement`, but a live flag is exact | Low |

Note how C3 and C4 changed. Both were listed as "only possible via Lua" in the first revision. Neither is. C1 is now the only capture here that is strictly required to unblock something, and C4's justification has shifted from capability to verification.

### 10.2 Opportunistic fixes while in the file

- `spawn_timing_score = 0` sentinel collides with a real score of zero (1,494 of 39,895 rows). Emit a distinct null.
- `enemy_spawn_interval = 0` rows should not be written at all.
- Re-check the reinforcement-offset read path against the live build (see gotchas).

### 10.3 Gotchas — read before touching the server

- **Puran runs an older tracker than the repo:** `16bf9fc4` (2026-06-22). Do not assume repo behaviour is live behaviour.
- **Live `shot_fired = true` is deliberate** and differs from the repo default. **Never blind-copy the repo file over the live one.**
- **Never `lua_restart`** — it has crashed the server before. Always a full map load.
- **`c0rnp0rn*.lua` is not ours. Do not touch it.**
- C4 must have its server cost measured on a test map before it is enabled in production. A trace per player-pair per tick is not free.

---

## §11 Phase D — visualisation

Deferred by explicit owner decision: *"podatki zdaj, vizualizacija ko bo signal dokazan."*

When it happens: a new page, not a modification of existing ones. Time slider across the round, players as nodes, edges between them, objective and wave phase shown. Nothing is drawn that has not passed §8 — a beautiful lie is worse than no picture.

---

## §12 Acceptance criteria

Measurable, not descriptive.

### Phase A — Layer 1
- **A1.** For every round with trajectories, positions reconstructed at each kill time match `proximity_combat_position` (an independent source) within a stated tolerance. Report the distribution of the discrepancy, not just a pass/fail. If it does not match, the reconstruction is wrong and nothing downstream is trustworthy.
- **A2.** Team-level aggregates derived from Layer 1 (centroid, dispersion, straggler count) reproduce `proximity_team_cohesion` for the same tick within tolerance.
- **A3.** No player appears twice in a snapshot. Overlap conflicts (§4.3) are counted and exposed.
- **A4.** Full-round reconstruction under **1 s** for a 12-minute round; if not, materialise (see §13.1).

### Phase B — Layers 2 and 3
- **B1.** Wave phase computed for ≥95% of rounds that have `proximity_spawn_timing` rows; the rest explicitly null with a reason.
- **B2.** Offset agreement reported per round; the 17 known-inconsistent groups are flagged, not silently averaged.
- **B3.** §6.4 delta check completed and reported, including the negative result if that is the outcome.

### Phase B — Layer 4
- **B4.** Every candidate in §7.4 measured under §8, with the full table published.
- **B5.** No signal with a zero-crossing interval receives weight.

### BSP toolchain (§9)
- **W1.** Every played map resolves to exactly one BSP or to an explicit "no geometry" result. The six uncovered maps are named in the output, not silently absent.
- **W2.** Parser refuses any file that is not `IBSP` v47 rather than misreading it.
- **W3.** Objective volumes extracted for every covered map, and each published zone states whether it came from a **measured volume** or the legacy sphere.
- **W4.** Trace validated against hand-checked cases on at least one map before any metric consumes it. Cost per trace measured and stated.
- **W5.** Reported honestly: **for how many of the 13 maps a stage model could actually be derived**. A partial answer is acceptable; a fabricated one is not.
- **W6.** Once §10 C4 exists, offline-vs-live agreement rate published. Until then every visibility output is labelled unvalidated.

### Phase C (§10)
- **C1.** Before/after comparison on one map showing the new fields populated.
- **C2.** Server cost of C4 measured and stated before enablement.
- **C3.** W6 agreement rate published, and the offline trace corrected or withdrawn if it disagrees materially.

---

## §13 Data-quality prerequisites

These will bite the implementer. They are listed with the measurement so nobody has to rediscover them.

### 13.1 Overlapping lives
3,674 same-GUID pairs overlap in time across 49 rounds (2,925 human). See §4.3 for the required rule.

### 13.2 The bot gate exists, is applied everywhere, and does nothing

This one deserves care, because the surface reading is the opposite of the truth.

`_round_quality_gate_sql()` (`website/backend/routers/proximity_helpers.py:170`) is a hard gate applied across proximity surfaces by owner decision (2026-07-25, no `include_bots` flag). It reads:

```sql
(prefix.round_id IS NULL OR EXISTS (
   SELECT 1 FROM rounds rq
   WHERE rq.id = prefix.round_id
     AND rq.is_bot_round IS DISTINCT FROM TRUE
     AND rq.is_valid   IS DISTINCT FROM FALSE))
```

So the intent and the plumbing are both correct. But **`rounds.is_bot_round` is FALSE for all 1,929 R1/R2 rounds and TRUE for none** — the flag is never set by anything. The bot half of that gate is therefore a permanent no-op, while reading as if bots were excluded.

Meanwhile the data contains **13 distinct `OMNIBOT*` GUIDs across 7,687 tracks — 13.4% of all tracks**. Bot movement is currently measured as if it were human, everywhere.

Until the flag is fixed, filter on `player_guid LIKE 'OMNIBOT%'` at the player level and treat a round as bot-contaminated above a stated share threshold. Whichever is chosen, **state it in the output**: 13.4% is far too large to leave implicit, and a gate that silently does nothing is worse than no gate, because it stops anyone from looking.

*(Correction to the description of PR #560, which said all bots share one GUID. They do not — there are 13. The duplicate `(round, player, spawn)` rows noted there are 216 human and 114 bot, not bot-only.)*

### 13.3 GUID length mismatch
`player_comprehensive_stats.player_guid` is **8 characters**; proximity tables use **32**. Join with `LEFT(proximity_guid, 8) = pcs_guid`. Omitting this produces a silent zero-row join, not an error — which is exactly how the first #556 measurement attempt produced empty results for all 18 metrics.

### 13.4 Round identity
- `rounds` has **`id`**, not `round_id`. The proximity tables' `round_id` references `rounds.id`.
- To link `player_track` to a round, use **`_TRACK_ROUND_JOIN`** from `replay_service.py`. Do not join on `(session_date, round_number, map_name)`: when a map is replayed on the same date that key matches every repeat. Before PR #560 that bound 24,428 track rows to more than one round, and one 8-player round rendered 14 players and 70 "alive" lives.
- 5.1% of `player_track` rows have `round_id IS NULL`. The helper falls back to the date key only when it is unambiguous.

### 13.5 Round validity
Use the established gate: `round_number IN (1,2) AND is_valid IS DISTINCT FROM FALSE AND (round_status IN ('completed','substitution') OR round_status IS NULL)`. See `_round_quality_gate_sql()` in `website/backend/routers/proximity_helpers.py` and `GamingSessionScope` in `website/backend/services/session_scope.py`.

---

## §14 Cross-session accumulation

The first revision of this document was entirely round-scoped, which missed the owner's founding requirement. He has stated it repeatedly and from the beginning:

> *"skozi čas bomo zajeli veliko sessionov in takrat bodo scori, ki jih collectamo, imeli veliko večjo težo"*
> *"več skillov ima lahko igralec... jaz osebno sem lurker/teamplayer"*

A per-round signal that is never accumulated cannot deliver either half of that: neither the growing weight of evidence, nor a multi-dimensional profile.

### 14.1 What accumulates

Web-derived signals that survive §8 become **axis evidence**, not leaderboard entries. The axes follow the owner's own vocabulary — teamplay, lurk, objective, carry — and a player has a value on each, with a confidence that grows as sessions accumulate.

This is the same subject as `docs/DESIGN_SKILL_PASSPORT_2026-07.md` (PR #551). **Do not build a second, parallel accumulation model.** The web supplies inputs; the Passport owns the accumulation. If the two disagree on shrinkage or versioning, the Passport wins and this document is wrong.

### 14.2 Constraints inherited from the #551 review

These were raised against the Passport design and apply verbatim to anything accumulating web signals. They are unresolved on that PR, so treat them as requirements rather than settled decisions.

1. **Keep shrinkage weights in one evidence unit.** A prior of `C = 5 sessions` cannot be combined with an `n` counted in kills or in axis-specific opportunities. Fifteen kills in one session and one kill in fifteen sessions are not the same evidence, and an unweighted mean of per-session values treats them as such.
2. **Persist the axis evidence count in every snapshot.** Storing only `n_sessions` makes shrinkage, confidence and the insufficient-data gate unreconstructable later, because `n_axis` differs in unit per axis.
3. **Restrict the percentile pool to evidence-qualified players.** If profiles below the evidence threshold are withheld from display but still shape the pool, the many low-evidence players drag the prior toward themselves.
4. **A formula version bump does not make history comparable.** Labelling later snapshots with a new version leaves the historical aggregate averaging percentiles produced by different axis definitions. Reads must be pinned to one formula generation, exactly as `KIS_FORMULA_VERSION` now pins the KIS reads.
5. **Define how a superseding snapshot preserves history.** When telemetry arrives late and the population has moved on, the replacement row carries a different `percentile_at_time` and a different pool. Decide explicitly whether historical reads see the original or the replacement, and store enough of the original pool to recompute — mean, size and standard deviation are **not** sufficient to re-derive an empirical percentile.
6. **Do not let a timeout bypass telemetry completeness.** A six-hour "snapshot anyway" branch produces profiles whose teamplay, lurk and objective axes were computed without their inputs, and nothing downstream can tell them apart from complete ones.

### 14.3 The honest constraint on all of it

Accumulation multiplies whatever it accumulates. If a per-round signal is noise, a season of it is confident noise, which is worse — it looks authoritative. **§8 comes first, always.** Nothing enters the accumulation layer that has not already survived the round-level measurement.

---

## §15 Open questions for the owner

1. **Materialise or compute on demand?** `get_player_positions` is 27–51 ms per call today. A full 3,600-tick reconstruction is a different order of magnitude. Decide after A4 is measured.
2. **The bot flag is never set (§13.2).** Fix it as a separate change before the web, or handle bots by GUID prefix inside the web?
3. **PR #551** (`DESIGN_SKILL_PASSPORT`, `PROXIMITY_VISION_AUDIT`) remains open with 19 unresolved review threads. Their findings are incorporated here as §3; the PR itself still needs a decision.
4. **PR #555** (release 1.28.0) is open and awaiting a call.

---

## §16 Provenance

Verified on the dev database (`etlegacy` @ localhost) on 2026-07-27. Key checks, all repeatable:

- Sample volume: `SELECT COUNT(*), SUM(sample_count) FROM player_track`
- Shared clock: min/max of `path[].time`, `spawn_time_ms`, `shot_fired.event_time`, `combat_engagement.start_time_ms` for `round_id = 11042`
- Offset recoverability: `(interval − time_to_next_spawn − kill_time) mod interval` grouped by `(round_id, victim_team)` having ≥3 rows → 1,249/1,266 single-valued
- Overlapping lives: self-join of `player_track` on `round_id, player_guid` with interval overlap → 3,674 pairs / 49 rounds
- Bot share: `player_guid LIKE 'OMNIBOT%'` → 13 guids, 7,687 of 57,311 tracks
- Linkage: comparison of the date-key join against `round_id` → 24,428 multi-round track rows before PR #560, 0 after

Map assets, checked by reading the archives in `/home/samba/share/etmain` directly:

- pk3 inventory: 22 archives; `map_name → bsp` index built by scanning `maps/*.bsp` in each
- Coverage: 1,767 of 1,929 R1/R2 rounds (91.6%) are on a map we hold; missing are `etl_frostbite` (151), `et_beach` (4), `radar` (2), `sp_delivery_te` (2), `etl_supply` (2), `mp_sillyctf` (1)
- BSP format: magic and version read from the first 8 bytes of each BSP → `IBSP` v47 on all 13 available maps
- Lump sizes: header parsed as 17 `(offset, length)` int32 pairs on `etl_adlernest.bsp` → planes 1,512,544 B; brushes 130,404 B; brushsides 927,960 B; entities 65,814 B
- Entity classes: regex over the entity lump → 540 entities, 34 classnames; per-map spawn / objective-trigger / WOLF-objective counts as tabulated in §2.5
- `.objdata` / `.script` presence: checked per archive → present on all 13 available maps
- Duplicate provision: `te_escape2` supplied by three pk3s; sha256 of each BSP compared → byte-identical

Related: #556 (metric validity method), #560 (track linkage fix), #551 (open design review), `docs/PROXIMITY_VISION_AUDIT_2026-07.md`, `docs/DESIGN_SKILL_PASSPORT_2026-07.md`.

### Revision history

**Rev 2 (2026-07-27)** — written after the owner asked whether the spec actually captured what he wanted from proximity. It did not; seven gaps were found and closed:

| # | Gap | Where |
|---|---|---|
| 1 | Offline line-of-sight declared impossible — **wrong** | §3.1 (B1 withdrawn), §9 |
| 2 | Objective zones left as spheres though volumes exist | §2.5.2, §9 W3 |
| 3 | Objective phase attributed to Lua though `.script` supplies it offline | §9 W5, §10 C3 |
| 4 | Class-agnostic objective work — the owner's explicit correction — absent entirely | §3.2 P7 |
| 5 | Stopwatch stages: "the space that matters" moves during a round | §7.4.1 |
| 6 | Sacrifice that opens space — the owner's own playstyle — unnamed | §7.4.2 |
| 7 | Cross-session accumulation missing; the spec was wholly round-scoped | §14 |

Gaps 1 and 3 were **incorrect claims**, not omissions, and both closed off tractable work. Both are marked in place as corrections rather than quietly rewritten.
