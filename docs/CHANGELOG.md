# Changelog

All notable changes to Slomix are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
