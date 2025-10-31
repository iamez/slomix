# 🤖 GitHub Copilot Instructions - ET:Legacy Stats Bot# 🤖 GitHub Copilot Instructions - ET:Legacy Discord Bot



**Last Updated**: October 6, 2025  ## 📋 Project Overview

**Purpose**: Quick reference for GitHub Copilot when working on this projectDiscord bot for ET:Legacy game statistics with beautiful embeds, image generation, and comprehensive stat tracking.



---## 🎯 Current Status (October 3, 2025)



## ⚠️ CRITICAL: READ THIS FIRST### ✅ COMPLETED WORK



**For comprehensive information, see:**#### Phase 1: Database Query Fix

→ **`docs/AI_AGENT_MASTER_GUIDE.md`** ⭐ (Single source of truth - 500+ lines)- **Problem**: Query referenced non-existent columns `p.time_played` and `p.xp`

- **Solution**: Removed those columns, added playtime calculation from `sessions.actual_time`

**For recent changes, see:**- **Status**: ✅ FIXED - Bot starts successfully

→ **`CHANGELOG.md`** (Chronological change history)- **Files Modified**:

  - `bot/ultimate_bot.py` (lines 758-780): Updated query to remove non-existent columns

**This file is a QUICK REFERENCE only.** The master guide has complete details.  - `bot/ultimate_bot.py` (lines 995-1017): Fixed data unpacking for 9 values instead of 10

  - `bot/image_generator.py` (lines 115-119): Removed XP from image display

---

#### Phase 2: Stats Display Format

## 📊 Current System State (October 6, 2025)- **Format**: Two-line player stats display

  - Line 1: `1222K/865D (1.41) • 287 DPM • 39.3% ACC (1814/4610)`

### Status: ✅ PRODUCTION READY  - Line 2: `1456 HSK (58.2%) • 891 HS (49.1%) • 125m`

- **Metrics**:

- **Bot**: `bot/ultimate_bot.py` (5,287 lines)  - HSK = Headshot Kills (from player table, % of total kills)

- **Database**: `etlegacy_production.db` (UNIFIED schema)  - HS = Headshots (from weapon table, % of hits)

- **Records**: 12,414+ player records  - Playtime calculated from sessions.actual_time (MM:SS format)

- **Commands**: 12 Discord commands working- **Status**: ✅ IMPLEMENTED (untested in Discord)

- **Latest Features**:

  - Hybrid file processing (Oct 6)#### Phase 3: Image Generation

  - SSH monitoring automation (Oct 6)- **Module**: `bot/image_generator.py` created

  - Team scoring system (Oct 5)- **Features**:

  - Alias & linking system (Oct 4)  - Discord dark theme colors

  - Session overview: 1400x900px PNG

---  - Top 5 players with 2-line stats

  - Team analytics with MVPs

## 🗄️ Database Schema - CRITICAL  - PIL/Pillow based rendering

- **Status**: ✅ IMPLEMENTED (untested - bot crashes before reaching it due to other error)

### ⚠️ USE THIS SCHEMA (UNIFIED)

### 🔧 CURRENT ISSUE

```sql

-- 7 tables total:**Bot Error**: `no such column: session_date` in !last_session command (line 719)

1. sessions (7 columns)- Query tries: `SELECT DISTINCT DATE(session_date) as date FROM sessions`

2. player_comprehensive_stats (53 columns) ⭐- But column is already named `session_date` (not needing DATE() wrapper)

3. weapon_comprehensive_stats (7 columns)- **Action Required**: Fix this query before testing other features

4. player_aliases (8 columns)

5. player_links (4 columns)### 🎯 IMMEDIATE TODO (Before New Feature Work)

6. session_teams (8 columns)

7. processed_files (6 columns) ← NEW Oct 61. ✅ **Fix session_date query error** (urgent - blocking all testing)

```2. 🔄 **Test !last_session command** in Discord

3. 🔄 **Verify image generation** displays correctly

### ❌ NEVER Use These4. 🔄 **Test weapon mastery embed** appearance



- ❌ SPLIT schema (4 tables) - Outdated### 🚀 MAJOR DISCOVERY - NEW WORK PENDING

- ❌ `dev/bulk_import_stats.py` - Wrong schema

- ❌ Any schema with 35 columns in player_comprehensive_stats#### Found: Complete Objective Stats Available!



### ✅ ALWAYS UseThe `c0rnp0rn3.lua` script **ALREADY TRACKS** all objective/support stats that were thought missing:



- ✅ `tools/simple_bulk_import.py` - Correct importer**Available in Lua Output** (37+ fields per player):

- ✅ `etlegacy_production.db` - Production database- ✅ XP/Experience points (field 10)

- ✅ Validate schema on startup: `validate_database_schema()`- ✅ Kill assists (field 13)

- ✅ Objectives stolen (field 16)

---- ✅ Objectives returned (field 17)

- ✅ Dynamites planted (field 18)

## 🎯 Key Files & Locations- ✅ Dynamites defused (field 19)

- ✅ Times revived (field 20)

### Bot Code- ✅ Bullets fired (field 21)

- **Main bot**: `bot/ultimate_bot.py`- ✅ Time played minutes per player (field 23)

  - Lines 71-3808: `ETLegacyCommands` (Discord commands)- ✅ Multikills 2x-6x (fields 30-34)

  - Lines 3809-5287: `UltimateETLegacyBot` (bot class, background tasks)- ✅ Repairs/constructions (field 37)

- ✅ Killing sprees (field 11)

### Database & Import- ✅ Death sprees (field 12)

- **Database**: `etlegacy_production.db` (SQLite)- ✅ Tank/meatshield score (field 24)

- **Correct importer**: `tools/simple_bulk_import.py` ⭐- ✅ Time dead ratio (field 25)

- **Parser**: `bot/community_stats_parser.py`- ✅ Most useful kills (field 28)

- ✅ Denied playtime (field 29)

### Configuration

- **Environment**: `.env` file**Current State**: Parser only reads ~12 fields, ignoring 25+ objective stats fields

- **Example**: `.env.example`

**Next Phase**: Enhance parser to extract ALL 37 fields and populate `player_stats` table

### Documentation

- **Master guide**: `docs/AI_AGENT_MASTER_GUIDE.md` ⭐---

- **Changelog**: `CHANGELOG.md`

- **Commands**: `docs/COMMAND_REFERENCE.md`## 🗂️ Database Schema

- **Archive**: `docs/archive/` (historical only)

### Current Tables (etlegacy_production.db)

---

#### `sessions` (1,459 records)

## 🔧 Common Copilot Tasks```sql

id INTEGER PRIMARY KEY

### Adding a New Discord Commandsession_date DATE NOT NULL           -- Format: 2025-01-01

map_name TEXT NOT NULL               -- e.g., "etl_adlernest"

```pythonround_number INTEGER NOT NULL        -- 1 or 2

# In ETLegacyCommands class (bot/ultimate_bot.py, lines 71-3808)time_limit TEXT                      -- MM:SS (e.g., "10:00")

actual_time TEXT                     -- MM:SS (e.g., "11:26")

@commands.command(name='mycommand')created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

async def my_command(self, ctx, arg: str = None):```

    """Short description"""

    try:#### `player_comprehensive_stats` (12,444 records) ✅ ACTIVE

        # Use self.bot.db_path for database```sql

        async with aiosqlite.connect(self.bot.db_path) as db:id INTEGER PRIMARY KEY

            cursor = await db.execute('SELECT ...')session_id INTEGER NOT NULL

            # ...player_guid TEXT NOT NULL            -- 8-char hex ID

        player_name TEXT NOT NULL

        embed = discord.Embed(title="Title", color=0x00FF00)clean_name TEXT NOT NULL

        await ctx.send(embed=embed)team INTEGER NOT NULL                -- 1=Axis, 2=Allies

        kills INTEGER DEFAULT 0

    except Exception as e:deaths INTEGER DEFAULT 0

        logger.error(f"Error in my_command: {e}")damage_given INTEGER DEFAULT 0

        await ctx.send(f"❌ Error: {e}")damage_received INTEGER DEFAULT 0

```headshot_kills INTEGER DEFAULT 0

kd_ratio REAL DEFAULT 0.0

### Querying Database Safelydpm REAL DEFAULT 0.0

created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

```python```

# ✅ GOOD: NULL-safe aggregations

SUM(COALESCE(kills, 0)) as total_kills,#### `weapon_comprehensive_stats` ✅ ACTIVE

AVG(COALESCE(damage_per_minute, 0)) as avg_dpm```sql

id INTEGER PRIMARY KEY

# ❌ BAD: NULL propagationsession_id INTEGER NOT NULL

SUM(kills) as total_kills,  # Returns NULL if any row is NULLplayer_guid TEXT NOT NULL

AVG(damage_per_minute)      # Returns NULL if any row is NULLweapon_id INTEGER

```weapon_name TEXT NOT NULL            -- WS_MP40, WS_THOMPSON, etc.

kills INTEGER DEFAULT 0

### Accessing Player Stats (53 columns!)deaths INTEGER DEFAULT 0

hits INTEGER DEFAULT 0               -- Shots that hit

```pythonshots INTEGER DEFAULT 0              -- Total shots fired

# All available columns in player_comprehensive_stats:headshots INTEGER DEFAULT 0          -- Headshots landed

# Combat: kills, deaths, damage_given, damage_received, headshots, gibs, etc.accuracy REAL DEFAULT 0.0

# Objective: objectives_completed, constructions, dynamites_planted, etc.created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

# Advanced: kill_assists, most_useful_kills, revives_given, multikill_*, etc.```

# Time: time_played_seconds, time_axis_seconds, time_allies_seconds

# Calculated: kills_per_death, damage_per_minute, efficiency_rating#### `player_stats` (0 records) ⚠️ EMPTY BUT AVAILABLE

```sql

# See docs/AI_AGENT_MASTER_GUIDE.md for complete schemaid INTEGER PRIMARY KEY

```session_id INTEGER

player_name TEXT NOT NULL

---discord_id TEXT

round_type TEXT

## 🐛 Known Issues & Solutionsteam TEXT

kills INTEGER DEFAULT 0

### Issue: "no such column: X"deaths INTEGER DEFAULT 0

**Solution**: Check actual schema in master guide, column names changeddamage INTEGER DEFAULT 0

time_played TEXT DEFAULT '0:00'

### Issue: "Missing required tables: {'processed_files'}"time_minutes REAL DEFAULT 0

**Solution**: Run `python add_processed_files_table.py`dpm REAL DEFAULT 0

kd_ratio REAL DEFAULT 0

### Issue: Bot re-downloading existing filesmvp_points INTEGER DEFAULT 0

**Solution**: Hybrid approach should prevent this (Oct 6 feature)weapon_stats TEXT

achievements TEXT

### Issue: Wrong schema usedawards TEXT                          -- For objective stats (JSON)

**Solution**: ALWAYS use `tools/simple_bulk_import.py`, not `dev/` scripts```



---**PLAN**: Populate `player_stats.awards` with JSON containing:

```json

## 📝 Code Style Guidelines{

  "xp": 45230,

### DO  "kill_assists": 12,

- ✅ Use `async`/`await` for database operations  "objectives_stolen": 3,

- ✅ Use `COALESCE(column, 0)` in SQL aggregations  "objectives_returned": 5,

- ✅ Log errors with context: `logger.error(f"Error in command X with player Y: {e}")`  "dynamites_planted": 2,

- ✅ Use `.env` for configuration (never hardcode)  "dynamites_defused": 1,

- ✅ Validate database schema on startup  "times_revived": 8,

- ✅ Test with small dataset before bulk operations  "bullets_fired": 1234,

  "multikills_2x": 5,

### DON'T  "multikills_3x": 2,

- ❌ Block main thread (use async for I/O)  "multikills_4x": 1,

- ❌ Skip error handling in commands  "multikills_5x": 0,

- ❌ Trust in-memory cache alone (use Hybrid 4-layer check)  "multikills_6x": 0,

- ❌ Modify database schema without migration script  "repairs_constructions": 7,

- ❌ Use `dev/bulk_import_stats.py` (wrong schema)  "killing_spree_best": 10,

  "death_spree_worst": 5,

---  "tank_meatshield_score": 2.3,

  "time_dead_ratio": 15.2,

## 🚀 Recent Major Changes (October 6, 2025)  "useful_kills": 45,

  "denied_playtime_seconds": 180

### 1. Hybrid File Processing}

**What**: Smart file processing to avoid re-downloading/re-importing existing files  ```

**Key Methods**:

- `should_process_file()` - 4-layer check---

- `sync_local_files_to_processed_table()` - Auto-sync on startup

## 📦 File Structure

**Files**: Added 5 methods to `ultimate_bot.py`, new `processed_files` table

```

### 2. SSH Monitoring Automationbot/

**What**: Fully automated stats collection via SSH  ├── ultimate_bot.py              # Main Discord bot (1846 lines)

**Key Features**:├── community_stats_parser.py    # Stats parser (724 lines) - NEEDS ENHANCEMENT

- Auto-start at 20:00 CET daily├── image_generator.py           # PIL-based image generation (313 lines)

- Auto-end after 3min voice timeout├── etlegacy_production.db       # SQLite database

- Round-by-round Discord posting└── logs/

- Full database import    └── ultimate_bot.log

```

**Files**: Added 9 SSH methods + 3 background tasks to `ultimate_bot.py`

---

**Config**: See `.env` for SSH settings (SSH_HOST, SSH_PORT, etc.)

## 🛠️ Key Functions in ultimate_bot.py

---

### `!last_session` Command (line 702-1400)

## 📚 Need More Info?**Purpose**: Display comprehensive stats for most recent session



### Quick Lookups**Current Error**: Line 719 - `no such column: session_date`

- **What changed?** → `CHANGELOG.md````python

- **How to do X?** → `docs/AI_AGENT_MASTER_GUIDE.md`# BROKEN:

- **Command syntax?** → `docs/COMMAND_REFERENCE.md`SELECT DISTINCT DATE(session_date) as date FROM sessions

- **Bot architecture?** → `docs/BOT_COMPLETE_GUIDE.md`

# SHOULD BE:

### Deep DivesSELECT DISTINCT session_date as date FROM sessions

- **Database schema** → `docs/DATABASE_SCHEMA.md````

- **Stats parser** → `docs/PARSER_DOCUMENTATION.md`

- **Lua script** → `docs/C0RNP0RN3_ANALYSIS.md`**Flow**:

1. Get latest session date

### Historical Context2. Get all session IDs for that date

- **Session summaries** → `docs/archive/` (Oct 4-5 work)3. Query top 5 players (aggregated)

- **Bug fix history** → `docs/archive/*_FIXES*.md`4. Query team stats

5. Query weapon details

---6. Query per-player weapon mastery

7. Generate 5 embeds + 1 image

## 🎯 Decision Tree

**Embeds**:

### "I need to understand the project"- Embed 1: Session info + Top 5 players (with 2-line stats)

→ Read `docs/AI_AGENT_MASTER_GUIDE.md` (complete overview)- Embed 2: Team comparison + MVPs

- Embed 3: DPM leaderboard

### "I need to add a feature"- Embed 4: Team composition

→ Check master guide for schema & architecture  - Embed 5: Weapon mastery (top 6 players, top 2 weapons each)

→ Follow code style guidelines above  - Image: Beautiful session overview card

→ Test with small dataset first

---

### "Something broke"

→ Check error message carefully  ## 🎨 Discord Bot Features

→ Search `CHANGELOG.md` for recent changes  

→ See troubleshooting in master guide### Commands Available

- `!ping` - Test bot responsiveness

### "What's the latest?"- `!session` - Manage sessions

→ Read `CHANGELOG.md` (chronological)  - `!session_start` - Start new session

→ Check Oct 6 entries (Hybrid + SSH)- `!session_end` - End current session

- `!last_session` - Show stats for latest session ⭐ MAIN COMMAND

---- `!stats <player>` - Show player stats

- `!leaderboard` - Show top players

**For complete documentation, always refer to:**  - `!link <discord_mention>` - Link Discord user to game GUID

→ **`docs/AI_AGENT_MASTER_GUIDE.md`** ⭐- `!unlink` - Unlink Discord account

- `!help` - Show help message

This file is intentionally brief. The master guide has everything you need.

### Color Scheme (Discord Dark Theme)
```python
bg_dark = '#2b2d31'
bg_medium = '#1e1f22'
bg_light = '#313338'
text_white = '#f2f3f5'
text_gray = '#b5bac1'
text_dim = '#80848e'
accent_blue = '#5865f2'
accent_green = '#57f287'
accent_red = '#ed4245'
accent_yellow = '#fee75c'
accent_pink = '#eb459e'
```

---

## 🔄 Parser Enhancement Required

### Current Parser (community_stats_parser.py)
**Reads**: ~12 fields after weapon stats
- damage_given, damage_received
- Basic combat stats

**Missing**: 25+ objective/support fields

### Enhanced Parser (TO BE CREATED)
**Must Read**: All 37 fields from c0rnp0rn3.lua output

**Field Mapping** (after weapon stats):
```python
FIELD_MAPPING = {
    0: 'damage_given',
    1: 'damage_received',
    2: 'team_damage_given',
    3: 'team_damage_received',
    4: 'gibs',
    5: 'selfkills',
    6: 'teamkills',
    7: 'teamgibs',
    8: 'time_played_percent',
    9: 'xp',                      # ⭐
    10: 'killing_spree',
    11: 'death_spree',
    12: 'kill_assists',           # ⭐
    13: 'kill_steals',
    14: 'headshot_kills',
    15: 'objectives_stolen',      # ⭐
    16: 'objectives_returned',    # ⭐
    17: 'dynamites_planted',      # ⭐
    18: 'dynamites_defused',      # ⭐
    19: 'times_revived',          # ⭐
    20: 'bullets_fired',          # ⭐
    21: 'dpm',
    22: 'time_played_minutes',    # ⭐
    23: 'tank_meatshield',
    24: 'time_dead_ratio',
    25: 'time_dead_minutes',
    26: 'kd_ratio',
    27: 'useful_kills',
    28: 'denied_playtime',
    29: 'multikill_2x',           # ⭐
    30: 'multikill_3x',           # ⭐
    31: 'multikill_4x',           # ⭐
    32: 'multikill_5x',           # ⭐
    33: 'multikill_6x',           # ⭐
    34: 'useless_kills',
    35: 'full_selfkills',
    36: 'repairs_constructions'   # ⭐
}
```

---

## 🎯 MVP Calculation Enhancement

### Current MVP (combat-only)
```python
mvp_score = (
    kills * 10 +
    (damage_given / 100) +
    (kd_ratio * 50) -
    deaths * 5
)
```

### Enhanced MVP (with objectives) - TO BE IMPLEMENTED
```python
combat_score = (
    kills * 10 +
    headshot_kills * 3 +
    (damage_given / 100) +
    (kd_ratio * 50) -
    deaths * 5
)

objective_score = (
    objectives_returned * 50 +
    objectives_stolen * 30 +
    dynamites_planted * 25 +
    dynamites_defused * 20
)

support_score = (
    times_revived * 10 +
    repairs_constructions * 15 +
    kill_assists * 5
)

performance_score = (
    (accuracy * 2) +
    useful_kills * 5 -
    useless_kills * 2 +
    (multikill_3x * 10) +
    (multikill_4x * 20) +
    (multikill_5x * 40) +
    (multikill_6x * 80)
)

mvp_score = combat_score + objective_score + support_score + performance_score
```

---

## 🚨 Known Issues

1. ❌ **session_date query error** (line 719) - BLOCKING
2. 🔄 **Image generation untested** - Need Discord test
3. 🔄 **Weapon mastery readability** - User feedback: "hard to look at"
4. ❌ **Parser missing 25+ fields** - Next major work

---

## 📝 User Requests Queue

### HIGH PRIORITY
1. ✅ Fix database column errors → DONE
2. 🔄 Test !last_session command → PENDING (blocked by session_date error)
3. 🔄 Verify image generation → PENDING
4. 📋 **NEW**: Extract all 37 fields from Lua stats
5. 📋 **NEW**: Populate player_stats table with objective data
6. 📋 Improve weapon mastery display (colors, complete stats)

### MEDIUM PRIORITY
7. 📋 Implement comprehensive MVP scoring with objectives
8. 📋 Add multikill badges/displays
9. 📋 Show killing sprees in stats
10. 📋 Display time dead ratio analysis

### LOW PRIORITY
11. 📋 Add achievement badges
12. 📋 Create player career stats
13. 📋 Historical trend graphs

---

## 🔧 Development Environment

- **Python**: 3.13
- **OS**: Windows (PowerShell)
- **Libraries**: discord.py 2.3+, aiosqlite, matplotlib, Pillow
- **Database**: SQLite (etlegacy_production.db)
- **Working Directory**: `g:\VisualStudio\Python\stats\bot\`

---

## 💡 Quick Reference

### Run Bot
```powershell
cd g:\VisualStudio\Python\stats
python bot\ultimate_bot.py
```

### Check Database
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); print(cursor.fetchone()[0])"
```

### Test Parser
```python
from bot.community_stats_parser import CommunityStatsParser
parser = CommunityStatsParser()
result = parser.parse_stats_file('path/to/stats.txt')
```

---

## 🎓 Learning Notes

### ET:Legacy Team System
- Team 0: Spectators
- Team 1: Axis (Red) 🔴
- Team 2: Allies (Blue) 🔵
- Team 3: Intermission/Limbo

### Round System
- Round 1: Team A attacks, Team B defends
- Round 2: Teams switch sides
- `round_number`: 1 or 2
- Stats tracked per round

### Time Format
- `time_limit`: Map time limit (MM:SS)
- `actual_time`: Actual round duration (MM:SS)
- Early finish: actual_time < time_limit (objective completed)
- Full time: actual_time ≈ time_limit (defenders held)

---

## 📌 Important Patterns

### Error Handling
```python
try:
    # Operation
except Exception as e:
    self.logger.error(f"Error: {e}", exc_info=True)
    await ctx.send(f"❌ Error: {str(e)}")
```

### Database Queries
```python
async with aiosqlite.connect(self.db_path) as db:
    async with db.execute(query, params) as cursor:
        results = await cursor.fetchall()
```

### Embed Creation
```python
embed = discord.Embed(
    title="Title",
    color=discord.Color.blue(),
    description="Description"
)
embed.add_field(name="Field", value="Value", inline=False)
await ctx.send(embed=embed)
```

---

## 🎯 Success Criteria

### Phase 1 (Current) - ALMOST COMPLETE
- [x] Bot starts without errors
- [x] Database queries work
- [ ] !last_session displays correctly (blocked)
- [ ] Images generate successfully

### Phase 2 (Next) - PLANNED
- [ ] Parser extracts all 37 fields
- [ ] player_stats table populated
- [ ] Objective stats displayed in bot
- [ ] Enhanced MVP calculation

### Phase 3 (Future)
- [ ] Weapon mastery improved with colors
- [ ] Multikill badges
- [ ] Achievement system
- [ ] Career statistics

---

**Last Updated**: October 3, 2025 03:40 AM
**Status**: Ready for session_date fix → Full parser enhancement
**Next Step**: Fix line 719 query error, then implement enhanced parser
