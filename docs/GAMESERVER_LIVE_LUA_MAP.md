# Game Server Live Lua Map

Created: 2026-03-07

Purpose:
- Record the Lua files currently running on `puran.hehe.si`
- Keep a stable reference for repo sync decisions
- Avoid rediscovering the live module set from server logs every time

## Live Server

- Host: `puran.hehe.si`
- SSH: `et@91.185.207.163:48101`
- ET root: `/home/et/etlegacy-v2.83.1-x86_64`
- Game dir: `/home/et/etlegacy-v2.83.1-x86_64/legacy`
- Lua dir: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts`
- Runtime log: `/home/et/.etlegacy/legacy/etconsole.log`

## Active Server Start

The live process is started with:

```bash
/home/et/etlegacy-v2.83.1-x86_64/etlded.x86_64 +exec vektor.cfg
```

The config file is:

- `/home/et/etlegacy-v2.83.1-x86_64/etmain/vektor.cfg`

## Live Lua Modules

The actual loaded modules are confirmed by `etconsole.log`, not just by static cfg files.

Active modules:

- `luascripts/team-lock.lua`
- `c0rnp0rn8.lua`
- `endstats.lua`
- `luascripts/proximity_tracker.lua`
- `luascripts/stats_discord_webhook.lua`
- `luascripts/live_events.lua`

In `lua_modules` order, which is the order the hooks are dispatched in — see
the dispatch table below. All six lists in this document describe the same six
modules; if one of them is short, it is stale.

## Hook dispatch: one module can starve the ones behind it

ET:Legacy calls a hook on every loaded module in `lua_modules` order, but some
hooks stop the walk when a module returns. Which value stops it differs per
hook, and that difference has already cost us a shipped feature:

| group | hooks | what stops the walk |
|---|---|---|
| **any value** | `et_Obituary`, `et_ClientConnect` | `lua_isstring(L,-1)` — true for **numbers too**, so even `return 0` stops it |
| one number | `et_ClientCommand`, `et_ConsoleCommand`, `et_Damage`, `et_Revive`, `et_WeaponFire`, `et_*Fire` (`==1`); `et_SetPlayerSkill`, `et_UpgradeSkill` (`==-1`) | only that exact number; `return 0` is safe |
| never | `et_InitGame`, `et_ShutdownGame`, `et_RunFrame`, `et_ClientBegin`, `et_ClientSpawn`, `et_ClientDisconnect`, `et_ClientUserinfoChanged`, `et_Print`, `et_IPCReceive` | return value ignored |

**What this cost us**: `stats_discord_webhook.lua` ended its `et_Obituary` with
`return 0` and loads before `live_events.lua`, so live_events received **zero**
obituaries from the day it shipped (2026-08-12). The Live page's K/D columns and
alive dots were dead for eight days while damage and DPM kept working — which is
precisely why it looked healthy. Measured on the local server 2026-08-20 with the
module order unchanged: 28 engine kills → 0 `K` lines before the fix, 14 → 14
after. `tests/unit/test_lua_hook_return_contract.py` now fails the build if any
of our modules returns a value from `et_Obituary`.

## Important Mismatch

Static config and live runtime do not fully agree.

- `/home/et/etlegacy-v2.83.1-x86_64/etmain/legacy.cfg` still contains:
  - `set lua_modules "luascripts/team-lock c0rnp0rn7.lua endstats.lua luascripts/stats_discord_webhook.lua"`
- But live `etconsole.log` shows (verified on puran 2026-08-20 — note that
  `live_events.lua` joined the list on 2026-08-12 and this doc did not):
  - `setl lua_modules "luascripts/team-lock.lua c0rnp0rn8.lua endstats.lua luascripts/proximity_tracker.lua luascripts/stats_discord_webhook.lua luascripts/live_events.lua"`
  - The order is not cosmetic — see the dispatch table above.

Rule:
- Treat `etconsole.log` as the source of truth for what is actually loaded.

## Live File Paths

- `c0rnp0rn8.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/c0rnp0rn8.lua`
- `endstats.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/endstats.lua`
- `stats_discord_webhook.lua` — ⚠️ **two copies exist; the homepath one runs**
  - `/home/et/.etlegacy/legacy/luascripts/stats_discord_webhook.lua` ← **live**
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua` (ignored)
  - `fs_homepath` overrides `fs_basepath` for module loading. Both files were
    present on puran on 2026-08-20 (verified). Deploying a fix to the basepath
    copy changes nothing and looks exactly like a fix that did not work.
- `proximity_tracker.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/proximity_tracker.lua`
- `team-lock.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/team-lock.lua`
- `live_events.lua`
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/live_events.lua`

## Repo Mapping

Keep these mirrored locally:

- Proximity:
  - [proximity_tracker.lua](/proximity/lua/proximity_tracker.lua)
- Non-proximity game-server scripts:
  - [c0rnp0rn8.lua](/vps_scripts/c0rnp0rn8.lua)
  - [endstats.lua](/vps_scripts/endstats.lua)
  - [stats_discord_webhook.lua](/vps_scripts/stats_discord_webhook.lua)
  - [team-lock.lua](/vps_scripts/team-lock.lua)
  - [live_events.lua](/vps_scripts/live_events.lua)

## Hashes Captured On 2026-03-11

- `c0rnp0rn8.lua`
  - `ec919bfa065f552ad6e0fffda9a784e359f960fd698079033887706139ac08b3`
- `endstats.lua`
  - `fd18f765a8df65c51a153dd601a396256478e95e9d82451b0fb98c9f69b36561`
- `stats_discord_webhook.lua`
  - `06d669aa6c7dd34922bf2817f573662b73cbccb59099c0fce86fbbe33cd0258f`
- `team-lock.lua`
  - `7b0e6c11b1d64195852446d6a9c276917e2a4194988f3f0787777a8af091c7c1`
- `proximity_tracker.lua`
  - `1a32a3a6eb9ba9d138d7b7a10c648abbe6150387832df924d3241299214b4984` (v5.0 — upgraded from v4.2 `85bb9cf0` on 2026-03-11)

## Practical Rule

When syncing or auditing game-server Lua:

1. Check live `etconsole.log`
2. Confirm loaded file paths
3. Pull current remote copies
4. Mirror non-proximity scripts into `vps_scripts/`
5. Mirror proximity only into `proximity/lua/`

## Tracker v6.14 (2026-09-05) — when the mover moved, and who took it down

`proximity_tracker.lua` only (the frame-health block is unchanged and still
byte-identical across the six modules). Two additions, both under the
existing `vehicle_tracking` flag (docs/design/20 slice 2):

- `# VEHICLE_PROGRESS` rows carry four trailing fields, `first_move_time;
  last_move_time;first_escort_time;last_escort_time` — `gameTime()` ms since
  round start (the carrier `kill_time` base), `0` = never. Move = the mover's
  own motion (a supply truck drives itself off the line at ~0.6 s); escort =
  motion with a player mounted or within `escort_radius`, i.e. when the
  escort happened — the moment's timestamp. The parser keeps its 12-field
  floor, so pre-v6.14 files still import; migration 082 adds the columns.
- `# VEHICLE_DESTROYED` — one row per destruction of a tracked mover:
  `vehicle_name;time;attacker_guid;attacker_name;attacker_team;means_of_death;
  health_before`. Source: a branch at the top of `et_Damage`, BEFORE the
  `isValidClient(target)` line that used to reject every non-client target.
  The engine's hook (`g_combat.c:1857`) fires for every damaged entity, and
  by then the engine has already subtracted the damage, so "dead now" is
  read from the entity and "health before" from the 500 ms poll's cache.
  An empty attacker means the poll saw the death without a hit (script
  kill, sub-threshold damage). Its per-frame cost shows up in the FM line as
  the `vehdmg` section.

## Frame-health v6.13 (2026-09-03) — the watchdog in every module

Every module above carries the same `-- BEGIN frame_health v6.13 … END`
block (pinned byte-identical by `tests/unit/test_lua_frame_health_block_identical.py`)
and a hook that wraps its own `et_RunFrame`. All six append to the ONE file
the tracker's gap watcher writes, `~/.etlegacy/legacy/proximity/frame_health.log`
(trap_FS paths are homepath-relative, so no per-module plumbing):

- `FH init wall=<ms> version=6.13 mod=<name>` — one per module per map load
  (a module whose line is missing after a map load did not load the new file);
- `FH watcher wall=<ms> version=<v>` — the tracker's gap watcher proving its own path;
- `FH wall=<ms> gap=<ms> self=<ms> gs=<n> players=<n> lt=<ms> paused=<0|1>` — the
  tracker only: the frame gap the engine saw; `paused=1` = levelTime frozen ≥ 1 s;
- `FM wall=<end> mod=<name> self=<ms> top=<section>:<ms>` — any module whose frame
  cost ≥ 50 ms (1 line/s/module, 3000 lines per lua state).

Read it with `scripts/frame_health_report.py`: for each gap the FM lines inside
`(wall − gap, wall]` are our Lua, the remainder is engine/host. Sections named
today: tracker `init_scan sample teamplay construction output round_end w6`,
webhook `sweep send`, c0rnp0rn8 `store_stats`, endstats `topshots`,
live_events `movement flush`. Deploy = the live paths in this document, a map
load on an empty server, then six `FH init … mod=` lines; ⛔ never `lua_restart`.
