# 📋 Production Files for Code Review

**Purpose:** Bare essentials for comprehensive code review by Claude Opus  
**Date:** November 3, 2025  
**Total Files:** 14 essential production files

---

## 🎯 Core Production Files (Priority Order)

### 1. **Main Bot** (5,000+ lines - THE CORE)
```
bot/ultimate_bot.py
```
- Main Discord bot with all commands
- Database operations (insert_player_stats, insert_weapon_stats)
- All cogs and event handlers
- Stats commands (!stats, !top_dpm, !leaderboard)
- Round management
- Alias tracking
- **CRITICAL** - This is the production bot

### 2. **Parser** (970 lines - DATA EXTRACTION)
```
bot/community_stats_parser.py
```
- Parses c0rnp0rn3.lua stats files
- Extracts 36 TAB-separated fields
- Handles Round 2 differential calculation
- Weapon stats parsing
- **CRITICAL** - All data flows through this

### 3. **Database Manager** (800+ lines - NEW TOOL)
```
database_manager.py
```
- THE ONLY database management tool
- Creates/imports/rebuilds/validates database
- Auto-detection and auto-creation
- Transaction safety and duplicate prevention
- **NEWLY CREATED** - Consolidates 20+ old tools

### 4. **Bulk Import** (873 lines - DATA INGESTION)
```
dev/bulk_import_stats.py
```
- Bulk imports all stats files
- 51-field implementation (recently fixed)
- Transaction handling
- UNIQUE constraints
- **RECENTLY FIXED** - Changed from 28 to 51 fields

### 5. **Stopwatch Scoring** (292 lines - GAME LOGIC)
```
tools/stopwatch_scoring.py
```
- Calculates map scores using independent round scoring
- Determines session winners in stopwatch mode
- Parses time limits and actual completion times
- Maps game teams to actual team names
- **CRITICAL** - Core game logic for competitive scoring

---

## 📊 Bot Cogs (Command Implementations)

### 6. **Stats Commands**
```
bot/cogs/stats_cog.py
```
- !stats <player> command
- Player lookup by name or GUID
- Alias resolution

### 7. **Leaderboard Commands**
```
bot/cogs/leaderboard_cog.py
```
- !top_dpm, !top_kd, !top_accuracy
- 11 different leaderboards
- Minimum playtime filtering

### 8. **Last Round**
```
bot/cogs/last_session_cog.py
```
- !last_round command
- Shows recent player performance
- Team-specific stats

### 9. **Admin Commands**
```
bot/cogs/admin_cog.py
```
- !sync_stats (SSH file sync)
- !session_start / !session_end
- Database maintenance commands

### 10. **Linking System**
```
bot/cogs/link_cog.py
```
- !link_me command
- Interactive Discord ↔ GUID linking
- Reaction-based selection

---

## 🤖 Automation Services (NEW - Not Yet Enabled)

### 11. **SSH Monitor**
```
bot/services/automation/ssh_monitor.py
```
- Monitors server for new stats files
- Auto-downloads via SSH/SFTP
- File change detection

### 12. **Health Monitor**
```
bot/services/automation/health_monitor.py
```
- Database health checks
- Connection monitoring
- Error rate tracking

### 13. **Metrics Logger**
```
bot/services/automation/metrics_logger.py
```
- Performance metrics
- Import statistics
- System health logging

### 14. **Database Maintenance**
```
bot/services/automation/database_maintenance.py
```
- Auto-cleanup of old data
- Index optimization
- Backup management

---

## 📝 Configuration & Setup

### 15. **.env.example** (Configuration Template)
```
.env.example
```
- All environment variables
- Discord bot token
- SSH credentials
- Database paths
- Automation flags

---

## 📊 File Size Summary

| File | Lines | Status | Priority |
|------|-------|--------|----------|
| bot/ultimate_bot.py | ~5,000 | Production | **CRITICAL** |
| bot/community_stats_parser.py | 970 | Production | **CRITICAL** |
| database_manager.py | 800+ | NEW | **HIGH** |
| dev/bulk_import_stats.py | 873 | Fixed | **HIGH** |
| tools/stopwatch_scoring.py | 292 | Production | **HIGH** |
| bot/cogs/stats_cog.py | ~300 | Production | Medium |
| bot/cogs/leaderboard_cog.py | ~400 | Production | Medium |
| bot/cogs/last_session_cog.py | ~250 | Production | Medium |
| bot/cogs/admin_cog.py | ~300 | Production | Medium |
| bot/cogs/link_cog.py | ~200 | Production | Medium |
| bot/services/automation/ssh_monitor.py | ~400 | Not Enabled | Low |
| bot/services/automation/health_monitor.py | ~200 | Not Enabled | Low |
| bot/services/automation/metrics_logger.py | ~150 | Not Enabled | Low |
| bot/services/automation/database_maintenance.py | ~200 | Not Enabled | Low |
| .env.example | ~30 | Config | Low |

**Total: ~9,365 lines of production code**

---

## 🔍 What to Focus On

### Critical Review Areas:

1. **tools/stopwatch_scoring.py**
   - `calculate_map_score()` method - Independent round scoring logic
   - `calculate_session_scores()` - Team name mapping and total calculation
   - `parse_time_to_seconds()` - Time parsing accuracy
   - Game team to actual team mapping logic
   - Edge cases: fullholds, ties, incomplete maps

2. **bot/ultimate_bot.py**
   - `_insert_player_stats()` method (lines ~3738-3900)
   - Transaction handling (lines ~3677-3745)
   - Alias tracking (lines ~3971-4008)
   - Error handling throughout

3. **bot/community_stats_parser.py**
   - `parse_player_line()` method (lines ~700-850)
   - `calculate_round_2_differential()` (lines ~367-480)
   - Type safety (safe_int, safe_float usage)
   - Field extraction accuracy

4. **database_manager.py**
   - `_ensure_database_exists()` - Auto-detection logic
   - `insert_player_stats()` - 51-field implementation
   - Transaction handling in all insert methods
   - Error recovery and rollback

5. **dev/bulk_import_stats.py**
   - Field mappings (recently changed from 28→51)
   - UNIQUE constraint handling
   - Duplicate prevention logic

### Security Concerns:
- SQL injection prevention (all using parameterized queries?)
- SSH credential handling in automation services
- File path validation
- Input sanitization

### Performance Concerns:
- Database transaction efficiency
- Batch insert optimization
- Index usage
- Memory usage with large imports

### Data Integrity:
- UNIQUE constraints properly applied
- Transaction rollback on errors
- Round 2 differential calculations
- Type conversion safety (safe_int, safe_float)

---

## 📦 How to Send to Claude Opus

1. Copy the 5 CRITICAL files first:
   - bot/ultimate_bot.py
   - bot/community_stats_parser.py
   - database_manager.py
   - dev/bulk_import_stats.py
   - tools/stopwatch_scoring.py

2. If token budget allows, add the cogs:
   - bot/cogs/*.py (5 files)

3. Skip automation services for now (not enabled in production)

4. Include this file (PRODUCTION_FILES_FOR_REVIEW.md) as context

---

## 🎯 Review Questions to Ask Claude Opus

1. **Field Mapping Accuracy**: Are all 51 fields correctly mapped between parser → bot → bulk_importer?

2. **Transaction Safety**: Are all database operations properly wrapped in transactions with rollback?

3. **Duplicate Prevention**: Are UNIQUE constraints sufficient? Any edge cases?

4. **Stopwatch Scoring Logic**: Is the independent round scoring correct? Are fullholds handled properly? Team mapping accurate?

5. **Round 2 Calculations**: Is the Round 2 differential logic correct?

6. **Error Handling**: Are errors caught and logged properly? Any silent failures?

7. **SQL Injection**: All queries using parameterized statements?

8. **Race Conditions**: Any concurrency issues with file processing or database writes?

9. **Memory Leaks**: Any unclosed connections or resource leaks?

10. **Performance Bottlenecks**: Any obvious optimization opportunities?

11. **Code Smells**: Any anti-patterns, duplicated logic, or technical debt?

---

## 📝 Recent Changes (Context for Reviewer)

### November 3, 2025 - Major Fixes:

1. **Field Mapping Bug Fixed**
   - Bulk importer had 28 fields, should be 51
   - Bot implementation was correct
   - Fixed by applying bot's implementation to bulk importer

2. **Transaction Handling Added**
   - Added BEGIN TRANSACTION/COMMIT/ROLLBACK to bulk importer
   - Prevents partial writes on errors

3. **Duplicate Prevention**
   - Added UNIQUE constraints to player_comprehensive_stats
   - Added UNIQUE constraints to weapon_comprehensive_stats
   - Three-layer protection: processed_files + UNIQUE + transactions

4. **Tool Consolidation**
   - Created database_manager.py
   - Archived 20+ scattered import/database tools
   - Added auto-detection and auto-creation

5. **System Audit**
   - Audited entire codebase
   - Verified 5/6 critical fixes already applied
   - Applied missing 6th fix (transaction handling)

---

## ✅ Files Ready for Review

All files listed above are in the GitHub repo: `iamez/slomix` (branch: `team-system`)

**Latest commits:**
- `58a71c4` - Major consolidation: Create database_manager.py
- `5733b59` - Add auto-detection and auto-creation
- `ab05d32` - Clean up: Add all remaining changes

Pull the latest from `team-system` branch for review.
