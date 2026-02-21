# Proximity Tracker v4 - Implementation Guide

## Overview

This document details the **exact code changes** needed to upgrade v3 to v4.
Focus: Systematic, merge-safe, no duplicate functions.

---

## Summary of Changes

| Category | What Changes | v3 Value | v4 Value |
|----------|--------------|----------|----------|
| Position Sampling | Interval | 2000ms | **500ms** |
| Position Sampling | Scope | During combat only | **All active players** |
| Spawn Tracking | Hook | None | **et_ClientSpawn** |
| Spawn Exit | Detection | None | **Distance from spawn pos** |
| Respawn Timing | Context | None | **Wave calculation** |
| Round Context | Score/Time | None | **Captured at engagement** |

---

## v3 Lua Structure (What Exists)

```text
proximity_tracker.lua (641 lines)
├── config (lines 21-41)
├── tracker state (lines 44-67)
├── Utility Functions (lines 69-129)
│   ├── getPlayerPos()
│   ├── getPlayerGUID()
│   ├── getPlayerName()
│   ├── getPlayerTeam()
│   ├── isPlayerActive()
│   ├── distance3D()
│   ├── round()
│   ├── getGridKey()
│   └── gameTime()
├── Engagement Management (lines 131-353)
│   ├── createEngagement()
│   ├── recordHit()
│   ├── detectCrossfire()
│   └── closeEngagement()
├── Escape Detection (lines 355-393)
│   └── checkEscapes()
├── File Output (lines 395-538)
│   ├── serializeAttackers()
│   ├── serializePositions()
│   └── outputData()
└── Engine Callbacks (lines 540-637)
    ├── et_InitGame()
    ├── et_RunFrame()
    ├── et_Damage()
    └── et_Obituary()
```yaml

---

## Change #1: Config Updates

**Location:** Lines 21-41

**What to change:**

```lua
-- OLD (v3)
position_sample_interval = 2000, -- sample every 2 seconds during engagement

-- NEW (v4)
position_sample_interval = 500,       -- 2 samples per second (all players)
precombat_sample_interval = 500,      -- pre-combat sampling rate
spawn_exit_distance = 400,            -- units from spawn to count as "exited"
```text

**Full v4 config block:**

```lua
local config = {
    enabled = true,
    debug = false,
    output_dir = "gamestats/",

    -- Crossfire detection
    crossfire_window_ms = 1000,     -- 1 second for crossfire detection

    -- Escape detection
    escape_time_ms = 5000,          -- 5 seconds no damage
    escape_distance = 300,          -- 300 units minimum travel

    -- Position sampling (CHANGED in v4)
    position_sample_interval = 500,  -- 2 samples per second (was 2000ms)
    precombat_sample_interval = 500, -- NEW: pre-combat sampling

    -- Spawn tracking (NEW in v4)
    spawn_exit_distance = 400,       -- distance from spawn_pos to count as "exited"

    -- Heatmap
    grid_size = 512,

    -- Minimum damage to count
    min_damage = 1
}
```yaml

---

## Change #2: Tracker State Additions

**Location:** Lines 44-67

**Add new state fields:**

```lua
local tracker = {
    -- EXISTING (keep all)
    engagements = {},
    completed = {},
    kill_heatmap = {},
    movement_heatmap = {},
    round = {
        map_name = "",
        round_num = 0,
        start_time = 0
    },
    engagement_counter = 0,
    last_positions = {},

    -- NEW in v4: Player journeys (spawn to combat/death)
    player_journeys = {},  -- clientnum -> journey data

    -- NEW in v4: Global position snapshots (1-second sampling)
    position_snapshots = {},  -- For aggregate heatmap data
    last_global_sample = 0,

    -- NEW in v4: Spawn wave tracking
    spawn_waves = {
        AXIS = { wave_time = 30000, last_spawn = 0 },
        ALLIES = { wave_time = 30000, last_spawn = 0 }
    }
}
```yaml

---

## Change #3: New Utility Functions

**Location:** After line 129 (after `gameTime()`)

**Add these new functions:**

```lua
-- ===== NEW v4 UTILITY FUNCTIONS =====

local function distance2D(pos1, pos2)
    if not pos1 or not pos2 then return 9999 end
    local dx = pos1.x - pos2.x
    local dy = pos1.y - pos2.y
    return math.sqrt(dx*dx + dy*dy)
end

local function getPlayerHealth(clientnum)
    return tonumber(et.gentity_get(clientnum, "health")) or 0
end

local function getPlayerClass(clientnum)
    local class = et.gentity_get(clientnum, "sess.playerType")
    local classes = { [0] = "SOLDIER", [1] = "MEDIC", [2] = "ENGINEER", [3] = "FIELDOPS", [4] = "COVERTOPS" }
    return classes[class] or "UNKNOWN"
end

-- Get spawn wave timing for a team
local function getSpawnWaveInfo(team)
    local now = gameTime()

    -- Read from game cvars
    local wave_time
    if team == "AXIS" then
        wave_time = tonumber(et.trap_Cvar_Get("g_redlimbotime")) or 30000
    else
        wave_time = tonumber(et.trap_Cvar_Get("g_bluelimbotime")) or 30000
    end

    -- Calculate wave timing
    local waves_elapsed = math.floor(now / wave_time)
    local last_wave = waves_elapsed * wave_time
    local next_wave = (waves_elapsed + 1) * wave_time
    local time_until = next_wave - now

    return {
        wave_time = wave_time,
        last_spawn = last_wave,
        next_spawn = next_wave,
        time_until = time_until
    }
end

-- Get respawn context (our team vs enemy)
local function getRespawnContext(player_team)
    local our_team = player_team
    local enemy_team = (our_team == "AXIS") and "ALLIES" or "AXIS"

    local our_wave = getSpawnWaveInfo(our_team)
    local enemy_wave = getSpawnWaveInfo(enemy_team)

    return {
        our_respawn_time = our_wave.time_until,
        enemy_respawn_time = enemy_wave.time_until,
        respawn_advantage = enemy_wave.time_until - our_wave.time_until,
        our_wave_time = our_wave.wave_time,
        enemy_wave_time = enemy_wave.wave_time
    }
end

-- Get round context (score, time remaining, objective)
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
        axis_score = axis_score,
        allies_score = allies_score
    }
end
```yaml

---

## Change #4: New Spawn Tracking System

**Location:** After new utility functions (new section)

**Add spawn journey management:**

```lua
-- ===== SPAWN JOURNEY TRACKING (NEW in v4) =====

local function createJourney(clientnum)
    local now = gameTime()
    local pos = getPlayerPos(clientnum)
    local guid = getPlayerGUID(clientnum)

    local journey = {
        guid = guid,
        name = getPlayerName(clientnum),
        team = getPlayerTeam(clientnum),
        class = getPlayerClass(clientnum),

        -- Spawn data
        spawn_time = now,
        spawn_pos = pos,

        -- Spawn exit tracking
        left_spawn = false,
        spawn_exit_time = nil,
        spawn_exit_pos = nil,
        time_in_spawn = nil,

        -- Movement tracking
        path_from_spawn = {},
        distance_traveled = 0,
        last_sample_pos = pos,
        last_sample_time = now,

        -- Combat state
        first_damage_time = nil,
        in_combat = false
    }

    -- Record spawn position
    if pos then
        table.insert(journey.path_from_spawn, {
            time = now,
            x = round(pos.x, 1),
            y = round(pos.y, 1),
            z = round(pos.z, 1),
            event = "spawn"
        })
    end

    tracker.player_journeys[clientnum] = journey

    if config.debug then
        et.G_Printf("[PROX] Journey started: %s (spawn at %.0f,%.0f)\n",
            journey.name, pos and pos.x or 0, pos and pos.y or 0)
    end

    return journey
end

local function checkSpawnExit(clientnum, journey)
    if journey.left_spawn then return end
    if not journey.spawn_pos then return end

    local pos = getPlayerPos(clientnum)
    if not pos then return end

    -- Check distance from spawn position
    local dist = distance2D(pos, journey.spawn_pos)

    if dist >= config.spawn_exit_distance then
        local now = gameTime()

        journey.left_spawn = true
        journey.spawn_exit_time = now
        journey.spawn_exit_pos = pos
        journey.time_in_spawn = now - journey.spawn_time

        -- Record exit in path
        table.insert(journey.path_from_spawn, {
            time = now,
            x = round(pos.x, 1),
            y = round(pos.y, 1),
            z = round(pos.z, 1),
            event = "spawn_exit"
        })

        if config.debug then
            et.G_Printf("[PROX] %s exited spawn after %dms\n",
                journey.name, journey.time_in_spawn)
        end
    end
end

local function updateJourneyPosition(clientnum, journey)
    local now = gameTime()
    local pos = getPlayerPos(clientnum)
    if not pos then return end

    -- Check if enough time passed for sample
    if now - journey.last_sample_time >= config.precombat_sample_interval then
        -- Update distance traveled
        if journey.last_sample_pos then
            journey.distance_traveled = journey.distance_traveled +
                distance3D(pos, journey.last_sample_pos)
        end

        -- Record position sample
        table.insert(journey.path_from_spawn, {
            time = now,
            x = round(pos.x, 1),
            y = round(pos.y, 1),
            z = round(pos.z, 1),
            event = "sample"
        })

        journey.last_sample_pos = pos
        journey.last_sample_time = now

        -- Update global movement heatmap
        local key = getGridKey(pos.x, pos.y)
        if not tracker.movement_heatmap[key] then
            tracker.movement_heatmap[key] = { traversal = 0, combat = 0, escape = 0 }
        end
        tracker.movement_heatmap[key].traversal = tracker.movement_heatmap[key].traversal + 1
    end
end

local function endJourney(clientnum)
    tracker.player_journeys[clientnum] = nil
end
```yaml

---

## Change #5: Modify createEngagement()

**Location:** Lines 133-184

**What to change:** Add journey data and respawn context to engagement

**Replace the function with:**

```lua
local function createEngagement(target_slot)
    tracker.engagement_counter = tracker.engagement_counter + 1

    local pos = getPlayerPos(target_slot)
    local now = gameTime()
    local team = getPlayerTeam(target_slot)

    -- Get journey data if exists
    local journey = tracker.player_journeys[target_slot]

    -- Get tactical context
    local respawn_ctx = getRespawnContext(team)
    local round_ctx = getRoundContext()

    -- Calculate scores from player's perspective
    local our_score, enemy_score
    if team == "AXIS" then
        our_score = round_ctx.axis_score
        enemy_score = round_ctx.allies_score
    else
        our_score = round_ctx.allies_score
        enemy_score = round_ctx.axis_score
    end

    local engagement = {
        id = tracker.engagement_counter,
        target_slot = target_slot,
        target_guid = getPlayerGUID(target_slot),
        target_name = getPlayerName(target_slot),
        target_team = team,
        target_class = getPlayerClass(target_slot),

        start_time = now,
        last_hit_time = now,
        last_sample_time = now,

        -- Position tracking
        start_pos = pos,
        last_hit_pos = pos,
        position_path = {},
        distance_traveled = 0,

        -- Attackers: attacker_guid -> {name, team, damage, hits, first_hit, last_hit, weapons}
        attackers = {},
        attacker_order = {},  -- ordered list of attacker GUIDs by first hit time

        total_damage = 0,
        outcome = nil,
        killer_guid = nil,
        killer_name = nil,

        -- NEW v4: Journey data (if available)
        spawn_time = journey and journey.spawn_time or nil,
        spawn_pos = journey and journey.spawn_pos or nil,
        spawn_exit_time = journey and journey.spawn_exit_time or nil,
        spawn_exit_pos = journey and journey.spawn_exit_pos or nil,
        time_in_spawn = journey and journey.time_in_spawn or nil,
        path_from_spawn = journey and journey.path_from_spawn or nil,
        distance_before_combat = journey and journey.distance_traveled or nil,
        time_alive_before_combat = journey and (now - journey.spawn_time) or nil,

        -- NEW v4: Respawn context
        our_respawn_time = respawn_ctx.our_respawn_time,
        enemy_respawn_time = respawn_ctx.enemy_respawn_time,
        respawn_advantage = respawn_ctx.respawn_advantage,

        -- NEW v4: Round context
        round_time_elapsed = round_ctx.round_time_elapsed,
        round_time_remaining = round_ctx.round_time_remaining,
        our_score = our_score,
        enemy_score = enemy_score,

        -- NEW v4: Combat initiation
        initial_health = getPlayerHealth(target_slot)
    }

    -- Record starting position
    if pos then
        table.insert(engagement.position_path, {
            time = now,
            x = round(pos.x, 1),
            y = round(pos.y, 1),
            z = round(pos.z, 1),
            event = "start"
        })
    end

    -- Mark journey as in-combat
    if journey then
        journey.in_combat = true
        journey.first_damage_time = now
    end

    tracker.engagements[target_slot] = engagement

    if config.debug then
        et.G_Printf("[PROX] Engagement #%d started: %s (respawn adv: %dms)\n",
            engagement.id, engagement.target_name, respawn_ctx.respawn_advantage)
    end

    return engagement
end
```yaml

---

## Change #6: Add et_ClientSpawn Callback

**Location:** After `et_Obituary()` (before module end)

**Add new callback:**

```lua
function et_ClientSpawn(clientnum, revived)
    if not config.enabled then return end

    -- Only track fresh spawns, not revives
    if revived == 1 then
        if config.debug then
            et.G_Printf("[PROX] %s was revived (not tracking)\n", getPlayerName(clientnum))
        end
        return
    end

    -- Check if player is on a team
    if not isPlayerActive(clientnum) then return end

    -- Create new journey for this player
    createJourney(clientnum)
end
```yaml

---

## Change #7: Modify et_RunFrame

**Location:** Lines 564-584

**What to change:** Add pre-combat position sampling for ALL players

**Replace with:**

```lua
local last_gamestate = -1

function et_RunFrame(levelTime)
    if not config.enabled then return end

    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    local now = gameTime()

    -- Check for round end
    if last_gamestate == 0 and gamestate == 3 then
        -- Close all active engagements as round_end
        for target_slot, engagement in pairs(tracker.engagements) do
            closeEngagement(engagement, "round_end", nil)
        end

        -- Clear all journeys
        tracker.player_journeys = {}

        outputData()
    end

    last_gamestate = gamestate

    -- During play: process all tracking
    if gamestate == 0 then
        -- 1. Check for escapes (existing)
        checkEscapes(levelTime)

        -- 2. NEW v4: Update pre-combat journeys
        for slot, journey in pairs(tracker.player_journeys) do
            -- Skip if player is in combat
            if tracker.engagements[slot] then
                goto continue
            end

            -- Check if player is still active
            if not isPlayerActive(slot) then
                endJourney(slot)
                goto continue
            end

            -- Check spawn exit
            checkSpawnExit(slot, journey)

            -- Sample position
            updateJourneyPosition(slot, journey)

            ::continue::
        end
    end
end
```sql

---

## Change #8: Modify checkEscapes

**Location:** Lines 357-393

**What to change:** Update position sampling interval from 2000 to 1000

**In checkEscapes(), line 378:**

```lua
-- OLD (v3)
if time_since_sample >= config.position_sample_interval then

-- NEW (v4) - already uses config.position_sample_interval,
-- just ensure config is updated to 1000
```sql

No code change needed here if config is updated.

---

## Change #9: Update Output Format

**Location:** Lines 428-538 (outputData function)

**What to change:** Add new fields to output

**Update header (line 448-460):**

```lua
local header = string.format(
    "# PROXIMITY_TRACKER_V4\n" ..
    "# map=%s\n" ..
    "# round=%d\n" ..
    "# crossfire_window=%d\n" ..
    "# escape_time=%d\n" ..
    "# escape_distance=%d\n" ..
    "# position_sample_interval=%d\n" ..
    "# axis_spawn_wave=%d\n" ..
    "# allies_spawn_wave=%d\n",
    tracker.round.map_name,
    tracker.round.round_num,
    config.crossfire_window_ms,
    config.escape_time_ms,
    config.escape_distance,
    config.position_sample_interval,
    getSpawnWaveInfo("AXIS").wave_time,
    getSpawnWaveInfo("ALLIES").wave_time
)
```sql

**Update engagement format (new columns):**

```lua
-- Add these to the engagement line format (after existing fields)
-- spawn_time;spawn_exit_time;time_in_spawn;distance_before_combat;
-- our_respawn;enemy_respawn;respawn_advantage;
-- round_elapsed;round_remaining;our_score;enemy_score;
-- initial_health;path_from_spawn

local line = string.format(
    "%d;%d;%d;%d;%s;%s;%s;%s;%d;%s;%s;%d;%s;%s;%s;" ..
    "%.1f;%.1f;%.1f;%.1f;%.1f;%.1f;%.1f;%s;%s;" ..
    -- NEW v4 fields:
    "%s;%s;%s;%.1f;" ..    -- spawn_time, spawn_exit_time, time_in_spawn, distance_before_combat
    "%d;%d;%d;" ..          -- our_respawn, enemy_respawn, respawn_advantage
    "%d;%d;%d;%d;" ..       -- round_elapsed, round_remaining, our_score, enemy_score
    "%d;%s\n",              -- initial_health, path_from_spawn

    -- existing fields...
    eng.id,
    eng.start_time,
    eng.end_time or 0,
    eng.duration or 0,
    -- ... (all existing fields)

    -- NEW v4 fields:
    eng.spawn_time or "",
    eng.spawn_exit_time or "",
    eng.time_in_spawn or "",
    eng.distance_before_combat or 0,
    eng.our_respawn_time or 0,
    eng.enemy_respawn_time or 0,
    eng.respawn_advantage or 0,
    eng.round_time_elapsed or 0,
    eng.round_time_remaining or 0,
    eng.our_score or 0,
    eng.enemy_score or 0,
    eng.initial_health or 100,
    eng.path_from_spawn and serializePositions(eng.path_from_spawn) or ""
)
```sql

---

## Change #10: Update et_InitGame

**Location:** Lines 542-560

**Add journey reset:**

```lua
function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)

    local serverinfo = et.trap_GetConfigstring(et.CS_SERVERINFO)
    tracker.round.map_name = et.Info_ValueForKey(serverinfo, "mapname") or "unknown"
    tracker.round.round_num = tonumber(et.trap_Cvar_Get("g_currentRound")) or 1
    tracker.round.start_time = levelTime

    -- Reset all trackers
    tracker.engagements = {}
    tracker.completed = {}
    tracker.kill_heatmap = {}
    tracker.movement_heatmap = {}
    tracker.engagement_counter = 0
    tracker.last_positions = {}

    -- NEW v4: Reset journey tracking
    tracker.player_journeys = {}
    tracker.last_global_sample = 0

    -- Initialize spawn wave times
    tracker.spawn_waves.AXIS.wave_time = tonumber(et.trap_Cvar_Get("g_redlimbotime")) or 30000
    tracker.spawn_waves.ALLIES.wave_time = tonumber(et.trap_Cvar_Get("g_bluelimbotime")) or 30000

    et.G_Print(">>> Proximity Tracker v" .. version .. " initialized\n")
    et.G_Print(">>> Map: " .. tracker.round.map_name .. ", Round: " .. tracker.round.round_num .. "\n")
    et.G_Print(">>> Position sampling: " .. config.position_sample_interval .. "ms\n")
end
```

---

## Complete Change Summary

| Section | Lines Changed | Type |
|---------|---------------|------|
| Config | 21-41 | MODIFY |
| Tracker state | 44-67 | MODIFY (add fields) |
| New utility functions | After 129 | ADD |
| Spawn journey system | New section | ADD |
| createEngagement() | 133-184 | REPLACE |
| et_ClientSpawn() | New | ADD |
| et_RunFrame() | 564-584 | REPLACE |
| outputData() | 428-538 | MODIFY (add fields) |
| et_InitGame() | 542-560 | MODIFY |

---

## Testing Checklist

After implementing v4:

1. [ ] Module loads without errors
2. [ ] `et_ClientSpawn` fires on fresh spawn (not revive)
3. [ ] Journey tracks position every 1 second pre-combat
4. [ ] Spawn exit detected when player moves 400 units from spawn
5. [ ] Engagement captures journey data
6. [ ] Respawn timing calculated correctly
7. [ ] Round context (scores) captured
8. [ ] Output file includes new fields
9. [ ] Parser handles new format (update needed)
10. [ ] No duplicate functions with v3

---

## Parser Updates Needed

After Lua changes, update `proximity/parser/parser.py` to:

1. Parse new header fields (spawn wave times)
2. Parse new engagement columns
3. Parse `path_from_spawn` field
4. Store new data in database

Schema changes will also be needed - see `DESIGN_v4.md` for SQL.
