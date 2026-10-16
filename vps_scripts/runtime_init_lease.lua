-- Opaque in-VM bootstrap lease, NOT authentication against hostile Lua/native
-- code. All loaded modules and this local adapter are trusted. The public wire
-- is an observation, never a lifecycle ID or permission to dispatch/recover.
local M = {}

local function snapshot(api, context)
    assert(type(context) == "table", "InitGame observation unavailable")
    local time, map, counter = context.init_time, context.map_name, context.counter
    assert(type(time) == "number" and time >= 0 and time <= 2147483647 and time % 1 == 0,
        "invalid observed InitGame time")
    assert(type(map) == "string" and #map >= 1 and #map <= 64
        and map:match("^[A-Za-z0-9_.+%-]+$") and not map:find("..",1,true), "invalid observed map")
    assert((counter == 0 or counter == 1) and context.gamestate == 0,
        "InitGame observation is not active stopwatch")
    local exit = api.trap_GetConfigstring(api.CS_INTERMISSION)
    assert(tonumber(api.trap_Cvar_Get("gamestate")) == 0
        -- ET2.85 map_restart retains CS_INTERMISSION from the previous half.
        -- Compare against fresh InitGame, not an assumed cleared configstring.
        -- G_LogExit flips g_currentRound before later Lua frame callbacks;
        -- the counter check below still fences a newly queued stopwatch exit.
        and tonumber(api.trap_Cvar_Get("g_gametype")) == 3
        and (exit == "" or exit == "0" or exit == "1") and exit == context.exit_flag
        and tonumber(api.trap_Cvar_Get("g_currentRound")) == counter
        and api.Info_ValueForKey(api.trap_GetConfigstring(api.CS_SERVERINFO), "mapname") == map,
        "live context disagrees with InitGame observation")
    -- ET stopwatch active-start values are 1 for R1 and 0 for R2.
    return "slomix_init_v1|" .. string.format("%.0f",time) .. "|" .. map .. "|" .. (2 - counter)
end

function M.capture(api, current, configure)
    assert(type(current) == "function" and type(configure) == "function", "invalid InitGame adapter")
    local observed = current()
    local wire = snapshot(api, observed)
    local used = false
    return wire, function(options, completed)
        assert(not used, "InitGame lease already consumed")
        used = true -- Errors may have side effects: never retry this closure.
        assert(current() == observed, "InitGame lease invalidated")
        assert(snapshot(api, observed) == wire, "InitGame observation changed")
        return configure(options, completed)
    end
end

return M
