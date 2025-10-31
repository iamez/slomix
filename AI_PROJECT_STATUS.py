"""
═══════════════════════════════════════════════════════════════════════════════
ET:LEGACY DISCORD BOT - AI ASSISTANT INSTRUCTIONS & STATUS DOCUMENT
═══════════════════════════════════════════════════════════════════════════════
Last Updated: October 3, 2025
Purpose: Complete context for AI assistants working on this project
═══════════════════════════════════════════════════════════════════════════════

## 🎯 PROJECT OVERVIEW

**Project**: ET:Legacy Stats Discord Bot with Comprehensive Objective/Support Stats
**Language**: Python 3.13
**Framework**: discord.py 2.3+
**Database**: SQLite (aiosqlite for async operations)
**Game**: Enemy Territory: Legacy (ET:Legacy)
**Stats Source**: c0rnp0rn3.lua mod (v3.0) - captures detailed game statistics

**Primary Goal**: Parse comprehensive stats files and display them in Discord with
rich embeds showing combat, objective, support, and performance metrics.

═══════════════════════════════════════════════════════════════════════════════
## 📊 CURRENT STATUS - WHAT'S BEEN ACCOMPLISHED
═══════════════════════════════════════════════════════════════════════════════

### ✅ PHASE 1: ENHANCED PARSER (COMPLETED)

**Achievement**: Extended parser from 12 fields to 33 comprehensive fields

**Files Modified**:
- `bot/community_stats_parser.py` (Lines 544-658)

**What It Does**:
1. **Split Logic**: Splits stats file on first TAB character
   - Before TAB: Weapon stats (space-separated, 5 fields per weapon)
   - After TAB: Extended stats (33 TAB-separated fields)

2. **33 Fields Extracted** (Indices 0-32):
   ```python
   # Fields 0-8: Damage & Team Stats
   - damage_given, damage_received, gibs, team_kills
   - time_axis_percent, time_allies_percent, time_spec_percent
   - unused_7, time_played_percent

   # Fields 9-19: XP, Kills, Objectives, Dynamites, Revives
   - xp, killing_spree, death_spree, kill_assists, kill_steals
   - headshot_kills, objectives_stolen, objectives_returned
   - dynamites_planted, dynamites_defused, times_revived

   # Fields 20-28: Bullets, DPM, Time, Performance
   - bullets_fired, dpm, time_played_minutes, tank_meatshield
   - time_dead_ratio, time_dead_minutes, kd_ratio
   - useful_kills, denied_playtime

   # Fields 29-32: Multikills
   - multikill_2x, multikill_3x, multikill_4x, multikill_5x
   ```

3. **Output**: Returns `objective_stats` dictionary for each player

**Testing**:
- Test script: `test_enhanced_parser.py`
- Verification: `show_objective_stats.py`
- ✅ All 33 fields extract correctly
- ✅ JSON serialization works
- ✅ Data validated on 6 players from test file

---

### ✅ PHASE 2: DATABASE INTEGRATION (COMPLETED)

**Achievement**: Store objective stats as JSON in database

**Files Modified**:
- `dev/bulk_import_stats.py` (Lines 162-227)
- `test_manual_import.py` (created for testing)

**Database Schema**:
```sql
-- Bot's database: bot/etlegacy_production.db
-- Table: sessions
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    date TEXT,                    -- Session date (not session_date!)
    map_name TEXT,
    status TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    total_rounds INTEGER,
    created_at TIMESTAMP
);

-- Table: player_stats
CREATE TABLE player_stats (
    id INTEGER PRIMARY KEY,
    session_id INTEGER,
    player_name TEXT,
    team TEXT,                    -- "Axis", "Allies", "Spectator"
    kills INTEGER,
    deaths INTEGER,
    damage INTEGER,
    kd_ratio REAL,
    dpm REAL,
    awards TEXT,                  -- ⭐ JSON with objective_stats
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

**Import Process**:
1. Parse stats file with enhanced parser
2. Extract `objective_stats` dictionary
3. Serialize to JSON: `json.dumps(objective_stats)`
4. Insert into `player_stats.awards` column
5. Commit to database

**Testing**:
- ✅ Imported test session (ID: 1) with 6 players
- ✅ All players have awards JSON populated
- ✅ Data queryable and deserializes correctly
- ✅ Verified with `verify_awards.py`

---

### ✅ PHASE 3: BOT DISPLAY (COMPLETED)

**Achievement**: New Discord embed showing objective/support stats

**Files Modified**:
- `bot/ultimate_bot.py` (Lines 1361-1446)

**New Embed: "🎯 Objective & Support Stats"**
- **Command**: `!last_session` (6th embed in sequence)
- **Color**: Green (#00D166)
- **Data Source**: `player_stats.awards` JSON field

**Display Format**:
```
🎯 Objective & Support Stats
Comprehensive battlefield contributions

1. PlayerName
   XP: 103
   Assists: 7
   Objectives: 0/0 S/R
   Dynamites: 0/1 P/D
   Revived: 1 times
   Multikills: 2x: 1

[Shows top 6 players sorted by XP]
Footer: 🎯 S/R = Stolen/Returned | P/D = Planted/Defused
```

**Implementation Details**:
- Queries `player_stats` WHERE `awards IS NOT NULL`
- Aggregates stats across all rounds per player
- Deserializes JSON with `json.loads(awards_json)`
- Conditional display (only shows non-zero values)
- Inline fields for compact 2-column layout

**Query Fix Applied**:
- Line 782-783: Fixed binding issue
- Query uses `session_ids_str` twice (subquery + WHERE)
- Solution: Pass `session_ids + session_ids` to db.execute()

---

### ⚠️ PHASE 4: BULK IMPORT (PARTIAL - HAS ISSUES)

**Status**: Script exists but has unicode emoji issues on Windows PowerShell

**Problem**:
- Emoji characters in logging (🚀, 📊, 🔢, etc.) cause encoding errors
- `UnicodeEncodeError: 'charmap' codec can't encode character`

**Files**:
- `dev/bulk_import_stats.py` (needs emoji removal for Windows compatibility)

**Workaround**:
- Use `test_manual_import.py` for single-file imports
- Or fix emojis in bulk_import_stats.py logging
- Or run bulk import in UTF-8 capable terminal

**What Works**:
- Single file manual import: ✅
- Parser: ✅
- Database insertion: ✅

---

### ⏳ PHASE 5: ENHANCED MVP CALCULATION (NOT STARTED)

**Plan**: Weight-based MVP score

**Formula**:
```python
mvp_score = (
    combat_score * 0.40 +        # Kills, HS, Damage, K/D
    objective_score * 0.30 +     # Objectives, Dynamites
    support_score * 0.20 +       # Revives, Repairs, Assists
    performance_score * 0.10     # Multikills, Accuracy
)
```

**Implementation Needed**:
- Create MVP calculation function
- Read objective_stats from awards JSON
- Calculate weighted scores
- Update bot's MVP display logic

═══════════════════════════════════════════════════════════════════════════════
## 🗂️ FILE STRUCTURE & KEY LOCATIONS
═══════════════════════════════════════════════════════════════════════════════

### **Critical Files**:

```
stats/
├── bot/
│   ├── ultimate_bot.py              # Main Discord bot (1931 lines)
│   │   └── Line 1361-1446: Objective stats embed
│   │   └── Line 782-783: Fixed query bindings
│   │   └── Line 1763: db_path = './etlegacy_production.db'
│   │
│   ├── community_stats_parser.py     # Enhanced parser (798 lines)
│   │   └── Line 544-552: TAB split logic
│   │   └── Line 600-606: Extended field processing
│   │   └── Line 607-658: 33 field extraction
│   │
│   └── etlegacy_production.db        # Bot's database (24 KB)
│       └── Contains: sessions, player_stats (with awards JSON)
│
├── dev/
│   ├── bulk_import_stats.py         # Bulk import (has unicode issues)
│   │   └── Line 162-227: Enhanced to store awards JSON
│   │
│   └── [other dev tools]
│
├── local_stats/                      # 3,300+ stats files
│   └── Format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
│
├── test_enhanced_parser.py          # Parser validation
├── test_manual_import.py            # Single-file import
├── show_objective_stats.py          # Display summary
├── verify_awards.py                 # Database verification
│
├── etlegacy_production.db           # Root database (7.5 MB)
│   └── Different schema! Don't confuse with bot's DB
│
└── AI_PROJECT_STATUS.py             # ⭐ THIS FILE
```

### **Database Confusion Warning**:
- **Bot uses**: `bot/etlegacy_production.db` (small, 24 KB)
- **Root has**: `etlegacy_production.db` (large, 7.5 MB, different schema)
- **ALWAYS use bot's database** for imports/testing
- Schema differences:
  - Bot: `date` column in sessions
  - Root: `session_date` column in sessions
  - Bot: Only `player_stats` table
  - Root: Has `player_comprehensive_stats` + `player_stats`

═══════════════════════════════════════════════════════════════════════════════
## 🔧 TECHNICAL DETAILS FOR AI ASSISTANTS
═══════════════════════════════════════════════════════════════════════════════

### **Stats File Format**:

```
^a#^7p^au^7rans^a.^7only\\supply\\legacy3\1\1\1\12:00\12:00
GUID\\PlayerName\rounds\team\\WEAPON_STATS\t33_TAB_SEPARATED_FIELDS

Example line:
FDA127DF\\^0.^7wjs^0:)\0\2\134350968 13 31 1 0 0...[weapons]	2976	3180	64	0...
         ↑         ↑   ↑ ↑ ↑                              ↑
       GUID     Name   R T Weapons (space-sep)           TAB → 33 fields
```

**Parsing Steps**:
1. Skip header lines (start with `^a#`)
2. Split line on `\\` → [GUID, name, rounds, team, stats_section]
3. Split stats_section on first `\t` → [weapon_section, extended_section]
4. Parse weapon_section with `.split()` (space-separated)
5. Parse extended_section with `.split('\t')` (TAB-separated, 33 fields)

### **Key Parser Methods** (community_stats_parser.py):

```python
class C0RNP0RN3StatsParser:
    def parse_stats_file(self, file_path):
        """Main entry point - returns dict with players, map_name, etc."""

    def parse_player_line(self, line):
        """Parses single player line, returns player dict with objective_stats"""

    def strip_color_codes(self, text):
        """Removes ET color codes ( ^ 0-^9, ^ a-^z)"""
```

### **Database Operations**:

```python
# Importing with awards JSON
import json
objective_stats = player.get('objective_stats', {})
awards_json = json.dumps(objective_stats) if objective_stats else None

cursor.execute('''
    INSERT INTO player_stats (
        session_id, player_name, team,
        kills, deaths, damage, kd_ratio, dpm, awards
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (session_id, clean_name, team_name, kills, deaths,
      damage_given, kd_ratio, dpm, awards_json))

# Querying awards
cursor.execute('SELECT player_name, awards FROM player_stats WHERE awards IS NOT NULL')
rows = cursor.fetchall()
for name, awards_json in rows:
    awards = json.loads(awards_json)
    xp = awards.get('xp', 0)
    assists = awards.get('kill_assists', 0)
    # ... use the data
```

### **Bot Command Flow** (!last_session):

1. Connect to `./etlegacy_production.db` (bot's database)
2. Get latest session date: `SELECT DISTINCT date FROM sessions ORDER BY date DESC LIMIT 1`
3. Get all session IDs for that date
4. Query player_stats with `WHERE session_id IN (?, ?, ...)`
5. Aggregate stats across rounds
6. Create multiple embeds:
   - Embed 1: Session overview
   - Embed 2: Top players
   - Embed 3: Team stats & MVPs
   - Embed 4: DPM leaderboard
   - Embed 5: Weapon mastery
   - **Embed 6: Objective & Support Stats** ⭐ NEW
   - Embed 7: Visual graphs (matplotlib)

### **Common Pitfalls & Solutions**:

1. **"Incorrect number of bindings"**
   - Check if query uses `session_ids_str` multiple times
   - Pass `session_ids` once per occurrence
   - Example: `db.execute(query, session_ids + session_ids)`

2. **"No such column: session_date"**
   - Bot's DB uses `date`, not `session_date`
   - Check which database you're working with

3. **"No such table: player_comprehensive_stats"**
   - Bot's DB only has `player_stats`
   - Root DB has both tables
   - Use correct database!

4. **Unicode/Emoji Errors in Windows PowerShell**
   - Replace emojis with ASCII: 🚀 → "[START]"
   - Or use UTF-8 capable terminal
   - Or redirect output to file

5. **Parser Returns Empty objective_stats**
   - Check if file has TAB after weapon stats
   - Verify 33 fields exist in extended_section
   - Use `test_enhanced_parser.py` to debug

═══════════════════════════════════════════════════════════════════════════════
## 📋 TODO LIST & NEXT STEPS
═══════════════════════════════════════════════════════════════════════════════

### ✅ COMPLETED:
1. ✅ Enhanced parser (33 fields)
2. ✅ Database integration (awards JSON)
3. ✅ Bot display (objective stats embed)
4. ✅ Testing (single file import works)
5. ✅ Verification (data queryable and correct)

### 🔄 CURRENT SPRINT - Critical Fixes:
6. 🔧 Fix bulk import unicode issues (Windows PowerShell compatibility)
7. 🔧 Import all 3,300+ historical files to database
8. 🔧 Implement enhanced MVP calculation (weighted formula)
9. 🧪 Test bot in Discord (verify embed displays correctly)
10. 🧪 Test full pipeline end-to-end

### 📊 DATA QUALITY REFINEMENTS:
11. 🔧 Perfect objective timing calculations (edge cases)
12. 🔧 Complete grenade AOE damage attribution
13. 🔧 Refine team switch detection during rounds
14. 🔧 Weapon stat backfilling for old sessions

═══════════════════════════════════════════════════════════════════════════════
## 🎨 DISCORD EMBED PREVIEW (Objective Stats)
═══════════════════════════════════════════════════════════════════════════════

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🎯 Objective & Support Stats                            ┃
┃ Comprehensive battlefield contributions                 ┃
┃━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┃
┃                                                          ┃
┃ 1. PlayerName         │ 2. AnotherPlayer                ┃
┃ XP: 122               │ XP: 119                         ┃
┃ Assists: 1            │ Assists: 9                      ┃
┃ Dynamites: 2/0 P/D    │ Revived: 8 times                ┃
┃ Revived: 2 times      │                                 ┃
┃                       │                                 ┃
┃ 3. ThirdPlayer        │ 4. FourthPlayer                 ┃
┃ XP: 103               │ XP: 89                          ┃
┃ Assists: 7            │ Assists: 10                     ┃
┃ Revived: 1 times      │ Dynamites: 0/1 P/D              ┃
┃                       │ Revived: 1 times                ┃
┃                       │ Multikills: 2x: 1               ┃
┃                                                          ┃
┃ 🎯 S/R = Stolen/Returned | P/D = Planted/Defused        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

═══════════════════════════════════════════════════════════════════════════════
## 🚀 QUICK START GUIDE FOR NEW AI ASSISTANTS
═══════════════════════════════════════════════════════════════════════════════

### **If user asks to...**

**"Test the bot"**:
1. Check if bot is running: Look for terminal with `python ultimate_bot.py`
2. If not running: `cd bot; python ultimate_bot.py` (background)
3. Wait for "Bot ready with 11 commands!"
4. User tests `!last_session` in Discord
5. Check terminal output for errors

**"Import more stats files"**:
1. Use `test_manual_import.py` for single files
2. Update `TEST_FILE` variable to point to desired file
3. Run: `python test_manual_import.py`
4. Verify with: `python verify_awards.py` (update session_id)

**"Fix bulk import"**:
1. Edit `dev/bulk_import_stats.py`
2. Remove/replace emoji characters in logging
3. Or: Batch process with manual imports (loop in Python)

**"Add new stat field"**:
1. Verify field exists in stats file (check TAB-separated section)
2. Update parser: `bot/community_stats_parser.py` line 607-658
3. Add field to objective_stats dictionary
4. Test with: `python test_enhanced_parser.py`
5. Update bot display: `bot/ultimate_bot.py` line 1361-1446

**"Implement MVP calculation"**:
1. Create function in ultimate_bot.py
2. Read awards JSON from player_stats
3. Calculate weighted score (see formula above)
4. Update MVP display in existing embed

**"Debug database issues"**:
1. Always check which database: `bot/etlegacy_production.db` (correct) vs `etlegacy_production.db` (wrong)
2. Verify schema: `PRAGMA table_info(sessions)` and `PRAGMA table_info(player_stats)`
3. Check awards data: `SELECT COUNT(*) FROM player_stats WHERE awards IS NOT NULL`

═══════════════════════════════════════════════════════════════════════════════
## 📞 CONTACT & REFERENCES
═══════════════════════════════════════════════════════════════════════════════

**Key Documentation Files**:
- `COPILOT_INSTRUCTIONS.md` - Original project instructions
- `PROGRESS_REPORT.md` - Development progress log
- `QUICK_STATUS.md` - Quick reference status
- `README.md` - Project overview
- `AI_PROJECT_STATUS.py` - This file (most comprehensive)

**Testing & Verification Scripts**:
- `test_enhanced_parser.py` - Verify 33-field extraction
- `show_objective_stats.py` - Display parsed objective stats
- `test_manual_import.py` - Import single file to database
- `verify_awards.py` - Check awards JSON in database

**Last Major Changes**:
- Date: October 3, 2025
- Changes:
  * Enhanced parser to extract 33 fields
  * Added awards JSON to database
  * Created objective stats Discord embed
  * Fixed query binding issues
- Status: 7/10 tasks completed, bot functional, ready for testing

═══════════════════════════════════════════════════════════════════════════════
## 🎯 SUCCESS METRICS
═══════════════════════════════════════════════════════════════════════════════

**Parser**:
- ✅ Extracts 33/33 fields (100%)
- ✅ Handles TAB-separated format
- ✅ JSON serialization works
- ✅ Tested on real stats files

**Database**:
- ✅ Awards JSON stored successfully
- ✅ Data queryable and deserializes
- ✅ Single file import verified
- ⏳ Bulk import pending (unicode fix needed)

**Bot**:
- ✅ New embed implemented
- ✅ Query fixed (binding issue resolved)
- ✅ Bot starts without errors
- 🔄 Discord display testing in progress

**Overall Progress**: **70% Complete**
- Core functionality: ✅ Working
- Testing phase: 🔄 In progress
- Bulk import: ⏳ Blocked by unicode issue
- MVP calculation: ⏳ Not started

═══════════════════════════════════════════════════════════════════════════════
END OF AI ASSISTANT INSTRUCTIONS
═══════════════════════════════════════════════════════════════════════════════
"""
