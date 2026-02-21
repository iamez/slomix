# ET:Legacy Bot — Commands Reference

This document lists the Discord bot commands found in the repository, their aliases, short descriptions, and where they are defined. It was generated automatically from the source in the repository and is intended to be published to GitHub.

---

## Analytics cog (`bot/cogs/analytics_cog.py`) - NEW v1.0.6

| Command | Aliases | Description |
|---|---|---|
| `consistency` | `reliable`, `variance` | Show player's performance reliability score (0-100) |
| `map_stats` | `mapstats` | Show player's performance by map vs their baseline |
| `playstyle` | `style`, `role` | Analyze attack vs defense preference |
| `awards` | `fun_stats`, `funstats` | Show fun awards for latest session (zombie, glass cannon, etc.) |
| `fatigue` | (none) | Show if player fatigued during their latest session |

---

## Matchup cog (`bot/cogs/matchup_cog.py`) - NEW v1.0.6

| Command | Aliases | Description |
|---|---|---|
| `matchup` | `vs`, `headtohead`, `h2h` | Show matchup stats between two lineups |
| `duo_perf` | `duoperf`, `pair_stats` | Show performance when two players are on same team |
| `nemesis` | (none) | Show which opponent counters a player most |

---

## Core commands (defined in `bot/ultimate_bot.py`)

| Command | Aliases | Description |
|---|---|---|
| `session_start` | (none) | Start a new gaming session (creates a round record) |
| `sync_stats` | `syncstats`, `sync_logs` | Manually sync and process unprocessed stats files from remote server via SSH |
| `session_end` | (none) | Stop monitoring / end the current session |
| `ping` | (none) | Check bot status, latency, DB latency and cache stats |
| `cache_clear` | (none) | Clear the internal query cache (admin-only) |
| `check_achievements` | (none) | Show achievement progress for a player (self, named, or mention) |
| `compare` | (none) | Compare two players and generate a visual radar chart (K/D, accuracy, DPM, HS%, games) |
| `season_info` | `season`, `seasons` | Show current season info and champions |
| `help_command` | (none) | Display help/command overview |
| `stats` | (none) | Show detailed statistics for a player (self, name or mention) |
| `leaderboard` | `lb`, `top` | Show leaderboards (kills, kd, dpm, accuracy, etc.) with pagination |
| `session` | `match`, `game` | Show session/match details |
| `last_round` | `last`, `latest`, `recent` | Show the most recent session |
| `rounds` | `list_sessions`, `ls` | List sessions |
| `list_players` | `players`, `lp` | List players (search/listing helpers) |
| `link` | (none) | Link a Discord user to an ET:Legacy account (by name or GUID) |
| `unlink` | (none) | Unlink a Discord account from an ET:Legacy GUID |
| `select` | (none) | Selection helper used in interactive flows |

---

## Synergy analytics cog (e.g. `bot/cogs/synergy_analytics.py`)

| Command | Aliases | Description |
|---|---|---|
| `synergy` | `chemistry`, `duo` | Show player synergy/chemistry statistics (pair performance) |
| `best_duos` | `top_duos`, `best_pairs` | Show the best player duos |
| `team_builder` | `balance_teams`, `suggest_teams` | Suggest balanced teams based on analytics |
| `player_impact` | `teammates`, `partners` | Show player impact on teammates / partners analytics |
| `fiveeyes_enable` | (none) | Enable the "fiveeyes" feature/flag |
| `fiveeyes_disable` | (none) | Disable the "fiveeyes" feature/flag |
| `recalculate_synergies` | (none) | Recalculate stored synergy statistics |

---

## Availability poll cog (`bot/cogs/availability_poll_cog.py`) - NEW

| Command | Aliases | Description |
|---|---|---|
| `poll_notify` | (none) | Toggle availability poll notification preferences (on/off/threshold/reminder) |
| `poll_status` | (none) | Show today's poll results (yes/no/maybe counts and threshold progress) |

---

## Server control cog (e.g. `bot/cogs/server_control.py`)

| Command | Aliases | Description |
|---|---|---|
| `server_status` | `status`, `srv_status` | Show server status |
| `server_start` | `start`, `srv_start` | Start the game server |
| `server_stop` | `stop`, `srv_stop` | Stop the server |
| `server_restart` | `restart`, `srv_restart` | Restart the server |
| `list_maps` | `map_list`, `listmaps` | List available maps |
| `map_add` | `addmap`, `upload_map` | Upload/add a map |
| `map_change` | `changemap`, `map` | Change current map |
| `map_delete` | `deletemap`, `remove_map` | Delete a map |
| `rcon` | (none) | Run an rcon command on the server |
| `kick` | (none) | Kick a player from server |
| `say` | (none) | Send a message to the server chat |

---

## Other / dev / backup commands (found in backups, dev copies)

These commands appear in older or dev copies and may be duplicates or previous variants:

- `session_status`
- `link_me` / `link_player`
- `top_dpm`
- `mvp_awards`
- `gather` / `gather_leave`
- `manual_ping`
- `session_stats`
- `start_monitoring` / `stop_monitoring`
- `import_status`

There are also small test placeholders (`@commands.command()` with no explicit name) in several `test_bots/*` files.

---

## CLI scripts (argparse) — not Discord commands

Several scripts expose command-line flags (examples):

- `run_overnight_tests.py` — flags: `--no-fix`, `--quiet`
- `dev/production_auto_link.py` — flags: `--historical-dir`, `--process-file`, `--add-mapping`, `--show-stats`, `--db-path`
- `dev/bulk_import_stats.py` and similar import scripts — various processing flags

---

## How to publish this file to GitHub

If you'd like to push `COMMANDS.md` to the repo on GitHub, from the repo root run (PowerShell):

```powershell
git add COMMANDS.md
git commit -m "Add COMMANDS.md — bot command reference"
git push origin HEAD
```

Note: replace `origin`/branch names as appropriate for your remote setup.

---

If you want I can also:

- Produce a machine-friendly CSV or JSON alongside this Markdown.
- Add inline links from each command to the source file and line numbers.
- Automatically open a PR with the change (I can't push from here — you'll need to run the git commands above or let me know to create a branch file and I can prepare a patch).

Tell me which extras you'd like (CSV/JSON, source links, or a PR-ready patch).
