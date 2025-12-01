# Slomix - ET:Legacy Discord Bot

**Version**: 1.0.1 (Released: December 1, 2025)
**Project**: ET:Legacy Statistics Discord Bot
**Database**: PostgreSQL (primary), SQLite (fallback)
**Language**: Python 3.11+
**Discord.py**: Version 2.0+
**Status**: Production-Ready ✅

---

## ⚠️ CRITICAL RULES - READ FIRST ⚠️

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
```

### Database Queries
1. ✅ **ALWAYS** use `gaming_session_id` for session queries (NOT dates)
2. ✅ **ALWAYS** group by `player_guid` (NOT `player_name`)
3. ✅ **ALWAYS** use 60-minute gap threshold for sessions (NOT 30!)
4. ❌ **NEVER** recalculate R2 differential (parser handles it correctly)
5. ❌ **NEVER** assume data corruption without checking raw files

### Terminology (MUST USE CORRECTLY)
- **ROUND** = One stats file (R1 or R2), one half of a match
- **MATCH** = R1 + R2 together (one complete map played)
- **GAMING SESSION** = Multiple matches within 60-minute gaps

### System Architecture
```
ET:Legacy Game Server → SSH Monitor → Parser → PostgreSQL → Discord Bot → Users
                        (30s poll)   (50+ fields)  (6 tables)   (63 commands)
```

---

## 🎉 Version 1.0 Release (November 20, 2025)

### Release Milestone
**Slomix** is now officially production-ready and fully documented!

### What's Included in 1.0:
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

### Documentation Structure:
```
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
```

---

## Recent Major Fixes (Dec 2025)

### 1. SSHMonitor Race Condition (FIXED Dec 1) 🆕
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

### ❌ DON'T:
1. Use date-based queries for gaming sessions (multiple sessions per day possible)
2. Group by player_name (name changes break aggregations)
3. Assume `headshots` = `headshot_kills` (different stats, both correct)
4. Try to recalculate R2 differential (parser output is correct)
5. Use 30-minute gap threshold (correct value is 60 minutes)
6. Modify processed_files manually (SHA256 hash validation in place)

### ✅ DO:
1. Use `gaming_session_id` for session queries
2. Group by `player_guid` for player aggregations
3. Read `AI_COMPREHENSIVE_SYSTEM_GUIDE.md` before claiming bugs
4. Check raw stats files when investigating data issues
5. Use transactions for all database imports
6. Test with midnight crossover scenarios

---

## File Locations

### Core Files
- `bot/ultimate_bot.py` (4,371 lines) - Main bot entry point
- `community_stats_parser.py` (1,036 lines) - Stats file parser
- `bot/cogs/last_session.py` - Gaming session logic
- `bot/core/database_adapter.py` - Database abstraction layer
- `postgresql_database_manager.py` - Database CLI manager

### Documentation (READ THESE FIRST)
- `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` - Complete system reference
- `docs/SAFETY_VALIDATION_SYSTEMS.md` - 6-layer validation system
- `docs/DATA_PIPELINE.md` - Complete data pipeline
- `docs/SYSTEM_ARCHITECTURE.md` - System architecture
- `docs/COMMANDS.md` - All 63 bot commands
- `docs/archive/` - Historical bug fixes and audits

### Services (New Architecture)
- `bot/services/player_badge_service.py` - Achievement badges
- `bot/services/player_formatter.py` - Global player display formatting
- `bot/services/session_data_service.py` - Session statistics

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
DB_PASSWORD=REDACTED_DB_PASSWORD

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
```

---

## Quick Command Reference

### Most Used Bot Commands
- `!last_session` - Show latest gaming session stats (main feature)
- `!leaderboard` - Weekly/monthly/all-time top players
- `!stats <player>` - Individual player lifetime stats
- `!achievements` - Achievement badge system help
- `!link <player_name>` - Link Discord account to player GUID
- `!admin refresh_cache` - Clear cached data

### Database Commands (via Bash)
```bash
# Connect to database
PGPASSWORD='REDACTED_DB_PASSWORD' psql -h localhost -U etlegacy_user -d etlegacy

# Common queries
SELECT COUNT(*) FROM rounds;
SELECT MAX(gaming_session_id) FROM rounds;
SELECT * FROM rounds ORDER BY id DESC LIMIT 5;
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

**Version**: 1.0.1
**Release Date**: December 1, 2025
**Last Updated**: 2025-12-01
**Schema Version**: 2.0
**Repository Size**: ~50-100 MB (cleaned)
**Status**: Production-ready, fully documented, maintainable ✅
