# Proximity Tracker v4 - Enhanced Design Document

## Overview

Extend the current engagement-centric tracker to capture the **full player journey** from spawn to death, with tactical context for decision analysis.

---

## Core Concept: The Player Journey

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        PLAYER JOURNEY                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SPAWN ──► EXIT ──► MOVEMENT ──► CONTACT ──► COMBAT ──► OUTCOME    │
│    │         │          │           │           │           │        │
│    │         │          │           │           │           │        │
│    ▼         ▼          ▼           ▼           ▼           ▼        │
│  spawn    which      path to     first      damage     death or     │
│  time     exit?      combat     sight?     exchange    escape       │
│  pos      route      distance   who saw                             │
│           timing     duration   who first                           │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                     TACTICAL CONTEXT                                 │
├─────────────────────────────────────────────────────────────────────┤
│  • Respawn timing (ours vs enemy)                                   │
│  • Objective state (planted? defusing?)                             │
│  • Round time remaining                                             │
│  • Team positions (alone? supported?)                               │
│  • Score context (leading? trailing?)                               │
└─────────────────────────────────────────────────────────────────────┘
```sql

---

## New Data Points to Capture

### 1. Spawn Event Data

| Field | Type | Description |
|-------|------|-------------|
| `spawn_time_ms` | int | Game time when player spawned |
| `spawn_pos` | {x,y,z} | Position at spawn |
| `spawn_wave` | int | Which wave (1st, 2nd, etc) |
| `time_since_round_start` | int | How far into round |

### 2. Spawn Exit Tracking

| Field | Type | Description |
|-------|------|-------------|
| `spawn_exit_time_ms` | int | When left spawn area |
| `spawn_exit_pos` | {x,y,z} | Where exited spawn |
| `spawn_exit_zone` | string | "main", "side", "back" (map-specific) |
| `time_in_spawn_ms` | int | How long stayed in spawn |

### 3. Pre-Combat Movement

| Field | Type | Description |
|-------|------|-------------|
| `path_from_spawn` | [{time,x,y,z}] | Position samples every 5s |
| `distance_to_first_combat` | float | Total distance traveled |
| `time_to_first_combat_ms` | int | How long before taking damage |

### 4. Respawn Timing Context

| Field | Type | Description |
|-------|------|-------------|
| `our_respawn_time_ms` | int | Time until our team respawns |
| `enemy_respawn_time_ms` | int | Time until enemy respawns |
| `respawn_advantage_ms` | int | Difference (positive = we respawn first) |
| `our_spawn_wave_time` | int | Our team's wave interval |
| `enemy_spawn_wave_time` | int | Enemy team's wave interval |

### 5. Round/Match Context

| Field | Type | Description |
|-------|------|-------------|
| `round_time_elapsed_ms` | int | Time since round start |
| `round_time_remaining_ms` | int | Time until round ends |
| `objective_status` | string | "inactive", "planted", "defusing", "destroyed" |
| `our_score` | int | Our team's current score |
| `enemy_score` | int | Enemy team's current score |
| `map_side` | string | "attack" or "defense" |

### 6. Combat Initiation

| Field | Type | Description |
|-------|------|-------------|
| `first_contact_time_ms` | int | When combat started |
| `we_shot_first` | bool | Did we deal damage before taking any? |
| `reaction_time_ms` | int | Time from taking damage to dealing damage |
| `initial_health` | int | Health when combat started |

---

## Implementation Plan

### Phase 1: Lua Script Enhancements

#### 1.1 Spawn Tracking Hook

```lua
-- Track player spawns
function et_ClientSpawn(clientnum, revived)
    if revived == 0 then  -- Fresh spawn, not revive
        local now = gameTime()
        local pos = getPlayerPos(clientnum)
        local guid = getPlayerGUID(clientnum)

        tracker.player_journeys[clientnum] = {
            guid = guid,
            name = getPlayerName(clientnum),
            team = getPlayerTeam(clientnum),

            -- Spawn data
            spawn_time = now,
            spawn_pos = pos,
            spawn_wave = getCurrentSpawnWave(clientnum),

            -- Journey tracking
            left_spawn = false,
            spawn_exit_time = nil,
            spawn_exit_pos = nil,
            path_from_spawn = { {time=now, x=pos.x, y=pos.y, z=pos.z, event="spawn"} },

            -- Pre-combat state
            first_damage_time = nil,
            distance_traveled = 0,
            last_sample_pos = pos,
            last_sample_time = now
        }
    end
end
```text

#### 1.2 Spawn Area Detection

```lua
-- Define spawn areas per map (approximate)
local SPAWN_AREAS = {
    ["goldrush"] = {
        AXIS = { center = {x=-1800, y=1200, z=0}, radius = 500 },
        ALLIES = { center = {x=2800, y=-800, z=0}, radius = 500 }
    },
    ["supply"] = {
        AXIS = { center = {x=200, y=-2400, z=0}, radius = 400 },
        ALLIES = { center = {x=2200, y=1800, z=0}, radius = 400 }
    }
    -- Add more maps...
}

-- Generic spawn detection (fallback if map not defined)
local function isInSpawnArea(pos, team)
    local map = tracker.round.map_name
    local spawn_config = SPAWN_AREAS[map]

    if spawn_config and spawn_config[team] then
        local spawn = spawn_config[team]
        local dist = distance2D(pos, spawn.center)
        return dist < spawn.radius
    end

    -- Fallback: check if near spawn point entities
    return false
end

-- Detect spawn exit
local function checkSpawnExit(clientnum, journey)
    if journey.left_spawn then return end

    local pos = getPlayerPos(clientnum)
    if not isInSpawnArea(pos, journey.team) then
        journey.left_spawn = true
        journey.spawn_exit_time = gameTime()
        journey.spawn_exit_pos = pos
        journey.time_in_spawn = journey.spawn_exit_time - journey.spawn_time

        -- Record exit in path
        table.insert(journey.path_from_spawn, {
            time = journey.spawn_exit_time,
            x = pos.x, y = pos.y, z = pos.z,
            event = "spawn_exit"
        })
    end
end
```text

#### 1.3 Respawn Wave Tracking

```lua
-- Track spawn waves using game cvars
local function getSpawnWaveInfo()
    -- ET:Legacy spawn wave cvars
    local axis_time = tonumber(et.trap_Cvar_Get("g_redlimbotime")) or 30000
    local allies_time = tonumber(et.trap_Cvar_Get("g_bluelimbotime")) or 30000

    local now = gameTime()

    return {
        AXIS = {
            wave_time = axis_time,
            last_spawn = math.floor(now / axis_time) * axis_time,
            next_spawn = (math.floor(now / axis_time) + 1) * axis_time,
            time_until = (math.floor(now / axis_time) + 1) * axis_time - now
        },
        ALLIES = {
            wave_time = allies_time,
            last_spawn = math.floor(now / allies_time) * allies_time,
            next_spawn = (math.floor(now / allies_time) + 1) * allies_time,
            time_until = (math.floor(now / allies_time) + 1) * allies_time - now
        }
    }
end

-- Get respawn context at time of engagement
local function getRespawnContext(player_team)
    local waves = getSpawnWaveInfo()
    local our_team = player_team
    local enemy_team = (our_team == "AXIS") and "ALLIES" or "AXIS"

    return {
        our_respawn_time = waves[our_team].time_until,
        enemy_respawn_time = waves[enemy_team].time_until,
        respawn_advantage = waves[enemy_team].time_until - waves[our_team].time_until,
        our_wave_time = waves[our_team].wave_time,
        enemy_wave_time = waves[enemy_team].wave_time
    }
end
```text

#### 1.4 Objective State Tracking

```lua
-- Track objective status
local function getObjectiveState()
    -- Check dynamite/bomb state
    local dynamite_planted = false
    local defuse_in_progress = false

    -- Iterate entities to find objectives
    -- This is map-specific and may need adjustment
    local num_entities = et.GetNumEntities()
    for i = 0, num_entities - 1 do
        local classname = et.gentity_get(i, "classname")

        if classname == "dynamite" then
            local armed = et.gentity_get(i, "s.teamNum")
            if armed then
                dynamite_planted = true
            end
        end

        -- Check for defuse action
        -- (would need to hook into player actions)
    end

    if dynamite_planted then
        return "planted"
    end

    return "inactive"
end

-- Get round context
local function getRoundContext()
    local timelimit = tonumber(et.trap_Cvar_Get("timelimit")) or 20
    local elapsed = gameTime()
    local remaining = (timelimit * 60 * 1000) - elapsed

    -- Get scores
    local axis_score = tonumber(et.trap_Cvar_Get("g_axisScore")) or 0
    local allies_score = tonumber(et.trap_Cvar_Get("g_alliesScore")) or 0

    return {
        round_time_elapsed = elapsed,
        round_time_remaining = math.max(0, remaining),
        objective_status = getObjectiveState(),
        axis_score = axis_score,
        allies_score = allies_score
    }
end
```text

#### 1.5 Enhanced Engagement Creation

```lua
-- Update createEngagement to include journey data
local function createEngagement(target_slot)
    local journey = tracker.player_journeys[target_slot]
    local now = gameTime()
    local pos = getPlayerPos(target_slot)

    -- Get tactical context
    local respawn_ctx = getRespawnContext(journey.team)
    local round_ctx = getRoundContext()

    -- Determine scores for this player's perspective
    local our_score, enemy_score
    if journey.team == "AXIS" then
        our_score = round_ctx.axis_score
        enemy_score = round_ctx.allies_score
    else
        our_score = round_ctx.allies_score
        enemy_score = round_ctx.axis_score
    end

    local engagement = {
        -- ... existing fields ...

        -- NEW: Journey data
        spawn_time = journey.spawn_time,
        spawn_pos = journey.spawn_pos,
        spawn_exit_time = journey.spawn_exit_time,
        spawn_exit_pos = journey.spawn_exit_pos,
        time_in_spawn = journey.time_in_spawn,
        path_from_spawn = journey.path_from_spawn,
        distance_before_combat = journey.distance_traveled,
        time_alive_before_combat = now - journey.spawn_time,

        -- NEW: Respawn context
        our_respawn_time = respawn_ctx.our_respawn_time,
        enemy_respawn_time = respawn_ctx.enemy_respawn_time,
        respawn_advantage = respawn_ctx.respawn_advantage,

        -- NEW: Round context
        round_time_elapsed = round_ctx.round_time_elapsed,
        round_time_remaining = round_ctx.round_time_remaining,
        objective_status = round_ctx.objective_status,
        our_score = our_score,
        enemy_score = enemy_score,
        map_side = getMapSide(journey.team),

        -- NEW: Combat initiation
        initial_health = et.gentity_get(target_slot, "health") or 100,
        we_shot_first = false,  -- Updated when target deals damage
        first_damage_dealt_time = nil
    }

    return engagement
end
```text

#### 1.6 Pre-Combat Position Sampling

```lua
-- In et_RunFrame, sample positions for players not yet in combat
function et_RunFrame(levelTime)
    local now = gameTime()

    -- Sample pre-combat positions every 5 seconds
    local PRECOMBAT_SAMPLE_INTERVAL = 5000

    for slot, journey in pairs(tracker.player_journeys) do
        -- Skip if already in combat
        if tracker.engagements[slot] then
            goto continue
        end

        -- Check if enough time passed
        if now - journey.last_sample_time >= PRECOMBAT_SAMPLE_INTERVAL then
            local pos = getPlayerPos(slot)
            if pos then
                -- Update distance
                if journey.last_sample_pos then
                    journey.distance_traveled = journey.distance_traveled +
                        distance3D(pos, journey.last_sample_pos)
                end

                -- Record position
                table.insert(journey.path_from_spawn, {
                    time = now,
                    x = round(pos.x, 1),
                    y = round(pos.y, 1),
                    z = round(pos.z, 1),
                    event = "sample"
                })

                journey.last_sample_pos = pos
                journey.last_sample_time = now
            end
        end

        -- Check spawn exit
        checkSpawnExit(slot, journey)

        ::continue::
    end

    -- ... existing frame logic ...
end
```yaml

---

### Phase 2: Schema Updates

```sql
-- Add new columns to combat_engagement
ALTER TABLE combat_engagement ADD COLUMN IF NOT EXISTS
    -- Journey data
    spawn_time_ms INTEGER,
    spawn_pos_x REAL,
    spawn_pos_y REAL,
    spawn_pos_z REAL,
    spawn_exit_time_ms INTEGER,
    spawn_exit_pos_x REAL,
    spawn_exit_pos_y REAL,
    spawn_exit_pos_z REAL,
    time_in_spawn_ms INTEGER,
    path_from_spawn JSONB DEFAULT '[]',
    distance_before_combat REAL,
    time_alive_before_combat_ms INTEGER,

    -- Respawn context
    our_respawn_time_ms INTEGER,
    enemy_respawn_time_ms INTEGER,
    respawn_advantage_ms INTEGER,

    -- Round context
    round_time_elapsed_ms INTEGER,
    round_time_remaining_ms INTEGER,
    objective_status VARCHAR(32),
    our_score INTEGER,
    enemy_score INTEGER,
    map_side VARCHAR(16),

    -- Combat initiation
    initial_health INTEGER,
    we_shot_first BOOLEAN DEFAULT FALSE,
    reaction_time_ms INTEGER;

-- New table for spawn patterns analysis
CREATE TABLE IF NOT EXISTS spawn_patterns (
    id SERIAL PRIMARY KEY,
    player_guid VARCHAR(32) NOT NULL,
    map_name VARCHAR(64) NOT NULL,

    -- Aggregated spawn behavior
    total_spawns INTEGER DEFAULT 0,
    avg_time_in_spawn_ms REAL,
    avg_time_to_combat_ms REAL,
    avg_distance_to_combat REAL,

    -- Common exits (JSONB: {"main": 45, "side": 30, "back": 5})
    exit_distribution JSONB DEFAULT '{}',

    -- Death zones (JSONB: {"grid_x,grid_y": count})
    common_death_zones JSONB DEFAULT '{}',

    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(player_guid, map_name)
);

-- New table for decision quality tracking
CREATE TABLE IF NOT EXISTS decision_analysis (
    id SERIAL PRIMARY KEY,
    engagement_id INTEGER REFERENCES combat_engagement(id),

    -- Context scores (0-100)
    respawn_advantage_score INTEGER,  -- Higher = we had respawn advantage
    objective_pressure_score INTEGER, -- Higher = objective was at risk
    team_support_score INTEGER,       -- Higher = teammates were nearby

    -- Outcome evaluation
    trade_quality VARCHAR(20),  -- "good_trade", "bad_trade", "neutral"
    should_have_engaged BOOLEAN,
    notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```yaml

---

### Phase 3: Output File Format Changes

```sql

# METADATA

map=goldrush
round=1
crossfire_window=1000
axis_spawn_wave=30000
allies_spawn_wave=25000

# ENGAGEMENTS

# Now includes journey data

engagement_id;spawn_time;spawn_exit_time;first_damage_time;...;our_respawn;enemy_respawn;objective_status;...

# SPAWN_JOURNEYS (NEW SECTION)

# For players who died this round

guid;spawn_time;spawn_pos;spawn_exit_time;spawn_exit_zone;path_to_combat;death_pos;total_distance

# KILL_HEATMAP

grid_x;grid_y;axis_kills;allies_kills

# DEATH_HEATMAP_BY_SPAWN_EXIT (NEW)

# Where do players die based on which exit they took?

spawn_exit;grid_x;grid_y;death_count

# MOVEMENT_HEATMAP

grid_x;grid_y;traversal;combat;escape

```yaml

---

### Phase 4: New Analytics Queries

```sql
-- Find players who spend too long in spawn
SELECT
    player_guid,
    player_name,
    AVG(time_in_spawn_ms) as avg_spawn_time,
    COUNT(*) as total_deaths
FROM combat_engagement
WHERE time_in_spawn_ms IS NOT NULL
GROUP BY player_guid, player_name
HAVING AVG(time_in_spawn_ms) > 5000  -- More than 5 seconds in spawn
ORDER BY avg_spawn_time DESC;

-- Find bad trade decisions (died with respawn disadvantage)
SELECT
    target_name,
    COUNT(*) as bad_trades,
    AVG(respawn_advantage_ms) as avg_disadvantage
FROM combat_engagement
WHERE outcome = 'killed'
  AND respawn_advantage_ms < -10000  -- Enemy respawns 10s+ before us
GROUP BY target_guid, target_name
ORDER BY bad_trades DESC;

-- Spawn exit effectiveness by map
SELECT
    map_name,
    -- Would need to parse spawn_exit from path
    COUNT(CASE WHEN outcome = 'escaped' THEN 1 END) as escapes,
    COUNT(CASE WHEN outcome = 'killed' THEN 1 END) as deaths,
    AVG(time_alive_before_combat_ms) as avg_survival_time
FROM combat_engagement
GROUP BY map_name;

-- Players who engage during objective pressure (good or bad?)
SELECT
    target_name,
    objective_status,
    outcome,
    COUNT(*) as engagements
FROM combat_engagement
WHERE objective_status IN ('planted', 'defusing')
GROUP BY target_guid, target_name, objective_status, outcome;
```yaml

---

### Phase 5: Discord Commands

```python
# New commands to add

@commands.command(name='journey')
async def show_journey(self, ctx, player: str = None):
    """Show player's typical journey from spawn to death"""
    # Average time in spawn
    # Most common exit
    # Average survival time
    # Common death zones

@commands.command(name='trades')
async def show_trade_quality(self, ctx, player: str = None):
    """Analyze if player makes good or bad trades"""
    # Deaths with respawn advantage (good trades)
    # Deaths with respawn disadvantage (bad trades)
    # Objective-related trades

@commands.command(name='awareness')
async def show_awareness(self, ctx, player: str = None):
    """Show combat initiation stats"""
    # % of fights where they shot first
    # Average reaction time
    # Survival rate when caught off guard

@commands.command(name='spawn_analysis')
async def spawn_analysis(self, ctx, player: str = None, map: str = None):
    """Analyze spawn exit patterns and outcomes"""
    # Exit distribution
    # Survival rate by exit
    # Recommended exits
```

---

## Implementation Order

### Week 1: Core Lua Changes

1. [ ] Add spawn tracking (`et_ClientSpawn` hook)
2. [ ] Add spawn area detection
3. [ ] Add pre-combat position sampling
4. [ ] Add respawn wave calculation
5. [ ] Test locally

### Week 2: Context & Output

1. [ ] Add round context (score, time, objective)
2. [ ] Add combat initiation tracking
3. [ ] Update output file format
4. [ ] Update parser to handle new format
5. [ ] Test locally

### Week 3: Schema & Analytics

1. [ ] Apply schema migrations
2. [ ] Update parser to store new data
3. [ ] Create spawn_patterns aggregation
4. [ ] Write analytics queries
5. [ ] Test end-to-end

### Week 4: Discord Integration

1. [ ] Add new commands
2. [ ] Create embed designs
3. [ ] Add decision analysis logic
4. [ ] Test with community
5. [ ] Document

---

## Open Questions

1. **Spawn area detection** - Need map-specific coordinates or generic algorithm?
2. **Performance** - Will pre-combat sampling every 5s be too expensive?
3. **Objective tracking** - How reliably can we detect plant/defuse state?
4. **Map side detection** - How to determine if team is attacking/defending?
5. **Historical data** - What to do with engagements collected before v4?

---

## Success Metrics

After v4 implementation, we should be able to answer:

- "Player X spends 8 seconds in spawn on average" (too slow?)
- "Player X dies at bridge 60% of the time after taking main exit"
- "Player X makes bad trades - dies with 15s respawn disadvantage"
- "Player X engages during bomb plant but dies (good sacrifice or bad?)"
- "Player X has 200ms reaction time when caught off guard"
