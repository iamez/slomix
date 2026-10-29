-- Whole shipped tracker with real fixture files behind simulated ET VFS calls.
local directory, fault, fail_at = arg[1], arg[2], tonumber(arg[3]) or 1
local state, counter, now = '0', '0', 1700000000
local wire, scenario = arg[4], arg[5] or 'normal'
package.path = 'vps_scripts/?.lua;' .. package.path
local identity = wire and require('runtime_round_identity').decode(wire) or nil
local half = identity and identity.round_number or 1
counter = tostring(half - 1)
local map_name, gametype = 'supply', '3'
local opens, writes, closes, bytes = 0, 0, 0, 0
local logs, file = {}, nil
local noop = function() end
local name = '2026-10-08-120000-supply-round-' .. half .. '_engagements.txt'
et = {
    FS_APPEND=2, FS_WRITE=1, CS_SERVERTOGGLES=32, CS_INTERMISSION=22,
    trap_Milliseconds=function() return 610000 end,
    trap_GetConfigstring=function(index)
        if index == 31 then return '0 0 0 0 0 0 0 0 0 0' end
        return ''
    end,
    trap_Cvar_Get=function(key)
        local values = {gamestate=state, g_currentRound=counter, mapname=map_name, g_gametype=gametype,
            sv_maxclients='0', g_redlimbotime='30000', g_bluelimbotime='20000'}
        return values[key] or '0'
    end,
    gentity_get=function() return nil end,
    trap_GetUserinfo=function() return '' end,
    Info_ValueForKey=function() return '' end,
    RegisterModname=noop, G_Printf=noop,
    G_Print=function(message) logs[#logs+1] = message end,
    trap_FS_FOpenFile=function(path, mode)
        if path:find('frame_health', 1, true) then return -1, -1 end
        opens = opens + 1
        assert(path == directory .. '/' .. name and mode == 1, 'unexpected output')
        if fault == 'open-nil' then return nil, -1 end
        if fault == 'open-zero' then return 0, -1 end
        if fault == 'open-negative' then return -1, -1 end
        if fault == 'open-length' then return 42, -1 end
        file = assert(io.open(path, 'wb'))
        return 42, 0
    end,
    trap_FS_Write=function(data, count, fd)
        writes = writes + 1
        assert(fd == 42 and count == #data and file, 'bad write contract')
        if fault == 'throw-write' and writes == fail_at then error('fixture write throw') end
        local amount = fault == 'short' and writes == fail_at and count - 1 or count
        assert(file:write(data:sub(1, amount)))
        bytes = bytes + amount
        if fault == 'nil-write' and writes == fail_at then return nil end
        return amount
    end,
    trap_FS_FCloseFile=function(fd)
        assert(fd == 42 and file, 'invalid/double close')
        closes = closes + 1
        assert(file:close())
        file = nil
        if fault == 'close' then error('fixture ambiguous close failure') end
        -- Real ET close returns no Lua value, NOT a bool acknowledgement.
    end,
}
os.time = function() return now end
os.date = function() return '2026-10-08-120000' end
dofile('proximity/lua/proximity_tracker.lua')
local function lookup(fn, wanted, seen)
    seen = seen or {}
    if seen[fn] then return end
    seen[fn] = true
    for index=1, math.huge do
        local key, value = debug.getupvalue(fn, index)
        if not key then break end
        if key == wanted then return value end
        if type(value) == 'function' then
            local found = lookup(value, wanted, seen)
            if found ~= nil then return found end
        end
    end
end
local function private(key)
    for _, callback in ipairs({et_RunFrame, et_InitGame}) do
        local found = lookup(callback, key)
        if found ~= nil then return found end
    end
    error('missing real upvalue: ' .. key)
end
local config, tracker = private('config'), private('tracker')
for flag in pairs(config.features) do config.features[flag] = false end
config.objective_tracking = false
config.output_dir = directory .. '/'
config.output_delay_ms = 0
config.log_in_intermission = true
config.test_mode.enabled = false
config.output_guard = true
if scenario == 'no-init' then
    assert(not pcall(BindRuntimeProximity, identity, map_name))
    print('BIND_REJECTED')
    return
end
if scenario == 'warmup' then state = '1' end
et_InitGame(0, 0, 0)
if identity then
    if scenario == 'wrong-map' then map_name = 'oasis' end
    if scenario == 'wrong-half' then counter = tostring(half % 2) end
    if scenario == 'wrong-gametype' then gametype = '2' end
    local accepted = pcall(BindRuntimeProximity, identity, 'supply')
    if scenario == 'warmup' or scenario:find('wrong-', 1, true) then
        assert(not accepted, 'invalid binding accepted')
        print('BIND_REJECTED')
        return
    end
    assert(accepted, 'valid binding rejected')
    assert(not pcall(BindRuntimeProximity, identity, 'supply'), 'binding replaced')
    if scenario == 'mutate' then identity.round_id = string.rep('e', 32) end
    if scenario == 'reset' then et_InitGame(0, 0, 1) end
end
et_RunFrame(0)
if fault ~= 'empty' then
    tracker.completed_tracks = {{guid=string.rep('a', 32), name='Fixture', team='AXIS', class='MEDIC',
        spawn_time=fault == 'format' and {} or 0, death_time=600000, first_move_time=1,
        death_type='round_end', path={{time=100, x=1, y=2, z=3, health=100,
            speed=50, weapon=8, stance=0, sprint=0, event='sample'}}}}
end
if scenario == 'aggregates' then
    -- Synthetic captured values through the actual shipped output writer.
    tracker.kill_heatmap = {['1,2']={axis=3, allies=2}}
    tracker.movement_heatmap = {['1,2']={traversal=7, combat=4, escape=1}}
end
state, counter, now = '3', tostring(half == 1 and 1 or 0), 1700000610
if scenario == 'end-map' then map_name = 'oasis' end
if scenario == 'end-half' then counter = tostring(half - 1) end
if scenario == 'end-gametype' then gametype = '2' end
et_RunFrame(610000)
local first_opens, first_writes, first_closes = opens, writes, closes
if scenario == 'second-live' then
    state, counter = '0', tostring(half - 1)
    et_RunFrame(620000)
    state, counter = '3', tostring(half == 1 and 1 or 0)
    et_RunFrame(630000)
end
et_ShutdownGame(0)
assert(opens == first_opens and writes == first_writes and closes == first_closes,
    'same-round shutdown retried/truncated output')
assert(file == nil, 'output handle leaked')
print(string.format('RESULT written=%s attempted=%s in_progress=%s opens=%d writes=%d closes=%d bytes=%d',
    tostring(tracker.output_written), tostring(tracker.output_attempted),
    tostring(tracker.output_in_progress), opens, writes, closes, bytes))
print(table.concat(logs, '\n'))
