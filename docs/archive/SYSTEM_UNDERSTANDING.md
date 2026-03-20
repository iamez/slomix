# 🎮 ET:Legacy Stats Bot - Complete System Understanding

**Research Date:** November 7, 2025  
**Purpose:** Deep dive into how the system works, file tracking, and Round 1/Round 2 pairing

---

## 🎯 What This Bot Does

### Core Purpose

Tracks player statistics from **Wolfenstein: Enemy Territory Legacy** game servers and provides Discord-based analytics, leaderboards, and session summaries.

### Key Features

1. **Real-time stats tracking** - Monitors game server for new stats files
2. **Round-by-round analytics** - Each match has 2 rounds (Round 1 and Round 2)
3. **Match summaries** - Cumulative stats for entire matches (R1 + R2 combined)
4. **Discord integration** - 50+ commands for querying stats (!stats, !last_session, !top, etc.)
5. **Team detection** - AI-powered team assignment (probabilistic, 5 different algorithms)
6. **Weapon breakdowns** - Per-weapon accuracy, kills, headshots
7. **Gaming sessions** - Groups rounds by 60-minute gaps (handles overnight sessions)
8. **Leaderboards** - Top players by various metrics

---

## 📁 How Stats Files Appear

### File Generation Flow

```python
ET:Legacy Game Server (Running on VPS or Dedicated Server)
  │
  │ [After each round ends]
  ▼
Stats Mod (C0RNP0RN3.lua) writes .txt file
  │
  ▼
Remote Directory: /path/to/gamestats/
  │
  │ Files appear in this pattern:
  │ ✅ 2025-11-06-213045-supply-round-1.txt      ← Round 1 ends at 21:30:45
  │    (10-20 minutes pass while Round 2 is played)
  │ ✅ 2025-11-06-215312-supply-round-2.txt      ← Round 2 ends at 21:53:12
  │
  ▼
SSH Monitor (bot/services/automation/ssh_monitor.py)
  │ - Checks remote directory every X minutes
  │ - Compares with processed_files table
  │ - Downloads new files to local_stats/
  │
  ▼
Local Directory: bot/local_stats/
  │
  ▼
Parser (bot/community_stats_parser.py)
  │
  ▼
Database (rounds, player_comprehensive_stats, weapon_comprehensive_stats)
  │
  ▼
Discord Bot Posts Stats
```text

### File Naming Convention

**Format:** `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`

**Examples:**

```text
2025-11-06-213045-supply-round-1.txt
  │    │    │   │      │       │   └─ Round number (1 or 2)
  │    │    │   │      │       └───── Always "round"
  │    │    │   │      └───────────── Map name (supply, goldrush, etc.)
  │    │    │   └──────────────────── Time (HHMMSS) when round ENDED
  │    │    └──────────────────────── Day
  │    └───────────────────────────── Month
  └────────────────────────────────── Year

2025-11-06-215312-supply-round-2.txt
  ↑ Same date, ~23 minutes later (round took ~23 min to play)
```yaml

**Critical Insight:** The timestamp is when the round **ENDED**, not when it started!

---

## 🔍 How Round 1 and Round 2 Are Tracked

### The Original Tracking System (That We Accidentally Broke)

#### 1. **match_id Generation (ORIGINAL WORKING VERSION)**

```python
# In postgresql_database_manager.py line 827:
match_id = filename.replace('.txt', '')

# Result for Round 1:
match_id = "2025-11-06-213045-supply-round-1"
#           ^^^^^^^^^^^^^^^^^^^^^^ INCLUDES TIMESTAMP

# Result for Round 2 (DIFFERENT match_id):
match_id = "2025-11-06-215312-supply-round-2"
#           ^^^^^^^^^^^^^^^^^^^^^^ DIFFERENT TIMESTAMP
```python

**The Problem:** Each round gets a DIFFERENT match_id because timestamps are different!

#### 2. **Why This Was Intentional**

The **parser** (community_stats_parser.py) has sophisticated logic to **find Round 1 for a given Round 2**:

```python
def find_corresponding_round_1_file(self, round_2_file_path: str):
    """
    Find the Round 1 file that corresponds to this Round 2 file
    
    Algorithm:
    1. Extract date and map from Round 2 filename
    2. Find all Round 1 files with same date and map
    3. Find the one CLOSEST IN TIME but BEFORE Round 2
    4. Must be within 30 minutes
    """
    
    r2_filename = os.path.basename(round_2_file_path)
    r2_parts = r2_filename.split('-')
    
    # Extract Round 2 timestamp
    r2_date = '-'.join(r2_parts[:3])  # "2025-11-06"
    r2_time = r2_parts[3]              # "215312"
    r2_datetime = datetime.strptime(f"{r2_date} {r2_time}", '%Y-%m-%d %H%M%S')
    
    # Find Round 1 files for same date and map
    map_name = '-'.join(r2_parts[4:-2])  # "supply"
    potential_files = glob.glob(f"local_stats/{r2_date}-*-{map_name}-round-1.txt")
    
    best_r1_file = None
    best_r1_datetime = None
    
    for r1_file in potential_files:
        r1_parts = os.path.basename(r1_file).split('-')
        r1_time = r1_parts[3]
        r1_datetime = datetime.strptime(f"{r2_date} {r1_time}", '%Y-%m-%d %H%M%S')
        
        # Round 1 must be BEFORE Round 2
        if r1_datetime < r2_datetime:
            time_diff = (r2_datetime - r1_datetime).total_seconds() / 60
            
            # Accept if within 30 minutes
            if time_diff <= 30:
                # Keep the CLOSEST one
                if best_r1_datetime is None or r1_datetime > best_r1_datetime:
                    best_r1_datetime = r1_datetime
                    best_r1_file = r1_file
                    print(f"✅ Match found: {r1_filename} ({time_diff:.1f} min before)")
    
    return best_r1_file
```text

**How It Works:**

- Uses **filename timestamps** to find the Round 1 file that is **closest in time** but **before** Round 2
- Allows up to 30 minutes gap (typical rounds are 10-20 minutes)
- Returns the **most recent** Round 1 for the same map on the same day

#### 3. **Why Round 2 Needs Round 1**

**Critical Detail:** Round 2 stats files contain **CUMULATIVE** stats!

```text

Player Stats in Round 1 file:
  Kills: 15
  Deaths: 8
  Damage: 4500

Player Stats in Round 2 file (CUMULATIVE):
  Kills: 32     ← This is R1 kills (15) + R2 kills (17)
  Deaths: 21    ← This is R1 deaths (8) + R2 deaths (13)
  Damage: 9800  ← This is R1 damage (4500) + R2 damage (5300)

```text

**To get Round 2 ONLY stats:**

```python
r2_only_kills = r2_cumulative_kills - r1_kills
r2_only_kills = 32 - 15 = 17  ✅
```sql

**This is why the parser needs to find Round 1!**

---

## 🏗️ The 3-Round System (New Feature)

### Round Number Meanings

| round_number | Meaning | Data Source |
|--------------|---------|-------------|
| **1** | Round 1 only | Parsed from R1 file |
| **2** | Round 2 only (differential) | R2 file MINUS R1 file |
| **0** | Match summary (R1 + R2 cumulative) | Copied from R2 file before differential |

### Why Round 0 Exists

**Before:**

```sql
-- To get match totals, had to aggregate:
SELECT player_guid, 
       SUM(kills), SUM(deaths), SUM(damage_given)
FROM player_comprehensive_stats
WHERE match_id LIKE '2025-11-06-%-supply-%'
  AND round_number IN (1, 2)
GROUP BY player_guid
```text

**After:**

```sql
-- Now just query round 0:
SELECT player_guid, kills, deaths, damage_given
FROM player_comprehensive_stats
WHERE match_id = '2025-11-06-213045-supply-round-1'
  AND round_number = 0
```yaml

**Performance:** 50-70% faster queries for `!last_session` command

---

## 🚨 What We Accidentally Broke

### The Centralized Match Tracker Mistake

**What We Did:**

```python
# Created bot/core/match_tracker.py with:
def generate_match_id(filename):
    # Strip timestamp to make R1 and R2 have same match_id
    return f"{date}-{map_name}"  # "2025-11-06-supply"
```text

**The Problem:**

1. ✅ **Good intent:** Make R1 and R2 share the same match_id
2. ❌ **Bad side effect:** Parser's `find_round_1_file()` uses **timestamp proximity** to find the correct R1 file
3. ❌ **Result:** When match_id no longer includes timestamp, parser can't find correct R1 file
4. ❌ **Symptom:** Headshot mismatches (bronze expected 4, got 6 - wrong R1 file used for differential!)

### Why It Failed

```yaml

Scenario: Two games of supply on same day

Game 1:
  2025-11-06-140000-supply-round-1.txt  (2:00 PM)
  2025-11-06-142000-supply-round-2.txt  (2:20 PM)

Game 2:
  2025-11-06-210000-supply-round-1.txt  (9:00 PM)
  2025-11-06-212500-supply-round-2.txt  (9:25 PM)

With centralized match_tracker:
  All 4 files get match_id = "2025-11-06-supply"
  
When parsing 2025-11-06-212500-supply-round-2.txt:
  Parser looks for R1 with same date/map
  Finds BOTH R1 files!
  Without timestamps, it picks the WRONG one
  Calculates differential against 2:00 PM game instead of 9:00 PM game
  Result: Garbage stats, negative kills, headshot scrambling

```yaml

---

## ✅ How To Fix Match Linking (Future Work)

### Option 1: Use gaming_session_id

```python
# gaming_session_id groups rounds by 60-minute gaps
# If R1 and R2 happen within 60 minutes, they get same gaming_session_id

match_identifier = f"{gaming_session_id}-{map_name}"
# This naturally links R1 and R2 without breaking parser!
```text

### Option 2: Store Round 1 filename reference in Round 2

```python
# When parsing Round 2, store which R1 file was used:
rounds table:
  - match_id (unique per round)
  - parent_round_id (for R2, references R1's round_id)
  - round_1_filename (for R2, stores R1 filename)
```text

### Option 3: Keep timestamp, add match_group_id

```python
# Don't change match_id (keep timestamp)
# Add NEW column: match_group_id
rounds table:
  - match_id: "2025-11-06-213045-supply-round-1" (unique)
  - match_group_id: "2025-11-06-supply-session-5" (links R1 and R2)
  - gaming_session_id: 5
```yaml

---

## 📊 Database Schema (Key Tables)

### rounds

```sql
CREATE TABLE rounds (
    id SERIAL PRIMARY KEY,
    match_id TEXT,                    -- Full filename without .txt
    round_number INTEGER,              -- 0=summary, 1=R1, 2=R2
    round_date TEXT,                   -- YYYY-MM-DD
    round_time TEXT,                   -- HHMMSS
    map_name TEXT,
    gaming_session_id INTEGER,         -- Groups rounds by 60-min gaps
    winner_team INTEGER,
    round_outcome TEXT,
    UNIQUE(match_id, round_number)
)
```text

### player_comprehensive_stats (51 columns!)

```sql
CREATE TABLE player_comprehensive_stats (
    id SERIAL PRIMARY KEY,
    round_id INTEGER REFERENCES rounds(id),
    player_guid TEXT,
    player_name TEXT,
    kills INTEGER,
    deaths INTEGER,
    headshots INTEGER,              -- Sum of weapon headshots
    headshot_kills INTEGER,         -- Actual headshot kills (TAB field 14)
    damage_given INTEGER,
    damage_received INTEGER,
    accuracy REAL,
    kd_ratio REAL,
    efficiency REAL,
    dpm REAL,                       -- Damage per minute
    time_played_seconds INTEGER,
    -- ... 35 more fields ...
    UNIQUE(round_id, player_guid)
)
```text

### weapon_comprehensive_stats

```sql
CREATE TABLE weapon_comprehensive_stats (
    id SERIAL PRIMARY KEY,
    round_id INTEGER REFERENCES rounds(id),
    player_guid TEXT,
    weapon_name TEXT,
    kills INTEGER,
    deaths INTEGER,
    headshots INTEGER,
    shots INTEGER,
    hits INTEGER,
    accuracy REAL,
    UNIQUE(round_id, player_guid, weapon_name)
)
```text

### processed_files (Duplicate Detection)

```sql
CREATE TABLE processed_files (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE,
    file_hash TEXT,                 -- SHA256 hash
    success BOOLEAN,
    error_message TEXT,
    processed_at TIMESTAMP
)
```yaml

---

## 🔄 Complete File Processing Pipeline

### 1. File Appears on Game Server

```yaml

ET:Legacy server writes:
  /path/to/gamestats/2025-11-06-213045-supply-round-1.txt

```text

### 2. SSH Monitor Detects File

```python
# ssh_monitor.py runs every N minutes
async def check_and_process_new_files(self):
    # List remote directory
    remote_files = await self._list_remote_files()
    
    # Compare with processed_files table
    new_files = [f for f in remote_files if f not in self.processed_files]
    
    # Download new files
    for filename in new_files:
        await self._process_new_file(filename)
```text

### 3. Download File

```python
# Downloads to bot/local_stats/
local_path = await self._download_file(filename)
# Result: bot/local_stats/2025-11-06-213045-supply-round-1.txt
```text

### 4. Parse File

```python
# community_stats_parser.py
parsed_data = parser.parse_stats_file(local_path)

# For Round 1:
{
    'map_name': 'supply',
    'round_num': 1,
    'players': [
        {
            'guid': 'ABC123',
            'name': 'Player1',
            'kills': 15,
            'deaths': 8,
            'headshots': 3,
            'weapon_stats': {
                'thompson': {'kills': 10, 'shots': 250, 'hits': 89},
                'mp40': {'kills': 5, 'shots': 120, 'hits': 45}
            }
        },
        # ... more players
    ]
}
```python

### 5. Import to Database

```python
# postgresql_database_manager.py
async def process_file(file_path):
    # Check if already processed (SHA256 hash)
    if await self.is_file_processed(filename):
        return "Already processed"
    
    # Parse file
    parsed_data = parser.parse_stats_file(file_path)
    
    # Create round
    round_id = await self._create_round_postgresql(conn, parsed_data, filename)
    
    # Insert player stats (51 fields)
    await self._insert_player_stats(conn, round_id, parsed_data)
    
    # Insert weapon stats
    await self._insert_weapon_stats(conn, round_id, parsed_data)
    
    # If Round 2, also insert match summary (round_number=0)
    if parsed_data.get('match_summary'):
        summary_round_id = await self._create_round_postgresql(
            conn, match_summary, filename, is_match_summary=True
        )
        await self._insert_player_stats(conn, summary_round_id, match_summary)
    
    # Mark as processed
    await self.mark_file_processed(filename, success=True)
```text

### 6. Post to Discord

```python
# ssh_monitor.py
await self._post_round_stats(filename)

# If Round 2, also post match summary
if '-round-2.txt' in filename:
    await self._post_match_summary(filename)
```

---

## 🎯 Key Insights for AI Agents

1. **Timestamps are sacred** - They're used for Round 1/Round 2 pairing, don't strip them!

2. **Round 2 is cumulative** - Always needs Round 1 for differential calculation

3. **Parser finds Round 1 by proximity** - Uses timestamp to find the closest Round 1 before Round 2

4. **gaming_session_id is already smart** - 60-minute gap detection naturally groups related rounds

5. **Verification system is crucial** - Reads back inserted data to catch differential calculation errors

6. **Multiple games of same map per day** - Must handle multiple supply games on 2025-11-06

7. **round_number=0 is optimization** - Pre-computed match summaries for fast queries

---

## 🔧 Current State (November 7, 2025)

### What Works ✅

- Round numbering (R0, R1, R2) stored correctly
- Parser differential calculation
- SSH monitoring and file download
- Database imports
- Match summaries created
- Gaming session grouping

### What's Broken ❌

- match_tracker.py exists but shouldn't (causes differential calculation errors)
- Verification warnings indicate headshot mismatches
- R1 and R2 have different match_ids (can't easily link them in queries)

### What's Next 🚀

1. Delete match_tracker.py (cleanup)
2. Rebuild database with clean code
3. Investigate better match linking (gaming_session_id + map?)
4. Test optimized !last_session commands
5. Install matplotlib on VPS for graphs
