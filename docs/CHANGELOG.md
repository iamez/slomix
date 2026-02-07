# Changelog

All notable changes to the ET:Legacy Stats Bot project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.6] - 2026-02-01

### Player Analytics System (Phase 1)

New commands for advanced player performance analysis:

| Command | Aliases | Description |
|---------|---------|-------------|
| `!consistency <player>` | `!reliable`, `!variance` | Performance reliability score (0-100) |
| `!map_stats <player>` | `!mapstats` | Per-map performance vs player baseline |
| `!playstyle <player>` | `!style`, `!role` | Attack vs defense preference analysis |
| `!awards` | `!fun_stats`, `!funstats` | Fun session awards (zombie, glass cannon, etc.) |
| `!fatigue <player>` | - | Session performance trend (early vs late) |

- New files: `bot/cogs/analytics_cog.py`, `bot/services/player_analytics_service.py`

### Matchup Analytics System

New commands for lineup vs lineup statistics:

| Command | Aliases | Description |
|---------|---------|-------------|
| `!matchup A vs B` | `!vs`, `!h2h`, `!headtohead` | Lineup vs lineup historical stats |
| `!duo_perf p1 p2` | `!duoperf`, `!pair_stats` | Performance when two players on same team |
| `!nemesis <player>` | - | Which opponent counters this player most |

- New files: `bot/cogs/matchup_cog.py`, `bot/services/matchup_analytics_service.py`
- Database: `matchup_history` table with JSONB player stats
- Auto-records matchups when session results are saved
- Confidence levels based on sample size

### Added

- **Map-Based Stopwatch Scoring** (Feb 1, 2026)
  - Session scores now count MAP wins, not round wins (correct for stopwatch mode)
  - `StopwatchScoringService.calculate_session_scores_with_teams()` maps side-winner to persistent team
  - Full map breakdown with timing in `!last_session` embed
  - Display format: `🏆 Match Result: puran 3 - 2 sWat` with per-map detail
  - Tie handling: Double fullhold = 1-1 (both teams defended successfully)

- **Matchup Analytics System** (Feb 1, 2026)
  - Track lineup vs lineup statistics across sessions
  - Commands: `!matchup`, `!synergy`, `!nemesis`
  - Per-player performance deltas vs baseline
  - Synergy analysis (performance WITH teammates)
  - Anti-synergy/nemesis detection (performance AGAINST opponents)
  - Confidence levels (low/medium/high) based on sample size
  - Auto-records matchups when session results are saved
  - Database: `matchup_history` table with JSONB player stats

- **Real-Time Team Tracking** (Feb 1, 2026)
  - Teams created immediately on R1 import (first round of new session)
  - Side 1 = Team A, Side 2 = Team B (clean split before any swaps)
  - New players automatically added to teams on subsequent rounds
  - Supports games growing from 3v3 → 4v4 → 6v6 with proper team assignment
  - New `TeamManager` methods: `create_initial_teams_from_round()`, `update_teams_from_round()`
  - Added `_handle_team_tracking()` hook in import pipeline
  - `gaming_session_id` column added to `session_teams` table

- **Website Frontend Fixes & Enhancements** (Jan 31, 2026)
  - Fixed critical bugs: map win rates, team sorting (5v1→3v3), match scoring (kills→times), player stats format
  - Added SVG badge system with 14 badge types (achievements, ranks, special admin badge for Discord ID 231165917604741121)
  - Added season leaders panel (6 categories: DMG given/received, friendly fire, revives, deaths, longest session)
  - Added GitHub-style activity calendar widget (90-day summary, ready for Chart.js heatmap)
  - Implemented inline player details expansion (combat, support, weapons, sprees - no navigation)
  - Matched Discord !last_session format exactly (K/D/G, DMG↑/↓, REV↑/↓, ACC, HS, Useful, Playtime)
  - Files modified: 6 (3 backend, 3 frontend), ~900 lines added
  - New endpoints: `/seasons/current/leaders`, `/rounds/{round_id}/player/{player_guid}/details`
  - See: `docs/SESSION_2026-01-31_WEBSITE_FRONTEND_FIXES.md`

- **Claude Code Configuration Restoration & Optimization** (Jan 31, 2026)
  - Recovered from 362 MB config crash (reduced to 1.45 MB)
  - Restored project settings, MCP PostgreSQL server, and permissions
  - Created automated upgrade script: `~/claude_settings_improvement_plan.sh`
  - Added comprehensive documentation:
    - `docs/SESSION_2026-01-31_CLAUDE_CODE_RESTORATION.md` - Full session report
    - `docs/reference/CLAUDE_CODE_QUICK_REFERENCE.md` - Daily reference guide
    - `docs/reports/CLAUDE_SETTINGS_REVIEW_2026-01-31.md` - Settings audit
    - `docs/reports/CLAUDE_CONFIG_AUDIT_2026-01-31.md` - Config analysis
    - `docs/SESSION_INDEX.md` - Documentation navigation index
  - Identified scattered configs across 3 projects (bot/website/proximity)
  - Scorecard: 7.1/10 (good with room for improvement)
  - Recommendations: Install GitHub CLI, add filesystem/git MCP servers
  - Configuration status: Healthy and optimized ✅

- **ET:Legacy Game Server Optimization** (Jan 25, 2026)
  - CPU affinity: Game server pinned to cores 0,1 for better cache locality
  - UDP buffer optimization: Increased minimum from 4KB to 16KB
  - Modified startup script: `/home/et/etlegacy-v2.83.1-x86_64/etdaemon.sh`
  - Created sysctl config: `/etc/sysctl.d/99-etlegacy.conf`
  - Backups saved to: `/home/et/backups/2026-01-25/`
  - See: `docs/SESSION_2026-01-25_SERVER_OPTIMIZATION.md`

- **Lua Webhook Real-Time Stats Notification** - Instant round-end notification from game server
  - Lua script `stats_discord_webhook.lua` (v1.3.0) runs on ET:Legacy game server
  - Captures accurate round timing at gamestate transition (fixes surrender timing bug)
  - Captures team composition at round end (Axis/Allies player lists)
  - Tracks pause count and duration (new capability)
  - Uses Discord webhook as relay (supports outbound-only architecture)
  - ~3 second latency vs 60-second SSH polling
  - Config: Webhook URL in Lua script, webhook ID in `WEBHOOK_TRIGGER_WHITELIST`

- **Lua Webhook v1.3.0 Timing Enhancements** (Jan 2026)
  - `Lua_WarmupEnd` field - Unix timestamp when warmup ended (= round start)
  - `Lua_Pauses_JSON` field - detailed pause event timestamps `[{n,start,end,sec},...]`
  - Timing legend in webhook embed explaining Playtime vs Warmup vs Wall-clock
  - Database: `lua_pause_events` JSONB column for queryable pause data
  - Migration: `tools/migrations/004_add_pause_events.sql`

- **Lua Webhook v1.2.0 Warmup Tracking** (Jan 2026)
  - `Lua_Warmup` field - warmup phase duration in seconds
  - `Lua_WarmupStart` field - Unix timestamp when warmup began
  - Database: `lua_warmup_seconds`, `lua_warmup_start_unix` columns
  - Migration: `tools/migrations/003_add_warmup_columns.sql`

- **lua_round_teams Database Table** - Stores Lua-captured data separately for cross-reference
  - Team composition (JSONB arrays with guid/name)
  - Accurate timing data for validation against stats files
  - Links to rounds table via `match_id` + `round_number`

- **Timing Comparison Debug Logging** - Shows stats file vs Lua timing for every webhook-processed round
  - Identifies surrender scenarios automatically
  - Logs to bot logs (not visible to users)

### Fixed

- **Time Dead/Alive Calculation Bug** (Feb 1, 2026)
  - Fixed bug where R2 rounds used wrong calculation method (`time_played_minutes * time_dead_ratio`)
  - R2 `time_dead_ratio` is calculated against cumulative time in Lua, but parser stores differential `time_played`
  - Multiplying them together caused ~15 min/session undercount of death time
  - Now uses `time_dead_minutes` directly (already correct in database for both R1 and R2)
  - Files fixed: `session_stats_aggregator.py`, `ssh_monitor.py`

- **Surrender Timing Bug** - Rounds ending early (surrender/objective) now show actual played time instead of full map duration
  - Stats files show map time limit on surrender (e.g., 20 min)
  - Lua captures actual end time (e.g., 8 min)
  - Bot overrides broken timing with accurate Lua data
- **SSHHandler method name** - Fixed `list_files` → `list_remote_files` in webhook file fetch
- **Webhook username** - Lua script now sends correct username for bot message filtering

### Changed

- **Field naming convention** - All webhook fields now use `Lua_` prefix to distinguish from stats file timing
  - `Duration` → `Lua_Playtime`
  - `Start Unix` → `Lua_RoundStart`
  - `End Unix` → `Lua_RoundEnd`

### Technical Details

- **New Files**: `vps_scripts/stats_discord_webhook.lua`, `tools/migrations/001_add_timing_metadata_columns.sql`, `tools/migrations/002_add_lua_round_teams_table.sql`, `tools/migrations/003_add_warmup_columns.sql`, `tools/migrations/004_add_pause_events.sql`, `docs/LUA_WEBHOOK_SETUP.md`, `docs/reference/TIMING_DATA_SOURCES.md`
- **Modified**: `bot/ultimate_bot.py` (+600 lines), `postgresql_database_manager.py` (+7 lines)
- **Branch**: `feature/lua-webhook-realtime-stats`
- **Inspiration**: Patterns adapted from Oksii's `game-stats-web.lua` used by competitive ET:Legacy communities

---

## [1.0.2] - 2025-12-04

### December 2025 Feature Release - Real-Time Push & Voice Logging

### Added

- **WebSocket Real-Time Push System** - Instant file detection from VPS via WebSocket (replaces 60s SSH polling)
  - `vps_ws_notifier.py` - VPS-side file watcher that pushes notifications to bot
  - Bot receives instant alerts when new stats files are written
  - Config: `WS_ENABLED`, `WS_HOST`, `WS_PORT`, `WS_AUTH_TOKEN`
- **Voice Session Logging** - Track player voice channel activity for gaming sessions
  - Logs join/leave events for configured gaming voice channels
  - Config: `ENABLE_VOICE_LOGGING=true`
- **Round Publisher Service** - Auto-post rich Discord embeds after each round
  - Shows ALL players ranked by kills with comprehensive stats
  - Compact 2-line format: Name on line 1, all stats on line 2-3
  - Stats include: K/D/G, DPM, damage dealt/received, accuracy, headshots, revives, team damage, time played/dead/denied, multikills
  - Map completion summaries posted after Round 2
- **Team Suggestion Commands** - AI-powered team balancing
  - `!suggest_teams` - Suggest balanced teams from voice channel players
  - `!balance_teams` - Alias for suggest_teams
  - Uses historical player stats to optimize team balance
- **FiveEyes Synergy Analytics Framework** - Infrastructure for player synergy tracking (disabled by default)
  - `fiveeyes_config.json` - Configuration for synergy analytics
  - Synergy calculation and team optimization algorithms ready for future activation

### Changed

- **SSH Monitoring Now Optional** - WebSocket push is preferred method for instant file detection
- **Round Stats Format Enhanced** - New compact 2-line format with all stats including multikills and time denied
- **Player Chunk Size Increased** - Bumped from 5 to 8 players per embed field (typical games don't split across fields)

### Fixed

- **SQL Nosec Comment Bug** - Fixed `# nosec B608` comment appearing inside SQL query string causing PostgreSQL syntax errors
- **Command Alias Conflicts** - Resolved `balance_teams` and `suggest_teams` alias conflicts between team_builder and synergy_analytics cogs
- **Channel Check Decorators** - Removed `@is_public_channel()` from team commands that was blocking execution
- **Critical SQL Placeholder Bugs** - Fixed 12 queries using `{placeholders}` in regular strings instead of f-strings (would silently fail)
- **Kill Thief Typo** - Fixed `kill_thie` → `kill_thief` in session_embed_builder.py (would cause KeyError)
- **Foreign Key Constraint Mapping** - Fixed empty string `''` to `'f'` in validate_vps_schema.py
- **Unused Variables** - Removed unused `ph`, `placeholder`, `heapq` variables
- **Redundant Imports** - Removed duplicate `datetime` imports in ultimate_bot.py

### Technical Details

- **New Files**: `bot/services/round_publisher_service.py`, `bot/services/voice_session_service.py`, `tools/vps_ws_notifier.py`
- **Config Additions**: WebSocket settings (`WS_*`), voice logging (`ENABLE_VOICE_LOGGING`)
- **Branch**: Merged from `feature/websocket-push-voice-logging` (PR #22)

---

## [1.0.1] - 2025-12-01

### December 2025 Maintenance Release - Critical Bug Fixes

### Fixed

- **CRITICAL: SSHMonitor Race Condition** - Fixed live Discord posting not working due to race condition between SSHMonitor service and endstats_monitor task. Both were running simultaneously causing files to be marked "processed" before Discord posting could occur. Solution: Disabled SSHMonitor auto-start; endstats_monitor now handles SSH + DB import + Discord posting.
- **Channel Permission Checks** - `is_public_channel()` and `is_admin_channel()` decorators now silently return `False` instead of raising exceptions and sending error messages. Bot no longer announces "wrong channel" to users.
- **on_message Channel Filtering** - Fixed bot responding to commands in wrong channels. Now properly uses `public_channels` config as fallback when `bot_command_channels` is not set.
- **Website HTML Corruption** - Fixed `website/index.html` structure that was corrupted (duplicate opening tags, malformed document structure).
- **Website JS Duplicate Functions** - Fixed `website/js/app.js` with duplicate `loadLeaderboard()` function declarations and broken `loadMatches()` function.
- **Website SQL Injection** - Added `escape_like_pattern()` function to `website/backend/routers/api.py` to prevent SQL injection via search patterns.

### Changed

- SSHMonitor service is now initialized but NOT auto-started on bot startup
- SSHMonitor remains available for manual control via `!automation` commands
- endstats_monitor task loop is now the sole handler for: SSH connection, file download, database import, and Discord posting

### Technical Details

- **Root Cause**: Two monitoring systems (SSHMonitor + endstats_monitor) were competing for the same files. SSHMonitor downloaded files first, marking them as "processed" in local filesystem. When endstats_monitor ran, `should_process_file()` check #3 ("does file exist locally?") returned True, skipping the file before Discord posting could occur.
- **Files Modified**: `bot/ultimate_bot.py`, `bot/core/checks.py`, `bot/services/automation/ssh_monitor.py`, `website/index.html`, `website/js/app.js`, `website/backend/routers/api.py`

---

## [1.0.0] - 2025-11-20

### Version 1.0 Release - Production Ready

### Added

- Achievement badge system for players (medic, engineer, sharpshooter, rambo, objective specialist)
- Custom display name system for linked Discord accounts
- `!set_display_name` command to set personalized display names
- `!achievements` command to view available achievement badges
- Exact value labels on all performance graphs for better readability
- Badge stacking support for players with multiple achievements

### Changed

- **BREAKING**: Auto-posting now shows ALL players with comprehensive stats (not just top performers)
- Improved !last_session output format with achievement badges displayed next to player names
- Enhanced session statistics display with two-line player format for better readability
- Updated achievement badges to appear in !last_session player listings

### Fixed

- Critical bug in !list_players command that caused crashes
- Codacy static analysis warnings for code quality
- Various production bugs and edge cases

## [2.0.0] - 2025-11-18

### Major Release - Production-Ready System

### Added

- **6-Layer Data Validation System** - Comprehensive data integrity with ACID guarantees
- **Full Automation Suite** - Zero-touch operation with SSH monitoring
- **Voice-Conditional SSH Monitoring** - Resource-efficient monitoring based on voice channel activity
- **Gaming Session Grouping** - Automatic 60-minute gap detection for session tracking
- **Round 2 Differential Calculation** - Accurate team-swap stat calculation
- **PostgreSQL Migration** - Complete migration from SQLite to PostgreSQL 18.0
- **Interactive Linking System** - React-based player account linking
- **Comprehensive Leaderboards** - 11 different ranking categories
- **Session Analytics** - Detailed session summaries and statistics
- **Alias Tracking** - Automatic player name consolidation
- **Structured Logging** - Comprehensive logging system with separate log files
- **Connection Pooling** - High-performance async database operations
- **TTL-based Caching** - 300-second cache for improved performance

### Changed

- **DPM Calculations** - Now use actual playtime instead of round duration for accuracy
- **Leaderboard Queries** - Fixed stat inflation by properly filtering R0 warmup rounds
- **Session Detection** - Improved gaming session boundary detection
- **Startup Optimization** - SSH monitor now only checks last 24 hours on startup (not all 3,766+ files)
- **File Filtering** - Automatically excludes `_ws.txt` and unwanted files
- **Voice Detection** - Enhanced voice channel monitoring with grace periods

### Fixed

- **Security**: Rate limiting, Discord intents, database SSL support
- **Performance**: Fixed !lp command unbounded query (critical optimization)
- **Data Integrity**: R0/R1/R2 filtering across all queries
- **Memory Leaks**: Fixed async blocking and resource cleanup
- **PostgreSQL Compatibility**: Fixed boolean type errors and parameter mismatches
- **Shell Injection**: Proper command sanitization with shlex.quote()
- **Voice Detection Bug**: Fixed 31% file loss issue
- **Team Aggregation**: Fixed DPM and stat calculations
- **Session Commands**: Fixed !last_session and !session queries
- **Sync Commands**: Fixed !sync_month and !sync_week errors

### Security

- Added rate limiting to prevent abuse
- Implemented secure temp file handling
- Added command sanitization for shell commands
- Fixed SQL injection warnings in link_cog.py
- Added database SSL support
- Proper Discord intents configuration

## [1.0.0] - 2025-10-15

### Initial Production Release

### Added

- Basic Discord bot functionality
- SQLite database support
- Manual stats file import
- Player statistics commands (!stats, !compare)
- Basic leaderboard system
- Round and session tracking
- Player linking system

### Features

- 53+ statistics tracked per player
- K/D ratio, DPM, accuracy calculations
- Weapon statistics breakdown
- Map-specific statistics
- Basic automation support

---

## Version History Summary

- **v2.0.0** (2025-11-18): Major production release with PostgreSQL, full automation, and 6-layer validation
- **v1.0.0** (2025-10-15): Initial production release with basic features

---

## Upgrade Notes

### Upgrading to 2.0.0

1. **Database Migration Required**: Run `postgresql_database_manager.py` to migrate from SQLite to PostgreSQL
2. **Configuration Changes**: Update `.env` file with PostgreSQL credentials
3. **New Dependencies**: Install updated requirements with `pip install -r requirements.txt`
4. **Automation Setup**: Configure SSH settings for automation features
5. **Voice Monitoring**: Add `GAMING_VOICE_CHANNELS` to `.env` for voice-conditional monitoring

### Breaking Changes in 2.0.0

- SQLite is no longer the primary database (PostgreSQL required)
- Database schema changes require migration
- Some command outputs have changed format
- Automation configuration moved to `.env` file

---

## Contribution Guidelines

When adding entries to this changelog:

1. **Group changes** into Added, Changed, Deprecated, Removed, Fixed, and Security sections
2. **Use present tense** for consistency ("Add feature" not "Added feature")
3. **Be specific** - include command names, file names, or feature names
4. **Link to issues/PRs** when relevant
5. **Update [Unreleased]** section for ongoing development
6. **Create new version** section when releasing

---

**Note**: This CHANGELOG was started on 2025-11-18. Prior changes were retroactively documented from git history.
