-- ============================================================
-- PROXIMITY TRACKER v3.0 - ENGAGEMENT-CENTRIC
-- ET:Legacy Lua Module for Combat Analytics
--
-- KEY FEATURES:
--   • Track combat engagements (not every bullet)
--   • Escape detection (5s no damage + 300 units moved)
--   • Crossfire detection (2+ attackers within 1 second)
--   • Position sampling during engagement (every 2s + events)
--   • GUID tracking for forever stats
--   • Per-map heatmaps
--
-- OUTPUT: Single file per round with engagement data
-- LOAD ORDER: lua_modules "c0rnp0rn.lua proximity_tracker.lua"
-- ============================================================

local modname = "proximity_tracker"
local version = "3.0"

-- ===== CONFIGURATION =====
local config = {
    enabled = true,
    debug = false,
    output_dir = "gamestats/",
    
    -- Crossfire detection
    crossfire_window_ms = 1000,     -- 1 second for crossfire detection
    
    -- Escape detection
    escape_time_ms = 5000,          -- 5 seconds no damage
    escape_distance = 300,          -- 300 units minimum travel
    
    -- Position sampling
    position_sample_interval = 2000, -- sample every 2 seconds during engagement
    
    -- Heatmap
    grid_size = 512,
    
    -- Minimum damage to count
    min_damage = 1
}

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
    last_positions = {}
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
    local guid = et.Info_ValueForKey(et.trap_GetUserinfo(clientnum), "cl_guid")
    if not guid or guid == "" then
        guid = et.gentity_get(clientnum, "sess.guid")
    end
    return guid or "UNKNOWN"
end

local function getPlayerName(clientnum)
    return et.gentity_get(clientnum, "pers.netname") or "Unknown"
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
        
        -- Update movement heatmap
        local key = getGridKey(target_pos.x, target_pos.y)
        if not tracker.movement_heatmap[key] then
            tracker.movement_heatmap[key] = { traversal = 0, combat = 0, escape = 0 }
        end
        tracker.movement_heatmap[key].combat = tracker.movement_heatmap[key].combat + 1
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
        
        -- Update kill heatmap
        if end_pos then
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
    
    -- Escape movement heatmap
    if outcome == "escaped" and end_pos then
        local key = getGridKey(end_pos.x, end_pos.y)
        if not tracker.movement_heatmap[key] then
            tracker.movement_heatmap[key] = { traversal = 0, combat = 0, escape = 0 }
        end
        tracker.movement_heatmap[key].escape = tracker.movement_heatmap[key].escape + 1
    end
    
    -- Detect crossfire
    local is_crossfire, delay, participants = detectCrossfire(engagement)
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

local function outputData()
    if #tracker.completed == 0 then
        et.G_Print("[PROX] No engagements to output\n")
        return
    end
    
    -- Filename
    local filename = string.format("%s%s-%s-round-%d_engagements.txt",
        config.output_dir,
        os.date('%Y-%m-%d-%H%M%S'),
        tracker.round.map_name,
        tracker.round.round_num)
    
    local fd = et.trap_FS_FOpenFile(filename, et.FS_WRITE)
    if fd == -1 then
        et.G_Print("[PROX] ERROR: Could not open file\n")
        return
    end
    
    -- Header
    local header = string.format(
        "# PROXIMITY_TRACKER_V3\n" ..
        "# map=%s\n" ..
        "# round=%d\n" ..
        "# crossfire_window=%d\n" ..
        "# escape_time=%d\n" ..
        "# escape_distance=%d\n",
        tracker.round.map_name,
        tracker.round.round_num,
        config.crossfire_window_ms,
        config.escape_time_ms,
        config.escape_distance
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
    
    et.G_Print(string.format("[PROX] Saved %d engagements (%d crossfire) to %s\n",
        #tracker.completed, crossfire_count, filename))
end

-- ===== ENGINE CALLBACKS =====

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)
    
    local serverinfo = et.trap_GetConfigstring(et.CS_SERVERINFO)
    tracker.round.map_name = et.Info_ValueForKey(serverinfo, "mapname") or "unknown"
    tracker.round.round_num = tonumber(et.trap_Cvar_Get("g_currentRound")) or 1
    tracker.round.start_time = levelTime
    
    -- Reset
    tracker.engagements = {}
    tracker.completed = {}
    tracker.kill_heatmap = {}
    tracker.movement_heatmap = {}
    tracker.engagement_counter = 0
    tracker.last_positions = {}
    
    et.G_Print(">>> Proximity Tracker v" .. version .. " initialized\n")
    et.G_Print(">>> Map: " .. tracker.round.map_name .. ", Round: " .. tracker.round.round_num .. "\n")
end

local last_gamestate = -1

function et_RunFrame(levelTime)
    if not config.enabled then return end
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    
    -- Check for round end
    if last_gamestate == 0 and gamestate == 3 then
        -- Close all active engagements as round_end
        for target_slot, engagement in pairs(tracker.engagements) do
            closeEngagement(engagement, "round_end", nil)
        end
        outputData()
    end
    
    last_gamestate = gamestate
    
    -- During play: check for escapes
    if gamestate == 0 then
        checkEscapes(levelTime)
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
    
    -- Get or create engagement for target
    local engagement = tracker.engagements[target]
    if not engagement then
        engagement = createEngagement(target)
    end
    
    -- Record the hit
    local weapon = et.gentity_get(attacker, "ps.weapon") or 0
    recordHit(engagement, attacker, damage, weapon)
end

function et_Obituary(victim, killer, meansOfDeath)
    if not config.enabled then return end
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end
    
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

-- ===== MODULE END =====
et.G_Print(">>> Proximity Tracker v" .. version .. " loaded\n")
