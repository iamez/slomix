# 📅 CHANGELOG - ET:Legacy Stats Bot

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Planned
- Enhanced session summary with detailed statistics
- Multiple sessions per day support
- Timezone configuration in .env
- Player chemistry analytics
- Team composition analytics

---

## [3.0.1] - 2025-10-07

### Fixed - Database Rebuild Process & session_teams Setup
**What Happened**: User accidentally used wrong schema tool (60 cols instead of 53), required complete database deletion and rebuild. Also discovered session_teams table was missing (causing bot warning). Created and populated session_teams for Oct 2nd session with real team names.

**The Loop**: Multiple database rebuild attempts using wrong tool before discovering the issue. Classic "got ourselves into trouble and deleted everything and had so much trouble getting back up" situation.

**Files Created**:
- `tools/update_team_names.py` - Team name mapper script
- `comprehensive_audit.py` - System diagnostic tool
- `check_current_db.py` - Quick database schema checker
- `docs/OCT7_DATABASE_REBUILD_JOURNEY.md` - Complete troubleshooting story (500+ lines)
- `docs/OCT7_FINAL_STATUS.md` - Final status report

**Impact**:
- ✅ Database rebuilt with correct 53-column schema
- ✅ All 1,862 sessions reimported successfully (100% success rate)
- ✅ session_teams table created and populated (20 records)
- ✅ Bot now shows real team names (puran vs insAne)
- ✅ No more "hardcoded teams not found" warning
- ✅ Comprehensive system audit passed (17 successes, 3 warnings, 0 critical issues)

**Lessons Learned**:
- ❌ DON'T USE `tools/create_fresh_database.py` for bot deployments (creates 60 columns)
- ✅ ALWAYS USE `create_unified_database.py` for bot deployments (creates 53 columns)
- session_teams is critical for accurate team tracking in multi-round sessions
- Three-step workflow required: create table → populate data → update team names
- Bot restart required after session_teams changes (loads at startup, not dynamically)

**Documentation**: See `docs/OCT7_DATABASE_REBUILD_JOURNEY.md` for complete story

---

## [3.0.0] - 2025-10-06

### Added - Hybrid File Processing System
**Why**: User had existing local files from manual imports. Bot needed to avoid re-downloading and re-importing them.

**What Changed**:
- Added `processed_files` table to database (7 columns)
- Added 5 new helper methods to `UltimateETLegacyBot`:
  - `should_process_file()` - 4-layer smart check
  - `_is_in_processed_files_table()` - Check persistent table
  - `_session_exists_in_db()` - Check sessions table
  - `_mark_file_processed()` - Track processing results
  - `sync_local_files_to_processed_table()` - Auto-sync on startup
- Updated `endstats_monitor()` to use new smart checking logic
- Updated `setup_hook()` to call sync on startup
- Updated `initialize_database()` to verify processed_files table

**Files Created**:
- `add_processed_files_table.py` - Migration script
- `verify_processed_files_table.py` - Verification script
- `docs/HYBRID_IMPLEMENTATION_SUMMARY.md` - User guide
- `docs/HYBRID_APPROACH_COMPLETE.md` - Technical docs

**Impact**: 
- ✅ No re-downloads of existing files
- ✅ No re-imports of existing sessions
- ✅ Persistent tracking survives bot restarts
- ✅ Fast performance (in-memory cache checked first)

**Documentation**: See `docs/HYBRID_IMPLEMENTATION_SUMMARY.md`

---

### Added - SSH Monitoring & Automation System
**Why**: Fully automate stats collection without manual commands.

**What Changed**:
- Added 9 SSH-related methods to `UltimateETLegacyBot`:
  - `parse_gamestats_filename()` - Extract metadata from filenames
  - `ssh_list_remote_files()` / `_ssh_list_files_sync()` - List remote files
  - `ssh_download_file()` / `_ssh_download_file_sync()` - Download via SFTP
  - `process_gamestats_file()` - Parse stats file
  - `_import_stats_to_db()` - Full database import (53 columns)
  - `_insert_player_stats()` - Insert player stats
  - `post_round_summary()` - Discord round completion embed
  - `post_map_summary()` - Discord map completion embed

- Added 3 background tasks:
  - `endstats_monitor()` - Check server every 30s for new files
  - `scheduled_monitoring_check()` - Auto-start at 20:00 CET daily
  - `voice_session_monitor()` - Auto-end after 3min voice timeout

- Added SSH configuration to `.env`:
  - `SSH_ENABLED` - Toggle SSH monitoring
  - `SSH_HOST`, `SSH_PORT`, `SSH_USER` - Server connection
  - `SSH_KEY_PATH` - SSH private key location
  - `REMOTE_STATS_PATH` - Remote stats directory

- Added automation flags:
  - `AUTOMATION_ENABLED` - Voice detection (OFF by default)
  - `GAMING_VOICE_CHANNELS` - Which channels to monitor
  - `SESSION_END_DELAY` - 3-minute timeout before auto-end

**Files Created**:
- `docs/SSH_MONITORING_SETUP.md` - Complete setup guide (450 lines)
- `docs/SSH_IMPLEMENTATION_SUMMARY.md` - Technical overview (350 lines)
- `docs/SSH_QUICKSTART.md` - 15-minute quick start
- `docs/FINAL_AUTOMATION_COMPLETE.md` - Feature documentation (600 lines)

**Impact**:
- ✅ Fully automated stats collection
- ✅ Auto-start at 20:00 CET (no manual commands)
- ✅ Auto-end when players leave voice
- ✅ Round-by-round Discord posting
- ✅ Complete database import for each round

**Documentation**: See `docs/FINAL_AUTOMATION_COMPLETE.md`

---

## [2.5.0] - 2025-10-05

### Fixed - Critical Bot Bugs
**Issues Found During User Testing**:

1. **!last_session only showed 1 map instead of 9** ❌ FIXED
   - Changed query to use `SUBSTR(session_date, 1, 10)` for date matching
   - Now correctly shows all rounds from same gaming day

2. **!stats command crashing** ❌ FIXED
   - Wrapped entire command in single database connection
   - Fixed "no active connection" errors
   - All scenarios (@mention, self-lookup, name search) now work

3. **!last_session SQL errors** ❌ FIXED
   - Fixed column name: `repairs_constructions` → `constructions`
   - Fixed column name: `full_selfkills` → `self_kills`
   - Removed reference to non-existent `special_flag` column

**Files Modified**:
- `bot/ultimate_bot.py` - All three fixes applied

**Documentation**: See `CRITICAL_FIXES_OCT5.md`, `CRITICAL_FIXES_OCT5_PART2.md`

---

### Added - Leaderboard Pagination
**Feature**: Navigate through leaderboard pages.

**What Changed**:
- Enhanced `!leaderboard` command to accept page numbers
- Syntax: `!lb [stat] [page]` (e.g., `!lb dpm 2`)
- Shows 10 players per page
- Works with all stat types (kills, dpm, kd, accuracy, etc.)

**Files Modified**:
- `bot/ultimate_bot.py` - Updated leaderboard_command()

**Documentation**: See `LEADERBOARD_PAGINATION_COMPLETE.md`

---

### Added - Team Scoring System
**Why**: Bot was incorrectly treating Axis/Allies as the teams in Stopwatch mode.

**What Changed**:
- Created `session_teams` table (7 columns, 3 indexes)
- Populated with October 2nd session data (20 records)
- Updated `!last_session` to use GUID-based team matching
- MVP now calculated per actual team (not Axis/Allies)
- Eliminated false "player swapped teams" warnings

**Files Created**:
- `tools/create_session_teams_table.py` - Table creation
- `tools/populate_session_teams.py` - Data population
- `tools/normalize_team_assignments.py` - Data normalization

**Files Modified**:
- `bot/ultimate_bot.py` - Updated get_hardcoded_teams() and !last_session

**Impact**:
- ✅ Accurate team rosters
- ✅ Correct MVP calculation per team
- ✅ No more false swap warnings

**Documentation**: See `TEAM_SCORING_FIX_COMPLETE.md`, `ALL_DONE_TEAM_SCORING.md`

---

## [2.0.0] - 2025-10-04

### Added - Alias & Linking System
**Feature**: Track player name changes and link Discord accounts to game GUIDs.

**What Changed**:
- Created `player_aliases` table (8 columns, 3 indexes)
- Created `player_links` table (4 columns)
- Populated 48 aliases from 12,414 historical records
- Added 3 linking scenarios:
  1. Self-linking with smart suggestions: `!link`
  2. Name search with alias support: `!link <name>`
  3. Admin linking: `!link @user <GUID>`

**Files Created**:
- `tools/populate_player_aliases.py` - Alias extraction script
- `docs/ALIAS_LINKING_SYSTEM.md` - System documentation

**Files Modified**:
- `bot/ultimate_bot.py` - Added link_command() with all scenarios

**Impact**:
- ✅ Smart self-linking with suggestions
- ✅ Discord @mention support for stats (!stats @user)
- ✅ Alias display in stats footer
- ✅ Stats consolidation by GUID

**Documentation**: See `COMPLETE_SESSION_REPORT.md`, `LINKING_ENHANCEMENT_COMPLETE.md`

---

### Fixed - Critical Schema & Safety Issues
**Why**: Bot review found 13 potential issues (4 critical).

**What Changed**:
1. **Added Schema Validation** ✅
   - New method: `validate_database_schema()`
   - Checks for 53 columns in player_comprehensive_stats
   - Verifies objective stats columns exist
   - Fails fast with clear error if schema wrong

2. **NULL-Safe Calculations** ✅
   - All SQL aggregations now use `COALESCE(column, 0)`
   - Prevents NULL propagation in calculations
   - Affects SUM(), AVG(), and arithmetic operations

3. **Safe Column Extraction** ✅
   - New helper: `safe_get_column()`
   - Prevents "index out of range" errors
   - Returns None for missing columns

4. **Import Safety** ✅
   - Fixed `tools/simple_bulk_import.py` to insert all 53 columns
   - Previously only inserted 13 columns!
   - Correctly maps parser fields to database columns

**Files Created**:
- `test_bot_fixes.py` - Validation test suite
- `docs/BOT_FIXES_COMPLETE_SUMMARY.md` - Fix documentation

**Files Modified**:
- `bot/ultimate_bot.py` - All 3 bot fixes applied
- `tools/simple_bulk_import.py` - Complete field mapping

**Impact**:
- ✅ Bot now fails fast with clear errors
- ✅ No more silent data corruption
- ✅ Robust against missing/NULL data
- ✅ Complete stats import (53 columns)

**Documentation**: See `BOT_FIXES_COMPLETE_SUMMARY.md`, `ULTIMATE_PROJECT_SUMMARY.md`

---

### Added - Enhanced !last_session Command
**Feature**: Comprehensive session summaries with chaos stats and awards.

**What Changed**:
- Added 2 new Discord embeds:
  1. **🏆 Special Awards** - Auto-generated funny awards
  2. **📊 Chaos Stats** - Teamkills, self-kills, kill steals
- Added 1 new graph:
  - **Graph 5: Combat Efficiency Analysis** (2x2 panels)

**Files Modified**:
- `bot/ultimate_bot.py` - Enhanced last_session() command

**Impact**:
- ✅ More engaging session summaries
- ✅ Highlights funny/chaotic moments
- ✅ Shows combat efficiency metrics

**Documentation**: See `NEW_FEATURES_COMPLETE.md`

---

## [1.5.0] - 2025-10-03

### Changed - Time Format to Seconds
**Why**: Community vote - decimals in minutes were confusing.

**What Changed**:
- All time displays now show seconds instead of fractional minutes
- Example: `9:41` → `581 seconds` (not `9.7 minutes`)
- Updated parser, importer, and bot display logic

**Files Modified**:
- `bot/community_stats_parser.py` - Time parsing
- `tools/simple_bulk_import.py` - Time storage
- `bot/ultimate_bot.py` - Time display

**Documentation**: See `SECONDS_IMPLEMENTATION_PLAN.md`, `TIME_FORMAT_EXPLANATION.md`

---

### Added - Smart Sync Scheduler
**Feature**: Automated stats file sync from game server.

**What Changed**:
- Created intelligent scheduler with prime-time detection
- Checks frequently during gaming hours (20:00-23:00 CET)
- Checks less frequently during off-hours
- Adaptive intervals based on file discovery

**Files Created**:
- `tools/smart_scheduler.py` - Scheduler implementation
- `docs/SCHEDULER_READY.md` - Setup guide
- `docs/SMART_SCHEDULER.md` - Technical docs

**Impact**:
- ✅ Automated file sync
- ✅ Smart timing (frequent when needed, rare when not)
- ✅ No manual intervention required

**Documentation**: See `SCHEDULER_READY.md`

---

## [1.0.0] - 2025-10-02

### Initial Production Release
**Status**: First fully working version with complete feature set.

**Features**:
- ✅ Discord bot with 12 commands
- ✅ UNIFIED schema (3 tables, 53 columns)
- ✅ 12,414+ player records imported
- ✅ Full stats parsing from C0RNP0RN3.lua files
- ✅ Beautiful Discord embeds with graphs
- ✅ Comprehensive leaderboards (13 types)
- ✅ Complete documentation

**Core Files**:
- `bot/ultimate_bot.py` - Main bot (4,184 lines)
- `bot/community_stats_parser.py` - Stats parser
- `tools/simple_bulk_import.py` - Correct importer
- `etlegacy_production.db` - Production database

**Documentation**: See `README.md`, `docs/BOT_COMPLETE_GUIDE.md`

---

## Archive

### [0.x] - 2025-09-XX
**Development Phase**: Multiple schema iterations, parser fixes, import script development.

**Key Milestones**:
- Parser bug fixes (player dropping issue)
- Schema migration (SPLIT → UNIFIED)
- Bulk import script corrections
- Database integrity testing

**Documentation**: See `docs/archive/` for historical session summaries.

---

## Legend

### Change Types
- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes

### Status Indicators
- ✅ Complete and tested
- 🚧 In progress
- 📋 Planned
- ⏸️ On hold
- ❌ Abandoned

---

**Maintained By**: ET:Legacy Stats Bot Development Team  
**Last Updated**: October 6, 2025, 07:30 UTC
