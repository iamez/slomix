-- Frame-health watcher harness (runs under lua5.4, the interpreter the
-- game server embeds). Stubs the et API, loads the real tracker, and
-- drives et_RunFrame through the behaviours the watcher exists for.
-- Run from the repo root:  lua5.4 tests/lua/frame_health_harness.lua
--
-- v6.13: the body's cost is injected where the tracker reads `gamestate`
-- (its first cvar read of the frame), not by advancing the clock on every
-- trap_Milliseconds call -- the shared block added calls of its own, and a
-- per-call step would make every expectation depend on how many times the
-- clock is read rather than on how long the frame took.
local writes = {}       -- lines written to frame_health.log
local now_ms = 100000   -- simulated wall clock (engine already up)
local burn_in_body = 0  -- ms the frame body consumes (charged at the gamestate read)
local gamestate = "0"
local server_toggles = 0
local diagnostic_errors = {}
local throw_on_maxclients = false
et = setmetatable({
    FS_APPEND = 2, FS_WRITE = 1,
    CS_SERVERTOGGLES = 32,
    trap_GetConfigstring = function(index)
        if index == 32 then return tostring(server_toggles) end
        return ""
    end,
    trap_Milliseconds = function() return now_ms end,
    trap_Cvar_Get = function(name)
        if name == "sv_maxclients" and throw_on_maxclients then
            error("harness: injected engine error")
        end
        if name == "gamestate" then
            now_ms = now_ms + burn_in_body
            return gamestate
        end
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
        return len
    end,
    trap_FS_FCloseFile = function(fd) end,
    G_Print = function(msg)
        if msg:find("frame_health error:", 1, true) then
            diagnostic_errors[#diagnostic_errors + 1] = msg
        end
    end,
    RegisterModname = function() end,
}, { __index = function(t, k) return function() return 0 end end })

dofile("proximity/lua/proximity_tracker.lua")

local level = 0
local function frame(advance, hold_level)
    now_ms = now_ms + advance
    if not hold_level then level = level + advance end
    -- et_RunFrame may abort by design in scenario 4; the engine also
    -- survives a lua error, so the harness must too.
    pcall(et_RunFrame, level)
end
local function last_of(tag)
    for i = #writes, 1, -1 do
        if writes[i]:find("^" .. tag) then return writes[i] end
    end
    return nil
end

-- 0) map load -> the shared block's INIT line (mod=proximity_tracker) and,
--    on the first frame, the gap watcher's own proof line. Two write
--    paths, two proofs; an empty log is otherwise ambiguous.
et_InitGame(0, 0, 0)
assert(#writes >= 1 and writes[1]:find("FH init ") and writes[1]:find("mod=proximity_tracker"),
    "FAIL(0): no block INIT line on map load: " .. tostring(writes[1]))
writes = {}
frame(25)
assert(#writes == 1, "FAIL(0b): expected the watcher proof line on the first frame, got " .. #writes)
assert(writes[1]:find("FH watcher "), "FAIL(0b): not the watcher line: " .. writes[1])
writes = {}

-- 1) normal frames (25 ms apart) -> nothing further is written
for _ = 1, 10 do frame(25) end
assert(#writes == 0, "FAIL(1): wrote during normal frames: " .. tostring(writes[1]))

-- 2) a host-style stall: 300 ms BETWEEN frames, tracker itself cheap.
--    The line must carry the previous frame's (zero) self, not garbage,
--    and it is not paused: the engine pause bit is clear.
frame(300)
assert(#writes == 1, "FAIL(2): expected 1 line, got " .. #writes)
assert(writes[1]:find("gap=300 self=0 "), "FAIL(2): wrong pairing: " .. writes[1])
assert(writes[1]:find("players=6"), "FAIL(2): players: " .. writes[1])
assert(writes[1]:find("paused=0"), "FAIL(2): engine pause bit is clear: " .. writes[1])
writes = {}

-- 3) a slow TRACKER frame: the body burns 1500 ms. The NEXT frame's gap
--    line must attribute the burst to self (gap = 25 + 1500, self = 1500);
--    the shared block writes its FM line for the same frame. This is the
--    P0 pairing pin: the pre-fix code logged this line with self=0,
--    reading as "not the tracker".
frame(1200)          -- clear the 1/s throttle window first
writes = {}
burn_in_body = 1500
frame(25)
burn_in_body = 0
local fm = last_of("FM ")
assert(fm and fm:find("mod=proximity_tracker self=1500 "), "FAIL(3a): no FM line for the burning frame: " .. tostring(fm))
frame(25)
local gap_line = last_of("FH wall")
assert(gap_line and gap_line:find("gap=1525 "), "FAIL(3): gap should be 1525: " .. tostring(gap_line))
assert(gap_line:find("self=1500 "), "FAIL(3): burst not attributed to self: " .. gap_line)
writes = {}

-- 4) an error-aborted frame body: the sentinel, not stale data. The
--    hook re-raises, so pcall in frame() sees the error; the watcher's
--    prev_self stays -1 and the next line says so.
frame(1200)
writes = {}
throw_on_maxclients = true
frame(1200)          -- body throws mid-frame; watcher already updated cadence
throw_on_maxclients = false
frame(1200)
gap_line = last_of("FH wall")
assert(gap_line and gap_line:find("self=%-1 "), "FAIL(4): aborted frame must report self=-1: " .. tostring(gap_line))
writes = {}

-- 5) ET v2.85 G_RunFrame advances levelTime during match pause; only
-- timeCurrent freezes. The client also reads CV_SVS_PAUSE (16) from
-- CS_SERVERTOGGLES. Test the engine contract, not a frozen-clock surrogate.
frame(1200)
writes = {}
server_toggles = 16 + 2  -- unrelated setting must not hide pause
frame(1200)
frame(1200)
gap_line = last_of("FH wall")
assert(gap_line and gap_line:find("paused=1"), "FAIL(5): engine pause bit with advancing levelTime must read paused=1: " .. tostring(gap_line))
print("PAUSE PROOF: " .. gap_line:gsub("\n", ""))
server_toggles = 2
frame(1200)
gap_line = last_of("FH wall")
assert(gap_line and gap_line:find("paused=0"), "FAIL(5b): cleared pause bit must read paused=0: " .. tostring(gap_line))
frame(1200, true)
frame(1200, true)
gap_line = last_of("FH wall")
assert(gap_line and gap_line:find("paused=0"), "FAIL(5c): frozen levelTime alone is not a match pause: " .. tostring(gap_line))
print("NO-PAUSE PROOF: " .. gap_line:gsub("\n", ""))
writes = {}

-- Missing engine metadata is not a fabricated all-clear. The watcher
-- reports once, the frame body completes, and valid metadata recovers.
-- Isolate from scenario 4, which already exercised the one-error latch.
dofile("proximity/lua/proximity_tracker.lua")
et_InitGame(level, 0, 0)
frame(25)
writes = {}
diagnostic_errors = {}
server_toggles = ""
frame(1200)
frame(1200)
assert(not last_of("FH wall"), "FAIL(5d): missing toggles fabricated a gap status")
assert(#diagnostic_errors == 1 and diagnostic_errors[1]:find("invalid server toggles", 1, true),
    "FAIL(5d): missing metadata must produce one visible diagnostic")
server_toggles = 0
frame(1200)
gap_line = last_of("FH wall")
assert(gap_line and gap_line:find("self=0 ") and gap_line:find("paused=0"),
    "FAIL(5e): previous frame must complete and reporting must recover")
writes = {}

-- 6) the per-state cap bounds the file but does not truncate a two-hour
--    storm: 3000 gap lines fit (300 cut the 2026-09-02 storm at 301).
--    A fresh state first, so the count is the cap and not "cap minus the
--    lines the scenarios above already spent".
et_InitGame(0, 0, 1)
writes = {}
for _ = 1, 3100 do frame(1200) end
local gap_lines = 0
for _, w in ipairs(writes) do if w:find("^FH wall") then gap_lines = gap_lines + 1 end end
assert(gap_lines == 3000, "FAIL(6): cap should be 3000 gap lines per state, wrote " .. gap_lines)
writes = {}

-- 7) Defensive same-instance InitGame reset: cadence and write cap start over.
--    This is NOT official ET 2.85 map_restart (which reloads Lua VMs).
et_InitGame(0, 0, 1)
assert(#writes >= 1 and writes[1]:find("FH init "), "FAIL(7): no block INIT line after map_restart: " .. tostring(writes[1]))
writes = {}
frame(25)
assert(writes[#writes] and writes[#writes]:find("FH watcher "), "FAIL(7b): no watcher line after map_restart: " .. tostring(writes[#writes]))
frame(25)  -- and the very next frame must NOT log a bogus gap
assert(writes[#writes]:find("FH watcher "), "FAIL(7c): spurious line right after restart: " .. writes[#writes])

print(string.format("HARNESS OK (%d lines): %s", #writes,
    table.concat(writes, ""):gsub("\n", " | ")))
