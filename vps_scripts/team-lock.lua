--[[
    Author: mAxPower
    Contributors:
    License: MIT

    Description:    In ETLegacy stopwatch, teams are unlocked when there is a gamestate change.
                    This script solves the issue by locking each team using referee commands when there
                    is a start to a round or a gamestate change from pause/unpause.
]]--

-- version info

local modname = "team-lock"
local version = "1.0"

-- BEGIN frame_health v6.13 (identical in every module; tests/unit/test_lua_frame_health_block_identical.py pins it)
-- Every Lua module runs in its own VM, and the engine calls their
-- et_RunFrame hooks one after another (g_lua.c G_LuaHook_RunFrame). They
-- share one clock (et.trap_Milliseconds) and one process, so each module
-- can append its own frame cost to the SAME log the tracker's gap watcher
-- writes, and the reader attributes a gap offline: sum of the modules'
-- `self` inside the gap window is "our Lua", the rest is engine/host.
--   FH init wall=<ms> version=6.13 mod=<name>   one per map load (write-path proof)
--   FM wall=<frame end ms> mod=<name> self=<ms> top=<section>:<ms>
--                                          when a frame cost >= self_threshold_ms
-- Rate-limited to one line per second per module and capped per lua state.
-- trap_FS paths are relative to the homepath game dir, so this is the
-- tracker's ~/.etlegacy/legacy/proximity/frame_health.log for every module.
local FH_MOD = "team-lock"
local fh = {
    version = "6.13", log = "proximity/frame_health.log",
    self_threshold_ms = 50, min_write_interval_ms = 1000, max_lines_per_state = 3000,
    writes = 0, last_write = -math.huge, frame_start = nil, top_name = nil, top_ms = 0,
    error_printed = false,
}
local function fh_now()
    return (et and et.trap_Milliseconds and et.trap_Milliseconds()) or 0
end
local function fh_write(line)
    if fh.writes >= fh.max_lines_per_state then return end
    -- endstats append idiom: the SECOND return signals an open failure
    local fd, open_len = et.trap_FS_FOpenFile(fh.log, et.FS_APPEND)
    if not fd or fd == -1 or fd == 0 or open_len == -1 then return end
    fh.writes = fh.writes + 1
    et.trap_FS_Write(line, string.len(line), fd)
    et.trap_FS_FCloseFile(fd)
end
local function fh_guard(what, f, ...)
    local ok, err = pcall(f, ...)
    if not ok and not fh.error_printed then
        fh.error_printed = true
        et.G_Print("[" .. FH_MOD .. "] frame_health " .. what .. " error: " .. tostring(err) .. "\n")
    end
end
-- Call from et_InitGame: a map load (and map_restart) starts a fresh cadence.
local function fh_init()
    fh_guard("init", function()
        fh.writes = 0
        fh.last_write = -math.huge
        fh.frame_start = nil
        fh.top_name = nil
        fh.top_ms = 0
        fh_write(string.format("FH init wall=%d version=%s mod=%s\n", fh_now(), fh.version, FH_MOD))
    end)
end
local function fh_begin()
    fh.frame_start = fh_now()
    fh.top_name = nil
    fh.top_ms = 0
end
-- Call right after a known-costly section with the wall time taken before
-- it: the costliest section of the frame is what the FM line names.
local function fh_section(name, t0)
    local ms = fh_now() - t0
    if ms > fh.top_ms then
        fh.top_ms = ms
        fh.top_name = name
    end
end
local function fh_end()
    fh_guard("end", function()
        if fh.frame_start == nil then return end
        local now = fh_now()
        local self_ms = now - fh.frame_start
        fh.frame_start = nil
        if self_ms < fh.self_threshold_ms then return end
        if now - fh.last_write < fh.min_write_interval_ms then return end
        fh.last_write = now
        fh_write(string.format("FM wall=%d mod=%s self=%d top=%s:%d\n",
            now, FH_MOD, self_ms, fh.top_name or "-", fh.top_ms))
    end)
end
-- END frame_health v6.13

-- local flags

local roundStarted = false

function et_InitGame(levelTime, randomSeed, restart)
    fh_init()
    et.RegisterModname(modname .. " " .. version)
end

function et_RunFrame(levelTime)
    if et.trap_Cvar_Get("gamestate") == "0" then -- Game is running
        if not roundStarted then
            et.trap_SendConsoleCommand(et.EXEC_APPEND, "ref lock r\n")
            et.trap_SendConsoleCommand(et.EXEC_APPEND, "ref lock b\n")
            roundStarted = true
        end
    else
        roundStarted = false
    end
end

function et_ClientCommand(clientNum, command)
    local cmd = string.lower(et.trap_Argv(0))
    if cmd == "pause" then
        et.trap_SendConsoleCommand(et.EXEC_APPEND, "ref unlock r\n")
        et.trap_SendConsoleCommand(et.EXEC_APPEND, "ref unlock b\n")
    elseif cmd == "unpause" then
        roundStarted = false -- This will allow the lock commands to be reissued when the game resumes
    end
end

-- BEGIN frame_health hook v6.13 (identical in every module)
-- Wraps the module's own et_RunFrame so its whole cost -- early returns
-- included -- lands in fh_end. An error inside is re-raised unchanged so
-- the engine still prints it; the measurement is taken first.
local fh_wrapped_run_frame = et_RunFrame
function et_RunFrame(levelTime)
    fh_begin()
    local ok, err = pcall(fh_wrapped_run_frame, levelTime)
    fh_end()
    if not ok then error(err, 0) end
end
-- END frame_health hook v6.13
