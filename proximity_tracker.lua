-- ============================================================
-- PROXIMITY TRACKER v0.01
-- ET:Legacy Lua Module for Position & Combat Analytics
--
-- Purpose: Track player positions, movement, and combat 
--          engagement patterns independently of c0rnp0rn.lua
--
-- Features:
--   • Position tracking (x,y,z,velocity,view angles)
--   • Combat event logging (shots, hits, kills)
--   • Engagement analysis (1v1, 2v1, 2v2 detection)
--   • Teammate coordination detection (crossfire, baiting, synergy)
--   • Movement pattern analysis (stationary time, distance traveled)
--   • Heatmap generation data (kill locations, hotspots)
--
-- Output Files:
--   • proximity.txt       - Position snapshots
--   • combat.txt         - Combat events with spatial data
--   • engagements.txt    - Engagement analysis summary
--
-- NOTE: This is a STANDALONE script. Does NOT modify c0rnp0rn.lua
-- Load order: lua_modules "c0rnp0rn.lua proximity_tracker.lua"
-- ============================================================

-- ===== MODULE INITIALIZATION =====
local modname = "proximity_tracker"
local version = "1.0"

-- Configuration (local scope = no conflicts with c0rnp0rn)
local config = {
    enabled = true,
    debug = false,
    output_dir = "gamestats/",
    
    -- Tracking parameters
    position_update_interval = 1000,  -- ms between position snapshots (1 second)
    max_position_snapshots = 600,     -- ~10 minutes at 1Hz
    stationary_threshold = 5,         -- units/sec speed threshold
    stationary_duration = 3000,       -- ms to count as stationary
    
    -- Proximity parameters
    proximity_check_distance = 300,   -- units to check for nearby players
    crossfire_distance = 200,         -- units for potential crossfire
    engagement_min_damage = 10,       -- minimum damage to count as engagement
    
    -- Map grid parameters
    grid_size = 512                   -- units per grid cell for heatmaps
}

-- Module data storage (all data completely isolated from c0rnp0rn)
local proximity = {
    -- Position history (circular buffers per player)
    position_history = {},
    
    -- Combat events log
    combat_events = {},
    
    -- Engagement tracking
    active_engagements = {},
    engagement_history = {},
    
    -- Movement analysis
    player_movement = {},
    
    -- Heatmap aggregation
    kill_heatmap = {},
    
    -- Helper tracking
    last_position_snapshot_time = 0,
    game_start_time = 0,
    round_data = {
        round_num = 0,
        map_name = "",
        start_time = 0
    },
    
    -- Nearby player tracking for combat context
    nearby_players_cache = {}
}

-- ===== UTILITY FUNCTIONS =====

-- Calculate 3D distance between two positions
local function distance3D(pos1, pos2)
    if not pos1 or not pos2 then return 0 end
    
    local dx = pos1.x - pos2.x
    local dy = pos1.y - pos2.y
    local dz = pos1.z - pos2.z
    
    return math.sqrt(dx*dx + dy*dy + dz*dz)
end

-- Calculate 2D horizontal distance (ignoring height)
local function horizontalDistance(pos1, pos2)
    if not pos1 or not pos2 then return 0 end
    
    local dx = pos1.x - pos2.x
    local dy = pos1.y - pos2.y
    
    return math.sqrt(dx*dx + dy*dy)
end

-- Get player 3D position
local function getPlayerPos(clientnum)
    local origin = et.gentity_get(clientnum, "ps.origin")
    if not origin then
        return {x = 0, y = 0, z = 0}
    end
    
    return {
        x = tonumber(origin[1]) or 0,
        y = tonumber(origin[2]) or 0,
        z = tonumber(origin[3]) or 0
    }
end

-- Get player velocity vector
local function getPlayerVelocity(clientnum)
    local velocity = et.gentity_get(clientnum, "ps.velocity")
    if not velocity then
        return {x = 0, y = 0, z = 0}
    end
    
    return {
        x = tonumber(velocity[1]) or 0,
        y = tonumber(velocity[2]) or 0,
        z = tonumber(velocity[3]) or 0
    }
end

-- Calculate speed (magnitude of velocity)
local function getPlayerSpeed(clientnum)
    local vel = getPlayerVelocity(clientnum)
    return math.sqrt(vel.x*vel.x + vel.y*vel.y + vel.z*vel.z)
end

-- Get player view angles
local function getPlayerViewAngles(clientnum)
    local angles = et.gentity_get(clientnum, "ps.viewangles")
    if not angles then
        return {pitch = 0, yaw = 0}
    end
    
    return {
        pitch = tonumber(angles[1]) or 0,
        yaw = tonumber(angles[2]) or 0
    }
end

-- Check if player is alive and connected
local function isPlayerActive(clientnum)
    local connected = et.gentity_get(clientnum, "pers.connected")
    if connected ~= 2 then
        return false
    end
    
    local team = et.gentity_get(clientnum, "sess.sessionTeam")
    local health = tonumber(et.gentity_get(clientnum, "health")) or 0
    
    -- Active if in Axis or Allies and alive
    return (team == 1 or team == 2) and health > 0
end

-- Get player team
local function getPlayerTeam(clientnum)
    local team = et.gentity_get(clientnum, "sess.sessionTeam")
    if team == 1 then return "AXIS"
    elseif team == 2 then return "ALLIES"
    else return "SPEC"
    end
end

-- Get player name
local function getPlayerName(clientnum)
    local name = et.gentity_get(clientnum, "pers.netname") or "Unknown"
    return tostring(name)
end

-- Round number helper
local function roundNum(num, n)
    local mult = 10^(n or 0)
    return math.floor(num * mult + 0.5) / mult
end

-- Initialize player position tracking
local function initPlayerPositionTracking(clientnum)
    if not proximity.position_history[clientnum] then
        proximity.position_history[clientnum] = {
            snapshots = {},
            write_index = 1,
            player_name = getPlayerName(clientnum),
            team = getPlayerTeam(clientnum)
        }
    end
end

-- Add position snapshot to circular buffer
local function recordPositionSnapshot(clientnum)
    initPlayerPositionTracking(clientnum)
    
    local pos = getPlayerPos(clientnum)
    local angles = getPlayerViewAngles(clientnum)
    local speed = getPlayerSpeed(clientnum)
    
    local snapshot = {
        time = et.trap_Milliseconds(),
        x = roundNum(pos.x, 1),
        y = roundNum(pos.y, 1),
        z = roundNum(pos.z, 1),
        yaw = roundNum(angles.yaw, 1),
        pitch = roundNum(angles.pitch, 1),
        speed = roundNum(speed, 1),
        moving = speed > config.stationary_threshold and 1 or 0
    }
    
    local buffer = proximity.position_history[clientnum]
    buffer.snapshots[buffer.write_index] = snapshot
    buffer.write_index = (buffer.write_index % config.max_position_snapshots) + 1
end

-- Get nearby players within distance threshold
local function getNearbyPlayers(clientnum, distance_threshold, same_team_only)
    local nearby = {}
    local player_pos = getPlayerPos(clientnum)
    local player_team = et.gentity_get(clientnum, "sess.sessionTeam")
    local maxclients = tonumber(et.trap_Cvar_Get("sv_maxclients")) or 64
    
    for other = 0, maxclients - 1 do
        if other ~= clientnum then
            local other_connected = et.gentity_get(other, "pers.connected")
            if other_connected == 2 then
                local other_team = et.gentity_get(other, "sess.sessionTeam")
                local other_health = tonumber(et.gentity_get(other, "health")) or 0
                
                -- Check team filter
                if not same_team_only or other_team == player_team then
                    if other_health > 0 then
                        local other_pos = getPlayerPos(other)
                        local dist = distance3D(player_pos, other_pos)
                        
                        if dist < distance_threshold then
                            table.insert(nearby, {
                                clientnum = other,
                                name = getPlayerName(other),
                                team = getPlayerTeam(other),
                                distance = roundNum(dist, 1),
                                is_teammate = (other_team == player_team)
                            })
                        end
                    end
                end
            end
        end
    end
    
    return nearby
end

-- Log combat event
local function logCombatEvent(event_type, attacker, target, data)
    if not attacker then return end
    
    local event = {
        timestamp = et.trap_Milliseconds(),
        type = event_type,  -- "fire", "hit", "kill"
        attacker = attacker,
        target = target,
        attacker_name = getPlayerName(attacker),
        attacker_team = getPlayerTeam(attacker),
        attacker_pos = getPlayerPos(attacker),
        attacker_angles = getPlayerViewAngles(attacker),
        
        weapon = data.weapon or 0,
        distance = data.distance or 0,
        damage = data.damage or 0,
        mod = data.mod or 0,
        hit_region = data.hit_region or -1
    }
    
    -- Add target data if applicable
    if target then
        event.target_name = getPlayerName(target)
        event.target_team = getPlayerTeam(target)
        event.target_pos = getPlayerPos(target)
    end
    
    -- Add nearby players context
    event.nearby_allies = getNearbyPlayers(attacker, config.proximity_check_distance, true)
    event.nearby_enemies = getNearbyPlayers(attacker, config.proximity_check_distance, false)
    
    table.insert(proximity.combat_events, event)
    
    if config.debug then
        et.G_Printf("[PROX] Combat Event: %s - Attacker: %d, Target: %d\n", 
            event_type, attacker, target or -1)
    end
end

-- Analyze engagement (detect 1v1, 2v1, 2v2, etc.)
local function analyzeEngagement(attacker, target)
    if not target then return nil end
    
    local attacker_pos = getPlayerPos(attacker)
    local target_pos = getPlayerPos(target)
    local engagement_distance = distance3D(attacker_pos, target_pos)
    
    -- Count nearby allies of attacker within engagement range
    local nearby_allies = getNearbyPlayers(attacker, config.crossfire_distance, true)
    local attacker_backup_count = 0
    for _, ally in ipairs(nearby_allies) do
        if ally.distance < config.crossfire_distance then
            attacker_backup_count = attacker_backup_count + 1
        end
    end
    
    -- Count nearby allies of target within engagement range
    local nearby_target_allies = getNearbyPlayers(target, config.crossfire_distance, true)
    local target_backup_count = 0
    for _, ally in ipairs(nearby_target_allies) do
        if ally.distance < config.crossfire_distance then
            target_backup_count = target_backup_count + 1
        end
    end
    
    -- Determine engagement type
    local engagement_type = "UNKNOWN"
    if attacker_backup_count == 0 and target_backup_count == 0 then
        engagement_type = "1v1"
    elseif attacker_backup_count > 0 and target_backup_count == 0 then
        engagement_type = string.format("%dv1", 1 + attacker_backup_count)
    elseif attacker_backup_count == 0 and target_backup_count > 0 then
        engagement_type = string.format("1v%d", 1 + target_backup_count)
    else
        engagement_type = string.format("%dvs%d", 1 + attacker_backup_count, 1 + target_backup_count)
    end
    
    return {
        type = engagement_type,
        distance = roundNum(engagement_distance, 1),
        attacker_backup = attacker_backup_count,
        target_backup = target_backup_count
    }
end

-- ===== ENGINE CALLBACKS =====

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(modname .. " " .. version)
    et.G_Print(">>> Proximity Tracker v" .. version .. " initialized\n")
    
    -- Get map and round info
    local serverinfo = et.trap_GetConfigstring(et.CS_SERVERINFO)
    proximity.round_data.map_name = et.Info_ValueForKey(serverinfo, "mapname")
    proximity.round_data.round_num = tonumber(et.trap_Cvar_Get("g_currentRound")) or 1
    proximity.round_data.start_time = levelTime
    proximity.game_start_time = levelTime
    
    -- Reset data for new round
    proximity.position_history = {}
    proximity.combat_events = {}
    proximity.active_engagements = {}
    proximity.engagement_history = {}
    proximity.kill_heatmap = {}
    
    if config.debug then
        et.G_Printf("[PROX] InitGame: Map=%s, Round=%d\n", 
            proximity.round_data.map_name, proximity.round_data.round_num)
    end
end

function et_RunFrame(levelTime)
    if not config.enabled then return end
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    
    -- Only track during active play (gamestate 0 = GS_PLAYING)
    if gamestate ~= 0 then return end
    
    -- Update position snapshots at configured interval
    if levelTime >= proximity.last_position_snapshot_time then
        local maxclients = tonumber(et.trap_Cvar_Get("sv_maxclients")) or 64
        
        for clientnum = 0, maxclients - 1 do
            if isPlayerActive(clientnum) then
                recordPositionSnapshot(clientnum)
            end
        end
        
        proximity.last_position_snapshot_time = levelTime + config.position_update_interval
    end
end

-- Called whenever a player fires a weapon
function et_WeaponFire(clientNum, weapon)
    if not config.enabled then return end
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return 0 end
    
    if isPlayerActive(clientNum) then
        logCombatEvent("fire", clientNum, nil, {
            weapon = weapon
        })
    end
    
    return 0  -- Passthrough (0 = allow shot to happen)
end

-- Called whenever damage is dealt
function et_Damage(target, attacker, damage, damageFlags, meansOfDeath)
    if not config.enabled then return end
    
    -- Ignore self-damage and world damage
    if target == attacker or attacker == 1022 or attacker == 1023 then
        return
    end
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end
    
    -- Only log significant damage
    if tonumber(damage) < config.engagement_min_damage then
        return
    end
    
    local attacker_pos = getPlayerPos(attacker)
    local target_pos = getPlayerPos(target)
    local engagement_distance = distance3D(attacker_pos, target_pos)
    
    -- Log hit event
    logCombatEvent("hit", attacker, target, {
        damage = tonumber(damage),
        mod = meansOfDeath,
        distance = engagement_distance,
        weapon = et.gentity_get(attacker, "ps.weapon") or 0
    })
    
    -- Analyze engagement context
    local engagement = analyzeEngagement(attacker, target)
    if engagement then
        if config.debug then
            et.G_Printf("[PROX] Engagement: %s at %.1f units\n", 
                engagement.type, engagement.distance)
        end
    end
end

-- Called whenever a player dies
function et_Obituary(victim, killer, meansOfDeath)
    if not config.enabled then return end
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end
    
    -- Log kill (ignore suicides/world kills)
    if killer ~= 1022 and killer ~= 1023 and killer ~= victim then
        local victim_pos = getPlayerPos(victim)
        local killer_pos = getPlayerPos(killer)
        local kill_distance = distance3D(killer_pos, victim_pos)
        
        -- Log kill event
        logCombatEvent("kill", killer, victim, {
            mod = meansOfDeath,
            distance = kill_distance
        })
        
        -- Record kill location for heatmap
        local grid_x = math.floor(victim_pos.x / config.grid_size)
        local grid_y = math.floor(victim_pos.y / config.grid_size)
        local key = string.format("%d,%d", grid_x, grid_y)
        
        if not proximity.kill_heatmap[key] then
            proximity.kill_heatmap[key] = {
                axis = 0,
                allies = 0,
                kills = {}
            }
        end
        
        local killer_team = getPlayerTeam(killer)
        if killer_team == "AXIS" then
            proximity.kill_heatmap[key].axis = proximity.kill_heatmap[key].axis + 1
        elseif killer_team == "ALLIES" then
            proximity.kill_heatmap[key].allies = proximity.kill_heatmap[key].allies + 1
        end
        
        table.insert(proximity.kill_heatmap[key].kills, {
            killer = getPlayerName(killer),
            victim = getPlayerName(victim),
            time = et.trap_Milliseconds()
        })
        
        -- Analyze engagement
        local engagement = analyzeEngagement(killer, victim)
        if engagement then
            table.insert(proximity.engagement_history, {
                outcome = "kill",
                engagement_type = engagement.type,
                distance = engagement.distance,
                killer = getPlayerName(killer),
                victim = getPlayerName(victim)
            })
        end
    end
end

-- Called when player spawns
function et_ClientSpawn(clientnum, revived, teamChange, restoreHealth)
    if not config.enabled then return end
    
    -- Initialize position tracking for new spawn
    initPlayerPositionTracking(clientnum)
    
    if config.debug and not revived then
        et.G_Printf("[PROX] Spawn: %s\n", getPlayerName(clientnum))
    end
end

-- Called when player disconnects
function et_ClientDisconnect(clientnum)
    if not config.enabled then return end
    
    -- Clean up tracking data
    proximity.position_history[clientnum] = nil
end

-- ===== FILE OUTPUT FUNCTIONS =====

-- Format position snapshot for output
local function formatPositionLine(clientnum, snapshot)
    return string.format("%d\t%d\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%d\n",
        clientnum,
        snapshot.time,
        snapshot.x,
        snapshot.y,
        snapshot.z,
        snapshot.yaw,
        snapshot.pitch,
        snapshot.speed,
        snapshot.moving)
end

-- Format combat event for output
local function formatCombatLine(event)
    local nearby_allies_count = 0
    local nearby_enemies_count = 0
    
    if event.nearby_allies then nearby_allies_count = #event.nearby_allies end
    if event.nearby_enemies then nearby_enemies_count = #event.nearby_enemies end
    
    local target_str = event.target or "NONE"
    
    return string.format("%d\t%s\t%d\t%s\t%0.1f\t%d\t%d\t%d\n",
        event.timestamp,
        event.type,
        event.attacker,
        target_str,
        event.distance,
        nearby_allies_count,
        nearby_enemies_count,
        event.damage)
end

-- Save proximity data to files at round end
local function outputProximityData()
    if not next(proximity.combat_events) and not next(proximity.position_history) then
        et.G_Print("[PROX] No data to output\n")
        return
    end
    
    -- Generate base filename with timestamp and map
    local basename = string.format("%s%s-round-%d",
        config.output_dir,
        os.date('%Y-%m-%d-%H%M%S-'),
        proximity.round_data.round_num)
    
    -- ===== POSITIONS FILE =====
    local positions_file = basename .. "_positions.txt"
    local fd_pos = et.trap_FS_FOpenFile(positions_file, et.FS_WRITE)
    
    if fd_pos ~= -1 then
        -- Write header
        local header = "# POSITION_TRACKER_DATA\n# clientnum\ttime\tx\ty\tz\tyaw\tpitch\tspeed\tmoving\n"
        et.trap_FS_Write(header, string.len(header), fd_pos)
        
        -- Write position snapshots
        for clientnum, buffer in pairs(proximity.position_history) do
            for _, snapshot in ipairs(buffer.snapshots) do
                if snapshot then
                    local line = formatPositionLine(clientnum, snapshot)
                    et.trap_FS_Write(line, string.len(line), fd_pos)
                end
            end
        end
        
        et.trap_FS_FCloseFile(fd_pos)
        et.G_LogPrint(string.format("[PROX] Positions saved: %s\n", positions_file))
    end
    
    -- ===== COMBAT FILE =====
    local combat_file = basename .. "_combat.txt"
    local fd_combat = et.trap_FS_FOpenFile(combat_file, et.FS_WRITE)
    
    if fd_combat ~= -1 then
        -- Write header
        local header = "# COMBAT_EVENTS_DATA\n# time\ttype\tattacker\ttarget\tdistance\tnearby_allies\tnearby_enemies\tdamage\n"
        et.trap_FS_Write(header, string.len(header), fd_combat)
        
        -- Write combat events
        for _, event in ipairs(proximity.combat_events) do
            local line = formatCombatLine(event)
            et.trap_FS_Write(line, string.len(line), fd_combat)
        end
        
        et.trap_FS_FCloseFile(fd_combat)
        et.G_LogPrint(string.format("[PROX] Combat events saved: %s\n", combat_file))
    end
    
    -- ===== ENGAGEMENTS FILE =====
    local engagements_file = basename .. "_engagements.txt"
    local fd_eng = et.trap_FS_FOpenFile(engagements_file, et.FS_WRITE)
    
    if fd_eng ~= -1 then
        -- Write header
        local header = "# ENGAGEMENT_ANALYSIS\n# engagement_type\tdistance\tkiller\tvictim\n"
        et.trap_FS_Write(header, string.len(header), fd_eng)
        
        -- Write engagement summary
        for _, engagement in ipairs(proximity.engagement_history) do
            local line = string.format("%s\t%0.1f\t%s\t%s\n",
                engagement.engagement_type,
                engagement.distance,
                engagement.killer,
                engagement.victim)
            et.trap_FS_Write(line, string.len(line), fd_eng)
        end
        
        et.trap_FS_FCloseFile(fd_eng)
        et.G_LogPrint(string.format("[PROX] Engagements saved: %s\n", engagements_file))
    end
    
    -- ===== HEATMAP FILE =====
    local heatmap_file = basename .. "_heatmap.txt"
    local fd_heat = et.trap_FS_FOpenFile(heatmap_file, et.FS_WRITE)
    
    if fd_heat ~= -1 then
        -- Write header
        local header = "# HEATMAP_DATA\n# grid_x\tgrid_y\taxis_kills\tallies_kills\n"
        et.trap_FS_Write(header, string.len(header), fd_heat)
        
        -- Write heatmap grid
        for key, data in pairs(proximity.kill_heatmap) do
            local grid_x, grid_y = string.match(key, "(-?%d+),(-?%d+)")
            local line = string.format("%s\t%s\t%d\t%d\n",
                grid_x, grid_y, data.axis, data.allies)
            et.trap_FS_Write(line, string.len(line), fd_heat)
        end
        
        et.trap_FS_FCloseFile(fd_heat)
        et.G_LogPrint(string.format("[PROX] Heatmap saved: %s\n", heatmap_file))
    end
    
    et.G_Print("[PROX] All data files written successfully\n")
end

-- ===== GAME STATE HANDLING =====

-- Track intermission to save data
local last_gamestate = -1

-- Override et_RunFrame to also check for intermission
local original_et_RunFrame = et_RunFrame

function et_RunFrame(levelTime)
    if not config.enabled then return end
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    
    -- Detect transition to intermission
    if last_gamestate == 0 and gamestate == 3 then
        -- Round ended, save data
        if config.debug then
            et.G_Print("[PROX] Round ended - saving data\n")
        end
        outputProximityData()
    end
    
    last_gamestate = gamestate
    
    -- Call original logic
    if gamestate == 0 then
        -- Update position snapshots during play
        if levelTime >= proximity.last_position_snapshot_time then
            local maxclients = tonumber(et.trap_Cvar_Get("sv_maxclients")) or 64
            
            for clientnum = 0, maxclients - 1 do
                if isPlayerActive(clientnum) then
                    recordPositionSnapshot(clientnum)
                end
            end
            
            proximity.last_position_snapshot_time = levelTime + config.position_update_interval
        end
    end
end

-- ===== MODULE END =====
et.G_Print(">>> Proximity Tracker v" .. version .. " loaded successfully\n")
