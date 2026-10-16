-- Install only after the WHOLE stats module, including its frame-health wrapper.
-- Trusted same-VM adapter. Explicit configuration before ANY engine callback;
-- no socket discovery, dependency installation, retry loop or completion sink.
local M = {}

function M.attach()
    local init, frame, shutdown = et_InitGame, et_RunFrame, et_ShutdownGame
    local capture = CaptureRuntimeStatsHostInit
    assert(type(init) == "function" and type(frame) == "function"
        and type(shutdown) == "function" and type(capture) == "function", "stats hooks unavailable")
    local seen, attempted, start, client = false, false, nil, nil
    local phase, reason = "unconfigured", nil
    local reported = false
    local function report_failure()
        if reported or (phase ~= "failed" and phase ~= "unconfirmed") then return end
        reported = true
        -- Fixed labels only: never emit arbitrary exception/peer payload text.
        local code = "bootstrap_failure"
        if type(reason) == "string" and reason:find("live context disagrees with InitGame observation", 1, true) then
            code = "live_context_mismatch"
        elseif reason == "unexpected InitGame gamestate" then
            code = "unexpected_init_state"
        end
        if type(et.G_Print) == "function" then
            pcall(et.G_Print, "Slomix runtime host: " .. phase .. " " .. code .. "\n")
        end
    end
    local function cancel()
        if client then client.close(); client = nil end
    end
    et_InitGame = function(...)
        seen = true
        cancel() -- Old lease/channel must not cross an InitGame boundary.
        reported = false
        phase, reason = "init_failed", "original InitGame did not finish"
        init(...) -- Do not mask original callback errors or start after failure.
        phase, reason = start and "starting" or "unconfigured", nil
        if start then
            -- ET2.85 initializes warmup both on map load and between halves.
            -- Never consume a lease/open a channel for these callbacks. A later
            -- frame changing state is NOT a new InitGame observation.
            local state = tonumber(et.trap_Cvar_Get("gamestate"))
            if state == -1 or state == 1 or state == 2 or state == 4 or state == 5 then
                phase, reason = "waiting_playing_init", nil
                return
            elseif state ~= 0 then
                phase, reason = "failed", "unexpected InitGame gamestate"
                report_failure()
                return
            end
            local ok, value = pcall(start)
            if ok then client = value; phase, reason = client.status()
            else phase, reason = "failed", tostring(value) end
            report_failure()
        end
    end
    et_RunFrame = function(...)
        seen = true
        if client then phase, reason = client.poll() end -- One bounded step, never a loop.
        report_failure()
        return frame(...) -- Preserve the final c0rn frame-health/error wrapper.
    end
    et_ShutdownGame = function(...)
        seen = true
        cancel() -- Close even if the original writer subsequently raises.
        phase, reason = "stopped", nil
        return shutdown(...) -- A previously bound final write remains permitted.
    end
    return {
        configure = function(options)
            assert(not seen and not attempted, "host hooks configuration is load-time and one-shot")
            attempted = true -- A failed dependency/config attempt cannot be retried.
            phase, reason = "configuration_failed", "configuration did not finish"
            assert(type(options) == "table", "host hooks options required")
            local keys = {source_id=true, socket_path=true, timeout_ms=true, completed=true}
            for key in pairs(options) do assert(keys[key], "unknown host hooks option") end
            local source, path, timeout, completed = options.source_id, options.socket_path,
                options.timeout_ms, options.completed
            assert(type(source) == "string" and #source >= 1 and #source <= 64
                and source:match("^[a-z0-9][a-z0-9_.%-]*$"), "invalid host hooks source")
            assert(type(path) == "string" and path:sub(1,1) == "/" and #path <= 107
                and not path:find("%z"), "explicit local socket path required")
            assert(type(timeout) == "number" and timeout > 0 and timeout <= 10000,
                "bounded channel deadline required")
            assert(type(completed) == "function", "explicit completion sink required")
            local now = et.trap_Milliseconds
            assert(type(now) == "function", "engine monotonic clock required")
            -- Resolve all optional dependencies outside game callbacks. LuaSocket
            -- and its search path must be approved/provisioned by the operator.
            require("socket.unix")
            require("runtime_init_lease")
            require("runtime_completed_stats")
            local bootstrap = require("runtime_host_bootstrap")
            local channel = require("runtime_host_channel")
            start = function()
                return bootstrap.start(capture, function() return channel.open(path, now, timeout) end,
                    source, completed)
            end
            phase, reason = "waiting_init", nil
        end,
        status = function() return phase, reason end,
    }
end

return M
