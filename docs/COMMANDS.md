# ET:Legacy Bot — Commands Reference

This document lists Discord bot commands declared in the repository (via `@commands.command(...)` and `@commands.group(...)`), with aliases and short descriptions. It is **auto-generated** from the source by `scripts/regen_commands_doc.py` — re-run that script after adding, renaming, or removing commands.

**Coverage:** 107 visible commands across 20 cog files / cog-mixin groups.

> Hidden commands (`@commands.command(hidden=True)`) are intentionally excluded.
> Slash commands (`@app_commands.command(...)`) are NOT in this list — none are currently declared in the repo.


---

## Achievements cog (`bot/cogs/achievements_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `achievements` | `medals`, `achievement` | 🏆 View achievement badge information |

---

## Admin cog (`bot/cogs/admin_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `cache_clear` | (none) | 🗑️ Clear query cache (Admin only - use in admin channel) |
| `correlation_status` | (none) | 🔗 Show round correlation status (Admin only) |
| `reload` | (none) | 🔄 Reload the bot (Root only) - Reconnects to Discord with updated code |
| `weapon_diag` | (none) | 🧪 Diagnostic: show weapon stats aggregates for a session |

---

## Admin Predictions cog (`bot/cogs/admin_predictions_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `admin_prediction_help` | (none) | Show help for admin prediction commands |
| `admin_predictions` | (none) | View all predictions with filtering options |
| `prediction_performance` | (none) | View system performance metrics for predictions |
| `recalculate_predictions` | (none) | Recalculate accuracy for all completed predictions |
| `update_prediction_outcome` | (none) | Manually update a prediction outcome |

---

## Analytics cog (`bot/cogs/analytics_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `awards` | `fun_stats`, `funstats` | Show fun/celebratory awards for the latest session |
| `consistency` | `reliable`, `variance` | Show player's consistency score (reliability) |
| `fatigue` | (none) | Show if a player fatigued during their latest session |
| `map_stats` | `mapstats` | Show player's performance by map |
| `playstyle` | `style`, `role` | Show player's attack vs defense preference |

---

## Automation cog (`bot/cogs/automation_commands.py`)

| Command | Aliases | Description |
|---|---|---|
| `automation_status` | (none) | 📋 Show all automation services status |
| `backup_db` | (none) | 💾 Manually trigger database backup |
| `health` | (none) | 📊 Show comprehensive bot health status |
| `metrics_report` | (none) | 📊 Generate comprehensive metrics report |
| `metrics_summary` | (none) | 📊 Quick metrics summary |
| `ssh_stats` | (none) | 🔄 Show SSH monitor statistics and status |
| `start_monitoring` | (none) | 🟢 Start SSH monitoring |
| `stop_monitoring` | (none) | 🔴 Stop SSH monitoring |
| `vacuum_db` | (none) | 🧹 Optimize database (VACUUM) |

---

## Availability (Inferred) cog (`bot/cogs/availability_mixins/daily_poll_mixin.py`, `bot/cogs/availability_mixins/external_channels_mixin.py`)

| Command | Aliases | Description |
|---|---|---|
| `avail` | (none) | Set date-based availability |
| `avail_link` | (none) | Generate a one-time link token for Telegram/Signal notification subscription |
| `avail_unsubscribe` | (none) | Disable availability notifications for a channel type |
| `poll_notify` | (none) | Toggle availability poll notifications |
| `poll_status` | (none) | Show today's poll results |

---

## Last Session cog (`bot/cogs/last_session_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `endstats_audit` | `endstats_check`, `endstats_status` | 🔎 Audit endstats coverage for the latest session |
| `last_session` | `last`, `latest`, `recent`, `last_round` | 🎮 Show the most recent session/match |
| `last_session_debug` | `last_debug`, `ls_debug` | Admin debug: compact top-N timing diffs (old vs shadow/new) |
| `team_history` | (none) | 📊 Show team performance history (PLACEHOLDER) |

---

## Leaderboard cog (`bot/cogs/leaderboard_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `leaderboard` | `lb`, `top` | 🏆 Show players leaderboard with pagination |
| `stats` | (none) | 📊 Show detailed player statistics |

---

## Link cog (`bot/cogs/link_mixins/browse_mixin.py`, `bot/cogs/link_mixins/core_mixin.py`, `bot/cogs/link_mixins/interactive_mixin.py`)

| Command | Aliases | Description |
|---|---|---|
| `find_player` | `findplayer`, `fp`, `search_player` | 🔍 Find players by name with GUIDs and aliases (Helper for linking) |
| `link` | (none) | 🔗 Link your Discord account to your in-game profile |
| `list_players` | `players`, `lp` | 👥 List all players with pagination |
| `myaliases` | `aliases`, `mynames` | 📝 View all your player aliases |
| `select` | (none) | 🔢 Select an option from a link prompt (alternative to reactions) |
| `setname` | (none) | ✏️ Set your custom display name |
| `unlink` | (none) | 🔓 Unlink your Discord account from your in-game profile |

---

## Matchup cog (`bot/cogs/matchup_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `duo_perf` | `duoperf`, `pair_stats` | Show performance stats when two players are on the same team |
| `matchup` | `vs`, `headtohead` | Show matchup statistics between two lineups |
| `nemesis` | `counter` | Show which opponents suppress a player's performance |

---

## Permission Management cog (`bot/cogs/permission_management_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `admin_add` | `perm_add` | ➕ Add user to permission whitelist (Root only) |
| `admin_audit` | `perm_audit` | 📜 View permission change audit log (Root only) |
| `admin_list` | `perm_list`, `admins` | 📋 List all users with permissions (Admin+) |
| `admin_remove` | `perm_remove` | ➖ Remove user from permission whitelist (Root only) |

---

## Predictions cog (`bot/cogs/predictions_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `map_predictions` | (none) | View prediction statistics by map |
| `my_predictions` | (none) | View predictions for matches you participated in |
| `prediction_help` | (none) | Show help for prediction commands |
| `prediction_leaderboard` | (none) | View prediction leaderboards |
| `prediction_stats` | (none) | View prediction accuracy statistics |
| `prediction_trends` | (none) | View prediction accuracy trends over time |
| `predictions` | (none) | View recent match predictions |

---

## Proximity cog (`bot/cogs/proximity_mixins/admin_commands_mixin.py`, `bot/cogs/proximity_mixins/stats_commands_mixin.py`)

| Command | Aliases | Description |
|---|---|---|
| `proximity_carrier_kills` | `pck` | Top carrier killers - who stops objective runners (v6) |
| `proximity_carriers` | `pca` | Top carrier leaderboard - distance, secures, efficiency (v6) |
| `proximity_carry_detail` | `pcd` | Detailed carrier event log for a session (v6) |
| `proximity_cohesion` | `pco` | Team cohesion summary - Axis vs Allies formation tightness (v5) |
| `proximity_crossfire_angles` | `pxa` | Crossfire opportunity analysis with utilization rate (v5) |
| `proximity_import` | (none) | Manually import an engagement file (admin only) |
| `proximity_objectives` | (none) | Show which maps have objective coordinates configured |
| `proximity_pushes` | `ppu` | Team push quality comparison - Axis vs Allies (v5) |
| `proximity_scan` | (none) | Force scan for new engagement files (admin only) |
| `proximity_session` | `psession`, `pscore` | Per-session proximity combat scores |
| `proximity_spawn_efficiency` | `pse` | Top 10 players by spawn timing efficiency (v5) |
| `proximity_status` | (none) | Show proximity tracker status (admin only) |
| `proximity_trades_lua` | `ptl` | Lua-detected trade kill leaderboard (v5) |

---

## Server Control cog (`bot/cogs/server_control.py`)

| Command | Aliases | Description |
|---|---|---|
| `kick` | (none) | 👢 Kick a player from server (Admin channel only) |
| `list_maps` | `map_list`, `listmaps` | 📋 List available maps on server |
| `map_add` | `addmap`, `upload_map` | ➕ Upload new map to server (Admin channel only) |
| `map_change` | `changemap`, `map` | 🗺️ Change current map (Admin channel only) |
| `map_delete` | `deletemap`, `remove_map` | 🗑️ Delete a map from server (Admin channel only) |
| `rcon` | (none) | 🎮 Send RCON command to server (Admin channel only) |
| `say` | (none) | 💬 Send message to server chat (Admin channel only) |
| `server_restart` | `restart`, `srv_restart` | 🔄 Restart the ET:Legacy server (Admin channel only) |
| `server_start` | `start`, `srv_start` | 🚀 Start the ET:Legacy server (Admin channel only) |
| `server_status` | `status`, `srv_status` | 💚 Check if ET:Legacy server is running |
| `server_stop` | `stop`, `srv_stop` | 🛑 Stop the ET:Legacy server (Admin channel only) |

---

## Session cog (`bot/cogs/session_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `rounds` | `sessions`, `list_sessions`, `ls` | 📅 List all gaming sessions, optionally filtered by month |
| `session` | `match`, `game` | 📅 Show detailed session/match statistics for a specific date |

---

## Session Management cog (`bot/cogs/session_management_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `session_end` | (none) | 🏁 Stop SSH monitoring |
| `session_start` | (none) | 🎬 Start a new gaming session |

---

## Stats cog (`bot/cogs/stats_cog.py`, `bot/cogs/stats_mixins/compare_mixin.py`)

| Command | Aliases | Description |
|---|---|---|
| `badges` | `badge_legend`, `achievements_legend` | 🏅 Show achievement badge legend |
| `check_achievements` | `check_achivements`, `check_achievement` | 🏆 Check your achievement progress |
| `compare` | (none) | 📊 Compare two players with a visual radar chart |
| `help_command` | `commands`, `cmds`, `bothelp` | 📚 Show all available commands with examples |
| `ping` | (none) | 🏓 Check bot status and performance |
| `season_info` | `season`, `seasons` | 📅 Show current season information and champions |

---

## Sync cog (`bot/cogs/sync_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `sync_all` | (none) | 🔄 Quick sync: ALL unprocessed files (no time filter) |
| `sync_historical` | `sync_missing`, `backfill` | 📥 Download missing files from game server to local_stats/ |
| `sync_month` | `sync1month` | 🔄 Quick sync: This month's matches (last 30 days) |
| `sync_stats` | `syncstats`, `sync_logs` | 🔄 Manually sync and process stats files from server |
| `sync_today` | `sync1day` | 🔄 Quick sync: Today's matches only (last 24 hours) |
| `sync_week` | `sync1week` | 🔄 Quick sync: This week's matches (last 7 days) |

---

## Team cog (`bot/cogs/team_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `add_team` | (none) | Add a new team to the pool (requires permissions) |
| `assign_teams` | (none) | Randomly assign team names from pool to a session |
| `head_to_head` | `h2h` | Show head-to-head record between two teams |
| `lineup_changes` | (none) | Show lineup changes between two sessions |
| `session_score` | (none) | Show final score for a session |
| `set_team_names` | (none) | Set custom team names for a session |
| `team_pool` | (none) | Show available team names in the pool |
| `team_record` | (none) | Show win/loss record for a team |
| `teams` | (none) | Show team rosters for a session |

---

## Team Management cog (`bot/cogs/team_management_cog.py`)

| Command | Aliases | Description |
|---|---|---|
| `assign_player` | (none) | 👤 Assign a player to a persistent team for the latest session date |
| `set_teams` | (none) | 👥 Manually set persistent team names for the latest session date |
