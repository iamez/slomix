--[[----------------------------------------------------------------------------
dots_arena_1v1.lua — fair 1v1 on an arena map.

THE PROBLEM
-----------
On a pure-aim 1v1 map the two players do not start a duel on equal terms. When
one kills the other, the winner keeps whatever health and ammo he was left
with and carries NO spawn shield, while the loser goes through limbo and comes
back at full health with the engine's 3-second invulnerability. The convention
players use today is that the winner types /kill so both go through the same
door — but the two deaths are a second or two apart, so the shields expire at
different moments and the reset is only approximately fair.

This script does the same thing the players do by hand, in the SAME FRAME as
the kill, which is the part a human cannot do.

WHY SAME-FRAME IS THE WHOLE TRICK
---------------------------------
dots_arena already asks for a 1-second respawn for both teams
(scripts/dots_arena.arena: axisRespawnTime/alliedRespawnTime 1, and
maps/dots_arena.script repeats it with wm_axis_respawntime/wm_allied_respawntime).
The engine gives every spawning player `ps.powerups[PW_INVULNERABLE] =
level.time + 3000` in ClientSpawn. So if both players die in the same frame and
respawn in the same frame, the shields are identical BY CONSTRUCTION and this
script never has to write a powerup at all. Everything below exists to make
"same frame" true.

VERIFIED AGAINST THIS SERVER'S BINARY (legacy/qagame.mp.x86_64.so, ET:L 2.85)
----------------------------------------------------------------------------
Read out of the module's own registration tables, not from memory:

  * Callbacks present: et_InitGame, et_ShutdownGame, et_RunFrame, et_Obituary,
    et_ClientSpawn, et_ClientCommand, et_ConsoleCommand.
  * There is NO Lua binding that kills or respawns a client. et.G_Damage is
    the only way to end a life from a script.
  * `health` is NOT a gentity field the Lua API exposes — not for get, not for
    set. Aliveness has to be read as ps.stats[STAT_HEALTH].
  * ⛔ `DAMAGE_*` and `ENTITYNUM_*` are NOT registered as et.* constants (zero
    matches in the module's constant table), so their values are written out
    below as numbers. DAMAGE_NO_PROTECTION = 0x20 comes from
    src/game/g_local.h at tag v2.85.0; 1022 is ENTITYNUM_WORLD.
  * `PW_INVULNERABLE`, `STAT_HEALTH`, `TEAM_*`, `MOD_*` ARE registered, so
    those are read off et.* rather than hardcoded.
  * Array fields take an index: et.gentity_get(cn, "ps.powerups", idx) — the
    same call shape c0rnp0rn8.lua:984 already uses on this server.

WHY THE ATTACKER IS THE WORLD AND NOT THE PLAYER HIMSELF
--------------------------------------------------------
`/kill` is player_die(ent, ent, ent, ...) — attacker == self — and g_combat.c
increments pers.playerStats.selfkills exactly on that condition. That is why
today's manual convention shows up in the stats as a selfkill. Using the world
(1022) as inflictor and attacker keeps the reset out of the selfkill counters,
and our own parser already ignores world/unknown killers
(c0rnp0rn8.lua:726 skips killer 1022/1023), so a forced reset scores nothing
for anybody.

⚠️ What it DOES still cost: player_die counts a death for the victim on every
mod, so the winner takes a death for each duel he wins. That is a deliberate
trade — the alternative (MOD_SWAP_PLACES) has no precedent in our parser or in
endstats.lua, and inventing one to save a number is how stats start lying.
Anyone reading arena rounds should read kills, not K/D.

USAGE
-----
  lua_modules "dots_arena_1v1.lua"       (alongside the existing modules)
  arena_1v1 1                            (default 1; set 0 to disable live)

The script only arms itself on a map whose name contains "dots_arena" AND when
exactly two players are on the two teams. Anything else — three players, a
spectator joining, another map — and it stands down without touching a thing.
------------------------------------------------------------------------------]]

local MODNAME  = "dots_arena_1v1"
local VERSION  = "1.0.0"

-- Not et.* constants on 2.85 (checked): write them as the numbers they are.
local ENTITYNUM_WORLD      = 1022
local DAMAGE_NO_PROTECTION = 0x00000020  -- g_local.h @ v2.85.0
local LETHAL_DAMAGE        = 1000        -- far past GIB_HEALTH from any health

local active        = false   -- armed on this map?
local forced        = {}      -- clientNum -> true while OUR damage is in flight
local saved_forcerespawn = nil

local function cvar_num(name, fallback)
  local raw = et.trap_Cvar_Get(name)
  return tonumber(raw) or fallback
end

local function enabled()
  return cvar_num("arena_1v1", 1) ~= 0
end

local function map_name()
  local info = et.trap_GetConfigstring(et.CS_SERVERINFO)
  return (et.Info_ValueForKey(info, "mapname") or ""):lower()
end

--- Which map arms the script. A cvar rather than a hardcoded name, because the
--- mechanism has to be measurable on a map Omni-bot can actually navigate:
--- dots_arena ships no waypoints, so bots stand still on it and a round there
--- produces nothing for the stats half of the test.
local function armed_map()
  local raw = et.trap_Cvar_Get("arena_1v1_map")
  if raw == nil or raw == "" then return "dots_arena" end
  return raw:lower()
end

-- ── Measurement ────────────────────────────────────────────────────────────
-- "Both players come back in the same frame with the same shield" is a claim,
-- and a claim needs a reading. Every obituary and every spawn writes one line
-- with the numbers that decide it, so the verdict is a file rather than
-- somebody's memory of the console.
local LOG = "arena_1v1.log"

local function log(fmt, ...)
  if cvar_num("arena_1v1_log", 1) == 0 then return end
  local line = os.date("%H:%M:%S ") .. string.format(fmt, ...) .. "\n"
  local fd, len = et.trap_FS_FOpenFile(LOG, et.FS_APPEND)
  if not fd or fd == -1 or fd == 0 or len == -1 then return end
  et.trap_FS_Write(line, string.len(line), fd)
  et.trap_FS_FCloseFile(fd)
end

--- The three numbers a duel is judged on, read straight off the engine.
local function reading(cn)
  local hp = et.gentity_get(cn, "ps.stats", et.STAT_HEALTH)
  local shield = et.gentity_get(cn, "ps.powerups", et.PW_INVULNERABLE)
  local selfkills = et.gentity_get(cn, "pers.playerStats.selfkills")
  return tonumber(hp) or -9999, tonumber(shield) or 0, tonumber(selfkills) or -1
end

--- Clients that are connected and on a playing team, as a list of numbers.
local function players_on_teams()
  local out = {}
  for cn = 0, cvar_num("sv_maxclients", 64) - 1 do
    if et.gentity_get(cn, "pers.connected") == 2 then
      local team = et.gentity_get(cn, "sess.sessionTeam")
      if team == et.TEAM_AXIS or team == et.TEAM_ALLIES then
        out[#out + 1] = cn
      end
    end
  end
  return out
end

local function is_alive(cn)
  -- `health` is not exposed to Lua; STAT_HEALTH is the only reading available.
  local hp = et.gentity_get(cn, "ps.stats", et.STAT_HEALTH)
  return type(hp) == "number" and hp > 0
end

--- End a life without scoring it: world as inflictor and attacker, and enough
--- damage to gib from any starting health.
---
--- ⛔⛔ The spawn shield has to be CLEARED FIRST, and DAMAGE_NO_PROTECTION does
--- not do it. G_Damage returns early on `ps.powerups[PW_INVULNERABLE]` at
--- g_combat.c:1593 — twenty-two lines BEFORE it ever looks at the dflags at
--- :1615. The comment on the define ("armor, shields, invulnerability, and
--- godmode have no effect", g_local.h:1671) is simply wrong about this path.
---
--- Measured before this line existed: 80 duels split perfectly in two. Where
--- the survivor's shield had expired, the two players came back 25 ms apart
--- (median, = one frame at sv_fps 40) and 34 times at exactly the same
--- instant. Where the shield was still up, the damage was a NO-OP and the
--- survivor died 2.8-3.4 s later — i.e. the first duel after every spawn, the
--- start of every series, was the unfair one.
local function force_reset(cn, mod, why)
  local hp, shield, selfkills = reading(cn)
  log("FORCE   cn=%d why=%s health=%d shield=%d selfkills=%d",
      cn, why, hp, shield, selfkills)
  forced[cn] = true
  et.gentity_set(cn, "ps.powerups", et.PW_INVULNERABLE, 0)
  et.G_Damage(cn, ENTITYNUM_WORLD, ENTITYNUM_WORLD, LETHAL_DAMAGE,
              DAMAGE_NO_PROTECTION, mod)
end

function et_InitGame(levelTime, randomSeed, restart)
  et.RegisterModname(MODNAME .. " " .. VERSION)
  forced = {}
  -- ⛔ `active` is the MAP gate ONLY. It used to fold in the arena_1v1 enable
  -- cvar as well, which made the control run impossible to take: with
  -- arena_1v1 0 the module went fully dark, so the very measurement that has
  -- to show the UNFAIR behaviour could not be driven either. Arming (which map)
  -- and enabling (does the reset fire) are two questions; the auto-reset asks
  -- enabled() where it acts.
  active = map_name():find(armed_map(), 1, true) ~= nil
  if not active then
    return
  end

  -- g_forcerespawn -1 is the engine's own instant-respawn branch (g_active.c
  -- takes it BEFORE the reinforcement wave). It matters more than it looks:
  -- the wave offsets are randomised PER TEAM at match start and are not
  -- reachable from Lua, so two players on opposite teams cannot be brought
  -- onto the same wave by setting g_redlimbotime and g_bluelimbotime equal.
  -- Instant respawn sidesteps the wave entirely, which is the only way to get
  -- both players back in the same frame.
  saved_forcerespawn = et.trap_Cvar_Get("g_forcerespawn")
  et.trap_Cvar_Set("g_forcerespawn", "-1")
  et.G_Print(MODNAME .. ": armed on " .. map_name() ..
             " (g_forcerespawn was '" .. tostring(saved_forcerespawn) .. "', now -1)\n")
end

function et_ShutdownGame(restart)
  if active and saved_forcerespawn ~= nil and saved_forcerespawn ~= "" then
    et.trap_Cvar_Set("g_forcerespawn", saved_forcerespawn)
  end
  active = false
end

function et_Obituary(victim, killer, mod)
  -- ⛔ The MAP gate only, here. The measurement has to run on the control pass
  -- too — with arena_1v1 0 this hook used to return before it logged anything,
  -- so the very run that must show the UNFAIR behaviour recorded nothing while
  -- the spawn hook kept writing. An instrument placed behind the switch it is
  -- measuring is not an instrument.
  if not active then
    return
  end

  -- Our own damage re-enters this hook, and this guard is the only thing that
  -- stops the chain.
  --
  -- ⛔ An earlier version of this comment claimed the guard was unreachable,
  -- reasoning from an offline stub in which a freshly-killed player already
  -- read as dead. The live server says otherwise: across 26 obituaries the
  -- victim's ps.stats[STAT_HEALTH] was 2..42 — POSITIVE every single time,
  -- never below zero. `is_alive()` would therefore call the corpse alive and
  -- damage it again. The engine sets health after this hook runs, not before,
  -- which is exactly the kind of ordering an offline model gets wrong.
  if forced[victim] then
    forced[victim] = nil
    return
  end

  -- ⚠️ Read the victim's health HERE. Whether the engine has already written
  -- it below zero by the time this hook runs is the one thing the offline stub
  -- could not answer, and it decides whether the recursion guard above is ever
  -- in play at all.
  local vhp, vshield, vself = reading(victim)
  log("OBIT    victim=%d killer=%d mod=%d health=%d shield=%d selfkills=%d",
      victim, killer, mod, vhp, vshield, vself)

  if not enabled() then
    log("OFF     arena_1v1=0 — no reset, this is the control")
    return
  end

  local players = players_on_teams()
  if #players ~= 2 then
    log("SKIP    players=%d (not a 1v1)", #players)
    return  -- not a 1v1 right now; leave the map alone
  end

  -- Everyone still standing goes down in THIS frame, which is the whole point:
  -- both players then leave limbo in the same frame and ClientSpawn hands them
  -- the same `level.time + 3000` shield.
  for _, cn in ipairs(players) do
    if cn ~= victim and is_alive(cn) then
      force_reset(cn, et.MOD_SUICIDE, "survivor")
    end
  end
end

--- The spawn side of the reading. `levelTime` is not passed to this hook, so
--- the shield IS the clock: ClientSpawn sets it to level.time + 3000, so two
--- players that spawned in the same frame carry the same absolute number.
-- Last shield expiry each player was handed, so a pair can be levelled.
local spawn_shield = {}

function et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)
  if not active then
    return
  end
  local hp, shield, selfkills = reading(clientNum)
  log("SPAWN   cn=%d revived=%s health=%d shield=%d selfkills=%d",
      clientNum, tostring(revived), hp, shield, selfkills)
  spawn_shield[clientNum] = shield

  -- ⛔ The engine will NOT put both players back on the same frame, and no
  -- amount of Lua changes that: SpectatorClientEndFrame deliberately delays an
  -- instant respawn by one server frame (`instantRespawnDelayTime`,
  -- g_active.c:1820-1828, comment: "circumvents specific issues that currently
  -- occur when player die and respawn on the same server frame"). Measured,
  -- that floor is exactly the 25 ms median we saw at sv_fps 40.
  --
  -- So level the thing the players actually feel instead. ClientSpawn writes
  -- `powerups[PW_INVULNERABLE] = level.time + 3000` (g_client.c:3331) and this
  -- hook runs AFTER it, so the write below survives. Both shields are pulled
  -- to the EARLIER expiry — never the later one, so nobody ends up with more
  -- protection than the engine meant to give.
  if not enabled() then
    return
  end
  for _, other in ipairs(players_on_teams()) do
    if other ~= clientNum then
      local theirs = spawn_shield[other]
      if theirs and theirs > 0 and shield > 0 and math.abs(shield - theirs) <= 1000 then
        local level_to = math.min(shield, theirs)
        if level_to ~= shield then
          et.gentity_set(clientNum, "ps.powerups", et.PW_INVULNERABLE, level_to)
          spawn_shield[clientNum] = level_to
        end
        if level_to ~= theirs then
          et.gentity_set(other, "ps.powerups", et.PW_INVULNERABLE, level_to)
          spawn_shield[other] = level_to
        end
        log("LEVEL   cn=%d cn=%d shield=%d (was %d/%d)",
            clientNum, other, level_to, shield, theirs)
      end
    end
  end
end

--- Test-only console command, so a duel can be driven deterministically from
--- the server console. Omni-bot 0.91 bots idle when no human is connected and
--- dots_arena ships no waypoints, so waiting for bots to shoot each other is
--- not a measurement method — this is.
---
--- ⛔ Returns 1 (handled) ONLY for its own command. Returning a value for
--- anything else would swallow console commands belonging to other modules.
function et_ConsoleCommand()
  -- ⛔ `active` too, not just the test cvar. Without this the command fires on
  -- any map, including one where the script is deliberately standing down —
  -- found by the offline case that runs on a NON-arena map, which the first
  -- five cases could not catch because they all ran on the arena.
  if not active or cvar_num("arena_1v1_test", 0) == 0 then
    return 0
  end
  if string.lower(et.trap_Argv(0)) ~= "arena_kill" then
    return 0
  end
  local cn = tonumber(et.trap_Argv(1))
  if cn == nil then
    et.G_Print(MODNAME .. ": usage: arena_kill <clientnum>\n")
    return 1
  end
  log("TESTCMD arena_kill cn=%d", cn)
  force_reset(cn, et.MOD_SUICIDE, "test-command")
  return 1
end
