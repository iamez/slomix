-- ============================================================
-- PROXIMITY TRACKER v2.0 - KILL-CENTRIC
-- ET:Legacy Lua Module for Combat Analytics
--
-- DESIGN PHILOSOPHY:
--   • Only store data at KILL events (not every frame)
--   • Include GUID for cross-session player tracking
--   • Include map_name for heatmap context
--   • 350x less data than v1 (~70 rows/round vs ~24,500)
--
-- OUTPUT: Single file per round with all kill context
--   • kills.txt - Kill events with full spatial context
--
-- LOAD ORDER: lua_modules "c0rnp0rn.lua proximity_tracker.lua"
-- ============================================================

local modname = "proximity_tracker"
local version = "2.0"

-- Configuration
local config = {
    enabled = true,
    debug = false,
    output_dir = "gamestats/",
    
    -- Proximity thresholds
    nearby_distance = 300,      -- units to count as "nearby" ally/enemy
    crossfire_distance = 400,   -- units for crossfire detection
    
    -- Heatmap
    grid_size = 512             -- units per grid cell
}

-- Module data (isolated, no globals)
local tracker = {
    -- Kill events with full context
    kills = {},
    
    -- Heatmap aggregation
    heatmap = {},
    
    -- Round info
    round = {
        map_name = "",
        round_num = 0,
        start_time = 0
    }
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
    -- Get player GUID for cross-session tracking
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
    local health = tonumber(et.gentity_get(clientnum, "health")) or 0
    
    return (team == 1 or team == 2) and health > 0
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

-- ===== CORE TRACKING FUNCTIONS =====

-- Get nearby players at a specific moment
local function getNearbyPlayers(clientnum, distance_threshold, same_team_only)
    local nearby = {}
    local pos = getPlayerPos(clientnum)
    if not pos then return nearby end
    
    local team = et.gentity_get(clientnum, "sess.sessionTeam")
    local maxclients = tonumber(et.trap_Cvar_Get("sv_maxclients")) or 64
    
    for other = 0, maxclients - 1 do
        if other ~= clientnum then
            local other_connected = et.gentity_get(other, "pers.connected")
            if other_connected == 2 then
                local other_team = et.gentity_get(other, "sess.sessionTeam")
                local other_health = tonumber(et.gentity_get(other, "health")) or 0
                
                -- Filter by team if requested
                local team_match = not same_team_only or (other_team == team)
                
                if team_match and other_health > 0 and (other_team == 1 or other_team == 2) then
                    local other_pos = getPlayerPos(other)
                    if other_pos then
                        local dist = distance3D(pos, other_pos)
                        if dist < distance_threshold then
                            table.insert(nearby, {
                                slot = other,
                                name = getPlayerName(other),
                                guid = getPlayerGUID(other),
                                distance = round(dist, 1)
                            })
                        end
                    end
                end
            end
        end
    end
    
    return nearby
end

-- Determine engagement type (1v1, 2v1, etc.)
local function getEngagementType(killer_allies, victim_allies)
    local attackers = 1 + killer_allies
    local defenders = 1 + victim_allies
    
    if attackers == 1 and defenders == 1 then
        return "1v1"
    elseif attackers > defenders then
        return string.format("%dv%d", attackers, defenders)
    elseif defenders > attackers then
        return string.format("%dv%d", attackers, defenders)
    else
        return string.format("%dv%d", attackers, defenders)
    end
end

-- Record a kill with full context
local function recordKill(killer, victim, mod)
    local killer_pos = getPlayerPos(killer)
    local victim_pos = getPlayerPos(victim)
    
    if not killer_pos or not victim_pos then return end
    
    -- Get nearby allies for both
    local killer_allies = getNearbyPlayers(killer, config.nearby_distance, true)
    local victim_allies = getNearbyPlayers(victim, config.nearby_distance, true)
    
    -- Build supporting allies list (names only, for crossfire tracking)
    local supporting = {}
    for _, ally in ipairs(killer_allies) do
        table.insert(supporting, ally.name)
    end
    
    local kill_data = {
        game_time = et.trap_Milliseconds() - tracker.round.start_time,
        
        -- Killer
        killer_slot = killer,
        killer_guid = getPlayerGUID(killer),
        killer_name = getPlayerName(killer),
        killer_team = getPlayerTeam(killer),
        killer_x = round(killer_pos.x, 1),
        killer_y = round(killer_pos.y, 1),
        killer_z = round(killer_pos.z, 1),
        
        -- Victim
        victim_slot = victim,
        victim_guid = getPlayerGUID(victim),
        victim_name = getPlayerName(victim),
        victim_team = getPlayerTeam(victim),
        victim_x = round(victim_pos.x, 1),
        victim_y = round(victim_pos.y, 1),
        victim_z = round(victim_pos.z, 1),
        
        -- Combat
        distance = round(distance3D(killer_pos, victim_pos), 1),
        weapon = et.gentity_get(killer, "ps.weapon") or 0,
        mod = mod,
        
        -- Engagement context
        engagement_type = getEngagementType(#killer_allies, #victim_allies),
        killer_nearby_allies = #killer_allies,
        victim_nearby_allies = #victim_allies,
        supporting_allies = supporting
    }
    
    table.insert(tracker.kills, kill_data)
    
    -- Update heatmap (based on victim death location)
    local grid_x = math.floor(victim_pos.x / config.grid_size)
    local grid_y = math.floor(victim_pos.y / config.grid_size)
    local key = string.format("%d,%d", grid_x, grid_y)
    
    if not tracker.heatmap[key] then
        tracker.heatmap[key] = { axis = 0, allies = 0 }
    end
    
    if kill_data.killer_team == "AXIS" then
        tracker.heatmap[key].axis = tracker.heatmap[key].axis + 1
    else
        tracker.heatmap[key].allies = tracker.heatmap[key].allies + 1
    end
    
    if config.debug then
        et.G_Printf("[PROX] Kill: %s -> %s (%s, %.0f units)\n",
            kill_data.killer_name, kill_data.victim_name,
            kill_data.engagement_type, kill_data.distance)
    end
end

-- ===== FILE OUTPUT =====

local function outputData()
    if #tracker.kills == 0 then
        et.G_Print("[PROX] No kills to output\n")
        return
    end
    
    -- Generate filename: YYYY-MM-DD-HHMMSS-mapname-round-N_proximity.txt
    local filename = string.format("%s%s-%s-round-%d_proximity.txt",
        config.output_dir,
        os.date('%Y-%m-%d-%H%M%S'),
        tracker.round.map_name,
        tracker.round.round_num)
    
    local fd = et.trap_FS_FOpenFile(filename, et.FS_WRITE)
    if fd == -1 then
        et.G_Print("[PROX] ERROR: Could not open file for writing\n")
        return
    end
    
    -- Write header
    local header = string.format("# PROXIMITY_TRACKER_V2\n# map=%s\n# round=%d\n",
        tracker.round.map_name, tracker.round.round_num)
    header = header .. "# FORMAT: game_time|killer_slot|killer_guid|killer_name|killer_team|killer_x|killer_y|killer_z|"
    header = header .. "victim_slot|victim_guid|victim_name|victim_team|victim_x|victim_y|victim_z|"
    header = header .. "distance|weapon|mod|engagement_type|killer_allies|victim_allies|supporting_allies\n"
    et.trap_FS_Write(header, string.len(header), fd)
    
    -- Write kills
    for _, kill in ipairs(tracker.kills) do
        local supporting_str = table.concat(kill.supporting_allies, ",")
        if supporting_str == "" then supporting_str = "NONE" end
        
        local line = string.format("%d|%d|%s|%s|%s|%.1f|%.1f|%.1f|%d|%s|%s|%s|%.1f|%.1f|%.1f|%.1f|%d|%d|%s|%d|%d|%s\n",
            kill.game_time,
            kill.killer_slot, kill.killer_guid, kill.killer_name, kill.killer_team,
            kill.killer_x, kill.killer_y, kill.killer_z,
            kill.victim_slot, kill.victim_guid, kill.victim_name, kill.victim_team,
            kill.victim_x, kill.victim_y, kill.victim_z,
            kill.distance, kill.weapon, kill.mod,
            kill.engagement_type, kill.killer_nearby_allies, kill.victim_nearby_allies,
            supporting_str)
        
        et.trap_FS_Write(line, string.len(line), fd)
    end
    
    -- Write heatmap section
    local heatmap_header = "\n# HEATMAP\n# grid_x|grid_y|axis_kills|allies_kills\n"
    et.trap_FS_Write(heatmap_header, string.len(heatmap_header), fd)
    
    for key, data in pairs(tracker.heatmap) do
        local grid_x, grid_y = string.match(key, "(-?%d+),(-?%d+)")
        local line = string.format("%s|%s|%d|%d\n", grid_x, grid_y, data.axis, data.allies)
        et.trap_FS_Write(line, string.len(line), fd)
    end
    
    et.trap_FS_FCloseFile(fd)
    
    et.G_Print(string.format("[PROX] Saved %d kills to %s\n", #tracker.kills, filename))
end

-- ===== ENGINE CALLBACKS =====

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)
    
    -- Get map info
    local serverinfo = et.trap_GetConfigstring(et.CS_SERVERINFO)
    tracker.round.map_name = et.Info_ValueForKey(serverinfo, "mapname") or "unknown"
    tracker.round.round_num = tonumber(et.trap_Cvar_Get("g_currentRound")) or 1
    tracker.round.start_time = levelTime
    
    -- Reset data
    tracker.kills = {}
    tracker.heatmap = {}
    
    et.G_Print(">>> Proximity Tracker v" .. version .. " initialized\n")
    et.G_Print(">>> Map: " .. tracker.round.map_name .. ", Round: " .. tracker.round.round_num .. "\n")
end

-- Track gamestate for intermission detection
local last_gamestate = -1

function et_RunFrame(levelTime)
    if not config.enabled then return end
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    
    -- Detect round end (transition to intermission)
    if last_gamestate == 0 and gamestate == 3 then
        if config.debug then
            et.G_Print("[PROX] Round ended - saving data\n")
        end
        outputData()
    end
    
    last_gamestate = gamestate
end

function et_Obituary(victim, killer, meansOfDeath)
    if not config.enabled then return end
    
    -- Only during active play
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end
    
    -- Ignore suicides and world kills
    if killer == 1022 or killer == 1023 or killer == victim then
        return
    end
    
    -- Ignore spectator kills
    local killer_team = et.gentity_get(killer, "sess.sessionTeam")
    local victim_team = et.gentity_get(victim, "sess.sessionTeam")
    if killer_team ~= 1 and killer_team ~= 2 then return end
    if victim_team ~= 1 and victim_team ~= 2 then return end
    
    -- Record the kill with full context
    recordKill(killer, victim, meansOfDeath)
end

-- ===== MODULE END =====
et.G_Print(">>> Proximity Tracker v" .. version .. " loaded\n")
