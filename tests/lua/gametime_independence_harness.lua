-- Whole shipped module, real local writer, synthetic ET state, no network.
local source, directory, mode = arg[1], arg[2], arg[3]
local enabled, target, capture, failure_only = arg[4] == '1', arg[5] == '1', arg[6] == '1', arg[7] == '1'
local logs, launches, opens, shell_calls = {}, 0, 0, 0
local values = {mapname='supply', g_currentRound='1', timelimit='20',
    gamestate='3', sv_maxclients='0', sv_maxClients='0', net_ip='127.0.0.1', net_port='27960',
    g_gametype='3', fs_homepath=directory}
local identity_wire, binding_fault = arg[8], arg[9]
local half = 1
local identity
local exit_flag = binding_fault == 'stale-intermission' and '1' or ''
if identity_wire then
    package.path = assert(source:match('^(.*)/')) .. '/?.lua;' .. package.path
    identity = require('runtime_round_identity').decode(identity_wire)
    half = identity.round_number
end
et = {
    trap_Cvar_Get = function(key)
        return values[key] or ''
    end,
    CS_INTERMISSION=22, CS_SERVERINFO=0,
    trap_GetConfigstring = function(index)
        if index == 22 then return exit_flag end
        if index == 0 then return '\\mapname\\' .. values.mapname end
        return ''
    end,
    Info_ValueForKey = function(_, key) return key == 'mapname' and values.mapname or '' end,
    RegisterModname = function() end,
    trap_FS_FOpenFile = function() return -1, -1 end,
    gentity_get = function() return 0 end,
    trap_Milliseconds = function() return 610000 end,
    G_Print = function(message) logs[#logs + 1] = message end,
}
dofile(source)

-- Introspect closures, never extract/reimplement production function bodies.
local function locate(root, name, seen)
    seen = seen or {}
    if seen[root] then return end
    seen[root] = true
    local children = {}
    for index = 1, math.huge do
        local key, value = debug.getupvalue(root, index)
        if not key then break end
        if key == name then return root, index, value end
        if type(value) == 'function' then children[#children + 1] = value end
    end
    for _, child in ipairs(children) do
        local parent, index, value = locate(child, name, seen)
        if parent then return parent, index, value end
    end
end
local function get(name)
    local parent, index, value = locate(et_RunFrame, name)
    assert(parent, 'missing actual upvalue: ' .. name)
    return value, parent, index
end
local function set(name, value)
    local _, parent, index = get(name)
    assert(debug.setupvalue(parent, index, value) == name)
end
local config = get('configuration')
config.enabled = enabled
config.discord_webhook_urls = target and {'https://example.invalid/fixture-only'} or {}
config.discord_webhook_url = 'REPLACE_WITH_YOUR_WEBHOOK_URL'
config.gametimes_enabled = capture
config.gametimes_write_on_failure_only = failure_only
config.gametimes_dir = directory
config.pending_dir = directory .. '/pending'
config.debug = true
os.time = function() return 1700000610 end
local output_closed = false
local real_open = io.open
io.open = function(path, flags)
    if identity_wire and path == directory .. '/legacy/luascripts/stats_discord_webhook_config.lua' then
        assert(flags == 'r')
        return nil, 'fixture config absent', 2
    end
    opens = opens + 1
    if mode == 'transport' or mode == 'sweep' then error('forbidden queue file access') end
    assert(path == directory .. (binding_fault == 'map-output' and '/gametime-supply_te_test-R' or '/gametime-supply-R') .. half .. '-1700000610.json', 'unexpected file path')
    if mode == 'write-fail' then return nil, 'fixture open failure' end
    local file, failure = real_open(path, flags)
    if binding_fault and binding_fault:match('^completion') and file then
        return {write=function(_,bytes) return file:write(bytes) end,
            close=function()
                local result=file:close()
                if binding_fault=='completion-close-fail' then return nil,'fixture close failure' end
                output_closed=true; return result
            end}
    end
    return file, failure
end
os.execute = function(command)
    shell_calls = shell_calls + 1
    if mode == 'transport' or mode == 'sweep' then error('forbidden queue shell command') end
    assert(command == "mkdir -p '" .. directory .. "'", 'unexpected shell command: ' .. command)
    return true
end
io.popen = function() error('forbidden pending scan') end

if identity_wire then
    if binding_fault == 'map-alphabet' or binding_fault == 'map-output' then values.mapname = 'supply.te+test' end
    values.gamestate, values.g_currentRound = '0', tostring(2 - half)
    if binding_fault ~= 'noinit' then et_InitGame(100, 0, 0) end
    local observed = {init_time=100, map_name=values.mapname, counter=tonumber(values.g_currentRound),
        gamestate=0, exit_flag=exit_flag}
    local lease = require('runtime_init_lease').capture(et, function() return observed end, function() end)
    assert(lease:match('|(%d+)$') == tostring(half), 'timing profile disagrees with actual stats lease')
    print('STATS_LEASE_PROFILE half=' .. half .. ' counter=' .. values.g_currentRound)
    if binding_fault == 'wrong-half' then values.g_currentRound = tostring(half - 1) end
    if binding_fault == 'warmup' then values.gamestate = '2' end
    if binding_fault == 'wrong-map' then values.mapname = 'oasis' end
    local completion
    if binding_fault and binding_fault:match('^completion') then
        completion={generation=string.rep('a',32), directory=directory, completed=function(receipt,generation)
            assert(output_closed, 'callback ran before checked writer close')
            assert(receipt.version==1 and receipt.state=='writer_closed')
            assert(generation==string.rep('a',32))
            local file=assert(real_open(directory .. '/' .. receipt.filename,'rb'))
            local bytes=file:read('*a'); file:close()
            assert(#bytes==receipt.bytes)
            print('TIMING_CLOSED_AFTER_READ bytes=' .. #bytes)
        end}
    end
    local accepted, reason = pcall(BindRuntimeGametime, identity, observed.map_name, completion)
    print('BIND=' .. tostring(accepted) .. ':' .. tostring(reason))
    if not accepted then
        print(string.format('COUNTS launches=%d opens=%d shell=%d', launches, opens, shell_calls))
        return
    end
    assert(reason == identity_wire)
    if binding_fault == 'map-alphabet' then print('MAP_BIND_ACCEPTED'); return end
    identity.round_id = string.rep('f', 32) -- Caller mutation must not change frozen wire.
    if binding_fault == 'reset' then et_InitGame(200, 0, 0) end
    if binding_fault == 'replace' then assert(not pcall(BindRuntimeGametime, identity, 'supply')) end
    values.gamestate, values.g_currentRound = '3', tostring(half - 1)
    if binding_fault == 'end-half' then values.g_currentRound = tostring(2 - half) end
    if binding_fault == 'end-map' then values.mapname = 'oasis' end
    if binding_fault == 'end-counter' then values.g_currentRound = '2' end
    if binding_fault == 'end-state' then values.gamestate = '0' end
    if binding_fault == 'end-gametype' then values.g_gametype = '2' end
end

if mode == 'transport' then
    local ok = get('execute_curl_async')('{}')
    assert(ok == false)
elseif mode == 'sweep' then
    get('pending_retry_sweep')()
else
    set('execute_curl_async', function(payload)
        launches = launches + 1
        assert(payload:find('STATS_READY', 1, true))
        return mode ~= 'launch-fail', 'fixture launch only; not delivery acknowledgement'
    end)
    set('round_start_unix', 1700000000)
    set('round_end_unix', 1700000610)
    set('total_pause_seconds', 10)
    set('pause_count', 1)
    if mode == 'frame' then
        assert(not enabled or not target, 'frame proof must use real disabled sweep')
        et_RunFrame(610000)
        et_RunFrame(610050)
    else
        local send = get('send_webhook')
        send()
        -- Successful local write or launch deduplicates the same round result.
        if mode ~= 'write-fail' then send() end
    end
end
print(string.format('COUNTS launches=%d opens=%d shell=%d', launches, opens, shell_calls))
print(table.concat(logs, '\n'))

if binding_fault=='two-halves' then
    local second=require('runtime_round_identity').decode(assert(arg[10]))
    half=2
    values.gamestate,values.g_currentRound='0','0'
    exit_flag=''
    et_InitGame(200,0,1)
    assert(not pcall(BindRuntimeGametime,require('runtime_round_identity').decode(identity_wire),'supply'))
    assert(BindRuntimeGametime(second,'supply')==arg[10])
    values.gamestate,values.g_currentRound='3','1'
    set('round_start_unix',1700000000)
    set('round_end_unix',1700000610)
    set('total_pause_seconds',10)
    set('pause_count',1)
    get('send_webhook')()
    print('TWO_HALVES_REBOUND')
end
