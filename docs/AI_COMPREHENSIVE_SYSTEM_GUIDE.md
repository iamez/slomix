# AI Comprehensive System Guide - ET:Legacy Discord Bot

**READ THIS FIRST IN EVERY AI SESSION**

This document contains complete system understanding to prevent circular problem-solving and ensure consistent development.

---

## Quick Reference

### System Architecture

```yaml
ET:Legacy Game Server → SSH/Local Files → Parser → PostgreSQL → Discord Bot → Users
```python

### Critical Rules

1. ✅ **ALWAYS** use `gaming_session_id` for session queries, not dates
2. ✅ **ALWAYS** group by `player_guid`, never `player_name`
3. ✅ **ALWAYS** use 60-minute gap threshold (not 30!)
4. ✅ **ALWAYS** read validation docs before claiming bugs
5. ❌ **NEVER** recalculate R2 differential (parser handles it)
6. ❌ **NEVER** assume corruption without checking raw files

### Terminology Hierarchy

- **ROUND** = One stats file (R1 or R2)
- **MATCH** = R1 + R2 together (one map played)
- **GAMING SESSION** = Multiple matches within 60-min gaps

---

## Section 1: System Architecture

### Components

1. **Stats Parser** (`community_stats_parser.py`) - Extracts 50+ fields per player
2. **Database** (PostgreSQL primary, SQLite fallback) - 6 main tables
3. **Bot Core** (`bot/ultimate_bot.py`) - 4,371 lines, 14 cogs
4. **SSH Monitor** - 30-second polling for new stats files
5. **Discord Interface** - 63 commands across 6 categories

### Data Flow (30-70 seconds total)

1. Round ends → Server generates .txt file
2. SSH monitor detects new file (30s polling)
3. File downloaded to local_stats/
4. Parser extracts stats (50+ fields per player)
5. Team detection algorithm runs
6. Database import with transaction safety
7. Auto-post to Discord
8. Cache refresh

---

## Section 2: Database Schema

### Primary Tables

#### rounds

```sql
id SERIAL PRIMARY KEY
round_date TEXT                 -- YYYY-MM-DD from filename
round_time TEXT                 -- HHMMSS from filename
match_id TEXT                   -- Links R1+R2
map_name TEXT
round_number INTEGER            -- 1 or 2 (not 0!)
gaming_session_id INTEGER       -- Groups continuous play
time_limit TEXT
actual_time TEXT
```yaml

#### player_comprehensive_stats (53 columns)

- Core: player_guid, player_name, round_id
- Combat: kills, deaths, damage_given, damage_received, accuracy
- Weapons: headshots, headshot_kills, gibs
- Objectives: revives_given, ammo_given, health_given
- Performance: efficiency, kdr, skill_rating
- Time: time_played_seconds (source of truth)
- Team: team ('axis'/'allies'), team_detection_confidence

#### weapon_comprehensive_stats

Per-weapon breakdown: weapon_name, kills, deaths, headshots, hits, shots, accuracy

#### processed_files

Duplicate detection: filename (UNIQUE), file_hash (SHA256), processed_at, success

---

## Section 3: Gaming Session Logic

### 60-Minute Gap Rule

**Algorithm**:

```python
# Get last round in database
last_round = SELECT id, time FROM rounds ORDER BY date DESC, time DESC LIMIT 1

# Work backwards with 60-minute gap detection
for previous_round in get_previous_rounds():
    time_gap = current_time - previous_round.time

    if time_gap <= 60 minutes:  # 60-MINUTE THRESHOLD!
        add_to_session(previous_round)
    else:
        break  # Gap too large - different session
```python

**Key Points**:

- ✅ Handles midnight crossovers correctly
- ✅ Uses datetime arithmetic (not string comparison)
- ✅ Groups rounds into continuous play sessions
- ⚠️ **CRITICAL**: Must be 60 minutes, not 30!

### Session ID Formats

- **session_id**: `YYYY-MM-DD-HHMMSS` (legacy, from first round)
- **gaming_session_id**: Auto-incrementing integer (current system)
- **match_id**: `YYYY-MM-DD-HHMMSS` (pairs R1+R2)

---

## Section 4: Round Number System

### R1 and R2 Explained

- **round_number = 1**: Round 1 (first half)
- **round_number = 2**: Round 2 (teams swap sides)
- **round_number = 0**: Match summary (NOT USED IN CURRENT SYSTEM)

### R2 Differential Calculation

**CRITICAL**: Round 2 stats files contain **CUMULATIVE** stats (R1 + R2)

**Parser Logic** (`community_stats_parser.py`):

```python
def parse_round_2_with_differential(round2_file):
    # 1. Parse R2 file → cumulative (R1+R2) stats
    r2_cumulative = parse_stats_file(round2_file)

    # 2. Find corresponding R1 file
    r1_stats = find_matching_round1_file(round2_file)

    # 3. Calculate differential: R2_only = R2_cumulative - R1
    for player in r2_cumulative['players']:
        player.kills = r2_cumulative.kills - r1_stats.kills
        player.deaths = r2_cumulative.deaths - r1_stats.deaths
        # ... all 50+ fields

    # 4. Return ONLY Round 2 differential (not cumulative)
    return r2_differential
```sql

**Status**: ✅ **100% VALIDATED** (Nov 3, 2025 - 2,700 field comparisons)

---

## Section 5: Known Bugs and Fixes

### Fixed Issues

#### 1. Gaming Session Detection Bug (FIXED Nov 3, 2025)

**Problem**: Date-based queries included orphan rounds from different sessions

**Fix**: Changed to session_ids list approach

```python
# OLD (BROKEN):
WHERE round_date = '2025-11-02'  # Gets ALL rounds on that date ❌

# NEW (FIXED):
WHERE round_id IN (2134, 2135, ..., 2151)  # Only session rounds ✅
```text

#### 2. Player Duplication Bug (FIXED Nov 3, 2025)

**Problem**: Name changes created duplicate player entries

**Fix**: Group by GUID instead of name

```python
# OLD (BROKEN):
GROUP BY player_name  # Duplicates on name change ❌

# NEW (FIXED):
GROUP BY player_guid  # One entry per player ✅
```text

#### 3. Duplicate Detection Bug (FIXED Nov 19, 2025)

**Problem**: Only checked `map_name` and `round_number`, not `round_time`

- Same map played twice in one session → second play skipped

**Fix**: Added `round_time` to duplicate check

```python
# OLD (BROKEN):
WHERE round_date = ? AND map_name = ? AND round_number = ?  ❌

# NEW (FIXED):
WHERE round_date = ? AND round_time = ? AND map_name = ? AND round_number = ?  ✅
```python

**Location**: `bot/ultimate_bot.py` line 1337

#### 4. Schema Bug - Lost Sessions (FIXED Nov 3, 2025)

**Problem**: UNIQUE constraint rejected multiple matches on same map per day

**Fix**: Changed constraint from `(round_date, map_name, round_number)` to `(match_id, round_number)`

#### 5. 30-Minute vs 60-Minute Gap (FIXED Nov 4, 2025)

**Problem**: Used 30-minute threshold instead of 60 minutes

**Fix**: Changed all instances to 60 minutes

---

## Section 6: Critical Pitfalls to Avoid

### DO NOT

1. ❌ **Use date-based queries for gaming sessions**
   - Multiple sessions possible per day
   - Midnight crossovers
   - Use `gaming_session_id` instead

2. ❌ **Group by player_name in aggregations**
   - Name changes create duplicates
   - Always use `player_guid`

3. ❌ **Assume headshots = headshot_kills**
   - `headshots`: Weapon sum (hits to head)
   - `headshot_kills`: Fatal headshots only
   - Two different stats, both correct

4. ❌ **Try to recalculate R2 differential**
   - Parser already handles it correctly
   - Trust parser output

5. ❌ **Use 30-minute gap threshold**
   - Correct threshold is 60 minutes
   - Update all code that uses gaps

6. ❌ **Modify field mappings in only one place**
   - Update both `ultimate_bot.py` AND bulk importer
   - Keep parsers in sync

### ALWAYS DO

1. ✅ **Use gaming_session_id for session queries**
2. ✅ **Group by player_guid for aggregations**
3. ✅ **Read validation docs before claiming bugs**
4. ✅ **Check raw stats files when investigating issues**
5. ✅ **Use transactions for all database imports**
6. ✅ **Test with midnight crossover scenarios**
7. ✅ **Verify 60-minute gap threshold in code**

---

## Section 7: Testing Protocol

### Before Making Changes

1. ✅ Read related documentation (search .md files)
2. ✅ Understand current implementation
3. ✅ Identify root cause (not symptoms)
4. ✅ Create test case with actual data

### After Making Changes

1. ✅ Run validation script
2. ✅ Test midnight crossover scenarios
3. ✅ Test name-change scenarios
4. ✅ Test multiple sessions per day
5. ✅ Compare raw files vs database
6. ✅ Document changes in BUGFIX_*.md

---

## Section 8: Common Issues and Solutions

### Issue: "!last_session shows wrong data"

**First Check**: Using session_ids list or date-based query?
**Solution**: Use `WHERE round_id IN (session_ids_list)`

### Issue: "Player appears twice in stats"

**First Check**: Grouping by player_guid or player_name?
**Solution**: Always `GROUP BY player_guid`

### Issue: "R2 stats seem wrong"

**First Check**: Parser handles differential correctly
**Solution**: Don't recalculate, trust parser output

### Issue: "Same map played twice, second missing"

**First Check**: Duplicate detection includes round_time?
**Solution**: Check query has `round_time` parameter (fixed Nov 19, 2025)

### Issue: "Import rejected duplicate"

**First Check**: SHA256 hash match or UNIQUE constraint issue?
**Solution**: Check if actually duplicate or constraint problem

### Issue: "Session spans midnight, split incorrectly"

**First Check**: gaming_session_id calculation uses datetime arithmetic?
**Solution**: Verify 60-minute gap logic handles date boundaries

---

## Section 9: Essential Files Reference

### Must-Read Documentation

1. `COMPLETE_SYSTEM_RUNDOWN.md` - High-level architecture
2. `BUGFIX_SESSION_NOV3_2025.md` - Latest critical fixes
3. `VALIDATION_FINDINGS_NOV3.md` - Data validation (100% accurate)
4. `COMPLETE_SESSION_TERMINOLOGY_AUDIT.md` - Terminology guide
5. `DUPLICATE_DETECTION_BUG.md` - Duplicate detection fix

### Core Code Files

1. `bot/ultimate_bot.py` (4,371 lines) - Main bot
2. `community_stats_parser.py` (1,036 lines) - Stats parser
3. `bot/cogs/last_session.py` - Session logic
4. `bot/core/database_adapter.py` - Database abstraction
5. `postgresql_database_manager.py` - Database management

---

## Section 10: Quick Checklist for AI Sessions

### Starting a New Session

- [ ] Read this document (AI_COMPREHENSIVE_SYSTEM_GUIDE.md)
- [ ] Check recent commits for new fixes
- [ ] Review BUGFIX_*.md files for recent changes
- [ ] Understand the specific issue user is reporting
- [ ] Check if issue was already fixed

### Before Claiming a Bug

- [ ] Read VALIDATION_FINDINGS_NOV3.md
- [ ] Check raw stats files
- [ ] Understand field meanings
- [ ] Check recent bug fixes
- [ ] Test with current data

### Before Modifying Code

- [ ] Understand current implementation
- [ ] Identify all affected files
- [ ] Create test case
- [ ] Plan migration if schema change
- [ ] Document changes

### After Fixing an Issue

- [ ] Verify with validation script
- [ ] Test edge cases (midnight, name changes, duplicates)
- [ ] Document in new BUGFIX_*.md file
- [ ] Update this guide if needed
- [ ] Commit changes with clear message

---

## Section 11: Environment Configuration

### Required .env Variables

```bash
# Discord
DISCORD_BOT_TOKEN=your_token
GUILD_ID=your_server_id
STATS_CHANNEL_ID=your_channel_id

# Database (PostgreSQL)
DATABASE_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=your_password

# SSH Automation
SSH_ENABLED=true
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot
REMOTE_STATS_PATH=/home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats

# Voice Automation
AUTOMATION_ENABLED=true
GAMING_VOICE_CHANNELS=channel_id1,channel_id2
SESSION_START_THRESHOLD=6
SESSION_END_THRESHOLD=2
SESSION_END_DELAY=180
```

---

## System Health Status

- ✅ Parser: 100% functional, R2 differential working perfectly
- ✅ Database: 100% accurate, no corruption
- ✅ Bot Commands: All 63 commands functional
- ✅ SSH Monitoring: Active and working
- ✅ Duplicate Detection: Fixed (includes round_time now)
- ✅ Gaming Session Logic: Fixed (60-minute gaps, handles midnight)
- ✅ Player Aggregation: Fixed (uses player_guid)
- ✅ Automation: Voice channel + scheduled monitoring active

---

**Document Created**: 2025-11-19
**Last Updated**: 2025-11-19
**Database Schema Version**: 2.0
**Bot Status**: Production-ready, validated
**Critical Fixes Applied**: 5 major bugs fixed (Nov 2025)

---

## Emergency Contact

If this document doesn't resolve your issue:

1. Search all BUGFIX_*.md files for keywords
2. Check VALIDATION_FINDINGS_NOV3.md (2,700 field comparisons)
3. Review raw stats files in local_stats/
4. Check database with direct SQL queries
5. Review bot logs in logs/ directory

**Remember**: Trust validation data. If validation says it's correct, it probably is. Check your assumptions first.
