# Proximity Tracker - Gap Analysis

## Your Full Vision (What You Want)

Based on your description:

1. **Solo play analysis** - Track individual movement patterns, decision-making quality
2. **Enemy tracking** - Where enemies move, their patterns
3. **Decision review** - Did player make right or wrong decision?
4. **Respawn timing** - Seconds until enemy/our respawn (affects tactical decisions)
5. **Spawn-to-death journey** - Where players go from spawn, exit routes, where they die
6. **Improvement feedback** - Understanding if there's room to improve

---

## What Current Prototype Tracks

| Feature | Status | Details |
|---------|--------|---------|
| Combat engagements | YES | When player takes damage until death/escape |
| Crossfire detection | YES | 2+ attackers within 1 second |
| Escape detection | YES | 5s no damage + 300 units travel |
| Position during combat | YES | Sampled every 2s during engagement |
| Heatmaps | YES | Kill zones, combat zones, escape routes |
| Solo vs focused metrics | YES | 1v1 vs 2+ attacker stats |

---

## GAPS - What's Missing

### GAP 1: Respawn Timing
**Impact: CRITICAL for decision analysis**

NOT TRACKED:
- Time until enemy respawn
- Time until our respawn
- Spawn wave timing
- Reinforcement advantage/disadvantage

**Why it matters:**
- If enemy has 20s respawn and you have 5s, dying is less costly
- If enemy just spawned (30s to respawn), aggressive play is rewarded
- Good players track this mentally - we should track it too

**What we need:**
```lua
-- Track spawn waves
local team_spawn_times = {
    AXIS = { last_spawn = 0, next_spawn = 0, wave_time = 30000 },
    ALLIES = { last_spawn = 0, next_spawn = 0, wave_time = 30000 }
}

-- On death, record:
-- time_to_enemy_respawn, time_to_our_respawn, respawn_advantage
```

---

### GAP 2: Spawn-to-Death Journey (Full Movement)
**Impact: HIGH for understanding pathing**

CURRENT: Only track position DURING combat engagement (after first hit)

MISSING:
- Where player spawned
- Which exit they took from spawn
- Path from spawn to first combat
- Full journey before engagement

**Why it matters:**
- "This player always exits main and dies at tank"
- "This player flanks but gets caught at stairs"
- Spawn exit patterns reveal playstyle

**What we need:**
```lua
-- Track from spawn, not from first damage
local player_journey = {
    spawn_time = 0,
    spawn_pos = {x, y, z},
    spawn_exit = nil,  -- "main", "side", "back"
    path_to_first_combat = {},
    total_distance_before_combat = 0
}
```

---

### GAP 3: Enemy Movement Tracking
**Impact: MEDIUM for tactical analysis**

CURRENT: Only track enemies who attack YOU (attackers in engagement)

MISSING:
- Where enemies are moving (even if not attacking you)
- Enemy patrol patterns
- Common enemy positions

**Why it matters:**
- "Enemy often positions at bridge"
- "Medic usually stays back"
- Pattern prediction

**Challenge:** High data volume - tracking all player positions constantly is expensive

**Possible solution:**
```lua
-- Sample ALL player positions every 10 seconds (not every frame)
-- Store in separate "position_snapshot" table
-- Use for aggregate analysis, not real-time
```

---

### GAP 4: Decision Analysis (Right/Wrong)
**Impact: HIGH for improvement feedback**

CURRENT: We track WHAT happened, not IF it was a good decision

MISSING:
- Context of engagement (were you outnumbered?)
- Objective state (should you have pushed?)
- Team positions (were teammates nearby?)
- Outcome vs expected outcome

**Why it matters:**
- "You died but objective was planted = GOOD TRADE"
- "You survived but let bomb defuse = BAD DECISION"
- "You engaged 1v3 = BAD POSITIONING"

**What we need:**
```lua
-- Capture decision context:
local engagement_context = {
    -- Tactical state
    objective_status = "inactive|planted|defusing|destroyed",
    friendly_count_nearby = 0,
    enemy_count_nearby = 0,

    -- Was this a good time to fight?
    time_to_objective_end = 0,

    -- Result analysis
    outcome_rating = "good_trade|bad_trade|neutral"
}
```

---

### GAP 5: Pre-Engagement Awareness
**Impact: MEDIUM for decision quality**

CURRENT: Engagement starts when you take damage

MISSING:
- Did player see enemy first?
- Reaction time (first shot to first return fire)
- Who initiated combat?

**Why it matters:**
- "You got shot first 80% of the time = bad positioning"
- "Your reaction time is slow = need better awareness"

---

### GAP 6: Round/Match Context
**Impact: MEDIUM for understanding performance variance**

CURRENT: Track per-engagement, per-round

MISSING:
- Current score
- Time remaining
- Which objectives are active
- Map side (attack vs defense)

**Why it matters:**
- Performance varies by game state
- Clutch situations vs normal play
- Leading vs trailing behavior

---

## Data We CAN Get From ET:Legacy Lua

| Data | Available? | How |
|------|------------|-----|
| Player positions | YES | `et.gentity_get(slot, "ps.origin")` |
| Player health | YES | `et.gentity_get(slot, "health")` |
| Player team | YES | `et.gentity_get(slot, "sess.sessionTeam")` |
| Player class | YES | `et.gentity_get(slot, "sess.playerType")` |
| Spawn time | MAYBE | Track `et_ClientSpawn()` callback |
| Respawn wave | MAYBE | `et.trap_Cvar_Get("g_redlimbotime")` etc. |
| Objective state | MAYBE | Entity queries for objectives |
| Round time | YES | `et.trap_Cvar_Get("gamestate")` + timers |
| Score | YES | `et.trap_Cvar_Get("score")` type cvars |
| Damage events | YES | `et_Damage()` callback |
| Kill events | YES | `et_Obituary()` callback |

---

## Priority Fixes

### P0: Respawn Timing (Most impactful)
Add to Lua:
- Track spawn wave times per team
- On death, record: `time_to_respawn`, `enemy_time_to_respawn`
- Add to engagement record

### P1: Spawn Journey Tracking
Add to Lua:
- Hook `et_ClientSpawn()` to start tracking
- Sample position every 5s until first combat
- Record spawn exit zone

### P2: Round Context
Add to Lua:
- Round start time, round time limit
- Objective states at engagement time
- Current score

### P3: Enemy Position Snapshots (if performance allows)
Add to Lua:
- Every 10s, snapshot all player positions
- Aggregate into "common enemy positions" per map
- Lightweight - only position + team, no damage tracking

---

## Schema Changes Needed

```sql
-- Add to combat_engagement:
ALTER TABLE combat_engagement ADD COLUMN
    spawn_time_ms INTEGER,                    -- when player spawned
    time_since_spawn_ms INTEGER,              -- how long alive before engagement
    spawn_pos_x REAL,
    spawn_pos_y REAL,
    spawn_pos_z REAL,
    spawn_exit VARCHAR(32),                   -- "main", "side", etc.

    -- Respawn timing context
    our_respawn_time_ms INTEGER,              -- time until we respawn
    enemy_respawn_time_ms INTEGER,            -- time until enemy respawns
    respawn_advantage_ms INTEGER,             -- positive = we respawn first

    -- Round context
    round_time_remaining_ms INTEGER,
    objective_status VARCHAR(32),
    team_score INTEGER,
    enemy_score INTEGER,
    map_side VARCHAR(10);                     -- "attack" or "defense"

-- New table: position snapshots for aggregate analysis
CREATE TABLE IF NOT EXISTS position_snapshots (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    map_name VARCHAR(64) NOT NULL,
    sample_time_ms INTEGER NOT NULL,

    -- All player positions at this moment (JSONB array)
    -- [{guid, team, class, x, y, z, health}]
    positions JSONB NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Current vs Full Vision Summary

| Feature | Current | Full Vision | Gap |
|---------|---------|-------------|-----|
| Combat engagement tracking | YES | YES | - |
| Position during combat | YES | YES | - |
| Crossfire detection | YES | YES | - |
| Escape detection | YES | YES | - |
| Heatmaps | YES | YES | - |
| Solo/focused metrics | YES | YES | - |
| Respawn timing | NO | YES | **BIG GAP** |
| Spawn-to-death journey | NO | YES | **BIG GAP** |
| Enemy movement patterns | NO | YES | Medium gap |
| Decision analysis | NO | YES | Medium gap |
| Round context | NO | YES | Medium gap |
| Pre-engagement awareness | NO | YES | Small gap |

---

## Recommendation

1. **Don't deploy current prototype to production yet** - it's missing critical data
2. **Add respawn timing** - most impactful gap, not too hard
3. **Add spawn journey tracking** - high value, medium effort
4. **Test with round context** - easy to add
5. **Consider enemy snapshots** - need to test performance impact

The current prototype is a good foundation but only captures ~40% of what you described.
