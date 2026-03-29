-- ============================================================
-- PROXIMITY TRACKER v6.01 - OBJECTIVE RUN INTELLIGENCE
-- ET:Legacy Lua Module for Combat, Team Coordination & Objective Analytics
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
local version = "6.01"

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
        adlernest = {
            { name = "allied_cp", x = -412, y = -2064, z = 128, type = "command_post" },
            { name = "transmitter", x = -298, y = -3288, z = 12, type = "objective" },
            { name = "documents", x = -676, y = 672, z = 108, type = "objective" },
            { name = "health_and_ammo_cabinets", x = 1830, y = 992, z = 12, type = "objective" },
        },
        battery = {},
        braundorf_b4 = {
            { name = "command_post", x = 4776, y = -256, z = 403, type = "command_post" },
            { name = "health_and_ammo_cabinets", x = 1094, y = -4170, z = 417, type = "objective" },
            { name = "the_side_gate", x = 4352, y = 896, z = 152, type = "objective" },
        },
        bremen_b2 = {},
        bremen_b3 = {
            { name = "neutral_command_post", x = 2320, y = 2432, z = 366, type = "command_post" },
            { name = "side_door", x = -1476, y = 1954, z = 296, type = "objective" },
            { name = "keycard", x = 1260, y = 88, z = 240, type = "objective" },
            { name = "truck", x = 1716, y = -924, z = 130, type = "escort" },
            { name = "truck_barrier_1", x = 1744, y = 376, z = 160, type = "escort" },
            { name = "truck_barrier_2", x = -1428, y = 320, z = 113, type = "escort" },
            { name = "wooden_barrier", x = 1560, y = 8, z = 112, type = "objective" },
            { name = "generator", x = 674, y = 2624, z = 140, type = "objective" },
        },
        default = {},
        dubrovnik_final = {},
        erdenberg_t1 = {},
        erdenberg_t2 = {
            { name = "neutral_command_post", x = 5568, y = -2264, z = -382, type = "command_post" },
        },
        et_beach = {},
        et_ice = {},
        et_ufo_final = {},
        etl_adlernest = {
            { name = "transmitter", x = -298, y = -3288, z = 24, type = "objective" },
            { name = "documents", x = -676, y = 672, z = 108, type = "objective" },
            { name = "health_and_ammo_cabinets", x = 1830, y = 992, z = 12, type = "objective" },
        },
        etl_frostbite = {},
        etl_ice = {
            { name = "transmitter", x = 328, y = -2792, z = 280, type = "objective" },
            { name = "documents", x = -6016, y = 2176, z = 1088, type = "objective" },
        },
        etl_sp_delivery = {
            { name = "axis_gold", x = -1160, y = 1332, z = 168, type = "objective" },
            { name = "getaway_trucks", x = 1456, y = 4280, z = -56, type = "escort" },
        },
        etl_supply = {
            { name = "forward_bunker_gate", x = 56, y = 2368, z = -48, type = "objective" },
            { name = "truck", x = -2368, y = 688, z = 0, type = "escort" },
            { name = "depot_fence", x = 144, y = -1792, z = 52, type = "objective" },
            { name = "command_post", x = 2432, y = 904, z = 288, type = "command_post" },
            { name = "forward_spawn_door", x = -68, y = 2368, z = 304, type = "objective" },
            { name = "crane_controls", x = 656, y = -1360, z = 372, type = "objective" },
        },
        frostbite = {
            { name = "main_door", x = -32, y = 208, z = 352, type = "objective" },
            { name = "storage_wall", x = -32, y = 208, z = 352, type = "objective" },
            { name = "transmitter", x = -4544, y = 2240, z = -96, type = "objective" },
            { name = "health_and_ammo_cabinets", x = -150, y = -662, z = 296, type = "objective" },
            { name = "platform_mg", x = -1512, y = 1868, z = 45, type = "objective" },
            { name = "axis_command_post", x = -5056, y = 1896, z = -108, type = "command_post" },
            { name = "documents", x = 816, y = 160, z = 432, type = "objective" },
            { name = "the_gramophone", x = -299, y = 1264, z = 343, type = "objective" },
            { name = "allied_command_post", x = -1836, y = 404, z = 444, type = "command_post" },
        },
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
            { name = "forward_bunker_gate", x = 56, y = 2368, z = -48, type = "objective" },
            { name = "truck", x = -2368, y = 688, z = 0, type = "escort" },
            { name = "depot_fence", x = 144, y = -1792, z = 52, type = "objective" },
            { name = "command_post", x = 2432, y = 904, z = 288, type = "command_post" },
            { name = "forward_spawn_door", x = -68, y = 2368, z = 304, type = "objective" },
            { name = "crane_controls", x = 656, y = -1360, z = 372, type = "objective" },
        },
        supplydepot2 = {},
        sw_battery = {
            { name = "axis_south_east_mg", x = 4248, y = -4864, z = 1056, type = "objective" },
            { name = "axis_north_west_mg", x = 1992, y = -4018, z = 1180, type = "objective" },
            { name = "gun_controls", x = 3200, y = -2924, z = 1016, type = "objective" },
            { name = "allied_west_mg", x = 992, y = -992, z = 152, type = "objective" },
            { name = "allied_east_mg", x = 4012, y = -1100, z = 264, type = "objective" },
            { name = "command_post", x = 6172, y = -3652, z = 1192, type = "command_post" },
            { name = "generator", x = 3986, y = -5122, z = 1036, type = "objective" },
            { name = "health_and_ammo_cabinets", x = 3506, y = -4926, z = 1226, type = "objective" },
            { name = "backdoor_barrier", x = 4600, y = -4640, z = 1132, type = "objective" },
        },
        sw_goldrush_te = {
            { name = "tank_barrier", x = 688, y = 184, z = -11, type = "escort" },
            { name = "jagdpanther", x = -272, y = 2200, z = 416, type = "objective" },
            { name = "command_post", x = 1336, y = 264, z = 284, type = "command_post" },
            { name = "bank_doors", x = 1600, y = -1948, z = -214, type = "objective" },
            { name = "gold_bars", x = 2480, y = -2248, z = -296, type = "objective" },
            { name = "health_and_ammo_cabinets", x = -1884, y = 1984, z = 244, type = "objective" },
            { name = "truck", x = 2315, y = 1047, z = -352, type = "escort" },
            { name = "truck_barrier", x = 1920, y = 40, z = -368, type = "escort" },
        },
        sw_oasis_b3 = {
            { name = "axis_command_post", x = 8577, y = 5696, z = -120, type = "command_post" },
            { name = "old_city_wall", x = 4896, y = 7586, z = -420, type = "objective" },
            { name = "allied_command_post", x = 2393, y = 4678, z = -232, type = "command_post" },
            { name = "health_and_ammo_cabinets", x = 4182, y = 7470, z = -456, type = "objective" },
        },
        tc_base = {},
        te_escape2 = {
            { name = "secret_exit", x = -6165, y = 1606, z = -20, type = "objective" },
            { name = "command_post", x = -3340, y = 1372, z = 252, type = "command_post" },
            { name = "health_and_ammo_cabinets", x = -2362, y = 990, z = 17, type = "objective" },
            { name = "holy_grail", x = -5828, y = -228, z = -24, type = "objective" },
        },
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
        kill_outcome_tracking = true,
        hit_region_tracking = true,
        combat_positions = true,
        -- v6 objective intelligence
        carrier_tracking = true,
        carrier_returns = true,
        vehicle_tracking = true,
        construction_tracking = true,
        objective_run_tracking = true,
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

        -- Safety cap for pending crossfire opportunities (FIFO eviction above this)
        max_crossfire_pending = 200,

        -- v6: Carrier tracking
        carrier_sample_interval_ms = 200,
        carrier_return_timeout_ms = 35000,
    },

    -- ===== v6 VEHICLE CONFIG =====
    vehicle = {
        sample_interval_ms = 500,
        escort_radius = 500,
        min_move_speed = 5,
        known_script_names = {"tank", "truck", "Tank", "Truck", "tank1", "tank2", "truck1", "truck2"},
    },

    -- Objective Run Intelligence (v6.01)
    objective_run = {
        path_clear_radius = 800,
        path_clear_window_ms = 30000,
        constructible_poll_interval_ms = 1000,
        denied_run_radius = 500,
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

-- ===== MOD → WEAPON MAPPING =====
-- Maps meansOfDeath_t → weapon_t for accurate weapon attribution.
-- meansOfDeath is always correct (set by the engine when damage occurs),
-- unlike ps.weapon which reflects the currently held weapon and can be wrong
-- for delayed-damage weapons (grenades, artillery, mines, etc).
-- Source: etlegacy/src/game/bg_public.h meansOfDeath_t + weapon_t enums
local MOD_TO_WEAPON = {
    [4] = 4,     -- MOD_GRENADE → WP_GRENADE_LAUNCHER
    [5] = 1,     -- MOD_KNIFE → WP_KNIFE
    [6] = 2,     -- MOD_LUGER → WP_LUGER
    [7] = 7,     -- MOD_COLT → WP_COLT
    [8] = 3,     -- MOD_MP40 → WP_MP40
    [9] = 8,     -- MOD_THOMPSON → WP_THOMPSON
    [10] = 10,   -- MOD_STEN → WP_STEN
    [11] = 25,   -- MOD_GARAND → WP_GARAND
    [12] = 14,   -- MOD_SILENCER → WP_SILENCER
    [13] = 32,   -- MOD_FG42 → WP_FG42
    [14] = 42,   -- MOD_FG42SCOPE → WP_FG42_SCOPE
    [15] = 5,    -- MOD_PANZERFAUST → WP_PANZERFAUST
    [16] = 4,    -- MOD_GRENADE_LAUNCHER → WP_GRENADE_LAUNCHER
    [17] = 6,    -- MOD_FLAMETHROWER → WP_FLAMETHROWER
    [18] = 9,    -- MOD_GRENADE_PINEAPPLE → WP_GRENADE_PINEAPPLE
    [19] = 17,   -- MOD_MAPMORTAR → WP_MAPMORTAR
    [20] = 17,   -- MOD_MAPMORTAR_SPLASH → WP_MAPMORTAR
    [22] = 15,   -- MOD_DYNAMITE → WP_DYNAMITE
    [23] = 55,   -- MOD_AIRSTRIKE → WP_AIRSTRIKE
    [24] = 11,   -- MOD_SYRINGE → WP_MEDIC_SYRINGE
    [25] = 12,   -- MOD_AMMO → WP_AMMO
    [26] = 13,   -- MOD_ARTY → WP_ARTY
    [37] = 24,   -- MOD_CARBINE → WP_CARBINE
    [38] = 23,   -- MOD_KAR98 → WP_KAR98
    [39] = 37,   -- MOD_GPG40 → WP_GPG40
    [40] = 38,   -- MOD_M7 → WP_M7
    [41] = 26,   -- MOD_LANDMINE → WP_LANDMINE
    [42] = 27,   -- MOD_SATCHEL → WP_SATCHEL
    [43] = 29,   -- MOD_SMOKEBOMB → WP_SMOKE_BOMB
    [44] = 30,   -- MOD_MOBILE_MG42 → WP_MOBILE_MG42
    [45] = 39,   -- MOD_SILENCED_COLT → WP_SILENCED_COLT
    [46] = 40,   -- MOD_GARAND_SCOPE → WP_GARAND_SCOPE
    [50] = 31,   -- MOD_K43 → WP_K43
    [51] = 41,   -- MOD_K43_SCOPE → WP_K43_SCOPE
    [52] = 34,   -- MOD_MORTAR → WP_MORTAR
    [53] = 35,   -- MOD_AKIMBO_COLT → WP_AKIMBO_COLT
    [54] = 36,   -- MOD_AKIMBO_LUGER → WP_AKIMBO_LUGER
    [55] = 45,   -- MOD_AKIMBO_SILENCEDCOLT → WP_AKIMBO_SILENCEDCOLT
    [56] = 46,   -- MOD_AKIMBO_SILENCEDLUGER → WP_AKIMBO_SILENCEDLUGER
    [57] = 29,   -- MOD_SMOKEGRENADE → WP_SMOKE_BOMB
    [61] = 48,   -- MOD_KNIFE_KABAR → WP_KNIFE_KABAR
    [62] = 49,   -- MOD_MOBILE_BROWNING → WP_MOBILE_BROWNING
    [63] = 51,   -- MOD_MORTAR2 → WP_MORTAR2
    [64] = 53,   -- MOD_BAZOOKA → WP_BAZOOKA
    [65] = 1,    -- MOD_BACKSTAB → WP_KNIFE
    [66] = 54,   -- MOD_MP34 → WP_MP34
}

-- Hit region tracking: hitRegion_t enum from ET:Legacy source (g_local.h).
-- pers.playerStats.hitRegions[HR_*] is incremented by G_LogRegionHit()
-- BEFORE the Lua et_Damage hook fires (g_combat.c:1689 vs 1811).
-- We detect hit region by comparing delta across all 4 regions.
local HR_HEAD = 0
local HR_ARMS = 1
local HR_BODY = 2
local HR_LEGS = 3
local HR_NUM_HITREGIONS = 4
local HR_NAMES = { [0] = "HEAD", [1] = "ARMS", [2] = "BODY", [3] = "LEGS" }
local last_hr_head = {}  -- [clientnum] = last known hitRegions[HR_HEAD] count (legacy, kept for compatibility)
local last_hr_all = {}   -- [clientnum] = { [0]=N, [1]=N, [2]=N, [3]=N } for hit region delta detection

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
        axis_interval = 0,          -- ms from cvar
        allies_interval = 0,        -- ms from cvar
        axis_reinf_offset = 0,      -- random 0-15s offset from CS_REINFSEEDS
        allies_reinf_offset = 0,    -- random 0-15s offset from CS_REINFSEEDS
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

    -- Revive tracking
    revives = {},               -- array of {time, medic_guid, medic_name, revived_guid, revived_name, x, y, z, distance_to_enemy, under_fire}

    -- Weapon fire tracking (for accuracy)
    weapon_fire = {},           -- [guid] = { [weapon_id] = { shots=N, hits=N, kills=N, headshots=N } }

    -- Hit region tracking (v5.2)
    hit_regions = {},           -- array of {time, attacker_guid, attacker_name, victim_guid, victim_name, weapon, region, damage}

    -- Combat position tracking (v5.2)
    combat_positions = {},      -- array of kill positions with attacker+victim coords, weapon, class, team

    -- Kill outcome tracking (v5.1)
    -- State machine: ALIVE→DEAD→gibbed/revived/tapped_out
    kill_outcomes = {
        dead_players = {},      -- [clientnum] = {kill_time, killer_guid, killer_name, kill_mod, victim_guid, victim_name, pos, body_damage}
        completed = {},         -- array of completed outcomes for output
    },

    -- v6 carrier tracking
    carrier = {
        active = {},        -- [clientNum] = {guid, name, team, flag_team, pickup_time, pickup_pos, last_pos, carry_distance, path_samples, last_sample_time}
        events = {},        -- completed carrier events for output
        kills = {},         -- carrier kill events for output
        returns = {},       -- completed return events for output
        pending_drops = {}, -- [flag_team] = {flag_team, drop_time, drop_pos, carrier_guid, carrier_name, carrier_team}
    },

    -- v6 vehicle/escort tracking
    vehicles = {
        entities = {},          -- [entNum] = {name, type, start_pos, last_pos, total_distance, max_health, last_health, destroyed_count}
        escort_credits = {},    -- [guid:vehicle_name] = {player_guid, player_name, player_team, vehicle_name, mounted_ms, proximity_ms, total_escort_dist, credit_dist, samples}
        last_check_time = 0,
    },

    -- v6 construction/destruction tracking
    construction = {
        events = {},     -- completed construction/destruction events for output
    },

    -- v6.01 objective run intelligence
    objective_runs = {
        completed = {},
        constructibles = {},   -- [entNum] = {track, x, y, z, scriptName, last_progress}
        explosives = {},       -- [entNum] = {track, x, y, z, scriptName}
        checkpoints = {},      -- [entNum] = {x, y, z, scriptName, last_team}
        last_poll = 0,
    },
}

local round_start_unix = 0
local round_end_unix = 0
local client_cache = {}
local frame_level_time = 0  -- updated each et_RunFrame; freezes during pause (unlike trap_Milliseconds)

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
    name = string.gsub(name, "\t", "_")
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
    -- Use frame_level_time (from et_RunFrame) instead of trap_Milliseconds.
    -- trap_Milliseconds is wall-clock and keeps ticking during pause;
    -- levelTime freezes during pause, giving correct game-relative timestamps.
    return frame_level_time - tracker.round.start_time
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
    -- Bug 12 fix: zero vectors (overlapping positions) would produce false 90° angle
    if (ax == 0 and ay == 0) or (bx == 0 and by == 0) then return 0 end
    local dot = clamp(ax*bx + ay*by, -1, 1)
    return math.deg(math.acos(dot))
end

-- ===== v5 LINE OF SIGHT =====
-- et.trap_Trace returns a table with .fraction in ET:Legacy Lua.
-- fraction = 1.0 means clear LOS (no solid hit).
-- We wrap in pcall for safety since Lua binding may vary by ETL version.

local last_trace_error_time = 0

local function getEyeHeight(clientnum)
    if not isValidClient(clientnum) then return 36 end
    local pm_flags = tonumber(safe_gentity_get(clientnum, "ps.pm_flags")) or 0
    if has_flag(pm_flags, PMF_PRONE) then return 12 end
    if has_flag(pm_flags, PMF_DUCKED) then return 36 end
    return 56  -- standing
end

local function hasLineOfSight(pos_a, pos_b, ignore_ent, slot_a, slot_b)
    -- Use stance-appropriate eye height for each player
    local eye_a = (slot_a and getEyeHeight(slot_a)) or 36
    local eye_b = (slot_b and getEyeHeight(slot_b)) or 36
    local start_pos = {pos_a.x, pos_a.y, pos_a.z + eye_a}
    local end_pos = {pos_b.x, pos_b.y, pos_b.z + eye_b}
    local mins = {0, 0, 0}
    local maxs = {0, 0, 0}

    -- MASK_SOLID (CONTENTS_SOLID = 0x1): LOS through world geometry only.
    -- Using MASK_SOLID instead of MASK_SHOT (0x06000001) to avoid player bodies blocking LOS checks
    -- between teammates, which would cause false negatives in crossfire detection.
    local ok, result = pcall(et.trap_Trace, start_pos, mins, maxs, end_pos, ignore_ent or -1, 1)
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

-- ===== KILL OUTCOME CONSTANTS =====
local PM_DEAD = 3
local PMF_LIMBO = 16384        -- 0x4000
local GIB_HEALTH = -175
local KILL_OUTCOME_TIMEOUT = 30000  -- cleanup stale entries after 30s

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

-- Oksii adoption: alive count per team (lightweight, no position data)
local function countAlivePerTeam()
    local axis_alive = 0
    local allies_alive = 0
    local max_clients = get_max_clients()
    for cn = 0, max_clients - 1 do
        if isPlayerActive(cn) and isPlayerAlive(cn) then
            local team = getPlayerTeamNum(cn)
            if team == 1 then axis_alive = axis_alive + 1
            elseif team == 2 then allies_alive = allies_alive + 1
            end
        end
    end
    return axis_alive, allies_alive
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

-- Forward declarations for functions defined after sampleAllPlayers but called within it
local sampleCarrierPosition
local checkCarrierPowerups
local sampleVehiclePositions

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

    -- v6: carrier position sampling + powerup polling
    if isFeatureEnabled("carrier_tracking") then
        for clientnum, _ in pairs(tracker.carrier.active) do
            sampleCarrierPosition(clientnum)
        end
        checkCarrierPowerups()
    end

    -- Phase 1.5: expire stale pending drops
    if isFeatureEnabled("carrier_returns") then
        local now = gameTime()
        for flag_team, pd in pairs(tracker.carrier.pending_drops) do
            if now - pd.drop_time > config.teamplay.carrier_return_timeout_ms then
                tracker.carrier.pending_drops[flag_team] = nil
            end
        end
    end

    -- v6: vehicle position sampling
    if isFeatureEnabled("vehicle_tracking") then
        sampleVehiclePositions()
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

        -- Compute focus_score: measures coordination quality (0-1 scale)
        -- timing_tightness: how quickly all attackers converged on the target
        -- dps_score: damage output rate (higher = faster kill via coordination)
        local min_first_hit, max_first_hit = math.huge, 0
        for _, atk in pairs(engagement.attackers) do
            if atk.first_hit then
                if atk.first_hit < min_first_hit then min_first_hit = atk.first_hit end
                if atk.first_hit > max_first_hit then max_first_hit = atk.first_hit end
            end
        end
        local spread = max_first_hit - min_first_hit
        -- 0ms spread = perfect timing (1.0), 2000ms+ spread = poor (0.0)
        local timing_tightness = 1.0 - math.min(spread / 2000, 1.0)

        local dur = math.max(engagement.duration or 100, 100)
        local dps = (engagement.total_damage / dur) * 1000  -- damage per second
        -- 500+ dps = max score (1.0), scales linearly below
        local dps_score = math.min(dps / 500, 1.0)

        local focus_score = timing_tightness * 0.6 + dps_score * 0.4

        table.insert(tracker.focus_fire.events, {
            engagement_id = engagement.id,
            target_guid = engagement.target_guid,
            target_name = engagement.target_name,
            attacker_count = #engagement.attacker_order,
            attacker_guids = guids_str,
            total_damage = engagement.total_damage,
            duration = engagement.duration or 0,
            focus_score = focus_score
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

-- Reinforcement seeds array from ET:Legacy bg_misc.c
-- Used to decode the per-team random spawn offset from CS_REINFSEEDS
local REINF_SEEDS = {11, 3, 13, 7, 2, 5, 1, 17}

local function parseReinfOffsets()
    -- CS_REINFSEEDS (configstring 31) format: "<blue_packed> <red_packed> <seed0> ... <seed7>"
    local cs = et.trap_GetConfigstring(31)
    if not cs or cs == "" then return 0, 0 end
    local parts = {}
    for token in string.gmatch(cs, "%S+") do
        table.insert(parts, tonumber(token) or 0)
    end
    if #parts < 10 then return 0, 0 end
    local blue_packed = parts[1]
    local red_packed = parts[2]
    -- Extract 0-based index into seed array (REINF_BLUEDELT=3, REINF_REDDELT=2)
    local blue_idx = math.floor(blue_packed / 8) % 8   -- >> 3, clamp 0-7
    local red_idx = math.floor(red_packed / 4) % 8      -- >> 2, clamp 0-7
    -- Seeds at parts[3..10] map to C's seeds[0..7]
    local blue_seed = parts[blue_idx + 3] or 0
    local red_seed = parts[red_idx + 3] or 0
    local blue_div = REINF_SEEDS[blue_idx + 1] or 1  -- +1 for Lua 1-indexing
    local red_div = REINF_SEEDS[red_idx + 1] or 1
    -- Offsets in ms (0 to ~15000ms)
    local allies_offset = blue_div > 0 and math.floor(1000 * blue_seed / blue_div) or 0
    local axis_offset = red_div > 0 and math.floor(1000 * red_seed / red_div) or 0
    return axis_offset, allies_offset
end

local function refreshSpawnTimers()
    -- ET:Legacy sets spawn times via map scripts (wm_axis_respawntime / wm_allied_respawntime)
    -- which store values in g_redlimbotime (Axis) and g_bluelimbotime (Allies) in MILLISECONDS.
    -- g_userAxisRespawnTime / g_userAlliedRespawnTime are admin overrides (in seconds).
    -- The old cvars g_axisSpawnTime / g_alliedSpawnTime do NOT exist in ET:Legacy.
    local axis_ms = tonumber(et.trap_Cvar_Get("g_redlimbotime")) or 0
    local allies_ms = tonumber(et.trap_Cvar_Get("g_bluelimbotime")) or 0
    -- Fallback: try user override cvars (in seconds, need *1000)
    if axis_ms <= 0 then
        local user_axis = tonumber(et.trap_Cvar_Get("g_userAxisRespawnTime")) or 0
        if user_axis > 0 then axis_ms = user_axis * 1000 end
    end
    if allies_ms <= 0 then
        local user_allies = tonumber(et.trap_Cvar_Get("g_userAlliedRespawnTime")) or 0
        if user_allies > 0 then allies_ms = user_allies * 1000 end
    end
    -- Safety: convert seconds to ms if values look like seconds (< 1000)
    if axis_ms > 0 and axis_ms < 1000 then axis_ms = axis_ms * 1000 end
    if allies_ms > 0 and allies_ms < 1000 then allies_ms = allies_ms * 1000 end
    tracker.spawn.axis_interval = axis_ms
    tracker.spawn.allies_interval = allies_ms
    -- Parse random reinforcement offsets from CS_REINFSEEDS configstring
    tracker.spawn.axis_reinf_offset, tracker.spawn.allies_reinf_offset = parseReinfOffsets()
    if config.debug then
        et.G_Printf("[PROX] Reinf offsets: Axis=%dms, Allies=%dms\n",
            tracker.spawn.axis_reinf_offset, tracker.spawn.allies_reinf_offset)
    end
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

    -- ET:Legacy spawn formula (from CG_CalculateReinfTime in cg_draw.c):
    --   time_to_next = 1 + (interval - ((reinf_offset + elapsed_time) % interval)) / 1000
    -- Where reinf_offset is a per-team random 0-15s offset set at match start via CS_REINFSEEDS.
    local reinf_offset = 0
    if victim_team_num == 1 then
        reinf_offset = tracker.spawn.axis_reinf_offset or 0
    else
        reinf_offset = tracker.spawn.allies_reinf_offset or 0
    end
    local cycle_elapsed = (reinf_offset + kill_game_time) % interval
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

    -- Oksii adoption: raw reinforcement seconds for both teams
    local killer_team_num = getPlayerTeamNum(killer_slot)
    local killer_interval = killer_team_num == 1 and tracker.spawn.axis_interval or tracker.spawn.allies_interval
    local killer_reinf_ms = 0
    if killer_interval > 0 then
        local elapsed = kill_time - (tracker.round.start_time or 0)
        local reinf_offset = (killer_team_num == 1) and (tracker.spawn.axis_offset or 0) or (tracker.spawn.allies_offset or 0)
        killer_reinf_ms = killer_interval - ((reinf_offset + elapsed) % killer_interval)
    end
    local victim_reinf_ms = time_to_next  -- already calculated above

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
        killer_reinf = round(killer_reinf_ms / 1000, 1),
        victim_reinf = round(victim_reinf_ms / 1000, 1),
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

    if #members < config.teamplay.min_team_size then return end

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
    -- Safety: FIFO eviction if pending queue exceeds cap
    local max_pending = config.teamplay.max_crossfire_pending
    while #tracker.crossfire_opps.pending > max_pending do
        local evicted = table.remove(tracker.crossfire_opps.pending, 1)
        -- Record evicted opportunity as not-executed
        table.insert(tracker.crossfire_opps.events, {
            time = evicted.detect_time,
            target_guid = evicted.target_guid,
            target_name = evicted.target_name,
            target_team = evicted.target_team,
            teammate1_guid = evicted.t1_guid,
            teammate2_guid = evicted.t2_guid,
            angular_separation = evicted.angle,
            was_executed = "0",
            damage_within_window = evicted.damage_dealt,
        })
    end

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
                        if hasLineOfSight(mate.pos, enemy.pos, mate.slot, mate.slot, enemy.slot) then
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

-- ===== v5.1 KILL OUTCOME STATE MACHINE =====

-- NOTE: finalizeKillOutcome MUST be defined before recordKillOutcomeBodyDamage
-- because Lua local functions are not visible before their definition point.

local function finalizeKillOutcome(victim_slot, outcome, resolver_guid, resolver_name)
    local info = tracker.kill_outcomes.dead_players[victim_slot]
    if not info then return end

    local now = gameTime()
    local delta_ms = now - info.kill_time

    -- Calculate effective denied time
    -- For "revived": effective = time dead until revive
    -- For "gibbed"/"tapped_out": effective = time until next spawn wave
    local effective_denied_ms = delta_ms
    if outcome == "gibbed" or outcome == "tapped_out" then
        -- Time until next spawn wave from NOW
        local victim_team_num = 0
        if isValidClient(victim_slot) then
            victim_team_num = getPlayerTeamNum(victim_slot)
        end
        local interval = 0
        local reinf_offset = 0
        if victim_team_num == 1 then
            interval = tracker.spawn.axis_interval
            reinf_offset = tracker.spawn.axis_reinf_offset or 0
        elseif victim_team_num == 2 then
            interval = tracker.spawn.allies_interval
            reinf_offset = tracker.spawn.allies_reinf_offset or 0
        end
        if interval > 0 then
            local cycle_pos = (reinf_offset + now) % interval
            local remaining = interval - cycle_pos
            effective_denied_ms = delta_ms + remaining
        end
    end

    table.insert(tracker.kill_outcomes.completed, {
        kill_time = info.kill_time,
        victim_guid = info.victim_guid,
        victim_name = info.victim_name,
        killer_guid = info.killer_guid,
        killer_name = info.killer_name,
        kill_mod = info.kill_mod,
        outcome = outcome,
        outcome_time = now,
        delta_ms = delta_ms,
        effective_denied_ms = round(effective_denied_ms, 0),
        gibber_guid = outcome == "gibbed" and info.last_damager_guid or "",
        gibber_name = outcome == "gibbed" and info.last_damager_name or "",
        reviver_guid = outcome == "revived" and (resolver_guid or "") or "",
        reviver_name = outcome == "revived" and (resolver_name or "") or "",
    })

    tracker.kill_outcomes.dead_players[victim_slot] = nil

    if config.debug then
        et.G_Printf("[PROX] Kill outcome: %s → %s (%dms, effective=%dms)\n",
            info.victim_name, outcome, delta_ms, effective_denied_ms)
    end
end

local function recordKillOutcomeDeath(victim_slot, killer_slot, meansOfDeath)
    local now = gameTime()
    local victim_guid = getPlayerGUID(victim_slot)
    local victim_name = getPlayerName(victim_slot)
    local killer_guid = (killer_slot and isValidClient(killer_slot)) and getPlayerGUID(killer_slot) or ""
    local killer_name = (killer_slot and isValidClient(killer_slot)) and getPlayerName(killer_slot) or ""
    local pos = getPlayerPos(victim_slot)

    tracker.kill_outcomes.dead_players[victim_slot] = {
        kill_time = now,
        victim_guid = victim_guid,
        victim_name = victim_name,
        killer_guid = killer_guid,
        killer_name = killer_name,
        kill_mod = meansOfDeath or 0,
        pos = pos,
        body_damage = 0,
        body_hits = 0,
        last_damager_guid = "",
        last_damager_name = "",
        last_damage_mod = 0,
    }
end

local function recordKillOutcomeBodyDamage(victim_slot, attacker_slot, damage, meansOfDeath)
    local info = tracker.kill_outcomes.dead_players[victim_slot]
    if not info then return end
    info.body_damage = info.body_damage + damage
    info.body_hits = info.body_hits + 1
    if isValidClient(attacker_slot) then
        info.last_damager_guid = getPlayerGUID(attacker_slot)
        info.last_damager_name = getPlayerName(attacker_slot)
        info.last_damage_mod = meansOfDeath or 0
    end

    -- v5.2: Gib detection via cumulative body damage threshold (replaces broken PMF_LIMBO polling)
    -- ET:Legacy gibs corpses at -175 health. Body damage accumulates post-mortem from all sources.
    if info.body_damage >= 175 then
        finalizeKillOutcome(victim_slot, "gibbed", nil, nil)
    end
end

-- v5.2: Simplified cleanup — only handles stale entries (timeout safety net).
-- Gib detection moved to recordKillOutcomeBodyDamage (body_damage >= 175).
-- Tap-out detection moved to et_ClientSpawn (revived ~= 1).
-- Revive detection already handled in et_ClientSpawn (revived == 1).
local KILL_OUTCOME_CLEANUP_INTERVAL = 5000  -- check every 5s instead of every frame
local last_kill_outcome_cleanup = 0

local function cleanupStaleKillOutcomes(now)
    if now - last_kill_outcome_cleanup < KILL_OUTCOME_CLEANUP_INTERVAL then return end
    last_kill_outcome_cleanup = now
    for slot, info in pairs(tracker.kill_outcomes.dead_players) do
        if now - info.kill_time > KILL_OUTCOME_TIMEOUT then
            finalizeKillOutcome(slot, "expired", nil, nil)
        end
    end
end

-- ===== v5 TEAMPLAY FRAME UPDATE =====
-- Called from et_RunFrame during active play

local function updateTeamplay(now)
    -- Team cohesion (every 500ms, throttle to 1000ms after 6000 samples to cap memory)
    if isFeatureEnabled("team_cohesion") then
        local cohesion_interval = config.teamplay.cohesion_interval_ms
        if #tracker.cohesion.samples > 6000 then
            cohesion_interval = cohesion_interval * 2  -- reduce sampling rate for long rounds
        end
        if now - tracker.cohesion.last_check_time >= cohesion_interval then
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

    -- v5.2: Kill outcome cleanup (stale entry timeout only, every 5s)
    if isFeatureEnabled("kill_outcome_tracking") then
        cleanupStaleKillOutcomes(now)
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

local function countTableKeys(t)
    local count = 0
    for _ in pairs(t) do count = count + 1 end
    return count
end

-- ===== v6 CARRIER TRACKING =====

local function startCarrierTracking(clientNum, flag_team)
    if not isFeatureEnabled("carrier_tracking") then return end
    if tracker.carrier.active[clientNum] then return end
    local pos = getPlayerPos(clientNum)
    if not pos then return end
    local now = gameTime()
    tracker.carrier.active[clientNum] = {
        guid = getPlayerGUID(clientNum),
        name = getPlayerName(clientNum),
        team = getPlayerTeam(clientNum),
        flag_team = flag_team,
        pickup_time = now,
        pickup_pos = { x = round(pos.x, 0), y = round(pos.y, 0), z = round(pos.z, 0) },
        last_pos = pos,
        carry_distance = 0,
        path_samples = 1,
        last_sample_time = now,
    }
    -- Phase 1.5: detect re-pickup
    if isFeatureEnabled("carrier_returns") and tracker.carrier.pending_drops[flag_team] then
        local pd = tracker.carrier.pending_drops[flag_team]
        tracker.carrier.active[clientNum].is_repickup = true
        tracker.carrier.active[clientNum].repickup_delay_ms = gameTime() - pd.drop_time
        tracker.carrier.pending_drops[flag_team] = nil
    end
    if config.debug then
        et.G_Print(string.format("[PROX] Carrier started: %s flag=%s\n",
            getPlayerName(clientNum), flag_team))
    end
end

sampleCarrierPosition = function(clientNum)
    local state = tracker.carrier.active[clientNum]
    if not state then return end
    local pos = getPlayerPos(clientNum)
    if not pos then return end
    local now = gameTime()
    if now - state.last_sample_time < config.teamplay.carrier_sample_interval_ms then return end
    local d = distance3D(pos, state.last_pos)
    state.carry_distance = state.carry_distance + d
    state.last_pos = pos
    state.path_samples = state.path_samples + 1
    state.last_sample_time = now
end

local function endCarrierTracking(clientNum, outcome, killer_guid, killer_name)
    local state = tracker.carrier.active[clientNum]
    if not state then return end
    local now = gameTime()
    local drop_pos = getPlayerPos(clientNum) or state.last_pos
    local beeline = distance3D(state.pickup_pos, drop_pos)
    local efficiency = 0
    if state.carry_distance > 0 then
        efficiency = beeline / state.carry_distance
        if efficiency > 1.0 then efficiency = 1.0 end
    end
    table.insert(tracker.carrier.events, {
        carrier_guid = state.guid,
        carrier_name = state.name,
        carrier_team = state.team,
        flag_team = state.flag_team,
        pickup_time = state.pickup_time,
        drop_time = now,
        duration_ms = now - state.pickup_time,
        outcome = outcome,
        carry_distance = round(state.carry_distance, 1),
        beeline_distance = round(beeline, 1),
        efficiency = round(efficiency, 3),
        path_samples = state.path_samples,
        pickup_x = state.pickup_pos.x,
        pickup_y = state.pickup_pos.y,
        pickup_z = state.pickup_pos.z,
        drop_x = round(drop_pos.x, 0),
        drop_y = round(drop_pos.y, 0),
        drop_z = round(drop_pos.z, 0),
        killer_guid = killer_guid or "",
        killer_name = killer_name or "",
    })
    -- Phase 1.5: track pending drops for return detection
    if (outcome == "killed" or outcome == "dropped") and isFeatureEnabled("carrier_returns") then
        tracker.carrier.pending_drops[state.flag_team] = {
            flag_team = state.flag_team,
            drop_time = now,
            drop_pos = drop_pos,
            carrier_guid = state.guid,
            carrier_name = state.name,
            carrier_team = state.team,
        }
    end
    if outcome == "killed" and killer_guid and killer_guid ~= "" then
        table.insert(tracker.carrier.kills, {
            kill_time = now,
            carrier_guid = state.guid,
            carrier_name = state.name,
            carrier_team = state.team,
            killer_guid = killer_guid,
            killer_name = killer_name,
            killer_team = "",
            means_of_death = 0,
            carrier_distance_at_kill = round(state.carry_distance, 1),
            flag_team = state.flag_team,
        })
    end
    tracker.carrier.active[clientNum] = nil
    if config.debug then
        et.G_Print(string.format("[PROX] Carrier ended: %s outcome=%s dist=%.0f eff=%.3f\n",
            state.name, outcome, state.carry_distance, efficiency))
    end
end

checkCarrierPowerups = function()
    if not isFeatureEnabled("carrier_tracking") then return end
    local max_clients = get_max_clients()
    for clientnum = 0, max_clients - 1 do
        if isPlayerActive(clientnum) and isPlayerAlive(clientnum) then
            local red_pw = tonumber(safe_gentity_get(clientnum, "ps.powerups", 5)) or 0
            local blue_pw = tonumber(safe_gentity_get(clientnum, "ps.powerups", 6)) or 0
            if red_pw > 0 and not tracker.carrier.active[clientnum] then
                startCarrierTracking(clientnum, "redflag")
            elseif blue_pw > 0 and not tracker.carrier.active[clientnum] then
                startCarrierTracking(clientnum, "blueflag")
            end
            if tracker.carrier.active[clientnum] then
                local expected_flag = tracker.carrier.active[clientnum].flag_team
                local still_carrying = false
                if expected_flag == "redflag" and red_pw > 0 then still_carrying = true end
                if expected_flag == "blueflag" and blue_pw > 0 then still_carrying = true end
                if not still_carrying then
                    endCarrierTracking(clientnum, "dropped", nil, nil)
                end
            end
        end
    end
end

-- ===== v6 VEHICLE/ESCORT TRACKING =====

local function scanVehicleEntities()
    if not isFeatureEnabled("vehicle_tracking") then return end
    tracker.vehicles.entities = {}
    tracker.vehicles.escort_credits = {}
    tracker.vehicles.last_check_time = 0

    local known = {}
    for _, name in ipairs(config.vehicle.known_script_names) do
        known[name] = true
    end

    for i = 64, 1023 do
        local ok_cn, classname = pcall(et.gentity_get, i, "classname")
        if ok_cn and classname == "script_mover" then
            local ok_sn, script_name = pcall(et.gentity_get, i, "scriptName")
            local name = (ok_sn and script_name) or ""
            if known[name] then
                local ox = tonumber(safe_gentity_get(i, "r.currentOrigin", 1)) or 0
                local oy = tonumber(safe_gentity_get(i, "r.currentOrigin", 2)) or 0
                local oz = tonumber(safe_gentity_get(i, "r.currentOrigin", 3)) or 0
                local health = tonumber(safe_gentity_get(i, "health")) or 0
                tracker.vehicles.entities[i] = {
                    name = name,
                    type = "script_mover",
                    start_pos = {x = ox, y = oy, z = oz},
                    last_pos = {x = ox, y = oy, z = oz},
                    total_distance = 0,
                    max_health = health,
                    last_health = health,
                    destroyed_count = 0,
                }
                et.G_Print(string.format("[PROX v6] Vehicle found: ent=%d name=%s pos=(%d,%d,%d) hp=%d\n",
                    i, name, ox, oy, oz, health))
            end
        end
    end
end

sampleVehiclePositions = function()
    if not isFeatureEnabled("vehicle_tracking") then return end
    local now = gameTime()
    if now - tracker.vehicles.last_check_time < config.vehicle.sample_interval_ms then return end
    tracker.vehicles.last_check_time = now

    for entNum, veh in pairs(tracker.vehicles.entities) do
        local vx = tonumber(safe_gentity_get(entNum, "r.currentOrigin", 1)) or 0
        local vy = tonumber(safe_gentity_get(entNum, "r.currentOrigin", 2)) or 0
        local vz = tonumber(safe_gentity_get(entNum, "r.currentOrigin", 3)) or 0
        local current_pos = {x = vx, y = vy, z = vz}

        local delta = distance3D(current_pos, veh.last_pos)
        local is_moving = delta > config.vehicle.min_move_speed

        if is_moving then
            veh.total_distance = veh.total_distance + delta
        end
        veh.last_pos = current_pos

        -- Track health changes
        local health = tonumber(safe_gentity_get(entNum, "health")) or 0
        if health <= 0 and veh.last_health > 0 then
            veh.destroyed_count = veh.destroyed_count + 1
        end
        if health > veh.max_health then veh.max_health = health end
        veh.last_health = health

        -- Attribution: check all players for mounted or proximity
        local max_clients = get_max_clients()
        for cn = 0, max_clients - 1 do
            if isPlayerActive(cn) and isPlayerAlive(cn) then
                local guid = getPlayerGUID(cn)
                if guid and guid ~= "" then
                    local key = guid .. ":" .. veh.name
                    if not tracker.vehicles.escort_credits[key] then
                        tracker.vehicles.escort_credits[key] = {
                            player_guid = guid,
                            player_name = getPlayerName(cn),
                            player_team = getPlayerTeam(cn),
                            vehicle_name = veh.name,
                            mounted_ms = 0,
                            proximity_ms = 0,
                            total_escort_distance = 0,
                            credit_distance = 0,
                            samples = 0,
                        }
                    end
                    local credit = tracker.vehicles.escort_credits[key]

                    -- Check if mounted on this vehicle
                    local player_tank = tonumber(safe_gentity_get(cn, "tankLink")) or -1
                    if player_tank == entNum then
                        credit.mounted_ms = credit.mounted_ms + config.vehicle.sample_interval_ms
                        credit.samples = credit.samples + 1
                        if is_moving then
                            credit.credit_distance = credit.credit_distance + delta
                            credit.total_escort_distance = credit.total_escort_distance + delta
                        end
                    else
                        -- Check proximity while vehicle is moving
                        if is_moving then
                            local player_pos = getPlayerPos(cn)
                            if player_pos then
                                local d = distance3D(player_pos, current_pos)
                                if d <= config.vehicle.escort_radius then
                                    credit.proximity_ms = credit.proximity_ms + config.vehicle.sample_interval_ms
                                    credit.samples = credit.samples + 1
                                    credit.total_escort_distance = credit.total_escort_distance + delta
                                    local proximity_factor = 1.0 - (d / config.vehicle.escort_radius)
                                    credit.credit_distance = credit.credit_distance + (delta * proximity_factor)
                                end
                            end
                        end
                    end
                    credit.player_name = getPlayerName(cn)
                end
            end
        end
    end
end

-- ===== v6.01 OBJECTIVE RUN INTELLIGENCE =====

local function countByField(tbl, field, value)
    local count = 0
    for _, item in ipairs(tbl) do
        if item[field] == value then count = count + 1 end
    end
    return count
end

local function scanObjectiveEntities()
    if not isFeatureEnabled("objective_run_tracking") then return end
    tracker.objective_runs.constructibles = {}
    tracker.objective_runs.explosives = {}
    tracker.objective_runs.checkpoints = {}

    local constructible_count = 0
    local explosive_count = 0
    local checkpoint_count = 0

    for i = 64, 1023 do
        local ok_cn, classname = pcall(et.gentity_get, i, "classname")
        if ok_cn and classname then
            if classname == "team_WOLF_checkpoint" then
                local ok_sn, script_name = pcall(et.gentity_get, i, "scriptName")
                local sname = (ok_sn and script_name) or ""
                local ox, oy, oz = 0, 0, 0
                local origin = safe_gentity_get(i, "r.currentOrigin")
                if origin then
                    if origin[1] then
                        ox = tonumber(origin[1]) or 0
                        oy = tonumber(origin[2]) or 0
                        oz = tonumber(origin[3]) or 0
                    elseif origin.x then
                        ox = tonumber(origin.x) or 0
                        oy = tonumber(origin.y) or 0
                        oz = tonumber(origin.z) or 0
                    end
                end
                if ox == 0 and oy == 0 and oz == 0 then
                    ox = tonumber(safe_gentity_get(i, "r.currentOrigin", 1)) or 0
                    oy = tonumber(safe_gentity_get(i, "r.currentOrigin", 2)) or 0
                    oz = tonumber(safe_gentity_get(i, "r.currentOrigin", 3)) or 0
                end
                -- count = controlling team (NOT s.teamNum which is for animation)
                local initial_team = tonumber(safe_gentity_get(i, "count")) or 0
                tracker.objective_runs.checkpoints[i] = {
                    x = ox, y = oy, z = oz,
                    scriptName = sname,
                    last_team = initial_team,
                }
                checkpoint_count = checkpoint_count + 1
            elseif classname == "func_constructible" then
                local ok_sn, script_name = pcall(et.gentity_get, i, "scriptName")
                local sname = (ok_sn and script_name) or ""
                local ok_tn, track_name = pcall(et.gentity_get, i, "track")
                local tname = (ok_tn and track_name) or ""
                -- Get origin (handle table with [1],[2],[3] or .x,.y,.z)
                local ox, oy, oz = 0, 0, 0
                local origin = safe_gentity_get(i, "r.currentOrigin")
                if origin then
                    if origin[1] then
                        ox = tonumber(origin[1]) or 0
                        oy = tonumber(origin[2]) or 0
                        oz = tonumber(origin[3]) or 0
                    elseif origin.x then
                        ox = tonumber(origin.x) or 0
                        oy = tonumber(origin.y) or 0
                        oz = tonumber(origin.z) or 0
                    end
                end
                -- Fallback: try indexed access
                if ox == 0 and oy == 0 and oz == 0 then
                    ox = tonumber(safe_gentity_get(i, "r.currentOrigin", 1)) or 0
                    oy = tonumber(safe_gentity_get(i, "r.currentOrigin", 2)) or 0
                    oz = tonumber(safe_gentity_get(i, "r.currentOrigin", 3)) or 0
                end
                tracker.objective_runs.constructibles[i] = {
                    track = tname,
                    x = ox, y = oy, z = oz,
                    scriptName = sname,
                    last_progress = 0,
                }
                constructible_count = constructible_count + 1
            elseif classname == "func_explosive" then
                local ok_sn, script_name = pcall(et.gentity_get, i, "scriptName")
                local sname = (ok_sn and script_name) or ""
                local ok_tn, track_name = pcall(et.gentity_get, i, "track")
                local tname = (ok_tn and track_name) or ""
                local ox, oy, oz = 0, 0, 0
                local origin = safe_gentity_get(i, "r.currentOrigin")
                if origin then
                    if origin[1] then
                        ox = tonumber(origin[1]) or 0
                        oy = tonumber(origin[2]) or 0
                        oz = tonumber(origin[3]) or 0
                    elseif origin.x then
                        ox = tonumber(origin.x) or 0
                        oy = tonumber(origin.y) or 0
                        oz = tonumber(origin.z) or 0
                    end
                end
                if ox == 0 and oy == 0 and oz == 0 then
                    ox = tonumber(safe_gentity_get(i, "r.currentOrigin", 1)) or 0
                    oy = tonumber(safe_gentity_get(i, "r.currentOrigin", 2)) or 0
                    oz = tonumber(safe_gentity_get(i, "r.currentOrigin", 3)) or 0
                end
                tracker.objective_runs.explosives[i] = {
                    track = tname,
                    x = ox, y = oy, z = oz,
                    scriptName = sname,
                }
                explosive_count = explosive_count + 1
            end
        end
    end

    et.G_Print(string.format("[PROX v6.01] Objective entities: %d constructibles, %d explosives, %d checkpoints\n",
        constructible_count, explosive_count, checkpoint_count))
end

local function findNearestConstructible(pos, max_dist)
    if not pos then return nil end
    local best_obj, best_dist = nil, max_dist
    for _, obj in pairs(tracker.objective_runs.constructibles) do
        local obj_pos = {x = obj.x, y = obj.y, z = obj.z}
        local d = distance3D(pos, obj_pos)
        if d < best_dist then
            best_dist = d
            best_obj = obj
        end
    end
    if best_obj then
        return best_obj, best_dist
    end
    return nil
end

local function findNearestExplosive(pos, max_dist)
    if not pos then return nil end
    local best_obj, best_dist = nil, max_dist
    for _, obj in pairs(tracker.objective_runs.explosives) do
        local obj_pos = {x = obj.x, y = obj.y, z = obj.z}
        local d = distance3D(pos, obj_pos)
        if d < best_dist then
            best_dist = d
            best_obj = obj
        end
    end
    if best_obj then
        return best_obj, best_dist
    end
    return nil
end

local function findNearestCheckpoint(pos, max_dist)
    if not pos then return nil, nil end
    local best_obj, best_dist, best_ent = nil, max_dist, nil
    for entNum, obj in pairs(tracker.objective_runs.checkpoints) do
        local obj_pos = {x = obj.x, y = obj.y, z = obj.z}
        local d = distance3D(pos, obj_pos)
        if d < best_dist then
            best_dist = d
            best_obj = obj
            best_ent = entNum
        end
    end
    if best_obj then
        return best_obj, best_dist, best_ent
    end
    return nil
end

local function countAreaKills(obj_pos, engineer_guid, engineer_team, action_time, window_ms, radius)
    local self_kills = 0
    local team_kills = 0
    local escort_set = {}

    for i = #tracker.combat_positions, 1, -1 do
        local cp = tracker.combat_positions[i]
        local time_before = action_time - cp.time
        if time_before > window_ms then
            break  -- too old, stop
        end
        if time_before >= 0 then
            local victim_pos = {x = cp.vx, y = cp.vy, z = cp.vz}
            local d = distance3D(obj_pos, victim_pos)
            if d <= radius then
                if cp.attacker_guid == engineer_guid then
                    self_kills = self_kills + 1
                elseif cp.attacker_team == engineer_team then
                    team_kills = team_kills + 1
                    escort_set[cp.attacker_guid] = true
                end
            end
        end
    end

    local escort_guids = {}
    for guid, _ in pairs(escort_set) do
        table.insert(escort_guids, guid)
    end
    local escort_guids_str = table.concat(escort_guids, "|")

    return self_kills, team_kills, escort_guids_str
end

local function countNearbyAlive(team, pos, radius, exclude_cn)
    local teammates_count = 0
    local enemies_count = 0
    local max_clients = get_max_clients()

    for cn = 0, max_clients - 1 do
        if cn ~= exclude_cn and isPlayerActive(cn) and isPlayerAlive(cn) then
            local p = getPlayerPos(cn)
            if p then
                local d = distance3D(pos, p)
                if d <= radius then
                    local t = getPlayerTeam(cn)
                    if t == team then
                        teammates_count = teammates_count + 1
                    elseif t ~= "SPEC" then
                        enemies_count = enemies_count + 1
                    end
                end
            end
        end
    end

    return teammates_count, enemies_count
end

local function calculateApproachMetrics(track, action_time, window_ms)
    if not track or not track.path or #track.path == 0 then
        return 0, 0, 0, 0
    end

    local start_time = action_time - window_ms
    local first_sample = nil
    local last_sample = nil
    local approach_distance = 0
    local prev_sample = nil

    for _, sample in ipairs(track.path) do
        if sample.time >= start_time and sample.time <= action_time then
            if not first_sample then
                first_sample = sample
            end
            if prev_sample then
                local seg_pos1 = {x = prev_sample.x, y = prev_sample.y, z = prev_sample.z}
                local seg_pos2 = {x = sample.x, y = sample.y, z = sample.z}
                approach_distance = approach_distance + distance3D(seg_pos1, seg_pos2)
            end
            prev_sample = sample
            last_sample = sample
        end
    end

    if not first_sample or not last_sample then
        return 0, 0, 0, 0
    end

    local approach_time_ms = last_sample.time - first_sample.time
    local first_pos = {x = first_sample.x, y = first_sample.y, z = first_sample.z}
    local last_pos = {x = last_sample.x, y = last_sample.y, z = last_sample.z}
    local beeline_distance = distance3D(first_pos, last_pos)

    local path_efficiency = 0
    if approach_distance > 0 then
        path_efficiency = beeline_distance / approach_distance
        if path_efficiency > 1.0 then path_efficiency = 1.0 end
    end

    return round(approach_time_ms, 0), round(approach_distance, 1), round(beeline_distance, 1), round(path_efficiency, 3)
end

local function classifyRunType(self_kills, team_kills, nearby_teammates, enemies_nearby)
    local total_kills = self_kills + team_kills

    if total_kills == 0 and enemies_nearby == 0 then
        return "unopposed"
    end
    if self_kills > 0 and team_kills == 0 and nearby_teammates == 0 then
        return "solo"
    end
    if self_kills > 0 and enemies_nearby > 0 and team_kills == 0 then
        return "contested_solo"
    end
    if team_kills > 0 and self_kills == 0 then
        return "assisted"
    end
    if total_kills >= 3 or (team_kills > 0 and self_kills > 0) then
        return "team_effort"
    end

    -- Default fallback
    if enemies_nearby > 0 then
        return "contested_solo"
    end
    return "unopposed"
end

local function assembleObjectiveRun(engineer_cn, action_type, track_name, action_pos)
    if not isFeatureEnabled("objective_run_tracking") then return end
    if not isValidClient(engineer_cn) then return end

    local track = tracker.player_tracks[engineer_cn]
    if not track then return end

    local now = gameTime()
    local pos = action_pos or getPlayerPos(engineer_cn)
    if not pos then return end

    -- For construction_complete without track_name, use findNearestConstructible to resolve
    local resolved_track_name = track_name or ""
    if action_type == "construction_complete" and (resolved_track_name == "" or resolved_track_name == nil) then
        local nearest = findNearestConstructible(pos, config.objective_run.path_clear_radius)
        if nearest then
            resolved_track_name = nearest.track or ""
        end
    end

    -- For objective_destroyed, find the explosive entity by track_name for accurate position
    local obj_pos = pos
    if action_type == "objective_destroyed" and resolved_track_name ~= "" then
        for _, exp in pairs(tracker.objective_runs.explosives) do
            if exp.track == resolved_track_name then
                obj_pos = {x = exp.x, y = exp.y, z = exp.z}
                break
            end
        end
    end

    -- Calculate area kills
    local self_kills, team_kills, escort_guids = countAreaKills(
        obj_pos, track.guid, track.team, now,
        config.objective_run.path_clear_window_ms,
        config.objective_run.path_clear_radius)

    -- Count nearby alive players
    local nearby_teammates, enemies_nearby = countNearbyAlive(
        track.team, obj_pos, config.objective_run.path_clear_radius, engineer_cn)

    -- Calculate approach metrics
    local approach_time_ms, approach_distance, beeline_distance, path_efficiency =
        calculateApproachMetrics(track, now, config.objective_run.path_clear_window_ms)

    -- Classify run type
    local run_type = classifyRunType(self_kills, team_kills, nearby_teammates, enemies_nearby)

    table.insert(tracker.objective_runs.completed, {
        engineer_guid = track.guid,
        engineer_name = track.name,
        engineer_team = track.team,
        action_type = action_type,
        track_name = resolved_track_name,
        action_time = now,
        approach_time_ms = approach_time_ms,
        approach_distance = approach_distance,
        beeline_distance = beeline_distance,
        path_efficiency = path_efficiency,
        self_kills = self_kills,
        team_kills = team_kills,
        escort_guids = escort_guids,
        enemies_nearby = enemies_nearby,
        nearby_teammates = nearby_teammates,
        run_type = run_type,
        obj_x = round(obj_pos.x, 0),
        obj_y = round(obj_pos.y, 0),
        obj_z = round(obj_pos.z, 0),
        killer_guid = "",
        killer_name = "",
    })

    if config.debug then
        et.G_Print(string.format("[PROX v6.01] Objective run: %s %s track=%s type=%s kills=%d+%d\n",
            track.name, action_type, resolved_track_name, run_type, self_kills, team_kills))
    end
end

local function pollConstructionProgress(now)
    if not isFeatureEnabled("objective_run_tracking") then return end
    if now - tracker.objective_runs.last_poll < config.objective_run.constructible_poll_interval_ms then return end
    tracker.objective_runs.last_poll = now

    for entNum, obj in pairs(tracker.objective_runs.constructibles) do
        local ok, progress = pcall(et.gentity_get, entNum, "s.angles2", 0)
        if ok and progress then
            progress = tonumber(progress) or 0
            local prev = obj.last_progress or 0
            if prev == 0 and progress > 0 then
                if config.debug then
                    et.G_Print(string.format("[PROX v6.01] Construction started: ent=%d track=%s progress=%.1f\n",
                        entNum, obj.track or "", progress))
                end
            elseif prev > 0 and progress == 0 then
                if config.debug then
                    et.G_Print(string.format("[PROX v6.01] Construction interrupted: ent=%d track=%s\n",
                        entNum, obj.track or ""))
                end
            end
            obj.last_progress = progress
        end
    end
end

local function outputDataInner()
    if #tracker.completed == 0 and #tracker.completed_tracks == 0 then
        proxPrint("[PROX] No data to output\n")
        return
    end

    if tracker.round.map_name == "" or tracker.round.map_name == "unknown" then
        refreshRoundInfo()
    end
    local filename = string.format("%s%s-%s-round-%d_engagements.txt",
        config.output_dir, os.date('%Y-%m-%d-%H%M%S'),
        tracker.round.map_name, tracker.round.round_num)

    proxPrint("[PROX] Attempting to write: " .. filename .. "\n")

    local fd, len = et.trap_FS_FOpenFile(filename, et.FS_WRITE)
    if not fd or fd == -1 or fd == 0 then
        et.G_Print("[PROX] ERROR: Could not open file: " .. filename .. "\n")
        return
    end

    -- ===== HEADER =====
    local header = string.format(
        "# PROXIMITY_TRACKER_V6\n" ..
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
        local line = string.format("%s;%s;%d;%d\n", gx, gy, data.axis, data.allies)
        et.trap_FS_Write(line, string.len(line), fd)
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
            "kill_time;enemy_spawn_interval;time_to_next_spawn;spawn_timing_score;" ..
            "killer_reinf;victim_reinf\n"
        et.trap_FS_Write(st_header, string.len(st_header), fd)
        for _, t in ipairs(tracker.spawn.kill_timings) do
            local line = string.format("%s;%s;%s;%s;%s;%s;%d;%d;%d;%.3f;%.1f;%.1f\n",
                t.killer_guid, t.killer_name, t.killer_team,
                t.victim_guid, t.victim_name, t.victim_team,
                t.kill_time, t.enemy_spawn_interval, t.time_to_next_spawn, t.spawn_timing_score,
                t.killer_reinf or 0, t.victim_reinf or 0)
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

    -- ===== REVIVES =====
    if #tracker.revives > 0 then
        local rev_header = "\n# REVIVES\n" ..
            "# time;medic_guid;medic_name;revived_guid;revived_name;x;y;z;distance_to_enemy;nearest_enemy_guid;under_fire\n"
        et.trap_FS_Write(rev_header, string.len(rev_header), fd)
        for _, r in ipairs(tracker.revives) do
            local line = string.format("%d;%s;%s;%s;%s;%.1f;%.1f;%.1f;%.1f;%s;%s\n",
                r.time, r.medic_guid, r.medic_name,
                r.revived_guid, r.revived_name,
                r.x, r.y, r.z,
                r.distance_to_enemy, r.nearest_enemy_guid, r.under_fire)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== WEAPON ACCURACY =====
    local has_weapon_data = false
    for _, _ in pairs(tracker.weapon_fire) do has_weapon_data = true; break end
    if has_weapon_data then
        local wa_header = "\n# WEAPON_ACCURACY\n" ..
            "# player_guid;player_name;team;weapon_id;shots_fired;hits;kills;headshots\n"
        et.trap_FS_Write(wa_header, string.len(wa_header), fd)
        for guid, weapons in pairs(tracker.weapon_fire) do
            local name = weapons._name or "Unknown"
            local team = weapons._team or "SPEC"
            for weapon_id, data in pairs(weapons) do
                if type(weapon_id) == "number" then
                    local line = string.format("%s;%s;%s;%d;%d;%d;%d;%d\n",
                        guid, name, team, weapon_id,
                        data.shots or 0, data.hits or 0,
                        data.kills or 0, data.headshots or 0)
                    et.trap_FS_Write(line, string.len(line), fd)
                end
            end
        end
    end

    -- ===== KILL OUTCOMES (v5.1) =====
    -- Finalize any still-pending dead players before output
    for slot, _ in pairs(tracker.kill_outcomes.dead_players) do
        finalizeKillOutcome(slot, "round_end", nil, nil)
    end

    if #tracker.kill_outcomes.completed > 0 then
        local ko_header = "\n# KILL_OUTCOME\n" ..
            "# kill_time;victim_guid;victim_name;killer_guid;killer_name;kill_mod;" ..
            "outcome;outcome_time;delta_ms;effective_denied_ms;" ..
            "gibber_guid;gibber_name;reviver_guid;reviver_name\n" ..
            "# outcome: gibbed|revived|tapped_out|round_end|expired\n"
        et.trap_FS_Write(ko_header, string.len(ko_header), fd)
        for _, ko in ipairs(tracker.kill_outcomes.completed) do
            local line = string.format("%d;%s;%s;%s;%s;%d;%s;%d;%d;%d;%s;%s;%s;%s\n",
                ko.kill_time, ko.victim_guid, ko.victim_name,
                ko.killer_guid, ko.killer_name, ko.kill_mod,
                ko.outcome, ko.outcome_time, ko.delta_ms, ko.effective_denied_ms,
                ko.gibber_guid, ko.gibber_name,
                ko.reviver_guid, ko.reviver_name)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== HIT REGIONS (v5.2) =====
    if isFeatureEnabled("hit_region_tracking") and #tracker.hit_regions > 0 then
        local hr_header = "\n# HIT_REGIONS\n" ..
            "# time;attacker_guid;attacker_name;victim_guid;victim_name;weapon;region;damage\n" ..
            "# region: 0=HEAD, 1=ARMS, 2=BODY, 3=LEGS\n"
        et.trap_FS_Write(hr_header, string.len(hr_header), fd)
        for _, hr in ipairs(tracker.hit_regions) do
            local line = string.format("%d;%s;%s;%s;%s;%d;%d;%d\n",
                hr.time, hr.attacker_guid, hr.attacker_name,
                hr.victim_guid, hr.victim_name,
                hr.weapon, hr.region, hr.damage)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== COMBAT POSITIONS (v5.2) =====
    if isFeatureEnabled("combat_positions") and #tracker.combat_positions > 0 then
        local cp_header = "\n# COMBAT_POSITIONS\n" ..
            "# time;event;atk_guid;atk_name;atk_team;atk_class;" ..
            "vic_guid;vic_name;vic_team;vic_class;" ..
            "ax;ay;az;vx;vy;vz;weapon;mod;killer_health;axis_alive;allies_alive\n"
        et.trap_FS_Write(cp_header, string.len(cp_header), fd)
        for _, cp in ipairs(tracker.combat_positions) do
            local line = string.format("%d;%s;%s;%s;%s;%s;%s;%s;%s;%s;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d\n",
                cp.time, cp.event_type,
                cp.attacker_guid, cp.attacker_name, cp.attacker_team, cp.attacker_class,
                cp.victim_guid, cp.victim_name, cp.victim_team, cp.victim_class,
                cp.ax, cp.ay, cp.az, cp.vx, cp.vy, cp.vz,
                cp.weapon, cp.mod,
                cp.killer_health or 0, cp.axis_alive or 0, cp.allies_alive or 0)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== CARRIER EVENTS (v6) =====
    if isFeatureEnabled("carrier_tracking") and #tracker.carrier.events > 0 then
        local ce_header = "\n# CARRIER_EVENTS\n" ..
            "# carrier_guid;carrier_name;carrier_team;flag_team;pickup_time;drop_time;duration_ms;" ..
            "outcome;carry_distance;beeline_distance;efficiency;path_samples;" ..
            "pickup_x;pickup_y;pickup_z;drop_x;drop_y;drop_z;killer_guid;killer_name\n"
        et.trap_FS_Write(ce_header, string.len(ce_header), fd)
        for _, ce in ipairs(tracker.carrier.events) do
            local line = string.format(
                "%s;%s;%s;%s;%d;%d;%d;%s;%.1f;%.1f;%.3f;%d;%d;%d;%d;%d;%d;%d;%s;%s\n",
                ce.carrier_guid, ce.carrier_name, ce.carrier_team, ce.flag_team,
                ce.pickup_time, ce.drop_time, ce.duration_ms,
                ce.outcome, ce.carry_distance, ce.beeline_distance, ce.efficiency,
                ce.path_samples,
                ce.pickup_x, ce.pickup_y, ce.pickup_z,
                ce.drop_x, ce.drop_y, ce.drop_z,
                ce.killer_guid, ce.killer_name)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== CARRIER KILLS (v6) =====
    if isFeatureEnabled("carrier_tracking") and #tracker.carrier.kills > 0 then
        local ck_header = "\n# CARRIER_KILLS\n" ..
            "# kill_time;carrier_guid;carrier_name;carrier_team;" ..
            "killer_guid;killer_name;killer_team;means_of_death;" ..
            "carrier_distance_at_kill;flag_team\n"
        et.trap_FS_Write(ck_header, string.len(ck_header), fd)
        for _, ck in ipairs(tracker.carrier.kills) do
            local line = string.format("%d;%s;%s;%s;%s;%s;%s;%d;%.1f;%s\n",
                ck.kill_time, ck.carrier_guid, ck.carrier_name, ck.carrier_team,
                ck.killer_guid, ck.killer_name, ck.killer_team,
                ck.means_of_death, ck.carrier_distance_at_kill, ck.flag_team)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== CARRIER RETURNS (v6 Phase 1.5) =====
    if isFeatureEnabled("carrier_returns") and #tracker.carrier.returns > 0 then
        local cr_header = "\n# CARRIER_RETURNS\n" ..
            "# return_time;returner_guid;returner_name;returner_team;flag_team;" ..
            "original_carrier_guid;drop_time;return_delay_ms;drop_x;drop_y;drop_z\n"
        et.trap_FS_Write(cr_header, string.len(cr_header), fd)
        for _, cr in ipairs(tracker.carrier.returns) do
            local line = string.format("%d;%s;%s;%s;%s;%s;%d;%d;%d;%d;%d\n",
                cr.return_time, cr.returner_guid, cr.returner_name, cr.returner_team,
                cr.flag_team, cr.original_carrier_guid, cr.drop_time, cr.return_delay_ms,
                cr.drop_x, cr.drop_y, cr.drop_z)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- ===== VEHICLE PROGRESS (v6 Phase 2) =====
    if isFeatureEnabled("vehicle_tracking") then
        local vp_items = {}
        for _, veh in pairs(tracker.vehicles.entities) do
            if veh.total_distance > 0 or veh.destroyed_count > 0 then
                table.insert(vp_items, veh)
            end
        end
        if #vp_items > 0 then
            local vp_header = "\n# VEHICLE_PROGRESS\n" ..
                "# vehicle_name;vehicle_type;start_x;start_y;start_z;end_x;end_y;end_z;" ..
                "total_distance;max_health;final_health;destroyed_count\n"
            et.trap_FS_Write(vp_header, string.len(vp_header), fd)
            for _, veh in ipairs(vp_items) do
                local line = string.format("%s;%s;%d;%d;%d;%d;%d;%d;%.1f;%d;%d;%d\n",
                    veh.name, veh.type,
                    veh.start_pos.x, veh.start_pos.y, veh.start_pos.z,
                    veh.last_pos.x, veh.last_pos.y, veh.last_pos.z,
                    veh.total_distance, veh.max_health, veh.last_health, veh.destroyed_count)
                et.trap_FS_Write(line, string.len(line), fd)
            end
        end
    end

    -- ===== ESCORT CREDIT (v6 Phase 2) =====
    if isFeatureEnabled("vehicle_tracking") then
        local ec_items = {}
        for _, credit in pairs(tracker.vehicles.escort_credits) do
            if credit.samples > 0 then
                table.insert(ec_items, credit)
            end
        end
        if #ec_items > 0 then
            local ec_header = "\n# ESCORT_CREDIT\n" ..
                "# player_guid;player_name;player_team;vehicle_name;mounted_time_ms;" ..
                "proximity_time_ms;total_escort_distance;credit_distance;samples\n"
            et.trap_FS_Write(ec_header, string.len(ec_header), fd)
            for _, ec in ipairs(ec_items) do
                local line = string.format("%s;%s;%s;%s;%d;%d;%.1f;%.1f;%d\n",
                    ec.player_guid, ec.player_name, ec.player_team, ec.vehicle_name,
                    ec.mounted_ms, ec.proximity_ms, ec.total_escort_distance,
                    ec.credit_distance, ec.samples)
                et.trap_FS_Write(line, string.len(line), fd)
            end
        end
    end

    -- ===== CONSTRUCTION EVENTS (v6 Phase 3) =====
    if isFeatureEnabled("construction_tracking") and #tracker.construction.events > 0 then
        local con_header = "\n# CONSTRUCTION_EVENTS\n" ..
            "# event_time;event_type;player_guid;player_name;player_team;track_name;" ..
            "player_x;player_y;player_z\n"
        et.trap_FS_Write(con_header, string.len(con_header), fd)
        for _, ev in ipairs(tracker.construction.events) do
            local line = string.format("%d;%s;%s;%s;%s;%s;%d;%d;%d\n",
                ev.event_time, ev.event_type, ev.player_guid, ev.player_name, ev.player_team,
                ev.track_name, ev.player_x, ev.player_y, ev.player_z)
            et.trap_FS_Write(line, string.len(line), fd)
        end
    end

    -- v6.01: Objective Runs
    if isFeatureEnabled("objective_run_tracking") and #tracker.objective_runs.completed > 0 then
        local orun_header = "\n# OBJECTIVE_RUNS\n" ..
            "# engineer_guid;engineer_name;engineer_team;action_type;track_name;action_time;" ..
            "approach_time_ms;approach_distance;beeline_distance;path_efficiency;" ..
            "self_kills;team_kills;escort_guids;enemies_nearby;nearby_teammates;" ..
            "run_type;obj_x;obj_y;obj_z;killer_guid;killer_name\n"
        et.trap_FS_Write(orun_header, string.len(orun_header), fd)
        for _, run in ipairs(tracker.objective_runs.completed) do
            local line = string.format("%s;%s;%s;%s;%s;%d;%d;%.1f;%.1f;%.3f;%d;%d;%s;%d;%d;%s;%d;%d;%d;%s;%s\n",
                run.engineer_guid, run.engineer_name, run.engineer_team,
                run.action_type, run.track_name, run.action_time,
                run.approach_time_ms, run.approach_distance, run.beeline_distance, run.path_efficiency,
                run.self_kills, run.team_kills, run.escort_guids, run.enemies_nearby, run.nearby_teammates,
                run.run_type, run.obj_x, run.obj_y, run.obj_z,
                run.killer_guid, run.killer_name)
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
    local weapon_fire_count = 0
    for _, _ in pairs(tracker.weapon_fire) do weapon_fire_count = weapon_fire_count + 1 end

    proxPrint(string.format("[PROX v5] Teamplay: %d spawn timings, %d cohesion samples, %d crossfire opps, %d focus fire, %d pushes, %d trades\n",
        #tracker.spawn.kill_timings,
        #tracker.cohesion.samples,
        #tracker.crossfire_opps.events,
        #tracker.focus_fire.events,
        #tracker.pushes.events,
        #tracker.trade_kills.events))
    proxPrint(string.format("[PROX v5] New: %d revives, %d weapon accuracy players, %d kill outcomes, %d hit regions, %d combat positions\n",
        #tracker.revives, weapon_fire_count, #tracker.kill_outcomes.completed, #tracker.hit_regions, #tracker.combat_positions))

    if isFeatureEnabled("reaction_tracking") then
        proxPrint(string.format("[PROX v5] Reaction metrics: %d rows\n", #tracker.reaction_metrics))
    end
    proxPrint(string.format("[PROX v6] Carrier: %d events, %d kills, %d returns | Construction: %d | Vehicles: %d ent, %d escort credits\n",
        #tracker.carrier.events, #tracker.carrier.kills, #tracker.carrier.returns,
        #tracker.construction.events,
        countTableKeys(tracker.vehicles.entities), countTableKeys(tracker.vehicles.escort_credits)))
    proxPrint(string.format("[PROX v6.01] Objective runs: %d completed (%d denied)\n",
        #tracker.objective_runs.completed,
        countByField(tracker.objective_runs.completed, "run_type", "denied")))
    proxPrint(string.format("[PROX v6] Output: %s\n", filename))

    if config.test_mode.enabled and config.test_mode.lifecycle_log then
        outputLifecycleLog()
    end
end

-- Bug 15 fix: pcall wrapper ensures output_in_progress is always cleared
local function outputData()
    if config.output_guard and (tracker.output_in_progress or tracker.output_written) then
        proxPrint("[PROX] Output already written or in progress, skipping\n")
        return
    end
    tracker.output_in_progress = true
    local ok, err = pcall(outputDataInner)
    tracker.output_in_progress = false
    if ok then
        tracker.output_written = true
    else
        et.G_Print("[PROX] ERROR in outputData: " .. tostring(err) .. "\n")
    end
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
    local fd, len = et.trap_FS_FOpenFile(filename, et.FS_WRITE)
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
    tracker.revives = {}
    tracker.weapon_fire = {}
    tracker.kill_outcomes.dead_players = {}
    tracker.kill_outcomes.completed = {}
    tracker.hit_regions = {}
    tracker.combat_positions = {}
    -- v6 carrier reset
    tracker.carrier.active = {}
    tracker.carrier.events = {}
    tracker.carrier.kills = {}
    tracker.carrier.returns = {}
    tracker.carrier.pending_drops = {}
    tracker.vehicles = { entities = {}, escort_credits = {}, last_check_time = 0 }
    tracker.construction = { events = {} }
    tracker.objective_runs.completed = {}
    tracker.objective_runs.constructibles = {}
    tracker.objective_runs.explosives = {}
    tracker.objective_runs.checkpoints = {}
    tracker.objective_runs.last_poll = 0
    last_hr_head = {}
    last_hr_all = {}

    -- Read spawn timers
    refreshSpawnTimers()

    et.G_Print(">>> Proximity Tracker v" .. version .. " initialized\n")
    et.G_Print(">>> Map: " .. tracker.round.map_name .. ", Round: " .. tracker.round.round_num .. "\n")
    et.G_Print(">>> Position sample: " .. config.position_sample_interval .. "ms\n")
    et.G_Print(">>> Spawn timers: Axis=" .. tracker.spawn.axis_interval .. "ms, Allies=" .. tracker.spawn.allies_interval .. "ms\n")
    et.G_Print(">>> Output: " .. config.output_dir .. "\n")
    logObjectiveConfigSummary()
    scanVehicleEntities()
    scanObjectiveEntities()

    -- v5 feature status
    local v5_features = {"spawn_timing", "team_cohesion", "crossfire_opportunities", "focus_fire", "team_push_detection", "trade_kills"}
    local enabled_list = {}
    for _, f in ipairs(v5_features) do
        if isFeatureEnabled(f) then table.insert(enabled_list, f) end
    end
    et.G_Print(">>> v5 Teamplay: " .. (#enabled_list > 0 and table.concat(enabled_list, ", ") or "NONE") .. "\n")

    -- v6 feature status
    local v6_features = {"carrier_tracking", "carrier_returns", "vehicle_tracking", "construction_tracking"}
    local v6_enabled = {}
    for _, f in ipairs(v6_features) do
        if isFeatureEnabled(f) then table.insert(v6_enabled, f) end
    end
    et.G_Print(">>> v6 Objective: " .. (#v6_enabled > 0 and table.concat(v6_enabled, ", ") or "NONE") .. "\n")
    et.G_Print(">>> v6.01 Objective runs: " .. (isFeatureEnabled("objective_run_tracking") and "ENABLED" or "DISABLED") .. "\n")

    if config.test_mode.enabled then
        et.G_Print(">>> TEST MODE ENABLED\n")
    end
end

local last_gamestate = -1

function et_RunFrame(levelTime)
    if not config.enabled then return end
    frame_level_time = levelTime  -- Bug 1 fix: store for gameTime(); freezes during pause

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

        -- v6: Close all active carriers
        if isFeatureEnabled("carrier_tracking") then
            for clientNum, _ in pairs(tracker.carrier.active) do
                endCarrierTracking(clientNum, "round_end", nil, nil)
            end
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

        if isFeatureEnabled("objective_run_tracking") then
            pollConstructionProgress(gameTime())
        end
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

    local weapon = safe_gentity_get(attacker, "ps.weapon") or 0  -- Bug 5 fix: fetch once

    -- v4: Engagement tracking
    if isFeatureEnabled("engagement_tracking") then
        local engagement = tracker.engagements[target]
        if not engagement then engagement = createEngagement(target) end
        recordHit(engagement, attacker, damage, weapon)
    end

    -- v4: Reaction tracking
    if isFeatureEnabled("reaction_tracking") then
        registerReactionSignals(target, attacker, gameTime())
    end

    -- v5.1: Kill outcome — track body damage (gib detection via threshold)
    if isFeatureEnabled("kill_outcome_tracking") then
        local victim_pm_type = safe_gentity_get(target, "ps.pm_type")
        if victim_pm_type == PM_DEAD then
            recordKillOutcomeBodyDamage(target, attacker, damage, meansOfDeath)
        end
    end

    -- v5: Crossfire opportunity execution check
    checkCrossfireExecution(attacker, target, damage)

    -- v5: Weapon accuracy — record hit
    -- Use meansOfDeath → weapon mapping for correct attribution (fixes delayed-damage weapons)
    local accuracy_weapon = MOD_TO_WEAPON[meansOfDeath] or weapon
    local atk_guid = getPlayerGUID(attacker)
    if atk_guid and atk_guid ~= "" then
        if not tracker.weapon_fire[atk_guid] then
            tracker.weapon_fire[atk_guid] = {
                _name = getPlayerName(attacker),
                _team = getPlayerTeam(attacker),
            }
        end
        if not tracker.weapon_fire[atk_guid][accuracy_weapon] then
            tracker.weapon_fire[atk_guid][accuracy_weapon] = { shots = 0, hits = 0, kills = 0, headshots = 0 }
        end
        tracker.weapon_fire[atk_guid][accuracy_weapon].hits = tracker.weapon_fire[atk_guid][accuracy_weapon].hits + 1

        -- Headshot detection via hitRegions delta.
        -- G_LogRegionHit(attacker, HR_HEAD) fires BEFORE this Lua callback (g_combat.c:1689 vs 1811),
        -- so pers.playerStats.hitRegions[0] is already incremented when we read it here.
        local hr_head = tonumber(safe_gentity_get(attacker, "pers.playerStats.hitRegions", HR_HEAD)) or 0
        local prev_hr = last_hr_head[attacker] or 0
        if hr_head > prev_hr then
            tracker.weapon_fire[atk_guid][accuracy_weapon].headshots = tracker.weapon_fire[atk_guid][accuracy_weapon].headshots + 1
        end
        last_hr_head[attacker] = hr_head

        -- v5.2: Full hit region tracking (HEAD/ARMS/BODY/LEGS)
        if isFeatureEnabled("hit_region_tracking") then
            -- Initialize cached region counts for this attacker on first hit
            if not last_hr_all[attacker] then
                last_hr_all[attacker] = {}
                for hr = 0, HR_NUM_HITREGIONS - 1 do
                    last_hr_all[attacker][hr] = tonumber(safe_gentity_get(attacker, "pers.playerStats.hitRegions", hr)) or 0
                end
            end
            -- Detect which region was hit via delta comparison
            local detected_region = -1
            for hr = 0, HR_NUM_HITREGIONS - 1 do
                local cur = tonumber(safe_gentity_get(attacker, "pers.playerStats.hitRegions", hr)) or 0
                if cur > (last_hr_all[attacker][hr] or 0) then
                    detected_region = hr
                    break
                end
            end
            -- Update cached values
            for hr = 0, HR_NUM_HITREGIONS - 1 do
                last_hr_all[attacker][hr] = tonumber(safe_gentity_get(attacker, "pers.playerStats.hitRegions", hr)) or 0
            end
            -- Record hit region event
            if detected_region >= 0 and #tracker.hit_regions < 5000 then
                local vic_guid = getPlayerGUID(target)
                table.insert(tracker.hit_regions, {
                    time = gameTime(),
                    attacker_guid = atk_guid,
                    attacker_name = getPlayerName(attacker),
                    victim_guid = vic_guid or "",
                    victim_name = getPlayerName(target) or "",
                    weapon = accuracy_weapon,
                    region = detected_region,
                    damage = damage,
                })
            end
        end
    end

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

    -- v5.1: Kill outcome tracking (all deaths from enemy kills)
    if isFeatureEnabled("kill_outcome_tracking") and death_type == "killed" and killer and isValidClient(killer) then
        recordKillOutcomeDeath(victim, killer, meansOfDeath)
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

        -- v5: Weapon accuracy — record kill (use MOD → weapon for correct attribution)
        local kill_guid = getPlayerGUID(killer)
        if kill_guid and kill_guid ~= "" then
            local kill_weapon = MOD_TO_WEAPON[meansOfDeath] or (safe_gentity_get(killer, "ps.weapon") or 0)
            if tracker.weapon_fire[kill_guid] and tracker.weapon_fire[kill_guid][kill_weapon] then
                tracker.weapon_fire[kill_guid][kill_weapon].kills = tracker.weapon_fire[kill_guid][kill_weapon].kills + 1
            end
        end

        -- v5.2: Combat position tracking (killer + victim positions on kill)
        if isFeatureEnabled("combat_positions") then
            local killer_pos = getPlayerPos(killer)
            if killer_pos and death_pos then
                local cp_weapon = MOD_TO_WEAPON[meansOfDeath] or (safe_gentity_get(killer, "ps.weapon") or 0)
                local cp_killer_health = tonumber(safe_gentity_get(killer, "health")) or 0
                local cp_axis_alive, cp_allies_alive = countAlivePerTeam()
                table.insert(tracker.combat_positions, {
                    time = now,
                    event_type = "kill",
                    attacker_guid = getPlayerGUID(killer) or "",
                    attacker_name = getPlayerName(killer) or "",
                    attacker_team = getPlayerTeam(killer) or "",
                    attacker_class = getPlayerClass(killer) or "",
                    victim_guid = getPlayerGUID(victim) or "",
                    victim_name = getPlayerName(victim) or "",
                    victim_team = getPlayerTeam(victim) or "",
                    victim_class = getPlayerClass(victim) or "",
                    ax = round(killer_pos.x, 0),
                    ay = round(killer_pos.y, 0),
                    az = round(killer_pos.z, 0),
                    vx = round(death_pos.x, 0),
                    vy = round(death_pos.y, 0),
                    vz = round(death_pos.z, 0),
                    weapon = cp_weapon,
                    mod = meansOfDeath or 0,
                    killer_health = cp_killer_health,
                    axis_alive = cp_axis_alive,
                    allies_alive = cp_allies_alive,
                })
            end
        end

        -- v6: Carrier kill detection
        if isFeatureEnabled("carrier_tracking") and tracker.carrier.active[victim] then
            local k_guid = (killer and isValidClient(killer)) and getPlayerGUID(killer) or ""
            local k_name = (killer and isValidClient(killer)) and getPlayerName(killer) or ""
            local k_team = (killer and isValidClient(killer)) and getPlayerTeam(killer) or ""
            endCarrierTracking(victim, "killed", k_guid, k_name)
            -- Patch killer_team and means_of_death into the last carrier kill entry
            local kills = tracker.carrier.kills
            if #kills > 0 then
                kills[#kills].killer_team = k_team
                kills[#kills].means_of_death = meansOfDeath or 0
            end
        end
    end

    -- v6.01: Denied objective run detection
    if isFeatureEnabled("objective_run_tracking") and death_type == "killed" then
        local orun_track = tracker.player_tracks[victim]
        if orun_track and orun_track.class == "ENGINEER" then
            local orun_pos = death_pos or getPlayerPos(victim)
            if orun_pos then
                local nearest_obj = findNearestConstructible(orun_pos, config.objective_run.denied_run_radius)
                if not nearest_obj then
                    nearest_obj = findNearestExplosive(orun_pos, config.objective_run.denied_run_radius)
                end
                if not nearest_obj then
                    nearest_obj = findNearestCheckpoint(orun_pos, config.objective_run.denied_run_radius)
                end
                if nearest_obj then
                    local obj_p = {x = nearest_obj.x, y = nearest_obj.y, z = nearest_obj.z}
                    local appr_time, appr_dist, bee_dist, eff =
                        calculateApproachMetrics(orun_track, gameTime(), config.objective_run.path_clear_window_ms)
                    local k_guid = (killer and killer ~= 1022 and killer ~= 1023 and isValidClient(killer)) and getPlayerGUID(killer) or ""
                    local k_name = (killer and killer ~= 1022 and killer ~= 1023 and isValidClient(killer)) and getPlayerName(killer) or ""

                    table.insert(tracker.objective_runs.completed, {
                        engineer_guid = orun_track.guid,
                        engineer_name = orun_track.name,
                        engineer_team = orun_track.team,
                        action_type = "approach_killed",
                        track_name = nearest_obj.track or "",
                        action_time = gameTime(),
                        approach_time_ms = appr_time,
                        approach_distance = appr_dist,
                        beeline_distance = bee_dist,
                        path_efficiency = eff,
                        self_kills = 0, team_kills = 0, escort_guids = "",
                        enemies_nearby = 0, nearby_teammates = 0,
                        run_type = "denied",
                        obj_x = round(obj_p.x, 0), obj_y = round(obj_p.y, 0), obj_z = round(obj_p.z, 0),
                        killer_guid = k_guid,
                        killer_name = k_name,
                    })
                end
            end
        end
    end
end

function et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)
    if not config.enabled then return end
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end

    if revived == 1 then
        -- v5.1: Kill outcome — revive resolves pending death
        if isFeatureEnabled("kill_outcome_tracking") and tracker.kill_outcomes.dead_players[clientNum] then
            local reviver_client = tonumber(safe_gentity_get(clientNum, "pers.lastrevive_client"))
            local reviver_guid = (reviver_client and isValidClient(reviver_client)) and getPlayerGUID(reviver_client) or ""
            local reviver_name = (reviver_client and isValidClient(reviver_client)) and getPlayerName(reviver_client) or ""
            finalizeKillOutcome(clientNum, "revived", reviver_guid, reviver_name)
        end

        local track = tracker.player_tracks[clientNum]
        local now = gameTime()
        local pos = getPlayerPos(clientNum)

        -- Always record revive event in player track (not just in test mode)
        if track and pos then
            local health = safe_gentity_get(clientNum, "health") or 100
            local weapon = safe_gentity_get(clientNum, "ps.weapon") or 0
            local stance, sprint = getPlayerMovementState(clientNum, 0)
            table.insert(track.path, {
                time = now, x = round(pos.x, 1), y = round(pos.y, 1), z = round(pos.z, 1),
                health = health, speed = 0, weapon = weapon,
                stance = stance, sprint = sprint, event = "revived"
            })
        end

        -- Record revive event with medic detection
        if pos then
            local revived_guid = getPlayerGUID(clientNum)
            local revived_name = getPlayerName(clientNum)
            local revived_team_num = safe_gentity_get(clientNum, "sess.sessionTeam") or 0

            -- Find nearest medic-class teammate (the one who revived)
            local medic_guid, medic_name = "", ""
            local min_medic_dist = math.huge
            local max_clients = get_max_clients()
            for i = 0, max_clients - 1 do
                if i ~= clientNum and isPlayerAlive(i) then
                    local t = safe_gentity_get(i, "sess.sessionTeam")
                    local pclass = safe_gentity_get(i, "sess.playerType")
                    if t == revived_team_num and pclass == 1 then  -- 1 = MEDIC
                        local mpos = getPlayerPos(i)
                        if mpos then
                            local d = distance3D(pos, mpos)
                            if d < min_medic_dist then
                                min_medic_dist = d
                                medic_guid = getPlayerGUID(i)
                                medic_name = getPlayerName(i)
                            end
                        end
                    end
                end
            end

            -- Find distance to nearest enemy
            local enemy_team_num = revived_team_num == 1 and 2 or 1
            local min_enemy_dist = math.huge
            local nearest_enemy_guid = ""
            for i = 0, max_clients - 1 do
                if isPlayerAlive(i) then
                    local t = safe_gentity_get(i, "sess.sessionTeam")
                    if t == enemy_team_num then
                        local epos = getPlayerPos(i)
                        if epos then
                            local d = distance3D(pos, epos)
                            if d < min_enemy_dist then
                                min_enemy_dist = d
                                nearest_enemy_guid = getPlayerGUID(i)
                            end
                        end
                    end
                end
            end

            -- under_fire: was the revived player in an active engagement?
            local under_fire = tracker.engagements[clientNum] ~= nil and "1" or "0"

            table.insert(tracker.revives, {
                time = now,
                medic_guid = medic_guid,
                medic_name = medic_name,
                revived_guid = revived_guid,
                revived_name = revived_name,
                x = round(pos.x, 1),
                y = round(pos.y, 1),
                z = round(pos.z, 1),
                distance_to_enemy = round(min_enemy_dist == math.huge and 0 or min_enemy_dist, 1),
                nearest_enemy_guid = nearest_enemy_guid,
                under_fire = under_fire,
            })
        end

        return
    end

    -- v5.2: Tap-out detection — normal respawn (not revive) resolves pending kill outcome
    if isFeatureEnabled("kill_outcome_tracking") and tracker.kill_outcomes.dead_players[clientNum] then
        finalizeKillOutcome(clientNum, "tapped_out", nil, nil)
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
    -- Bug 3 fix: close active engagement if this client was the target
    local engagement = tracker.engagements[clientNum]
    if engagement then
        closeEngagement(engagement, "disconnect", nil)
    end
    -- v6: End carrier tracking on disconnect
    if tracker.carrier.active[clientNum] then
        endCarrierTracking(clientNum, "disconnected", nil, nil)
    end
    tracker.last_stamina[clientNum] = nil
    last_hr_head[clientNum] = nil
    last_hr_all[clientNum] = nil
    client_cache[clientNum] = nil
end

function et_ClientConnect(clientNum, firstTime, isBot)
    updateClientCache(clientNum)
    return nil
end

function et_ClientUserinfoChanged(clientNum)
    updateClientCache(clientNum)
end

-- ===== WEAPON FIRE TRACKING =====

function et_WeaponFire(clientNum, weapon)
    if not config.enabled then return end
    if not isValidClient(clientNum) or not isPlayerActive(clientNum) then return end
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end

    local guid = getPlayerGUID(clientNum)
    if not guid or guid == "" then return end

    if not tracker.weapon_fire[guid] then
        tracker.weapon_fire[guid] = {
            _name = getPlayerName(clientNum),
            _team = getPlayerTeam(clientNum),
        }
    end
    if not tracker.weapon_fire[guid][weapon] then
        tracker.weapon_fire[guid][weapon] = { shots = 0, hits = 0, kills = 0, headshots = 0 }
    end
    tracker.weapon_fire[guid][weapon].shots = tracker.weapon_fire[guid][weapon].shots + 1
end

-- ===== SHUTDOWN HANDLER =====
-- Saves data if map changes without going through intermission (server crash, map command, etc.)
function et_ShutdownGame(restart)
    if not config.enabled then return end
    if restart == 0 and not tracker.output_written then
        round_end_unix = os.time()
        -- End all active player tracks
        for clientnum, track in pairs(tracker.player_tracks) do
            local pos = getPlayerPos(clientnum)
            track.death_time = gameTime()
            track.death_pos = pos
            track.death_type = "shutdown"
            if pos then
                table.insert(track.path, {
                    time = track.death_time, x = round(pos.x, 1), y = round(pos.y, 1), z = round(pos.z, 1),
                    health = safe_gentity_get(clientnum, "health") or 0,
                    speed = 0, weapon = safe_gentity_get(clientnum, "ps.weapon") or 0,
                    stance = 0, sprint = 0, event = "shutdown"
                })
            end
            table.insert(tracker.completed_tracks, track)
        end
        tracker.player_tracks = {}
        -- Close all active engagements
        local active_targets = {}
        for target_slot, _ in pairs(tracker.engagements) do
            table.insert(active_targets, target_slot)
        end
        for _, target_slot in ipairs(active_targets) do
            local engagement = tracker.engagements[target_slot]
            if engagement then closeEngagement(engagement, "shutdown", nil) end
        end
        -- v6: Close all active carriers
        if isFeatureEnabled("carrier_tracking") then
            for clientNum, _ in pairs(tracker.carrier.active) do
                endCarrierTracking(clientNum, "shutdown", nil, nil)
            end
        end
        outputData()
    end
end

-- ===== v6 EVENT DETECTION VIA CONSOLE =====

function et_Print(text)
    if not config.enabled then return end
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end

    -- v6 Phase 1: Carrier pickup + secure detection
    if isFeatureEnabled("carrier_tracking") then
        -- Item pickup detection
        local pickup_client, pickup_flag = string.match(text, "Item:%s+(%d+)%s+(team_CTF_%a+)")
        if pickup_client and pickup_flag then
            local cn = tonumber(pickup_client)
            if cn and isValidClient(cn) and isPlayerActive(cn) then
                local flag_team = "redflag"
                if string.find(pickup_flag, "blue") then flag_team = "blueflag" end
                startCarrierTracking(cn, flag_team)
            end
        end

        -- Secure detection via announce
        if string.find(text, "legacy announce:") then
            local lower = string.lower(text)
            if string.find(lower, "transmitted") or string.find(lower, "secured") or
               string.find(lower, "delivered") or string.find(lower, "escaped") then
                for clientnum, state in pairs(tracker.carrier.active) do
                    local pw5 = tonumber(safe_gentity_get(clientnum, "ps.powerups", 5)) or 0
                    local pw6 = tonumber(safe_gentity_get(clientnum, "ps.powerups", 6)) or 0
                    if pw5 == 0 and pw6 == 0 then
                        endCarrierTracking(clientnum, "secured", nil, nil)
                    end
                end
            end
        end
    end

    -- v6 Phase 1.5: Flag return detection
    if isFeatureEnabled("carrier_returns") then
        if string.find(text, "legacy popup:") and string.find(string.lower(text), "returned") then
            -- Find which pending drop matches
            for flag_team, pd in pairs(tracker.carrier.pending_drops) do
                -- Attribution: find nearest defending player to drop position
                local best_client, best_dist = nil, math.huge
                local max_clients = get_max_clients()
                for cn = 0, max_clients - 1 do
                    if isPlayerActive(cn) and isPlayerAlive(cn) then
                        local team = getPlayerTeam(cn)
                        local is_defender = (flag_team == "redflag" and team == "AXIS") or
                                           (flag_team == "blueflag" and team == "ALLIES")
                        if is_defender then
                            local pos = getPlayerPos(cn)
                            if pos and pd.drop_pos then
                                local d = distance3D(pos, pd.drop_pos)
                                if d < best_dist then
                                    best_dist = d
                                    best_client = cn
                                end
                            end
                        end
                    end
                end
                if best_client then
                    local now = gameTime()
                    table.insert(tracker.carrier.returns, {
                        return_time = now,
                        returner_guid = getPlayerGUID(best_client),
                        returner_name = getPlayerName(best_client),
                        returner_team = getPlayerTeam(best_client),
                        flag_team = flag_team,
                        original_carrier_guid = pd.carrier_guid or "",
                        drop_time = pd.drop_time,
                        return_delay_ms = now - pd.drop_time,
                        drop_x = round((pd.drop_pos and pd.drop_pos.x) or 0, 0),
                        drop_y = round((pd.drop_pos and pd.drop_pos.y) or 0, 0),
                        drop_z = round((pd.drop_pos and pd.drop_pos.z) or 0, 0),
                    })
                end
                tracker.carrier.pending_drops[flag_team] = nil
                break  -- only one return per message
            end
        end
    end

    -- v6.01: Flag/checkpoint capture detection
    if isFeatureEnabled("objective_run_tracking") then
        if string.find(text, "legacy popup:") and string.find(string.lower(text), "captured") then
            -- Poll all cached checkpoints to find which one changed team
            for entNum, cp in pairs(tracker.objective_runs.checkpoints) do
                local current_team = tonumber(safe_gentity_get(entNum, "count")) or 0
                if current_team ~= cp.last_team and current_team > 0 then
                    -- This checkpoint was just captured! Find nearest player of capturing team
                    local cap_team_str = current_team == 1 and "AXIS" or "ALLIES"
                    local best_cn, best_dist = nil, 500  -- max 500u from checkpoint
                    local max_clients = get_max_clients()
                    for cn = 0, max_clients - 1 do
                        if isPlayerActive(cn) and isPlayerAlive(cn) and getPlayerTeam(cn) == cap_team_str then
                            local p = getPlayerPos(cn)
                            if p then
                                local d = distance3D(p, {x = cp.x, y = cp.y, z = cp.z})
                                if d < best_dist then
                                    best_dist = d
                                    best_cn = cn
                                end
                            end
                        end
                    end
                    if best_cn then
                        local pos = getPlayerPos(best_cn)
                        local cap_name = cp.scriptName ~= "" and cp.scriptName or string.format("checkpoint_%d", entNum)
                        -- Record as construction event
                        table.insert(tracker.construction.events, {
                            event_time = gameTime(),
                            event_type = "flag_captured",
                            player_guid = getPlayerGUID(best_cn),
                            player_name = getPlayerName(best_cn),
                            player_team = getPlayerTeam(best_cn),
                            track_name = cap_name,
                            player_x = round((pos and pos.x) or 0, 0),
                            player_y = round((pos and pos.y) or 0, 0),
                            player_z = round((pos and pos.z) or 0, 0),
                        })
                        -- Also record as objective run
                        assembleObjectiveRun(best_cn, "flag_captured", cap_name, {x = cp.x, y = cp.y, z = cp.z})
                    end
                    cp.last_team = current_team
                end
            end
        end
    end

    -- v6 Phase 3: Construction/destruction events
    if isFeatureEnabled("construction_tracking") then
        -- Dynamite Plant
        local plant_client, plant_track = string.match(text, "Dynamite_Plant:%s+(%d+)%s+(.+)")
        if plant_client then
            local cn = tonumber(plant_client)
            if cn and isValidClient(cn) and isPlayerActive(cn) then
                local pos = getPlayerPos(cn)
                table.insert(tracker.construction.events, {
                    event_time = gameTime(),
                    event_type = "dynamite_plant",
                    player_guid = getPlayerGUID(cn),
                    player_name = getPlayerName(cn),
                    player_team = getPlayerTeam(cn),
                    track_name = plant_track:gsub("%s+$", ""),
                    player_x = round((pos and pos.x) or 0, 0),
                    player_y = round((pos and pos.y) or 0, 0),
                    player_z = round((pos and pos.z) or 0, 0),
                })
                assembleObjectiveRun(cn, "dynamite_plant", plant_track:gsub("%s+$", ""), pos and {x=pos.x, y=pos.y, z=pos.z} or nil)
            end
        end

        -- Dynamite Diffuse (engine typo for "defuse")
        local defuse_client, defuse_track = string.match(text, "Dynamite_Diffuse:%s+(%d+)%s+(.+)")
        if defuse_client then
            local cn = tonumber(defuse_client)
            if cn and isValidClient(cn) and isPlayerActive(cn) then
                local pos = getPlayerPos(cn)
                table.insert(tracker.construction.events, {
                    event_time = gameTime(),
                    event_type = "dynamite_defuse",
                    player_guid = getPlayerGUID(cn),
                    player_name = getPlayerName(cn),
                    player_team = getPlayerTeam(cn),
                    track_name = defuse_track:gsub("%s+$", ""),
                    player_x = round((pos and pos.x) or 0, 0),
                    player_y = round((pos and pos.y) or 0, 0),
                    player_z = round((pos and pos.z) or 0, 0),
                })
                assembleObjectiveRun(cn, "dynamite_defuse", defuse_track:gsub("%s+$", ""), pos and {x=pos.x, y=pos.y, z=pos.z} or nil)
            end
        end

        -- Objective Destroyed
        local destroy_client, destroy_track = string.match(text, "Objective_Destroyed:%s+(%d+)%s+(.+)")
        if destroy_client then
            local cn = tonumber(destroy_client)
            if cn and isValidClient(cn) and isPlayerActive(cn) then
                local pos = getPlayerPos(cn)
                table.insert(tracker.construction.events, {
                    event_time = gameTime(),
                    event_type = "objective_destroyed",
                    player_guid = getPlayerGUID(cn),
                    player_name = getPlayerName(cn),
                    player_team = getPlayerTeam(cn),
                    track_name = destroy_track:gsub("%s+$", ""),
                    player_x = round((pos and pos.x) or 0, 0),
                    player_y = round((pos and pos.y) or 0, 0),
                    player_z = round((pos and pos.z) or 0, 0),
                })
                assembleObjectiveRun(cn, "objective_destroyed", destroy_track:gsub("%s+$", ""), pos and {x=pos.x, y=pos.y, z=pos.z} or nil)
            end
        end

        -- Repair (construction complete) — NO track name available
        local repair_client = string.match(text, "Repair:%s+(%d+)")
        if repair_client and not plant_client and not defuse_client and not destroy_client then
            local cn = tonumber(repair_client)
            if cn and isValidClient(cn) and isPlayerActive(cn) then
                local pos = getPlayerPos(cn)
                table.insert(tracker.construction.events, {
                    event_time = gameTime(),
                    event_type = "construction_complete",
                    player_guid = getPlayerGUID(cn),
                    player_name = getPlayerName(cn),
                    player_team = getPlayerTeam(cn),
                    track_name = "",
                    player_x = round((pos and pos.x) or 0, 0),
                    player_y = round((pos and pos.y) or 0, 0),
                    player_z = round((pos and pos.z) or 0, 0),
                })
                assembleObjectiveRun(cn, "construction_complete", "", pos and {x=pos.x, y=pos.y, z=pos.z} or nil)
            end
        end
    end
end

-- ===== MODULE END =====
et.G_Print(">>> Proximity Tracker v" .. version .. " loaded\n")
