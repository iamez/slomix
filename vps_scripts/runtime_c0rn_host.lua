-- Explicit load-time host adapter, replacing (never accompanying) c0rnp0rn8
-- in an operator-owned lua_modules wrapper. Loading fences legacy writes first.
-- No cvar/environment discovery, network listener, dependency installation,
-- retry or acknowledgement. Trusted Lua search paths and protected local socket
-- must be provisioned independently. This does NOT activate a game service.
require("runtime_c0rn_entrypoint")
local M, attempted = {}, false

function M.configure(options)
    assert(not attempted, "runtime host adapter configuration is one-shot")
    attempted = true -- Failed configuration stays fenced; never retry in this VM.
    assert(type(options)=="table", "explicit runtime host options required")
    local keys = {source_id=true, socket_path=true, bootstrap_timeout_ms=true, completion_timeout_ms=true}
    for key in pairs(options) do assert(keys[key], "unknown runtime host option") end
    local source, path = options.source_id, options.socket_path
    local bootstrap_timeout, completion_timeout = options.bootstrap_timeout_ms, options.completion_timeout_ms
    local now = et.trap_Milliseconds
    assert(type(now)=="function", "engine monotonic clock required")
    -- Construction preloads dependencies outside callbacks and does not connect.
    -- One sender per stats VM: writer-close delivery is one-shot, not a queue.
    local sender = require("runtime_host_completion").sender(path, now, completion_timeout)
    ConfigureRuntimeStatsHostHooks({source_id=source, socket_path=path,
        timeout_ms=bootstrap_timeout, completed=sender.completed})
    -- Capture the functions, not mutable caller options or globals, for observation.
    return {bootstrap_status=RuntimeStatsHostStatus, completion_status=sender.status}
end

return M
