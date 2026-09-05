# Omni-bot files for the dots_arena training server

Two files, both installed **as user `et`**, neither of them enabled by copying
this directory anywhere. Read `docs/research/2026-09-05-BOTI-NA-DOTS-ARENA.md`
for the full reasoning; this is the install sheet.

⚠️ Everything here was read from the **v2.85.0** Omni-bot tree, because the
live server's own tree (`etlegacy-v2.83.1-x86_64`, which actually contains
v2.84.0) is `drwxr--r-- et:et` and unreadable to any other account. Compare
with `sha256sum` as `et` before relying on it.

## 1. `dots_arena.gm`

```
cp dots_arena.gm  <install>/legacy/omni-bot/et/nav/dots_arena.gm
```

Loads with no `.way` file — the DLL looks for `nav/<map>.gm` independently.
Sets per-bot skill 4 (not the install's default 6, which is a zero-error
aimbot), combat movement 3, no combat crouch, and adds the `ArenaStrafe` goal.

**Verify it loaded:** `rcon bot debug <botname> gamestate` or watch for the
bots actually travelling. If nothing changes, the map name is the check — the
file must be named exactly as the map is.

## 2. Class forcing (edit, not copy)

`et/scripts/et_botnames_ext.gm:27-68` maps each bot name to
`{ class=CLASS.X, weapon=N }`. For a symmetric SMG duel set every entry to
`CLASS.MEDIC` with `WEAPON.MP40` (Axis table) / `WEAPON.THOMPSON` (Allies).

⛔ Then create `et/scripts/et_autoexec_user.gm` (the DLL looks for this file and
it does not exist; it survives Omni-bot upgrades) containing:

```
global DisableClassManager = 1;
```

Without it, `goal_classmanager.gm:53-60` will `/kill` a bot and change its
class mid-session.

## Why not Lua

`sess.playerType` is writable but `g_client.c:3276-3281` overwrites it from
`sess.latchPlayerType` on every spawn. `latchPlayerType` is the writable one
that survives — but the DLL re-derives both weapons and forces a suicide when
it disagrees (`g_etbot_interface.cpp:2245-2267`). Our own weapon experiment
held for **2 duels out of 25**. Fix it in Omni-bot, not in Lua.

And a bot's **view** cannot be turned from Lua at all: `ps.delta_angles` is
absent from the entire gclient field table (`g_lua.c:1285-1362`), and
`PM_UpdateViewAngles` (`bg_pmove.c:4317-4335`) recomputes `ps.viewangles` from
it every pmove.
