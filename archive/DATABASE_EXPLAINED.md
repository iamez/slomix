# 📚 DATABASE STRUCTURE EXPLAINED - Simple Guide

**Created:** October 4, 2025  
**For:** Understanding how ET:Legacy stats database works

---

## 🎯 THE BIG PICTURE

Think of your database like a **filing cabinet** with different **drawers** (tables). Each drawer stores a specific type of information.

### **The 4 Main Drawers (Tables):**

```
📁 sessions                      ← One folder per game round
   └── 📄 Each session = 1 game round (map + round number)
   
📁 player_comprehensive_stats    ← Player records for each session
   └── 📄 Each record = 1 player's stats in 1 session
   
📁 weapon_comprehensive_stats    ← Weapon details per player per session
   └── 📄 Each record = 1 weapon used by 1 player in 1 session
   
📁 player_objective_stats        ← Objective/support actions
   └── 📄 Each record = 1 player's objective stats in 1 session
```

---

## 📊 TABLE 1: `sessions` - The Game Sessions

**What it stores:** Basic info about each game round played

**Think of it as:** The cover page of each game's report

**Example:**
```
Session ID: 1234
Date: 2025-10-02
Map: etl_adlernest
Round: 1 (first round)
Time Played: 11:26 (686 seconds)
```

**Key Point:** Each round (Round 1, Round 2) gets its own session record!

---

## 📊 TABLE 2: `player_comprehensive_stats` - The Main Player Stats

**What it stores:** ALL the main stats for each player in each session

**Think of it as:** The detailed scorecard for each player in each game

**This is the BIGGEST table** - it has 35 columns storing:

### Combat Stats (what you do in battle):
- `kills` - How many enemies you killed
- `deaths` - How many times you died
- `damage_given` - Total damage you dealt
- `damage_received` - Total damage you took
- `headshot_kills` - Headshots you scored
- `gibs` - Overkill kills (gibbing enemies)
- `self_kills` - Times you killed yourself (oops!)
- `team_kills` - Times you killed teammates (oops x2!)

### Time Stats:
- `time_played_seconds` - How many seconds you played (INTEGER - this is the REAL number!)
- `time_played_minutes` - Same but in minutes (REAL number, calculated from seconds)
- `time_display` - Pretty format like "11:26" for showing to users

### Performance Metrics (calculated):
- `dpm` - Damage Per Minute (how much damage you do per minute)
- `kd_ratio` - Kill/Death ratio (kills divided by deaths)
- `efficiency` - Overall performance score

### Objective Stats (from c0rnp0rn3.lua):
- `xp` - Experience points earned
- `killing_spree_best` - Best kill streak
- `death_spree_worst` - Worst death streak  
- `kill_assists` - Times you helped kill someone
- `kill_steals` - Times you "stole" a kill
- `objectives_stolen` - Flags/documents stolen
- `objectives_returned` - Flags/documents returned
- `dynamites_planted` - Dynamite charges planted
- `dynamites_defused` - Dynamites you defused
- `times_revived` - Times a medic revived you

**Example Record:**
```
Player: vid
Session: etl_adlernest Round 1
Kills: 9, Deaths: 3, K/D: 3.00
Damage Given: 1328, Damage Received: 1105
Time Played: 686 seconds (11:26)
DPM: 116.2
XP: 48
```

---

## 📊 TABLE 3: `weapon_comprehensive_stats` - The Weapon Details

**What it stores:** How well you used each weapon in each session

**Think of it as:** Your weapon report card

**Each record tracks ONE weapon used by ONE player in ONE session:**
- `weapon_name` - Which weapon (e.g., "MP40", "Thompson", "Panzerfaust")
- `hits` - How many shots hit
- `shots` - How many shots fired
- `kills` - Kills with this weapon
- `deaths` - Deaths while holding this weapon
- `headshots` - Headshots with this weapon
- `accuracy` - Hit percentage (hits/shots * 100)

**Example Records for vid in etl_adlernest Round 1:**
```
MP40:      52 hits / 98 shots (53.1% accuracy) - 5 kills
Thompson:  31 hits / 67 shots (46.3% accuracy) - 3 kills
Grenade:   3 hits / 5 shots (60% accuracy) - 1 kill
```

---

## 📊 TABLE 4: `player_objective_stats` - The Support Actions

**What it stores:** All the objective and support-related actions

**Think of it as:** Everything you did beyond just shooting

**This table has 26 columns for:**
- Construction work (built/destroyed)
- Landmines (planted/spotted)
- Health packs given
- Ammo packs given
- Revives performed
- Useful vs useless kills
- Time you denied enemy team (by killing them)
- Tank damage absorbed

**Why separate table?** Because these stats are different from combat stats and not every player does them every round.

---

## 🔗 HOW TABLES CONNECT (Relationships)

This is the **KEY** to understanding databases!

```
sessions (Session ID: 1234)
    │
    ├─► player_comprehensive_stats (Player "vid" in Session 1234)
    │       │
    │       ├─► weapon_comprehensive_stats (vid's MP40 in Session 1234)
    │       ├─► weapon_comprehensive_stats (vid's Thompson in Session 1234)
    │       └─► weapon_comprehensive_stats (vid's Grenade in Session 1234)
    │
    ├─► player_comprehensive_stats (Player "olz" in Session 1234)
    │       └─► weapon_comprehensive_stats (olz's weapons...)
    │
    └─► player_objective_stats (All players' objective stats in Session 1234)
```

**The Magic: `session_id` field** - This connects everything!
- Every player record has a `session_id` pointing to which game it's from
- Every weapon record has a `session_id` pointing to which game it's from
- This way you can find all players in a session, or all sessions a player was in!

---

## 🌊 THE DATA FLOW - From Game to Database

### **STEP 1: Game Server (c0rnp0rn3.lua)**
The Lua script runs on game server and writes a `.txt` file when round ends:

```
File: 2025-10-02-211808-etl_adlernest-round-1.txt

Header:
ETL Server\etl_adlernest\3on3\1\2\2\10:00\10:00\686

Player Lines (one per player):
12345678\vid\1\2\134217727 [weapon data] \t [38 TAB-separated stats]
87654321\olz\1\1\134217727 [weapon data] \t [38 TAB-separated stats]
```

**The 38 TAB-separated fields c0rnp0rn3.lua writes:**
1. damage_given
2. damage_received  
3. team_damage_given
4. team_damage_received
5. gibs
6. self_kills
7. team_kills
8. team_gibs
9. time_played_percent
10. xp
11. killing_spree
12. death_spree
13. kill_assists
14. kill_steals
15. headshot_kills
16. objectives_stolen
17. objectives_returned
18. dynamites_planted
19. dynamites_defused
20. times_revived
21. bullets_fired
22. dpm (Lua writes 0.0, we calculate real DPM)
23. time_played_minutes
24. tank_meatshield
25. time_dead_ratio
26. time_dead_minutes
27. kd_ratio
28. useful_kills
29. denied_playtime
30. multikill_2x
31. multikill_3x
32. multikill_4x
33. multikill_5x
34. multikill_6x
35. useless_kills
36. full_selfkills
37. repairs_constructions
38. revives_given

---

### **STEP 2: Parser (community_stats_parser.py)**
Python reads the `.txt` file and extracts data into a dictionary:

```python
result = {
    'map_name': 'etl_adlernest',
    'round_num': 1,
    'actual_time': '11:26',
    'players': [
        {
            'guid': '12345678',
            'name': 'vid',
            'team': 2,
            'kills': 9,
            'deaths': 3,
            'objective_stats': {
                'damage_given': 1328,
                'damage_received': 1105,
                'gibs': 3,
                'xp': 48,
                'time_played_minutes': 11.43,
                # ... all 38 fields ...
            },
            'weapon_stats': [
                {'name': 'MP40', 'kills': 5, ...},
                {'name': 'Thompson', 'kills': 3, ...},
            ]
        }
    ]
}
```

---

### **STEP 3: Bulk Import (bulk_import_stats.py)**
Takes parser output and inserts into database:

```python
# 1. Create session record
INSERT INTO sessions (session_date, map_name, round_number, actual_time)
VALUES ('2025-10-02', 'etl_adlernest', 1, '11:26')
# Gets back session_id = 1234

# 2. Insert player stats (one per player)
INSERT INTO player_comprehensive_stats (
    session_id, player_guid, player_name, team,
    kills, deaths, damage_given, damage_received,
    gibs, xp, time_played_seconds, dpm, kd_ratio,
    # ... all the columns ...
) VALUES (1234, '12345678', 'vid', 2, 9, 3, 1328, 1105, ...)

# 3. Insert weapon stats (one per weapon per player)
INSERT INTO weapon_comprehensive_stats (
    session_id, player_guid, weapon_name,
    hits, shots, kills, accuracy
) VALUES (1234, '12345678', 'MP40', 52, 98, 5, 53.1)

# 4. Insert objective stats
INSERT INTO player_objective_stats (
    session_id, player_guid,
    objectives_stolen, dynamites_planted, ...
) VALUES (1234, '12345678', 0, 2, ...)
```

---

### **STEP 4: Discord Bot Queries**
When user types `!last_session`, bot queries database:

```python
# Get latest session
SELECT * FROM sessions ORDER BY id DESC LIMIT 1

# Get all players in that session
SELECT * FROM player_comprehensive_stats WHERE session_id = 1234

# Get top DPM players
SELECT player_name, dpm 
FROM player_comprehensive_stats 
WHERE session_id = 1234 
ORDER BY dpm DESC 
LIMIT 10

# Get weapon stats for a player
SELECT * FROM weapon_comprehensive_stats 
WHERE session_id = 1234 AND player_guid = '12345678'
```

---

## ❓ YOUR QUESTION: Do We Need Separate Tables?

**YES! Here's why:**

### **Why NOT put everything in one giant table?**

**Bad Approach:** One huge table with all stats
```
player_stats_EVERYTHING:
- session info (6 columns)
- player basic (10 columns)
- player combat (15 columns)
- player objective (20 columns)
- weapon1_stats (7 columns)
- weapon2_stats (7 columns)
- weapon3_stats (7 columns)
... 28 weapons × 7 columns = 196 columns!
Total: 250+ columns!!!
```

**Problems:**
1. **Waste of space** - Most players don't use all 28 weapons, but table reserves space for all
2. **Can't query weapons** - How do you find "all players who used MP40"?
3. **Fixed weapon count** - What if game adds weapon 29?
4. **Messy updates** - Changing one weapon stat requires finding the right column
5. **Duplication** - Session info repeated for every player

---

### **Good Approach: Separate Tables (What We Have)**

**Benefits:**
1. **Efficient storage** - Only store weapons actually used
2. **Flexible queries** - "Show me all MP40 kills" is easy
3. **Scalable** - Adding weapon 29 just adds more rows, not new columns
4. **Clean organization** - Each table has one purpose
5. **No duplication** - Session info stored once

**Example of power:**
```sql
-- Find best MP40 players across ALL sessions:
SELECT player_guid, SUM(kills) as total_mp40_kills
FROM weapon_comprehensive_stats
WHERE weapon_name = 'MP40'
GROUP BY player_guid
ORDER BY total_mp40_kills DESC
LIMIT 10

-- Find maps where vid had best DPM:
SELECT map_name, dpm
FROM player_comprehensive_stats
WHERE player_guid = '12345678'
ORDER BY dpm DESC
LIMIT 5

-- Find total kills per session:
SELECT session_id, SUM(kills) as total_kills
FROM player_comprehensive_stats
GROUP BY session_id
```

---

## 🎯 CURRENT STATUS OF YOUR DATABASE

✅ **Database schema created** (via `create_clean_database.py`)
- 4 tables with correct structure
- Indexes for fast queries
- Ready to receive data

❌ **Bulk import has wrong field mapping** (needs fixing)
- Only inserts 13 fields into player_comprehensive_stats (should be 35!)
- Missing: team_damage, gibs, self_kills, xp, time_played_seconds, etc.

✅ **Parser works correctly**
- Extracts all 38 fields from c0rnp0rn3.lua output
- Provides complete data to importer

---

## 🔧 WHAT NEEDS TO HAPPEN NEXT

1. **Fix `dev/bulk_import_stats.py`** - Update INSERT statements to include all fields:
   - player_comprehensive_stats: Insert ALL 35 columns
   - player_objective_stats: Map parser fields correctly

2. **Run bulk import** - Import all 1,862 stat files

3. **Test bot commands** - Verify `!last_session` shows correct data

---

## 📖 KEY TERMS EXPLAINED

- **Schema** = The blueprint/structure (what tables exist, what columns they have)
- **Table** = A collection of related records (like a drawer in filing cabinet)
- **Column** = A field in a record (like "name", "kills", "deaths")
- **Row/Record** = One entry in a table (one player's stats, one session, etc.)
- **Primary Key (PK)** = Unique ID for each record (like `id` field)
- **Foreign Key (FK)** = Reference to another table (like `session_id` pointing to sessions table)
- **Index** = Speed boost for queries (like index in back of book)
- **Query** = Request for data ("SELECT * FROM players WHERE kills > 10")

---

## 💡 ANALOGY: Database Like a Library

**Sessions table** = Card catalog (lists all books/games)  
**Player_comprehensive_stats table** = The books themselves (main content)  
**Weapon_comprehensive_stats table** = Appendices in books (detailed weapon info)  
**Player_objective_stats table** = Supplementary materials (extra info)  
**session_id** = Call number that connects catalog to books

When someone asks "Show me game from Oct 2nd", you:
1. Look up session in card catalog (sessions table)
2. Get session_id (like call number)
3. Find all player records with that session_id (like finding all books with that call number)
4. Find all weapon records with that session_id
5. Combine everything and show user!

---

**Questions? Read the context docs or ask!**
