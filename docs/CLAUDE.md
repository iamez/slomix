# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **📝 Session Memory:** Check `.claude/memories.md` for recent session context, ongoing work, and things to remember across sessions.

---

# Slomix - ET:Legacy Discord Bot

**Version**: 1.0.5 (Updated: January 24, 2026)
**Project**: ET:Legacy Statistics Discord Bot
**Database**: PostgreSQL (primary), SQLite (fallback)
**Language**: Python 3.11+
**Discord.py**: Version 2.0+
**Status**: Production-Ready ✅

## Recent Updates (1.0.5)

- **Lua Webhook v1.3.0** - Enhanced timing capture from game server
  - Pause event timestamps (`Lua_Pauses_JSON`) - know exactly when each pause occurred
  - Warmup end timestamp (`Lua_WarmupEnd`) - when warmup phase ended
  - Timing legend in Discord embed explaining Playtime vs Warmup vs Wall-clock
  - Database: `lua_pause_events` JSONB column for queryable pause data
- **Lua Webhook v1.2.0** - Warmup phase tracking
  - `Lua_Warmup` - warmup duration in seconds
  - `Lua_WarmupStart` - Unix timestamp when warmup began
- **Field Naming Convention** - All webhook fields use `Lua_` prefix to distinguish from stats file

## Previous Updates (1.0.4)

- **Lua Webhook Real-Time Stats** - Instant round notification from game server (~3s vs 60s polling)
- **Surrender Timing Fix** - Accurate duration captured via Lua (stats files show wrong time on surrender)
- **Team Composition Capture** - Lua captures Axis/Allies player lists at round end
- **Pause Tracking** - New capability to track game pauses
- **lua_round_teams Table** - Separate storage for Lua-captured data (cross-reference/validation)
- **Debug Timing Logs** - Compares stats file vs Lua timing for every webhook-processed round

## Previous Updates (1.0.3)

- Configurable timing values (R1-R2 matching, grace period, session gap)
- SHA256 file integrity checking on import
- Cross-field data validation (headshots <= kills, etc.)
- CLAUDE.md files in all core directories

---

## 🤖 Claude Code Environment

### File Structure
```
/CLAUDE.md                    # Symlink → docs/CLAUDE.md (auto-loaded by Claude Code)
docs/CLAUDE.md                # Main documentation (this file)
.claude/
├── settings.json             # Project permissions (gitignored)
├── settings.local.json       # Local permissions (gitignored)
└── memories.md               # Session memory (gitignored)
~/.claude/
├── settings.json             # Global user settings
└── mcp.json                  # MCP server configurations
```

### MCP PostgreSQL Server
Direct database access via MCP tools (`mcp__db__execute_sql`, `mcp__db__search_objects`):
```bash
# Configured via:
claude mcp add --transport stdio --scope user db -- npx -y @bytebase/dbhub \
  --dsn "postgresql://etlegacy_user:etlegacy_secure_2025@localhost:5432/etlegacy"
```

### User Preferences
- **Model**: Opus (claude-opus-4-5-20251101)
- **Default Mode**: Plan (requires approval before edits)
- **Output Style**: Explanatory (educational insights enabled)

### Related Projects
See `docs/WEBSITE_CLAUDE.md` and `docs/PROXIMITY_CLAUDE.md` for sister project documentation.

---

## ⚠️ CRITICAL RULES - READ FIRST ⚠️

### 🗄️ DATABASE: PostgreSQL (NOT SQLite!)

**IMPORTANT**: Bot migrated from SQLite to PostgreSQL in December 2025

**Database Details**:

- **Type**: PostgreSQL 14 (system service)
- **Database**: etlegacy
- **User**: etlegacy_user
- **Password**: etlegacy_secure_2025 (in .env)
- **Host**: localhost:5432
- **Data Location**: `/var/lib/postgresql/14/main/` (managed by PostgreSQL service)
- **Service**: `postgresql.service` (systemd)
- **Old SQLite**: `bot/database.db` - NO LONGER EXISTS

**Critical Differences**:

- ✅ Use `postgresql_database_manager.py` for ALL database operations (NOT `database_manager.py`)
- ✅ Use `?` for query parameters (NOT `{ph}` placeholders)
- ✅ Backups: `pg_dump` to `.sql` files (NOT `.db` files)
- ✅ Schema: `/bot/schema_postgresql.sql` (NOT `schema.sql`)
- ❌ NEVER try to read/write `bot/database.db` - it doesn't exist
- ❌ NEVER use SQLite syntax (`INSERT OR REPLACE`, `AUTOINCREMENT`, etc.)

**See**: `docs/POSTGRESQL_MIGRATION_INDEX.md` for full migration details

---

### 🚨 BRANCH POLICY (Version 1.0+)

**NEVER COMMIT DIRECTLY TO MAIN!**

1. ✅ **ALWAYS** create a feature branch for changes
2. ✅ **ALWAYS** use descriptive branch names (e.g., `feature/new-command`, `fix/session-bug`)
3. ✅ **ALWAYS** test thoroughly in the branch before merging
4. ❌ **NEVER** push directly to `main` branch
5. ❌ **NEVER** use `git commit` without being on a feature branch

**Workflow:**

```bash
# Create and switch to feature branch
git checkout -b feature/my-feature-name

# Make changes, test, commit
git add <files>
git commit -m "description"
git push origin feature/my-feature-name

# When ready: merge via pull request or manually
git checkout main
git merge feature/my-feature-name
git push origin main
```python

### Database Operations

1. ✅ **ALWAYS** use `postgresql_database_manager.py` for ALL database operations (NOT `database_manager.py`)
2. ✅ **ALWAYS** use `gaming_session_id` for session queries (NOT dates)
3. ✅ **ALWAYS** group by `player_guid` (NOT `player_name`)
4. ✅ **ALWAYS** use 60-minute gap threshold for sessions (NOT 30!)
5. ✅ **ALWAYS** use async database calls via `database_adapter.py` in Cogs
6. ❌ **NEVER** recalculate R2 differential (parser handles it correctly)
7. ❌ **NEVER** assume data corruption without checking raw files
8. ❌ **NEVER** create new import/database scripts (use `postgresql_database_manager.py`)

### Terminology (MUST USE CORRECTLY)

- **ROUND** = One stats file (R1 or R2), one half of a match
- **MATCH** = R1 + R2 together (one complete map played)
- **GAMING SESSION** = Multiple matches within 60-minute gaps

### System Architecture

```yaml

ET:Legacy Game Server → SSH Monitor → Parser → PostgreSQL → Discord Bot → Users
                        (60s poll)   (53+ fields)  (7 tables)   (70+ commands)

```python

### Critical Architecture Patterns

#### SSH Monitoring - Single System Design (Dec 2025 Fix)

**Only `endstats_monitor` task loop handles SSH operations.** SSHMonitor service is initialized but NOT auto-started.

- **endstats_monitor** (in `ultimate_bot.py` lines 551-568): SSH check → Download → DB import → Discord posting
- **SSHMonitor** (disabled): Previously caused race condition where files marked "processed" before Discord posting

**If live posting stops:** Check that SSHMonitor isn't being auto-started. This is a known race condition fix.

#### Database Adapter Pattern

- **Active abstraction:** `bot/core/database_adapter.py` provides unified async interface
- **PostgreSQL is primary:** Configured via `.env` or `bot_config.json`
- **Schema validation critical:** Bot validates 53-column schema on startup - wrong schema = silent failures

#### Stats Import Pipeline (4 Stages + Lua Webhook)

1. **File Generation** → ET:Legacy server writes `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`
2. **Parsing** → `bot/community_stats_parser.py` extracts 53+ fields per player
3. **Database Import** → `postgresql_database_manager.py` with:
   - Filename-based duplicate detection (unique constraint)
   - SHA256 hash stored for integrity verification
   - Cross-field validation (headshots <= kills, etc.)
   - Transaction safety (atomic commits)
4. **Bot Access** → Cogs query via `database_adapter.py` with 5-min cache (`bot/core/stats_cache.py`)

**Critical:** Round 2 files contain CUMULATIVE stats - parser calculates differentials by subtracting Round 1 values.

#### Lua Webhook Real-Time Notification (Jan 2026)

**Real-time stats notification system, fixing surrender timing bug:**

```
Game Server Lua → POST to Discord Webhook → Bot sees message → SSH fetch → Override timing
```

- **Lua Script**: `vps_scripts/stats_discord_webhook.lua` (v1.3.0) runs on game server
- **Trigger**: Gamestate transition PLAYING → INTERMISSION
- **Data Captured**: Accurate timing, winner, pause events, warmup duration, team composition
- **Storage**: `lua_round_teams` table (separate from stats file data)
- **Purpose**: Fixes surrender timing bug (stats files show full map time on surrender)

**Webhook Fields (v1.3.0):**
| Field | Description |
|-------|-------------|
| `Lua_Playtime` | Actual gameplay (pauses excluded) |
| `Lua_Warmup` | Pre-round warmup duration |
| `Lua_Pauses` | Count + total duration |
| `Lua_Pauses_JSON` | Individual pause timestamps (v1.3.0) |
| `Lua_WarmupStart` / `Lua_WarmupEnd` | Warmup phase timestamps |
| `Lua_RoundStart` / `Lua_RoundEnd` | Gameplay timestamps |
| `Lua_EndReason` | objective/surrender/time_expired |

**Database columns (`lua_round_teams`):**
- `lua_warmup_seconds`, `lua_warmup_start_unix` (v1.2.0+)
- `lua_pause_events` JSONB (v1.3.0+)

**Why needed:** Stats files have a bug where surrenders show full map duration (e.g., 20 min) instead of actual played time (e.g., 8 min). Lua captures the exact moment the round ends.

**Cross-reference:** Both sources stored for data health validation:
- `rounds` table: Stats file data
- `lua_round_teams` table: Lua webhook data
- Compare timing to detect/validate surrender scenarios

**See:** `docs/reference/TIMING_DATA_SOURCES.md` for complete timing documentation.

#### Timing Configuration (Dec 2025 Update)

| Setting | Default | Purpose |
|---------|---------|---------|
| `SESSION_GAP_MINUTES` | 60 | Minutes of inactivity before new session |
| `ROUND_MATCH_WINDOW_MINUTES` | 45 | Max gap for R1-R2 matching |
| `MONITORING_GRACE_PERIOD_MINUTES` | 45 | Keep checking after voice empties |

These values work together - ensure `ROUND_MATCH_WINDOW_MINUTES` < `SESSION_GAP_MINUTES`.

---

## 🎉 Version 1.0 Release (November 20, 2025)

### Release Milestone

**Slomix** is now officially production-ready and fully documented!

### What's Included in 1.0

- ✅ **63 Discord Commands** - Complete bot functionality
- ✅ **6-Layer Data Validation** - ACID-compliant PostgreSQL pipeline
- ✅ **Full Automation** - SSH monitoring, voice detection, auto-posting
- ✅ **Achievement System** - Player badges and lifetime stats
- ✅ **Advanced Team Detection** - Accurate team-swap handling
- ✅ **Differential R2 Calculation** - Smart Round 2 stat parsing
- ✅ **Gaming Session Tracking** - 60-minute gap detection
- ✅ **Comprehensive Documentation** - Complete technical docs

### Repository Cleanup (Nov 20, 2025)

- 🧹 Removed **~6.5 GB** of development artifacts from GitHub
- 📁 Organized all documentation into `/docs/` structure
- 🛡️ Updated `.gitignore` to prevent future clutter
- 📚 Created comprehensive documentation index
- ✨ Clean root directory with only essential files

### Documentation Structure

```text

docs/
├── SAFETY_VALIDATION_SYSTEMS.md
├── CHANGELOG.md
├── DATA_PIPELINE.md
├── FIELD_MAPPING.md
├── COMMANDS.md
├── SYSTEM_ARCHITECTURE.md
├── TECHNICAL_OVERVIEW.md
├── DEPLOYMENT_CHECKLIST.md
├── FRESH_INSTALL_GUIDE.md
├── AI_COMPREHENSIVE_SYSTEM_GUIDE.md
├── archive/ (historical documentation)
└── [30+ additional system docs]

```python

---

## Known Issues (Unsolved)

### Time Dead Anomalies (Dec 16, 2025) - Low Priority

**Issue**: 13 player records show `time_dead_minutes > time_played_minutes` by small margins (0.06 to 2.06 minutes).

**Investigation**: Comprehensive investigation revealed:

- Parser correctly uses round duration for stopwatch mode (design intent)
- DPM calculations are correct (confirmed by user)
- Database rebuild reduced corruption from 43 records (100+ min errors) to 13 records (0.06-2.06 min errors)
- Field mappings verified correct: tab_fields[22] = time_played, [25] = time_dead_ratio, [26] = time_dead_minutes

**Possible Causes**:

1. Rounding differences between Lua (`roundNum(value, 1)`) and Python (`int(minutes * 60)`)
2. Edge cases: players joining mid-round or disconnecting
3. Potential Lua bug in `death_time_total` accumulation
4. Acceptable tolerance given system complexity

**Status**: Marked as **unsolved** - low priority. System works well enough for production use.

**Reference**: Investigation documented in `/home/samba/.claude/plans/sorted-wandering-horizon.md`

**Recommendation**: Accept current state or investigate Lua script if time permits in future.

---

## Recent Major Fixes (Dec 2025)

### 1. Duplicate Player Entries in Rankings (FIXED Dec 14-15) 🆕

- **Problem**: Player "olympus" appeared twice in `!last_session` rankings (positions 6 and 7) due to name aliases.
- **Root Cause**: SQL queries used `GROUP BY player_guid, player_name`, creating separate groups when same player had different names.
- **Fix**: Changed all GROUP BY clauses to use only `player_guid` and select name with `MAX(player_name)`.
- **Files**:
  - `bot/services/session_stats_aggregator.py` (4 queries fixed)
  - `bot/services/session_graph_generator.py` (1 query fixed)
  - `bot/services/session_view_handlers.py` (7 queries fixed)
  - `bot/services/session_data_service.py` (1 query fixed)

### 2. Stats Command UnboundLocalError (FIXED Dec 14-15) 🆕

- **Problem**: `!stats` command crashed with "UnboundLocalError: local variable 'embed' referenced before assignment".
- **Root Cause**: `embed` variable created inside cache MISS block but referenced outside for both HIT and MISS paths.
- **Fix**: Moved embed creation and formatting code outside the if/else blocks to run for both cache paths.
- **Location**: `bot/cogs/leaderboard_cog.py` lines 316-440

### 3. Find Player SQL Syntax Error (FIXED Dec 14-15) 🆕

- **Problem**: `!find_player` command crashed with "syntax error at or near {".
- **Root Cause**: SQL queries used `{ph}` placeholder instead of PostgreSQL `?` parameter syntax.
- **Fix**: Replaced `{ph}` with `?` in 2 SQL queries.
- **Location**: `bot/cogs/link_cog.py` lines 334 and 348

### 4. Impossible Time Dead Values (FIXED Dec 14-15) 🆕

- **Problem**: Players showing dead longer than they played (e.g., qmr: 96:41 played, 💀131:45 dead).
- **Root Cause**: ET:Legacy Lua stats script has bug tracking `death_time_total`, causing impossible values like 1255% dead ratio. Affects 43 player records across 33 rounds.
- **Fix**: Cap `time_dead` at `time_played` per-round before aggregating using PostgreSQL `LEAST()` function.
- **Files**:
  - `bot/services/session_stats_aggregator.py` lines 54-59
  - `bot/services/session_graph_generator.py` lines 142-147
- **SQL Logic**: `LEAST(time_played_minutes * time_dead_ratio / 100.0 * 60, time_played_seconds)` caps per-round death time.

### 5. Webhook Notification Security Hardening (FIXED Dec 14) 🆕

- **Commit**: 3f15b1a - Security: Webhook notification hardening
- Enhanced security for webhook notification system.

### 6. Leaderboard Pagination & Session Graphs (FIXED Dec 14) 🆕

- **Commit**: 065d01b - Change Denied Playtime graph to show percentage instead of seconds
- **Commit**: ba8e89e - Fix leaderboard pagination, expand help command, improve session graphs
- Improved graph visualizations and command help.

### 7. Incomplete local_stats Sync (FIXED Dec 17) 🆕

- **Problem**: Bot's startup time filter skipped ALL files created before bot startup, causing incomplete local_stats mirror and data loss during bot downtime.
- **Root Cause**: `file_tracker.py` had hard cutoff at bot startup time - files created while bot offline were never downloaded.
- **Fix**: Implemented 7-day lookback window + new !sync_historical command:
  - **Lookback Window**: Bot now processes files from 7 days BEFORE startup (configurable via `STARTUP_LOOKBACK_HOURS`)
  - **!sync_historical Command**: Admin command to download missing files from game server to local_stats/
- **Files Modified**:
  - `bot/automation/file_tracker.py` - Lookback window implementation
  - `bot/config.py` - Added STARTUP_LOOKBACK_HOURS config (default: 168h = 7 days)
  - `bot/cogs/sync_cog.py` - New !sync_historical command
  - `.env.example` - Added STARTUP_LOOKBACK_HOURS documentation
- **Usage**: `!sync_historical` or `!sync_historical 90` (check last 90 days)
- **Result**: local_stats maintained as complete mirror, database rebuilds work correctly, no data loss from bot restarts

### 8. SSHMonitor Race Condition (FIXED Dec 1)

- **Problem**: Two monitoring systems (SSHMonitor + endstats_monitor) competed for files. SSHMonitor processed files first, marking them as "already processed" before Discord posting could occur.
- **Fix**: Disabled SSHMonitor auto-start. endstats_monitor now handles SSH + DB import + Discord posting as single unified system.
- **Location**: `bot/ultimate_bot.py` lines 551-568

### 2. Channel Checks Silent Ignore (FIXED Dec 1) 🆕

- **Problem**: `is_public_channel()` and `is_admin_channel()` raised exceptions and sent error messages when commands used in wrong channels.
- **Fix**: Changed to silently `return False` instead of raising `ChannelCheckFailure`.
- **Location**: `bot/core/checks.py`

### 3. on_message Channel Filtering (FIXED Dec 1) 🆕

- **Problem**: Bot responded to commands in wrong channels when `bot_command_channels` was not configured.
- **Fix**: Now uses `public_channels` config as fallback for channel filtering.
- **Location**: `bot/ultimate_bot.py` `on_message` handler

### 4. Website Security Fixes (FIXED Dec 1) 🆕

- Fixed HTML corruption in `website/index.html`
- Fixed duplicate function declarations in `website/js/app.js`
- Added SQL injection protection via `escape_like_pattern()` in `website/backend/routers/api.py`

### 5. Gaming Session Detection Bug (FIXED Nov 3)

- **Problem**: Date-based queries included orphan rounds
- **Fix**: Use `WHERE round_id IN (session_ids_list)` instead of date filters

### 2. Player Duplication Bug (FIXED Nov 3)

- **Problem**: Name changes created duplicate entries
- **Fix**: Always `GROUP BY player_guid`, never by player_name

### 3. Duplicate Detection Bug (FIXED Nov 19)

- **Problem**: Same map played twice in one session → second play skipped
- **Fix**: Added `round_time` to duplicate check (not just map_name + round_number)
- **Location**: `bot/ultimate_bot.py` line 1337

### 4. 30-Minute vs 60-Minute Gap (FIXED Nov 4)

- **Problem**: Used 30-minute threshold instead of 60
- **Fix**: Changed all instances to 60 minutes

### 5. Achievement System (ADDED Nov 19)

- **Feature**: Badge emojis for lifetime achievements
- **Files**: `bot/services/player_badge_service.py`, `bot/cogs/achievements_cog.py`
- **Display**: Shown in `!last_session`, `!leaderboard`, `!badges`
- **Thresholds**: Rebalanced Nov 19 (kills 1K+, games 50+, K/D 0.0-3.0)

---

## Key Database Schema

### rounds table

- `gaming_session_id` - Groups continuous play (60-minute gaps)
- `match_id` - Links R1+R2 (format: YYYY-MM-DD-HHMMSS)
- `round_number` - 1 or 2 (NOT 0 - no warmup rounds)
- `round_date`, `round_time` - From filename

### player_comprehensive_stats (53 columns)

- Primary keys: `player_guid` (string), `round_id` (foreign key)
- Combat: kills, deaths, damage_given, damage_received, accuracy
- Weapons: headshots, headshot_kills, gibs
- Support: revives_given, times_revived, ammo_given, health_given
- Objectives: objectives_stolen, objectives_returned
- Demolition: dynamites_planted, dynamites_defused
- Performance: efficiency, kdr, skill_rating, dpm (damage per minute)
- Time: time_played_seconds (source of truth)
- Team: team ('axis'/'allies'), team_detection_confidence

### weapon_comprehensive_stats

- Per-weapon breakdown: weapon_name, kills, deaths, headshots, hits, shots, accuracy
- Linked by round_id and player_guid

---

## Common Pitfalls (AVOID THESE)

### ❌ DON'T

1. Use date-based queries for gaming sessions (multiple sessions per day possible)
2. Group by player_name (name changes break aggregations)
3. Assume `headshots` = `headshot_kills` (different stats, both correct)
4. Try to recalculate R2 differential (parser output is correct)
5. Use 30-minute gap threshold (use configurable values in config.py)
6. Modify processed_files manually (SHA256 hash stored for integrity verification)
7. **NEVER provide destructive commands unprompted** - No `rm`, `del`, `Remove-Item`, `DROP TABLE`, etc. Report findings, let user decide what to delete

### ✅ DO

1. Use `gaming_session_id` for session queries
2. Group by `player_guid` for player aggregations
3. Read `AI_COMPREHENSIVE_SYSTEM_GUIDE.md` before claiming bugs
4. Check raw stats files when investigating data issues
5. Use transactions for all database imports
6. Test with midnight crossover scenarios

---

## Common Development Tasks

### Building & Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python -m bot.ultimate_bot

# Or with systemd service
sudo systemctl start etlegacy-bot
sudo systemctl status etlegacy-bot
```text

### Database Operations

```bash
# All database operations use this ONE tool:
python postgresql_database_manager.py

# Available options:
# 1 - Create fresh database (initialize schema)
# 2 - Import all files from local_stats/
# 3 - Rebuild from scratch (wipes + re-imports)
# 4 - Fix specific date range
# 5 - Validate database (7-check validation)
# 6 - Quick test (10 files)

# Connect to PostgreSQL directly
PGPASSWORD='etlegacy_secure_2025' psql -h localhost -U etlegacy_user -d etlegacy

# Common queries
psql -d etlegacy -c "SELECT COUNT(*) FROM rounds;"
psql -d etlegacy -c "SELECT MAX(gaming_session_id) FROM rounds;"
```text

### Testing

```bash
# No formal test suite - use validation scripts:
python test_phase1_implementation.py    # Schema validation
python test_parser_fixes.py             # Parser accuracy
python validate_nov2_complete.py        # Data integrity

# Test parser with specific file
python bot/community_stats_parser.py local_stats/sample-round-1.txt

# Test Discord bot commands (in Discord)
!ping                # Check latency
!health              # System health check
!last_session        # Latest gaming session
```text

### Deployment

```bash
# Automated installation (recommended)
sudo ./install.sh --full --auto           # Full VPS setup
./install.sh --env-only                   # Dev environment only

# Manual deployment
cp .env.example .env
# Edit .env with your settings
nano .env
python postgresql_database_manager.py    # Create DB (option 1)
python -m bot.ultimate_bot               # Run bot
```python

## File Locations

### Core Files (MUST UNDERSTAND)

- `bot/ultimate_bot.py` (4,990 lines) - Main bot entry point, 14 Cogs, on_ready handler
- `bot/community_stats_parser.py` (1,036 lines) - R1/R2 differential parser
- `postgresql_database_manager.py` (1,573 lines) - **ONLY tool for DB operations**
- `bot/core/database_adapter.py` - Async PostgreSQL/SQLite abstraction
- `bot/core/stats_cache.py` - 5-minute TTL query cache

### 14 Cogs (Command Modules)

- `bot/cogs/last_session_cog.py` - Session stats & summaries (!last_session)
- `bot/cogs/leaderboard_cog.py` - Rankings (!top_dpm, !top_kd, etc.)
- `bot/cogs/stats_cog.py` - Player statistics (!stats <player>)
- `bot/cogs/admin_cog.py` - Admin commands (!sync_all, !rebuild_sessions)
- `bot/cogs/link_cog.py` - Account linking (!link, !unlink)
- `bot/cogs/session_management_cog.py` - Session operations
- `bot/cogs/team_cog.py` - Team statistics
- `bot/cogs/predictions_cog.py` - Match predictions (7 user commands)
- `bot/cogs/admin_predictions_cog.py` - Prediction admin tools (5 admin commands)
- Plus 5 more specialized cogs

**Always add new commands to appropriate Cog** - never add to `ultimate_bot.py` directly.

### 12 Core Modules (Business Logic)

- `bot/core/team_manager.py` - Team detection orchestration
- `bot/core/advanced_team_detector.py` - Snapshot-based detection
- `bot/core/substitution_detector.py` - Mid-game player switches
- `bot/core/achievement_system.py` - Badge awards
- `bot/core/database_adapter.py` - DB abstraction layer
- `bot/core/stats_cache.py` - 5-minute TTL caching
- Plus 6 more modules (season, pagination, checks, utils, etc.)

### Services Layer

- `bot/services/prediction_engine.py` (540 lines) - AI prediction engine
- `bot/services/round_publisher_service.py` - Auto-post round stats
- `bot/services/voice_session_service.py` - Voice logging & team detection
- `bot/services/session_stats_aggregator.py` - Statistical aggregations
- `bot/services/session_graph_generator.py` - Performance graphs
- `bot/services/player_badge_service.py` - Achievement badges
- `bot/services/player_formatter.py` - Global player display formatting

### Documentation (READ THESE FIRST)

- `docs/CLAUDE.md` - This file (AI assistant guide)
- `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` - Complete system reference
- `docs/SAFETY_VALIDATION_SYSTEMS.md` - 6-layer validation system
- `docs/DATA_PIPELINE.md` - Complete data pipeline
- `docs/ROUND_2_PIPELINE_EXPLAINED.txt` - Differential calculation logic
- `docs/COMMANDS.md` - All 70+ bot commands
- `docs/archive/` - Historical bug fixes and audits

---

## Environment (.env required)

```bash
# Discord
DISCORD_BOT_TOKEN=...
GUILD_ID=...
STATS_CHANNEL_ID=...

# Database
DATABASE_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=etlegacy_secure_2025

# SSH Automation
SSH_ENABLED=true
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot

# Voice Automation
AUTOMATION_ENABLED=true
GAMING_VOICE_CHANNELS=...
SESSION_START_THRESHOLD=6
SESSION_END_THRESHOLD=2
SESSION_END_DELAY=180
```python

---

## High-Level Architecture

### Cog-Based Modular Design

The bot follows Discord.py's **Cog pattern** for separation of concerns:

```python

bot/ultimate_bot.py (Main Entry Point)
├── Loads 14 Cogs from bot/cogs/
├── Initializes database adapter (async PostgreSQL/SQLite)
├── Sets up 5-minute TTL cache (stats_cache.py)
├── Validates 53-column schema on startup
└── Runs event loops (on_ready, on_message, endstats_monitor)

bot/cogs/ (Command Modules)
├── Each Cog handles specific command domain
├── Uses database_adapter.py for async DB queries
├── Uses stats_cache.py for query caching
└── Never add commands directly to ultimate_bot.py

bot/core/ (Business Logic Layer)
├── Team detection (5 modules work together)
├── Achievement system (badge awards)
├── Season management
├── Pagination utilities
└── Shared utilities

bot/services/ (Service Layer)
├── Prediction engine (AI match predictions)
├── Round publisher (auto-post to Discord)
├── Voice session service (team detection from voice)
├── Stats aggregation (session statistics)
└── Graph generation (performance visualizations)

```text

### Round 2 Differential Calculation (CRITICAL)

**Problem:** ET:Legacy Round 2 stats files show **cumulative totals** (R1 + R2), not R2-only performance.

**Solution:** Parser automatically:

1. Detects Round 2 files by filename pattern `*-round-2.txt`
2. Searches for matching Round 1 file (same map, same day)
3. **Rejects Round 1 files with >60min time gap** (different gaming session)
4. Calculates R2-only stats: `R2_stat = R2_cumulative - R1_stat`

**Example:**

```sql

Round 1 (21:31): Player vid = 20 kills
Round 2 (23:41): Stats file = 42 kills (cumulative)
Time gap: 5.8 minutes ✅ (same session)

Parser calculates: R2 kills = 42 - 20 = 22 kills (correct!)

If Round 1 was from 2 hours earlier:
Time gap: 135 minutes ❌ (rejected - different session)
Parser finds correct Round 1 from 5 minutes earlier instead.

```python

**Never treat R2 stats as standalone** - they are always differential calculations.

### Bot Startup Sequence (Debug Reference)

1. `bot/logging_config.py` - Sets up logging to `logs/` directory
2. `bot/config.py` - Loads `.env` or `bot_config.json` (env vars take precedence)
3. Schema validation - `validate_database_schema()` checks for 53 columns
4. Cog loading - Loads 14 cogs (failure = missing dependency or syntax error)
5. Cache priming - `stats_cache.py` initializes 5-min TTL cache
6. Ready event - `on_ready()` logs startup, begins monitoring loops

**If bot won't start:** Check `logs/bot.log` for schema mismatch or cog load errors.

---

## Quick Command Reference

### Most Used Bot Commands

- `!last_session` - Show latest gaming session stats (main feature)
- `!last_session graphs` - Performance graphs for session
- `!stats <player>` - Individual player lifetime stats
- `!stats @discord_user` - Stats for linked Discord account
- `!top_dpm` - Damage per minute rankings
- `!top_kd` - K/D ratio leaderboard
- `!predictions` - View recent match predictions
- `!link` - Link Discord account to player GUID
- `!health` - System health check
- `!admin sync_all` - Sync all unprocessed files from VPS
- `!admin sync_historical` - Download missing files to local_stats/ (complete mirror)

### PostgreSQL Commands (Direct Access)

```bash
# Connect to database
PGPASSWORD='etlegacy_secure_2025' psql -h localhost -U etlegacy_user -d etlegacy

# Common diagnostic queries
SELECT COUNT(*) FROM rounds;
SELECT MAX(gaming_session_id) FROM rounds;
SELECT * FROM rounds ORDER BY id DESC LIMIT 5;

# Check for duplicate player entries (should use player_guid)
SELECT player_guid, COUNT(*) FROM player_comprehensive_stats
GROUP BY player_guid, player_name HAVING COUNT(*) > 1;

# Verify processed files
SELECT COUNT(*) FROM processed_files WHERE success = true;
```

---

## System Status (Version 1.0.1)

✅ **Parser**: 100% functional, R2 differential validated
✅ **Database**: PostgreSQL, no corruption, 100% accurate
✅ **Bot Commands**: All 63 commands functional
✅ **SSH Monitoring**: endstats_monitor handles all SSH operations (SSHMonitor disabled)
✅ **Live Posting**: Fixed - endstats_monitor posts to Discord after DB import
✅ **Channel Checks**: Silent ignore for wrong channels (no error messages)
✅ **Duplicate Detection**: Fixed (includes round_time)
✅ **Gaming Session Logic**: Fixed (60-minute gaps, handles midnight)
✅ **Player Aggregation**: Fixed (uses player_guid)
✅ **Achievement System**: Active, rebalanced thresholds
✅ **Automation**: Voice channel monitoring + scheduled tasks
✅ **Lua Webhook**: Real-time stats notification, surrender timing fix (branch: feature/lua-webhook-realtime-stats)
✅ **Documentation**: Complete and organized in /docs/
✅ **Repository**: Clean and maintainable (50-100 MB)
✅ **Website**: HTML/JS/SQL injection fixes applied
✅ **Production Ready**: Fully tested and validated

---

## Before Making Changes

1. Read `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` for full context
2. Check recent commits and `docs/archive/` for historical fixes
3. Understand current implementation completely
4. Identify root cause, not symptoms
5. Test with actual data, especially edge cases:
   - Midnight crossovers
   - Name changes
   - Multiple sessions per day
   - Same map played twice

---

## Maintenance Guidelines (Version 1.0+)

### Repository Cleanliness

- ✅ Keep root directory minimal (12-15 files only)
- ✅ All documentation goes in `/docs/`
- ✅ All bot code goes in `/bot/`
- ❌ Never commit: logs, backups, test scripts, database files
- 📖 See repository maintenance guide for details

### Before Committing

1. **Ensure you're on a feature branch** (NOT main!)
2. Check `git status` - ensure no trash files
3. Review `git diff --cached --name-only`
4. Add files individually, not with `git add -A`
5. Update `docs/CHANGELOG.md` for significant changes
6. Test thoroughly before pushing
7. Create pull request or merge only when tested

---

**Version**: 1.0.5
**Release Date**: January 24, 2026
**Last Updated**: 2026-01-26
**Schema Version**: 2.0
**Repository Size**: ~50-100 MB (cleaned)
**Status**: Production-ready, fully documented, maintainable ✅
