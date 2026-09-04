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
local MAX_CLIENTS          = 64    -- entity numbers below this are players
local WP_MP40              = 3     -- bg_public.h:848+ ; Axis SMG
local WP_THOMPSON          = 8     -- ; Allies SMG
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

-- ── Vampiric: what you take off them, you get back ─────────────────────────
--
-- Diabotical's Shaft Arena and QuakeLive's vampiric servers, on ET's numbers.
-- Diabotical leeches 50% ("do 10 damage, receive 5hp") and that is the default
-- here; QuakeLive's own community warns that 100% makes LG fights "almost
-- endless", which is the failure this mode has to avoid, not chase.
--
-- MP40 and Thompson both do 18 damage every 150 ms (bg_misc.c:164, :169) =
-- 120 dmg/s sustained. With a 1000 HP pool and 50% leech, a duel where one
-- player lands 60% and the other 40% resolves in roughly 20-30 s -- long
-- enough for movement and tracking to decide it, short enough to end.
--
-- ⛔ Two engine facts shape this, both read out of the source rather than
-- assumed:
--
--  * ps.stats[STAT_MAX_HEALTH] CANNOT be raised. ClientEndFrame calls
--    AddMedicTeamBonus() every frame (g_active.c:2307), which recomputes it
--    from pers.maxHealth -- and pers.maxHealth is read-only to Lua
--    (g_lua.c:1282). So we raise `health` and leave the ceiling alone; nothing
--    clamps health down to it. The engine does bleed the surplus at 1 HP per
--    second while health > max (g_active.c:941-944) -- about 30 HP over a
--    30 s duel, which is noise, but it LOOKS like a lifesteal bug, so it is
--    written down here.
--  * et_Damage can CANCEL damage (return 1) but cannot change it, and a
--    returned 1 stops the module walk -- which would starve c0rnp0rn8,
--    endstats, live_events and proximity_tracker of every damage event. This
--    hook therefore returns NOTHING, ever.

local vamp_active  = false   -- in force for the duel being fought now
local vamp_pending = nil     -- what the next spawn will adopt
local duel_started = nil     -- trap_Milliseconds at the start of this duel

--- Measured on the local 2.84 server with two bots, 2026-09-04. The pool and
--- the duel length are NOT proportional — lifesteal makes it a race between
--- two drains, so the curve bends hard:
---
---     300 HP  ->  median  7 s  (n=11)
---     500 HP  ->  median 14 s  (n=7)
---    1000 HP  ->  ONE duel in 120 s
---
--- 1000 was the first guess and it is the "fights take forever" failure the
--- QuakeLive community warns about, reached at 50% leech rather than 100%.
--- 500 is the measured middle and the default; raise it with the cvar if you
--- want longer, but raise it knowing the curve.
local function vamp_hp()    return cvar_num("arena_vamp_hp", 500) end
local function vamp_steal() return cvar_num("arena_vamp_steal", 50) end
local function vamp_grace() return cvar_num("arena_vamp_grace", 90) end
local function vamp_decay() return cvar_num("arena_vamp_decay", 30) end

--- The leech fraction right now: full until the grace period, then falling to
--- zero across the decay window. A duel that will not end on skill ends on
--- arithmetic instead of running until someone leaves.
local function steal_fraction()
  local base = vamp_steal() / 100.0
  if base <= 0 or duel_started == nil then return base end
  local elapsed = (et.trap_Milliseconds() - duel_started) / 1000.0
  local grace = vamp_grace()
  if elapsed <= grace then return base end
  local decay = vamp_decay()
  if decay <= 0 then return 0 end
  local left = 1.0 - (elapsed - grace) / decay
  if left <= 0 then return 0 end
  return base * left
end

-- ── The world keeps the score ──────────────────────────────────────────────
--
-- The world kills both players, so the world owes them the tally. It has to,
-- because nothing else here can:
--
--   * the scoreboard is useless on this map — every duel gives the WINNER a
--     death too (player_die counts one for every mod, g_combat.c:861), so K/D
--     reads as a draw no matter who is winning;
--   * arena rounds are excluded from stats on purpose (owner, 2026-09-04), so
--     nothing downstream will ever add them up either.
--
-- A point goes to the OPPONENT of whoever died — including when a player kills
-- themselves, which is the duel convention and also stops "/kill to deny the
-- point" from being a tactic. Our own forced reset is not a death anybody
-- earned and scores nothing; the recursion guard already tells the two apart.
local score = {}     -- clientNum -> duels won
local score_pair = nil  -- the two clientNums the current tally belongs to

local function player_name(cn)
  local raw = et.gentity_get(cn, "pers.netname")
  if type(raw) ~= "string" or raw == "" then return "cn" .. tostring(cn) end
  return et.Q_CleanStr(raw)
end

--- Reset the tally whenever the pair changes: a score carried over from a
--- different pair of players is a lie about both of them.
local function ensure_pair(players)
  local key = table.concat(players, ":")
  if score_pair ~= key then
    score_pair = key
    score = {}
    for _, cn in ipairs(players) do score[cn] = 0 end
  end
end

local function announce(players)
  local parts = {}
  for _, cn in ipairs(players) do
    parts[#parts + 1] = string.format("%s ^3%d", player_name(cn), score[cn] or 0)
  end
  local line = table.concat(parts, " ^7- ")
  et.trap_SendServerCommand(-1, 'cp "^7' .. line .. '\n"')
  et.trap_SendServerCommand(-1, 'chat "^7arena: ' .. line .. '"')
  log("SCORE   %s", line:gsub("%^%d", ""))
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
  -- A new map starts 0-0. Without this the tally survives a map change and
  -- the first announcement of the next map is a score nobody played for.
  score = {}
  score_pair = nil
  vamp_active = cvar_num("arena_vamp", 0) ~= 0
  vamp_pending = nil
  duel_started = nil
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

  -- The point goes to the other player, however the victim died — killed,
  -- gibbed by the world, or self-inflicted. Only OUR reset is exempt, and the
  -- guard above has already returned for that case.
  ensure_pair(players)
  for _, cn in ipairs(players) do
    if cn ~= victim then
      score[cn] = (score[cn] or 0) + 1
    end
  end

  -- Everyone still standing goes down in THIS frame, which is the whole point:
  -- both players then leave limbo in the same frame and ClientSpawn hands them
  -- the same `level.time + 3000` shield.
  for _, cn in ipairs(players) do
    if cn ~= victim and is_alive(cn) then
      force_reset(cn, et.MOD_SUICIDE, "survivor")
    end
  end

  announce(players)
end

--- The spawn side of the reading. `levelTime` is not passed to this hook, so
--- the shield IS the clock: ClientSpawn sets it to level.time + 3000, so two
--- players that spawned in the same frame carry the same absolute number.
-- Last shield expiry each player was handed, so a pair can be levelled.
local spawn_shield = {}

--- Give the arena loadout: one SMG, per team, nothing else. Also the reason
--- the 190-damage gib trap (g_combat.c:1928, any single hit above 190 sets
--- health to -176 regardless of the pool) cannot fire here — an 18-damage SMG
--- never reaches it, while a panzerfaust would end a 1000 HP duel in one shot.
--- ⛔ WITHDRAWN after the first live run (2026-09-04). This stripped every
--- weapon but one on each spawn, and the measurement said it did not work:
--- Axis bots kept spawning with `w\23` (Kar98, their class default) instead of
--- MP40, while the server produced a ClientUserinfoChanged storm at ~1 Hz and
--- the bots stopped killing each other entirely — 246 lifesteal events and a
--- single obituary in two minutes.
---
--- Two mistakes worth naming rather than quietly deleting:
---  * `pcall` around every RemoveWeaponFromPlayer swallowed whatever the
---    binding was actually saying. A loop that cannot fail is a loop that
---    cannot be debugged.
---  * removing the weapon a client is HOLDING sets ps.weapon = 0 and fires
---    EV_WEAPONSWITCHED (g_lua.c:1163-1176); doing that 54 times per spawn,
---    against a bot that re-picks its own weapon every frame, is a fight the
---    script cannot win.
---
--- Forcing the loadout is not required by lifesteal and is now an open item,
--- not a silent half-feature. Left as a stub so its absence is deliberate.
local function arena_loadout(cn)
  return   -- see the note above; weapon forcing is not attempted
end

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
  -- ⛔ The 1v1 gate belongs here too. Without it the levelling ran on every
  -- spawn no matter how many players were on the teams — measured on 2.84:
  -- 55 levelling events against 12 actual duels, the surplus being a six-bot
  -- warm-up in which this module has no business touching anybody's shield.
  local roster = players_on_teams()
  if #roster ~= 2 then
    return
  end
  -- The switch takes effect HERE and nowhere else: flipping vampiric in the
  -- middle of a duel would hand one player a pool the other never had. The
  -- request waits until both are fresh, which is this moment.
  if vamp_pending ~= nil then
    vamp_active = vamp_pending
    vamp_pending = nil
    log("VAMP    now %s", tostring(vamp_active))
  end
  duel_started = et.trap_Milliseconds()
  if vamp_active then
    et.gentity_set(clientNum, "health", vamp_hp())
    et.gentity_set(clientNum, "ps.stats", et.STAT_HEALTH, vamp_hp())
    arena_loadout(clientNum)
    -- ⛔ The SPAWN line above was written BEFORE this, so it reports the
    -- engine's 100 and not the pool a vampiric duel actually starts with. It
    -- read like the mode was not applying at all (live run, 2026-09-04) while
    -- the STEAL lines showed health climbing to exactly the configured cap.
    -- An instrument that logs before the action measures the wrong moment.
    log("VAMPHP  cn=%d health=%d", clientNum, vamp_hp())
  end

  for _, other in ipairs(roster) do
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

--- Lifesteal. `damage` is the FINAL figure the engine is about to subtract —
--- every multiplier (headshot, helmet, adrenaline, falloff) already applied
--- (g_combat.c:1856) — so leeching a fraction of it is leeching what the
--- opponent actually lost.
---
--- ⛔ RETURNS NOTHING. A returned 1 cancels the damage AND stops the module
--- walk, which would leave c0rnp0rn8, endstats, live_events and
--- proximity_tracker without a single damage event. This hook only watches.
function et_Damage(target, attacker, damage, dflags, mod)
  if not active or not vamp_active then
    return
  end
  -- ⚠️ These are ENTITY numbers, not clientNums: attacker can be the world
  -- (1022), and target can be a mover or a missile. Both must be players, and
  -- the world must never heal anybody — including our own forced reset.
  if type(attacker) ~= "number" or type(target) ~= "number" then
    return
  end
  if attacker == target then
    return   -- self-damage heals nobody
  end
  -- ⚠️ The next test and the roster test below are MUTUALLY REDUNDANT for the
  -- world: remove either one and the other still stops entity 1022, which is
  -- why neither shows up as a surviving mutation on its own. Removing BOTH
  -- does break the harness, and that is the case that pins the behaviour. Both
  -- stay: this one keeps et.gentity_get away from non-client entities, the
  -- roster one keeps the heal inside the duel, and they would stop covering
  -- for each other the moment this mode grew past 1v1.
  if attacker >= MAX_CLIENTS or target >= MAX_CLIENTS then
    return
  end
  local roster = players_on_teams()
  if #roster ~= 2 then
    return
  end
  local in_duel = 0
  for _, cn in ipairs(roster) do
    if cn == attacker or cn == target then in_duel = in_duel + 1 end
  end
  if in_duel ~= 2 then
    return
  end

  local heal = math.floor((tonumber(damage) or 0) * steal_fraction())
  if heal <= 0 then
    return
  end
  local hp = et.gentity_get(attacker, "ps.stats", et.STAT_HEALTH)
  hp = tonumber(hp) or 0
  local capped = math.min(hp + heal, vamp_hp())
  if capped <= hp then
    return
  end
  et.gentity_set(attacker, "health", capped)
  et.gentity_set(attacker, "ps.stats", et.STAT_HEALTH, capped)
  log("STEAL   cn=%d dmg=%d heal=%d health=%d", attacker, damage, capped - hp, capped)
end

--- The switch a player can reach. Not everybody wants lifesteal, and in a 1v1
--- the agreement is two people, so this needs neither a vote nor an admin.
---
--- ⛔ Returns 1 ONLY for its own command. et_ClientCommand stops the module
--- walk on a returned 1 (tests/unit/test_lua_hook_return_contract.py), so
--- claiming anything else would swallow /say, /kill and every other command
--- the other modules read.
function et_ClientCommand(clientNum, command)
  if not active then
    return 0
  end
  local cmd = string.lower(et.trap_Argv(0))
  if cmd ~= "vampiric" and cmd ~= "vamp" then
    return 0
  end
  local want = not (vamp_pending == nil and vamp_active or vamp_pending)
  vamp_pending = want
  local state = want and "^2ON" or "^1OFF"
  local line = "^7vampiric " .. state .. " ^7— from the next spawn"
  et.trap_SendServerCommand(-1, 'cp "' .. line .. '\n"')
  et.trap_SendServerCommand(-1, 'chat "^7arena: ' .. line .. '"')
  log("VAMPREQ cn=%d want=%s", clientNum, tostring(want))
  return 1
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
  local cmd = string.lower(et.trap_Argv(0))
  -- The switch, reachable from the server console. Bots do not send custom
  -- client commands and a human cannot reach this box through ufw, so without
  -- this the /vampiric path could never be measured on a running server — only
  -- against a stub, which is exactly the kind of coverage that has been wrong
  -- three times in this module already.
  if cmd == "arena_vamp_toggle" then
    local want = not (vamp_pending == nil and vamp_active or vamp_pending)
    vamp_pending = want
    log("VAMPREQ console want=%s", tostring(want))
    et.G_Print(MODNAME .. ": vampiric " .. (want and "ON" or "OFF") ..
               " from the next spawn\n")
    return 1
  end
  if cmd ~= "arena_kill" then
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
