--[[============================================================================
 live_events.lua — real-time match events for the Slomix Live view.

 DESIGN: docs/research/LIVE_EVENTS_LUA_DESIGN_2026-08-12.md

 Writes rich per-event lines to its OWN log file (slomix-live.log) via a held
 file descriptor — NEVER through et.G_LogPrint. This is deliberate: every
 G_LogPrint line is also fed to et_Print of every other loaded module, and
 c0rnp0rn8/endstats use UNANCHORED string.find matchers (e.g. "Repair", the
 first "%d+" as a client id) that a rich payload could silently corrupt. A
 private FD sidesteps that entirely and never grows legacy3.log.

 Emits (see parser vps_scripts/liveview_parser.py, LIVEX grammar):
   I <ms> map <name>                     init/round-boundary marker
   K <ms> <ks> <vs> <mod> <kx,ky,kz> <vx,vy,vz> <khp> <dist>   enriched kill
   A <ms> <slot> <dg> <dr> <k> <d>       10s per-slot combat aggregate
   M <ms> <slot>:<x>,<y>[,<yaw>] ...     movement tick (0.5 Hz)

 Slots only, never names (the website resolves slot->name from its roster).
 No GUIDs. Config flag live_events_enabled defaults FALSE — the module loads
 inert until explicitly turned on. Must be LAST in lua_modules.

 Owner decisions (2026-08-12): movement 0.5 Hz, damage aggregate in v1,
 viewangles attempted (fail-closed), NOT deployed to the gameserver today.
============================================================================]]

local M = {}

-- ---- config ---------------------------------------------------------------
local config = {
    enabled = false,            -- master flag; overridden by config file below
    log_name = "slomix-live.log",
    movement_interval = 2000,   -- ms between movement ticks (0.5 Hz)
    aggregate_interval = 10000, -- ms between combat aggregates
    emit_viewangles = true,     -- try ps.viewangles; disabled if unsupported
    truncate_on_init = true,    -- reset the log each InitGame (tailer survives)
}

-- Optional override file next to the other Lua config (same loader idea as
-- stats_discord_webhook.lua): fs_homepath/<fs_game>/live_events_config.lua
-- returning a table of overrides. Fail-open to defaults.
local function load_overrides()
    local ok_home, homepath = pcall(et.trap_Cvar_Get, "fs_homepath")
    local ok_game, game = pcall(et.trap_Cvar_Get, "fs_game")
    if not ok_home or homepath == nil or homepath == "" then return end
    if not ok_game or game == nil or game == "" then game = "legacy" end
    local path = homepath .. "/" .. game .. "/luascripts/live_events_config.lua"
    local f = io.open(path, "r")
    if not f then return end
    f:close()
    local chunk = loadfile(path)
    if not chunk then return end
    local ok, tbl = pcall(chunk)
    if ok and type(tbl) == "table" then
        for k, v in pairs(tbl) do
            if config[k] ~= nil and type(v) == type(config[k]) then
                config[k] = v
            end
        end
    end
end

-- ---- state ----------------------------------------------------------------
local log_fd = nil
local epoch_offset_ms = 0        -- os.time*1000 - levelTime at InitGame
local last_move_tick = 0
local last_agg_tick = 0
local round_number = 0
local unsupported = {}           -- gentity fields this engine rejects
local agg = {}                   -- slot -> {dg, dr, k, d}

-- ---- helpers --------------------------------------------------------------
local function safe_get(clientnum, field, index)
    if unsupported[field] then return nil end
    local ok, value
    if index ~= nil then
        ok, value = pcall(et.gentity_get, clientnum, field, index)
    else
        ok, value = pcall(et.gentity_get, clientnum, field)
    end
    if ok then return value end
    if tostring(value):find("invalid gentity field") then
        unsupported[field] = true
    end
    return nil
end

local function now_ms(levelTime)
    -- Prefer the real epoch (offset captured at InitGame); levelTime is the
    -- fallback and is monotonic per map, which the parser also tolerates.
    if epoch_offset_ms ~= 0 then return levelTime + epoch_offset_ms end
    return levelTime
end

local function write(line)
    if not config.enabled or not log_fd then return end
    -- pcall: a full disk must never take down the game frame.
    pcall(function()
        log_fd:write(line, "\n")
        log_fd:flush()
    end)
end

local function open_log()
    local ok_home, homepath = pcall(et.trap_Cvar_Get, "fs_homepath")
    local ok_game, game = pcall(et.trap_Cvar_Get, "fs_game")
    if not ok_home or homepath == nil or homepath == "" then return end
    if not ok_game or game == nil or game == "" then game = "legacy" end
    local path = homepath .. "/" .. game .. "/" .. config.log_name
    local mode = config.truncate_on_init and "w" or "a"
    local f = io.open(path, mode)
    if f then log_fd = f end
end

local function is_active(clientnum)
    return safe_get(clientnum, "pers.connected") == 2
end

-- et_Damage / et_Obituary can fire with non-client entity ids (constructibles,
-- tanks, the world, MOD sources > maxclients). Only real player slots
-- [0, sv_maxclients) may enter the aggregate — otherwise entity id 578 with
-- 99999 damage lands in the feed (caught in the 2026-08-12 bot test).
local function is_client(id)
    return type(id) == "number" and id >= 0 and id < maxclients()
end

local function pos_of(clientnum)
    local o = safe_get(clientnum, "ps.origin")
    if not o then return nil end
    return tonumber(o[1]) or 0, tonumber(o[2]) or 0, tonumber(o[3]) or 0
end

local function yaw_of(clientnum)
    if not config.emit_viewangles then return nil end
    local a = safe_get(clientnum, "ps.viewangles")
    if not a then return nil end
    return tonumber(a[2])  -- [pitch, yaw, roll]
end

local function maxclients()
    local n = tonumber(et.trap_Cvar_Get("sv_maxclients")) or 64
    return n
end

-- ---- callbacks ------------------------------------------------------------
function et_InitGame(levelTime, _randomSeed, _restart)
    load_overrides()
    epoch_offset_ms = (os.time() * 1000) - levelTime
    if config.enabled then
        open_log()
        write(string.format("I %d map %s", now_ms(levelTime),
            tostring(et.trap_Cvar_Get("mapname"))))
    end
    last_move_tick = levelTime
    last_agg_tick = levelTime
    agg = {}
end

function et_ShutdownGame(_restart)
    if log_fd then pcall(function() log_fd:close() end); log_fd = nil end
end

-- c0rnp0rn8 signature: et_Obituary(victim, killer, mod)
function et_Obituary(victim, killer, mod)
    if not config.enabled then return end
    if not is_client(victim) then return end
    local lvl = et.trap_Milliseconds()
    -- combat aggregate
    agg[victim] = agg[victim] or { dg = 0, dr = 0, k = 0, d = 0 }
    agg[victim].d = agg[victim].d + 1
    local dist = -1
    local kx, ky, kz = 0, 0, 0
    local vx, vy, vz = pos_of(victim)
    vx, vy, vz = vx or 0, vy or 0, vz or 0
    local khp = -1
    if killer ~= victim and killer ~= 1022 and killer ~= 1023 then
        agg[killer] = agg[killer] or { dg = 0, dr = 0, k = 0, d = 0 }
        agg[killer].k = agg[killer].k + 1
        kx, ky, kz = pos_of(killer)
        kx, ky, kz = kx or 0, ky or 0, kz or 0
        khp = tonumber(safe_get(killer, "health")) or -1
        local dx, dy, dz = kx - vx, ky - vy, kz - vz
        dist = math.floor(math.sqrt(dx * dx + dy * dy + dz * dz))
    end
    write(string.format("K %d %d %d %d %d,%d,%d %d,%d,%d %d %d",
        now_ms(lvl), killer, victim, mod or 0,
        kx, ky, kz, vx, vy, vz, khp, dist))
end

-- et_Damage(target, attacker, damage, damageFlags, meansOfDeath)
function et_Damage(target, attacker, damage, _flags, _mod)
    if not config.enabled then return end
    local dmg = tonumber(damage) or 0
    if dmg <= 0 then return 0 end
    -- cap absurd single-hit values (world/telefrag) so one line can't skew MVP
    if dmg > 1000 then dmg = 1000 end
    if is_client(target) then
        agg[target] = agg[target] or { dg = 0, dr = 0, k = 0, d = 0 }
        agg[target].dr = agg[target].dr + dmg
    end
    if is_client(attacker) and attacker ~= target then
        agg[attacker] = agg[attacker] or { dg = 0, dr = 0, k = 0, d = 0 }
        agg[attacker].dg = agg[attacker].dg + dmg
    end
    return 0  -- passthrough, never alter damage
end

local function flush_aggregate(levelTime)
    for slot, a in pairs(agg) do
        if is_client(slot) and (a.dg ~= 0 or a.dr ~= 0 or a.k ~= 0 or a.d ~= 0) then
            write(string.format("A %d %d %d %d %d %d",
                now_ms(levelTime), slot, a.dg, a.dr, a.k, a.d))
        end
    end
    agg = {}
end

local function movement_tick(levelTime)
    local parts = {}
    for i = 0, maxclients() - 1 do
        if is_active(i) then
            local x, y = pos_of(i)
            if x then
                local yaw = yaw_of(i)
                if yaw then
                    parts[#parts + 1] = string.format("%d:%d,%d,%d",
                        i, math.floor(x), math.floor(y), math.floor(yaw))
                else
                    parts[#parts + 1] = string.format("%d:%d,%d",
                        i, math.floor(x), math.floor(y))
                end
            end
        end
    end
    if #parts > 0 then
        write(string.format("M %d %s", now_ms(levelTime), table.concat(parts, " ")))
    end
end

function et_RunFrame(levelTime)
    if not config.enabled then return end
    if levelTime - last_move_tick >= config.movement_interval then
        last_move_tick = levelTime
        movement_tick(levelTime)
    end
    if levelTime - last_agg_tick >= config.aggregate_interval then
        last_agg_tick = levelTime
        flush_aggregate(levelTime)
    end
end

return M
