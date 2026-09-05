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

WHICH SOURCE THE LINE NUMBERS BELOW REFER TO
--------------------------------------------
⛔ Every citation in this file was labelled "v2.85.0". That was wrong, and a
citation whose version label does not match the tree it was read from is a
citation nobody can re-check. Corrected, and stated once here:

  * source tree read:   v2.84.0-26-g732518ef
  * server it runs on:  ET Legacy v2.84.0  (etlded.x86_64, built 2026-05-18)

Those are 26 commits apart. Of the files cited here, only two differ across
that gap: g_lua.c (-3 lines, all after 1348, i.e. after every line cited here)
and g_client.c (-27 lines, hunks from 2091). So g_combat.c, g_active.c,
bg_pmove.c, bg_misc.c and msg.c citations are exact for the running binary,
g_lua.c citations are exact, and **g_client.c citations are given in the
running binary's numbering** (which is +18 from the tree).

VERIFIED AGAINST THIS SERVER'S BINARY (legacy/qagame.mp.x86_64.so, ET:L 2.84)
----------------------------------------------------------------------------
Read out of the module's own registration tables, not from memory:

  * Callbacks this module implements: et_InitGame, et_ShutdownGame, et_Quit,
    et_ClientDisconnect, et_Obituary, et_ClientSpawn, et_Damage,
    et_ClientCommand, et_ConsoleCommand.
    ⛔ This list used to be wrong in BOTH directions — it omitted et_Damage,
    which this very file implements, and named et_RunFrame, which it
    deliberately does not. It claimed to be "read out of the module's own
    registration tables"; it was not read out of anything. 2.84 also offers
    et_ClientConnect, et_ClientBegin, et_ClientUserinfoChanged, et_Print,
    et_Revive and et_WeaponFire, none of which this module wants.
  * There is NO Lua binding that kills or respawns a client. et.G_Damage is
    the only way to end a life from a script.
  * `health` IS exposed and IS writable — g_lua.c:1397, flags 0 — and the
    official Lua API docs say the same. This file used to claim the opposite
    while the module itself wrote the field; two statements in one file
    disagreeing is worse than either being wrong alone.
    ⭐ And `ent->health` is the REAL quantity: ps.stats[STAT_HEALTH] is
    re-derived from it every ClientEndFrame (g_active.c:2331), death is
    decided on ent->health (g_combat.c:1942), and the client HUD only ever
    sees STAT_HEALTH. Writing both, as this module does, is redundant but
    harmless; writing ONLY ps.stats would show the number for one frame and
    then snap back.
  * ⛔ `DAMAGE_*` and `ENTITYNUM_*` are NOT registered as et.* constants (zero
    matches in the module's constant table), so their values are written out
    below as numbers. DAMAGE_NO_PROTECTION = 0x20 comes from
    src/game/g_local.h; 1022 is ENTITYNUM_WORLD.
  * `PW_INVULNERABLE`, `PW_NOFATIGUE`, `STAT_HEALTH`, `TEAM_*`, `MOD_*` ARE
    registered (PW_NOFATIGUE at g_lua.c:2985), so those are read off et.*
    rather than hardcoded.
  * Array fields take an index: et.gentity_get(cn, "ps.powerups", idx) — the
    same call shape c0rnp0rn8.lua:984 already uses on this server.

WHAT THE POOL DOES NOT PROTECT AGAINST, AND WHAT QUIETLY EATS IT
----------------------------------------------------------------
⛔⛔ **A hit over 190 damage sets health to -176 regardless of the pool.**
g_combat.c:1931 is an UNCONDITIONAL assignment — it never looks at remaining
health:
    if (targ->s.number < MAX_CLIENTS && take > 190) { targ->health = GIB_HEALTH - 1; }
Good news: that is why LETHAL_DAMAGE = 1000 reliably kills at any pool. Bad
news: a duelist on 1000 HP is still one-shot by panzerfaust, dynamite, satchel
or mortar. Against those weapons the pool is worth nothing.

⛔⛔ **G_Damage is a silent no-op during warmup.** g_combat.c:1445 returns
early when `g_gamestate != GS_PLAYING && match_warmupDamage == 0`. The forced
reset then does not happen AND reports nothing — which reads exactly like "the
module is broken". Check gamestate before concluding anything.

⛔ **The engine bleeds surplus health at 1 HP per second** (g_active.c:941-943,
compared against ps.stats[STAT_MAX_HEALTH], which is ~100-140 and cannot be
raised past 156 by any supported field). Measured against the presets:
250 -> ~140 in 110 s, 500 -> 360 s, 1000 -> 860 s. At the 500 default and a
14 s duel that is ~14 HP, about 3%. Deliberately not fixed: the clean fix is
to re-assert STAT_MAX_HEALTH from et_RunFrame (which runs after
ClientEndFrame, g_main.c:4649 vs 4676), and that would give this module a
frame hook — too much machinery for 3%.
⚠️ Consequence that stays visible: the HUD health bar is scaled against
STAT_MAX_HEALTH, so a 500 HP duelist shows an overfull bar. Cosmetic.

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

  arena_hp 0|250|500|1000                the health both duelists spawn with.
                                         0 (default) leaves the engine alone.
                                         Only these three are accepted; any
                                         other number snaps to the nearest and
                                         says so, because the duel-length curve
                                         below only speaks for these points.
  arena_vamp 0|1                         lifesteal (default 0)
  arena_vamp_steal 50                    percent of damage healed back
  arena_ammo 1                           9999/9999 at spawn (default on)
  arena_nofatigue 1                      unlimited sprint (default on)

  In game:  /arenahp 250|500|1000|0      set the pool (takes effect next spawn)
            /vampiric [250|500|1000]     toggle lifesteal, optionally with pool
  Console:  arena_hp_set <n>, arena_vamp_toggle, arena_kill <cn>
                                         (need arena_1v1_test 1)

HOW LONG A DUEL LASTS (measured, local 2.84, two bots, 2026-09-04)
------------------------------------------------------------------
  250 HP -> median  6 s (n=13)
  500 HP -> median 14 s (n=7)
  1000 HP -> ONE duel in 120 s

250 was an interpolation when it was added; it is a reading now (2026-09-04,
local 2.84), and it landed where the interpolation said it would.

⛔ The 300 HP row (median 7 s, n=11) is gone from this table on purpose. It was
a real reading, but nearest_preset snaps 300 to 250, so no operator can ask for
it — a row in an operator-facing table that names an unreachable setting is a
lie about the interface, however true it is about the past.

⚠️ Every one of these points was measured with MIXED loadouts — Omni-bot picks
its own class and this module cannot make it stop (see arena_loadout below).
The numbers are consistent with each other because the same mess was present
at all four, but none of them is a mirrored-SMG duel.
With lifesteal the pool and the duel length are NOT proportional — the fight
is a race between two drains, so the curve bends. Pick the pool for the duel
length you want, not for the number that sounds generous.

The script only arms itself on a map whose name contains "dots_arena" AND when
exactly two players are on the two teams. Anything else — three players, a
spectator joining, another map — and it stands down without touching a thing.
------------------------------------------------------------------------------]]

local MODNAME  = "dots_arena_1v1"
local VERSION  = "1.1.0"

-- Not et.* constants on 2.84 (checked): write them as the numbers they are.
local ENTITYNUM_WORLD      = 1022
local MAX_CLIENTS          = 64    -- entity numbers below this are players
local WP_MP40              = 3     -- bg_public.h:848+ ; Axis SMG
local WP_THOMPSON          = 8     -- ; Allies SMG
local DAMAGE_NO_PROTECTION = 0x00000020  -- g_local.h:1669
local LETHAL_DAMAGE        = 1000        -- far past GIB_HEALTH from any health
local GIB_HEALTH           = -175        -- bg_public.h:58
local TAPOUT_HEALTH        = GIB_HEALTH - 25   -- comfortably past it, not on it

local active        = false   -- armed on this map?
local forced        = {}      -- clientNum -> true while OUR damage is in flight
--- Last shield expiry each player was handed, so a pair can be levelled.
--- ⛔ Declared up HERE, not next to the levelling code where it is used:
--- et_ClientDisconnect has to clear it, and a Lua function closes over the
--- locals that already exist when it is defined — a declaration further down
--- the file would have left the hook writing to a nil GLOBAL instead. That is
--- the same trap the withdrawn AMMO_FILL note records.
local spawn_shield  = {}
local saved_forcerespawn = nil
--- Set when a duelist leaves mid-duel. The player still standing keeps
--- whatever health he had, and nothing respawns him — so the re-levelling has
--- to wait until somebody joins and a duel exists again.
local relevel_pending    = false
local saved_arena_hp     = nil   -- what arena_hp was before anyone typed /arenahp
--- ⛔ Only true once THIS module has written the cvar. The first version of
--- the restore was unconditional, and the live run caught what that costs: an
--- admin who sets arena_hp at the console between two maps had it wiped by the
--- previous map's teardown. Restore what we changed; leave alone what we did
--- not.
local pool_typed         = false
--- Last time each client used one of the two arena commands.
--- ⛔ Keyed by clientNum, so et_ClientDisconnect must clear it — otherwise this
--- is a fresh instance of the very class this review exists to remove.
local last_cmd           = {}
local CMD_COOLDOWN_MS    = 3000
--- Whether the module last saw a real 1v1. Only used to announce TRANSITIONS,
--- so a three-player warm-up does not spam the chat every death.
local was_armed_pair     = false

local function cvar_num(name, fallback)
  local raw = et.trap_Cvar_Get(name)
  return tonumber(raw) or fallback
end

local function enabled()
  return cvar_num("arena_1v1", 1) ~= 0
end

--- ⛔⛔ The `mapname` CVAR, not the serverinfo configstring — and this is the
--- difference between a module that arms and one that never does.
---
--- Measured on the local 2.84 with a throwaway probe module, 2026-09-04:
---
---     fresh `map dots_arena`   CS_SERVERINFO length 0, mapname ""   -> NEVER ARMED
---     `map_restart 0`          CS_SERVERINFO length 743, mapname ok -> armed
---
--- The engine populates CS_SERVERINFO after GAME_INIT, so at et_InitGame on a
--- first map load it is EMPTY. The `mapname` cvar is already correct at that
--- point (the same probe read "dots_arena" from it while the configstring was
--- blank).
---
--- ⛔⛔ Everything measured before this fix was still real — but the mechanism
--- that made it work was an ACCIDENT. G_configSet issues a map_restart every
--- time it loads a config (g_config.c:500-508), and this dev server always had
--- g_customConfig set, so a restart always followed the map load and the
--- module armed on the second pass. On a server with no custom config there is
--- no restart, and the arena would have silently never armed — which is
--- exactly what a recipient of the shipped bundle would have got.
---
--- The configstring stays as a fallback: it is the correct source once the map
--- is up, and costs nothing when the cvar already answered.
local function map_name()
  local raw = et.trap_Cvar_Get("mapname")
  if raw == nil or raw == "" then
    local info = et.trap_GetConfigstring(et.CS_SERVERINFO)
    raw = et.Info_ValueForKey(info, "mapname") or ""
  end
  return raw:lower()
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
--- ⛔ 303 KB and 5311 lines after two days of testing, and the first line read
--- `03:56:59` with no date — two days interleaved in one file with no way to
--- separate them. Both halves of that are fixed here.
local LOG_MAX_BYTES        = 512 * 1024
local LOG_MAX_LINES_PER_MAP = 3000   -- house figure: frame_health v6.13
local log_writes            = 0

--- Rotate when the file is over the cap. ⭐ This is possible at all because
--- `et.trap_FS_Rename(old, new)` IS registered in 2.84 (g_lua.c:734, table
--- entry :2489) — the Lua FS layer is not append-only, which is the usual
--- assumption. Size comes from FS_READ, whose second return value is the file
--- length (files.c:5259); FS_APPEND returns 0/-1 and NOT a length, so the file
--- has to be probed with a separate read-open.
---
--- ⛔ `trap_FS_Rename` returns nothing at all — there is no success indication,
--- so this cannot verify itself. If it fails the log simply keeps growing,
--- which is the same failure we started from and never worse.
local function rotate_log_if_large()
  local fd, len = et.trap_FS_FOpenFile(LOG, et.FS_READ)
  if fd and fd ~= 0 and fd ~= -1 then
    et.trap_FS_FCloseFile(fd)
  end
  if type(len) == "number" and len > LOG_MAX_BYTES then
    et.trap_FS_Rename(LOG, "arena_1v1-" .. os.date("%Y-%m-%d-%H%M%S") .. ".log")
  end
end

local function log(fmt, ...)
  if cvar_num("arena_1v1_log", 1) == 0 then return end
  -- ⛔ One runaway map must not be able to fill a disk. The cap is per map
  -- load (log_writes is reset in et_InitGame), which is the house pattern from
  -- frame_health v6.13 — `max_lines_per_state = 3000`, and proximity records
  -- the measurement behind it: "300 cut a 2 h storm on 2026-09-02".
  if log_writes >= LOG_MAX_LINES_PER_MAP then return end
  -- ⛔ The DATE, not just the time. Everything else in this file is written so
  -- a reading can be re-checked later; a timestamp without a day is a reading
  -- you cannot place.
  local line = os.date("%Y-%m-%d %H:%M:%S ") .. string.format(fmt, ...) .. "\n"
  local fd, len = et.trap_FS_FOpenFile(LOG, et.FS_APPEND)
  if not fd or fd == -1 or fd == 0 or len == -1 then return end
  log_writes = log_writes + 1
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
--- ⛔⛔ ONE BOUNDARY, AND IT HAS TO BE MINE.
---
--- Seventeen bindings in g_lua.c build a `gentity_t*` as `g_entities + n`
--- straight from a Lua integer with NO range check — twelve of them without
--- even an `ent->client` guard — while `et.GetCurrentWeapon` (g_lua.c:1195)
--- DOES check. `et.gentity_set` on a FIELD_INT_ARRAY (g_lua.c:2184) is an
--- unbounded arbitrary-offset WRITE.
---
--- `arena_kill -1` was a server crash for exactly one reason: I read the
--- binding that validates, inferred a policy from it, and treated "checked"
--- as a property of the API rather than of that one function. The engine is
--- inconsistent here; the consistency has to come from this file.
local function max_clients()
  -- ⛔ The cvar is NOT trustworthy on its own. SV_BoundMaxClients clamps it to
  -- MAX_CLIENTS (sv_init.c:355-361) only when the server spawns, so between a
  -- `set sv_maxclients 9999` and the next map load the cvar reads 9999 while
  -- g_entities is still 1024 entries — and the loop below would walk straight
  -- off the end of it. Shape copied from proximity_tracker.lua:552-556.
  local n = cvar_num("sv_maxclients", MAX_CLIENTS)
  if n <= 0 or n > MAX_CLIENTS then n = MAX_CLIENTS end
  return n
end

--- ⛔ `math.type`, not a plain `type(cn) == "number"`. In Lua 5.4
--- `luaL_checkinteger` RAISES on a non-integral float ("number has no integer
--- representation") rather than truncating, and a raise inside a hook unwinds
--- the rest of it — half-applied state and one console line. The house helper
--- (proximity_tracker.lua:558-561) tests only `type(...) == "number"`, so 3.5
--- passes it and blows up one call later. Measured: tonumber("3") is an
--- integer, tonumber("3.0") and tonumber("1e999") are floats.
local function valid_client(cn)
  if math.type(cn) ~= "integer" then return false end
  return cn >= 0 and cn < max_clients()
end

local function players_on_teams()
  local out = {}
  for cn = 0, max_clients() - 1 do
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
  -- STAT_HEALTH is the reading, not the truth: it is re-derived from
  -- ent->health every ClientEndFrame (g_active.c:2331). For "is he alive"
  -- that distinction does not matter, because both are written together.
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
-- ⛔ This block used to compute a duel out of "MP40 and Thompson both do 18
-- damage every 150 ms = 120 dmg/s". That duel never happened. The bots in the
-- run those numbers came from played whatever class Omni-bot picked: from the
-- server's own userinfo, akimbo colt (506) and akimbo luger (500) led, then
-- Thompson (314), Kar98 (286), MP40 (266) and Carbine (242). A second and
-- independent route to the same conclusion -- damage per hit in this module's
-- own STEAL lines -- says the same thing: dmg=34 dominates (94 hits, a
-- bolt-action rifle) against dmg=18 (33, an SMG).
--
-- So the curve below is real but it is a MIXED-LOADOUT curve, not a mirrored
-- SMG one. The ratios between its three points should survive (the same mess
-- was present at all three), the arithmetic explaining them did not.
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
local duel_pool    = 0       -- the pool BOTH players actually spawned with

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
---
--- ⛔ ONE number, not two. The pool a duelist SPAWNS with and the ceiling
--- lifesteal heals up to are the same thing, and giving them separate cvars is
--- how "one name, two measurements" starts — you would be able to set a cap
--- above the health both players began the duel with, and the mode would look
--- like it was leaking health when it was only obeying a second setting.
local HP_PRESETS       = { 250, 500, 1000 }
local VAMP_FALLBACK_HP = 500
local hp_warned        = nil    -- the last bad value we complained about
--- ⛔ The cvar is the INTERFACE, not the storage. et.trap_Cvar_Set goes through
--- Cvar_Set2 with force = qtrue (g_lua.c:287-294 -> sv_game.c:454 ->
--- cvar.c:841), which creates arena_hp with flags 0 and bypasses every
--- latch/ROM/cheat rejection — so the write always lands. What it does NOT
--- survive is Cvar_Restart, which resets a flags-0 cvar to the FIRST value it
--- ever held (cvar.c:1552-1555), not the last. Keeping the number in Lua state
--- as well means an in-game change cannot be silently rolled back to whatever
--- the pool happened to be the first time somebody set it.
local pool_state       = nil    -- what a command asked for, this map

--- The preset closest to what was asked for. An unrecognised number is NOT
--- silently honoured: a typo would create a regime nobody has measured, and
--- the curve above only speaks for these three points.
local function nearest_preset(want)
  -- ⛔ `inf` and `nan` walk straight through the comparison below: every gap is
  -- `inf`, `inf < math.huge` is false for all three presets, so `best` keeps
  -- its initialiser and a nonsense pool silently becomes a VALID one — 250,
  -- indistinguishable from someone typing /arenahp 260. `nan` is worse still:
  -- every comparison with it is false. Reject them where they arrive.
  if want ~= want or want == math.huge or want == -math.huge or want < 0 then
    return nil
  end
  local best, best_gap = HP_PRESETS[1], math.huge
  for _, preset in ipairs(HP_PRESETS) do
    local gap = math.abs(preset - want)
    if gap < best_gap then
      best, best_gap = preset, gap
    end
  end
  return best
end

--- What a duel should start with, resolved from the settings.
---   arena_hp 0        -> do not touch health at all (the default, and exactly
---                        what the already-measured plain arena does)
---   arena_hp 250/500/1000 -> that pool, vampiric on or off
---   arena_hp unset, vampiric on -> 500, the measured middle
local function configured_pool()
  local want = pool_state or cvar_num("arena_hp", -1)
  if want == -1 then
    -- Compatibility with the cvar this started life as. Read only when the new
    -- name is absent, so nobody ends up with two settings disagreeing.
    want = cvar_num("arena_vamp_hp", -1)
  end
  if want == -1 or want == 0 then
    -- ⛔ Vampiric with no pool is a contradiction, and a dangerous one: the
    -- leech caps at this number, so 0 would cap every heal at zero — the mode
    -- would heal players to death. When lifesteal is on there is always a pool.
    return vamp_active and VAMP_FALLBACK_HP or 0
  end
  for _, preset in ipairs(HP_PRESETS) do
    if want == preset then return preset end
  end
  local snapped = nearest_preset(want)
  if snapped == nil then
    -- Not a number we can honour and not a number we can snap: fall back to
    -- the engine's own health rather than inventing a pool.
    if hp_warned ~= want then
      hp_warned = want
      log("HPWARN  arena_hp=%s is not a finite non-negative number -> ignored",
          tostring(want))
    end
    return vamp_active and VAMP_FALLBACK_HP or 0
  end
  if hp_warned ~= want then
    hp_warned = want
    -- ⛔ %s, not %d. cvar_num is tonumber, and tonumber("750.5") is a FLOAT;
    -- Lua 5.4 raises "number has no integer representation" on %d with one.
    -- Measured: 750.5 throws, 500.0 does not. A throw here would abort
    -- et_ClientSpawn three statements after the 1v1 gate, taking the ammo
    -- fill, the pool write and the whole shield-levelling loop with it —
    -- and exactly ONCE, because hp_warned is set on the line above before
    -- the throw. One duel with no shields, one console line, never again.
    log("HPWARN  arena_hp=%s is not a measured preset -> using %d", tostring(want), snapped)
    et.G_Print(MODNAME .. ": arena_hp " .. tostring(want) ..
               " is not one of 250/500/1000; using " .. snapped .. "\n")
  end
  return snapped
end

--- Apply a requested pool. The cvar IS the state — there is no second pending
--- variable, because et_ClientSpawn is the only place health is written and it
--- reads the cvar there. A change therefore cannot reach a duel in progress.
local function set_pool(want, cn)
  local applied = want
  if want ~= 0 then
    applied = nearest_preset(want)
    if applied == nil then
      log("POOL    cn=%s want=%s REFUSED (not finite / negative)",
          tostring(cn), tostring(want))
      return nil
    end
  end
  pool_state = applied
  pool_typed = true
  et.trap_Cvar_Set("arena_hp", tostring(applied))
  local shown = (applied == 0) and "engine default" or (applied .. " HP")
  local line = "^7arena pool ^3" .. shown .. " ^7— from the next spawn"
  et.trap_SendServerCommand(-1, 'chat "^7arena: ' .. line .. '"')
  log("POOL    cn=%s want=%s applied=%s", tostring(cn), tostring(want), tostring(applied))
  return applied
end
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
--- Push a dead-but-not-gibbed duellist past GIB_HEALTH so the engine limbos
--- him on its very next frame — the forced tap-out.
---
--- ⛔⛔ ROOT CAUSE, and it is OURS. The engine has exactly two routes out of
--- the wounded state (g_active.c:1592-1615), and this module closed both:
---
---   if (ucmd->upmove > 0) { ... limbo(...) }                        -- (a) the player jumps
---   if ((g_forcerespawn.integer > 0 && elapsed > g_forcerespawn*1000)
---       || client->ps.stats[STAT_HEALTH] <= GIB_HEALTH) { limbo(); } -- (b) timer OR gib
---
--- We set `g_forcerespawn -1` for instant respawn. That switches on the
--- instant-respawn branch at :1816 — but it makes `g_forcerespawn.integer > 0`
--- FALSE, so the timer half of (b) is dead code. And a normal MP40 kill (18
--- damage) leaves the loser at about -5, nowhere near -175, so the gib half of
--- (b) does not fire either. Only (a) is left: the loser lies there until HE
--- decides to press space.
---
--- The winner has no such choice. force_reset sends LETHAL_DAMAGE = 1000, the
--- engine clamps anything over 190 to health = GIB_HEALTH - 1 = -176
--- (g_combat.c:1931), (b) fires immediately, and he is respawned within two
--- frames. So the two players leave the round by different mechanisms with
--- different latencies, and the spawn shield — a hardcoded `level.time + 3000`
--- with no cvar (g_client.c:3327-3331) — is handed out at two different
--- moments. Whoever respawns LAST holds a shield the other one has already
--- spent. Owner saw it from the losing side: "on respawna in ze zgubi
--- spawnshield.. potem js space prtisnem da respawnam in mam spawnshield on ga
--- nima."
---
--- ⚠️ The shield-gap relevel below was written against this same fact and
--- treats the symptom: it notices two shields far apart and sends one player
--- back. This treats the cause, so the gap should stop occurring. The relevel
--- stays as the backstop for every route that does not pass through here
--- (revive, a mod that changes the wounded rules, a death we did not observe).
---
--- ⭐ Free bonus: limbo() computes `makeCorpse = makeCorpse && ent->health >
--- GIB_HEALTH` (g_client.c:886), so a tapped-out loser leaves NO corpse. A
--- corpse is unlinked from every bullet trace (G_TempTraceIgnoreBodies,
--- g_weapon.c:3551) while still being visible, which is one of the documented
--- reasons shots on a body register nothing at all.
local function force_tapout(cn)
  if cvar_num("arena_instant_tapout", 1) == 0 then return end
  -- ⛔ Write BOTH. The limbo trigger at g_active.c:1612 reads
  -- `client->ps.stats[STAT_HEALTH]`; limbo() itself reads the gentity's
  -- `ent->health` for the corpse decision. They are separate storage and
  -- G_Damage syncs one to the other only on its own way out (g_combat.c:2052),
  -- which does not happen for a value we set ourselves.
  et.gentity_set(cn, "ps.stats", et.STAT_HEALTH, TAPOUT_HEALTH)
  et.gentity_set(cn, "health", TAPOUT_HEALTH)
  log("TAPOUT  cn=%d health forced to %d (past GIB_HEALTH %d) — engine limbos next frame",
      cn, TAPOUT_HEALTH, GIB_HEALTH)
end

local function force_reset(cn, mod, why)
  -- ⛔ NO second bounds check here, deliberately. One belongs at the entry
  -- point (arena_kill), and the only other callers pass a clientNum that came
  -- from players_on_teams(), which max_clients() already bounds. A copy here
  -- would be unreachable — and this file's own standard is that a guard nobody
  -- can see fail is decoration, not a guard. It was written, its mutation
  -- survived because the entry-point check masks it, and it was removed.
  local hp, shield, selfkills = reading(cn)
  -- ⛔⛔ Never arm the latch on a path that cannot produce an obituary.
  -- G_Damage on a client already at health <= 0 takes the `!wasAlive` branch
  -- (g_combat.c:1946): it gibs, and it NEVER calls targ->die — so player_die
  -- never runs, G_LuaHook_Obituary never fires, and nothing clears
  -- forced[cn]. The `is_alive` check after the call then reads -176, concludes
  -- the damage landed, and leaves the flag set forever. That client's next
  -- REAL death is then swallowed: no point, no reset, no announcement, no log
  -- line. Reproduced by a review agent through the harness stub.
  if not is_alive(cn) then
    log("FORCE   cn=%d why=%s SKIPPED — already dead, no obituary would fire", cn, why)
    return
  end
  log("FORCE   cn=%d why=%s health=%d shield=%d selfkills=%d",
      cn, why, hp, shield, selfkills)
  forced[cn] = true
  et.gentity_set(cn, "ps.powerups", et.PW_INVULNERABLE, 0)
  et.G_Damage(cn, ENTITYNUM_WORLD, ENTITYNUM_WORLD, LETHAL_DAMAGE,
              DAMAGE_NO_PROTECTION, mod)

  -- ⛔⛔ G_Damage IS ALLOWED TO DO NOTHING, and it says nothing when it does.
  -- It returns early on !takedamage (g_combat.c:1435), on
  -- `intermissionQueued || (gamestate != GS_PLAYING && match_warmupDamage == 0)`
  -- (:1445), on noclip (:1593) and on FL_GODMODE (:1600) — the last two BEFORE
  -- dflags is ever read, so DAMAGE_NO_PROTECTION does not cover them.
  --
  -- Two things then rot, and both are silent. The flag latches, so this
  -- player's NEXT REAL DEATH is swallowed by the recursion guard — no point,
  -- no reset, no line. And his spawn shield has already been stripped one
  -- statement above, leaving him alive and unprotected: the precise
  -- unfairness this module exists to remove, produced by the module.
  --
  -- ⭐ Reading health HERE is sound even though reading it inside et_Obituary
  -- is not. G_Damage syncs ps.stats[STAT_HEALTH] from ent->health at
  -- g_combat.c:2052, on its way out — the 2..42 positive readings this file
  -- records elsewhere were taken from INSIDE the obituary, before that sync.
  if is_alive(cn) then
    forced[cn] = nil
    et.gentity_set(cn, "ps.powerups", et.PW_INVULNERABLE, shield)
    log("FORCE   cn=%d REFUSED by the engine — shield restored, flag cleared", cn)
  end
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
  -- ⛔ The pool has to go back to 0 with everything else. It did not, and the
  -- mutation battery is what found it: with the last map's pool still in the
  -- variable, a damage event on the new map — before anybody had spawned —
  -- was capped by a number from a duel that was over. Carrying state across a
  -- map change is the same defect the score reset above already fixes.
  duel_pool = 0
  relevel_pending = false
  was_armed_pair = false
  spawn_shield = {}
  pool_typed = false
  last_cmd = {}
  log_writes = 0
  rotate_log_if_large()
  -- A new map starts from the server's configuration, not from what somebody
  -- typed on the last one.
  pool_state = nil
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
  saved_arena_hp = et.trap_Cvar_Get("arena_hp")
  saved_forcerespawn = et.trap_Cvar_Get("g_forcerespawn")
  et.trap_Cvar_Set("g_forcerespawn", "-1")
  et.G_Print(MODNAME .. ": armed on " .. map_name() ..
             " (g_forcerespawn was '" .. tostring(saved_forcerespawn) .. "', now -1)\n")
end

--- Put g_forcerespawn back the way we found it. Idempotent: once restored the
--- saved value is dropped, so whichever teardown path runs first wins and the
--- second is a no-op.
local function restore_forcerespawn()
  if saved_forcerespawn ~= nil and saved_forcerespawn ~= "" then
    et.trap_Cvar_Set("g_forcerespawn", saved_forcerespawn)
  end
  -- ⛔ `arena_hp` too, and for a reason the old comment on `pool_state = nil`
  -- got backwards. That reset claimed "a new map starts from the server's
  -- configuration, not from what somebody typed on the last one" — but
  -- set_pool writes the CVAR as well, and configured_pool falls straight back
  -- to it, so clearing the Lua state only demoted the read one level onto the
  -- value the typing had already overwritten. Two players agreeing on
  -- /arenahp 1000 silently handed 1000 to the next pair. Restoring the cvar
  -- here is what makes the sentence true.
  if pool_typed and saved_arena_hp ~= nil then
    et.trap_Cvar_Set("arena_hp", saved_arena_hp)
  end
  pool_typed = false
  saved_arena_hp = nil
  saved_forcerespawn = nil
  active = false
end

function et_ShutdownGame(restart)
  restore_forcerespawn()
end

--- ⛔⛔ THE OTHER TEARDOWN, and the one that actually happens when somebody
--- votes a different config.
---
--- Changing lua_modules at runtime calls G_LuaShutdown() straight from the
--- cvar-change hook (g_cvars.c:907-913) — with NO matching G_LuaHook_
--- ShutdownGame. G_LuaShutdown walks the VMs into G_LuaStopVM, which calls
--- **et_Quit** and then lua_close (g_lua.c:3450-3468). et_ShutdownGame is only
--- ever reached through G_ShutdownGame (g_main.c:1903), and by the time that
--- runs the VM is already gone.
---
--- So without this hook, `callvote config legacy3` from inside the arena kills
--- the module and leaves g_forcerespawn at -1 — instant respawn for everyone,
--- on every map, until somebody notices. Checked on the production box: NOT
--- ONE of its ten configs sets g_forcerespawn, so nothing would have put it
--- back on its own.
function et_Quit()
  restore_forcerespawn()
end

--- ⛔⛔ LEAVING IS INVISIBLE WITHOUT THIS HOOK.
---
--- `ClientDisconnect` NEVER calls player_die (g_client.c:3526), so a duelist
--- who quits produces no obituary at all and the module simply does not learn
--- about it. The consequence is the module's one guarantee, off by a factor of
--- six: the survivor keeps whatever he had — 87 HP and no shield — while the
--- next player to join spawns with the full pool, full ammo and a fresh
--- shield. The engine's own rescue does not cover it either: G_verifyMatchState
--- only restarts when g_gamestate is PLAYING/WARMUP_COUNTDOWN and
--- g_doWarmup > 0, and an arena server sits in plain GS_WARMUP.
---
--- ⭐ The leaver STILL COUNTS here. The hook fires at g_client.c:3585 and
--- `pers.connected = CON_DISCONNECTED` is 138 lines later at :3723, so
--- players_on_teams() still returns two and the leaver has to be excluded by
--- hand rather than by the roster.
---
--- ⛔ And the re-levelling cannot happen now. Resetting the survivor while he
--- is alone would put him back at the engine's default health with no pool and
--- no ammo, because et_ClientSpawn bails on a roster of one — so he would be
--- the disadvantaged one instead. The flag waits for a duel to exist again.
function et_ClientDisconnect(clientNum)
  if not active then
    return
  end
  local roster = players_on_teams()
  local was_duelling = false
  if #roster == 2 then
    for _, cn in ipairs(roster) do
      if cn == clientNum then was_duelling = true end
    end
  end

  -- Slot numbers are recycled. Every table this module keys by clientNum stops
  -- describing a person the moment that person leaves, and the next connection
  -- to take the slot would inherit it — including the score.
  local was_scored = score[clientNum] ~= nil
  forced[clientNum]       = nil
  spawn_shield[clientNum] = nil
  score[clientNum]        = nil
  last_cmd[clientNum]     = nil

  -- ⛔ `score[cn] ~= nil` is exactly "was one of the two being scored" —
  -- ensure_pair populates that table for the duelists and nobody else. Testing
  -- the roster instead missed the case where a duelist leaves after the roster
  -- has already grown past two. `score_pair = nil` used to sit outside any
  -- gate, so ANY disconnect rebuilt the tally: a spectator could reset a 9-0
  -- series by pressing disconnect, and hold it at 0-0 by reconnecting on a
  -- loop, while the QUIT line said `duelling=false` as if he had been ignored.
  if was_scored then
    score_pair = nil
  end

  if was_duelling then
    relevel_pending = true
  elseif #roster == 1 and roster[1] == clientNum then
    -- ⛔⛔ The arena just emptied. Without this the flag armed by the FIRST
    -- player to leave survives an empty arena and fires on the first spawn of
    -- the next pair — a brand-new player is gibbed on arrival, takes a death
    -- he did not earn, and nothing in the log explains it. Reproduced by a
    -- review agent driving the harness stub, not by any case here.
    -- ⚠️ The `roster[1] == clientNum` term matters: a plain `= was_duelling`
    -- would clear a legitimately pending flag whenever a SPECTATOR left, since
    -- spectators are absent from the roster and never set `was_duelling`.
    relevel_pending = false
  end
  log("QUIT    cn=%d duelling=%s — state cleared", clientNum, tostring(was_duelling))
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
  -- ⛔ The weapon belongs on THIS line. Whether a forced loadout survives is a
  -- question about a moment seconds after the spawn, and the spawn line cannot
  -- answer it — an instrument that only reads at the moment of the write can
  -- never see the write being undone.
  -- ⛔ Ammo and stamina belong on THIS line too, and for the same reason: the
  -- spawn line is written at the moment of the write, so it can only ever say
  -- that the write happened — never that it survived. A duel's END is where
  -- "did the clip hold" and "did the sprint bar stay full" are answerable.
  local vic_wp, vic_ammo, vic_clip = et.GetCurrentWeapon(victim)
  local vic_sprint = et.gentity_get(victim, "ps.stats", et.STAT_SPRINTTIME)
  local vic_max = et.gentity_get(victim, "ps.stats", et.STAT_MAX_HEALTH)
  log("OBIT    victim=%d killer=%d mod=%d health=%d shield=%d selfkills=%d " ..
      "vicwp=%s ammo=%s clip=%s sprint=%s maxhp=%s",
      victim, killer, mod, vhp, vshield, vself, tostring(vic_wp),
      tostring(vic_ammo), tostring(vic_clip), tostring(vic_sprint), tostring(vic_max))

  if not enabled() then
    log("OFF     arena_1v1=0 — no reset, this is the control")
    return
  end

  -- ⛔⛔ LEAVING IS NOT DYING, and the engine makes it look exactly like it.
  --
  -- SetTeam kills you BEFORE it writes your new team: player_die(ent, ent,
  -- ent, 100000, MOD_SWITCHTEAM) at g_cmds.c:1589, sess.sessionTeam = team
  -- only at :1644 — 55 lines later. So when somebody types /team s in the
  -- middle of a duel, this hook runs while they are still on their old team,
  -- players_on_teams() still returns two, and without this guard the module
  -- would score a point for the opponent AND execute him. Pressing spectate
  -- was the strongest move in the game.
  --
  -- ⛔ Only MOD_SWITCHTEAM returns here. My first cut also returned on
  -- MOD_SUICIDE, and that BROKE /kill: the module would have done nothing at
  -- all, so the player who typed /kill would come back fresh while his
  -- opponent kept his leftover health — the exact unfairness this file exists
  -- to remove, reintroduced by the fix for a different bug. A self-inflicted
  -- death still deserves the reset; what it does not deserve is a POINT, and
  -- those are two different decisions (see `self_inflicted` below).
  if victim == killer and mod == et.MOD_SWITCHTEAM then
    -- ⛔ Leaving the roster by team change and leaving it by disconnect have
    -- IDENTICAL consequences for the player left standing: he keeps his
    -- leftover health while whoever arrives next spawns full. The guard above
    -- stopped "pressing spectate executes your opponent" and, on its own,
    -- replaced it with "pressing spectate is a free full heal" — /team s at
    -- 20 HP, /team r two seconds later, back at the pool with a shield the
    -- opponent no longer has. The flag is what closes it.
    relevel_pending = true
    log("LEAVE   cn=%d — team change, relevel armed", victim)
    return
  end

  local players = players_on_teams()
  if #players ~= 2 then
    log("SKIP    players=%d (not a 1v1)", #players)
    -- ⛔ Say it out loud, ONCE. Until now every roster change disarmed the
    -- module in total silence: the winner simply stopped being reset, there
    -- was no announcement, and the only evidence was a log line the players
    -- cannot read. A disarmed arena was indistinguishable from an armed one.
    if was_armed_pair then
      was_armed_pair = false
      -- ⛔ The roster leaving 2 is the third way a pair stops being levelled,
      -- and it is the quietest: a spectator taps a team button, the module
      -- pauses, the winner is no longer reset, and the loser respawns at the
      -- ENGINE's health with no pool and no ammo. Nothing used to put that
      -- right when the roster came back to 2.
      relevel_pending = true
      et.trap_SendServerCommand(-1, string.format(
        'chat "^7arena: ^3paused ^7— %d players on the teams, needs exactly 2"', #players))
    end
    return  -- not a 1v1 right now; leave the map alone
  end
  was_armed_pair = true

  -- ⛔⛔ EVERY death scores for the other player. /kill included.
  --
  -- I got this wrong twice today, in opposite directions, and the header had
  -- it right from the start: "a point goes to the OPPONENT of whoever died —
  -- including when a player kills themselves, which stops '/kill to deny the
  -- point' from being a tactic."
  --
  -- First I exempted `victim == killer`, reasoning that paying a point for
  -- /kill would make "kill yourself when you are behind" a tactic. That is
  -- backwards. If /kill is FREE it is a tactic: at 3 HP against a full-health
  -- opponent you type /kill, nobody scores, both reset, and you have escaped a
  -- duel you had already lost — every time, forever, while the scoreboard
  -- reads 0-0. If /kill COSTS you the point you were about to lose anyway,
  -- there is nothing to gain by typing it.
  --
  -- Then a second model pointed out the exemption also swallowed self-frags —
  -- your own grenade, panzerfaust or dynamite arrive with attacker == self and
  -- a weapon mod — so I narrowed it to MOD_SUICIDE. Correct as far as it went,
  -- but it left the /kill escape intact. The exemption is gone entirely.
  --
  -- ⚠️ The cost: a WINNER who types /kill out of the old manual habit now hands
  -- his opponent a point. That is visible, self-inflicted, and it stops being a
  -- habit after one duel — the module does the reset for him now. A loser's
  -- escape is deliberate and repeatable, which is the worse of the two.
  --
  -- Falling stays scored too, by a different route: MOD_FALLING arrives with
  -- killer = ENTITYNUM_WORLD, so it never looked self-inflicted in the first
  -- place. Two equivalent mistakes — died to the map, died to yourself — now
  -- score the same, which they did not before.
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

  -- ⭐ And the victim leaves by the same mechanism as the survivors, in the
  -- same frame. Before this line the survivors gibbed (LETHAL_DAMAGE) and the
  -- victim did not, so the two sides of one duel used two different exits with
  -- two different latencies — see force_tapout's header. Ordering matters: the
  -- survivors' force_reset must run FIRST, because force_reset refuses an
  -- already-dead target and this write makes the victim look freshly gibbed.
  force_tapout(victim)

  announce(players)
end

--- The spawn side of the reading. `levelTime` is not passed to this hook, so
--- the shield IS the clock: ClientSpawn sets it to level.time + 3000, so two
--- players that spawned in the same frame carry the same absolute number.
-- (declared next to `forced` near the top — see the note there.)

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
-- The retry lives further down, after AMMO_FILL is in scope. ⛔ Defining it
-- here would have referenced a GLOBAL AMMO_FILL (nil) rather than the local
-- declared below it — Lua closes over locals that already exist, not ones
-- that come later.

-- ── Ammo: unlimited, and why the number is 9999 and not 99999 ─────────────
--
-- A duel decided by who has to reload first is decided by the magazine, not by
-- movement or aim. So both duelists get a magazine and a reserve neither can
-- empty inside a duel.
--
-- ⛔ 99999 DOES NOT SURVIVE THE NETWORK, and this is invisible on the server.
-- ps.ammo and ps.ammoclip are delta-encoded with MSG_WriteShort/MSG_ReadShort
-- (qcommon/msg.c:2503, :2537, :2755, :2773) and MSG_ReadShort sign-extends 16
-- bits (`c = (short)MSG_ReadBits(msg, 16)`, msg.c:655). The server would go on
-- holding 99999 and every reading taken server-side would agree with itself,
-- while the client — and client-side prediction runs the SAME bg_pmove — would
-- receive (int16)99999 = -31073 and predict a player who cannot shoot.
-- MSG_WriteShort even carries a PARANOID range check for exactly this.
--
-- 9999 is the ceiling with room to spare, and it is the number abs1.3.lua was
-- already using. The margin matters for a second reason: PM_ReloadClip
-- (bg_pmove.c:2814-2828) computes `ammomove = maxClip - ammoclip`, which goes
-- NEGATIVE when the clip is over-full, so a manual reload MOVES AMMO BACKWARDS
-- — clip 9999 -> 30 and reserve 9999 -> 19968. That still fits in the field;
-- 99999 would not have, twice over.
--
-- 9999 rounds at the MP40's 150 ms cycle (bg_misc.c:164) is 1500 seconds of
-- held trigger. The longest duel ever measured here was 120 s.
--
-- ✅ MEASURED 2026-09-04 on the local 2.84: 9999/9999 at every one of ~100
-- spawns, and at the end of every duel the clip had dropped ONLY by the shots
-- fired (9999/9949 was the worst case). Nothing clamped it, nothing topped it
-- up, and no reload was ever needed.
-- ⚠️ The corpse hazard below did NOT fire in ~45 minutes of duels: the bots
-- kill each other in 4-6 s and do not walk over the weapons they drop. So it
-- stays a prediction derived from the source, not an observation -- which is
-- the honest status, not a clean bill of health.
--
-- Two more things a source sweep settled, both of which change how this is
-- allowed to be written:
--
-- ✅ NOTHING PERIODIC FIGHTS THE WRITE. An exhaustive grep of ps.ammo[ and
--    ps.ammoclip[ across the whole tree finds exactly two per-frame writers,
--    and neither is real ammo: ps.ammo[WP_ARTY] used as an airstrike bitfield
--    (g_active.c:1223-1231) and ps.ammo[WP_DUMMY_MG42] used as mounted-MG heat
--    (bg_pmove.c:5427). Every other writer is event-driven. maxAmmo/maxClip
--    are enforced ONLY on pickup (g_items.c:148-151) and reload
--    (bg_pmove.c:2500), never as a general clamp -- and the pickup guard
--    `ps->ammo[clip] < maxAmmo` (bg_misc.c:2651) is simply false at 9999.
--
-- ⚠️ ONCE PER SPAWN IS THE DESIGN, NOT A SHORTCUT. CG_PredictionOk
--    (cg_predict.c:902-910) returns a prediction error on ANY unpredicted ammo
--    change. Once per spawn is one resync and harmless; a per-frame top-up
--    would be a PERMANENT prediction failure. That is why this fills at spawn
--    and never on a timer.
--
-- ⛔ THE ONE REAL HAZARD IS CORPSES. dots_arena itself is clean -- its BSP
--    entity lump has no item_health*, ammo_* or weapon_* at all, only spawns,
--    objectives and lights -- so the medpack clamp that would cut health back
--    to STAT_MAX_HEALTH (g_items.c:601-603) cannot fire here. But a dying
--    player DROPS his primary weapon (G_DropWeapon from player_die,
--    g_combat.c:194), and picking one up runs Fill_Clip -> AddToClip
--    (g_items.c:67-95) where `ammomove = maxclip - inclip` is NEGATIVE at
--    9999: the clip moves DOWN toward 30 and the reserve moves UP. Not fatal
--    -- reloading from a ~19968 reserve works fine -- but "never has to
--    reload" degrades to "reloads sometimes" for whoever walks over a corpse.
--
-- ⚠️ 9999 DOES overflow two spectator relays: the shoutcast overlay ships ammo
--    in 10 bits (bg_ebs.h:63-64, written g_team.c:2492-2493) and multiview in
--    9-11 (g_multiview.c:490-499), so 9999 shows up there as 783. Affects
--    shoutcasters and multiview spectators only, never the duelists.
local AMMO_FILL = 9999

--- Top up whatever the player is actually holding. Deliberately NOT weapon
--- forcing — that was tried, measured and withdrawn (see above). This asks the
--- engine what the weapon is and refills that.
---
--- et.AddWeaponToPlayer is the right call rather than writing ps.ammo
--- directly: the array is indexed by the weapon table's ammoIndex/clipIndex,
--- not by the weapon number (g_lua.c:1110-1112), and that mapping is not
--- exposed to Lua. For the SMGs the two happen to be equal (bg_misc.c:164,
--- :169), which is exactly the kind of coincidence that makes a hardcoded
--- index look right until somebody duels with a pistol.
local function arena_ammo(cn)
  if cvar_num("arena_ammo", 1) == 0 then return end
  local weapon = et.GetCurrentWeapon(cn)
  -- WP_NONE would make AddWeaponToPlayer raise a Lua error (IS_VALID_WEAPON,
  -- g_lua.c:1104), and an error raised inside et_ClientSpawn takes the rest of
  -- the spawn handling with it — including the shield levelling.
  if type(weapon) ~= "number" or weapon <= 0 then
    log("AMMO    cn=%d skipped weapon=%s", cn, tostring(weapon))
    return
  end
  -- setcurrent = 0: fill the weapon, never switch it. ps.weapon is read-only
  -- to Lua (g_lua.c:1289) so AddWeaponToPlayer is the ONLY way to change the
  -- held weapon, and we are deliberately not doing that.
  local ok, err = pcall(et.AddWeaponToPlayer, cn, weapon, AMMO_FILL, AMMO_FILL, 0)
  if not ok then
    -- ⛔ NOT a silent pcall. The last time a pcall wrapped this area it
    -- swallowed whatever the binding was saying and the loadout feature was
    -- debugged blind for an hour.
    log("AMMO    cn=%d weapon=%d FAILED %s", cn, weapon, tostring(err))
    et.G_Print(MODNAME .. ": ammo fill failed: " .. tostring(err) .. "\n")
    return
  end
  local _, ammo, clip = et.GetCurrentWeapon(cn)
  log("AMMO    cn=%d weapon=%d ammo=%s clip=%s", cn, weapon, tostring(ammo), tostring(clip))
end

--- Unlimited sprint. A strafe duel in which one player runs out of stamina
--- mid-circle is decided by the stamina bar, which is the same complaint as
--- the magazine. PW_NOFATIGUE is one of the powerups ClientEndFrame explicitly
--- never expires (g_active.c:2222-2227), so it is set once per spawn and stays.
---
--- ⚠️ My addition, not asked for — abs1.3.lua sets it and a movement-decided
--- duel wants it. `arena_nofatigue 0` turns it off.
local function arena_nofatigue(cn)
  if cvar_num("arena_nofatigue", 1) == 0 then return end
  -- The literal 1 is correct and not a timestamp. Both readers are truthiness
  -- tests inside PM_Sprint (bg_pmove.c:4973, :4999) and nothing anywhere reads
  -- the VALUE — the engine's own /nofatigue cheat writes FL_NOFATIGUE = 65536
  -- (g_cmds.c:1090), which would be nonsense as a level.time expiry.
  et.gentity_set(cn, "ps.powerups", et.PW_NOFATIGUE, 1)
end

--- ⚠️ Side effect nobody asked for, found while checking what the powerup
--- actually does: a jump deducts 2500 from sprintTime (bg_pmove.c:1341) and
--- PM_Sprint puts it straight back, so this also grants UNLIMITED JUMPING.
--- For a strafe duel that is probably wanted, but it was not the request, so
--- it is written down rather than discovered later.

--- ⛔ Weapon forcing, ATTEMPT TWO. The first attempt removed 54 weapons per
--- spawn, produced a ClientUserinfoChanged storm at ~1 Hz and stopped the bots
--- fighting; it was withdrawn. This one only ADDS, which the source says is a
--- different path entirely: Bot_Event_AddWeapon (g_etbot_interface.cpp:6310)
--- is fire-and-forget into the Omni-bot DLL, writes nothing to the playerState
--- and never calls ClientUserinfoChanged — unlike the Remove path.
---
--- ⛔ One exception the source names: for Garand, K43, FG42 and their _SCOPE
--- variants, Bot_Event_AddWeapon itself ALSO emits MESSAGE_REMOVEWEAPON
--- (g_etbot_interface.cpp:6317-6382) — the very message class that caused the
--- storm. MP40 and Thompson are not in that set, which is why this is limited
--- to the two SMGs and not generalised.
---
--- setcurrent = 1 here (unlike arena_ammo) precisely because ps.weapon is
--- read-only to Lua (g_lua.c:1289): this binding is the only way to select a
--- weapon at all.
---
--- ⛔⛔ MEASURED, 2026-09-04, local 2.84, and the answer is: THE WRITE LANDS,
--- THE WEAPON DOES NOT STAY. 50 forced loadouts in one three-minute window;
--- every one confirmed by reading the weapon back immediately (`now=` equals
--- `want=` on all 50), and at the end of those duels the victim was holding
--- the forced weapon in 2 of 25 obituaries. Omni-bot re-picks its class
--- weapon within seconds and this module has no way to argue.
---
--- ⚠️ It DOES cost userinfo traffic, and the first version of this note said
--- otherwise. ClientUserinfoChanged, three windows:
---
---     1.76/s   forcing off (contaminated: forcing came on mid-window)
---     1.53/s   forcing ON, 180 s clean
---     1.03/s   forcing off, 95 s clean control
---
--- The clean pair is 1.53 against 1.03 — forcing runs about **1.5x baseline**,
--- roughly 1.8 extra userinfo changes per forced loadout. AddWeaponToPlayer
--- itself never calls ClientUserinfoChanged (checked in
--- g_etbot_interface.cpp), so the extra traffic is the BOT answering: it
--- re-selects its own weapon, and re-selection goes through Cmd_Team_f /
--- G_SetClientWeapons, which do call it (g_cmds.c:2358, :2034).
---
--- ⛔ I wrote "1.52/s in the control" from a partial reading taken 50 s into
--- that window and committed it before the window closed. The finished
--- control said 1.03. A rate read off an unfinished window is not a rate.
---
--- ⭐ What is still true, and is the whole difference from attempt one: this
--- is EXTRA TRAFFIC, not a storm, and nothing breaks. Duels kept their cadence
--- (median 6 s with forcing on, 7 s in the control) instead of collapsing to
--- one obituary in two minutes. So this is not withdrawn a second time — but
--- it is not free either, and on a busy server that cost is worth knowing.
---
--- ⭐ And it is only visible at all because the reading was moved to the
--- OBITUARY line. `now=` is taken one instruction after the write, so it can
--- only ever report that the write happened -- exactly the mistake the first
--- attempt made. An instrument that reads at the moment of the write can
--- never see the write being undone.
---
--- Default OFF: useful for humans, ineffective against bots, and the curve it
--- was meant to produce (mirrored SMGs) is therefore still not measurable
--- with bots.
local function arena_loadout(cn)
  if cvar_num("arena_symmetric", 0) == 0 then return end
  local team = et.gentity_get(cn, "sess.sessionTeam")
  local want
  if team == et.TEAM_AXIS then
    want = WP_MP40
  elseif team == et.TEAM_ALLIES then
    want = WP_THOMPSON
  else
    return
  end
  local ok, err = pcall(et.AddWeaponToPlayer, cn, want, AMMO_FILL, AMMO_FILL, 1)
  if not ok then
    log("LOADOUT cn=%d want=%d FAILED %s", cn, want, tostring(err))
    return
  end
  local now = et.GetCurrentWeapon(cn)
  log("LOADOUT cn=%d want=%d now=%s", cn, want, tostring(now))
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
  -- `powerups[PW_INVULNERABLE] = level.time + 3000` (g_client.c:3349) and this
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
    if was_armed_pair then
      was_armed_pair = false
      relevel_pending = true
      et.trap_SendServerCommand(-1, string.format(
        'chat "^7arena: ^3paused ^7— %d players on the teams, needs exactly 2"', #roster))
    end
    return
  end
  if not was_armed_pair then
    was_armed_pair = true
    et.trap_SendServerCommand(-1, 'chat "^7arena: ^2armed ^7— 1v1"')
  end
  -- The switch takes effect HERE and nowhere else: flipping vampiric in the
  -- middle of a duel would hand one player a pool the other never had. The
  -- request waits until both are fresh, which is this moment.
  if vamp_pending ~= nil then
    vamp_active = vamp_pending
    vamp_pending = nil
    log("VAMP    now %s", tostring(vamp_active))
  end
  -- ⛔ The other half of the disconnect fix. A duel exists again, and the
  -- player who never died still carries the leftover health from the duel his
  -- opponent walked out of. Send him through the same door the module uses
  -- after a kill, so both come back together.
  --
  -- ⛔⛔ This is deliberately gated on the flag and NOT a blanket "reset
  -- whoever is alive". After a normal kill both players are dead when the
  -- first one spawns, but the SECOND spawn would find the first one alive —
  -- and a blanket rule would reset him, which resets the other, forever.
  if relevel_pending then
    relevel_pending = false
    for _, other in ipairs(roster) do
      if other ~= clientNum and is_alive(other) then
        log("RELEVEL cn=%d — opponent had left mid-duel", other)
        force_reset(other, et.MOD_SUICIDE, "opponent-left")
      end
    end
  end

  duel_started = et.trap_Milliseconds()
  -- ⛔ Snapshot, not a live read. The cap lifesteal heals up to has to be the
  -- pool both players ACTUALLY spawned with: reading the cvar again from the
  -- damage path meant that raising arena_hp mid-duel lifted the ceiling above
  -- the health either player started with, and the mode looked like it was
  -- inventing health when it was only obeying a setting that had moved.
  duel_pool = configured_pool()
  arena_ammo(clientNum)
  arena_nofatigue(clientNum)
  if duel_pool > 0 then
    et.gentity_set(clientNum, "health", duel_pool)
    et.gentity_set(clientNum, "ps.stats", et.STAT_HEALTH, duel_pool)
    arena_loadout(clientNum)
    -- ⛔ The SPAWN line above was written BEFORE this, so it reports the
    -- engine's 100 and not the pool a vampiric duel actually starts with. It
    -- read like the mode was not applying at all (live run, 2026-09-04) while
    -- the STEAL lines showed health climbing to exactly the configured cap.
    -- An instrument that logs before the action measures the wrong moment.
    log("VAMPHP  cn=%d health=%d vamp=%s", clientNum, duel_pool, tostring(vamp_active))
  end

  for _, other in ipairs(roster) do
    if other ~= clientNum then
      local theirs = spawn_shield[other]
      -- ⛔⛔ A gap WIDER than the window is the dangerous case, not the safe
      -- one. The loser does not gib — LETHAL_DAMAGE gibs only the winner — so
      -- he is never forced into limbo, and with g_forcerespawn -1 the timer
      -- route is gone too. He can lie on the floor as long as he likes, watch
      -- where the winner spawned, and then jump: a fresh 3-second shield
      -- against an opponent whose shield expired seconds ago. Silently
      -- skipping the levelling handed that to him.
      if theirs and theirs > 0 and shield > 0 and math.abs(shield - theirs) > 1000
         and is_alive(other) then
        -- ⛔ Act NOW, not on a flag. The relevel flag is consumed earlier in
        -- this same hook, so setting it here would defer the fix to the NEXT
        -- spawn — which is the spawn after the one that already handed out the
        -- unmatched shield. (Written as a flag first; the test caught it.)
        log("REGAP   cn=%d cn=%d shields %d apart — sending the other one back",
            clientNum, other, math.abs(shield - theirs))
        force_reset(other, et.MOD_SUICIDE, "shield-gap")
      end
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
  -- Defence in depth for the same reason: a zero cap here is lethal, and this
  -- line is reached from the damage path where a mistake is a dead player
  -- rather than a wrong log line.
  local cap = duel_pool > 0 and duel_pool or VAMP_FALLBACK_HP
  local capped = math.min(hp + heal, cap)
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
  if cmd ~= "arenahp" and cmd ~= "arena_hp"
     and cmd ~= "vampiric" and cmd ~= "vamp" then
    return 0
  end

  -- ⛔⛔ THE ENGINE WILL NOT DO THIS FOR US. ClientCommand runs the Lua hook
  -- FIRST (g_cmds.c:5240) and only reaches G_commandCheck — where
  -- G_ClientIsFlooding lives (g_cmds_ext.c:233) — if no module claimed the
  -- command. A command this module handles therefore never touches flood
  -- protection at all, and none of the engine's rate-limit state
  -- (sess.nextReliableTime, sess.numReliableCommands, pers.cmd_debounce) is
  -- exposed to Lua. Both gates below have to be ours.
  local team = et.gentity_get(clientNum, "sess.sessionTeam")
  if team ~= et.TEAM_AXIS and team ~= et.TEAM_ALLIES then
    et.trap_SendServerCommand(clientNum,
      'print "^7arena: only the two players in the duel can change the mode\n"')
    return 1
  end

  local now = et.trap_Milliseconds()
  local prev = last_cmd[clientNum]
  -- ⚠️ trap_Milliseconds is Sys_Milliseconds as a C int and wraps after ~24.8
  -- days of uptime; `now < prev` after a wrap would lock a player out forever,
  -- so a backwards jump resets the timer instead of trapping on it.
  if prev ~= nil and now >= prev and now - prev < CMD_COOLDOWN_MS then
    et.trap_SendServerCommand(clientNum,
      'print "^7arena: slow down — one change every 3 seconds\n"')
    return 1
  end

  -- ⛔ The charge happens where the STATE CHANGES, not here. Writing it at this
  -- point billed the player for a read-only `/arenahp` with no argument — the
  -- usage line — and then refused the command he actually wanted 100 ms later.
  -- Two people agreeing on a pool had to discover that asking costs three
  -- seconds. Reproduced by a review agent.
  local function charge()
    last_cmd[clientNum] = now
  end

  -- The pool, without touching lifesteal. 250 / 500 / 1000 are the measured
  -- points; 0 hands health back to the engine. It lands at the next spawn for
  -- the same reason the switch does — changing the pool mid-duel would give
  -- one player a number the other never had.
  if cmd == "arenahp" or cmd == "arena_hp" then
    local want = tonumber(et.trap_Argv(1))
    if want == nil then
      et.trap_SendServerCommand(clientNum,
        'print "^7arena: usage: /arenahp 250|500|1000|0 (now: ' .. configured_pool() .. ')\n"')
      return 1
    end
    charge()
    set_pool(want, clientNum)
    return 1
  end
  if cmd ~= "vampiric" and cmd ~= "vamp" then
    return 0
  end
  -- /vampiric 250 turns lifesteal on AND sets the pool in one command, which
  -- is how it will actually be typed between two people agreeing on a duel.
  -- ⛔ `/vampiric 0` used to turn lifesteal ON. `tonumber("0")` is not nil, so
  -- it took the "on, with a pool" branch, and the only line the player saw was
  -- about the POOL — the vampiric announcement lives past that branch's return.
  -- Worse, configured_pool maps a 0 pool under vamp_active to the 500 fallback,
  -- so the most natural spelling of "turn it off" enabled it AND handed out
  -- 500 HP, silently. 0 now falls through to the toggle below, which announces.
  local pool_arg = tonumber(et.trap_Argv(1))
  -- ⛔ 0 means OFF, explicitly — not "toggle". Falling through to the toggle
  -- was my first fix and it still turned lifesteal ON when it happened to be
  -- off, which is the same defect with a different path.
  if pool_arg == 0 then
    charge()
    vamp_pending = false
    local off = "^7vampiric ^1OFF ^7— from the next spawn"
    et.trap_SendServerCommand(-1, 'cp "' .. off .. '\n"')
    et.trap_SendServerCommand(-1, 'chat "^7arena: ' .. off .. '"')
    log("VAMPREQ cn=%d want=false (explicit 0)", clientNum)
    return 1
  end
  if pool_arg ~= nil then
    charge()
    vamp_pending = true
    set_pool(pool_arg, clientNum)
    log("VAMPREQ cn=%d want=true pool=%s", clientNum, tostring(pool_arg))
    return 1
  end
  charge()
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
  if cmd == "arena_hp_set" then
    local want = tonumber(et.trap_Argv(1))
    if want == nil then
      et.G_Print(MODNAME .. ": usage: arena_hp_set <250|500|1000|0>\n")
      return 1
    end
    local applied = set_pool(want, nil)
    if applied == nil then
      -- ⛔ set_pool now refuses inf/nan/negative, and this line used to
      -- concatenate its return value straight into a string — a nil there
      -- would have thrown inside the console handler, i.e. the refusal path
      -- would itself have been a defect.
      et.G_Print(MODNAME .. ": refused " .. tostring(want) ..
                 " (needs a finite value: 0, 250, 500 or 1000)\n")
      return 1
    end
    et.G_Print(MODNAME .. ": pool " .. applied .. " from the next spawn\n")
    return 1
  end
  if cmd ~= "arena_kill" then
    return 0
  end
  -- ⛔⛔ THIS is where the crash was. `tonumber` accepts -1, 5000 and 3.5, and
  -- et.G_Damage hands all three to `g_entities + n` unchecked (g_lua.c:918).
  -- A negative or oversized index is an out-of-bounds read AND, one line
  -- earlier in force_reset, an out-of-bounds WRITE through gentity_set.
  local cn = tonumber(et.trap_Argv(1))
  if not valid_client(cn) then
    et.G_Print(MODNAME .. ": usage: arena_kill <clientnum 0.." ..
               (max_clients() - 1) .. ">, got " .. tostring(et.trap_Argv(1)) .. "\n")
    return 1
  end
  log("TESTCMD arena_kill cn=%s", tostring(cn))
  force_reset(cn, et.MOD_SUICIDE, "test-command")
  return 1
end
