-- Frame-health watcher harness (runs under lua5.4, the interpreter the
-- game server embeds). Stubs the et API, loads the real tracker, and
-- drives et_RunFrame through the four behaviours the watcher exists for.
-- Run from the repo root:  lua5.4 tests/lua/frame_health_harness.lua

local writes = {}       -- lines written to frame_health.log
local now_ms = 100000   -- simulated wall clock (engine already up)
local clock_step = 0    -- added AFTER each trap_Milliseconds call
local throw_on_maxclients = false

et = setmetatable({
    FS_APPEND = 2, FS_WRITE = 1,
    trap_Milliseconds = function()
        local t = now_ms
        now_ms = now_ms + clock_step
        return t
    end,
    trap_Cvar_Get = function(name)
        if name == "sv_maxclients" and throw_on_maxclients then
            error("harness: injected engine error")
        end
        if name == "gamestate" then return "0" end
        if name == "sv_maxclients" then return "16" end
        return ""
    end,
    gentity_get = function(clientNum, field)
        if field == "sess.sessionTeam" then return (clientNum < 6) and 1 or 3 end
        if field == "pers.connected" then return (clientNum < 6) and 2 or 0 end
        return 0
    end,
    trap_FS_FOpenFile = function(name, mode)
        if name:find("frame_health") then return 99, 0 end
        return 42, 0
    end,
    trap_FS_Write = function(data, len, fd)
        if fd == 99 then writes[#writes + 1] = data end
    end,
    trap_FS_FCloseFile = function(fd) end,
    G_Print = function(msg) end,
    RegisterModname = function() end,
}, { __index = function(t, k) return function() return 0 end end })

dofile("proximity/lua/proximity_tracker.lua")

local function frame(advance)
    now_ms = now_ms + advance
    -- et_RunFrame may abort by design in scenario 4; the engine also
    -- survives a lua error, so the harness must too.
    pcall(et_RunFrame, now_ms)
end

-- 0) the very first frame writes the INIT line -- the positive proof that
--    the write path works (an empty log is otherwise ambiguous).
frame(25)
assert(#writes == 1, "FAIL(0): no INIT line on first frame")
assert(writes[1]:find("FH init "), "FAIL(0): not an init line: " .. writes[1])
table.remove(writes, 1)

-- 1) normal frames (25 ms apart) -> nothing further is written
for _ = 1, 10 do frame(25) end
assert(#writes == 0, "FAIL(1): wrote during normal frames")

-- 2) a host-style stall: 300 ms BETWEEN frames, tracker itself cheap.
--    The line must carry the previous frame's (small) self, not garbage.
frame(300)
assert(#writes == 1, "FAIL(2): expected 1 line, got " .. #writes)
assert(writes[1]:find("gap=300 self=0 "), "FAIL(2): wrong pairing: " .. writes[1])
assert(writes[1]:find("players=6"), "FAIL(2): players: " .. writes[1])

-- 3) a slow TRACKER frame: the frame's own body burns wall time (the
--    round-end burst shape). The stub clock advances on EVERY
--    trap_Milliseconds call and the frame makes two (start, end), so
--    step=1500 yields self=1500 and a 3000 ms frame period; the NEXT
--    frame's line must attribute both to the SAME frame. This is the P0
--    pairing pin: the pre-fix code logged this line with self=0,
--    reading as "not the tracker".
clock_step = 1500
frame(1200)          -- clear the 1/s throttle window first
clock_step = 0
frame(25)
local last = writes[#writes]
assert(last:find("gap=3025 "), "FAIL(3): gap should be 3025: " .. last)
assert(last:find("self=1500 "), "FAIL(3): burst not attributed to self: " .. last)

-- 4) an error-aborted frame body: the sentinel, not stale data.
throw_on_maxclients = true
frame(1200)          -- body throws mid-frame; watcher already updated cadence
throw_on_maxclients = false
frame(1200)
last = writes[#writes]
assert(last:find("self=%-1 "), "FAIL(4): aborted frame must report self=-1: " .. last)

-- 5) map_restart keeps the lua VM alive; et_InitGame must reset the
--    cadence so the INIT proof fires on restarts too (review on #876).
et_InitGame(0, 0, 1)
frame(25)
assert(writes[#writes]:find("FH init "), "FAIL(5): no INIT line after map_restart: " .. writes[#writes])
frame(25)  -- and the very next frame must NOT log a bogus gap
assert(writes[#writes]:find("FH init "), "FAIL(5b): spurious line right after restart: " .. writes[#writes])

print(string.format("HARNESS OK (%d lines): %s", #writes,
    table.concat(writes, ""):gsub("\n", " | ")))
