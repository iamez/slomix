# 🎮 ET:Legacy Discord Stats Bot - Complete Project Context

**Purpose:** This document provides comprehensive context about the entire project for AI assistants and developers. Read this FIRST before making any changes.

**Last Updated:** October 3, 2025  
**Author:** Debugging session with user  
**Status:** Living document - update as system evolves

---

## 📖 Table of Contents

1. [Project Overview](#project-overview)
2. [Game Context - ET:Legacy](#game-context---etlegacy)
3. [Data Flow Pipeline](#data-flow-pipeline)
4. [Time Format Confusion (CRITICAL)](#time-format-confusion-critical)
5. [The DPM Problem](#the-dpm-problem)
6. [Database Schema](#database-schema)
7. [File Formats](#file-formats)
8. [Parser Behavior](#parser-behavior)
9. [Common Pitfalls](#common-pitfalls)
10. [Debug History](#debug-history)

---

## 🎯 Project Overview

### What This Is
A Discord bot that tracks **Enemy Territory: Legacy** (ET:Legacy) game statistics from a dedicated server. Players compete in multiplayer matches, and the bot:
- Imports stats from server-generated files
- Stores comprehensive player statistics in SQLite database
- Provides Discord commands to view stats, leaderboards, MVP, etc.

### Key Components
```
ET:Legacy Game Server (Linux)
├─ c0rnp0rn3.lua - Server-side stats script
└─ Generates .txt files in /home/et/.etlegacy/legacy/gamestats/

         ↓ (files transferred via SSH/manual download)

Python Stats Bot (Windows)
├─ bot/community_stats_parser.py - Parses .txt files
├─ database/etlegacy_production.db - SQLite database
└─ bot/ultimate_bot.py - Discord bot

         ↓ (players use Discord commands)

Discord Server
└─ !last_session, !stats, !leaderboard, etc.
```

---

## 🎮 Game Context - ET:Legacy

### What is ET:Legacy?
- **Genre:** Team-based FPS (First Person Shooter)
- **Game Mode:** Stopwatch - Two rounds per map
  - **Round 1:** Team A attacks, Team B defends
  - **Round 2:** Teams swap sides
- **Objectives:** Complete map objectives within time limit
- **Match Start:** ALL players must be on server and ready (can't join late!)

### Important Game Mechanics
1. **Stopwatch Mode:** 
   - Round 1 sets the time to beat
   - Round 2: Other team tries to beat that time
   
2. **Player Join Rules:**
   - Players CANNOT join mid-round
   - Match only starts when ALL players ready
   - This means: **ALL players play the ENTIRE round**
   
3. **Time Tracking:**
   - Each map has a time limit (e.g., 10 minutes)
   - Actual time = How long round actually took
   - If defenders win: actual_time = time_limit
   - If attackers win: actual_time = time when last objective completed

### Example Match Flow
```
Map: supply (10 minute time limit)

Round 1:
- Team AXIS attacks, Team ALLIES defends
- AXIS completes all objectives in 9:41 (9 minutes 41 seconds)
- Round 1 actual_time: 9:41

Round 2:
- Teams swap: ALLIES attacks, AXIS defends
- ALLIES must complete faster than 9:41 to win
- ALLIES completes in 8:23 (8 minutes 23 seconds)
- Round 2 actual_time: 8:23
- ALLIES WIN (faster time)
```

---

## 🔄 Data Flow Pipeline

### Step-by-Step Data Journey

#### 1. Game Server (c0rnp0rn3.lua)
**Location:** `/home/et/.etlegacy/legacy/gamestats/`  
**Language:** Lua (runs on game server)

**What It Does:**
- Tracks player actions during match
- Writes stats to .txt files when round ends
- File naming: `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`

**What It DOESN'T Do:**
- Does NOT calculate DPM (Damage Per Minute)
- Does NOT write individual player time to Tab[22] field (always 0.0)
- Only writes session-level time in header

#### 2. File Transfer
**Method:** SSH download or manual copy  
**From:** Linux server `/home/et/.etlegacy/legacy/gamestats/*.txt`  
**To:** Windows bot `local_stats/*.txt`

#### 3. Python Parser (community_stats_parser.py)
**Reads:** Raw .txt stats files  
**Outputs:** Structured data for database

**Key Operations:**
1. Parse header (map, round, time, etc.)
2. Parse player lines (damage, kills, deaths, etc.)
3. Calculate DPM using session time from header
4. Round 2: Calculate differential (R2_cumulative - R1_cumulative)
5. Store all data to database

#### 4. SQLite Database (etlegacy_production.db)
**Purpose:** Persistent storage of all stats  
**Key Tables:**
- `sessions` - One row per map/round combo
- `player_comprehensive_stats` - One row per player per round
- `processed_files` - Tracks which files already imported

#### 5. Discord Bot (ultimate_bot.py)
**Purpose:** Query database and display stats  
**Commands:**
- `!last_session` - Show most recent match stats
- `!stats [player]` - Show player statistics
- `!leaderboard` - Show top players
- `!mvp` - Show MVP stats

---

## ⏰ Time Format Confusion (CRITICAL)

### THE PROBLEM: Decimal Minutes Are Confusing!

**User's Valid Concern:**
> "9:41 → 9.7 minutes? WTF? There are 60 seconds in a minute!"

**Why This Confuses People:**
```
9:41 in real life = 9 minutes and 41 seconds
9.7 minutes = 9 minutes and 42 seconds (9 + 0.7*60)

The numbers DON'T match what humans expect!
```

### How We Currently Handle Time

#### 1. Raw File Format (MM:SS)
```
Header: server\map\config\round\team\winner\timelimit\actualtime
Example: ^a#^7p^au^7rans^a.^7only\supply\etl_cfg\1\1\2\10:00\9:41
                                                           ^^^^
                                                        MM:SS format
```

**This is INTUITIVE:** 
- 9:41 = Nine minutes, forty-one seconds
- Everyone understands this instantly

#### 2. Parser Conversion (MM:SS → Decimal Minutes)
```python
def parse_time_to_seconds(self, time_str: str) -> int:
    parts = time_str.split(':')
    minutes = int(parts[0])      # 9
    seconds = int(parts[1])      # 41
    return minutes * 60 + seconds # 581 seconds

# Then converts to decimal minutes:
round_time_minutes = 581 / 60.0  # 9.683... → stored as 9.7
```

**This is CONFUSING:**
- 9.7 minutes doesn't match 9:41
- Users expect whole minutes + seconds
- Decimal minutes are programmer convenience, not user-friendly

#### 3. Database Storage (Decimal Minutes)
```sql
SELECT time_played_minutes FROM player_comprehensive_stats;
-- Results: 9.7, 3.9, 8.4, etc.
```

**This is UNINTUITIVE:**
- 3.9 minutes = 3 minutes 54 seconds (3 + 0.9*60)
- But raw file says 3:51!
- The numbers don't match due to lua rounding

### Why We Use Decimal Minutes (Technical Reason)

**DPM Calculation Requires Decimal:**
```python
# DPM = Damage Per Minute
damage_given = 1328
time_minutes = 3.85  # Must be decimal for division
dpm = 1328 / 3.85 = 344.94
```

**Can't use MM:SS string directly in math:**
```python
# This doesn't work:
dpm = 1328 / "3:51"  # ❌ Can't divide by string
```

### SOLUTION: Store Both Formats

**Recommendation:**
```python
# In database, store BOTH:
time_played_seconds = 231      # Raw seconds (3*60 + 51)
time_played_display = "3:51"   # Human-readable MM:SS

# For calculations:
time_minutes = time_played_seconds / 60.0  # 3.85

# For display:
print(f"Time: {time_played_display}")  # Users see "3:51"
```

**Benefits:**
- ✅ Calculations work (use decimal)
- ✅ Display makes sense (use MM:SS)
- ✅ No confusion in documentation
- ✅ Raw data preserved

---

## 💥 The DPM Problem

### What is DPM?
**DPM = Damage Per Minute**
- Measures how much damage a player deals per minute of gameplay
- Higher DPM = More aggressive/effective player
- Formula: `DPM = Total Damage / Time Played (in minutes)`

### Why DPM Was Wrong (Investigation Summary)

#### Problem 1: Bot Uses AVG() Incorrectly
**What Bot Did:**
```sql
SELECT AVG(dpm) FROM player_comprehensive_stats WHERE player_name = 'vid';
-- Result: 302.53
```

**Why This is WRONG:**
- Averaging rates with different time periods is mathematically incorrect
- Example:
  ```
  Round 1: 10 min, 2500 dmg → 250 DPM
  Round 2: 5 min, 2000 dmg → 400 DPM
  
  Bot calculates: (250 + 400) / 2 = 325 DPM ❌
  Should be: (2500 + 2000) / (10 + 5) = 300 DPM ✅
  ```

**Correct Method:**
```sql
-- Weighted average (sum of damage / sum of time)
SELECT 
    SUM(damage_given) / NULLIF(SUM(time_played_minutes), 0) as correct_dpm
FROM player_comprehensive_stats 
WHERE player_name = 'vid';
```

#### Problem 2: Round 2 Differential Lost Time Data
**The Bug:**
- Round 2 files contain CUMULATIVE stats (R1 + R2 combined)
- Parser must calculate differential: R2_cumulative - R1_cumulative
- OLD parser didn't preserve `time_played_minutes` in differential
- Result: 41% of Round 2 records had time = 0

**Example:**
```
Round 1 file (vid):
- damage_given: 1500
- time_played_minutes: 3.9

Round 2 file (vid) - CUMULATIVE:
- damage_given: 3200 (R1 + R2 combined)
- time_played_minutes: 7.7 (R1 + R2 combined)

Parser calculates differential:
- damage_given: 3200 - 1500 = 1700 ✅
- time_played_minutes: OLD PARSER LOST THIS ❌

After fix:
- time_played_minutes: 7.7 - 3.9 = 3.8 ✅
```

#### Problem 3: Tab[22] Field is Useless
**Discovery:**
- Raw stats files have Tab[22] field supposedly for `time_played_minutes`
- **ACTUAL VALUE:** Always 0.0 for ALL players in ALL files
- **Reason:** c0rnp0rn3.lua script doesn't write player time to this field
- **Parser Solution:** Ignores Tab[22], uses session header time instead

**Evidence:**
```
File: 2025-10-02-213333-supply-round-1.txt
Header: actualtime = 9:41

Player lines (Tab[22] values):
- Player 1: 0.0 ❌
- Player 2: 0.0 ❌
- Player 3: 0.0 ❌
- ALL PLAYERS: 0.0 ❌

Parser gives all players: 9.7 minutes (from header) ✅
```

**Why This is Correct:**
- User confirmed: "Players can't join late, match only starts if all on server and ready"
- Therefore: ALL players play ENTIRE round
- Therefore: ALL players should have SAME time
- Using session time for everyone is CORRECT behavior

---

## 🗄️ Database Schema

### Key Tables

#### 1. sessions
**Purpose:** One row per map/round combination
```sql
CREATE TABLE sessions (
    session_id INTEGER PRIMARY KEY,
    session_date DATE,
    session_time TIME,
    map_name TEXT,
    round_number INTEGER,
    round_outcome TEXT,
    defender_team INTEGER,
    winner_team INTEGER,
    map_time TEXT,
    actual_time TEXT,
    config_name TEXT,
    server_name TEXT,
    total_players INTEGER,
    mvp_player_name TEXT,
    import_timestamp DATETIME
);
```

**Key Fields:**
- `actual_time` - How long round took (MM:SS format string)
- `round_number` - 1 or 2
- `round_outcome` - "Attackers Win", "Defenders Win", etc.

#### 2. player_comprehensive_stats
**Purpose:** One row per player per round
```sql
CREATE TABLE player_comprehensive_stats (
    stat_id INTEGER PRIMARY KEY,
    session_id INTEGER,
    player_name TEXT,
    player_guid TEXT,
    team INTEGER,
    
    -- Core Stats
    kills INTEGER,
    deaths INTEGER,
    damage_given INTEGER,
    damage_received INTEGER,
    
    -- Time & Performance
    time_played_minutes REAL,  -- Currently stored as decimal (CONFUSING!)
    dpm REAL,                   -- Damage Per Minute
    kd_ratio REAL,
    
    -- Objective Stats
    obj_captured INTEGER,
    obj_destroyed INTEGER,
    obj_returned INTEGER,
    obj_taken INTEGER,
    
    -- Support Stats
    revives INTEGER,
    medpacks INTEGER,
    ammopacks INTEGER,
    
    -- Weapon Stats (JSON)
    weapon_stats TEXT,
    
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

**Key Fields:**
- `time_played_minutes` - DECIMAL format (e.g., 9.7) - CONFUSING!
- `dpm` - Calculated by parser using session time
- `session_id` - Links to sessions table

#### 3. processed_files
**Purpose:** Track which files already imported (prevent duplicates)
```sql
CREATE TABLE processed_files (
    file_id INTEGER PRIMARY KEY,
    filename TEXT UNIQUE,
    import_timestamp DATETIME,
    session_id INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

---

## 📄 File Formats

### Stats File Format (Generated by c0rnp0rn3.lua)

#### File Naming Convention
```
YYYY-MM-DD-HHMMSS-mapname-round-N.txt

Examples:
2025-10-02-211808-etl_adlernest-round-1.txt
2025-10-02-212249-etl_adlernest-round-2.txt
2025-10-02-213333-supply-round-1.txt
```

#### File Structure
```
LINE 1: HEADER (backslash-delimited)
server\map\config\round\defenderteam\winnerteam\timelimit\actualtime

LINE 2+: PLAYER DATA (space + TAB delimited)
<weapon_stats> TAB <field1> TAB <field2> TAB ... TAB <field37>
```

#### Header Example
```
^a#^7p^au^7rans^a.^7only\supply\etl_cfg\1\1\2\10:00\9:41

Fields:
[0] server_name: ^a#^7p^au^7rans^a.^7only
[1] map_name: supply
[2] config: etl_cfg
[3] round_number: 1
[4] defender_team: 1 (AXIS)
[5] winner_team: 2 (ALLIES)
[6] time_limit: 10:00 (MM:SS)
[7] actual_time: 9:41 (MM:SS)
```

#### Player Line Example
```
<weapon_stats> TAB f1 TAB f2 TAB ... TAB f37

Weapon stats (space-delimited):
GUID name WS_KNIFE hits shots kills deaths hs ... WS_COLT hits shots kills deaths hs ...

Tab Fields (37 total):
[0] weapon_stats (parsed separately)
[1] damage_given
[2] damage_received
[3] team_damage
[4] team_kills
[5] kills
[6] deaths
[7] gibs
[8] suicides
[9] team_gibs
[10] obj_captured
[11] obj_destroyed
[12] obj_returned
[13] obj_taken
[14] obj_checkpoint
[15] revives
[16] ammopacks
[17] medpacks
[18] npc_kills
[19] disguises
[20] class (0-4: soldier, medic, engineer, field ops, covert ops)
[21] dpm (ALWAYS 0.0 - lua doesn't calculate this)
[22] time_played_minutes (ALWAYS 0.0 - lua doesn't write this)
[23-36] Other fields...
```

**CRITICAL:** Fields 21 and 22 are ALWAYS 0.0 in raw files!

---

## 🔧 Parser Behavior

### community_stats_parser.py

#### Main Entry Point
```python
def parse_stats_file(self, filename: str) -> dict:
    """Parse a single stats file and return structured data"""
```

#### Key Steps

##### 1. Read File
```python
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()
```

##### 2. Parse Header
```python
header = lines[0].strip()
header_parts = header.split('\\')

server_name = header_parts[0]
map_name = header_parts[1]
config = header_parts[2]
round_num = int(header_parts[3])
defender_team = int(header_parts[4])
winner_team = int(header_parts[5])
map_time = header_parts[6]        # MM:SS string
actual_time = header_parts[7]     # MM:SS string
```

##### 3. Parse Time (Convert MM:SS to seconds)
```python
def parse_time_to_seconds(self, time_str: str) -> int:
    """Convert time string (MM:SS or M:SS) to seconds"""
    if ':' in time_str:
        parts = time_str.split(':')
        minutes = int(parts[0])
        seconds = int(parts[1])
        return minutes * 60 + seconds
    else:
        return int(time_str)
```

**Example:**
```python
actual_time = "9:41"
seconds = parse_time_to_seconds("9:41")  # 9*60 + 41 = 581
minutes = seconds / 60.0                  # 581 / 60 = 9.683...
```

##### 4. Parse Player Lines
```python
for line in lines[1:]:
    if line.strip() and '\\' in line:
        player_data = self.parse_player_line(line)
        players.append(player_data)
```

##### 5. Calculate DPM (Using Session Time)
```python
round_time_seconds = self.parse_time_to_seconds(actual_time)
round_time_minutes = round_time_seconds / 60.0  # Convert to decimal

for player in players:
    damage_given = player.get('damage_given', 0)
    player['dpm'] = damage_given / round_time_minutes
```

**Why Session Time for All Players?**
- Tab[22] is always 0.0 (useless)
- Players can't join late (all play full round)
- Therefore: Everyone gets same time (from header)

##### 6. Round 2 Differential Calculation
```python
def calculate_round_2_differential(self, r2_cumulative, r1_data):
    """
    Round 2 files contain CUMULATIVE stats (R1 + R2 combined).
    Must subtract Round 1 to get Round 2-only stats.
    """
    differential_player = {
        'objective_stats': {}  # MUST preserve this!
    }
    
    # Calculate differentials for all fields
    for key in r2_obj:
        if key == 'time_played_minutes':
            r2_time = r2_obj.get('time_played_minutes', 0)
            r1_time = r1_obj.get('time_played_minutes', 0)
            diff_time = max(0, r2_time - r1_time)
            differential_player['objective_stats']['time_played_minutes'] = diff_time
        else:
            # Calculate differential for other fields
            differential_player['objective_stats'][key] = r2_obj[key] - r1_obj[key]
```

**Example:**
```
Round 1 (vid):
- damage: 1500
- time: 3.9

Round 2 CUMULATIVE (vid):
- damage: 3200 (total both rounds)
- time: 7.7 (total both rounds)

Differential (R2 only):
- damage: 3200 - 1500 = 1700 ✅
- time: 7.7 - 3.9 = 3.8 ✅
```

---

## ⚠️ Common Pitfalls

### 1. Decimal Minutes Are Confusing
**Problem:** 9:41 becomes 9.7, which confuses users  
**Solution:** Store both seconds AND display format (MM:SS)

### 2. Can't Average Rates
**Problem:** `AVG(dpm)` gives wrong results  
**Solution:** Use weighted average: `SUM(damage) / SUM(time)`

### 3. Tab[22] Field is Useless
**Problem:** Always 0.0 in raw files  
**Solution:** Use session header time for all players

### 4. Round 2 is Cumulative
**Problem:** Round 2 files contain R1+R2 combined  
**Solution:** Must subtract Round 1 data to get R2-only

### 5. Round 2 Differential Lost Data
**Problem:** Old parser didn't preserve objective_stats  
**Solution:** Fixed in lines 386-417 of parser

### 6. Players Can't Join Late
**Important:** All players play full round  
**Implication:** Using same time for everyone is CORRECT

### 7. Lua Rounding Creates Confusion
**Problem:** Lua rounds 3.85 to 3.9  
**Example:**
```
Raw file: 3:51 = 3.85 minutes
Lua writes: 3.9 minutes (rounded)
Users confused: "Why don't they match?"
```

---

## 📜 Debug History

### October 3, 2025 - The Great DPM Investigation

#### Initial Problem
User: "debug !last_session more explicitly the dpm, i want to know exactly how we ended up with the dpm we did"

**Symptoms:**
- Bot shows vid: 302.53 DPM
- User calculates: ~514.88 DPM
- Error: 70% difference!

#### Investigation Journey

**Phase 1: Trace DPM Source**
- Created `trace_dpm_source.py`
- Found: DPM comes from parser, NOT lua script
- Discovery: Field 21 (DPM) is always 0.0 in raw files

**Phase 2: Found Bot Math Error**
- Bot uses `AVG(dpm)` - mathematically wrong
- Should use weighted average: `SUM(damage) / SUM(time)`

**Phase 3: Found Missing Time Data**
- 41% of October 2nd records had time = 0
- Parser was losing time_played_minutes in Round 2 differential

**Phase 4: Deep Data Investigation**
- User became suspicious: "this round is supper susspicous to me"
- Created `trace_data_source.py` to find exact file sources
- Created `parse_raw_files.py` to check raw file contents

**Phase 5: Critical Discoveries**
1. **Tab[22] Always 0.0:** Lua doesn't write player time
2. **Parser Uses Session Time:** Gets time from header (correct!)
3. **Players Can't Join Late:** User revealed match start rules
4. **Decimal Minutes Confusing:** 9:41 ≠ 9.7 in user's mind

#### Resolution
1. ✅ Fixed Round 2 differential to preserve time_played_minutes
2. ✅ Validated parser uses correct approach (session time)
3. ✅ Understood Tab[22] is useless (always 0.0)
4. ⏳ Need to store both time formats (seconds + MM:SS display)
5. ⏳ Need to update bot query to use weighted average
6. ⏳ Need to re-import database with fixed parser

---

## 🚀 Recommendations for Future AI

### Before Making Changes

1. **Read this entire document** - Understand the big picture
2. **Understand game mechanics** - Stopwatch mode, can't join late, etc.
3. **Know the data pipeline** - Server → Files → Parser → Database → Bot
4. **Check existing bugs** - Don't re-introduce fixed issues

### When Debugging

1. **Trace backwards** - Bot → Database → Parser → Raw files
2. **Verify each step** - Don't assume, check actual values
3. **Check raw files** - Parser might be losing data
4. **Question everything** - User insights often reveal hidden issues

### When Displaying Time

1. **Store seconds** - For calculations
2. **Display MM:SS** - For users
3. **Never show decimal minutes** - Confuses everyone
4. **Document conversions** - Be explicit about format changes

### When Calculating DPM

1. **Never use AVG(dpm)** - Mathematically wrong
2. **Use weighted average** - `SUM(damage) / SUM(time)`
3. **Handle time=0 cases** - Check for division by zero
4. **Validate results** - Do manual spot checks

---

## 📊 Quick Reference

### Important File Locations
```
G:\VisualStudio\Python\stats\
├── bot/
│   ├── community_stats_parser.py - Stats file parser
│   └── ultimate_bot.py - Discord bot
├── database/
│   └── etlegacy_production.db - Main database
├── local_stats/ - Raw .txt stats files
├── logs/
│   └── etconsole.log - Server console logs
└── docs/
    └── COMPLETE_PROJECT_CONTEXT.md - This file!
```

### Important Database Queries

#### Get Player's True DPM (Weighted Average)
```sql
SELECT 
    player_name,
    SUM(damage_given) as total_damage,
    SUM(time_played_minutes) as total_time,
    SUM(damage_given) / NULLIF(SUM(time_played_minutes), 0) as correct_dpm
FROM player_comprehensive_stats
WHERE session_date = '2025-10-02'
GROUP BY player_name;
```

#### Check for Missing Time Data
```sql
SELECT 
    COUNT(*) as records_with_zero_time
FROM player_comprehensive_stats
WHERE time_played_minutes = 0 OR time_played_minutes IS NULL;
```

#### Find Round 2 Records
```sql
SELECT 
    ps.*,
    s.round_number,
    s.actual_time
FROM player_comprehensive_stats ps
JOIN sessions s ON ps.session_id = s.session_id
WHERE s.round_number = 2;
```

### Time Format Conversions

#### MM:SS to Seconds
```python
def mmss_to_seconds(time_str: str) -> int:
    """Convert 'MM:SS' to total seconds"""
    if ':' not in time_str:
        return int(time_str)
    parts = time_str.split(':')
    minutes = int(parts[0])
    seconds = int(parts[1])
    return minutes * 60 + seconds

# Example: "9:41" → 581 seconds
```

#### Seconds to MM:SS
```python
def seconds_to_mmss(seconds: int) -> str:
    """Convert seconds to 'MM:SS' display format"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"

# Example: 581 → "9:41"
```

#### Seconds to Decimal Minutes (For DPM Calculation)
```python
def seconds_to_decimal_minutes(seconds: int) -> float:
    """Convert seconds to decimal minutes for math"""
    return seconds / 60.0

# Example: 581 → 9.683333...
```

---

## 🎓 Key Lessons Learned

### Technical Lessons
1. **Always verify data sources** - Don't assume lua calculates what fields suggest
2. **Check raw files** - Parser can lose data during processing
3. **Mathematical correctness** - Can't average rates with different denominators
4. **Preserve all fields** - Especially in differential calculations

### Communication Lessons
1. **Decimal minutes confuse users** - Use MM:SS for display
2. **Show your work** - Let users verify calculations
3. **Listen to domain experts** - User knows game mechanics
4. **Document as you go** - Don't wait until end

### Debugging Lessons
1. **Start with symptoms** - What's wrong from user perspective?
2. **Trace backwards** - Follow data from display to source
3. **Verify assumptions** - Check ACTUAL values in files
4. **Question everything** - Field names can be misleading

---

## 🔄 Future Improvements

### High Priority
1. Store both time formats (seconds + MM:SS display)
2. Update bot queries to use weighted average DPM
3. Re-import database with fixed parser
4. Add validation to catch time=0 during import

### Medium Priority
1. Add unit tests for parser differential calculations
2. Create data integrity checks for imported sessions
3. Add error handling for malformed files
4. Implement dual DPM system (session vs player time)

### Low Priority
1. Optimize database queries
2. Add more Discord commands
3. Implement web dashboard
4. Add real-time stats import

---

## 📞 Getting Help

### For AI Assistants
If you're an AI working on this project and get stuck:

1. **Read this document thoroughly**
2. **Check the debug history section**
3. **Look at recent fixes** in git history
4. **Verify against raw files** - Don't trust database alone
5. **Ask user about game mechanics** - They know the domain

### For Human Developers
If you're a human taking over this project:

1. **Start with this document** - Understand the system
2. **Read the markdown files** in docs/ and root directory
3. **Check recent commits** for context
4. **Test with October 2nd data** - Known good test case
5. **Join Discord server** - Talk to users

---

## 📝 Document Maintenance

### Update This Document When:
- ✅ New features added
- ✅ Bugs discovered and fixed
- ✅ Database schema changes
- ✅ File formats change
- ✅ New insights about game mechanics
- ✅ Parser behavior changes

### Version History
- **v1.0** - October 3, 2025 - Initial creation from debugging session

---

**END OF DOCUMENT**

Remember: This project tracks competitive gaming stats. Accuracy matters. When in doubt, trace back to raw files and verify against actual game behavior. And ALWAYS use MM:SS for display - decimal minutes confuse everyone! 🎮
