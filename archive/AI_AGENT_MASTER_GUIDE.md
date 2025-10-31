# 🎯 AI AGENT MASTER GUIDE
**Last Updated:** October 6, 2025  
**Purpose:** Single source of truth for AI agents working on ET:Legacy Stats Bot  
**Read This First!** Everything you need to know in one place.

---

## 📊 CURRENT SYSTEM STATE (October 6, 2025)

### ✅ What's Working
- **Bot**: `bot/ultimate_bot.py` (5,287 lines) - Fully functional Discord bot
- **Database**: `etlegacy_production.db` - SQLite with UNIFIED schema
- **Schema**: 3 tables + 53 columns in `player_comprehensive_stats`
- **Records**: 12,414+ player records imported and working
- **Commands**: 12+ Discord commands (`!stats`, `!leaderboard`, `!last_session`, etc.)
- **Features**: Alias system, Discord linking, team scoring, SSH monitoring

### 🚀 Recent Major Updates

#### **October 6, 2025 - Hybrid File Processing**
- **What**: Smart file processing to avoid re-downloading/re-importing existing files
- **Why**: User had local files from manual imports, bot would re-process them
- **How**: 4-layer check (memory cache → local files → processed_files table → sessions table)
- **Files**: 
  - Added 5 helper methods to `ultimate_bot.py`
  - Created `processed_files` table in database
  - Migration script: `add_processed_files_table.py`
- **Docs**: `docs/HYBRID_IMPLEMENTATION_SUMMARY.md`, `docs/HYBRID_APPROACH_COMPLETE.md`

#### **October 6, 2025 - SSH Monitoring (Automation)**
- **What**: Bot automatically downloads new stats files from game server via SSH
- **Features**:
  - Auto-start monitoring at 20:00 CET daily
  - Auto-end session when voice channel empties (3min timeout)
  - Round-by-round Discord posting
  - Full database import
- **Files**: 9 methods in `ultimate_bot.py` (lines 4577-5252)
- **Docs**: `docs/FINAL_AUTOMATION_COMPLETE.md`, `docs/SSH_MONITORING_SETUP.md`

#### **October 4-5, 2025 - Core Fixes & Features**
- Fixed team scoring (session_teams table)
- Added alias system (player_aliases table)
- Implemented Discord @mention support
- Fixed critical SQL bugs
- Enhanced !last_session command

---

## 🗄️ DATABASE SCHEMA

### Current Schema: **UNIFIED** (October 2025)

```sql
-- Table 1: sessions (session metadata)
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL,      -- Format: YYYY-MM-DD-HHMMSS or YYYY-MM-DD
    map_name TEXT NOT NULL,
    round_number INTEGER,
    time_limit TEXT,
    actual_time TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: player_comprehensive_stats (53 columns!)
CREATE TABLE player_comprehensive_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    player_guid TEXT NOT NULL,
    player_name TEXT,
    clean_name TEXT,
    team INTEGER,  -- 1=Axis, 2=Allies
    
    -- Combat stats (13 columns)
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    damage_given INTEGER DEFAULT 0,
    damage_received INTEGER DEFAULT 0,
    team_damage_given INTEGER DEFAULT 0,
    team_damage_received INTEGER DEFAULT 0,
    gibs INTEGER DEFAULT 0,
    self_kills INTEGER DEFAULT 0,
    team_kills INTEGER DEFAULT 0,
    team_gibs INTEGER DEFAULT 0,
    headshots INTEGER DEFAULT 0,
    headshot_kills INTEGER DEFAULT 0,
    kill_streak INTEGER DEFAULT 0,
    death_streak INTEGER DEFAULT 0,
    
    -- Time stats (3 columns)
    time_played_seconds INTEGER DEFAULT 0,
    time_axis_seconds INTEGER DEFAULT 0,
    time_allies_seconds INTEGER DEFAULT 0,
    
    -- XP & efficiency (4 columns)
    experience_points INTEGER DEFAULT 0,
    kills_per_death REAL,
    damage_per_minute REAL,
    efficiency_rating REAL,
    
    -- Objective stats (12 columns)
    objectives_completed INTEGER DEFAULT 0,
    objectives_stolen INTEGER DEFAULT 0,
    objectives_returned INTEGER DEFAULT 0,
    objectives_captured INTEGER DEFAULT 0,
    objectives_defended INTEGER DEFAULT 0,
    constructions INTEGER DEFAULT 0,
    destructions INTEGER DEFAULT 0,
    dynamites_planted INTEGER DEFAULT 0,
    dynamites_defused INTEGER DEFAULT 0,
    landmines_planted INTEGER DEFAULT 0,
    landmines_spotted INTEGER DEFAULT 0,
    grenade_airtime_total INTEGER DEFAULT 0,
    
    -- Advanced stats (15 columns)
    kill_assists INTEGER DEFAULT 0,
    most_useful_kills INTEGER DEFAULT 0,
    useless_kills INTEGER DEFAULT 0,
    times_revived INTEGER DEFAULT 0,
    revives_given INTEGER DEFAULT 0,
    revives_teammates INTEGER DEFAULT 0,
    suicides INTEGER DEFAULT 0,
    poison_deaths INTEGER DEFAULT 0,
    damage_from_grenades INTEGER DEFAULT 0,
    multikill_2x INTEGER DEFAULT 0,
    multikill_3x INTEGER DEFAULT 0,
    multikill_4x INTEGER DEFAULT 0,
    multikill_5x INTEGER DEFAULT 0,
    multikill_6x INTEGER DEFAULT 0,
    kill_steals INTEGER DEFAULT 0,
    
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Table 3: weapon_comprehensive_stats
CREATE TABLE weapon_comprehensive_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    player_guid TEXT NOT NULL,
    weapon_name TEXT NOT NULL,
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    headshots INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Table 4: player_aliases (tracking name changes)
CREATE TABLE player_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_guid TEXT NOT NULL,
    alias_name TEXT NOT NULL,
    clean_name TEXT,
    first_seen TEXT,
    last_seen TEXT,
    total_sessions INTEGER DEFAULT 1,
    UNIQUE(player_guid, clean_name)
);

-- Table 5: player_links (Discord account linking)
CREATE TABLE player_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL UNIQUE,
    player_guid TEXT NOT NULL,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 6: session_teams (for team scoring)
CREATE TABLE session_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    team_name TEXT NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT,
    player_team INTEGER,
    round_number INTEGER
);

-- Table 7: processed_files (Hybrid approach - NEW Oct 6)
CREATE TABLE processed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    file_hash TEXT,
    success BOOLEAN DEFAULT 1,
    error_message TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### ⚠️ CRITICAL: What NOT to Use

**NEVER use these schemas** (outdated, will break everything):
- ❌ SPLIT schema (4 tables) - Old design from September
- ❌ Any schema with 35 columns in player_comprehensive_stats
- ❌ `dev/bulk_import_stats.py` - Uses wrong schema

**ALWAYS use**:
- ✅ `tools/simple_bulk_import.py` - Correct UNIFIED schema importer
- ✅ Current database: `etlegacy_production.db`

---

## 🤖 BOT ARCHITECTURE

### Class Structure

```python
# bot/ultimate_bot.py

class ETLegacyCommands(commands.Cog):
    """
    Lines 71-3808
    Contains all Discord commands (!stats, !leaderboard, !last_session, etc.)
    """
    
    async def stats_command(...)      # !stats [player/@mention]
    async def leaderboard_command(...) # !leaderboard [stat] [page]
    async def last_session(...)       # !last_session
    async def link_command(...)       # !link [GUID/@mention]
    # ... 12 total commands

class UltimateETLegacyBot(commands.Bot):
    """
    Lines 3809-5287
    Main bot class with initialization, background tasks, SSH monitoring
    """
    
    # Database & validation
    async def validate_database_schema(...)
    async def initialize_database(...)
    
    # SSH monitoring (NEW Oct 6)
    async def endstats_monitor(...)           # Background task (30s loop)
    async def scheduled_monitoring_check(...) # Auto-start at 20:00 CET
    async def voice_session_monitor(...)      # Auto-end detection
    
    # Hybrid file processing (NEW Oct 6)
    async def should_process_file(...)        # 4-layer smart check
    async def _is_in_processed_files_table(...)
    async def _session_exists_in_db(...)
    async def _mark_file_processed(...)
    async def sync_local_files_to_processed_table(...)
    
    # SSH helpers
    def parse_gamestats_filename(...)
    async def ssh_list_remote_files(...)
    async def ssh_download_file(...)
    async def process_gamestats_file(...)
    async def _import_stats_to_db(...)
    async def _insert_player_stats(...)
```

### Key Configuration (.env)

```bash
# Discord
DISCORD_TOKEN=your_token
GUILD_ID=your_guild
STATS_CHANNEL_ID=channel_for_stats

# Database
DB_PATH=./etlegacy_production.db
STATS_DIRECTORY=./local_stats

# SSH Monitoring (NEW Oct 6)
SSH_ENABLED=true                              # Enable SSH monitoring
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot
REMOTE_STATS_PATH=/home/et/.etlegacy/legacy/gamestats

# Automation (NEW Oct 6)
AUTOMATION_ENABLED=false                      # Voice detection OFF by default
GAMING_VOICE_CHANNELS=channel_id1,channel_id2
SESSION_START_THRESHOLD=6
SESSION_END_THRESHOLD=2
SESSION_END_DELAY=180                         # 3 minutes
```

---

## 🔧 COMMON TASKS

### Task 1: Add New Bot Command

```python
# In ETLegacyCommands class (bot/ultimate_bot.py)

@commands.command(name='newcommand')
async def new_command(self, ctx, arg: str = None):
    """Description of what command does"""
    try:
        # Your logic here
        async with aiosqlite.connect(self.bot.db_path) as db:
            cursor = await db.execute('SELECT ...')
            # ...
        
        # Send response
        embed = discord.Embed(title="Title", color=0x00FF00)
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in new_command: {e}")
        await ctx.send(f"❌ Error: {e}")
```

### Task 2: Add New Database Column

```python
# 1. Create migration script
# tools/add_new_column.py

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

cursor.execute('''
    ALTER TABLE player_comprehensive_stats 
    ADD COLUMN new_column_name INTEGER DEFAULT 0
''')

conn.commit()
conn.close()

# 2. Update parser to extract the stat (if needed)
# bot/community_stats_parser.py

# 3. Update importer to insert the stat
# tools/simple_bulk_import.py

# 4. Update bot queries to use the stat
# bot/ultimate_bot.py
```

### Task 3: Test Hybrid File Processing

```bash
# 1. Check local files
ls local_stats/*.txt | Measure-Object

# 2. Start bot (watch for sync message)
python bot/ultimate_bot.py
# Output: "🔄 Syncing 42 local files to processed_files table..."
# Output: "✅ Synced 42 local files to processed_files table"

# 3. Enable SSH monitoring
# In .env: SSH_ENABLED=true

# 4. Watch monitoring logs
# Bot will check every 30s, only download NEW files
```

### Task 4: Manual Stats Import

```bash
# Use the CORRECT importer (UNIFIED schema)
python tools/simple_bulk_import.py

# Input directory when prompted: local_stats
# Watch for success rate (should be 100%)
```

---

## 🐛 TROUBLESHOOTING

### Issue: "Missing required tables: {'processed_files'}"

**Solution**:
```bash
python add_processed_files_table.py
```

### Issue: "no such column: X"

**Cause**: Query references column that doesn't exist  
**Solution**:
1. Check actual schema: `python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.execute('PRAGMA table_info(player_comprehensive_stats)'); print([row[1] for row in cursor.fetchall()])"`
2. Fix SQL query to use correct column name

### Issue: Bot re-downloading existing files

**Debug**:
```python
# Add logging to bot
logger.info(f"📁 Local files: {len(os.listdir('local_stats'))}")
logger.info(f"💾 In-memory cache: {len(self.processed_files)}")
logger.info(f"🗄️ Processed files table: {await self._count_processed_files()}")
```

**Common causes**:
- Filenames don't match exactly (case-sensitive)
- Sync not running on startup (check logs)
- processed_files table not populated

### Issue: SSH monitoring not working

**Check**:
1. SSH_ENABLED=true in .env
2. SSH credentials correct
3. SSH key exists: `~/.ssh/etlegacy_bot`
4. Can connect manually: `ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101`

---

## 📚 DOCUMENTATION STRUCTURE

### Active Documentation (Read These)

**Essential**:
- `docs/AI_AGENT_MASTER_GUIDE.md` ⭐ **THIS FILE**
- `CHANGELOG.md` - Chronological change history
- `README.md` - Project overview

**Feature-Specific**:
- `docs/HYBRID_IMPLEMENTATION_SUMMARY.md` - Hybrid file processing (Oct 6)
- `docs/FINAL_AUTOMATION_COMPLETE.md` - SSH monitoring system (Oct 6)
- `docs/SSH_MONITORING_SETUP.md` - SSH setup guide (Oct 6)
- `docs/COMMAND_REFERENCE.md` - All bot commands
- `docs/AI_AGENT_GUIDE.md` - Previous guide (being replaced by this)

**Technical Reference**:
- `docs/BOT_COMPLETE_GUIDE.md` - Bot architecture
- `docs/DATABASE_SCHEMA.md` - Database details
- `docs/PARSER_DOCUMENTATION.md` - Stats parser
- `docs/C0RNP0RN3_ANALYSIS.md` - Lua script analysis

### Archived Documentation (Historical)

Located in `docs/archive/`:
- Session summaries (Oct 4-5): *_COMPLETE.md, *_SUMMARY.md
- Feature progress reports: *_PROGRESS.md
- Bug fix records: *_FIXES*.md

---

## 🎯 QUICK DECISION TREE

### "I need to understand the project"
→ Read: This file (AI_AGENT_MASTER_GUIDE.md)
→ Then: README.md
→ Then: CHANGELOG.md

### "I need to add a feature"
→ Check: Database schema (section above)
→ Check: Bot architecture (section above)
→ Check: Common Tasks (section above)

### "Something broke"
→ Check: Troubleshooting (section above)
→ Check: CHANGELOG.md for recent changes
→ Search: `docs/` for relevant feature

### "What changed recently?"
→ Read: CHANGELOG.md (chronological)
→ Read: Hybrid docs (Oct 6)
→ Read: SSH docs (Oct 6)

---

## ⚠️ CRITICAL RULES

### DO
✅ Use `tools/simple_bulk_import.py` for imports
✅ Use UNIFIED schema (53 columns)
✅ Check schema with `validate_database_schema()` on startup
✅ Test with small dataset before bulk operations
✅ Use async/await for database operations
✅ Log errors with context (which command, which player, etc.)

### DON'T
❌ Use `dev/bulk_import_stats.py` (wrong schema)
❌ Modify database schema without migration script
❌ Skip error handling in bot commands
❌ Hardcode values (use .env configuration)
❌ Block main thread (use async for I/O)
❌ Trust in-memory cache alone (Hybrid uses 4 layers)

---

## 📞 NEED MORE HELP?

1. **Check CHANGELOG.md** - What changed when?
2. **Search docs/** - Feature-specific guides
3. **Read code comments** - Bot code is well-documented
4. **Check Git history** - See what was changed and why
5. **Ask user** - They've been building this for 3 days!

---

**Last Updated:** October 6, 2025, 07:30 UTC  
**Status:** ✅ Production Ready  
**Next Update:** When significant changes occur

