-- Execute the WHOLE shipped tracker; no production code injection or extraction.
-- Engine oracle: ET:Legacy v2.85.0, commit489f1c4f142903aa9d1619f1c107d00b554d0dd6,
-- g_main.c G_RunFrame/G_InitGame and g_active.c SpectatorClientEndFrame.
-- This models clocks only, not an actual server, physics or respawn eligibility.
local level, active, delta, start, cs_start = 0, 0, 0, 0, 0
local paused, gamestate, seeds = false, "2", "0 0 0 0 0 0 0 0 0 0"
local wall = 900000
local errors = {}
local player_present = false
local player_x, signal_override = 0, nil
local function noop() end
et = {
    FS_APPEND=2, FS_WRITE=1, CS_SERVERTOGGLES=32,
    trap_Milliseconds=function() return wall end,
    trap_GetConfigstring=function(index)
        if index == 32 then
            if signal_override ~= nil then return signal_override end
            return paused and "16" or "0"
        end
        if index == 11 then return tostring(cs_start) end
        if index == 31 then return seeds end
        return ""
    end,
    trap_Cvar_Get=function(name)
        if name == "gamestate" then return gamestate end
        if name == "sv_maxclients" then return "1" end
        if name == "g_redlimbotime" then return "30000" end
        if name == "g_bluelimbotime" then return "20000" end
        if name == "mapname" then return "supply" end
        return "0"
    end,
    gentity_get=function(slot, field)
        if slot == 64 and field == "r.currentOrigin" then return {player_x, 0, 0} end
        if slot == 64 and field == "health" then return 100 end
        if slot ~= 0 or not player_present then return nil end
        if field == "pers.connected" then return 2 end
        if field == "sess.sessionTeam" then return 1 end
        if field == "pers.netname" then return "Synthetic" end
        if field == "ps.origin" then return {player_x, 0, 0} end
        if field == "ps.velocity" then return {0, 0, 0} end
        if field == "health" then return 100 end
        return nil
    end,
    trap_GetUserinfo=function() return "" end,
    trap_FS_FOpenFile=function() return 42, 0 end,
    trap_FS_Write=function(_, count) return count end, trap_FS_FCloseFile=noop, RegisterModname=noop,
    Info_ValueForKey=function() return "" end,
    G_Print=function(message)
        if message:find("FAILED", 1, true) or message:find("error:", 1, true) then
            errors[#errors+1] = message
        end
    end,
    G_Printf=noop,
}

-- Inspect real closures by name; never silently substitute a copied function.
local function lookup(fn, wanted, seen)
    seen = seen or {}
    if seen[fn] then return nil end
    seen[fn] = true
    for i=1, math.huge do
        local name, value = debug.getupvalue(fn, i)
        if not name then break end
        if name == wanted then return value end
        if type(value) == "function" then
            local found = lookup(value, wanted, seen)
            if found ~= nil then return found end
        end
    end
end
local function private(name)
    for _, callback in ipairs({et_RunFrame, et_InitGame, et_Obituary}) do
        local value = lookup(callback, name)
        if value ~= nil then return value end
    end
    error("missing shipped upvalue: " .. name)
end
local tracker, game_time, score, decode
local function init(at)
    -- Official G_ShutdownGame destroys Lua VMs even on map_restart. Fresh locals
    -- here model that isolation, NOT the actual shutdown/restart callback sequence.
    dofile("proximity/lua/proximity_tracker.lua")
    tracker, game_time = private("tracker"), private("gameTime")
    score, decode = private("calculateSpawnTimingScore"), private("parseReinfOffsets")
    local config = private("config")
    for flag in pairs(config.features) do config.features[flag] = false end
    config.objective_tracking = false
    level, active, delta, start, cs_start = at, at, 0, at, at
    gamestate, paused = "2", false
    player_present = false
    et_InitGame(at, 0, 0)
end
local function frame(at, state, is_paused, before_lua)
    assert(at >= level, "scenario must use nondecreasing levelTime")
    wall = wall + at - level
    level, gamestate, paused = at, tostring(state), is_paused
    if paused then
        delta = level - active
        if cs_start + 500 <= start + delta then cs_start = start + delta end
    else
        active = level - delta
    end
    -- Entity think/ClientEndFrame work may change pause state or invoke a hook
    -- AFTER engine clock accounting but BEFORE Lua et_RunFrame.
    if before_lua then before_lua() end
    et_RunFrame(level)
    assert(#errors == 0, table.concat(errors, "\n"))
end
local function report(name)
    local wait_axis = score(game_time(), 1)
    local wait_allies = score(game_time(), 2)
    print(table.concat({name, level, active-start, game_time(), tracker.round.start_time,
        tracker.last_sample_time, wait_axis, wait_allies, cs_start,
        tracker.player_tracks[0] and #tracker.player_tracks[0].path or 0}, ","))
end

init(1000)
frame(1000, 0, false)
player_present = true
et_ClientSpawn(0, 0, 0, 0)
frame(1200, 0, false)
report("aligned")
frame(1250, 0, true)
frame(1450, 0, true)
report("pause_short")
frame(1800, 0, true)
report("pause_long")
frame(1850, 0, true, function()
    -- G_spawnPrintf DP_UNPAUSING publishes the final offset and clears the bit.
    paused, cs_start = false, start + delta
end)
report("resume_transition")
assert(not paused and active == 1200 and cs_start == 1650)
frame(1900, 0, false)
report("resumed")

init(1000)
frame(1050, 0, false)
frame(1250, 0, false)
report("first_frame_delay")
init(1000)
frame(1025, 2, false)
frame(4500, 0, false)
frame(4700, 0, false)
-- Deliberate synthetic no-restart transition; normal CheckWolfMP countdown
-- requests map_restart instead. Do not label this normal engine round start.
report("synthetic_live_without_restart")
-- Fresh module must not inherit pause debt, anchor or sampling state.
init(5000)
frame(5000, 0, false)
frame(5200, 0, false)
report("fresh_module")
frame(5250, 0, false, function()
    player_present = true
    et_ClientSpawn(0, 0, 0, 0)
    assert(tracker.player_tracks[0], "spawn hook must actually create a track")
    print(table.concat({"event", tracker.player_tracks[0].spawn_time, active-start}, ","))
end)

-- Server-valid encoded seeds (G_loadMatchGame multiplies integer seconds by
-- divisor). Exercise every red/blue index with unrelated low packed bits.
local divisors = {11, 3, 13, 7, 2, 5, 1, 17}
for blue=0,7 do
    for red=0,7 do
        local values = {blue*8+7, red*4+3}
        for i=1,8 do values[#values+1] = (i-1)*2*divisors[i] end
        seeds = table.concat(values, " ")
        local axis, allies = decode()
        assert(axis == red*2000 and allies == blue*2000, "server seed decode mismatch")
    end
end
tracker.spawn.axis_reinf_offset, tracker.spawn.allies_reinf_offset = 4000, 6000
for _, elapsed in ipairs({0, 13999, 14000, 14001, 25999, 26000, 26001, 60000}) do
    local axis, axis_score = score(elapsed, 1)
    local allies, allies_score = score(elapsed, 2)
    print(table.concat({"phase", elapsed, axis, allies, axis_score, allies_score}, ","))
end
print("ENGINE CONTRACT PROOF: whole tracker; 64 seed pairs; no live engine")

-- Independently check offline approach geometry, including unequal coordinates
-- at coincident callback times. Only the LAST boundary point is a baseline.
for _, marker_index in ipairs({2, 3, 4}) do
    local path = {
        {time=0, x=0, y=0, z=0, event="sample"},
        {time=200, x=990, y=0, z=0, event="sample"},
        {time=200, x=995, y=0, z=0, event="sample"},
        {time=200, x=1000, y=0, z=0, event="sample"},
        {time=400, x=1010, y=0, z=0, event="sample"},
    }
    path[marker_index].event = "capture_resume"
    local ms, dist, beeline = private("calculateApproachMetrics")({path=path}, 400, 1000)
    assert(ms == 200 and dist == 10 and beeline == 10, "approach bridged duplicate-time boundary")
end
print("APPROACH BOUNDARY PROOF: three marker orderings; 10 units; 200ms")

-- Optional functional proof: whole writer -> real file -> Python parser. The
-- filesystem is real; ET calls/positions/lifecycle remain explicitly synthetic.
if arg[1] then
    local output_dir, scenario = arg[1], arg[2]
    local file, written_path, writes, closes = nil, nil, 0, 0
    et.trap_FS_FOpenFile = function(path, mode)
        if not path:find("_engagements.txt", 1, true) then return -1, -1 end
        assert(not file and not written_path, "unexpected output retry")
        assert(mode == 1 and path:sub(1, #output_dir+1) == output_dir .. "/")
        written_path, file = path, assert(io.open(path, "wb"))
        return 42, 0
    end
    et.trap_FS_Write = function(data, count, fd)
        assert(fd == 42 and file and count == #data)
        assert(file:write(data))
        writes = writes + 1
        return count
    end
    et.trap_FS_FCloseFile = function(fd)
        assert(fd == 42 and file)
        assert(file:close())
        file, closes = nil, closes + 1
    end
    init(1000)
    local config = private("config")
    config.output_dir = output_dir .. "/"
    config.output_delay_ms = 100
    config.test_mode.enabled = false
    config.log_in_intermission = true
    player_x = 0
    frame(1000, 0, false)
    player_present = true
    et_ClientSpawn(0, 0, 0, 0)
    player_x = 10
    frame(1200, 0, false)
    local track = assert(tracker.player_tracks[0])
    assert(#track.path == 2)
    -- Real source accumulator state, exercised below without enabling unrelated
    -- objective detection/flag-powerup simulation in this clock harness.
    local carrier = {last_pos={x=10,y=0,z=0}, last_sample_time=200,
        carry_distance=0, path_samples=0}
    local vehicle = {last_pos={x=10,y=0,z=0}, total_distance=0, first_move_time=0,
        last_health=100, max_health=100, first_escort_time=0, name="fixture"}
    tracker.carrier.active[0], tracker.vehicles.entities[64] = carrier, vehicle
    if scenario == "unknown" then signal_override = "not-a-number" end
    frame(1250, 0, scenario ~= "unknown")
    player_x = 1000
    frame(1450, 0, scenario ~= "unknown")
    assert(#track.path == 2, "pause added position samples")
    assert(track.capture_gap, "pause did not mark path boundary")
    assert(carrier.capture_gap and vehicle.capture_gap, "pause did not mark accumulators")

    -- Missing/invalid signal fails closed, even when the actual model is live.
    if scenario == "unknown" then
        for _, value in ipairs({"", "-1", "1.5", "nan", "inf", "2147483648"}) do
            signal_override = value
            frame(level + 50, 0, false)
            assert(#track.path == 2, "invalid pause signal sampled")
        end
        signal_override = nil
    end
    if scenario == "paused_death" or scenario == "resume_death" then
        if scenario == "resume_death" then frame(level + 200, 0, false) end
        -- Full callback, not a replacement implementation. paused_death is an
        -- adversarial API invocation, NOT proof of normal paused ET gameplay:
        -- pinned g_cmds.c explicitly blocks /kill during a pause. resume_death
        -- exercises death before the first resumed positional sampler.
        et_Obituary(0, 1022, 0)
        assert(#tracker.completed_tracks == 1 and track.death_type == "world")
        assert(track.path[#track.path].event ==
            (scenario == "paused_death" and "sample" or "capture_resume"))
        player_present = false
        frame(level + 200, 3, scenario == "paused_death")
    elseif scenario == "paused_end" then
        frame(1600, 3, true)
    else
        frame(level + 200, 0, false)
        assert(#track.path == 2, "resume transition sampled")
        frame(level + 200, 0, false)
        assert(#track.path == 3 and track.path[3].event == "capture_resume",
            "first resumed point must break incoming segment")
        assert(track.path[3].x == 1000)
        private("sampleCarrierPosition")(0)
        config.features.vehicle_tracking = true
        config.vehicle.sample_interval_ms = 200
        private("sampleVehiclePositions")()
        config.features.vehicle_tracking = false
        assert(carrier.carry_distance == 0 and carrier.last_pos.x == 1000
            and not carrier.capture_gap, "carrier bridged pause")
        assert(vehicle.total_distance == 0 and vehicle.last_pos.x == 1000
            and not vehicle.capture_gap, "vehicle bridged pause")
        player_x = 1010
        frame(level + 200, 0, false)
        assert(track.path[4].event == "sample", "resume did not restore sampling")
        private("sampleCarrierPosition")(0)
        config.features.vehicle_tracking = true
        private("sampleVehiclePositions")()
        config.features.vehicle_tracking = false
        assert(carrier.carry_distance == 10 and carrier.path_samples == 1,
            "carrier did not resume measurement")
        assert(vehicle.total_distance == 10, "vehicle did not resume measurement")
        -- Approach metrics must use only the final contiguous segment.
        local ms, dist, beeline = private("calculateApproachMetrics")(track, game_time(), 10000)
        assert(ms == 200 and dist == 10 and beeline == 10, "approach bridged pause")
        frame(level + 200, 3, false)
    end
    assert(#tracker.completed_tracks == 1 and not tracker.player_tracks[0],
        "pause suppressed round-end lifecycle")
    assert(tracker.output_pending and not written_path, "delayed output not scheduled")
    frame(level + 100, 3, scenario == "paused_end")
    assert(tracker.output_written and written_path and closes == 1 and writes > 0,
        "delayed output failed during pause")
    frame(level + 100, 3, scenario == "paused_end")
    assert(closes == 1, "output repeated")
    print("CAPTURE_FILE=" .. written_path)
    print("PAUSE CAPTURE PROOF: " .. scenario .. "; real file closed; no live engine")
end
