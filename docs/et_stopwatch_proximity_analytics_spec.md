# ET:Legacy Stopwatch Proximity Analytics – Feature Spec (Codex-ready)

> **Purpose:** turn ET:Legacy Lua telemetry (positions + combat events) into **objective/teamplay analytics** for **competitive stopwatch** play (voice comms + strategy), while **minimizing false “baiting” flags** caused by legit sneaky/objective plays.

---

## 0) Design principles

1. **Event-anchored scoring** over “vibes”
   - Prefer scoring tied to **observable moments**: deaths, damage, objective actions, and nearby teammate context.
2. **“Opportunity → attempt → success”** taxonomy
   - Borrow the common FPS analytics framing for trades: **opportunity**, **attempt**, **success**. This is broadly used in CS analytics and translates well to ET. citeturn0search4turn0search14
3. **Stopwatch-aware context gates**
   - Avoid penalizing solo/sneaky plays when the player is likely doing **objective role work** (engineer tasks, objectives, rotations).
4. **Explainable outputs**
   - Every “penalty” should be accompanied by: *what event triggered it, what was expected, why it was considered possible, and what evidence was missing.*

---

## 1) Glossary (analytics terms)

- **Trade kill / trade:** killing the opponent who just killed your teammate. citeturn0search14turn0search4
- **Trade opportunity / attempt / success:** a structured way to track whether you *could* trade, *tried* to trade, and *did* trade. citeturn0search4
- **Baiting (bad):** letting a teammate die without following/supporting when a trade was realistically available. citeturn0search2turn0search18turn0search22
- **Crossfire:** a setup where an enemy cannot challenge one angle without getting shot from another. citeturn0search3
- **Structure/teamplay via trading:** trading stats are often used as a proxy for team structure (who plays in packs, who is isolated). citeturn0search1turn0search9

---

## 2) Telemetry inputs (from ET:Legacy Lua)

### 2.1 Core events
- `weapon_fire(attacker, weapon, time)`
- `damage(attacker, victim, weapon/mod, dmg, time)`
- `obituary(victim, killer, mod, time)` (kills)
- `round_start / round_end / halftime / match_end` (stopwatch rounds)
- `objective_events` (see 2.3)

### 2.2 Position snapshots
- Per player snapshot: `time, origin(x,y,z), velocity, viewangles(yaw/pitch), team, alive_state`
- Frequency targets:
  - **1 Hz** baseline for map control/cohesion
  - **5–10 Hz** “combat window” sampling for short trade/crossfire windows (optional optimization)

### 2.3 Objective context events (critical for false positives)
We need hooks (or approximations) for:
- Plant/defuse / dynamite armed/disarmed
- Objective pickup/deliver/return (flags, documents, gold, etc.)
- Engineer “work” state (building/repairing/constructing)
- Spawn wave / respawn cycles (timing context)

> If ET:Legacy Lua doesn’t expose all objective events directly, approximate via server logs or config-driven triggers per map.

---

## 3) Feature backlog (v1 → v3)

### V1 – Reliable proximity + trade system
1. **Team/enemy proximity windows**
   - nearest teammate distance
   - nearest enemy distance
   - “support radius” uptime (% time within X of >=1 teammate)

2. **Trade framework (opportunity/attempt/success)**
   - When teammate dies at time **T**:
     - teammates within `trade_dist` at T are marked with a **trade opportunity** (expires at `T + trade_window_s`)
   - **Attempt:** player damages killer before expiry
   - **Success:** player kills killer before expiry
   - Output per event: who had the opp, who attempted, who succeeded. citeturn0search4turn0search14

3. **“Missed trade” candidate flags (no penalties yet)**
   - record as *candidate* if:
     - opportunity existed
     - no attempt occurred
     - no objective-context exception triggered
   - This becomes a reviewable dataset before you assign punishment points.

4. **Crossfire uptime (basic)**
   - If >=2 teammates within `crossfire_dist` and viewing directions are sufficiently separated (angle > `crossfire_min_angle_deg`),
     count crossfire uptime. citeturn0search3

### V2 – Stopwatch-aware role/context features
5. **Objective-role exceptions (“anti-false-bait”)**
   - If player is within `objective_zone` OR recently performed objective action,
     suppress/discount baiting penalties for `objective_grace_s`.

6. **Rotation + arrival timing**
   - Time-to-support after teammate first contact
   - Late-follow rate: “fight started, you arrived after it ended”
   - These are *context* metrics; use them cautiously for scoring.

7. **Map control / occupancy heatmaps**
   - Per snapshot, increment team occupancy grid cell
   - Outputs:
     - occupancy_seconds_by_team[cell]
     - contested_time[cell] (both teams present)

### V3 – Higher-level teamwork signals
8. **Buddy system / pairing graph**
   - who plays with whom (pairwise proximity time)
   - stable duos vs floating supports

9. **Pack vs split states**
   - clustering-based team shape per snapshot (e.g., 4–2, 3–3)
   - correlate with round outcomes

10. **Engagement geometry upgrades**
   - Replace distance-only heuristics with:
     - viewangle alignment to fight axis
     - (optional) line-of-sight checks if feasible

---

## 4) Teamplay scoring system (versioned + explainable)

### 4.1 Score philosophy
- **Score = Σ (small continuous positioning value) + Σ (discrete event value) − Σ (validated negative events)**
- Negative events must pass strict validation gates (esp. in stopwatch).

### 4.2 Base weights (starter defaults; tune per league)
**Positive**
- `+0.20 / sec` Support readiness:
  - within `support_dist` of a teammate **who is in combat** (damage/fire in last `combat_recent_s`)  
- `+3` Trade attempt
- `+8` Trade success
- `+0.10 / sec` Crossfire uptime citeturn0search3

**Negative (strict validation)**
- `−6` **Missed trade** (validated):
  - opportunity existed
  - no attempt
  - not in objective exception window
  - not in “planned lurk” exception window (see 4.4)
- `−3` Isolated first contact death:
  - you die while `nearest_teammate_dist > isolation_dist`
  - AND teammates had no trade opportunity on you

> Notes:
> - Trading metrics are widely used to infer “playing in packs vs isolated,” but even HLTV notes trade-only systems can miss successful entries (where you don’t *need* to be traded). Use context and avoid punishing high-impact plays. citeturn0search1

### 4.3 Combat state definition
A player is “in combat” if any occurred in the last `combat_recent_s`:
- fired a weapon
- dealt damage
- took damage

### 4.4 False-positive mitigation (stopwatch/strat play)

**Objective exception**
- Suppress baiting/missed-trade penalties if:
  - player performed objective action within `objective_grace_s`
  - OR player is inside objective zone(s) within `objective_zone_grace_s`
  - OR round phase implies solo task is normal (map-specific)

**Planned lurk exception**
- If player is:
  - far from main cluster (by design) AND
  - not near teammate contact area BUT
  - within a known flank/route zone
- then missed-trade penalties are reduced or suppressed.

**Communication uncertainty**
- Because we can’t read voice comms, we treat “baiting” as **candidate** unless confidence is high.

**Confidence tiers**
- Each negative event outputs `confidence: low/med/high` and only `high` becomes a scored penalty by default.

**Hard caps**
- cap readiness/crossfire farming per round
- normalize by alive time

---

## 5) Config parameters (all tunable)

```yaml
sampling_hz_base: 1
sampling_hz_combat: 8  # optional burst sampling
support_dist: 600
trade_dist: 800
trade_window_s: 3.0
combat_recent_s: 1.5
isolation_dist: 1200
crossfire_dist: 700
crossfire_min_angle_deg: 40

objective_grace_s: 6.0
objective_zone_grace_s: 8.0

score_weights:
  readiness_per_sec: 0.20
  crossfire_per_sec: 0.10
  trade_attempt: 3
  trade_success: 8
  missed_trade: -6
  isolated_death: -3
```

---

## 6) Output schema (Codex-friendly, parseable)

### 6.1 `events.jsonl` (combat + objectives)
Each line:
```json
{
  "t": 123.45,
  "type": "damage|kill|weapon_fire|objective",
  "attacker": 3,
  "victim": 7,
  "killer": 3,
  "weapon": "MP40",
  "mod": "MOD_MP40",
  "dmg": 18,
  "map": "radar",
  "round_id": "m2026-02-07_r1"
}
```

### 6.2 `snapshots.jsonl` (position samples)
```json
{
  "t": 123.00,
  "client": 3,
  "team": "AXIS|ALLIES|SPEC",
  "alive": true,
  "pos": [x, y, z],
  "vel": [vx, vy, vz],
  "yaw": 123.4,
  "pitch": -5.0,
  "round_id": "..."
}
```

### 6.3 `trade_events.jsonl`
```json
{
  "t_death": 456.78,
  "victim": 7,
  "killer": 2,
  "team_of_victim": "ALLIES",
  "opportunities": [
    {"client": 3, "dist": 520, "confidence": "high"},
    {"client": 5, "dist": 910, "confidence": "low"}
  ],
  "attempts": [{"client": 3, "t": 458.01, "dmg": 12}],
  "successes": [{"client": 3, "t": 458.44}],
  "missed_candidates": [{"client": 5, "reason": "far_or_objective"}]
}
```

### 6.4 `score_round_player.jsonl`
```json
{
  "round_id": "...",
  "client": 3,
  "alive_time_s": 92.3,
  "score_total": 14.7,
  "components": {
    "readiness": 6.2,
    "crossfire": 1.5,
    "trade_attempt": 3,
    "trade_success": 8,
    "missed_trade": -4
  },
  "negatives": [
    {"type": "missed_trade", "confidence": "high", "t": 456.78, "victim": 7, "killer": 2}
  ]
}
```


## 6.5 Code-level bugfixes & refactors (apply while adding features)

> These are **implementation correctness** items to do in parallel with the feature work. They prevent bad data (the worst kind of analytics bug).

### A) Correctness bugs (high priority)

1. **Fix enemy vs teammate filtering**
   - Ensure any function named `getNearbyEnemies(...)` (or any variable named `nearby_enemies`) returns **only opposite-team players**.
   - If you want a mixed list for UI/debug, rename it to `nearby_players` and keep explicit filters (`is_teammate`) downstream.
   - **Why it matters:** trade/crossfire/bait logic becomes wrong if “enemies” includes teammates.

2. **Avoid duplicate callback definitions**
   - Do not define `et_RunFrame` (or other callbacks) more than once.
   - If you “wrap” a previous function, call the original inside your wrapper.
   - **Why it matters:** silent overrides = missing features and missing logs.

3. **Fix circular buffer export**
   - Do **not** export a ring buffer using `ipairs()`; it may stop early on nil gaps and/or export out-of-order.
   - Export with deterministic indexing (`for i=1,max do ... end`) or maintain an ordered list of snapshot IDs/timestamps.
   - **Why it matters:** you’ll silently drop snapshot history and skew spacing/heatmaps.

4. **Flush output on lifecycle boundaries**
   - Flush and close files on:
     - intermission / end-of-round
     - `et_ShutdownGame(restart)` (always flush here)
   - Assume Lua state can be reset on `map_restart` / map change; persist what you need to disk/cvars.
   - **Why it matters:** competitive matches often include restarts; losing data mid-map is brutal.

5. **Client validity & spectators**
   - Every time you read a client’s `ps.*` fields:
     - confirm client slot is connected
     - confirm team is not spectator (unless you intentionally track spec)
     - confirm the player is alive when needed (some `ps.origin` usage is fine even dead, but be explicit)
   - **Why it matters:** invalid reads create junk rows and false proximity spikes.

### B) Performance & data quality refactors (recommended)

6. **Don’t do heavy work per frame**
   - Keep `et_RunFrame` thin:
     - sample only at configured cadence
     - batch/queue expensive computations
   - Prefer burst sampling only during combat windows.

7. **Stable time base**
   - Use `levelTime` consistently (ms), and convert once on export if desired.
   - Store `t_ms` internally to avoid float drift.

8. **Structured logs**
   - Export JSON Lines (`.jsonl`) for events/snapshots/trades/scores.
   - Keep each line self-contained (no embedded Lua tables in TSV).

9. **Version everything**
   - Add:
     - `schema_version`
     - `score_model_version`
     - `script_git_sha` (optional)
   - **Why it matters:** you’ll iterate thresholds and need reproducible comparisons.

10. **Map-/league-specific config**
   - Support per-map overrides for:
     - `trade_dist`, `support_dist`, `objective_grace_s`, `objective_zones`
   - **Why it matters:** ET maps vary hugely in scale/geometry.

### C) “Stopwatch anti-false-bait” implementation gates (must-do before penalties)

11. **Penalty confidence tiers**
   - Default all negatives to `candidate` unless confidence is **high**.
   - Confidence should increase only when:
     - opportunity was close (distance + time)
     - no objective exception
     - player had LOS/heading plausibility (even coarse)
     - player survived long enough to react

12. **Objective & “planned lurk” suppression**
   - Maintain a rolling `role_context` per player:
     - `last_objective_action_t`
     - `in_objective_zone`
     - `recent_route_zone` (flank/route heuristics)
   - Suppress/reduce missed-trade penalties when the context suggests a legit strat play.

---



---

## 7) Acceptance criteria (what “good” looks like)

- Trade events correctly classify **opp/attempt/success** consistent with glossary. citeturn0search4turn0search14
- False baiting is minimized:
  - objective-role plays rarely produce `high` confidence penalties
  - most negatives start as `candidate` with explainable reasons
- Outputs are stable and easy to parse for Python pipelines.

---

## 8) Implementation notes (practical)

- Start by logging **candidates** (no penalties), review with the team, then enable scoring.
- Treat every threshold as a **per-map tuneable** (ET maps have very different scale and choke geometry).
- Keep the scoring system versioned: `score_model_version: v1.0.0`.

---

## 9) Next actions checklist

1. Implement trade framework + trade events export
2. Add objective context hooks (even partial)
3. Add confidence tiers + candidate-only negatives
4. Add scoring + per-round summaries
5. Tune thresholds on 3–5 matches, then lock v1


---

## 10) Reference links (for devs)

```text
ET:Legacy Lua API (ReadTheDocs): https://etlegacy-lua-docs.readthedocs.io/en/latest/
Callbacks (sample code shows et_RunFrame / et_InitGame): https://etlegacy-lua-docs.readthedocs.io/en/latest/sample.html
lua_apidoc callbacks.rst (Git mirror): https://github.com/etlegacy/lua_apidoc/blob/master/callbacks.rst
Note on lua reload on map_restart/map change (legacy mod manual): https://sites.google.com/site/peyoteet/enemy-territory-resources/mods/silent-mod/server-manual-0-8-2
```

