-- ============================================================
-- PROXIMITY TRACKER v4.1 - FULL PLAYER TRACKING + TEST MODE
-- ET:Legacy Lua Module for Combat Analytics
--
-- KEY FEATURES (v4):
--   • FULL PLAYER TRACKING - All players, spawn to death
--   • Position + velocity + health + weapon every 500ms
--   • Stance tracking (standing/crouching/prone)
--   • Sprint detection
--   • First movement time after spawn
--   • Combat engagement tracking (damage, kills, escapes)
--   • Crossfire detection (2+ attackers within 1 second)
--   • Per-map heatmaps (kills, movement, combat, escapes)
--   • GUID tracking for forever stats
--
-- NEW IN v4.1 (TEST MODE):
--   • test_mode config - disable advanced features for testing
--   • Feature flags - independent control of each analytics feature
--   • Death type categorization (killed/selfkill/fallen/world/teamkill)
--   • Action event tracking (damage received/dealt)
--   • Human-readable lifecycle log output (_lifecycle.txt)
--
-- OUTPUT: Single file per round with:
--   - PLAYER_TRACKS: Full movement history for each player
--   - ENGAGEMENTS: Combat interactions (if enabled)
--   - KILL_HEATMAP: Where kills happen (if enabled)
--   - MOVEMENT_HEATMAP: Where players move (if enabled)
--   - _lifecycle.txt: Human-readable lifecycle log (test mode)
--
-- LOAD ORDER: lua_modules "c0rnp0rn.lua proximity_tracker.lua"
-- ============================================================

local modname = "proximity_tracker"
local version = "4.1"

-- ===== CONFIGURATION =====
local config = {
    enabled = true,
    debug = false,
    output_dir = "proximity/",  -- Separate from gamestats/ to avoid mixing data

    -- Crossfire detection
    crossfire_window_ms = 1000,     -- 1 second for crossfire detection

    -- Escape detection
    escape_time_ms = 5000,          -- 5 seconds no damage
    escape_distance = 300,          -- 300 units minimum travel

    -- Position sampling (v4: 500ms for better movement capture)
    position_sample_interval = 500,  -- 2 samples per second - captures strafe/dodge patterns

    -- Heatmap
    grid_size = 512,

    -- Minimum damage to count
    min_damage = 1,

    -- ===== TEST MODE (v4.1) =====
    -- When enabled, disables advanced analytics and outputs human-readable lifecycle log
    test_mode = {
        enabled = false,            -- Master toggle for test mode
        lifecycle_log = true,       -- Output human-readable lifecycle log file
        action_annotations = true,  -- Capture fire/grenade/damage events in path
    },

    -- ===== FEATURE FLAGS (v4.1) =====
    -- Can be controlled independently, or auto-disabled when test_mode.enabled = true
    features = {
        engagement_tracking = true,   -- Full engagement analytics (damage tracking)
        crossfire_detection = true,   -- Multi-attacker coordination detection
        escape_detection = true,      -- Escape timeout/distance detection
        heatmap_generation = true,    -- Spatial heatmap aggregation
    }
}

-- ===== FEATURE FLAG HELPERS =====
-- Returns effective feature state (respects test_mode override)
local function isFeatureEnabled(feature_name)
    -- In test mode, all advanced features are disabled
    if config.test_mode.enabled then
        return false
    end
    return config.features[feature_name]
end

-- ===== MOVEMENT STATE BIT FLAGS =====
local PMF_DUCKED = 1        -- Crouching
local PMF_PRONE = 512       -- Prone
local PMF_SPRINT = 16384    -- Sprinting

-- ===== MODULE DATA =====
local tracker = {
    -- Active engagements (target_slot -> engagement data)
    engagements = {},

    -- Completed engagements for output
    completed = {},

    -- Heatmaps (aggregated during round)
    kill_heatmap = {},      -- grid_key -> {axis, allies}
    movement_heatmap = {},  -- grid_key -> {traversal, combat}

    -- Round info
    round = {
        map_name = "",
        round_num = 0,
        start_time = 0
    },

    -- Counter for unique engagement IDs
    engagement_counter = 0,

    -- Player position cache (for movement tracking)
    last_positions = {},

    -- Full player tracking (all players, spawn to death)
    player_tracks = {},         -- clientnum -> track data
    completed_tracks = {},      -- Finished tracks for output
    last_sample_time = 0,       -- Last global sample timestamp

    -- v4.1: Action event buffer for test mode (clientnum -> array of action events)
    action_buffer = {}
}

-- ===== UTILITY FUNCTIONS =====

local function getPlayerPos(clientnum)
    local origin = et.gentity_get(clientnum, "ps.origin")
    if not origin then return nil end
    return {
        x = tonumber(origin[1]) or 0,
        y = tonumber(origin[2]) or 0,
        z = tonumber(origin[3]) or 0
    }
end

local function getPlayerGUID(clientnum)
    -- Primary method: get from userinfo (most reliable)
    local userinfo = et.trap_GetUserinfo(clientnum)
    if userinfo then
        local guid = et.Info_ValueForKey(userinfo, "cl_guid")
        if guid and guid ~= "" then
            return guid
        end
    end
    -- Fallback: generate a session-unique ID from slot number
    -- This ensures we can still track players even without GUID
    return string.format("SLOT%d", clientnum)
end

local function sanitizeName(name)
    -- Remove characters that would break CSV/output parsing
    if not name then return "Unknown" end
    name = string.gsub(name, ";", "_")  -- semicolon breaks field separator
    name = string.gsub(name, "|", "_")  -- pipe breaks attacker separator
    name = string.gsub(name, ",", "_")  -- comma breaks sub-field separator
    name = string.gsub(name, "\n", "")  -- newline breaks line parsing
    name = string.gsub(name, "\r", "")  -- carriage return
    return name
end

local function getPlayerName(clientnum)
    local name = et.gentity_get(clientnum, "pers.netname") or "Unknown"
    return sanitizeName(name)
end

local function getPlayerTeam(clientnum)
    local team = et.gentity_get(clientnum, "sess.sessionTeam")
    if team == 1 then return "AXIS"
    elseif team == 2 then return "ALLIES"
    else return "SPEC"
    end
end

local function isPlayerActive(clientnum)
    local connected = et.gentity_get(clientnum, "pers.connected")
    if connected ~= 2 then return false end
    local team = et.gentity_get(clientnum, "sess.sessionTeam")
    return team == 1 or team == 2
end

local function distance3D(pos1, pos2)
    if not pos1 or not pos2 then return 9999 end
    local dx = pos1.x - pos2.x
    local dy = pos1.y - pos2.y
    local dz = pos1.z - pos2.z
    return math.sqrt(dx*dx + dy*dy + dz*dz)
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

-- ===== PLAYER STATE FUNCTIONS =====

local function getPlayerVelocity(clientnum)
    local vel = et.gentity_get(clientnum, "ps.velocity")
    if not vel then return 0, 0, 0 end
    return tonumber(vel[1]) or 0, tonumber(vel[2]) or 0, tonumber(vel[3]) or 0
end

local function getPlayerSpeed(clientnum)
    local vx, vy, vz = getPlayerVelocity(clientnum)
    -- Horizontal speed only (ignore vertical for movement analysis)
    return math.sqrt(vx*vx + vy*vy)
end

local function getPlayerMovementState(clientnum)
    local pm_flags = et.gentity_get(clientnum, "ps.pm_flags") or 0

    -- Decode stance: 0=standing, 1=crouching, 2=prone
    -- Lua 5.4 uses native & operator for bitwise AND
    local stance = 0
    if (pm_flags & PMF_PRONE) ~= 0 then
        stance = 2
    elseif (pm_flags & PMF_DUCKED) ~= 0 then
        stance = 1
    end

    -- Check sprint
    local sprinting = 0
    if (pm_flags & PMF_SPRINT) ~= 0 then
        sprinting = 1
    end

    return stance, sprinting
end

local function getPlayerClass(clientnum)
    local ptype = et.gentity_get(clientnum, "sess.playerType") or 0
    local classes = { [0] = "SOLDIER", [1] = "MEDIC", [2] = "ENGINEER", [3] = "FIELDOPS", [4] = "COVERTOPS" }
    return classes[ptype] or "UNKNOWN"
end

-- ===== DEATH TYPE CATEGORIZATION (v4.1) =====
-- ET:Legacy means of death constants
local MOD_SELFKILL = 37
local MOD_FALLING = 38

local function getDeathType(victim, killer, meansOfDeath)
    -- Self-kill (/kill command)
    if meansOfDeath == MOD_SELFKILL then
        return "selfkill"
    end

    -- Fall damage
    if meansOfDeath == MOD_FALLING then
        return "fallen"
    end

    -- World damage (1022 = world, 1023 = world)
    if killer == 1022 or killer == 1023 then
        return "world"
    end

    -- Self-inflicted (shouldn't reach here but safety check)
    if killer == victim then
        return "selfkill"
    end

    -- Check for teamkill
    if killer and isPlayerActive(killer) and isPlayerActive(victim) then
        local victim_team = getPlayerTeam(victim)
        local killer_team = getPlayerTeam(killer)
        if victim_team == killer_team then
            return "teamkill"
        end
    end

    -- Standard kill by enemy
    return "killed"
end

-- ===== FULL PLAYER TRACKING =====

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
        death_type = nil,  -- v4.1: killed/selfkill/fallen/world/teamkill/round_end/disconnect
        killer_name = nil, -- v4.1: Name of killer (if killed by player)

        -- Path: array of samples
        -- Each sample: {time, x, y, z, health, speed, weapon, stance, sprint}
        path = {},

        -- v4.1: Action events for lifecycle log (damage recv/dealt, etc.)
        actions = {},

        -- Track first movement (time to start moving after spawn)
        first_move_time = nil,
        had_input = false
    }

    -- Record spawn position as first sample
    if pos then
        local health = et.gentity_get(clientnum, "health") or 100
        local weapon = et.gentity_get(clientnum, "ps.weapon") or 0
        local stance, sprint = getPlayerMovementState(clientnum)
        local speed = getPlayerSpeed(clientnum)

        table.insert(track.path, {
            time = now,
            x = round(pos.x, 1),
            y = round(pos.y, 1),
            z = round(pos.z, 1),
            health = health,
            speed = round(speed, 1),
            weapon = weapon,
            stance = stance,
            sprint = sprint,
            event = "spawn"
        })
    end

    tracker.player_tracks[clientnum] = track

    if config.debug then
        et.G_Printf("[PROX] Track started: %s (%s) at %.0f,%.0f\n",
            track.name, track.class, pos and pos.x or 0, pos and pos.y or 0)
    end

    return track
end

local function samplePlayer(clientnum, track, event_type)
    local now = gameTime()
    local pos = getPlayerPos(clientnum)
    if not pos then return end

    local health = et.gentity_get(clientnum, "health") or 0
    local weapon = et.gentity_get(clientnum, "ps.weapon") or 0
    local stance, sprint = getPlayerMovementState(clientnum)
    local speed = getPlayerSpeed(clientnum)

    -- Detect first movement
    if not track.first_move_time and speed > 10 then
        track.first_move_time = now
        track.had_input = true
    end

    table.insert(track.path, {
        time = now,
        x = round(pos.x, 1),
        y = round(pos.y, 1),
        z = round(pos.z, 1),
        health = health,
        speed = round(speed, 1),
        weapon = weapon,
        stance = stance,
        sprint = sprint,
        event = event_type or "sample"
    })

    -- Update movement heatmap (only if feature enabled)
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
    track.death_type = death_type or "unknown"  -- v4.1: Store death type
    track.killer_name = killer_name             -- v4.1: Store killer name (if applicable)

    -- Add final sample
    if death_pos then
        local health = 0
        local weapon = et.gentity_get(clientnum, "ps.weapon") or 0
        table.insert(track.path, {
            time = track.death_time,
            x = round(death_pos.x, 1),
            y = round(death_pos.y, 1),
            z = round(death_pos.z, 1),
            health = health,
            speed = 0,
            weapon = weapon,
            stance = 0,
            sprint = 0,
            event = death_type or "death"  -- v4.1: Use death type as event
        })
    end

    -- Move to completed
    table.insert(tracker.completed_tracks, track)
    tracker.player_tracks[clientnum] = nil

    if config.debug then
        et.G_Printf("[PROX] Track ended: %s - %d samples, lived %dms, type=%s\n",
            track.name, #track.path, track.death_time - track.spawn_time, track.death_type)
    end
end

local function sampleAllPlayers()
    local now = gameTime()

    -- Only sample every position_sample_interval ms
    if now - tracker.last_sample_time < config.position_sample_interval then
        return
    end
    tracker.last_sample_time = now

    -- Sample all tracked players
    for clientnum, track in pairs(tracker.player_tracks) do
        if isPlayerActive(clientnum) then
            samplePlayer(clientnum, track, "sample")
        end
    end
end

-- ===== ENGAGEMENT MANAGEMENT =====

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
        killer_name = nil
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
    
    tracker.engagements[target_slot] = engagement
    
    if config.debug then
        et.G_Printf("[PROX] Engagement #%d started: %s\n", engagement.id, engagement.target_name)
    end
    
    return engagement
end

local function recordHit(engagement, attacker_slot, damage, weapon)
    local now = gameTime()
    local attacker_guid = getPlayerGUID(attacker_slot)
    local target_pos = getPlayerPos(engagement.target_slot)
    
    -- Update or create attacker entry
    if not engagement.attackers[attacker_guid] then
        engagement.attackers[attacker_guid] = {
            slot = attacker_slot,
            name = getPlayerName(attacker_slot),
            team = getPlayerTeam(attacker_slot),
            damage = 0,
            hits = 0,
            first_hit = now,
            last_hit = now,
            weapons = {},
            got_kill = false
        }
        table.insert(engagement.attacker_order, attacker_guid)
    end
    
    local attacker = engagement.attackers[attacker_guid]
    attacker.damage = attacker.damage + damage
    attacker.hits = attacker.hits + 1
    attacker.last_hit = now
    
    -- Track weapons used
    if weapon and weapon > 0 then
        attacker.weapons[weapon] = (attacker.weapons[weapon] or 0) + 1
    end
    
    -- Update engagement
    engagement.total_damage = engagement.total_damage + damage
    engagement.last_hit_time = now
    
    -- Calculate distance traveled
    if target_pos and engagement.last_hit_pos then
        local dist = distance3D(target_pos, engagement.last_hit_pos)
        engagement.distance_traveled = engagement.distance_traveled + dist
    end
    engagement.last_hit_pos = target_pos
    
    -- Record position on hit
    if target_pos then
        table.insert(engagement.position_path, {
            time = now,
            x = round(target_pos.x, 1),
            y = round(target_pos.y, 1),
            z = round(target_pos.z, 1),
            event = "hit"
        })

        -- Update movement heatmap (only if feature enabled)
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
    -- Need at least 2 attackers
    if #engagement.attacker_order < 2 then
        return false, nil, nil
    end
    
    -- Check if second attacker hit within crossfire window of first
    local first_guid = engagement.attacker_order[1]
    local second_guid = engagement.attacker_order[2]
    
    local first_hit = engagement.attackers[first_guid].first_hit
    local second_hit = engagement.attackers[second_guid].first_hit
    local delay = second_hit - first_hit
    
    if delay <= config.crossfire_window_ms then
        -- Crossfire detected! Collect all participants within window
        local participants = {}
        for _, guid in ipairs(engagement.attacker_order) do
            local attacker = engagement.attackers[guid]
            if attacker.first_hit - first_hit <= config.crossfire_window_ms then
                table.insert(participants, guid)
            end
        end
        return true, delay, participants
    end
    
    return false, nil, nil
end

local function closeEngagement(engagement, outcome, killer_slot)
    local now = gameTime()
    local end_pos = getPlayerPos(engagement.target_slot) or engagement.last_hit_pos
    
    engagement.end_time = now
    engagement.duration = now - engagement.start_time
    engagement.outcome = outcome
    engagement.end_pos = end_pos
    
    -- Record final position
    if end_pos then
        table.insert(engagement.position_path, {
            time = now,
            x = round(end_pos.x, 1),
            y = round(end_pos.y, 1),
            z = round(end_pos.z, 1),
            event = outcome == "killed" and "death" or "escape"
        })
        
        -- Update final distance
        if engagement.last_hit_pos then
            engagement.distance_traveled = engagement.distance_traveled + 
                distance3D(end_pos, engagement.last_hit_pos)
        end
    end
    
    -- If killed, mark the killer
    if outcome == "killed" and killer_slot then
        local killer_guid = getPlayerGUID(killer_slot)
        engagement.killer_guid = killer_guid
        engagement.killer_name = getPlayerName(killer_slot)

        if engagement.attackers[killer_guid] then
            engagement.attackers[killer_guid].got_kill = true
        end

        -- Update kill heatmap (only if feature enabled)
        if isFeatureEnabled("heatmap_generation") and end_pos then
            local key = getGridKey(end_pos.x, end_pos.y)
            if not tracker.kill_heatmap[key] then
                tracker.kill_heatmap[key] = { axis = 0, allies = 0 }
            end

            local killer_team = getPlayerTeam(killer_slot)
            if killer_team == "AXIS" then
                tracker.kill_heatmap[key].axis = tracker.kill_heatmap[key].axis + 1
            else
                tracker.kill_heatmap[key].allies = tracker.kill_heatmap[key].allies + 1
            end
        end
    end

    -- Escape movement heatmap (only if feature enabled)
    if isFeatureEnabled("heatmap_generation") and outcome == "escaped" and end_pos then
        local key = getGridKey(end_pos.x, end_pos.y)
        if not tracker.movement_heatmap[key] then
            tracker.movement_heatmap[key] = { traversal = 0, combat = 0, escape = 0 }
        end
        tracker.movement_heatmap[key].escape = tracker.movement_heatmap[key].escape + 1
    end

    -- Detect crossfire (only if feature enabled)
    local is_crossfire, delay, participants = false, nil, nil
    if isFeatureEnabled("crossfire_detection") then
        is_crossfire, delay, participants = detectCrossfire(engagement)
    end
    engagement.is_crossfire = is_crossfire
    engagement.crossfire_delay = delay
    engagement.crossfire_participants = participants
    
    -- Move to completed
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
    
    for target_slot, engagement in pairs(tracker.engagements) do
        local time_since_hit = now - engagement.last_hit_time
        
        -- Check if escape conditions met
        if time_since_hit >= config.escape_time_ms then
            local current_pos = getPlayerPos(target_slot)
            if current_pos and engagement.last_hit_pos then
                local escape_dist = distance3D(current_pos, engagement.last_hit_pos)
                
                if escape_dist >= config.escape_distance then
                    closeEngagement(engagement, "escaped", nil)
                end
            end
        end
        
        -- Position sampling during active engagement
        if tracker.engagements[target_slot] then  -- still active
            local time_since_sample = now - engagement.last_sample_time
            if time_since_sample >= config.position_sample_interval then
                local pos = getPlayerPos(target_slot)
                if pos then
                    table.insert(engagement.position_path, {
                        time = now,
                        x = round(pos.x, 1),
                        y = round(pos.y, 1),
                        z = round(pos.z, 1),
                        event = "sample"
                    })
                end
                engagement.last_sample_time = now
            end
        end
    end
end

-- ===== FILE OUTPUT =====

-- Forward declaration for lifecycle log function (defined below outputData)
local outputLifecycleLog

local function serializeAttackers(attackers, attacker_order)
    -- Convert attackers to JSON-like format
    local parts = {}
    for _, guid in ipairs(attacker_order) do
        local a = attackers[guid]
        local weapons_str = ""
        for w, count in pairs(a.weapons) do
            weapons_str = weapons_str .. w .. ":" .. count .. ";"
        end
        if weapons_str == "" then weapons_str = "0:0" end
        
        table.insert(parts, string.format(
            "%s,%s,%s,%d,%d,%d,%d,%s,%s",
            guid, a.name, a.team, a.damage, a.hits,
            a.first_hit, a.last_hit,
            a.got_kill and "1" or "0",
            weapons_str
        ))
    end
    return table.concat(parts, "|")
end

local function serializePositions(path)
    local parts = {}
    for _, p in ipairs(path) do
        table.insert(parts, string.format("%d,%.1f,%.1f,%.1f,%s",
            p.time, p.x, p.y, p.z, p.event))
    end
    return table.concat(parts, "|")
end

local function serializeTrackPath(path)
    -- Format: time,x,y,z,health,speed,weapon,stance,sprint,event
    local parts = {}
    for _, p in ipairs(path) do
        table.insert(parts, string.format("%d,%.1f,%.1f,%.1f,%d,%.1f,%d,%d,%d,%s",
            p.time, p.x, p.y, p.z, p.health, p.speed, p.weapon, p.stance, p.sprint, p.event))
    end
    return table.concat(parts, "|")
end

local function outputData()
    if #tracker.completed == 0 and #tracker.completed_tracks == 0 then
        et.G_Print("[PROX] No data to output\n")
        return
    end

    -- Filename: gamestats/YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt
    local filename = string.format("%s%s-%s-round-%d_engagements.txt",
        config.output_dir,
        os.date('%Y-%m-%d-%H%M%S'),
        tracker.round.map_name,
        tracker.round.round_num)

    et.G_Print("[PROX] Attempting to write: " .. filename .. "\n")

    -- et.FS_WRITE = 1 (write mode)
    local fd, len = et.trap_FS_FOpenFile(filename, 1)
    if not fd or fd == -1 or fd == 0 then
        et.G_Print("[PROX] ERROR: Could not open file for writing: " .. filename .. "\n")
        et.G_Print("[PROX] Check that " .. config.output_dir .. " directory exists!\n")
        return
    end
    
    -- Header
    local header = string.format(
        "# PROXIMITY_TRACKER_V4\n" ..
        "# map=%s\n" ..
        "# round=%d\n" ..
        "# crossfire_window=%d\n" ..
        "# escape_time=%d\n" ..
        "# escape_distance=%d\n" ..
        "# position_sample_interval=%d\n",
        tracker.round.map_name,
        tracker.round.round_num,
        config.crossfire_window_ms,
        config.escape_time_ms,
        config.escape_distance,
        config.position_sample_interval
    )
    et.trap_FS_Write(header, string.len(header), fd)
    
    -- Engagement format header
    local fmt_header = "# ENGAGEMENTS\n" ..
        "# id;start_time;end_time;duration;target_guid;target_name;target_team;" ..
        "outcome;total_damage;killer_guid;killer_name;num_attackers;" ..
        "is_crossfire;crossfire_delay;crossfire_participants;" ..
        "start_x;start_y;start_z;end_x;end_y;end_z;distance_traveled;" ..
        "positions;attackers\n"
    et.trap_FS_Write(fmt_header, string.len(fmt_header), fd)
    
    -- Write engagements
    for _, eng in ipairs(tracker.completed) do
        local cf_participants = eng.crossfire_participants and 
            table.concat(eng.crossfire_participants, ",") or ""
        
        local line = string.format(
            "%d;%d;%d;%d;%s;%s;%s;%s;%d;%s;%s;%d;%s;%s;%s;" ..
            "%.1f;%.1f;%.1f;%.1f;%.1f;%.1f;%.1f;%s;%s\n",
            eng.id,
            eng.start_time,
            eng.end_time or 0,
            eng.duration or 0,
            eng.target_guid,
            eng.target_name,
            eng.target_team,
            eng.outcome or "unknown",
            eng.total_damage,
            eng.killer_guid or "",
            eng.killer_name or "",
            #eng.attacker_order,
            eng.is_crossfire and "1" or "0",
            eng.crossfire_delay or "",
            cf_participants,
            eng.start_pos and eng.start_pos.x or 0,
            eng.start_pos and eng.start_pos.y or 0,
            eng.start_pos and eng.start_pos.z or 0,
            eng.end_pos and eng.end_pos.x or 0,
            eng.end_pos and eng.end_pos.y or 0,
            eng.end_pos and eng.end_pos.z or 0,
            eng.distance_traveled or 0,
            serializePositions(eng.position_path),
            serializeAttackers(eng.attackers, eng.attacker_order)
        )
        et.trap_FS_Write(line, string.len(line), fd)
    end

    -- PLAYER TRACKS (full movement history)
    -- v4.1: Added death_type field
    local track_header = "\n# PLAYER_TRACKS\n" ..
        "# guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path\n" ..
        "# death_type: killed|selfkill|fallen|world|teamkill|round_end|disconnect|unknown\n" ..
        "# path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |\n" ..
        "# stance: 0=standing, 1=crouching, 2=prone | sprint: 0=no, 1=yes\n"
    et.trap_FS_Write(track_header, string.len(track_header), fd)

    for _, track in ipairs(tracker.completed_tracks) do
        local line = string.format("%s;%s;%s;%s;%d;%d;%s;%s;%d;%s\n",
            track.guid,
            track.name,
            track.team,
            track.class,
            track.spawn_time,
            track.death_time or 0,
            track.first_move_time or "",
            track.death_type or "unknown",  -- v4.1: Include death type
            #track.path,
            serializeTrackPath(track.path)
        )
        et.trap_FS_Write(line, string.len(line), fd)
    end

    -- Kill heatmap
    local hm_header = "\n# KILL_HEATMAP\n# grid_x;grid_y;axis_kills;allies_kills\n"
    et.trap_FS_Write(hm_header, string.len(hm_header), fd)
    
    for key, data in pairs(tracker.kill_heatmap) do
        local gx, gy = string.match(key, "(-?%d+),(-?%d+)")
        local line = string.format("%s;%s;%d;%d\n", gx, gy, data.axis, data.allies)
        et.trap_FS_Write(line, string.len(line), fd)
    end
    
    -- Movement heatmap
    local mv_header = "\n# MOVEMENT_HEATMAP\n# grid_x;grid_y;traversal;combat;escape\n"
    et.trap_FS_Write(mv_header, string.len(mv_header), fd)
    
    for key, data in pairs(tracker.movement_heatmap) do
        local gx, gy = string.match(key, "(-?%d+),(-?%d+)")
        local line = string.format("%s;%s;%d;%d;%d\n", 
            gx, gy, data.traversal, data.combat, data.escape)
        et.trap_FS_Write(line, string.len(line), fd)
    end
    
    et.trap_FS_FCloseFile(fd)

    local crossfire_count = 0
    for _, eng in ipairs(tracker.completed) do
        if eng.is_crossfire then crossfire_count = crossfire_count + 1 end
    end

    local total_samples = 0
    for _, track in ipairs(tracker.completed_tracks) do
        total_samples = total_samples + #track.path
    end

    et.G_Print(string.format("[PROX] Saved: %d tracks (%d samples), %d engagements (%d crossfire)\n",
        #tracker.completed_tracks, total_samples, #tracker.completed, crossfire_count))
    et.G_Print(string.format("[PROX] Output: %s\n", filename))

    -- v4.1: Output lifecycle log if test mode enabled
    if config.test_mode.enabled and config.test_mode.lifecycle_log then
        outputLifecycleLog()
    end
end

-- ===== LIFECYCLE LOG OUTPUT (v4.1) =====
-- Human-readable log for testing player lifecycles

outputLifecycleLog = function()
    if #tracker.completed_tracks == 0 then
        et.G_Print("[PROX] No lifecycle data to output\n")
        return
    end

    -- Filename: proximity/YYYY-MM-DD-HHMMSS-mapname-round-N_lifecycle.txt
    local filename = string.format("%s%s-%s-round-%d_lifecycle.txt",
        config.output_dir,
        os.date('%Y-%m-%d-%H%M%S'),
        tracker.round.map_name,
        tracker.round.round_num)

    et.G_Print("[PROX] Writing lifecycle log: " .. filename .. "\n")

    local fd, len = et.trap_FS_FOpenFile(filename, 1)
    if not fd or fd == -1 or fd == 0 then
        et.G_Print("[PROX] ERROR: Could not open lifecycle log file\n")
        return
    end

    -- Header
    local header = string.format(
        "# PROXIMITY_TRACKER v%s - LIFECYCLE LOG\n" ..
        "# map=%s round=%d\n" ..
        "# test_mode=true\n" ..
        "# Generated: %s\n" ..
        "#\n" ..
        "# Format:\n" ..
        "#   [SPAWN] guid=X name=X team=X class=X pos=(x,y,z) time=X\n" ..
        "#     +Xms: MOVE pos=(x,y,z) speed=X health=X\n" ..
        "#     +Xms: ACTION type=dmg_recv|dmg_dealt amount=X from/to=X weapon=X\n" ..
        "#     +Xms: EVENT type=revived\n" ..
        "#   [END] guid=X type=killed|selfkill|fallen|... killer=X pos=(x,y,z) time=X duration=Xms\n" ..
        "#\n\n",
        version,
        tracker.round.map_name,
        tracker.round.round_num,
        os.date('%Y-%m-%d %H:%M:%S')
    )
    et.trap_FS_Write(header, string.len(header), fd)

    -- Process each completed track
    for _, track in ipairs(tracker.completed_tracks) do
        -- Merge path samples and actions into a single timeline
        local timeline = {}

        -- Add path samples
        for _, sample in ipairs(track.path) do
            table.insert(timeline, {
                time = sample.time,
                source = "path",
                data = sample
            })
        end

        -- Add action events
        if track.actions then
            for _, action in ipairs(track.actions) do
                table.insert(timeline, {
                    time = action.time,
                    source = "action",
                    data = action
                })
            end
        end

        -- Sort by time
        table.sort(timeline, function(a, b) return a.time < b.time end)

        -- Write SPAWN line
        local spawn_pos = track.spawn_pos or {x=0, y=0, z=0}
        local spawn_line = string.format("[SPAWN] guid=%s name=%s team=%s class=%s pos=(%.0f,%.0f,%.0f) time=%d\n",
            track.guid,
            track.name,
            track.team,
            track.class,
            spawn_pos.x, spawn_pos.y, spawn_pos.z,
            track.spawn_time)
        et.trap_FS_Write(spawn_line, string.len(spawn_line), fd)

        -- Write timeline entries (skip spawn event, it's already in SPAWN line)
        for _, entry in ipairs(timeline) do
            local delta = entry.time - track.spawn_time
            local line = ""

            if entry.source == "path" then
                local p = entry.data
                -- Skip spawn event (already written)
                if p.event == "spawn" then
                    -- skip
                elseif p.event == "revived" then
                    line = string.format("  +%dms: EVENT type=revived pos=(%.0f,%.0f,%.0f) health=%d\n",
                        delta, p.x, p.y, p.z, p.health)
                elseif p.event == "sample" then
                    line = string.format("  +%dms: MOVE pos=(%.0f,%.0f,%.0f) speed=%.1f health=%d\n",
                        delta, p.x, p.y, p.z, p.speed, p.health)
                -- Final events (death types) are handled by END line
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

            if line ~= "" then
                et.trap_FS_Write(line, string.len(line), fd)
            end
        end

        -- Write END line
        local death_pos = track.death_pos or {x=0, y=0, z=0}
        local duration = (track.death_time or track.spawn_time) - track.spawn_time
        local killer_str = track.killer_name and (" killer=" .. track.killer_name) or ""
        local end_line = string.format("[END] guid=%s type=%s%s pos=(%.0f,%.0f,%.0f) time=%d duration=%dms\n\n",
            track.guid,
            track.death_type or "unknown",
            killer_str,
            death_pos.x, death_pos.y, death_pos.z,
            track.death_time or 0,
            duration)
        et.trap_FS_Write(end_line, string.len(end_line), fd)
    end

    et.trap_FS_FCloseFile(fd)
    et.G_Print(string.format("[PROX] Lifecycle log: %d player lifecycles written\n", #tracker.completed_tracks))
end

-- ===== ENGINE CALLBACKS =====

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)

    -- Get map info safely
    local serverinfo = et.trap_GetConfigstring(0)  -- CS_SERVERINFO = 0
    if serverinfo then
        tracker.round.map_name = et.Info_ValueForKey(serverinfo, "mapname") or "unknown"
    else
        tracker.round.map_name = "unknown"
    end

    -- Get round number (may not exist on all servers)
    local round_str = et.trap_Cvar_Get("g_currentRound")
    tracker.round.round_num = tonumber(round_str) or 1
    tracker.round.start_time = levelTime

    -- Reset all tracking data
    tracker.engagements = {}
    tracker.completed = {}
    tracker.kill_heatmap = {}
    tracker.movement_heatmap = {}
    tracker.engagement_counter = 0
    tracker.last_positions = {}

    -- Reset player tracking
    tracker.player_tracks = {}
    tracker.completed_tracks = {}
    tracker.last_sample_time = 0
    tracker.action_buffer = {}  -- v4.1: Reset action buffer

    et.G_Print(">>> Proximity Tracker v" .. version .. " initialized\n")
    et.G_Print(">>> Map: " .. tracker.round.map_name .. ", Round: " .. tracker.round.round_num .. "\n")
    et.G_Print(">>> Position sample interval: " .. config.position_sample_interval .. "ms\n")
    et.G_Print(">>> Output directory: " .. config.output_dir .. "\n")
    -- v4.1: Show test mode status
    if config.test_mode.enabled then
        et.G_Print(">>> TEST MODE ENABLED - Advanced features disabled, lifecycle log active\n")
    end
end

local last_gamestate = -1

function et_RunFrame(levelTime)
    if not config.enabled then return end

    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1

    -- Check for round end
    if last_gamestate == 0 and gamestate == 3 then
        -- End all active player tracks (round ended)
        for clientnum, track in pairs(tracker.player_tracks) do
            local pos = getPlayerPos(clientnum)
            track.death_time = gameTime()
            track.death_pos = pos
            track.death_type = "round_end"  -- v4.1: Set death type
            if pos then
                table.insert(track.path, {
                    time = track.death_time,
                    x = round(pos.x, 1),
                    y = round(pos.y, 1),
                    z = round(pos.z, 1),
                    health = et.gentity_get(clientnum, "health") or 0,
                    speed = 0,
                    weapon = et.gentity_get(clientnum, "ps.weapon") or 0,
                    stance = 0,
                    sprint = 0,
                    event = "round_end"
                })
            end
            table.insert(tracker.completed_tracks, track)
        end
        tracker.player_tracks = {}

        -- Close all active engagements as round_end
        for target_slot, engagement in pairs(tracker.engagements) do
            closeEngagement(engagement, "round_end", nil)
        end

        outputData()
    end

    last_gamestate = gamestate

    -- During play
    if gamestate == 0 then
        -- Sample all player positions every interval
        sampleAllPlayers()

        -- Check for escapes (only if escape detection enabled)
        if isFeatureEnabled("escape_detection") then
            checkEscapes(levelTime)
        end
    end
end

function et_Damage(target, attacker, damage, damageFlags, meansOfDeath)
    if not config.enabled then return end

    -- Validate
    if not target or not attacker then return end
    if target == attacker then return end  -- self damage
    if attacker == 1022 or attacker == 1023 then return end  -- world damage
    if damage < config.min_damage then return end

    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end

    -- Check teams
    if not isPlayerActive(target) or not isPlayerActive(attacker) then return end

    -- Engagement tracking (only if feature enabled)
    if isFeatureEnabled("engagement_tracking") then
        -- Get or create engagement for target
        local engagement = tracker.engagements[target]
        if not engagement then
            engagement = createEngagement(target)
        end

        -- Record the hit
        local weapon = et.gentity_get(attacker, "ps.weapon") or 0
        recordHit(engagement, attacker, damage, weapon)
    end

    -- v4.1: Action annotation for test mode (record damage received/dealt)
    if config.test_mode.enabled and config.test_mode.action_annotations then
        local now = gameTime()
        local weapon = et.gentity_get(attacker, "ps.weapon") or 0

        -- Record damage received for target (store in track.actions)
        local target_track = tracker.player_tracks[target]
        if target_track then
            table.insert(target_track.actions, {
                time = now,
                type = "dmg_recv",
                amount = damage,
                from_guid = getPlayerGUID(attacker),
                from_name = getPlayerName(attacker),
                weapon = weapon
            })
        end

        -- Record damage dealt for attacker (store in track.actions)
        local attacker_track = tracker.player_tracks[attacker]
        if attacker_track then
            table.insert(attacker_track.actions, {
                time = now,
                type = "dmg_dealt",
                amount = damage,
                to_guid = getPlayerGUID(target),
                to_name = getPlayerName(target),
                weapon = weapon
            })
        end
    end
end

function et_Obituary(victim, killer, meansOfDeath)
    if not config.enabled then return end

    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end

    -- v4.1: Determine death type and killer name
    local death_type = getDeathType(victim, killer, meansOfDeath)
    local killer_name = nil
    if killer and killer ~= 1022 and killer ~= 1023 and killer ~= victim and isPlayerActive(killer) then
        killer_name = getPlayerName(killer)
    end

    -- End player track on death with death type and killer name
    local death_pos = getPlayerPos(victim)
    endPlayerTrack(victim, death_pos, death_type, killer_name)

    -- Engagement tracking (only if feature enabled)
    if isFeatureEnabled("engagement_tracking") then
        -- Check if we have an engagement for this victim
        local engagement = tracker.engagements[victim]

        if engagement then
            -- Close with kill
            closeEngagement(engagement, "killed", killer)
        else
            -- No engagement exists - create a minimal one for the kill
            -- (can happen if killed instantly without prior damage, e.g., headshot)
            engagement = createEngagement(victim)

            -- Add killer as attacker if valid
            if killer and killer ~= 1022 and killer ~= 1023 and killer ~= victim then
                local weapon = et.gentity_get(killer, "ps.weapon") or 0
                recordHit(engagement, killer, 100, weapon)  -- assume lethal damage
            end

            closeEngagement(engagement, "killed", killer)
        end
    end
end

function et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)
    if not config.enabled then return end

    -- Handle revives (v4.1: add revive action annotation but continue existing track)
    if revived == 1 then
        -- v4.1: Add revive action annotation for test mode
        if config.test_mode.enabled and config.test_mode.action_annotations then
            local track = tracker.player_tracks[clientNum]
            if track then
                local now = gameTime()
                local pos = getPlayerPos(clientNum)
                -- Add revive as a path sample with "revived" event
                if pos then
                    local health = et.gentity_get(clientNum, "health") or 100
                    local weapon = et.gentity_get(clientNum, "ps.weapon") or 0
                    local stance, sprint = getPlayerMovementState(clientNum)
                    table.insert(track.path, {
                        time = now,
                        x = round(pos.x, 1),
                        y = round(pos.y, 1),
                        z = round(pos.z, 1),
                        health = health,
                        speed = 0,
                        weapon = weapon,
                        stance = stance,
                        sprint = sprint,
                        event = "revived"
                    })
                end
            end
        end
        if config.debug then
            et.G_Printf("[PROX] %s was revived (continuing existing track)\n", getPlayerName(clientNum))
        end
        return
    end

    -- Check if player is on a team
    if not isPlayerActive(clientNum) then return end

    -- End any existing track for this slot (shouldn't happen, but safety)
    if tracker.player_tracks[clientNum] then
        endPlayerTrack(clientNum, nil, nil)  -- No death type for safety cleanup
    end

    -- Start new track
    createPlayerTrack(clientNum)
end

function et_ClientDisconnect(clientNum)
    -- End track if player disconnects mid-round
    if tracker.player_tracks[clientNum] then
        local pos = getPlayerPos(clientNum)
        endPlayerTrack(clientNum, pos, "disconnect")  -- v4.1: Pass disconnect death type
    end
end

-- ===== MODULE END =====
et.G_Print(">>> Proximity Tracker v" .. version .. " loaded\n")
