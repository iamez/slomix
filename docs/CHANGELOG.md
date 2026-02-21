# Changelog

> Historical long-form notes. Canonical release changelog: `../CHANGELOG.md`.

All notable changes to Slomix are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Fixed — 2026-02-16

- **R2 Lua Webhook Rejection** — `bot/ultimate_bot.py:3637` rejected all R2 webhook data because `round_metadata.get("round_number", 0) == 0` treated `round_number=0` as invalid. In ET:Legacy stopwatch mode, `g_currentRound=0` means R2, so `round_number=0` is a valid value. Changed guard to `round_metadata.get("round_number", -1) < 0`. DB evidence: `lua_round_teams` had 13 rows total, 11 R1, 0 R2.
- **Non-existent column references in round timing** — `bot/ultimate_bot.py:1459` referenced `round_time_seconds` and `time_limit_seconds` which do not exist in the `rounds` table. Fixed to `actual_duration_seconds` and `time_limit` respectively (WS1-006 related).

### Recovered

- **Restored deleted planning docs** — Two critical execution-tracking documents were recovered from git history (deleted in commit `1c0ab8e` during Feb 15 cleanup):
  - `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md` — Live gameplay monitoring protocol
  - `docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md` — Sprint execution order with gates

### Added

- **Website Redesign — Analytics-First Platform**
  - **Component System** — Reusable UI components (`website/js/components.js`): PageHeader, KpiTile, ChartCard, TableCard, PodiumCard, ExpandableList, EmptyState, LoadingSkeleton
  - **Filter System** — Shared filter logic with URL sync (`website/js/filters.js`): GlobalFilterBar, period options (All Time, Season, 7d/14d/30d/90d, Custom), shareable URLs
  - **Hall of Fame Page** — 12 metric categories (Most Active, Wins, Damage, Kills, Revives, XP, Assists, Deaths, Selfkills, Full Selfkills, Consecutive Games, DPM) with podium display, expandable rankings, and time filters (`website/js/hall-of-fame.js`)
  - **Hall of Fame API** — `GET /api/hall-of-fame` with period filtering, 12 aggregate queries grouped by player_guid
  - **Trends API** — `GET /api/stats/trends` with time-series data for rounds, active players, kills, and map distribution
  - **Round Visualizer** — Interactive Chart.js round analytics replacing the static PNG gallery (`website/js/retro-viz.js`): 6 panels (Match Summary, Combat Radar, Top Fraggers, Damage Heatmap, Support Performance, Time Distribution), round picker dropdown, click-to-expand lightbox
  - **Round Viz API** — `GET /api/rounds/{id}/viz` returns full player stats for a round; `GET /api/rounds/recent` returns recent rounds for the picker
  - **Retro Viz Gallery (legacy)** — `GET /api/retro-viz/gallery` still available for PNG files
  - **Landing Page Insights** — New insights charts strip (rounds/day, active players/day, map distribution) with 14d/30d/90d toggle
  - **Retro Viz Teaser** — Teaser card on home page linking to gallery

### Changed

- **Navigation** — Removed standalone Sessions button from top-level nav (still accessible in Stats dropdown); added Hall of Fame as top-level nav item; added Retro Viz to Stats dropdown
- **Landing Page KPI Tiles** — Restyled to 3x2 grid with glass-panel cards, monospace numbers, colored accent borders
- **Landing Page Hero** — Updated tagline to "Track every frag, analyze every round, celebrate every victory"

- **Upload Library** — Community file sharing for configs (.cfg, .hud), archives (.zip, .rar), and clips (.mp4, .avi, .mkv)
  - OWASP-compliant file validation: extension allowlists, magic byte verification, size limits, SHA256 hashing
  - UUID-based storage outside web root with streaming upload and cleanup on failure
  - Browse/search/filter by category and tags, paginated results
  - Safe download headers (X-Content-Type-Options, CSP, X-Frame-Options), inline playback for MP4
  - Rate limit: 10 uploads/hour per user
  - Soft-delete (owner only)
  - Migration: `website/migrations/003_upload_library.sql` (uploads + upload_tags tables)
  - Backend: `website/backend/routers/uploads.py`, `website/backend/services/upload_store.py`, `website/backend/services/upload_validators.py`
  - Frontend: `website/js/uploads.js`, upload view in index.html

- **Daily Availability Poll + Notifications** — Discord daily "Who can play tonight?" system
  - Automated daily poll posting with ✅❌❔ reactions at configurable CET time
  - Reaction tracking via `on_raw_reaction_add/remove` (survives bot restarts)
  - Threshold notification: DMs opted-in players when YES count reaches N
  - Game-time reminders at configurable CET times (default 20:45, 21:00)
  - Per-user notification preferences via `!poll_notify` command and website UI
  - Website availability page with today's poll, response list, and history chart
  - Migration: `website/migrations/004_daily_availability_poll.sql` (daily_polls + poll_responses + poll_reminder_preferences)
  - Bot cog: `bot/cogs/availability_poll_cog.py`
  - Backend: `website/backend/routers/availability.py`
  - Frontend: `website/js/availability.js`, availability view in index.html

### Fixed

- **Discord login broken** — `https_only=True` in SessionMiddleware prevented cookies over HTTP; made configurable via `SESSION_HTTPS_ONLY` env var (defaults to false)
- **Admin panel hidden behind login** — Renamed to "System Overview", moved to public nav bar (visible without auth)
- **Voice monitoring lag** — Reduced voice recording interval from 60s to 300s, frontend live polling from 10s to 60s, live status refresh from 30s to 300s

### Docs

- **Upload Security Threat Model** — `docs/UPLOAD_SECURITY.md` with 5 attack surfaces, 15 existing mitigations documented with file references, 6 gaps identified, 30+ red-team test cases
- Slimmed `docs/CLAUDE.md` from 894 to ~186 lines; moved fix history here and known issues to `docs/KNOWN_ISSUES.md`
- Fixed factual drift: table count (7→36), cog count (14→20), core modules (12→18), Lua version (v1.3.0→v1.6.0), command count (63→80+), system status version (1.0.1→1.0.6)

---

## Detailed Fix History (Dec 2025)

### Fixed - Dec 14-17, 2025

- **Duplicate Player Entries in Rankings** - Player "olympus" appeared twice due to `GROUP BY player_guid, player_name`. Fixed to `GROUP BY player_guid` with `MAX(player_name)`. Files: session_stats_aggregator.py, session_graph_generator.py, session_view_handlers.py, session_data_service.py
- **Stats Command UnboundLocalError** - `!stats` crashed because `embed` variable was only created in cache MISS path. Fixed in leaderboard_cog.py
- **Find Player SQL Syntax Error** - `{ph}` placeholder instead of `?` in link_cog.py
- **Impossible Time Dead Values** - Players showing dead longer than played. Capped `time_dead` at `time_played` using `LEAST()` in SQL
- **Webhook Notification Security Hardening** (commit 3f15b1a)
- **Leaderboard Pagination & Session Graphs** - Fixed pagination, changed Denied Playtime graph to percentage
- **Incomplete local_stats Sync** - Added 7-day lookback window + `!sync_historical` command to prevent data loss during bot downtime

### Fixed - Dec 1, 2025

- **SSHMonitor Race Condition** - Disabled SSHMonitor auto-start; endstats_monitor now handles SSH + DB import + Discord posting as unified system
- **Channel Checks Silent Ignore** - Changed `is_public_channel()` / `is_admin_channel()` to silently return False
- **on_message Channel Filtering** - Uses `public_channels` as fallback when `bot_command_channels` not configured
- **Website Security Fixes** - HTML corruption, duplicate functions, SQL injection protection

### Fixed - Nov 2025

- **Gaming Session Detection Bug** - Use `WHERE round_id IN (session_ids_list)` instead of date filters
- **Player Duplication Bug** - Always `GROUP BY player_guid`, never by player_name
- **Duplicate Detection Bug** - Added `round_time` to duplicate check (not just map_name + round_number)
- **30-Minute vs 60-Minute Gap** - Changed all instances to 60 minutes

### Added - Nov 19, 2025

- **Achievement System** - Badge emojis for lifetime achievements. Files: player_badge_service.py, achievements_cog.py

---

### Added - Greatshot Enhancements

- **Cross-reference Phase 2-5** - Dramatically improved demo-to-stats matching
  - Multi-round matching: Handle R1+R2 in one demo file
  - Filename date extraction: Filter candidates by YYYY-MM-DD in filename
  - Player overlap validation: +20 confidence for 80%+ roster match
  - Stats comparison validation: Detect wrong matches via kill counts
  - **Result:** Match rate improved from 10-20% → 80-90%

- **Topshots API endpoints** - Leaderboards across all analyzed demos
  - `GET /api/greatshot/topshots/kills` - Demos with most total kills
  - `GET /api/greatshot/topshots/players` - Best individual performances
  - `GET /api/greatshot/topshots/accuracy` - Highest accuracy (min 10 kills)
  - `GET /api/greatshot/topshots/damage` - Most damage dealt
  - `GET /api/greatshot/topshots/multikills` - Best multi-kill highlights
  - Files: `website/backend/routers/greatshot_topshots.py`

### Changed - Greatshot

- **Cross-reference duration tolerance** - Increased from 5s to 30s
  - Accounts for warmup time in demos
  - Approximate tolerance: 15s → 60s
  - File: `website/backend/services/greatshot_crossref.py`

---

## [1.0.9] - 2026-02-08

### Security Fixes

- **CRITICAL: Added admin permission decorators** - Server control commands now require admin channel
  - `rcon`, `map_add`, `map_change`, `map_delete`, `kick`, `say` commands protected
  - File: `bot/cogs/server_control.py`

- **CRITICAL: Fixed file integrity verification crash** - Runtime AttributeError on every file check
  - Changed `tuple.get()` to index access `[0]`
  - File: `bot/automation/file_tracker.py`

- **HIGH: Fixed player GUID grouping** - Eliminated duplicate player entries in leaderboards
  - Changed 14 SQL queries from `GROUP BY player_name` to `GROUP BY player_guid`
  - Each player now appears once regardless of name changes
  - Files: `bot/cogs/leaderboard_cog.py`, `bot/services/session_view_handlers.py`

- **HIGH: Fixed XSS in website onclick handlers** - JavaScript context injection vulnerability
  - Changed `escapeHtml()` to `escapeJsString()` in 6 onclick attributes
  - Files: `website/js/awards.js`, `website/js/greatshot.js`

- **MEDIUM: Fixed SSH resource leak** - Connections not closed on exceptions
  - Added try/finally blocks to ensure cleanup
  - File: `bot/automation/ssh_handler.py`

- **MEDIUM: Sanitized error messages** - Database details no longer leaked to Discord
  - Added `sanitize_error_message()` to 8 error handlers
  - Files: `bot/cogs/matchup_cog.py`, `bot/cogs/analytics_cog.py`

- **MEDIUM: Fixed SQL limit injection** - Unvalidated limit parameter
  - Added validation (1-1000 range) with ValueError on invalid input
  - File: `bot/services/session_stats_aggregator.py`

### Added

- **Secrets management system** - Password rotation and generation tool
  - New tool: `tools/secrets_manager.py`
  - Generate passwords in format: `thunder-mountain-eagle1337`
  - Rotate database passwords, Discord tokens, SSH keys
  - Audit codebase for hardcoded secrets
  - Documentation: `docs/SECRETS_MANAGEMENT.md`
  - **Status**: Ready to use, NOT activated (passwords unchanged)

- **Security audit documentation**
  - Complete fix report: `docs/SECURITY_FIXES_2026-02-08.md`
  - Lists all 9 critical/high fixes applied
  - Testing recommendations and deployment checklist

### Changed

- **Admin channel configuration** - Added documentation to `.env.example`
  - Production: 822036093775249438
  - Bot-dev: 1424620551300710511, 1424620499975274496

### Fixed

- **Orphaned error log statement** - Removed misleading "Failed to post map summary" message
  - File: `bot/ultimate_bot.py` line 2284

### Documentation

- Added comprehensive security audit report
- Added secrets management usage guide
- Updated .env.example with admin channel IDs

---

## [1.0.8] - 2026-02-08

### Added

- **Greatshot highlight metadata enrichment** - Richer fragmovie scout data
  - Kill sequences with victim, weapon, headshot per kill
  - Victims list, weapons_used dict, headshot_weapons dict
  - Kill timing rhythm: kill_gaps_ms, avg_kill_gap_ms, fastest_kill_gap_ms
  - Attacker match stats (kills, deaths, KDR, damage, accuracy) on each highlight
  - New file: `greatshot/highlights/detectors.py` with 3 enrichment helpers

- **Player stats extraction from demos** - Match-level performance data
  - Extract player_stats from UDT matchStats.playerStats
  - Fallback to timeline-derived kills/deaths when UDT data unavailable
  - player_stats field added to AnalysisResult output
  - Files: `greatshot/scanner/api.py`, `greatshot/contracts/types.py`

- **Database cross-reference system** - Match demos to ET:Legacy stats rounds
  - NEW: `website/backend/services/greatshot_crossref.py`
  - Match by map (exact), duration (±5s), winner, scores
  - Confidence scoring: 30% map + 30% duration + 20% winner + 20% scores
  - Auto-crossref after analysis, store matched_round_id in metadata_json
  - Enrich with 16-field player stats from player_comprehensive_stats
  - Side-by-side comparison (demo kills vs DB kills/deaths/KDR/DPM)
  - GET /api/greatshot/{demo_id}/crossref endpoint
  - Files: `website/backend/routers/greatshot.py`, `website/backend/services/greatshot_jobs.py`

- **Frontend highlight detail expansion** - Rich scout-friendly UI
  - Kill sequence display (timestamp, victim, weapon, HS indicator)
  - Weapon badges with headshot weapon highlighting
  - Kill rhythm visualization (avg/fastest gap stats)
  - Attacker's overall match stats display
  - Database crossref panel: matched round, confidence, stats comparison table
  - Files: `website/js/greatshot.js`, `website/index.html`

- **Enhanced text reports** - Richer highlight metadata in reports
  - Show victims, weapons, kill rhythm in highlight listings
  - Player stats summary section (top 16 by kills)
  - File: `greatshot/scanner/report.py`

### Changed

- Highlight detection now passes player_stats for attacker_stats enrichment
- AnalysisResult.to_dict() now includes player_stats when available
- Greatshot jobs auto-crossref demos with ≥50% confidence

---

## [1.0.6] - 2026-02-07

### Added

- **Player analytics commands** - `!consistency`, `!map_stats`, `!playstyle`, `!awards`, `!fatigue`
  - New files: `bot/cogs/analytics_cog.py`, `bot/services/player_analytics_service.py`

- **Matchup analytics system** - `!matchup A vs B`, `!duo_perf`, `!nemesis`
  - Lineup vs lineup historical stats with confidence levels
  - Auto-records matchups when session results are saved
  - New files: `bot/cogs/matchup_cog.py`, `bot/services/matchup_analytics_service.py`
  - Database: `matchup_history` table with JSONB player stats

- **Map-based stopwatch scoring**
  - Session scores now count MAP wins, not round wins
  - `StopwatchScoringService.calculate_session_scores_with_teams()` for proper team-to-winner mapping
  - Full map breakdown with timing in `!last_session` embed
  - Tie handling: double fullhold = 1-1 (both teams defended)

- **Real-time team tracking**
  - Teams created on R1 import, updated as players join subsequent rounds
  - Supports 3v3 -> 4v4 -> 6v6 growth with correct team assignment
  - `gaming_session_id` column added to `session_teams` table

- **Lua webhook v1.6.0** - spawn/death tracking, safe gentity access (crash fix)
- **Proximity tracker v3** - crossfire detection, trade kill support
- **Endstats pagination view** - paginated round awards display
- **Round linker** - cross-references R1/R2 data with Lua webhook data
- **Server control cog** - RCON, server status, map management, player list
- **Website SPA overhaul** - sessions, matches, player profiles, leaderboards, admin panel, badges, proximity, season stats pages

### Fixed

- **Time dead calculation** - R2 `time_dead_ratio` was calculated against cumulative time; now uses `time_dead_minutes` directly (fixed ~15 min/session undercount)
- **GROUP BY player_name** in `player_analytics_service.py` - changed to `GROUP BY player_guid` with `MAX(player_name)` to prevent duplicate entries on name changes
- **Division by zero guard** in `matchup_analytics_service.py` - empty match list check before averaging
- **Surrender timing** - Lua webhook captures actual played time instead of full map duration from stats files

### Changed

- Lua webhook fields use `Lua_` prefix to distinguish from stats file data
- Website auth improvements and live-status updates
- API router and service layer updates for website

---

## [1.0.5] - 2026-01-25

### Added

- **Lua webhook v1.3.0** - pause event timestamps (`Lua_Pauses_JSON`), warmup end timestamp (`Lua_WarmupEnd`), timing legend in Discord embed
  - Database: `lua_pause_events` JSONB column

- **Lua webhook v1.2.0** - warmup phase tracking (`Lua_Warmup`, `Lua_WarmupStart`)
  - Database: `lua_warmup_seconds`, `lua_warmup_start_unix` columns

- **ET:Legacy server optimization** - CPU affinity, UDP buffer tuning

---

## [1.0.4] - 2026-01-22

### Added

- **Lua webhook real-time stats** - instant round notification from game server (~3s vs 60s SSH polling)
  - `stats_discord_webhook.lua` v1.1.0 on game server
  - Captures accurate timing, winner, team composition at round end
  - `lua_round_teams` table for cross-reference with stats file data
  - Debug timing logs comparing stats file vs Lua timing

### Fixed

- **Surrender timing bug** - stats files show full map duration on surrender; Lua captures actual played time
- **SSHHandler method name** - `list_files` -> `list_remote_files` in webhook file fetch

---

## [1.0.3] - 2026-01-14

### Added

- **EndStats processing** - parses `-endstats.txt` files for round awards and player VS stats
- **7 award categories** - Combat, Deaths & Mayhem, Skills, Weapons, Teamwork, Objectives, Timing
- **VS stats tracking** - player-vs-player kill/death records per round
- **Discord follow-up embeds** - awards posted automatically after round stats
- **3 new tables** - `round_awards`, `round_vs_stats`, `processed_endstats_files`

---

## [1.0.2] - 2025-12-04

### Added

- **WebSocket real-time push** - VPS notifies bot instantly when new stats files are written
- **Voice session logging** - track player voice channel activity
- **Round publisher service** - auto-post rich Discord embeds with all player stats after each round
- **Team suggestion commands** - `!suggest_teams`, `!balance_teams` for AI-powered team balancing

### Fixed

- SQL nosec comment appearing inside query string causing PostgreSQL syntax errors
- Command alias conflicts between team_builder and synergy_analytics cogs
- 12 queries using `{placeholders}` in regular strings instead of f-strings
- `kill_thie` -> `kill_thief` typo in session_embed_builder.py

---

## [1.0.1] - 2025-12-01

### Fixed

- **SSHMonitor race condition** - two monitoring systems competed for files, causing live Discord posting to fail. Disabled SSHMonitor auto-start; `endstats_monitor` now handles SSH + DB import + Discord posting as single system.
- **Channel permission checks** - silently return `False` instead of raising exceptions and sending error messages
- **on_message channel filtering** - uses `public_channels` config as fallback when `bot_command_channels` not set
- **Website HTML corruption** - fixed malformed document structure in `index.html`
- **Website JS duplicate functions** - fixed duplicate `loadLeaderboard()` declarations
- **Website SQL injection** - added `escape_like_pattern()` to API router

---

## [1.0.0] - 2025-11-20

### Added

- Achievement badge system (medic, engineer, sharpshooter, rambo, objective specialist)
- Custom display name system for linked Discord accounts
- Exact value labels on performance graphs
- Auto-posting shows all players with comprehensive stats

### Fixed

- Critical bug in `!list_players` command
- Codacy static analysis warnings

---

## [0.9.0] - 2025-11-18

Major production release. Migrated from SQLite to PostgreSQL.

### Added

- **6-layer data validation** - file integrity, duplicate prevention, schema validation, cross-field checks, transaction safety, DB constraints
- **Full automation** - SSH monitoring, auto-download, auto-import, auto-post
- **Voice-conditional SSH monitoring** - only checks when players in voice channels
- **Gaming session grouping** - 60-minute gap detection
- **Round 2 differential calculation** - subtracts R1 from cumulative R2 stats
- **PostgreSQL migration** - from SQLite to PostgreSQL 14
- **AI match predictions** - 4-factor algorithm (H2H, form, map performance, substitutions)
- **11 leaderboard categories** - K/D, DPM, accuracy, headshots, efficiency, etc.
- **Interactive account linking** - react with emojis to link Discord to game stats
- **Connection pooling** - asyncpg for high-performance async queries
- **TTL-based caching** - 5-minute cache for query results

### Fixed

- DPM calculations now use actual playtime instead of round duration
- Leaderboard queries properly filter R0 warmup rounds
- SSH monitor only checks last 24h on startup (not all historical files)
- Rate limiting, shell injection prevention, database SSL support

---

## [0.1.0] - 2025-10-15

### Added

- Initial release with basic Discord bot functionality
- SQLite database support
- Manual stats file import
- Player statistics commands (`!stats`, `!compare`)
- Basic leaderboard system
- Round and session tracking
- 53+ statistics tracked per player per round
