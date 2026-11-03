-- Explicit fresh-VM loader composition. Does not discover paths or activate ET.
local hooks=require('runtime_combined_hooks')
local timing_bridge=require('runtime_gametime_binding')
local M,attempted={},false

local function clear_callbacks()
    for name,value in pairs(_G) do
        if type(name)=='string' and name:match('^et_') and type(value)=='function' then _G[name]=nil end
    end
end

function M.configure(options,loaders)
    assert(not attempted,'combined host configuration is one-shot')
    attempted=true
    assert(type(options)=='table' and type(loaders)=='table','explicit combined host provisioning required')
    local allowed={source_id=true,socket_path=true,bootstrap_timeout_ms=true,
        completion_timeout_ms=true,producer_spool=true,timing_sockets=true}
    for key in pairs(options) do assert(allowed[key],'unknown combined host option') end
    for key in pairs(loaders) do assert(key=='stats' or key=='timing','unknown producer loader') end
    assert(type(loaders.stats)=='function' and type(loaders.timing)=='function','both trusted loaders required')
    assert(type(options.timing_sockets)=='table'
        and options.socket_path~=options.timing_sockets[1]
        and options.socket_path~=options.timing_sockets[2],
        'stats and timing channels must be independent')
    assert(next(hooks.capture(_G))==nil,'fresh VM required; competing callbacks already installed')
    local result
    local ok,failure=pcall(function()
        -- The stats loader must use runtime_c0rn_host, which fences legacy stats.
        local host=loaders.stats()
        assert(type(host)=='table' and type(host.configure)=='function','fenced stats host required')
        local stats=hooks.capture(_G)
        assert(stats.et_InitGame and stats.et_RunFrame and stats.et_ShutdownGame,'whole stats callbacks required')
        clear_callbacks()
        loaders.timing()
        assert(type(BindRuntimeGametime)=='function' and type(RequireRuntimeGametimeBinding)=='function',
            'whole timing module with runtime fence required')
        RequireRuntimeGametimeBinding()
        local timing=hooks.capture(_G)
        assert(timing.et_InitGame and timing.et_RunFrame and timing.et_ShutdownGame,'whole timing callbacks required')
        local bridge=timing_bridge.prepare({source_id=options.source_id,
            producer_spool=options.producer_spool,timing_sockets=options.timing_sockets,
            timeout_ms=options.completion_timeout_ms},BindRuntimeGametime,et.trap_Milliseconds)
        result=host.configure({source_id=options.source_id,socket_path=options.socket_path,
            bootstrap_timeout_ms=options.bootstrap_timeout_ms,
            completion_timeout_ms=options.completion_timeout_ms,after_bound=bridge})
        local combined=hooks.compose(stats,timing)
        clear_callbacks()
        for name,callback in pairs(combined) do _G[name]=callback end
    end)
    if not ok then
        -- Fresh VM had no callbacks. Never leave a partially loaded legacy writer.
        clear_callbacks()
        error(failure,0)
    end
    return result
end
return M
