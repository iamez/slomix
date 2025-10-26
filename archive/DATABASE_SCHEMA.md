# 🗄️ ET:Legacy Database Schema - Complete Reference

**Version:** 3.0  
**Last Updated:** October 3, 2025  
**Database Type:** SQLite 3  
**Schema Status:** Stable ✅

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Schema Diagram](#schema-diagram)
3. [Tables](#tables)
4. [Indexes](#indexes)
5. [Views](#views)
6. [Migrations](#migrations)
7. [Maintenance](#maintenance)

---

## 🎯 Overview

The ET:Legacy statistics system uses SQLite for efficient, file-based storage of game statistics. The database contains 4 main tables tracking sessions, players, weapons, and Discord account links.

### Database File
- **Path:** `bot/etlegacy_production.db`
- **Size:** ~10 MB per 10,000 player records
- **Format:** SQLite 3 (compatible with Python 3.7+)

### Design Principles
- ✅ **Normalized** - Minimal data redundancy
- ✅ **Indexed** - Fast queries on common lookups
- ✅ **Flexible** - Easy to extend with new fields
- ✅ **Portable** - Single file, easy to backup/restore

---

## 📊 Schema Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        SESSIONS                              │
│  • id (PK)                                                   │
│  • session_date                                              │
│  • map_name                                                  │
│  • round_number                                              │
│  • time_limit                                                │
│  • actual_time                                               │
└────────────────────┬────────────────────────────────────────┘
                     │ 1
                     │
                     │ N
┌────────────────────┴────────────────────────────────────────┐
│              PLAYER_COMPREHENSIVE_STATS                      │
│  • id (PK)                                                   │
│  • session_id (FK) ──────────────────────┐                  │
│  • session_date                           │                  │
│  • player_guid                            │                  │
│  • player_name                            │                  │
│  • team                                   │                  │
│  • kills, deaths, damage...               │                  │
│  • time_played_seconds ⭐                 │                  │
│  • time_display                           │                  │
│  • dpm, kd_ratio                          │                  │
│  • objective_stats (37+ fields)           │                  │
└───────────────────────────────────────────┼──────────────────┘
                                            │
                                            │ 1
                                            │
                                            │ N
                     ┌──────────────────────┴──────────────────┐
                     │     WEAPON_COMPREHENSIVE_STATS          │
                     │  • id (PK)                              │
                     │  • session_id (FK)                      │
                     │  • player_guid                          │
                     │  • weapon_name                          │
                     │  • kills, deaths                        │
                     │  • hits, shots                          │
                     │  • headshots                            │
                     │  • accuracy                             │
                     └─────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      PLAYER_LINKS                            │
│  • discord_id (PK)                                           │
│  • player_guid                                               │
│  • player_name                                               │
│  • linked_at                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📚 Tables

### 1. `sessions`

**Purpose:** Track individual game sessions (rounds)

**Schema:**
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date DATE NOT NULL,           -- Format: YYYY-MM-DD
    map_name TEXT NOT NULL,               -- e.g., "etl_adlernest", "supply"
    round_number INTEGER NOT NULL,        -- 1 or 2
    server_name TEXT,                     -- Server hostname
    config_name TEXT,                     -- Server config (e.g., "3on3")
    defender_team INTEGER,                -- 1=Axis, 2=Allies
    winner_team INTEGER,                  -- 1=Axis, 2=Allies, 0=Draw
    time_limit TEXT,                      -- MM:SS format (e.g., "10:00")
    actual_time TEXT,                     -- MM:SS format (e.g., "11:26")
    actual_time_seconds INTEGER,          -- Actual time in seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX idx_sessions_date ON sessions(session_date);
CREATE INDEX idx_sessions_map ON sessions(map_name);
CREATE INDEX idx_sessions_date_map_round ON sessions(session_date, map_name, round_number);
```

**Sample Data:**
```
id  | session_date | map_name       | round_number | actual_time | actual_time_seconds
----|--------------|----------------|--------------|-------------|--------------------
1   | 2025-10-02   | etl_adlernest  | 1            | 11:26       | 686
2   | 2025-10-02   | etl_adlernest  | 2            | 10:15       | 615
3   | 2025-10-02   | supply         | 1            | 15:32       | 932
```

**Notes:**
- `session_date` is extracted from filename (not from header - header shows 1970-01-01 bug)
- `round_number` indicates which round (1 or 2)
- `actual_time` stores MM:SS format for display
- `actual_time_seconds` is the source of truth for calculations

---

### 2. `player_comprehensive_stats`

**Purpose:** Store all player statistics for each session

**Schema:**
```sql
CREATE TABLE player_comprehensive_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Session Info
    session_id INTEGER NOT NULL,
    session_date TEXT NOT NULL,           -- Denormalized for faster queries
    map_name TEXT NOT NULL,               -- Denormalized for faster queries
    round_number INTEGER NOT NULL,        -- Denormalized for faster queries
    
    -- Player Identity
    player_guid TEXT NOT NULL,            -- 8-character hex ID (e.g., "12345678")
    player_name TEXT NOT NULL,            -- Player nickname
    clean_name TEXT NOT NULL,             -- Name without color codes
    team INTEGER NOT NULL,                -- 1=Axis, 2=Allies
    
    -- Core Combat Stats
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    damage_given INTEGER DEFAULT 0,
    damage_received INTEGER DEFAULT 0,
    team_damage_given INTEGER DEFAULT 0,
    team_damage_received INTEGER DEFAULT 0,
    
    -- Combat Details
    gibs INTEGER DEFAULT 0,               -- Gib kills (overkill)
    self_kills INTEGER DEFAULT 0,         -- Suicide deaths
    team_kills INTEGER DEFAULT 0,         -- Team kills
    team_gibs INTEGER DEFAULT 0,          -- Team gibs
    
    -- Time Tracking ⭐ PRIMARY TIME STORAGE
    time_played_seconds INTEGER DEFAULT 0,  -- ⭐ INTEGER SECONDS (source of truth)
    time_played_minutes REAL DEFAULT 0,     -- DEPRECATED (backward compat only)
    time_display TEXT DEFAULT '0:00',       -- Display format "MM:SS"
    
    -- Performance Metrics
    xp INTEGER DEFAULT 0,                 -- Experience points
    dpm REAL DEFAULT 0,                   -- Damage per minute (pre-calculated)
    kd_ratio REAL DEFAULT 0,              -- Kill/death ratio
    
    -- Spree Stats
    killing_spree_best INTEGER DEFAULT 0,  -- Best killing spree
    death_spree_worst INTEGER DEFAULT 0,   -- Worst death spree
    
    -- Objective Stats (from c0rnp0rn3)
    kill_assists INTEGER DEFAULT 0,        -- Field 13: Assisted kills
    kill_steals INTEGER DEFAULT 0,         -- Field 14: Stolen kills
    headshot_kills INTEGER DEFAULT 0,      -- Field 5: Kills by headshot
    objectives_stolen INTEGER DEFAULT 0,   -- Field 6: Objectives stolen
    objectives_returned INTEGER DEFAULT 0, -- Field 7: Objectives returned
    dynamites_planted INTEGER DEFAULT 0,   -- Field 8: Dynamites planted
    dynamites_defused INTEGER DEFAULT 0,   -- Field 9: Dynamites defused
    times_revived INTEGER DEFAULT 0,       -- Field 10: Times player was revived
    revives_given INTEGER DEFAULT 0,       -- Field 20: Revives given by player
    bullets_fired INTEGER DEFAULT 0,       -- Field 11: Total bullets fired
    tank_meatshield REAL DEFAULT 0,        -- Field 13: Tank/meatshield score
    time_dead_ratio REAL DEFAULT 0,        -- Field 14: Time dead ratio
    most_useful_kills INTEGER DEFAULT 0,   -- Field 15: Most useful kills
    denied_playtime INTEGER DEFAULT 0,     -- Field 16: Denied playtime (seconds)
    useless_kills INTEGER DEFAULT 0,       -- Field 17: Useless kills
    full_selfkills INTEGER DEFAULT 0,      -- Field 18: Full selfkills
    repairs_constructions INTEGER DEFAULT 0, -- Field 19: Repairs/constructions
    
    -- Multikill Stats
    double_kills INTEGER DEFAULT 0,        -- Field 30: 2x multikills
    triple_kills INTEGER DEFAULT 0,        -- Field 31: 3x multikills
    quad_kills INTEGER DEFAULT 0,          -- Field 32: 4x multikills
    multi_kills INTEGER DEFAULT 0,         -- Field 33: 5x multikills
    mega_kills INTEGER DEFAULT 0,          -- Field 34: 6x multikills
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

**Indexes:**
```sql
CREATE INDEX idx_player_stats_session ON player_comprehensive_stats(session_id);
CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid);
CREATE INDEX idx_player_stats_name ON player_comprehensive_stats(player_name);
CREATE INDEX idx_player_stats_date ON player_comprehensive_stats(session_date);
CREATE INDEX idx_player_stats_guid_date ON player_comprehensive_stats(player_guid, session_date);
```

**Field Mapping (c0rnp0rn3 fields):**

| Field # | Lua Name | Database Column | Description |
|---------|----------|-----------------|-------------|
| 0 | damage_given | damage_given | Total damage dealt |
| 1 | damage_received | damage_received | Total damage received |
| 2 | team_damage_given | team_damage_given | Friendly fire damage |
| 3 | team_damage_received | team_damage_received | FF damage received |
| 4 | gibs | gibs | Gib kills |
| 5 | self_kills | self_kills | Suicide deaths |
| 6 | team_kills | team_kills | Team kills |
| 7 | team_gibs | team_gibs | Team gibs |
| 8 | time_played | time_played_seconds | ⭐ Time in seconds |
| 9 | xp | xp | Experience points |
| 10 | killing_spree | killing_spree_best | Best killing spree |
| 11 | death_spree | death_spree_worst | Worst death spree |
| 12 | DPM | dpm | Damage per minute |
| 13 | kill_assists | kill_assists | Assisted kills |
| 14 | kill_steals | kill_steals | Stolen kills |
| 15 | headshot_kills | headshot_kills | Kills by headshot |
| 16 | objectives_stolen | objectives_stolen | Objectives stolen |
| 17 | objectives_returned | objectives_returned | Objectives returned |
| 18 | dynamites_planted | dynamites_planted | Dynamites planted |
| 19 | dynamites_defused | dynamites_defused | Dynamites defused |
| 20 | times_revived | times_revived | Times revived |
| 21 | bullets_fired | bullets_fired | Total shots fired |
| 22 | (calculated) | dpm | DPM (recalculated) |
| 23 | time_minutes | time_played_minutes | Time in minutes (deprecated) |
| 24 | tank_meatshield | tank_meatshield | Tank/meatshield score |
| 25 | time_dead_ratio | time_dead_ratio | Time dead ratio |
| 26 | (unused) | - | - |
| 27 | kd_ratio | kd_ratio | Kill/death ratio |
| 28 | most_useful_kills | most_useful_kills | Most useful kills |
| 29 | denied_playtime | denied_playtime | Denied playtime (seconds) |
| 30 | double_kills | double_kills | 2x multikills |
| 31 | triple_kills | triple_kills | 3x multikills |
| 32 | quad_kills | quad_kills | 4x multikills |
| 33 | multi_kills | multi_kills | 5x multikills |
| 34 | mega_kills | mega_kills | 6x multikills |
| 35 | useless_kills | useless_kills | Useless kills |
| 36 | full_selfkills | full_selfkills | Full selfkills |
| 37 | repairs_constructions | repairs_constructions | Repairs/constructions |
| 38 | revives_given | revives_given | Revives given |

**Sample Data:**
```
id  | player_guid | player_name | kills | deaths | time_played_seconds | dpm    | kd_ratio
----|-------------|-------------|-------|--------|---------------------|--------|----------
1   | 12345678    | vid         | 45    | 32     | 686                 | 344.94 | 1.41
2   | 87654321    | SuperBoyy   | 42    | 30     | 615                 | 340.51 | 1.40
3   | ABCDEF12    | ciril       | 38    | 35     | 932                 | 245.23 | 1.09
```

---

### 3. `weapon_comprehensive_stats`

**Purpose:** Track weapon-specific statistics for each player in each session

**Schema:**
```sql
CREATE TABLE weapon_comprehensive_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Session & Player Info
    session_id INTEGER NOT NULL,
    session_date TEXT NOT NULL,           -- Denormalized
    player_guid TEXT NOT NULL,
    
    -- Weapon Identity
    weapon_id INTEGER,                    -- 0-27 (from WeaponStats_t)
    weapon_name TEXT NOT NULL,            -- e.g., "WS_MP40", "WS_THOMPSON"
    
    -- Weapon Stats
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,               -- Shots that hit target
    shots INTEGER DEFAULT 0,              -- Total shots fired
    headshots INTEGER DEFAULT 0,          -- Headshot hits
    accuracy REAL DEFAULT 0,              -- (hits / shots) * 100
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

**Indexes:**
```sql
CREATE INDEX idx_weapon_stats_session ON weapon_comprehensive_stats(session_id);
CREATE INDEX idx_weapon_stats_guid ON weapon_comprehensive_stats(player_guid);
CREATE INDEX idx_weapon_stats_weapon ON weapon_comprehensive_stats(weapon_name);
CREATE INDEX idx_weapon_stats_guid_weapon ON weapon_comprehensive_stats(player_guid, weapon_name);
```

**Weapon IDs (from c0rnp0rn3):**
```
0  = WS_KNIFE          14 = WS_DYNAMITE
1  = WS_KNIFE_KBAR     15 = WS_AIRSTRIKE
2  = WS_LUGER          16 = WS_ARTILLERY
3  = WS_COLT           17 = WS_SATCHEL
4  = WS_MP40           18 = WS_GRENADELAUNCHER
5  = WS_THOMPSON       19 = WS_LANDMINE
6  = WS_STEN           20 = WS_MG42
7  = WS_FG42           21 = WS_BROWNING
8  = WS_PANZERFAUST    22 = WS_CARBINE
9  = WS_BAZOOKA        23 = WS_KAR98
10 = WS_FLAMETHROWER   24 = WS_GARAND
11 = WS_GRENADE        25 = WS_K43
12 = WS_MORTAR         26 = WS_MP34
13 = WS_MORTAR2        27 = WS_SYRINGE
```

**Sample Data:**
```
id  | player_guid | weapon_name  | kills | hits | shots | headshots | accuracy
----|-------------|--------------|-------|------|-------|-----------|----------
1   | 12345678    | WS_MP40      | 25    | 312  | 845   | 45        | 36.92
2   | 12345678    | WS_PANZERFAUST| 8    | 12   | 18    | 0         | 66.67
3   | 87654321    | WS_THOMPSON  | 28    | 298  | 756   | 38        | 39.42
```

---

### 4. `player_links`

**Purpose:** Link Discord accounts to game GUIDs for easier stat lookups

**Schema:**
```sql
CREATE TABLE player_links (
    discord_id TEXT PRIMARY KEY,          -- Discord user ID
    player_guid TEXT NOT NULL,            -- 8-character game GUID
    player_name TEXT NOT NULL,            -- Most recent player name
    linked_by TEXT,                       -- Discord ID who created link
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX idx_player_links_guid ON player_links(player_guid);
```

**Sample Data:**
```
discord_id       | player_guid | player_name | linked_at
-----------------|-------------|-------------|---------------------
123456789012345  | 12345678    | vid         | 2025-10-02 21:30:00
987654321098765  | 87654321    | SuperBoyy   | 2025-10-02 21:35:00
```

**Usage:**
```sql
-- Query player stats by Discord ID
SELECT p.* 
FROM player_comprehensive_stats p
JOIN player_links l ON p.player_guid = l.player_guid
WHERE l.discord_id = '123456789012345';
```

---

## 📈 Views

### `v_player_totals`

**Purpose:** Aggregate player statistics across all sessions

```sql
CREATE VIEW v_player_totals AS
SELECT 
    player_guid,
    player_name,
    COUNT(DISTINCT session_id) as sessions_played,
    SUM(kills) as total_kills,
    SUM(deaths) as total_deaths,
    SUM(damage_given) as total_damage,
    SUM(time_played_seconds) as total_seconds,
    CAST(SUM(damage_given) * 60.0 / NULLIF(SUM(time_played_seconds), 0) AS REAL) as overall_dpm,
    CAST(SUM(kills) AS REAL) / NULLIF(SUM(deaths), 0) as overall_kd
FROM player_comprehensive_stats
GROUP BY player_guid, player_name;
```

### `v_session_summary`

**Purpose:** Summarize each session with player counts and stats

```sql
CREATE VIEW v_session_summary AS
SELECT 
    s.id as session_id,
    s.session_date,
    s.map_name,
    s.round_number,
    s.actual_time,
    COUNT(DISTINCT p.player_guid) as player_count,
    SUM(p.kills) as total_kills,
    SUM(p.deaths) as total_deaths,
    SUM(p.damage_given) as total_damage,
    AVG(p.dpm) as avg_dpm
FROM sessions s
LEFT JOIN player_comprehensive_stats p ON s.id = p.session_id
GROUP BY s.id, s.session_date, s.map_name, s.round_number, s.actual_time;
```

---

## 🔧 Migrations

### Version 2.0 → 3.0 (Seconds-Based Time)

**Migration Script:** `tools/migrate_to_seconds.py`

```sql
-- Add new seconds-based columns
ALTER TABLE player_comprehensive_stats
ADD COLUMN time_played_seconds INTEGER DEFAULT 0;

ALTER TABLE player_comprehensive_stats
ADD COLUMN time_display TEXT DEFAULT '0:00';

-- Convert existing time_played_minutes to seconds
UPDATE player_comprehensive_stats
SET time_played_seconds = CAST(time_played_minutes * 60 AS INTEGER),
    time_display = 
        CAST(time_played_minutes AS INTEGER) || ':' || 
        SUBSTR('0' || CAST((time_played_minutes - CAST(time_played_minutes AS INTEGER)) * 60 AS INTEGER), -2)
WHERE time_played_minutes > 0;

-- Recalculate DPM using seconds
UPDATE player_comprehensive_stats
SET dpm = CAST(damage_given * 60.0 / NULLIF(time_played_seconds, 0) AS REAL)
WHERE time_played_seconds > 0;
```

---

## 🛠️ Maintenance

### Database Vacuum

**Purpose:** Reclaim unused space and optimize database

```sql
-- Vacuum database (rebuild file)
VACUUM;

-- Analyze tables (update statistics)
ANALYZE;
```

**Schedule:** Run monthly or after large deletions

### Backup Procedures

**Full Backup:**
```powershell
# Copy database file
Copy-Item etlegacy_production.db etlegacy_backup_$(Get-Date -Format 'yyyyMMdd').db

# Or use SQLite dump
sqlite3 etlegacy_production.db ".backup etlegacy_backup.db"
```

**Automated Backup Script:**
```powershell
# backup_database.ps1
$date = Get-Date -Format "yyyyMMdd_HHmmss"
$source = "bot/etlegacy_production.db"
$destination = "backups/etlegacy_backup_$date.db"

Copy-Item $source $destination
Write-Host "✅ Backup created: $destination"

# Keep only last 30 backups
Get-ChildItem backups/*.db | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -Skip 30 | 
    Remove-Item
```

### Integrity Check

```sql
-- Check database integrity
PRAGMA integrity_check;

-- Check foreign key constraints
PRAGMA foreign_key_check;
```

### Performance Monitoring

```sql
-- Show table sizes
SELECT 
    name as table_name,
    SUM("pgsize") as size_bytes,
    SUM("pgsize") / 1024.0 as size_kb,
    SUM("pgsize") / 1024.0 / 1024.0 as size_mb
FROM "dbstat"
GROUP BY name
ORDER BY size_bytes DESC;

-- Show index usage
SELECT * FROM sqlite_stat1;
```

---

## 📊 Database Statistics

**Current Production Database:**
- **Total Records:** 24,774 player stats
- **Sessions:** 1,459 sessions
- **Time Coverage:** June 2024 - October 2025
- **File Size:** ~12 MB
- **Players Tracked:** ~150 unique GUIDs
- **Maps Covered:** 15+ unique maps

---

**Schema Version:** 3.0  
**Last Updated:** October 3, 2025  
**Status:** Production ✅
