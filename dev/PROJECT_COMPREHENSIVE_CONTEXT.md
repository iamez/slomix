# ET:Legacy Discord Bot - Comprehensive Project Context
**Generated:** October 3, 2025  
**Purpose:** Complete understanding of project structure, data flow, and implementation requirements

---

## 🎯 PROJECT OVERVIEW

### Mission
Create a Discord bot that automatically collects, parses, stores, and presents ET:Legacy game statistics from the game server in a user-friendly, professional manner.

### Core Components
1. **Game Server** - `puran.hehe.si:27960` running ET:Legacy with c0rnp0rn3.lua stats collector
2. **Stats Parser** - `bot/community_stats_parser.py` that translates c0rnp0rn3 format
3. **Database** - SQLite database to store all historical stats
4. **Discord Bot** - `bot/ultimate_bot.py` for user interaction and data presentation
5. **SSH Bridge** - Automatic file retrieval from game server

---

## 📊 DATA FLOW ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│  ET:Legacy Game Server (puran.hehe.si)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  c0rnp0rn3.lua - Real-time stats collection          │   │
│  │  Generates: YYYY-MM-DD-HHMMSS-mapname-round-N.txt   │   │
│  └──────────────────────────────────────────────────────┘   │
│       │                                                      │
│       │ Saves to: /home/et/.etlegacy/legacy/gamestats/     │
│       ▼                                                      │
└─────────────────────────────────────────────────────────────┘
        │
        │ SSH/SFTP (Automated every 5 mins)
        ▼
┌─────────────────────────────────────────────────────────────┐
│  Discord Bot Server (Local)                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  SSH Monitor - Detects new files                     │   │
│  │  Downloads to: local_stats/                          │   │
│  └──────────────────────────────────────────────────────┘   │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  community_stats_parser.py                           │   │
│  │  - Parses c0rnp0rn3 format                          │   │
│  │  - Extracts all player/weapon/match data            │   │
│  │  - Handles Round 1 & Round 2 differentials          │   │
│  └──────────────────────────────────────────────────────┘   │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  SQLite Database (etlegacy_*.db)                     │   │
│  │  - Sessions table (match metadata)                   │   │
│  │  - player_comprehensive_stats (all player stats)     │   │
│  │  - weapon_comprehensive_stats (all weapon stats)     │   │
│  │  - player_links (Discord ↔ GUID mapping)           │   │
│  │  - processed_files (tracking)                        │   │
│  └──────────────────────────────────────────────────────┘   │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Discord Bot Commands                                │   │
│  │  /stats, /leaderboard, /match, /compare, etc.       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 C0RNP0RN3.LUA FILE FORMAT

### File Naming Convention
```
YYYY-MM-DD-HHMMSS-mapname-round-N.txt
Examples:
  2025-09-30-211746-etl_adlernest-round-1.txt
  2025-09-30-212222-etl_adlernest-round-2.txt
```

**CRITICAL:** Date/time is essential for archiving and historical analysis!

### File Structure

#### Line 1: Header (Match Metadata)
```
^a#^7p^au^7rans^a.^7only\mapname\modname\defender_team\winner_team\round\time_limit\actual_time
Example:
^a#^7p^au^7rans^a.^7only\etl_adlernest\legacy3\1\1\2\10:00\3:42
```

**Fields:**
- `^a#^7p^au^7rans^a.^7only` - Server name (with color codes)
- `etl_adlernest` - Map name
- `legacy3` - Mod/config name
- `1` - Defender team (1=Axis, 2=Allies)
- `1` - Winner team (1=Axis, 2=Allies)
- `2` - Round number
- `10:00` - Time limit
- `3:42` - Actual round duration

#### Lines 2+: Player Stats (One per line)
```
GUID\PlayerName\Team\Rounds\PlayTime WEAPON_STATS EXTENDED_STATS
```

**Example:**
```
0A26D447\^7c^aa^7rniee\0\1\134219837 0 1 0 0 0 4 12 0 0 2 0 0 0 2 0 49 135 7 0 5 0 0 0 3 0 1 4 0 0 0 1 1 0 0 0 	1028	1147	0	0	1	3	0	1	74.7	31	0	0	1	1	2	0	0	0	0	0	4826	0.0	3.7	0.0	55.4	2.0	1.4	1	29	2	0	0	0	0	3	0	0
```

### Data Sections Breakdown

#### Section 1: Basic Info
- `GUID` - Unique player identifier (8 hex chars)
- `PlayerName` - In-game name (with ET color codes ^0-^9, ^a-^z)
- `Team` - 0=Axis, 1=Axis, 2=Allies (check parser for exact mapping)
- `Rounds` - Number of rounds played
- `PlayTime` - Time played in milliseconds

#### Section 2: Weapon Stats (28 weapons, 5 values each)
140 values total: `kills deaths hits shots headshots` × 28 weapons

**Weapon Order (from C0RNP0RN3_WEAPONS):**
```python
0: WS_KNIFE          10: WS_FLAMETHROWER   20: WS_MG42
1: WS_KNIFE_KBAR     11: WS_GRENADE        21: WS_BROWNING
2: WS_LUGER          12: WS_MORTAR         22: WS_CARBINE
3: WS_COLT           13: WS_MORTAR2        23: WS_KAR98
4: WS_MP40           14: WS_DYNAMITE       24: WS_GARAND
5: WS_THOMPSON       15: WS_AIRSTRIKE      25: WS_K43
6: WS_STEN           16: WS_ARTILLERY      26: WS_MP34
7: WS_FG42           17: WS_SATCHEL        27: WS_SYRINGE
8: WS_PANZERFAUST    18: WS_GRENADELAUNCHER
9: WS_BAZOOKA        19: WS_LANDMINE
```

#### Section 3: Extended Stats (TAB-separated)
After weapon stats, separated by TAB characters:

**Core Combat:**
1. `damage_given` - Total damage dealt
2. `damage_received` - Total damage taken
3. `team_damage_given` - Friendly fire damage dealt
4. `team_damage_received` - Friendly fire damage taken
5. `kills` - Total kills
6. `deaths` - Total deaths
7. `gibs` - Body gibs
8. `team_gibs` - Team member gibs
9. `accuracy` - Overall accuracy percentage
10. `time_played` - Time in seconds
11. `time_axis` - Time on Axis in seconds
12. `time_allies` - Time on Allies in seconds
13. `xp` - Experience points
14. `self_kills` - Suicide count
15. `team_kills` - Teamkill count

**Topshots Array (19 values):**
16. `killing_spree_best` - Longest kill streak
17. `death_spree_worst` - Longest death streak
18. `kill_assists` - Assisted kills
19. `kill_steals` - Stolen kills
20. `headshot_kills` - Total headshots
21. `objectives_stolen` - Objectives captured
22. `objectives_returned` - Objectives returned
23. `dynamites_planted` - Dynamites placed
24. `dynamites_defused` - Dynamites defused
25. `times_revived` - Times medic revived player
26. `bullets_fired` - Total shots
27. `dpm` - Damage per minute
28. `tank_meatshield` - Damage absorption stat
29. `time_dead_ratio` - Percentage of time dead
30. `most_useful_kills` - High-value kills
31. `denied_playtime` - Time denied to enemies (ms)
32. `useless_kills` - Low-value kills
33. `full_selfkills` - Complete suicides
34. `repairs_constructions` - Engineer actions

**Multikills Array (9 values):**
35. `double_kills` - 2 kills rapidly
36. `triple_kills` - 3 kills rapidly
37. `quad_kills` - 4 kills rapidly
38. `multi_kills` - 5 kills
39. `mega_kills` - 6 kills
40. `ultra_kills` - 7 kills
41. `monster_kills` - 8 kills
42. `ludicrous_kills` - 9 kills
43. `holy_shit_kills` - 10+ kills

---

## 🗄️ DATABASE SCHEMA

### Current Status
Multiple `.db` files exist:
- `etlegacy_comprehensive.db`
- `etlegacy_discord_ready.db`
- `etlegacy_fixed_bulk.db`
- `etlegacy_perfect.db`

**ACTION REQUIRED:** Determine production database or create new standardized one.

### Proposed Schema (from initialize_database.py)

#### Table: `sessions`
Match/round metadata
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date DATE NOT NULL,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    server_name TEXT,
    config_name TEXT,
    defender_team INTEGER,
    winner_team INTEGER,
    time_limit TEXT,
    next_time_limit TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, map_name, round_number)
)
```

#### Table: `player_comprehensive_stats`
**ALL** player statistics from c0rnp0rn3.lua
```sql
CREATE TABLE player_comprehensive_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    clean_name TEXT NOT NULL,  -- Name without color codes
    team INTEGER NOT NULL,
    rounds INTEGER DEFAULT 0,
    
    -- Basic combat
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
    
    -- Time and XP
    time_axis INTEGER DEFAULT 0,
    time_allies INTEGER DEFAULT 0,
    time_played REAL DEFAULT 0.0,
    time_played_minutes REAL DEFAULT 0.0,
    xp INTEGER DEFAULT 0,
    
    -- Topshots array (19 fields)
    killing_spree_best INTEGER DEFAULT 0,
    death_spree_worst INTEGER DEFAULT 0,
    kill_assists INTEGER DEFAULT 0,
    kill_steals INTEGER DEFAULT 0,
    headshot_kills INTEGER DEFAULT 0,
    objectives_stolen INTEGER DEFAULT 0,
    objectives_returned INTEGER DEFAULT 0,
    dynamites_planted INTEGER DEFAULT 0,
    dynamites_defused INTEGER DEFAULT 0,
    times_revived INTEGER DEFAULT 0,
    bullets_fired INTEGER DEFAULT 0,
    dpm REAL DEFAULT 0.0,
    tank_meatshield REAL DEFAULT 0.0,
    time_dead_ratio REAL DEFAULT 0.0,
    most_useful_kills INTEGER DEFAULT 0,
    denied_playtime INTEGER DEFAULT 0,
    useless_kills INTEGER DEFAULT 0,
    full_selfkills INTEGER DEFAULT 0,
    repairs_constructions INTEGER DEFAULT 0,
    
    -- Multikills array (9 fields)
    double_kills INTEGER DEFAULT 0,
    triple_kills INTEGER DEFAULT 0,
    quad_kills INTEGER DEFAULT 0,
    multi_kills INTEGER DEFAULT 0,
    mega_kills INTEGER DEFAULT 0,
    ultra_kills INTEGER DEFAULT 0,
    monster_kills INTEGER DEFAULT 0,
    ludicrous_kills INTEGER DEFAULT 0,
    holy_shit_kills INTEGER DEFAULT 0,
    
    -- Calculated fields
    kd_ratio REAL DEFAULT 0.0,
    accuracy REAL DEFAULT 0.0,
    headshot_ratio REAL DEFAULT 0.0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (id)
)
```

#### Table: `weapon_comprehensive_stats`
Per-weapon statistics for each player per session
```sql
CREATE TABLE weapon_comprehensive_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    player_guid TEXT NOT NULL,
    weapon_id INTEGER NOT NULL,      -- 0-27 from C0RNP0RN3_WEAPONS
    weapon_name TEXT NOT NULL,       -- WS_MP40, WS_THOMPSON, etc.
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    headshots INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0.0,
    headshot_ratio REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (id)
)
```

#### Table: `player_links`
Discord user ↔ Game GUID mapping
```sql
CREATE TABLE player_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_guid TEXT UNIQUE NOT NULL,
    discord_id TEXT UNIQUE NOT NULL,
    discord_username TEXT,
    player_name TEXT,                -- Most recent in-game name
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**NOTE:** Players use multiple aliases/fakenames, but GUID remains constant!

#### Table: `processed_files`
Track which stat files have been imported
```sql
CREATE TABLE processed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_size INTEGER,
    player_count INTEGER,
    success INTEGER DEFAULT 1
)
```

---

## 🔧 EXISTING CODE STATUS

### ✅ Working Components

1. **community_stats_parser.py**
   - ✅ Parses c0rnp0rn3.lua format correctly
   - ✅ Handles weapon stats (28 weapons)
   - ✅ Strips ET color codes from names
   - ✅ Creates styled Discord embeds
   - ✅ Round 2 differential calculation (compares Round 1 vs Round 2)
   - ✅ Weapon emoji mapping
   - ✅ K/D ratio formatting
   - ✅ Accuracy bars

2. **ultimate_bot.py**
   - ✅ Discord.py 2.3+ compatible
   - ✅ Uses Cogs pattern
   - ✅ Session management commands
   - ⚠️ Database operations (needs verification)
   - ⚠️ SSH monitoring (needs testing)

3. **Environment Configuration (.env)**
   - ✅ Discord token configured
   - ✅ SSH credentials set
   - ✅ Server paths defined
   - ✅ Database paths configured

### ⚠️ Needs Work

1. **Database Population**
   - ❌ No automated import of existing local_stats files
   - ❌ Schema finalization needed
   - ❌ Bulk import tool needed
   - ❌ Duplicate detection needed

2. **Discord Commands**
   - ❌ `/stats [player]` - Not implemented
   - ❌ `/leaderboard [stat]` - Not implemented
   - ❌ `/match [date/id]` - Not implemented
   - ❌ `/compare [player1] [player2]` - Not implemented
   - ❌ `/history [player]` - Not implemented

3. **SSH Monitoring**
   - ⚠️ Exists but needs testing
   - ⚠️ 5-minute check interval configured
   - ⚠️ File download logic present but unverified

4. **Player Management**
   - ❌ Discord linking system not implemented
   - ❌ Alias management (multiple names → one GUID) not complete
   - ❌ Profile merging not implemented

---

## 🎯 IMMEDIATE PRIORITIES

### Phase 1: Database Foundation
1. ✅ **Finalize database schema** (comprehensive schema exists)
2. 🔲 **Create/select production database**
3. 🔲 **Build bulk import tool** for existing 200+ stat files in local_stats/
4. 🔲 **Test parser accuracy** with 2025 files
5. 🔲 **Implement duplicate detection**
6. 🔲 **Create database validation tool**

### Phase 2: Parser Verification
1. 🔲 **Verify all 43+ data fields** parse correctly
2. 🔲 **Test Round 1/Round 2 differential** calculation
3. 🔲 **Validate weapon stats** (all 28 weapons)
4. 🔲 **Test with edge cases** (disconnects, short games, etc.)

### Phase 3: Bot Commands (After database is populated)
1. 🔲 `/stats [@user or name]` - Recent player stats
2. 🔲 `/leaderboard [kills|kd|accuracy|headshots]` - Rankings
3. 🔲 `/match [date or id]` - Specific match details
4. 🔲 `/compare [@user1] [@user2]` - Head-to-head comparison
5. 🔲 `/history [@user]` - Performance over time

### Phase 4: Automation
1. 🔲 **SSH monitoring** - Auto-download new files
2. 🔲 **Auto-processing** - Parse new files immediately
3. 🔲 **Auto-posting** - Post round results to Discord channel
4. 🔲 **File archiving** - Move processed files to archive/

---

## 📚 REFERENCE FILES

### In Repository
- `bot/community_stats_parser.py` - Main parser (712 lines)
- `bot/ultimate_bot.py` - Discord bot (361 lines)
- `dev/initialize_database.py` - Database schema creator
- `server/endstats_modified.lua` - Endstats awards integration
- `local_stats/` - 200+ stat files for testing

### To Review/Document
- `tools/` - Database utilities
- `dev/production_comprehensive_bot.py` - Production version?
- `dev/comprehensive_discord_bot.py` - Alternative implementation?

---

## 🚨 CRITICAL ISSUES TO RESOLVE

1. **Which database is production?**
   - Multiple .db files exist
   - Need single source of truth
   - Recommend: Create fresh `etlegacy_production.db`

2. **Parser field mapping verification**
   - Need to validate all 43 extended stat fields
   - Confirm weapon order (0-27)
   - Test with multiple 2025 files

3. **GUID → Discord linking strategy**
   - How to handle first-time linking?
   - Command for users to link themselves?
   - Admin override for linking?

4. **Round 2 differential accuracy**
   - Does it correctly calculate Round 2 - Round 1?
   - What if Round 1 file missing?
   - How to handle partial data?

5. **File archive strategy**
   - Keep originals in local_stats/?
   - Move to archive/ after processing?
   - Backup frequency?

---

## 📝 TESTING STRATEGY

### Use 2025 Files (as requested)
```
✅ Available: 2025-09-29-*.txt files
✅ Available: 2025-09-30-*.txt files
```

### Test Cases
1. **Single Round 1 file** - Basic parsing
2. **Round 1 + Round 2 pair** - Differential calculation
3. **Multiple sessions same map** - Data consistency
4. **Multiple sessions different maps** - Map variety
5. **Player with multiple aliases** - GUID tracking
6. **Disconnected players** - Partial data handling

---

## 🔐 GROUND RULES (from user)

1. ✅ **All new dev files go in `/dev` folder**
2. ✅ **Extensive documentation in all scripts**
3. ✅ **Backup before modifying tools/parsers**
4. ✅ **Test with 2025 stat files**
5. ✅ **Focus on database first, commands later**

---

## 📞 QUESTIONS ANSWERED

1. ✅ Bot connects to Discord & SSH
2. ✅ Parser works and translates c0rnp0rn3 format
3. ❌ Database operations not tested yet
4. ✅ All data points tracked (kills, deaths, weapons, objectives, etc.)
5. ✅ Both player-specific and match-wide stats exist
6. ✅ Weapon-specific stats tracked (28 weapons)
7. ✅ Team stats (Axis vs Allies) included
8. ✅ Streaks tracked (killing_spree_best, death_spree_worst)
9. ⚠️ Multiple .db files - need to choose/create production DB
10. ✅ Schema designed comprehensively
11. ✅ Track individual player stats per match
12. ✅ Track cumulative stats over time
13. ✅ Track match metadata (map, date, duration, winner)
14. ✅ Support historical comparisons
15. ✅ Support leaderboards/rankings
16. ✅ Commands planned but not implemented yet
17. ✅ SSH/SFTP code exists (needs testing)
18. ✅ Real-time monitoring configured (5 min interval)
19. ✅ File archiving planned
20. ✅ Link in-game names to Discord users (via GUID)
21. ✅ Multiple aliases per player supported (via GUID)
22. ✅ SQLite chosen (flexible on alternatives)
23. ✅ Current dependencies acceptable
24. ✅ Use discord.py cogs
25. ✅ Backups in `/dev/backups/`
26. ✅ Code comments required
27. ✅ User guides for commands needed

---

## 🎓 LEARNING OBJECTIVES (for user)

- Understand database design
- Learn API/function structure
- Document Discord commands
- Understand data flow
- Learn Python async patterns
- Understand ORM vs raw SQL (if used)

---

## 📋 NEXT STEPS

Before ANY code changes:
1. ✅ **This context document created**
2. 🔲 **Review and verify parser field mapping**
3. 🔲 **Create database inspection/validation tool**
4. 🔲 **Test parse 5-10 recent 2025 files manually**
5. 🔲 **Create bulk import script with progress tracking**
6. 🔲 **Decide on production database name**

After database is populated:
7. 🔲 **Implement basic `/stats` command**
8. 🔲 **Implement `/leaderboard` command**
9. 🔲 **Test Discord embed formatting**
10. 🔲 **Implement remaining commands**

---

**END OF CONTEXT DOCUMENT**
