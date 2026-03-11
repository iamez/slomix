-- ============================================================
-- PROXIMITY TRACKER v5.0 - TEAMPLAY ANALYTICS
-- ET:Legacy Lua Module for Combat & Team Coordination Analytics
--
-- KEY FEATURES (v4 inherited):
--   * FULL PLAYER TRACKING - All players, spawn to death
--   * Position + velocity + health + weapon every 200ms
--   * Stance tracking (standing/crouching/prone)
--   * Sprint detection
--   * First movement time after spawn
--   * Combat engagement tracking (damage, kills, escapes)
--   * Crossfire detection (2+ attackers within 1 second)
--   * Per-map heatmaps (kills, movement, combat, escapes)
--   * GUID tracking for forever stats
--   * Reaction metrics (return fire, dodge, support)
--   * Objective focus tracking
--   * Test mode with lifecycle logs
--
-- NEW IN v5.0 (TEAMPLAY):
--   * SPAWN WAVE TRACKING - Team spawn intervals, kill timing scores
--   * TEAM COHESION - Centroid, dispersion, buddy pairs, stragglers
--   * CROSSFIRE OPPORTUNITIES - LOS-based crossfire detection with
--     angular separation scoring + missed opportunity tracking
--   * FOCUS FIRE - Multiple teammates engaging same target analysis
--   * TEAM PUSH DETECTION - Coordinated movement toward objectives
--   * TRADE KILLS - Teammate avenges your death within time window
--
-- COMPETITIVE ET CONTEXT:
--   In Stopwatch mode, spawn times are fixed per-team (e.g. 20s/30s).
--   Killing an enemy right AFTER their spawn wave = max respawn wait.
--   Moving as a unit, crossfiring, and timing attacks to spawn waves
--   are the pillars of competitive ET teamplay.
--
-- OUTPUT: Single file per round with all v4 sections PLUS:
--   - SPAWN_TIMING: Kill timing relative to enemy spawn waves
--   - TEAM_COHESION: Time-series of team formation metrics
--   - CROSSFIRE_OPPORTUNITIES: LOS-based crossfire analysis
--   - FOCUS_FIRE: Multi-attacker coordination on same target
--   - TEAM_PUSHES: Coordinated team movement events
--   - TRADE_KILLS: Revenge/trade kill detection
--
-- LOAD ORDER: lua_modules "c0rnp0rn.lua proximity_tracker.lua"
-- ============================================================

local modname = "proximity_tracker"
local version = "5.0"

-- ===== CONFIGURATION =====
local config = {
    enabled = true,
    debug = false,
    output_dir = "proximity/",
    output_delay_ms = 0,
    max_string_length = 256,
    log_in_intermission = false,
    output_guard = true,

    -- Crossfire detection (v3 legacy - per-engagement)
    crossfire_window_ms = 1000,

    -- Escape detection
    escape_time_ms = 5000,
    escape_distance = 300,

    -- Position sampling
    position_sample_interval = 200,

    -- Heatmap
    grid_size = 512,

    -- Minimum damage to count
    min_damage = 1,

    -- Combat reaction tracking (Tier-B)
    reaction_window_ms = 5000,
    dodge_angle_threshold_deg = 45,
    dodge_min_step_units = 24,

    -- Objective tracking
    objective_tracking = true,
    objective_radius = 500,
    objectives = {
        Karsiah_te2 = {},
        adlernest = {},
        battery = {},
        braundorf_b4 = {},
        bremen_b2 = {},
        bremen_b3 = {
            { name = "truck_escape", x = -3143, y = -589, z = 128, type = "escort" },
        },
        default = {},
        dubrovnik_final = {},
        erdenberg_t1 = {},
        erdenberg_t2 = {},
        et_beach = {},
        et_ice = {},
        et_ufo_final = {},
        etl_adlernest = {},
        etl_frostbite = {},
        etl_ice = {},
        etl_sp_delivery = {},
        etl_supply = {
            { name = "crane_controls", x = 656, y = -1360, z = 372, type = "misc" },
            { name = "truck_escape", x = 2720, y = 1376, z = 192, type = "escort" },
        },
        frostbite = {},
        fueldump = {},
        goldrush = {},
        karsiah_te2 = {},
        mp_sillyctf = {},
        mp_sub_rc1 = {},
        oasis = {},
        pha_chateau = {},
        radar = {},
        railgun = {},
        reactor_final = {},
        sp_delivery_te = {},
        supply = {
            { name = "crane_controls", x = 656, y = -1360, z = 372, type = "misc" },
            { name = "truck_escape", x = 2720, y = 1376, z = 192, type = "escort" },
        },
        supplydepot2 = {},
        sw_battery = {},
        sw_goldrush_te = {
            { name = "tank_breakout", x = 1860, y = -80, z = -96, type = "escort" },
            { name = "truck_escape", x = -3310, y = -1060, z = -31, type = "escort" },
        },
        sw_oasis_b3 = {},
        tc_base = {},
        te_escape2 = {},
        the_station = {},
        warbell = {},
        wolken1_b1 = {},
    },

    -- Test mode (v4.1)
    test_mode = {
        enabled = false,
        lifecycle_log = true,
        action_annotations = true,
    },

    -- ===== FEATURE FLAGS =====
    features = {
        -- v4 features
        engagement_tracking = true,
        crossfire_detection = true,
        escape_detection = true,
        heatmap_generation = true,
        reaction_tracking = true,
        -- v5 teamplay features
        spawn_timing = true,
        team_cohesion = true,
        crossfire_opportunities = true,
        focus_fire = true,
        team_push_detection = true,
        trade_kills = true,
    },

    -- ===== v5 TEAMPLAY CONFIG =====
    teamplay = {
        -- Team cohesion analysis interval
        cohesion_interval_ms = 500,

        -- Crossfire opportunity analysis interval
        crossfire_opp_interval_ms = 1000,

        -- Team push detection interval
        push_interval_ms = 1000,

        -- Straggler distance threshold (units from team centroid)
        straggler_distance = 800,

        -- Crossfire angular separation threshold (degrees)
        crossfire_min_angle = 45,

        -- LOS check max range (skip enemies further than this)
        los_max_range = 2000,

        -- Trade kill window (ms after teammate death)
        trade_kill_window_ms = 3000,

        -- Push detection: minimum team speed to consider a push
        push_min_speed = 80,

        -- Push detection: minimum alignment score (0-1)
        push_min_alignment = 0.4,

        -- Minimum alive players per team to run team analytics
        min_team_size = 2,

        -- Crossfire opportunity execution window (ms)
        crossfire_execute_window_ms = 2000,

        -- Focus fire: minimum teammates engaging same target
        focus_fire_min_attackers = 2,
    },
}

-- ===== FEATURE FLAG HELPERS =====
local function isFeatureEnabled(feature_name)
    if config.test_mode.enabled then
        return false
    end
    return config.features[feature_name]
end

local function logObjectiveConfigSummary()
    if not config.objective_tracking then return end
    local total_maps, maps_with_coords, total_objectives = 0, 0, 0
    local missing = {}
    for map_name, objectives in pairs(config.objectives or {}) do
        total_maps = total_maps + 1
        local has_coords = false
        if type(objectives) == "table" then
            for _, obj in ipairs(objectives) do
                if type(obj) == "table" and obj.x ~= nil and obj.y ~= nil and obj.z ~= nil then
                    total_objectives = total_objectives + 1
                    has_coords = true
                end
            end
        end
        if has_coords then maps_with_coords = maps_with_coords + 1
        else table.insert(missing, map_name) end
    end
    et.G_Print(string.format(">>> Objective coords: %d/%d maps configured (%d objectives)\n",
        maps_with_coords, total_maps, total_objectives))
    if #missing > 0 then
        table.sort(missing)
        local preview = {}
        for i = 1, math.min(#missing, 10) do table.insert(preview, missing[i]) end
        local suffix = (#missing > 10) and string.format(" (+%d more)", #missing - 10) or ""
        et.G_Print(">>> Objective coords missing: " .. table.concat(preview, ", ") .. suffix .. "\n")
    end
end

-- ===== SAFE ENTITY ACCESS =====
local last_gentity_error_time = 0

local function safe_gentity_get(clientnum, field, index)
    local ok, value
    if index ~= nil then
        ok, value = pcall(et.gentity_get, clientnum, field, index)
    else
        ok, value = pcall(et.gentity_get, clientnum, field)
    end
    if ok then return value end
    local now = (et.trap_Milliseconds and et.trap_Milliseconds()) or (os.time() * 1000)
    if now - last_gentity_error_time > 5000 then
        local idx = index ~= nil and ("[" .. tostring(index) .. "]") or ""
        et.G_Print(string.format("[proximity] gentity_get failed client=%d field=%s%s err=%s\n",
            clientnum, field, idx, tostring(value)))
        last_gentity_error_time = now
    end
    return nil
end

local function get_max_clients()
    local max_clients = tonumber(et.trap_Cvar_Get("sv_maxclients")) or 0
    if max_clients <= 0 or max_clients > 64 then max_clients = 64 end
    return max_clients
end

local function isValidClient(clientnum)
    if type(clientnum) ~= "number" then return false end
    return clientnum >= 0 and clientnum < get_max_clients()
end

-- ===== MOVEMENT STATE BIT FLAGS =====
local PMF_DUCKED = 1
local PMF_PRONE = 512
local PMF_SPRINT = 16384
local STAT_SPRINTTIME = 8
local STAMINA_DELTA_SPRINT_THRESHOLD = 50
local MIN_SPRINT_SPEED = 140

-- ===== GAMESTATE CONSTANTS =====
local GS_INTERMISSION = et.GS_INTERMISSION or 3

-- ===== BIT OPERATIONS =====
local bit = nil
if _G.bit then bit = _G.bit
elseif _G.bit32 then bit = _G.bit32
else
    local ok, lib = pcall(require, "bit")
    if ok then bit = lib end
end

local function has_flag(value, flag)
    if bit and bit.band then return bit.band(value, flag) ~= 0 end
    return math.floor(value / flag) % 2 == 1
end

-- ===== MODULE DATA =====
local tracker = {
    -- v4 data
    engagements = {},
    completed = {},
    reaction_metrics = {},
    kill_heatmap = {},
    movement_heatmap = {},
    objective_stats = {},
    round = { map_name = "", round_num = 0, start_time = 0 },
    engagement_counter = 0,
    last_positions = {},
    player_tracks = {},
    completed_tracks = {},
    last_sample_time = 0,
    last_stamina = {},
    action_buffer = {},
    output_in_progress = false,
    output_written = false,
    output_pending = false,
    output_due_ms = 0,

    -- ===== v5 TEAMPLAY DATA =====
    -- Spawn wave tracking
    spawn = {
        axis_interval = 0,      -- ms from cvar
        allies_interval = 0,    -- ms from cvar
        -- Kill timing records
        kill_timings = {},       -- array of {killer_guid, victim_guid, kill_time, enemy_interval, time_to_next, score}
    },

    -- Team cohesion time series
    cohesion = {
        samples = {},           -- array of {time, team, alive, cx, cy, dispersion, max_spread, stragglers, buddy_guids, buddy_dist}
        last_check_time = 0,
    },

    -- Crossfire opportunities
    crossfire_opps = {
        events = {},            -- array of {time, target_guid, target_name, target_team, t1_guid, t2_guid, angle, executed, damage}
        last_check_time = 0,
        -- Pending opportunities awaiting execution check
        pending = {},           -- array of {expire_time, target_slot, t1_slot, t2_slot, t1_guid, t2_guid, target_guid, target_name, target_team, angle}
    },

    -- Focus fire events
    focus_fire = {
        events = {},            -- array of {engagement_id, target_guid, target_name, attacker_count, attacker_guids, total_damage, duration, focus_score}
    },

    -- Team push events
    pushes = {
        events = {},            -- array of {start_time, end_time, team, avg_speed, dir_x, dir_y, alignment, quality, participants, toward_obj}
        active = {},            -- team -> {start_time, team, ...} or nil
        last_check_time = 0,
    },

    -- Trade kills
    trade_kills = {
        events = {},            -- array of {orig_time, trade_time, delta, orig_victim_guid, orig_killer_guid, trader_guid, trader_name}
        recent_kills = {},      -- ring buffer of recent kills for trade detection
    },
}

local round_start_unix = 0
local round_end_unix = 0
local client_cache = {}

-- ===== UTILITY FUNCTIONS =====

local function getPlayerPos(clientnum)
    local origin = safe_gentity_get(clientnum, "ps.origin")
    if not origin then return nil end
    return {
        x = tonumber(origin[1]) or 0,
        y = tonumber(origin[2]) or 0,
        z = tonumber(origin[3]) or 0
    }
end

local function getPlayerGUID(clientnum)
    if not isValidClient(clientnum) then
        return string.format("WORLD_%s", tostring(clientnum))
    end
    if client_cache[clientnum] and client_cache[clientnum].guid then
        return client_cache[clientnum].guid
    end
    local userinfo = et.trap_GetUserinfo(clientnum)
    if userinfo then
        local guid = et.Info_ValueForKey(userinfo, "cl_guid")
        if guid and guid ~= "" then
            client_cache[clientnum] = client_cache[clientnum] or {}
            client_cache[clientnum].guid = guid
            return guid
        end
    end
    return string.format("SLOT%d", clientnum)
end

local function sanitizeName(name)
    if not name then return "Unknown" end
    name = string.gsub(name, ";", "_")
    name = string.gsub(name, "|", "_")
    name = string.gsub(name, ",", "_")
    name = string.gsub(name, "\n", "")
    name = string.gsub(name, "\r", "")
    if config.max_string_length and #name > config.max_string_length then
        name = string.sub(name, 1, config.max_string_length)
    end
    return name
end

local function updateClientCache(clientnum)
    local userinfo = et.trap_GetUserinfo(clientnum)
    local guid = nil
    if userinfo then guid = et.Info_ValueForKey(userinfo, "cl_guid") end
    local name = safe_gentity_get(clientnum, "pers.netname") or "Unknown"
    name = sanitizeName(name)
    local team = safe_gentity_get(clientnum, "sess.sessionTeam")
    local team_name = "SPEC"
    if team == 1 then team_name = "AXIS"
    elseif team == 2 then team_name = "ALLIES" end
    client_cache[clientnum] = {
        guid = guid or string.format("SLOT%d", clientnum),
        name = name,
        team = team_name
    }
end

local function getPlayerName(clientnum)
    if not isValidClient(clientnum) then return "World" end
    if client_cache[clientnum] and client_cache[clientnum].name then
        return client_cache[clientnum].name
    end
    local name = safe_gentity_get(clientnum, "pers.netname") or "Unknown"
    name = sanitizeName(name)
    client_cache[clientnum] = client_cache[clientnum] or {}
    client_cache[clientnum].name = name
    return name
end

local function getPlayerTeam(clientnum)
    if not isValidClient(clientnum) then return "SPEC" end
    if client_cache[clientnum] and client_cache[clientnum].team then
        return client_cache[clientnum].team
    end
    local team = safe_gentity_get(clientnum, "sess.sessionTeam")
    local team_str
    if team == 1 then team_str = "AXIS"
    elseif team == 2 then team_str = "ALLIES"
    else team_str = "SPEC" end
    -- Cache the result to avoid repeated gentity_get calls
    client_cache[clientnum] = client_cache[clientnum] or {}
    client_cache[clientnum].team = team_str
    return team_str
end

local function getPlayerTeamNum(clientnum)
    if not isValidClient(clientnum) then return 0 end
    return safe_gentity_get(clientnum, "sess.sessionTeam") or 0
end

local function isPlayerActive(clientnum)
    if not isValidClient(clientnum) then return false end
    local connected = safe_gentity_get(clientnum, "pers.connected")
    if connected ~= 2 then return false end
    local team = safe_gentity_get(clientnum, "sess.sessionTeam")
    return team == 1 or team == 2
end

local function isPlayerAlive(clientnum)
    if not isPlayerActive(clientnum) then return false end
    local health = tonumber(safe_gentity_get(clientnum, "health")) or 0
    return health > 0
end

local function distance3D(pos1, pos2)
    if not pos1 or not pos2 then return 9999 end
    local dx = pos1.x - pos2.x
    local dy = pos1.y - pos2.y
    local dz = pos1.z - pos2.z
    return math.sqrt(dx*dx + dy*dy + dz*dz)
end

local function distance2D(pos1, pos2)
    if not pos1 or not pos2 then return 9999 end
    local dx = pos1.x - pos2.x
    local dy = pos1.y - pos2.y
    return math.sqrt(dx*dx + dy*dy)
end

local function round(num, decimals)
    local mult = 10^(decimals or 0)
    return math.floor(num * mult + 0.5) / mult
end

local function getGridKey(x, y)
    local gx = math.floor(x / config.grid_size)
    local gy = math.floor(y / config.grid_size)
    return string.format("%d,%d", gx, gy)
end

local function gameTime()
    return et.trap_Milliseconds() - tracker.round.start_time
end

local function getMapName()
    local serverinfo = et.trap_GetConfigstring(0)
    local mapname = ""
    if serverinfo then mapname = et.Info_ValueForKey(serverinfo, "mapname") or "" end
    if not mapname or mapname == "" then mapname = et.trap_Cvar_Get("mapname") or "" end
    if not mapname or mapname == "" then mapname = "unknown" end
    return mapname
end

local function refreshRoundInfo()
    tracker.round.map_name = getMapName()
    local round_str = et.trap_Cvar_Get("g_currentRound")
    local round_num = (tonumber(round_str) or 0) + 1
    tracker.round.round_num = round_num
end

local function proxPrint(msg)
    local gs = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gs == GS_INTERMISSION and not config.log_in_intermission then return end
    et.G_Print(msg)
end

local function getObjectivesForMap(map_name)
    if not config.objective_tracking then return nil end
    return config.objectives[map_name]
end

local function getNearestObjective(pos, objectives)
    if not pos or not objectives then return nil, nil end
    local best_name, best_dist = nil, nil
    for _, obj in ipairs(objectives) do
        local dist = distance3D(pos, obj)
        if not best_dist or dist < best_dist then
            best_dist = dist
            best_name = obj.name
        end
    end
    return best_name, best_dist
end

-- ===== v5 VECTOR MATH =====

local function normalize2D(x, y)
    local mag = math.sqrt(x*x + y*y)
    if mag < 0.001 then return 0, 0 end
    return x/mag, y/mag
end

local function clamp(value, min_v, max_v)
    if value < min_v then return min_v end
    if value > max_v then return max_v end
    return value
end

-- Calculate angular separation (degrees) between two positions as seen from a target
local function angularSeparation(target_pos, pos_a, pos_b)
    if not target_pos or not pos_a or not pos_b then return 0 end
    local ax, ay = normalize2D(pos_a.x - target_pos.x, pos_a.y - target_pos.y)
    local bx, by = normalize2D(pos_b.x - target_pos.x, pos_b.y - target_pos.y)
    local dot = clamp(ax*bx + ay*by, -1, 1)
    return math.deg(math.acos(dot))
end

-- ===== v5 LINE OF SIGHT =====
-- et.trap_Trace returns a table with .fraction in ET:Legacy Lua.
-- fraction = 1.0 means clear LOS (no solid hit).
-- We wrap in pcall for safety since Lua binding may vary by ETL version.

local last_trace_error_time = 0

local function hasLineOfSight(pos_a, pos_b, ignore_ent)
    -- Raise trace slightly above ground to avoid floor clipping
    local start_pos = {pos_a.x, pos_a.y, pos_a.z + 36}  -- ~eye height
    local end_pos = {pos_b.x, pos_b.y, pos_b.z + 36}
    local mins = {0, 0, 0}
    local maxs = {0, 0, 0}

    -- Content mask: CONTENTS_SOLID(1) + CONTENTS_PLAYERCLIP(0x10000) + CONTENTS_SHOTCLIP(0x40000) = 327681
    -- This blocks traces through clip brushes that stop bullets, not just solid walls
    local ok, result = pcall(et.trap_Trace, start_pos, mins, maxs, end_pos, ignore_ent or -1, 327681)
    if not ok then
        local now = et.trap_Milliseconds()
        if now - last_trace_error_time > 10000 then
            et.G_Print("[PROX] trap_Trace error: " .. tostring(result) .. "\n")
            last_trace_error_time = now
        end
        return false
    end

    -- Handle different return formats
    if type(result) == "table" then
        local frac = result.fraction or result[1]
        if frac then return tonumber(frac) >= 0.98 end
    elseif type(result) == "number" then
        return result >= 0.98
    end
    return false
end

-- ===== PLAYER STATE FUNCTIONS =====

local function getPlayerVelocity(clientnum)
    local vel = safe_gentity_get(clientnum, "ps.velocity")
    if not vel then return 0, 0, 0 end
    return tonumber(vel[1]) or 0, tonumber(vel[2]) or 0, tonumber(vel[3]) or 0
end

local function getPlayerSpeed(clientnum)
    local vx, vy, vz = getPlayerVelocity(clientnum)
    return math.sqrt(vx*vx + vy*vy)
end

local function getPlayerMovementState(clientnum, speed)
    local pm_flags = tonumber(safe_gentity_get(clientnum, "ps.pm_flags")) or 0
    local stance = 0
    if has_flag(pm_flags, PMF_PRONE) then stance = 2
    elseif has_flag(pm_flags, PMF_DUCKED) then stance = 1 end
    local sprinting = 0
    if has_flag(pm_flags, PMF_SPRINT) then sprinting = 1 end
    local sprint_time = tonumber(safe_gentity_get(clientnum, "ps.stats", STAT_SPRINTTIME))
    if sprint_time then
        local last_sprint_time = tracker.last_stamina[clientnum]
        tracker.last_stamina[clientnum] = sprint_time
        if last_sprint_time and speed and speed >= MIN_SPRINT_SPEED and stance == 0 then
            local sprint_delta = last_sprint_time - sprint_time
            if sprint_delta > STAMINA_DELTA_SPRINT_THRESHOLD then sprinting = 1 end
        end
    end
    return stance, sprinting
end

local function getPlayerClass(clientnum)
    local ptype = safe_gentity_get(clientnum, "sess.playerType") or 0
    local classes = { [0] = "SOLDIER", [1] = "MEDIC", [2] = "ENGINEER", [3] = "FIELDOPS", [4] = "COVERTOPS" }
    return classes[ptype] or "UNKNOWN"
end

-- ===== DEATH TYPE CATEGORIZATION =====
local MOD_SELFKILL = 37
local MOD_FALLING = 38

local function getDeathType(victim, killer, meansOfDeath)
    if meansOfDeath == MOD_SELFKILL then return "selfkill" end
    if meansOfDeath == MOD_FALLING then return "fallen" end
    if killer == 1022 or killer == 1023 then return "world" end
    if killer == victim then return "selfkill" end
    if killer and isPlayerActive(killer) and isPlayerActive(victim) then
        if getPlayerTeam(victim) == getPlayerTeam(killer) then return "teamkill" end
    end
    return "killed"
end

-- ===== v5 TEAM ROSTER HELPERS =====
-- Get all alive players on a team, with positions

local function getAliveTeamMembers(team_num)
    local members = {}
    local max_clients = get_max_clients()
    for i = 0, max_clients - 1 do
        if isPlayerAlive(i) then
            local t = safe_gentity_get(i, "sess.sessionTeam")
            if t == team_num then
                local pos = getPlayerPos(i)
                if pos then
                    table.insert(members, {
                        slot = i,
                        guid = getPlayerGUID(i),
                        name = getPlayerName(i),
                        pos = pos,
                    })
                end
            end
        end
    end
    return members
end

local function getAliveEnemies(team_num)
    local enemy_team = (team_num == 1) and 2 or 1
    return getAliveTeamMembers(enemy_team)
end

-- ===== FULL PLAYER TRACKING (v4) =====

local function createPlayerTrack(clientnum)
    local now = gameTime()
    local pos = getPlayerPos(clientnum)
    local track = {
        clientnum = clientnum,
        guid = getPlayerGUID(clientnum),
        name = getPlayerName(clientnum),
        team = getPlayerTeam(clientnum),
        class = getPlayerClass(clientnum),
        spawn_time = now,
        spawn_pos = pos,
        death_time = nil,
        death_pos = nil,
        death_type = nil,
        killer_name = nil,
        path = {},
        actions = {},
        first_move_time = nil,
        had_input = false
    }
    if pos then
        local health = safe_gentity_get(clientnum, "health") or 100
        local weapon = safe_gentity_get(clientnum, "ps.weapon") or 0
        local speed = getPlayerSpeed(clientnum)
        local stance, sprint = getPlayerMovementState(clientnum, speed)
        table.insert(track.path, {
            time = now, x = round(pos.x, 1), y = round(pos.y, 1), z = round(pos.z, 1),
            health = health, speed = round(speed, 1), weapon = weapon,
            stance = stance, sprint = sprint, event = "spawn"
        })
    end
    tracker.player_tracks[clientnum] = track
    if config.debug then
        et.G_Printf("[PROX] Track started: %s (%s)\n", track.name, track.class)
    end
    return track
end

local function samplePlayer(clientnum, track, event_type)
    local now = gameTime()
    local pos = getPlayerPos(clientnum)
    if not pos then return end
    local health = safe_gentity_get(clientnum, "health") or 0
    local weapon = safe_gentity_get(clientnum, "ps.weapon") or 0
    local speed = getPlayerSpeed(clientnum)
    local stance, sprint = getPlayerMovementState(clientnum, speed)
    if not track.first_move_time and speed > 10 then
        local gs = tonumber(et.trap_Cvar_Get("gamestate")) or -1
        if gs == 0 and (track.spawn_time or 0) >= 0 and now >= 0 then
            track.first_move_time = now
            track.had_input = true
        end
    end
    table.insert(track.path, {
        time = now, x = round(pos.x, 1), y = round(pos.y, 1), z = round(pos.z, 1),
        health = health, speed = round(speed, 1), weapon = weapon,
        stance = stance, sprint = sprint, event = event_type or "sample"
    })
    if isFeatureEnabled("heatmap_generation") then
        local key = getGridKey(pos.x, pos.y)
        if not tracker.movement_heatmap[key] then
            tracker.movement_heatmap[key] = { traversal = 0, combat = 0, escape = 0 }
        end
        tracker.movement_heatmap[key].traversal = tracker.movement_heatmap[key].traversal + 1
    end
end

local function endPlayerTrack(clientnum, death_pos, death_type, killer_name)
    local track = tracker.player_tracks[clientnum]
    if not track then return end
    track.death_time = gameTime()
    track.death_pos = death_pos
    track.death_type = death_type or "unknown"
    track.killer_name = killer_name
    if death_pos then
        local weapon = safe_gentity_get(clientnum, "ps.weapon") or 0
        table.insert(track.path, {
            time = track.death_time, x = round(death_pos.x, 1), y = round(death_pos.y, 1), z = round(death_pos.z, 1),
            health = 0, speed = 0, weapon = weapon, stance = 0, sprint = 0,
            event = death_type or "death"
        })
    end
    table.insert(tracker.completed_tracks, track)
    tracker.player_tracks[clientnum] = nil
    tracker.last_stamina[clientnum] = nil
    if config.debug then
        et.G_Printf("[PROX] Track ended: %s - %d samples, type=%s\n",
            track.name, #track.path, track.death_type)
    end
end

local function sampleAllPlayers()
    local now = gameTime()
    if now - tracker.last_sample_time < config.position_sample_interval then return end
    tracker.last_sample_time = now

    local objectives = getObjectivesForMap(tracker.round.map_name)
    for clientnum, track in pairs(tracker.player_tracks) do
        if isPlayerActive(clientnum) then
            samplePlayer(clientnum, track, "sample")
            if objectives and config.objective_tracking then
                local pos = getPlayerPos(clientnum)
                local obj_name, dist = getNearestObjective(pos, objectives)
                if obj_name and dist then
                    local stats = tracker.objective_stats[track.guid]
                    if not stats then
                        stats = { guid = track.guid, name = track.name, team = track.team,
                            samples = 0, distance_sum = 0, time_within_radius_ms = 0, objective_counts = {} }
                        tracker.objective_stats[track.guid] = stats
                    end
                    stats.samples = stats.samples + 1
                    stats.distance_sum = stats.distance_sum + dist
                    stats.objective_counts[obj_name] = (stats.objective_counts[obj_name] or 0) + 1
                    if dist <= config.objective_radius then
                        stats.time_within_radius_ms = stats.time_within_radius_ms + config.position_sample_interval
                    end
                end
            end
        end
    end
end

-- ===== ENGAGEMENT MANAGEMENT (v4) =====

local function createEngagement(target_slot)
    tracker.engagement_counter = tracker.engagement_counter + 1
    local pos = getPlayerPos(target_slot)
    local now = gameTime()
    local engagement = {
        id = tracker.engagement_counter,
        target_slot = target_slot,
        target_guid = getPlayerGUID(target_slot),
        target_name = getPlayerName(target_slot),
        target_team = getPlayerTeam(target_slot),
        target_class = getPlayerClass(target_slot),
        start_time = now, first_hit_time = now, last_hit_time = now, last_sample_time = now,
        start_pos = pos, last_hit_pos = pos, position_path = {}, distance_traveled = 0,
        attackers = {}, attacker_order = {},
        total_damage = 0, outcome = nil, killer_guid = nil, killer_name = nil,
        return_fire_ms = nil, dodge_reaction_ms = nil, support_reaction_ms = nil
    }
    if pos then
        table.insert(engagement.position_path, {
            time = now, x = round(pos.x, 1), y = round(pos.y, 1), z = round(pos.z, 1), event = "start"
        })
    end
    tracker.engagements[target_slot] = engagement
    if config.debug then
        et.G_Printf("[PROX] Engagement #%d started: %s\n", engagement.id, engagement.target_name)
    end
    return engagement
end

local function recordHit(engagement, attacker_slot, damage, weapon)
    if not isValidClient(attacker_slot) then return end
    local now = gameTime()
    local attacker_guid = getPlayerGUID(attacker_slot)
    local target_pos = getPlayerPos(engagement.target_slot)
    if not engagement.attackers[attacker_guid] then
        engagement.attackers[attacker_guid] = {
            slot = attacker_slot, name = getPlayerName(attacker_slot), team = getPlayerTeam(attacker_slot),
            damage = 0, hits = 0, first_hit = now, last_hit = now, weapons = {}, got_kill = false
        }
        table.insert(engagement.attacker_order, attacker_guid)
    end
    local attacker = engagement.attackers[attacker_guid]
    attacker.damage = attacker.damage + damage
    attacker.hits = attacker.hits + 1
    attacker.last_hit = now
    if weapon and weapon > 0 then
        attacker.weapons[weapon] = (attacker.weapons[weapon] or 0) + 1
    end
    engagement.total_damage = engagement.total_damage + damage
    engagement.last_hit_time = now
    if target_pos and engagement.last_hit_pos then
        engagement.distance_traveled = engagement.distance_traveled + distance3D(target_pos, engagement.last_hit_pos)
    end
    engagement.last_hit_pos = target_pos
    if target_pos then
        table.insert(engagement.position_path, {
            time = now, x = round(target_pos.x, 1), y = round(target_pos.y, 1), z = round(target_pos.z, 1), event = "hit"
        })
        if isFeatureEnabled("heatmap_generation") then
            local key = getGridKey(target_pos.x, target_pos.y)
            if not tracker.movement_heatmap[key] then
                tracker.movement_heatmap[key] = { traversal = 0, combat = 0, escape = 0 }
            end
            tracker.movement_heatmap[key].combat = tracker.movement_heatmap[key].combat + 1
        end
    end
end

local function detectCrossfire(engagement)
    if #engagement.attacker_order < 2 then return false, nil, nil end
    local first_guid = engagement.attacker_order[1]
    local second_guid = engagement.attacker_order[2]
    local first_hit = engagement.attackers[first_guid].first_hit
    local second_hit = engagement.attackers[second_guid].first_hit
    local delay = second_hit - first_hit
    if delay <= config.crossfire_window_ms then
        local participants = {}
        for _, guid in ipairs(engagement.attacker_order) do
            if engagement.attackers[guid].first_hit - first_hit <= config.crossfire_window_ms then
                table.insert(participants, guid)
            end
        end
        return true, delay, participants
    end
    return false, nil, nil
end

local function computeDodgeReactionMs(engagement)
    if not engagement or not engagement.position_path then return nil end
    local first_hit = engagement.first_hit_time or engagement.start_time
    if not first_hit then return nil end
    local points = {}
    for _, point in ipairs(engagement.position_path) do
        if point.time and point.time >= first_hit then table.insert(points, point) end
    end
    if #points < 3 then return nil end
    local min_step = config.dodge_min_step_units or 24
    local angle_threshold = math.rad(config.dodge_angle_threshold_deg or 45)
    local base_dx, base_dy = nil, nil
    local function normalizeSegment(a, b)
        if not a or not b then return nil, nil, nil end
        local dx = (b.x or 0) - (a.x or 0)
        local dy = (b.y or 0) - (a.y or 0)
        local mag = math.sqrt(dx * dx + dy * dy)
        if mag < min_step then return nil, nil, nil end
        return dx / mag, dy / mag, mag
    end
    for idx = 2, #points do
        local ndx, ndy = normalizeSegment(points[idx - 1], points[idx])
        if ndx and ndy then
            if not base_dx then
                base_dx = ndx
                base_dy = ndy
            else
                local dot = clamp(base_dx * ndx + base_dy * ndy, -1, 1)
                local angle = math.acos(dot)
                if angle >= angle_threshold then
                    local delta = (points[idx].time or first_hit) - first_hit
                    if delta >= 0 and delta <= (config.reaction_window_ms or 5000) then return delta end
                    return nil
                end
            end
        end
    end
    return nil
end

local function registerReactionSignals(damage_target_slot, damage_attacker_slot, event_time_ms)
    if not isFeatureEnabled("reaction_tracking") then return end
    if not isValidClient(damage_target_slot) or not isValidClient(damage_attacker_slot) then return end
    local damage_target_guid = getPlayerGUID(damage_target_slot)
    local attacker_team = getPlayerTeam(damage_attacker_slot)
    for _, engagement in pairs(tracker.engagements) do
        local first_hit = engagement.first_hit_time or engagement.start_time
        if first_hit and event_time_ms >= first_hit then
            local delta_ms = event_time_ms - first_hit
            if delta_ms <= (config.reaction_window_ms or 5000) then
                if (not engagement.return_fire_ms) and damage_attacker_slot == engagement.target_slot then
                    if engagement.attackers[damage_target_guid] then
                        engagement.return_fire_ms = delta_ms
                    end
                end
                if (not engagement.support_reaction_ms)
                    and damage_attacker_slot ~= engagement.target_slot
                    and attacker_team == engagement.target_team
                    and engagement.attackers[damage_target_guid] then
                    engagement.support_reaction_ms = delta_ms
                end
            end
        end
    end
end

local function closeEngagement(engagement, outcome, killer_slot)
    local now = gameTime()
    local end_pos = getPlayerPos(engagement.target_slot) or engagement.last_hit_pos
    engagement.end_time = now
    engagement.duration = now - engagement.start_time
    engagement.outcome = outcome
    engagement.end_pos = end_pos
    if end_pos then
        table.insert(engagement.position_path, {
            time = now, x = round(end_pos.x, 1), y = round(end_pos.y, 1), z = round(end_pos.z, 1),
            event = outcome == "killed" and "death" or "escape"
        })
        if engagement.last_hit_pos then
            engagement.distance_traveled = engagement.distance_traveled + distance3D(end_pos, engagement.last_hit_pos)
        end
    end
    if outcome == "killed" and killer_slot and isValidClient(killer_slot) and isPlayerActive(killer_slot) then
        local killer_guid = getPlayerGUID(killer_slot)
        engagement.killer_guid = killer_guid
        engagement.killer_name = getPlayerName(killer_slot)
        if engagement.attackers[killer_guid] then
            engagement.attackers[killer_guid].got_kill = true
        end
        if isFeatureEnabled("heatmap_generation") and end_pos then
            local key = getGridKey(end_pos.x, end_pos.y)
            if not tracker.kill_heatmap[key] then tracker.kill_heatmap[key] = { axis = 0, allies = 0 } end
            local killer_team = getPlayerTeam(killer_slot)
            if killer_team == "AXIS" then tracker.kill_heatmap[key].axis = tracker.kill_heatmap[key].axis + 1
            else tracker.kill_heatmap[key].allies = tracker.kill_heatmap[key].allies + 1 end
        end
    else
        engagement.killer_guid = nil
        engagement.killer_name = nil
    end
    if isFeatureEnabled("heatmap_generation") and outcome == "escaped" and end_pos then
        local key = getGridKey(end_pos.x, end_pos.y)
        if not tracker.movement_heatmap[key] then
            tracker.movement_heatmap[key] = { traversal = 0, combat = 0, escape = 0 }
        end
        tracker.movement_heatmap[key].escape = tracker.movement_heatmap[key].escape + 1
    end
    local is_crossfire, delay, participants = false, nil, nil
    if isFeatureEnabled("crossfire_detection") then
        is_crossfire, delay, participants = detectCrossfire(engagement)
    end
    engagement.is_crossfire = is_crossfire
    engagement.crossfire_delay = delay
    engagement.crossfire_participants = participants

    if isFeatureEnabled("reaction_tracking") then
        engagement.dodge_reaction_ms = computeDodgeReactionMs(engagement)
        table.insert(tracker.reaction_metrics, {
            engagement_id = engagement.id,
            target_guid = engagement.target_guid,
            target_name = engagement.target_name,
            target_team = engagement.target_team,
            target_class = engagement.target_class or getPlayerClass(engagement.target_slot),
            outcome = engagement.outcome or "unknown",
            num_attackers = #engagement.attacker_order,
            return_fire_ms = engagement.return_fire_ms,
            dodge_reaction_ms = engagement.dodge_reaction_ms,
            support_reaction_ms = engagement.support_reaction_ms,
            start_time = engagement.start_time or 0,
            end_time = engagement.end_time or 0,
            duration = engagement.duration or 0
        })
    end

    -- v5: Focus fire detection
    if isFeatureEnabled("focus_fire") and #engagement.attacker_order >= config.teamplay.focus_fire_min_attackers then
        local guids_str = table.concat(engagement.attacker_order, ",")
        table.insert(tracker.focus_fire.events, {
            engagement_id = engagement.id,
            target_guid = engagement.target_guid,
            target_name = engagement.target_name,
            attacker_count = #engagement.attacker_order,
            attacker_guids = guids_str,
            total_damage = engagement.total_damage,
            duration = engagement.duration or 0,
            focus_score = 0  -- Will be computed below
        })
    end

    table.insert(tracker.completed, engagement)
    tracker.engagements[engagement.target_slot] = nil
    if config.debug then
        local cf_str = is_crossfire and string.format(" [CROSSFIRE %dms]", delay) or ""
        et.G_Printf("[PROX] Engagement #%d closed: %s -> %s (%d dmg, %d attackers)%s\n",
            engagement.id, engagement.target_name, outcome,
            engagement.total_damage, #engagement.attacker_order, cf_str)
    end
end

-- ===== ESCAPE DETECTION =====

local function checkEscapes(levelTime)
    local now = gameTime()
    local stale_timeout = 15000  -- 15 seconds: force-close engagements with no activity
    for target_slot, engagement in pairs(tracker.engagements) do
        local time_since_hit = now - engagement.last_hit_time

        -- Failsafe: close stale engagements (e.g. player disconnected mid-fight)
        if time_since_hit >= stale_timeout then
            closeEngagement(engagement, "timeout", nil)
        elseif time_since_hit >= config.escape_time_ms then
            local current_pos = getPlayerPos(target_slot)
            if current_pos and engagement.last_hit_pos then
                if distance3D(current_pos, engagement.last_hit_pos) >= config.escape_distance then
                    closeEngagement(engagement, "escaped", nil)
                end
            end
        end
        if tracker.engagements[target_slot] then
            local time_since_sample = now - engagement.last_sample_time
            if time_since_sample >= config.position_sample_interval then
                local pos = getPlayerPos(target_slot)
                if pos then
                    table.insert(engagement.position_path, {
                        time = now, x = round(pos.x, 1), y = round(pos.y, 1), z = round(pos.z, 1), event = "sample"
                    })
                end
                engagement.last_sample_time = now
            end
        end
    end
end

-- =============================================================
-- ===== v5 TEAMPLAY ANALYSIS SYSTEMS =====
-- =============================================================

-- ===== 1. SPAWN WAVE TRACKING =====

local function refreshSpawnTimers()
    local axis_ms = tonumber(et.trap_Cvar_Get("g_axisSpawnTime")) or 0
    local allies_ms = tonumber(et.trap_Cvar_Get("g_alliedSpawnTime")) or 0
    -- Convert seconds to ms if values look like seconds (< 1000)
    if axis_ms > 0 and axis_ms < 1000 then axis_ms = axis_ms * 1000 end
    if allies_ms > 0 and allies_ms < 1000 then allies_ms = allies_ms * 1000 end
    tracker.spawn.axis_interval = axis_ms
    tracker.spawn.allies_interval = allies_ms
end

-- Calculate spawn timing score for a kill
-- Returns: time_to_next_spawn (ms), score (0.0-1.0, higher = better timing)
local function calculateSpawnTimingScore(kill_game_time, victim_team_num)
    local interval = 0
    if victim_team_num == 1 then
        interval = tracker.spawn.axis_interval
    elseif victim_team_num == 2 then
        interval = tracker.spawn.allies_interval
    end

    if interval <= 0 then return 0, 0 end

    -- Time elapsed in the current spawn cycle
    local cycle_elapsed = kill_game_time % interval
    -- Time until the next spawn wave fires for the victim's team
    local time_to_next = interval - cycle_elapsed

    -- Score: 1.0 = killed right after spawn wave (max wait), 0.0 = killed right before (instant respawn)
    local score = time_to_next / interval
    return time_to_next, score
end

local function recordSpawnTiming(killer_slot, victim_slot, kill_time)
    if not isFeatureEnabled("spawn_timing") then return end

    local victim_team_num = getPlayerTeamNum(victim_slot)
    if victim_team_num ~= 1 and victim_team_num ~= 2 then return end

    local time_to_next, score = calculateSpawnTimingScore(kill_time, victim_team_num)
    local interval = victim_team_num == 1 and tracker.spawn.axis_interval or tracker.spawn.allies_interval

    table.insert(tracker.spawn.kill_timings, {
        killer_guid = getPlayerGUID(killer_slot),
        killer_name = getPlayerName(killer_slot),
        killer_team = getPlayerTeam(killer_slot),
        victim_guid = getPlayerGUID(victim_slot),
        victim_name = getPlayerName(victim_slot),
        victim_team = getPlayerTeam(victim_slot),
        kill_time = kill_time,
        enemy_spawn_interval = interval,
        time_to_next_spawn = round(time_to_next, 0),
        spawn_timing_score = round(score, 3),
    })

    if config.debug then
        et.G_Printf("[PROX] Spawn timing: %s killed %s, score=%.2f (%.0fms to next spawn, %dms interval)\n",
            getPlayerName(killer_slot), getPlayerName(victim_slot), score, time_to_next, interval)
    end
end

-- ===== 2. TEAM COHESION =====

local function analyzeTeamCohesion(team_num, now)
    local team_name = team_num == 1 and "AXIS" or "ALLIES"
    local members = getAliveTeamMembers(team_num)

    if #members < config.teamplay.min_team_size or #members == 0 then return end

    -- Calculate centroid
    local cx, cy = 0, 0
    for _, m in ipairs(members) do
        cx = cx + m.pos.x
        cy = cy + m.pos.y
    end
    cx = cx / #members
    cy = cy / #members

    -- Calculate dispersion (avg distance from centroid)
    local total_dist = 0
    local max_spread = 0
    local straggler_count = 0

    for _, m in ipairs(members) do
        local dx = m.pos.x - cx
        local dy = m.pos.y - cy
        local dist = math.sqrt(dx*dx + dy*dy)
        total_dist = total_dist + dist
        if dist > config.teamplay.straggler_distance then
            straggler_count = straggler_count + 1
        end
    end
    local dispersion = total_dist / #members

    -- Calculate max spread (distance between furthest two players)
    for i = 1, #members do
        for j = i + 1, #members do
            local d = distance2D(members[i].pos, members[j].pos)
            if d > max_spread then max_spread = d end
        end
    end

    -- Find buddy pair (closest two teammates)
    local buddy1_guid, buddy2_guid = "", ""
    local buddy_dist = 99999
    for i = 1, #members do
        for j = i + 1, #members do
            local d = distance2D(members[i].pos, members[j].pos)
            if d < buddy_dist then
                buddy_dist = d
                buddy1_guid = members[i].guid
                buddy2_guid = members[j].guid
            end
        end
    end

    table.insert(tracker.cohesion.samples, {
        time = now,
        team = team_name,
        alive_count = #members,
        centroid_x = round(cx, 1),
        centroid_y = round(cy, 1),
        dispersion = round(dispersion, 1),
        max_spread = round(max_spread, 1),
        straggler_count = straggler_count,
        buddy_pair_guids = buddy1_guid .. "+" .. buddy2_guid,
        buddy_distance = round(buddy_dist, 1),
    })
end

-- ===== 3. CROSSFIRE OPPORTUNITIES =====

local function analyzeCrossfireOpportunities(now)
    -- Dedup: track which (target, t1, t2) triples we've already recorded this tick
    local seen = {}

    -- For each team, check if pairs of teammates have LOS on the same enemy
    for team_num = 1, 2 do
        local teammates = getAliveTeamMembers(team_num)
        local enemies = getAliveEnemies(team_num)

        if #teammates >= 2 and #enemies >= 1 then
            for _, enemy in ipairs(enemies) do
                -- Find all teammates with LOS to this enemy within range
                local los_teammates = {}
                for _, mate in ipairs(teammates) do
                    local dist = distance2D(mate.pos, enemy.pos)
                    if dist <= config.teamplay.los_max_range then
                        if hasLineOfSight(mate.pos, enemy.pos, mate.slot) then
                            table.insert(los_teammates, mate)
                        end
                    end
                end

                -- Check pairs for crossfire angles
                if #los_teammates >= 2 then
                    for i = 1, #los_teammates do
                        for j = i + 1, #los_teammates do
                            -- Canonical key: sort GUIDs so (A,B) == (B,A)
                            local g1, g2 = los_teammates[i].guid, los_teammates[j].guid
                            if g1 > g2 then g1, g2 = g2, g1 end
                            local dedup_key = enemy.guid .. ":" .. g1 .. ":" .. g2
                            if seen[dedup_key] then
                                -- Skip duplicate
                            else
                            local angle = angularSeparation(enemy.pos, los_teammates[i].pos, los_teammates[j].pos)
                            if angle >= config.teamplay.crossfire_min_angle then
                                seen[dedup_key] = true
                                table.insert(tracker.crossfire_opps.pending, {
                                    detect_time = now,
                                    expire_time = now + config.teamplay.crossfire_execute_window_ms,
                                    target_slot = enemy.slot,
                                    target_guid = enemy.guid,
                                    target_name = enemy.name,
                                    target_team = getPlayerTeam(enemy.slot),
                                    t1_slot = los_teammates[i].slot,
                                    t1_guid = los_teammates[i].guid,
                                    t2_slot = los_teammates[j].slot,
                                    t2_guid = los_teammates[j].guid,
                                    angle = round(angle, 1),
                                    t1_fired = false,
                                    t2_fired = false,
                                    damage_dealt = 0,
                                })
                            end
                            end -- dedup else
                        end
                    end
                end
            end
        end -- #teammates >= 2
    end
end

-- Check if pending crossfire opportunities were executed (called from et_Damage)
local function checkCrossfireExecution(attacker_slot, target_slot, damage)
    if not isFeatureEnabled("crossfire_opportunities") then return end
    local now = gameTime()
    local attacker_guid = getPlayerGUID(attacker_slot)

    for _, opp in ipairs(tracker.crossfire_opps.pending) do
        if now <= opp.expire_time and target_slot == opp.target_slot then
            if attacker_guid == opp.t1_guid then
                opp.t1_fired = true
                opp.damage_dealt = opp.damage_dealt + damage
            elseif attacker_guid == opp.t2_guid then
                opp.t2_fired = true
                opp.damage_dealt = opp.damage_dealt + damage
            end
        end
    end
end

-- Flush expired pending crossfire opportunities to completed events
local function flushCrossfireOpps(now)
    local still_pending = {}
    for _, opp in ipairs(tracker.crossfire_opps.pending) do
        if now > opp.expire_time then
            -- Opportunity window expired - record result
            local executed = opp.t1_fired and opp.t2_fired
            table.insert(tracker.crossfire_opps.events, {
                time = opp.detect_time,
                target_guid = opp.target_guid,
                target_name = opp.target_name,
                target_team = opp.target_team,
                teammate1_guid = opp.t1_guid,
                teammate2_guid = opp.t2_guid,
                angular_separation = opp.angle,
                was_executed = executed and "1" or "0",
                damage_within_window = opp.damage_dealt,
            })
        else
            table.insert(still_pending, opp)
        end
    end
    tracker.crossfire_opps.pending = still_pending
end

-- ===== 5. TEAM PUSH DETECTION =====

local function analyzeTeamPushes(now)
    local objectives = getObjectivesForMap(tracker.round.map_name)

    for team_num = 1, 2 do
        local team_name = team_num == 1 and "AXIS" or "ALLIES"
        local members = getAliveTeamMembers(team_num)

        if #members < config.teamplay.min_team_size then
            -- End any active push
            if tracker.pushes.active[team_num] then
                local push = tracker.pushes.active[team_num]
                push.end_time = now
                table.insert(tracker.pushes.events, push)
                tracker.pushes.active[team_num] = nil
            end
        else
            -- Get velocities
            local avg_vx, avg_vy = 0, 0
            local avg_speed = 0
            local velocity_count = 0

            for _, m in ipairs(members) do
                local vx, vy = getPlayerVelocity(m.slot)
                local speed = math.sqrt(vx*vx + vy*vy)
                if speed > 10 then  -- Only count moving players
                    avg_vx = avg_vx + vx
                    avg_vy = avg_vy + vy
                    avg_speed = avg_speed + speed
                    velocity_count = velocity_count + 1
                end
            end

            if velocity_count < config.teamplay.min_team_size then
                if tracker.pushes.active[team_num] then
                    local push = tracker.pushes.active[team_num]
                    push.end_time = now
                    table.insert(tracker.pushes.events, push)
                    tracker.pushes.active[team_num] = nil
                end
            else
                avg_vx = avg_vx / velocity_count
                avg_vy = avg_vy / velocity_count
                avg_speed = avg_speed / velocity_count

                -- Calculate direction alignment (how aligned are individual velocities with team avg?)
                local team_dir_x, team_dir_y = normalize2D(avg_vx, avg_vy)
                local total_alignment = 0

                for _, m in ipairs(members) do
                    local vx, vy = getPlayerVelocity(m.slot)
                    local speed = math.sqrt(vx*vx + vy*vy)
                    if speed > 10 then
                        local px, py = normalize2D(vx, vy)
                        local dot = team_dir_x * px + team_dir_y * py
                        total_alignment = total_alignment + dot
                    end
                end
                local alignment = total_alignment / velocity_count

                -- Check if moving toward objective
                local toward_obj = "N/A"
                if objectives and #objectives > 0 then
                    -- Team centroid
                    local cx, cy = 0, 0
                    for _, m in ipairs(members) do cx = cx + m.pos.x; cy = cy + m.pos.y end
                    cx = cx / #members; cy = cy / #members

                    local obj_name, _ = getNearestObjective({x=cx, y=cy, z=0}, objectives)
                    if obj_name then
                        -- Find the objective coords
                        for _, obj in ipairs(objectives) do
                            if obj.name == obj_name then
                                local to_obj_x, to_obj_y = normalize2D(obj.x - cx, obj.y - cy)
                                local obj_dot = team_dir_x * to_obj_x + team_dir_y * to_obj_y
                                toward_obj = obj_dot > 0.3 and obj_name or "NO"
                                break
                            end
                        end
                    end
                end

                local push_quality = alignment * (avg_speed / 300)  -- 300 is approximate sprint speed

                -- Detect push state
                if avg_speed >= config.teamplay.push_min_speed and alignment >= config.teamplay.push_min_alignment then
                    -- Team is pushing
                    if not tracker.pushes.active[team_num] then
                        -- Start new push
                        tracker.pushes.active[team_num] = {
                            start_time = now,
                            end_time = nil,
                            team = team_name,
                            avg_speed = round(avg_speed, 1),
                            direction_x = round(team_dir_x, 3),
                            direction_y = round(team_dir_y, 3),
                            alignment_score = round(alignment, 3),
                            push_quality = round(push_quality, 3),
                            participant_count = velocity_count,
                            toward_objective = toward_obj,
                        }
                    else
                        -- Update ongoing push with latest values
                        local push = tracker.pushes.active[team_num]
                        push.avg_speed = round((push.avg_speed + avg_speed) / 2, 1)
                        push.alignment_score = round((push.alignment_score + alignment) / 2, 3)
                        push.push_quality = round((push.push_quality + push_quality) / 2, 3)
                        push.participant_count = math.max(push.participant_count, velocity_count)
                        if toward_obj ~= "NO" and toward_obj ~= "N/A" then
                            push.toward_objective = toward_obj
                        end
                    end
                else
                    -- Team stopped pushing
                    if tracker.pushes.active[team_num] then
                        local push = tracker.pushes.active[team_num]
                        push.end_time = now
                        table.insert(tracker.pushes.events, push)
                        tracker.pushes.active[team_num] = nil
                    end
                end
            end -- velocity_count check
        end -- members size check
    end
end

-- ===== 6. TRADE KILL DETECTION =====

local function checkTradeKill(killer_slot, victim_slot, kill_time)
    if not isFeatureEnabled("trade_kills") then return end

    local killer_guid = getPlayerGUID(killer_slot)
    local killer_team_num = getPlayerTeamNum(killer_slot)
    local window = config.teamplay.trade_kill_window_ms

    -- Check recent kills: did the victim recently kill one of the killer's teammates?
    for i = #tracker.trade_kills.recent_kills, 1, -1 do
        local rk = tracker.trade_kills.recent_kills[i]
        local delta = kill_time - rk.time

        if delta > window then break end  -- Too old, stop checking

        -- Trade: victim_slot just killed a teammate of killer_slot, and now killer_slot killed victim_slot
        if rk.killer_slot == victim_slot and rk.victim_team_num == killer_team_num then
            table.insert(tracker.trade_kills.events, {
                original_kill_time = rk.time,
                traded_kill_time = kill_time,
                delta_ms = delta,
                original_victim_guid = rk.victim_guid,
                original_victim_name = rk.victim_name,
                original_killer_guid = rk.killer_guid,
                original_killer_name = rk.killer_name,
                trader_guid = killer_guid,
                trader_name = getPlayerName(killer_slot),
            })

            if config.debug then
                et.G_Printf("[PROX] TRADE KILL: %s avenged %s (killed %s, %dms)\n",
                    getPlayerName(killer_slot), rk.victim_name, getPlayerName(victim_slot), delta)
            end
            break
        end
    end

    -- Record this kill for future trade detection
    table.insert(tracker.trade_kills.recent_kills, {
        time = kill_time,
        killer_slot = killer_slot,
        killer_guid = killer_guid,
        killer_name = getPlayerName(killer_slot),
        victim_slot = victim_slot,
        victim_guid = getPlayerGUID(victim_slot),
        victim_name = getPlayerName(victim_slot),
        victim_team_num = getPlayerTeamNum(victim_slot),
    })

    -- Trim old entries (keep last 30 seconds)
    while #tracker.trade_kills.recent_kills > 0 do
        if kill_time - tracker.trade_kills.recent_kills[1].time > 30000 then
            table.remove(tracker.trade_kills.recent_kills, 1)
        else
            break
        end
    end
end

-- ===== v5 TEAMPLAY FRAME UPDATE =====
-- Called from et_RunFrame during active play

local function updateTeamplay(now)
    -- Team cohesion (every 500ms)
    if isFeatureEnabled("team_cohesion") then
        if now - tracker.cohesion.last_check_time >= config.teamplay.cohesion_interval_ms then
            analyzeTeamCohesion(1, now)  -- Axis
            analyzeTeamCohesion(2, now)  -- Allies
            tracker.cohesion.last_check_time = now
        end
    end

    -- Crossfire opportunities (every 1000ms)
    if isFeatureEnabled("crossfire_opportunities") then
        if now - tracker.crossfire_opps.last_check_time >= config.teamplay.crossfire_opp_interval_ms then
            analyzeCrossfireOpportunities(now)
            flushCrossfireOpps(now)
            tracker.crossfire_opps.last_check_time = now
        end
    end

    -- Team push detection (every 1000ms)
    if isFeatureEnabled("team_push_detection") then
        if now - tracker.pushes.last_check_time >= config.teamplay.push_interval_ms then
            analyzeTeamPushes(now)
            tracker.pushes.last_check_time = now
        end
    end
end

-- ===== FILE OUTPUT =====

local outputLifecycleLog  -- forward declaration

local function serializeAttackers(attackers, attacker_order)
    local parts = {}
    for _, guid in ipairs(attacker_order) do
        local a = attackers[guid]
        local weapons_str = ""
        for w, count in pairs(a.weapons) do
            weapons_str = weapons_str .. w .. ":" .. count .. ";"
        end
        if weapons_str == "" then weapons_str = "0:0" end
        table.insert(parts, string.format("%s,%s,%s,%d,%d,%d,%d,%s,%s",
            guid, a.name, a.team, a.damage, a.hits, a.first_hit, a.last_hit,
            a.got_kill and "1" or "0", weapons_str))
    end
    return table.concat(parts, "|")
end

local function serializePositions(path)
    local parts = {}
    for _, p in ipairs(path) do
        table.insert(parts, string.format("%d,%.1f,%.1f,%.1f,%s", p.time, p.x, p.y, p.z, p.event))
    end
    return table.concat(parts, "|")
end

local function serializeTrackPath(path)
    local parts = {}
    for _, p in ipairs(path) do
        table.insert(parts, string.format("%d,%.1f,%.1f,%.1f,%d,%.1f,%d,%d,%d,%s",
            p.time, p.x, p.y, p.z, p.health, p.speed, p.weapon, p.stance, p.sprint, p.event))
    end
    return table.concat(parts, "|")
end

local function outputData()
    if config.output_guard and (tracker.output_in_progress or tracker.output_written) then
        proxPrint("[PROX] Output already written or in progress, skipping\n")
        return
    end
    tracker.output_in_progress = true

    if #tracker.completed == 0 and #tracker.completed_tracks == 0 then
        proxPrint("[PROX] No data to output\n")
        tracker.output_in_progress = false
        return
    end

    if tracker.round.map_name == "" or tracker.round.map_name == "unknown" then
        refreshRoundInfo()
    end
    local filename = string.format("%s%s-%s-round-%d_engagements.txt",
        config.output_dir, os.date('%Y-%m-%d-%H%M%S'),
        tracker.round.map_name, tracker.round.round_num)

    proxPrint("[PROX] Attempting to write: " .. filename .. "\n")

    local fd, len = et.trap_FS_FOpenFile(filename, 1)
    if not fd or fd == -1 or fd == 0 then
        et.G_Print("[PROX] ERROR: Could not open file: " .. filename .. "\n")
        tracker.output_in_progress = false
        return
    end

    -- ===== HEADER =====
    local header = string.format(
        "# PROXIMITY_TRACKER_V5\n" ..
        "# map=%s\n" ..
        "# round=%d\n" ..
        "# crossfire_window=%d\n" ..
        "# escape_time=%d\n" ..
        "# escape_distance=%d\n" ..
        "# position_sample_interval=%d\n" ..
        "# round_start_unix=%d\n" ..
        "# round_end_unix=%d\n" ..
        "# axis_spawn_interval=%d\n" ..
        "# allies_spawn_interval=%d\n",
        tracker.round.map_name, tracker.round.round_num,
        config.crossfire_window_ms, config.escape_time_ms, config.escape_distance,
        config.position_sample_interval, round_start_unix, round_end_unix,
        tracker.spawn.axis_interval, tracker.spawn.allies_interval)
    et.trap_FS_Write(header, string.len(header), fd)

    -- ===== ENGAGEMENTS (v4) =====
    local fmt_header = "# ENGAGEMENTS\n" ..
        "# id;start_time;end_time;duration;target_guid;target_name;target_team;" ..
        "outcome;total_damage;killer_guid;killer_name;num_attackers;" ..
        "is_crossfire;crossfire_delay;crossfire_participants;" ..
        "start_x;start_y;start_z;end_x;end_y;end_z;distance_traveled;" ..
        "positions;attackers\n"
    et.trap_FS_Write(fmt_header, string.len(fmt_header), fd)

    for _, eng in ipairs(tracker.completed) do
        local cf_participants = eng.crossfire_participants and table.concat(eng.crossfire_participants, ",") or ""
        local line = string.format(
            "%d;%d;%d;%d;%s;%s;%s;%s;%d;%s;%s;%d;%s;%s;%s;%.1f;%.1f;%.1f;%.1f;%.1f;%.1f;%.1f;%s;%s\n",
            eng.id, eng.start_time, eng.end_time or 0, eng.duration or 0,
            eng.target_guid, eng.target_name, eng.target_team,
            eng.outcome or "unknown", eng.total_damage,
            eng.killer_guid or "", eng.killer_name or "", #eng.attacker_order,
            eng.is_crossfire and "1" or "0", eng.crossfire_delay or "", cf_participants,
            eng.start_pos and eng.start_pos.x or 0, eng.start_pos and eng.start_pos.y or 0,
            eng.start_pos and eng.start_pos.z or 0,
            eng.end_pos and eng.end_pos.x or 0, eng.end_pos and eng.end_pos.y or 0,
            eng.end_pos and eng.end_pos.z or 0,
            eng.distance_traveled or 0,
            serializePositions(eng.position_path),
            serializeAttackers(eng.attackers, eng.attacker_order))
        et.trap_FS_Write(line, string.len(line), fd)
    end

    -- ===== PLAYER TRACKS (v4) =====
    local track_header = "\n# PLAYER_TRACKS\n" ..
        "# guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path\n" ..
        "# death_type: killed|selfkill|fallen|world|teamkill|round_end|disconnect|unknown\n" ..
        "# path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |\n" ..
        "# stance: 0=standing, 1=crouching, 2=prone | sprint: 0=no, 1=yes\n"
    et.trap_FS_Write(track_header, string.len(track_header), fd)

    for _, track in ipairs(tracker.completed_tracks) do
        local line = string.format("%s;%s;%s;%s;%d;%d;%s;%s;%d;%s\n",
            track.guid, track.name, track.team, track.class,
            track.spawn_time, track.death_time or 0,
            track.first_move_time or "", track.death_type or "unknown",
            #track.path, serializeTrackPath(track.path))
        et.trap_FS_Write(line, string.len(line), fd)
    end

    -- ===== KILL HEATMAP (v4) =====
    local hm_header = "\n# KILL_HEATMAP\n# grid_x;grid_y;axis_kills;allies_kills\n"
    et.trap_FS_Write(hm_header, string.len(hm_header), fd)
    for key, data in pairs(tracker.kill_heatmap) do
        local gx, gy = string.match(key, "(-?%d+),(-?%d+)")
        et.trap_FS_Write(string.format("%s;%s;%d;%d\n", gx, gy, data.axis, data.allies),
            string.len(string.format("%s;%s;%d;%d\n", gx, gy, data.axis, data.allies)), fd)
    end

    -- ===== MOVEMENT HEATMAP (v4) =====
    local mv_header = "\n# MOVEMENT_HEATMAP\n# grid_x;grid_y;traversal;combat;escape\n"
    et.trap_FS_Write(mv_header, string.len(mv_header), fd)
    for key, data in pairs(tracker.movement_heatmap) do
        local gx, gy = string.match(key, "(-?%d+),(-?%d+)")
        local line = string.format("%s;%s;%d;%d;%d\n", gx, gy, data.traversal, data.combat, data.escape)
        et.trap_FS_Write(line, string.len(line), fd)
    end

    -- ===== OBJECTIVE FOCUS (v4) =====
    if config.objective_tracking and next(tracker.objective_stats) then
        local obj_header = "\n# OBJECTIVE_FOCUS\n# guid;name;team;objective;avg_distance;time_within_radius_ms;samples\n"
        et.trap_FS_Write(obj_header, string.len(obj_header), fd)
        for guid, stats in pairs(tracker.objective_stats) do
            local top_obj, top_count = "", 0
            for name, count in pairs(stats.objective_counts or {}) do
                if count > top_count then top_obj = name; top_count = count end
            end
            local avg_dist = stats.samples > 0 and (stats.distance_sum / stats.samples) or 0
            local line = string.format("%s;%s;%s;%s;%.1f;%d;%d\n",
                guid, stats.name, stats.team, top_obj, avg_dist,
                stats.time_within_radius_ms or 0, stats.samples or 0)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== REACTION METRICS (v4) =====
    if isFeatureEnabled("reaction_tracking") and #tracker.reaction_metrics > 0 then
        local reaction_header = "\n# REACTION_METRICS\n" ..
            "# engagement_id;target_guid;target_name;target_team;target_class;outcome;num_attackers;" ..
            "return_fire_ms;dodge_reaction_ms;support_reaction_ms;start_time;end_time;duration\n"
        et.trap_FS_Write(reaction_header, string.len(reaction_header), fd)
        for _, m in ipairs(tracker.reaction_metrics) do
            local line = string.format("%d;%s;%s;%s;%s;%s;%d;%s;%s;%s;%d;%d;%d\n",
                m.engagement_id or 0, m.target_guid or "", m.target_name or "",
                m.target_team or "", m.target_class or "UNKNOWN", m.outcome or "unknown",
                m.num_attackers or 0,
                m.return_fire_ms ~= nil and tostring(m.return_fire_ms) or "",
                m.dodge_reaction_ms ~= nil and tostring(m.dodge_reaction_ms) or "",
                m.support_reaction_ms ~= nil and tostring(m.support_reaction_ms) or "",
                m.start_time or 0, m.end_time or 0, m.duration or 0)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- =============================================================
    -- ===== v5 TEAMPLAY OUTPUT SECTIONS =====
    -- =============================================================

    -- ===== SPAWN TIMING =====
    if isFeatureEnabled("spawn_timing") and #tracker.spawn.kill_timings > 0 then
        local st_header = "\n# SPAWN_TIMING\n" ..
            "# killer_guid;killer_name;killer_team;victim_guid;victim_name;victim_team;" ..
            "kill_time;enemy_spawn_interval;time_to_next_spawn;spawn_timing_score\n"
        et.trap_FS_Write(st_header, string.len(st_header), fd)
        for _, t in ipairs(tracker.spawn.kill_timings) do
            local line = string.format("%s;%s;%s;%s;%s;%s;%d;%d;%d;%.3f\n",
                t.killer_guid, t.killer_name, t.killer_team,
                t.victim_guid, t.victim_name, t.victim_team,
                t.kill_time, t.enemy_spawn_interval, t.time_to_next_spawn, t.spawn_timing_score)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== TEAM COHESION =====
    if isFeatureEnabled("team_cohesion") and #tracker.cohesion.samples > 0 then
        local tc_header = "\n# TEAM_COHESION\n" ..
            "# time;team;alive_count;centroid_x;centroid_y;dispersion;max_spread;straggler_count;buddy_pair_guids;buddy_distance\n"
        et.trap_FS_Write(tc_header, string.len(tc_header), fd)
        for _, s in ipairs(tracker.cohesion.samples) do
            local line = string.format("%d;%s;%d;%.1f;%.1f;%.1f;%.1f;%d;%s;%.1f\n",
                s.time, s.team, s.alive_count, s.centroid_x, s.centroid_y,
                s.dispersion, s.max_spread, s.straggler_count,
                s.buddy_pair_guids, s.buddy_distance)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== CROSSFIRE OPPORTUNITIES =====
    if isFeatureEnabled("crossfire_opportunities") then
        -- Flush any remaining pending
        flushCrossfireOpps(gameTime() + 999999)

        if #tracker.crossfire_opps.events > 0 then
            local cf_header = "\n# CROSSFIRE_OPPORTUNITIES\n" ..
                "# time;target_guid;target_name;target_team;teammate1_guid;teammate2_guid;" ..
                "angular_separation;was_executed;damage_within_window\n"
            et.trap_FS_Write(cf_header, string.len(cf_header), fd)
            for _, e in ipairs(tracker.crossfire_opps.events) do
                local line = string.format("%d;%s;%s;%s;%s;%s;%.1f;%s;%d\n",
                    e.time, e.target_guid, e.target_name, e.target_team,
                    e.teammate1_guid, e.teammate2_guid,
                    e.angular_separation, e.was_executed, e.damage_within_window)
                et.trap_FS_Write(line, string.len(line), fd)
            end
        end
    end

    -- ===== FOCUS FIRE =====
    if isFeatureEnabled("focus_fire") and #tracker.focus_fire.events > 0 then
        local ff_header = "\n# FOCUS_FIRE\n" ..
            "# engagement_id;target_guid;target_name;attacker_count;attacker_guids;total_damage;duration;focus_score\n"
        et.trap_FS_Write(ff_header, string.len(ff_header), fd)
        for _, e in ipairs(tracker.focus_fire.events) do
            local line = string.format("%d;%s;%s;%d;%s;%d;%d;%.3f\n",
                e.engagement_id, e.target_guid, e.target_name,
                e.attacker_count, e.attacker_guids, e.total_damage,
                e.duration, e.focus_score)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== TEAM PUSHES =====
    if isFeatureEnabled("team_push_detection") then
        -- Close any active pushes
        local now = gameTime()
        for team_num = 1, 2 do
            if tracker.pushes.active[team_num] then
                local push = tracker.pushes.active[team_num]
                push.end_time = now
                table.insert(tracker.pushes.events, push)
                tracker.pushes.active[team_num] = nil
            end
        end

        if #tracker.pushes.events > 0 then
            local tp_header = "\n# TEAM_PUSHES\n" ..
                "# start_time;end_time;team;avg_speed;direction_x;direction_y;" ..
                "alignment_score;push_quality;participant_count;toward_objective\n"
            et.trap_FS_Write(tp_header, string.len(tp_header), fd)
            for _, p in ipairs(tracker.pushes.events) do
                local line = string.format("%d;%d;%s;%.1f;%.3f;%.3f;%.3f;%.3f;%d;%s\n",
                    p.start_time, p.end_time or now, p.team, p.avg_speed,
                    p.direction_x, p.direction_y, p.alignment_score, p.push_quality,
                    p.participant_count, p.toward_objective or "N/A")
                et.trap_FS_Write(line, string.len(line), fd)
            end
        end
    end

    -- ===== TRADE KILLS =====
    if isFeatureEnabled("trade_kills") and #tracker.trade_kills.events > 0 then
        local tk_header = "\n# TRADE_KILLS\n" ..
            "# original_kill_time;traded_kill_time;delta_ms;" ..
            "original_victim_guid;original_victim_name;original_killer_guid;original_killer_name;" ..
            "trader_guid;trader_name\n"
        et.trap_FS_Write(tk_header, string.len(tk_header), fd)
        for _, t in ipairs(tracker.trade_kills.events) do
            local line = string.format("%d;%d;%d;%s;%s;%s;%s;%s;%s\n",
                t.original_kill_time, t.traded_kill_time, t.delta_ms,
                t.original_victim_guid, t.original_victim_name,
                t.original_killer_guid, t.original_killer_name,
                t.trader_guid, t.trader_name)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    et.trap_FS_FCloseFile(fd)

    -- Summary
    local crossfire_count = 0
    for _, eng in ipairs(tracker.completed) do
        if eng.is_crossfire then crossfire_count = crossfire_count + 1 end
    end
    local total_samples = 0
    for _, track in ipairs(tracker.completed_tracks) do
        total_samples = total_samples + #track.path
    end

    proxPrint(string.format("[PROX v5] Saved: %d tracks (%d samples), %d engagements (%d crossfire)\n",
        #tracker.completed_tracks, total_samples, #tracker.completed, crossfire_count))

    -- v5 summary
    proxPrint(string.format("[PROX v5] Teamplay: %d spawn timings, %d cohesion samples, %d crossfire opps, %d focus fire, %d pushes, %d trades\n",
        #tracker.spawn.kill_timings,
        #tracker.cohesion.samples,
        #tracker.crossfire_opps.events,
        #tracker.focus_fire.events,
        #tracker.pushes.events,
        #tracker.trade_kills.events))

    if isFeatureEnabled("reaction_tracking") then
        proxPrint(string.format("[PROX v5] Reaction metrics: %d rows\n", #tracker.reaction_metrics))
    end
    proxPrint(string.format("[PROX v5] Output: %s\n", filename))

    if config.test_mode.enabled and config.test_mode.lifecycle_log then
        outputLifecycleLog()
    end

    tracker.output_in_progress = false
    tracker.output_written = true
end

-- ===== LIFECYCLE LOG OUTPUT (v4.1) =====

outputLifecycleLog = function()
    if #tracker.completed_tracks == 0 then
        et.G_Print("[PROX] No lifecycle data to output\n")
        return
    end
    local filename = string.format("%s%s-%s-round-%d_lifecycle.txt",
        config.output_dir, os.date('%Y-%m-%d-%H%M%S'),
        tracker.round.map_name, tracker.round.round_num)
    proxPrint("[PROX] Writing lifecycle log: " .. filename .. "\n")
    local fd, len = et.trap_FS_FOpenFile(filename, 1)
    if not fd or fd == -1 or fd == 0 then
        et.G_Print("[PROX] ERROR: Could not open lifecycle log file\n")
        return
    end
    local header = string.format(
        "# PROXIMITY_TRACKER v%s - LIFECYCLE LOG\n# map=%s round=%d\n# Generated: %s\n#\n\n",
        version, tracker.round.map_name, tracker.round.round_num, os.date('%Y-%m-%d %H:%M:%S'))
    et.trap_FS_Write(header, string.len(header), fd)

    for _, track in ipairs(tracker.completed_tracks) do
        local timeline = {}
        for _, sample in ipairs(track.path) do
            table.insert(timeline, { time = sample.time, source = "path", data = sample })
        end
        if track.actions then
            for _, action in ipairs(track.actions) do
                table.insert(timeline, { time = action.time, source = "action", data = action })
            end
        end
        table.sort(timeline, function(a, b) return a.time < b.time end)

        local spawn_pos = track.spawn_pos or {x=0, y=0, z=0}
        local spawn_line = string.format("[SPAWN] guid=%s name=%s team=%s class=%s pos=(%.0f,%.0f,%.0f) time=%d\n",
            track.guid, track.name, track.team, track.class,
            spawn_pos.x, spawn_pos.y, spawn_pos.z, track.spawn_time)
        et.trap_FS_Write(spawn_line, string.len(spawn_line), fd)

        for _, entry in ipairs(timeline) do
            local delta = entry.time - track.spawn_time
            local line = ""
            if entry.source == "path" then
                local p = entry.data
                if p.event == "spawn" then
                    -- skip
                elseif p.event == "revived" then
                    line = string.format("  +%dms: EVENT type=revived pos=(%.0f,%.0f,%.0f) health=%d\n",
                        delta, p.x, p.y, p.z, p.health)
                elseif p.event == "sample" then
                    line = string.format("  +%dms: MOVE pos=(%.0f,%.0f,%.0f) speed=%.1f health=%d\n",
                        delta, p.x, p.y, p.z, p.speed, p.health)
                end
            elseif entry.source == "action" then
                local a = entry.data
                if a.type == "dmg_recv" then
                    line = string.format("  +%dms: ACTION type=dmg_recv amount=%d from=%s weapon=%d\n",
                        delta, a.amount, a.from_name or "?", a.weapon or 0)
                elseif a.type == "dmg_dealt" then
                    line = string.format("  +%dms: ACTION type=dmg_dealt amount=%d to=%s weapon=%d\n",
                        delta, a.amount, a.to_name or "?", a.weapon or 0)
                end
            end
            if line ~= "" then et.trap_FS_Write(line, string.len(line), fd) end
        end

        local death_pos = track.death_pos or {x=0, y=0, z=0}
        local duration = (track.death_time or track.spawn_time) - track.spawn_time
        local killer_str = track.killer_name and (" killer=" .. track.killer_name) or ""
        local end_line = string.format("[END] guid=%s type=%s%s pos=(%.0f,%.0f,%.0f) time=%d duration=%dms\n\n",
            track.guid, track.death_type or "unknown", killer_str,
            death_pos.x, death_pos.y, death_pos.z, track.death_time or 0, duration)
        et.trap_FS_Write(end_line, string.len(end_line), fd)
    end

    et.trap_FS_FCloseFile(fd)
    et.G_Print(string.format("[PROX] Lifecycle log: %d lifecycles written\n", #tracker.completed_tracks))
end

-- ===== ENGINE CALLBACKS =====

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)

    if not config.output_dir or config.output_dir == "" then
        config.output_dir = "proximity/"
    end
    if config.output_dir:sub(-1) ~= "/" then
        config.output_dir = config.output_dir .. "/"
    end

    refreshRoundInfo()
    tracker.round.start_time = levelTime
    -- Set fallback unix timestamp now; et_RunFrame will overwrite on warmup→live transition
    round_start_unix = os.time()
    round_end_unix = 0
    tracker.output_written = false
    tracker.output_in_progress = false
    tracker.output_pending = false
    tracker.output_due_ms = 0

    client_cache = {}

    -- Reset v4 data
    tracker.engagements = {}
    tracker.completed = {}
    tracker.kill_heatmap = {}
    tracker.movement_heatmap = {}
    tracker.engagement_counter = 0
    tracker.last_positions = {}
    tracker.player_tracks = {}
    tracker.completed_tracks = {}
    tracker.last_sample_time = 0
    tracker.last_stamina = {}
    tracker.action_buffer = {}
    tracker.objective_stats = {}
    tracker.reaction_metrics = {}

    -- Reset v5 teamplay data
    tracker.spawn.kill_timings = {}
    tracker.cohesion.samples = {}
    tracker.cohesion.last_check_time = 0
    tracker.crossfire_opps.events = {}
    tracker.crossfire_opps.pending = {}
    tracker.crossfire_opps.last_check_time = 0
    tracker.focus_fire.events = {}
    tracker.pushes.events = {}
    tracker.pushes.active = {}
    tracker.pushes.last_check_time = 0
    tracker.trade_kills.events = {}
    tracker.trade_kills.recent_kills = {}

    -- Read spawn timers
    refreshSpawnTimers()

    et.G_Print(">>> Proximity Tracker v" .. version .. " initialized\n")
    et.G_Print(">>> Map: " .. tracker.round.map_name .. ", Round: " .. tracker.round.round_num .. "\n")
    et.G_Print(">>> Position sample: " .. config.position_sample_interval .. "ms\n")
    et.G_Print(">>> Spawn timers: Axis=" .. tracker.spawn.axis_interval .. "ms, Allies=" .. tracker.spawn.allies_interval .. "ms\n")
    et.G_Print(">>> Output: " .. config.output_dir .. "\n")
    logObjectiveConfigSummary()

    -- v5 feature status
    local v5_features = {"spawn_timing", "team_cohesion", "crossfire_opportunities", "focus_fire", "team_push_detection", "trade_kills"}
    local enabled_list = {}
    for _, f in ipairs(v5_features) do
        if isFeatureEnabled(f) then table.insert(enabled_list, f) end
    end
    et.G_Print(">>> v5 Teamplay: " .. (#enabled_list > 0 and table.concat(enabled_list, ", ") or "NONE") .. "\n")

    if config.test_mode.enabled then
        et.G_Print(">>> TEST MODE ENABLED\n")
    end
end

local last_gamestate = -1

function et_RunFrame(levelTime)
    if not config.enabled then return end

    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1

    -- Detect round start
    if gamestate == 0 and last_gamestate ~= 0 then
        refreshRoundInfo()
        refreshSpawnTimers()
        round_start_unix = os.time()
        round_end_unix = 0
        tracker.output_written = false
        tracker.output_in_progress = false
        tracker.output_pending = false
        tracker.output_due_ms = 0
    end

    -- Detect round end
    if last_gamestate == 0 and gamestate == 3 then
        round_end_unix = os.time()

        -- End all active player tracks
        for clientnum, track in pairs(tracker.player_tracks) do
            local pos = getPlayerPos(clientnum)
            track.death_time = gameTime()
            track.death_pos = pos
            track.death_type = "round_end"
            if pos then
                table.insert(track.path, {
                    time = track.death_time, x = round(pos.x, 1), y = round(pos.y, 1), z = round(pos.z, 1),
                    health = safe_gentity_get(clientnum, "health") or 0,
                    speed = 0, weapon = safe_gentity_get(clientnum, "ps.weapon") or 0,
                    stance = 0, sprint = 0, event = "round_end"
                })
            end
            table.insert(tracker.completed_tracks, track)
            tracker.last_stamina[clientnum] = nil
        end
        tracker.player_tracks = {}

        -- Close all active engagements
        local active_targets = {}
        for target_slot, _ in pairs(tracker.engagements) do
            table.insert(active_targets, target_slot)
        end
        for _, target_slot in ipairs(active_targets) do
            local engagement = tracker.engagements[target_slot]
            if engagement then closeEngagement(engagement, "round_end", nil) end
        end

        if config.output_delay_ms and config.output_delay_ms > 0 then
            tracker.output_pending = true
            tracker.output_due_ms = et.trap_Milliseconds() + config.output_delay_ms
        else
            outputData()
        end
    end

    last_gamestate = gamestate

    -- During play
    if gamestate == 0 then
        sampleAllPlayers()

        if isFeatureEnabled("escape_detection") then
            checkEscapes(levelTime)
        end

        -- v5: Run teamplay analysis
        updateTeamplay(gameTime())
    end

    -- Handle delayed output
    if tracker.output_pending and et.trap_Milliseconds() >= tracker.output_due_ms then
        tracker.output_pending = false
        outputData()
    end
end

function et_Damage(target, attacker, damage, damageFlags, meansOfDeath)
    if not config.enabled then return end
    if not target or not attacker then return end
    if not isValidClient(target) or not isValidClient(attacker) then return end
    if target == attacker then return end
    if attacker == 1022 or attacker == 1023 then return end
    if damage < config.min_damage then return end
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end
    if not isPlayerActive(target) or not isPlayerActive(attacker) then return end

    -- Skip friendly fire — team damage should not create engagements or affect crossfire tracking
    if getPlayerTeamNum(target) == getPlayerTeamNum(attacker) then return end

    -- v4: Engagement tracking
    if isFeatureEnabled("engagement_tracking") then
        local engagement = tracker.engagements[target]
        if not engagement then engagement = createEngagement(target) end
        local weapon = safe_gentity_get(attacker, "ps.weapon") or 0
        recordHit(engagement, attacker, damage, weapon)
    end

    -- v4: Reaction tracking
    if isFeatureEnabled("reaction_tracking") then
        registerReactionSignals(target, attacker, gameTime())
    end

    -- v5: Crossfire opportunity execution check
    checkCrossfireExecution(attacker, target, damage)

    -- v4.1: Action annotation for test mode
    if config.test_mode.enabled and config.test_mode.action_annotations then
        local now = gameTime()
        local weapon = safe_gentity_get(attacker, "ps.weapon") or 0
        local target_track = tracker.player_tracks[target]
        if target_track then
            table.insert(target_track.actions, {
                time = now, type = "dmg_recv", amount = damage,
                from_guid = getPlayerGUID(attacker), from_name = getPlayerName(attacker), weapon = weapon
            })
        end
        local attacker_track = tracker.player_tracks[attacker]
        if attacker_track then
            table.insert(attacker_track.actions, {
                time = now, type = "dmg_dealt", amount = damage,
                to_guid = getPlayerGUID(target), to_name = getPlayerName(target), weapon = weapon
            })
        end
    end
end

function et_Obituary(victim, killer, meansOfDeath)
    if not config.enabled then return end
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end

    local death_type = getDeathType(victim, killer, meansOfDeath)
    local killer_name = nil
    if killer and killer ~= 1022 and killer ~= 1023 and killer ~= victim and isPlayerActive(killer) then
        killer_name = getPlayerName(killer)
    end

    -- End player track
    local death_pos = getPlayerPos(victim)
    endPlayerTrack(victim, death_pos, death_type, killer_name)

    -- v4: Engagement tracking
    if isFeatureEnabled("engagement_tracking") then
        local engagement = tracker.engagements[victim]
        if engagement then
            closeEngagement(engagement, "killed", killer)
        else
            engagement = createEngagement(victim)
            if killer and killer ~= 1022 and killer ~= 1023 and killer ~= victim then
                local weapon = safe_gentity_get(killer, "ps.weapon") or 0
                recordHit(engagement, killer, 100, weapon)
            end
            closeEngagement(engagement, "killed", killer)
        end
    end

    -- v5: Spawn timing + trade kills (only for enemy kills, not selfkills/world/teamkills)
    if killer and killer ~= 1022 and killer ~= 1023 and killer ~= victim
        and isValidClient(killer) and isPlayerActive(killer)
        and getPlayerTeamNum(killer) ~= getPlayerTeamNum(victim) then
        local now = gameTime()

        -- Spawn timing score
        recordSpawnTiming(killer, victim, now)

        -- Trade kill detection
        checkTradeKill(killer, victim, now)
    end
end

function et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)
    if not config.enabled then return end
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end

    if revived == 1 then
        if config.test_mode.enabled and config.test_mode.action_annotations then
            local track = tracker.player_tracks[clientNum]
            if track then
                local now = gameTime()
                local pos = getPlayerPos(clientNum)
                if pos then
                    local health = safe_gentity_get(clientNum, "health") or 100
                    local weapon = safe_gentity_get(clientNum, "ps.weapon") or 0
                    local stance, sprint = getPlayerMovementState(clientNum, 0)
                    table.insert(track.path, {
                        time = now, x = round(pos.x, 1), y = round(pos.y, 1), z = round(pos.z, 1),
                        health = health, speed = 0, weapon = weapon,
                        stance = stance, sprint = sprint, event = "revived"
                    })
                end
            end
        end
        return
    end

    if not isPlayerActive(clientNum) then return end
    if tracker.player_tracks[clientNum] then
        endPlayerTrack(clientNum, nil, nil)
    end
    createPlayerTrack(clientNum)
end

function et_ClientDisconnect(clientNum)
    if tracker.player_tracks[clientNum] then
        local pos = getPlayerPos(clientNum)
        endPlayerTrack(clientNum, pos, "disconnect")
    end
    tracker.last_stamina[clientNum] = nil
    client_cache[clientNum] = nil
end

function et_ClientConnect(clientNum, firstTime, isBot)
    updateClientCache(clientNum)
    return nil
end

function et_ClientUserinfoChanged(clientNum)
    updateClientCache(clientNum)
end

-- ===== MODULE END =====
et.G_Print(">>> Proximity Tracker v" .. version .. " loaded\n")
