-- tests/lua/vehicle_tracking_harness.lua — v6.14 vehicle timing + damage
-- attribution (docs/design/20 slice 2), driven through the real tracker
-- with a stubbed `et`.
--
--   lua5.4 tests/lua/vehicle_tracking_harness.lua
--
-- Scenario: one script_mover ("truck", ent 64), two axis and two allied
-- clients (0-3). The truck stands for two samples, moves for three, stands
-- again; client 3 then lands the hit that takes it to 0 HP; the poll runs
-- twice more; the round ends and the tracker writes its file.
-- Asserts: first/last_move_time are the sample times of the first and last
-- moving tick; exactly ONE destruction, credited to client 3's guid; the
-- poll does not count the death a second time; the VEHICLE_PROGRESS line
-- carries 14 fields; a VEHICLE_DESTROYED section follows; a hit on a client
-- never enters the vehicle branch (the control).

local now_ms = 100000          -- wall clock (trap_Milliseconds)
local level_time = 0           -- engine level time (et_RunFrame argument)
local gamestate = "0"
local truck = { x = 1000, y = 2000, z = 10, health = 800 }
local written = {}
local prints = {}
local client_hits = 0

local function origin_of(cn)
    return { 1000 + cn * 50, 2000, 10 }
end

et = setmetatable({
    trap_Milliseconds = function() return now_ms end,
    trap_Cvar_Get = function(name)
        if name == "sv_maxclients" then return "16" end
        if name == "gamestate" then return gamestate end
        if name == "mapname" then return "supply" end
        return ""
    end,
    trap_Cvar_Set = function() end,
    gentity_get = function(ent, field)
        if ent == 64 then
            if field == "classname" then return "script_mover" end
            if field == "scriptName" then return "truck" end
            if field == "r.currentOrigin" then return { truck.x, truck.y, truck.z } end
            if field == "health" then return truck.health end
            return nil
        end
        if ent < 4 then
            -- vectors the tracker indexes (velocity for the speed sample,
            -- angles for the FOV prefilter, origin for positions)
            if field == "ps.velocity" or field == "ps.viewangles" or field == "r.mins" or field == "r.maxs" then
                return { 0, 0, 0 }
            end
            if field == "sess.sessionTeam" then return (ent < 2) and 1 or 2 end
            if field == "pers.connected" then return 2 end
            if field == "health" then return 100 end
            if field == "ps.origin" then return origin_of(ent) end
            if field == "tankLink" then return -1 end
            if field == "ps.pm_type" then return 0 end
            if field == "ps.weapon" then return 8 end
            if field == "classname" then return "player" end
            return 0
        end
        if field == "classname" then return "" end
        return 0
    end,
    trap_GetUserinfo = function(cn) return "\\cl_guid\\GUID" .. cn .. "ABCDEF" end,
    trap_GetConfigstring = function() return "\\mapname\\supply\\g_gametype\\3" end,
    Info_ValueForKey = function(info, key)
        if type(info) ~= "string" then return "" end
        return info:match("\\" .. key .. "\\([^\\]*)") or ""
    end,
    trap_FS_FOpenFile = function() return 7, 0 end,
    trap_FS_Write = function(data, len, fd) written[#written + 1] = data end,
    trap_FS_FCloseFile = function() end,
    G_Print = function(msg) prints[#prints + 1] = msg end,
    RegisterModname = function() end,
    FS_READ = 0, FS_WRITE = 1, FS_APPEND = 2,
}, { __index = function(t, k) return function() return 0 end end })

dofile("proximity/lua/proximity_tracker.lua")

local function frame(advance_ms)
    level_time = level_time + advance_ms
    now_ms = now_ms + advance_ms
    et_RunFrame(level_time)
end

local function check(cond, msg)
    if not cond then
        io.stderr:write("FAIL: " .. msg .. "\n")
        os.exit(1)
    end
    print("ok   " .. msg)
end

-- Reach into the tracker through its own output: the only public surface
-- is the file it writes, plus the entity table exposed for tests.
et_InitGame(level_time, 0, 0)
local veh = nil
for _, p in ipairs(prints) do
    if p:find("Vehicle found: ent=64 name=truck", 1, true) then veh = true end
end
check(veh, "init scan registered the truck (ent 64)")

-- Two standing samples (500 ms poll interval), then three moving ones.
frame(500); frame(500)
truck.x = truck.x + 120; frame(500)
local t_first = level_time
truck.x = truck.x + 120; frame(500)
truck.x = truck.x + 120; frame(500)
local t_last = level_time
frame(500); frame(500)

-- Control: a hit on a client must take the normal path, never the vehicle branch.
local before = #prints
et_Damage(1, 3, 40, 0, 5)
check(client_hits == 0 and #prints == before, "a hit on client 1 does not touch the vehicle branch")

-- The engine has already subtracted the damage when the hook runs.
truck.health = 0
et_Damage(64, 3, 900, 0, 5)
-- Two more polls: health stays 0, last_health is 0 → no second count.
frame(500); frame(500)

-- Round end: gamestate 0 → 3 schedules the delayed output; advance past it.
gamestate = "3"
frame(500)
now_ms = now_ms + 60000
frame(500)

local out = table.concat(written)
check(out:find("# VEHICLE_PROGRESS", 1, true) ~= nil, "VEHICLE_PROGRESS section written")
-- Section-aware: the truck now has a row in two sections.
local function first_row_after(header)
    local in_section = false
    for line in out:gmatch("[^\n]+") do
        if line == header then in_section = true
        elseif in_section and line:sub(1, 1) == "#" and line:sub(1, 2) ~= "# " then in_section = false
        elseif in_section and line:sub(1, 1) ~= "#" then return line end
    end
    return nil
end
local vp_line = first_row_after("# VEHICLE_PROGRESS")
check(vp_line ~= nil, "truck row present")
local fields = {}
for f in (vp_line .. ";"):gmatch("([^;]*);") do fields[#fields + 1] = f end
check(#fields == 14, "VEHICLE_PROGRESS row has 14 fields (got " .. #fields .. ")")
check(tonumber(fields[12]) == 1, "destroyed_count is exactly 1 (poll did not double-count), got " .. fields[12])
-- gameTime() is level time minus the round's start, and the tracker
-- re-anchors that start on the first PLAYING frame (the warmup→play
-- transition), which here is the first frame at level time 500.
local base = 500
check(tonumber(fields[13]) == t_first - base, "first_move_time = first moving sample in gameTime (" .. fields[13] .. " vs " .. (t_first - base) .. ")")
check(tonumber(fields[14]) == t_last - base, "last_move_time = last moving sample in gameTime (" .. fields[14] .. " vs " .. (t_last - base) .. ")")
check(tonumber(fields[14]) - tonumber(fields[13]) == t_last - t_first, "the move window is base-independent")

check(out:find("# VEHICLE_DESTROYED", 1, true) ~= nil, "VEHICLE_DESTROYED section written")
local vd_line = first_row_after("# VEHICLE_DESTROYED")
check(vd_line ~= nil, "one VEHICLE_DESTROYED row")
local vd = {}
for f in (vd_line .. ";"):gmatch("([^;]*);") do vd[#vd + 1] = f end
check(#vd == 7, "VEHICLE_DESTROYED row has 7 fields (got " .. #vd .. ": '" .. vd_line .. "')")
check(vd[1] == "truck", "destroyed vehicle is the truck")
check(vd[3] == "GUID3ABCDEF", "attacker guid is client 3's (got " .. vd[3] .. ")")
check(vd[5] == "allies" or vd[5] == "ALLIES" or vd[5] ~= "", "attacker team recorded (" .. vd[5] .. ")")
check(tonumber(vd[6]) == 5, "means_of_death carried through")
check(tonumber(vd[7]) == 800, "health_before is the poll's last healthy reading")
local truck_rows = 0
for line in out:gmatch("[^\n]+") do
    if line:sub(1, 6) == "truck;" then truck_rows = truck_rows + 1 end
end
check(truck_rows == 2, "exactly one progress row and one destroyed row for the truck (got " .. truck_rows .. ")")

print("vehicle_tracking_harness: all checks passed")
