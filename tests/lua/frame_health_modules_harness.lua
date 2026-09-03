-- frame_health v6.13 harness for the five NON-tracker modules (runs under
-- lua5.4, the interpreter the game server embeds). Stubs the et API and
-- the host facilities a module touches at load (io, os, loadfile, bit),
-- loads each module in a fresh environment, and drives et_InitGame +
-- et_RunFrame through the behaviours the shared block exists for:
--   0) the INIT line with mod=<name> on map load (write-path proof);
--   1) quiet frames write nothing;
--   2) a frame whose body burns >= 50 ms writes ONE FM line naming the
--      module, attributed to that frame;
--   3) the 1 s throttle holds;
--   4) an error inside the body still yields the FM line, and the error
--      still reaches the caller (the engine prints it) -- a measurement
--      that swallows errors would turn a broken module into a calm one.
-- Run from the repo root:  lua5.4 tests/lua/frame_health_modules_harness.lua

local MODULES = {
    { path = "vps_scripts/team-lock.lua",             name = "team-lock" },
    { path = "vps_scripts/c0rnp0rn8.lua",             name = "c0rnp0rn8" },
    { path = "vps_scripts/endstats.lua",              name = "endstats" },
    { path = "vps_scripts/stats_discord_webhook.lua", name = "stats_discord_webhook" },
    { path = "vps_scripts/live_events.lua",           name = "live_events" },
}

local function run_one(mod)
    local writes = {}
    local now_ms = 100000
    local burn_in_body = 0   -- ms the frame body costs: charged once per frame,
                             -- right after the hook's opening clock read, so
                             -- a module that returns early (live_events with
                             -- config.enabled=false) is measured like any other
    local burn_pending = false
    local throw_in_body = false
    local read_gamestate = false

    local et = setmetatable({
        FS_APPEND = 2, FS_WRITE = 1, FS_READ = 0, EXEC_APPEND = 2, EXEC_NOW = 0,
        GS_PLAYING = 0, GS_WARMUP = 2, GS_INTERMISSION = 3, CS_SERVERTOGGLES = 7,
        trap_Milliseconds = function()
            local t = now_ms
            if burn_pending then
                burn_pending = false
                now_ms = now_ms + burn_in_body
            end
            return t
        end,
        trap_Cvar_Get = function(name)
            if name == "gamestate" then
                read_gamestate = true
                if throw_in_body then error("harness: injected body error") end
                return "2"
            end
            if name:lower() == "sv_maxclients" then return "16" end
            if name == "fs_homepath" then return "/tmp/fh-harness" end
            if name == "fs_game" then return "legacy" end
            return ""
        end,
        trap_Cvar_Set = function() end,
        trap_GetConfigstring = function() return "0" end,
        gentity_get = function() return 0 end,
        trap_FS_FOpenFile = function(name, mode)
            if name:find("frame_health") then return 99, 0 end
            return -1, -1
        end,
        trap_FS_Write = function(data, len, fd)
            if fd == 99 then writes[#writes + 1] = data end
        end,
        trap_FS_FCloseFile = function() end,
        trap_FS_Read = function() return "" end,
        trap_SendConsoleCommand = function() end,
        trap_Argv = function() return "" end,
        G_Print = function() end,
        RegisterModname = function() end,
        FindSelf = function() return 0 end,
        ConcatArgs = function() return "" end,
    }, { __index = function() return function() return 0 end end })

    -- Fresh globals per module: modules define globals (et_* hooks, helpers)
    -- and must not see each other.
    local env = setmetatable({ et = et }, { __index = _G })
    env.bit = { band = function(a, b) return a & b end, bor = function(a, b) return a | b end,
                lshift = function(a, n) return a << n end, rshift = function(a, n) return a >> n end }
    env.io = { open = function() return nil, "harness: no files" end,
               popen = function() return nil, "harness: no popen" end,
               write = function() end }
    env.os = { time = os.time, date = os.date, clock = os.clock, getenv = function() return nil end,
               execute = function() return 0 end, remove = function() return true end,
               rename = function() return true end, tmpname = function() return "/tmp/x" end }
    env.loadfile = function() return nil, "harness: no config file" end
    env.dofile = function() return nil end
    env.require = function() error("harness: require not available") end
    local chunk, err = loadfile(mod.path, "t", env)
    assert(chunk, "load " .. mod.path .. ": " .. tostring(err))
    chunk()
    assert(type(env.et_RunFrame) == "function", mod.name .. ": no et_RunFrame")
    assert(type(env.et_InitGame) == "function", mod.name .. ": no et_InitGame")

    local level = 0
    local function frame(advance)
        now_ms = now_ms + advance
        level = level + 25
        burn_pending = burn_in_body > 0
        return pcall(env.et_RunFrame, level)
    end

    -- 0) map load -> INIT line naming the module
    local ok, e = pcall(env.et_InitGame, 0, 0, 0)
    assert(ok, mod.name .. ": et_InitGame threw: " .. tostring(e))
    assert(#writes >= 1, mod.name .. " FAIL(0): no INIT line")
    assert(writes[1]:find("FH init "), mod.name .. " FAIL(0): not an init line: " .. writes[1])
    assert(writes[1]:find("mod=" .. mod.name .. "\n", 1, true), mod.name .. " FAIL(0): init line lacks mod=: " .. writes[1])
    writes = {}

    -- 1) quiet frames write nothing
    for _ = 1, 20 do frame(25) end
    assert(#writes == 0, mod.name .. " FAIL(1): wrote during quiet frames: " .. tostring(writes[1]))

    -- 2) a slow frame body -> one FM line for this module, self >= 50
    burn_in_body = 120
    frame(25)
    burn_in_body = 0
    assert(#writes == 1, mod.name .. " FAIL(2): expected 1 FM line, got " .. #writes .. " " .. tostring(writes[1]))
    assert(writes[1]:find("^FM wall=%d+ mod=" .. mod.name:gsub("%-", "%%-") .. " self=%d+ top="),
        mod.name .. " FAIL(2): bad FM line: " .. writes[1])
    local self_ms = tonumber(writes[1]:match("self=(%d+)"))
    assert(self_ms >= 120, mod.name .. " FAIL(2): self should include the body's 120 ms: " .. writes[1])
    writes = {}

    -- 3) the 1 s throttle: a second slow frame inside the same second is silent
    burn_in_body = 120
    frame(25)
    burn_in_body = 0
    assert(#writes == 0, mod.name .. " FAIL(3): throttle did not hold")
    frame(1200)
    burn_in_body = 120
    frame(25)
    burn_in_body = 0
    assert(#writes == 1, mod.name .. " FAIL(3b): after the window the line must come")
    writes = {}

    -- 4) an error in the body: measured AND re-raised. The error is injected
    --    at the gamestate read; a module that never reads it in a frame
    --    (live_events with the feature disabled) has no body to error in.
    if read_gamestate then
        frame(1200)
        writes = {}
        throw_in_body = true
        burn_in_body = 200
        local ok4 = frame(25)
        throw_in_body = false
        burn_in_body = 0
        assert(ok4 == false, mod.name .. " FAIL(4): the body's error was swallowed")
        assert(#writes == 1 and writes[1]:find("^FM "), mod.name .. " FAIL(4): erroring frame not measured: " .. tostring(writes[1]))
    else
        print("  (" .. mod.name .. ": no gamestate read in a frame -- error scenario not applicable)")
    end

    return true
end

for _, mod in ipairs(MODULES) do
    run_one(mod)
    print("HARNESS OK " .. mod.name)
end
