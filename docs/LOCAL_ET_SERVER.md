# Local ET:Legacy test server

A binary-identical copy of the game server, on the dev box, so Lua changes are
tested somewhere other than production.

Before it existed, testing a Lua module meant `slomix_rcon.py testmode on`
against **puran** — the server the community plays on. A module that throws in
`et_InitGame` takes the round with it, and that is not a thing to discover
during a gather.

The server is **on-demand**: it costs nothing while stopped, and nothing about
it runs at boot.

## Two versions, side by side

The competitive community is not always on the same ET:Legacy build as the
developers, so Slomix has to run on both. Each version gets its own port,
homepath, console socket and tmux session, so they can run at the same time
without mixing up their `gamestats` output.

| version | directory | homepath | port | tmux session |
|---|---|---|---|---|
| 2.84.0 (default) | `/home/et/etlegacy-v2.83.1-x86_64` | `/home/et/.etlegacy` | 27960 | `etlocal` |
| 2.85.0 | `/home/et/etlegacy-v2.85.0-x86_64` | `/home/et/.etlegacy-v2.85.0` | 27961 | `etlocal285` |

⚠️ **The directory name lies.** `etlegacy-v2.83.1-x86_64` contains v2.84.0 —
on puran as well as here. The name is hardcoded in four places (including
`bot/cogs/server_control.py`), so it is not renamed; `local_et.sh status`
prints the version the *binary* reports rather than trusting the path.

```bash
scripts/local_et.sh --versions        # what is registered, with paths and ports
scripts/local_et.sh -v 2.85.0 start   # anything below takes -v
```

## One-time setup

```bash
sudo bash scripts/local_et_setup.sh
```

Idempotent — re-running refreshes the copy and breaks nothing. It is the only
step that needs root. Everything after it runs **without sudo**, because the
setup puts your user in the `etconsole` group and the server lives in a shared
tmux session owned by `et`.

It needs two things to exist first:

- `~/.ssh/etlegacy_bot` — the key to puran, to copy the game directory from it
- `~/.ssh/etlegacy_local` — a local key; create with
  `ssh-keygen -t ed25519 -f ~/.ssh/etlegacy_local -N ''`

What it does, in order: installs dependencies (`curl unzip tmux rsync scp
sha256sum lua5.4 luac5.4` — `curl` is not optional, `stats_discord_webhook.lua`
calls it); creates the `et` user and `etconsole` group; copies ~766 MB of game
directory from puran over `tar` through ssh (**not** rsync — puran does not
have rsync); copies *selected* homepath files; installs `etmain/local.cfg` from
`server/local/local.cfg`; sets up Omni-bot; starts the tmux console session;
and writes one narrow sudoers rule so the session can be restarted after a
reboot without a password.

**The homepath is copied selectively, never wholesale.** These stay on puran:

| not copied | why |
|---|---|
| `stats_discord_webhook_config.lua` | the production Discord webhook URL |
| `sv_protect.log` | player IP addresses |
| `legacy3.log`, `etconsole.log` | 159 MB of history, overwritten on start anyway |

`stats_discord_webhook.lua` itself **is** copied, because on puran the live copy
of that module lives in the homepath, not the basepath (see below).

## Daily use

```bash
scripts/local_et.sh start              # boot it in the tmux session
scripts/local_et.sh status             # running? how many bots? which map?
scripts/local_et.sh testmode on        # bots + the stopwatch rotation
scripts/local_et.sh watch              # follow the console live
scripts/local_et.sh stop               # console `quit`; the tmux session stays
```

| command | what it does |
|---|---|
| `start` / `stop` / `status` | lifecycle; `stop` sends a console `quit`, not a kill |
| `console "<cmd>"` | send to the console and print exactly what that produced |
| `rcon "<cmd>"` | the same over UDP RCON — the path used against puran |
| `deploy <file.lua>` | parse-gate, copy to the right place, full map load |
| `tail [n]` / `watch` | last n console lines / follow live |
| `verify` | are all Lua modules loaded, and did any of them throw? |
| `parity` | sha256 of the installation against puran's |
| `files` | what landed in `gamestats/`, `proximity/`, `gametimes/` |
| `testmode on\|off\|status` | bots and rotation on, off, or report |
| `attach` | drop into the tmux console yourself |

`console` reports by recording the size of `etconsole.log`, sending the command,
waiting, and printing everything written after that offset. That catches output
arriving a few seconds late — a Lua error, typically — which `capture-pane`
would miss because it only sees the visible window.

If you `attach`, detach with **Ctrl-B then D**. Ctrl-C kills the server.

## Where each Lua module goes

Not one directory. `fs_homepath` **overrides** `fs_basepath`, so a module
present in both is loaded from the homepath — and a fix deployed to the wrong
one changes nothing while looking like it worked.

| module | destination |
|---|---|
| `stats_discord_webhook.lua` | `<homepath>/legacy/luascripts/` |
| `c0rnp0rn8.lua`, `endstats.lua` | `<gamedir>/legacy/` |
| `proximity_tracker.lua`, `live_events.lua`, `team-lock.lua` | `<gamedir>/legacy/luascripts/` |

`local_et.sh deploy <file>` knows this table, refuses a file it does not
recognise, runs `luac5.4 -p` before copying, and then does a **full map load**.

⛔ **Never `lua_restart`.** c0rnp0rn8 crashes on it. Always a full `map <name>`.

Load order comes from `configs/legacy3bot.config`, deliberately not duplicated
in `local.cfg`, so it stays identical to production:

```
luascripts/team-lock.lua c0rnp0rn8.lua endstats.lua
luascripts/proximity_tracker.lua luascripts/stats_discord_webhook.lua
luascripts/live_events.lua
```

Read off puran on 2026-08-20, `etmain/configs/legacy3bot.config:131` (and the
identical line 131 of `legacy3.config`) — not from an older `.bak`, several of
which are still lying around with a different, obsolete list. Six modules is
also what `local_et.sh verify` expects to see loaded per start.

Order is not cosmetic. `et_Obituary` stops at the first module that returns a
value — `return 0` included, because `lua_isstring` is true for numbers — so a
module early in this list can starve every module after it. That is not
hypothetical: it cost the Live page its K/D columns for eight days. See
`tests/unit/test_lua_hook_return_contract.py`.

That config file also **re-executes on every map load**, so an `rcon setl
lua_modules ...` experiment silently reverts at the next map. Verify the order
that actually applied before concluding anything from it.

## `verify` and `parity`: two different questions

`verify` reads the console log: it expects **6 module loads per start** and
greps for the shapes a Lua failure takes (`error running lua`, `attempt to
index/call/compare`, `stack traceback`, `bad argument`).

`parity` asks whether this box still matches puran, by sha256, over the binary,
`qagame`, the pk3, every Lua module and both configs — plus
`stats_discord_webhook.lua` in the homepath separately, since that is where the
live copy is. Run it before trusting a local test: a local test proves nothing
about production if the two have drifted.

## How local.cfg differs from production, and why

Derived from puran's `etmain/vektor.cfg` plus `etmain/seareal.cfg`. Every
difference is deliberate:

| difference | why |
|---|---|
| `dedicated 1` passed on the command line | LAN only. The cvar is latched, so it goes in the command line — the test server must **never** appear on `master.etlegacy.com` |
| `sv_hostname "^1[LOCAL]^7 slomix test"` | so it is obvious in-game that this is not puran |
| `rconpassword` / `refereePassword` `slomixlocal` | local throwaway values, no relation to production |
| `com_watchdog 0` | production has `com_watchdog 10` + `com_watchdog_cmd "exec vektor.cfg"`. Locally a stopped server must **stay** stopped |
| `timelimit 8`, `sv_maxclients 16` | shorter rounds, smaller box |
| `bot minbots/maxbots 6`, `omnibot_enable 1` | rounds that actually produce data with nobody playing |

⛔ **Do not use `seareal.cfg` locally.** It sets `sv_hostname "[TEST]
purans.only"`, overwriting the version tag that is the only way to tell 2.84
from 2.85 in a server list.

Everything else — `g_customConfig legacy3bot`, `g_gametype 3` (stopwatch),
`sv_fps 40`, the logging cvars, `sv_pure`, `sv_protect` — matches production, so
logs from here are comparable with logs from there.

⚠️ `g_filterBan 1` means whitelist. **Never** `g_filterBan 0` with an empty
`g_banIPs`: that reads as "ban everyone" and locked production out for 24 hours
on 2026-02-03.

## The map rotation

Six maps, two rounds each, twelve `t#` entries. Odd `t#` is R1 (a map load),
even `t#` is R2 (`map_restart`, i.e. sides swap).

```
etl_adlernest → supply → sw_goldrush_te → etl_sp_delivery → te_escape2 → etl_frostbite
```

Only these maps have the waypoints Omni-bot needs; on anything else the bots
stand still and the round produces nothing worth measuring.

`map_restart` does not call `SV_SpawnServer`, so `nextmap` survives it — which
is what makes a stopwatch pair work at all. Endstats are written *before* the
restart, in `G_LogExit`.

## What comes out

`local_et.sh files` lists the three output directories under the homepath:
`gamestats/` (the `-endstats.txt` files the bot parses), `proximity/`, and
`gametimes/`. A round that produced nothing there did not produce anything —
whatever the console said.

## Troubleshooting

| symptom | first thing to check |
|---|---|
| `Ni konzolnega socketa` | setup has not run: `sudo bash scripts/local_et_setup.sh` |
| tmux session gone (after a reboot) | the error message prints the exact `tmux new-session` line to restore it |
| server will not start | `scripts/local_et.sh tail 60` |
| a Lua fix "did nothing" | homepath vs basepath — check the deploy table above |
| a module gets no kills | something ahead of it in `lua_modules` returns from `et_Obituary` |
| module order reverted itself | `legacy3bot.config` re-executes on every map load |
