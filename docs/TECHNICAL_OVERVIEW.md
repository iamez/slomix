# 🎮 ET:Legacy Stats Bot - Technical Documentation

**Last Updated:** November 6, 2025  
**Version:** 2.0  
**Status:** Production-Ready

---

## 📋 Table of Contents

1. [Data Pipeline](#data-pipeline)
2. [System Architecture](#system-architecture)
3. [Database Schema](#database-schema)
4. [How Data Flows](#how-data-flows)
5. [Field Mapping](#field-mapping)

---

## 🔄 Data Pipeline

### Overview: From Game Server → Discord

```python
┌─────────────────┐
│  ET Game Server │ Generates .stats files every round
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ local_stats/    │ Stats files stored locally
│ YYYY-MM-DD-     │ Format: 2025-11-06-213045-supply-round-1.txt
│ HHMMSS-map-     │
│ round-N.txt     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Stats Parser    │ community_stats_parser.py
│ C0RNP0RNStats   │ Extracts 50+ fields per player
│ Parser          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PostgreSQL DB   │ postgresql_database_manager.py
│ (or SQLite)     │ Transaction-safe import
│                 │ Duplicate detection (SHA256)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Discord Bot     │ bot/ultimate_bot.py (4,990 lines)
│ Commands        │ 60+ commands across 14 cogs
│                 │ Real-time analytics
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Discord Channel │ Graphs, stats, leaderboards
│ User sees stats │ !stats, !last_session, !top, etc.
└─────────────────┘
```python

### Key Pipeline Stages

#### Stage 1: Stats File Generation

- **Source:** ET:Legacy game server mod
- **Frequency:** After each round completes
- **Format:** Plain text with tab-separated values
- **Location:** Server writes to `/path/to/stats/` directory
- **Naming:** `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`

#### Stage 2: File Collection

- **Method 1:** Direct file access (local bot)
- **Method 2:** SSH/SCP download (remote bot)
- **Storage:** `bot/local_stats/` directory
- **Monitoring:** Optional automation service (`ssh_monitor.py`)

#### Stage 3: Parsing

- **Parser:** `community_stats_parser.py` - Custom C0RNP0RN3StatsParser class
- **Input:** Raw .stats file
- **Output:** Structured Python dict with 50+ fields per player
- **Key Functions:**
  - `parse_file()` - Main parsing entry point
  - `extract_player_stats()` - Per-player data extraction
  - `extract_weapon_stats()` - Weapon-specific stats
  - `calculate_differential()` - R2 cumulative stats calculation

#### Stage 4: Database Import

- **Manager:** `postgresql_database_manager.py`
- **Features:**
  - SHA256 hash duplicate detection
  - Transaction safety (atomic commits)
  - Rollback on errors
  - Gaming session auto-consolidation
  - Team assignment
- **Tables Updated:**
  - `rounds` - Round metadata
  - `player_stats` - Player performance
  - `weapon_stats` - Weapon usage
  - `processed_files` - Import tracking
  - `gaming_sessions` - Session groups

#### Stage 5: Discord Bot Access

- **Adapter:** `bot/core/database_adapter.py`
- **Supports:** SQLite AND PostgreSQL
- **Mode:** Async queries (aiosqlite/asyncpg)
- **Caching:** `bot/core/stats_cache.py` for performance

#### Stage 6: User Commands

- **Framework:** discord.py with cog architecture
- **Commands:** 50+ across 14 cogs
- **Output:** Embedded messages, graphs (matplotlib), leaderboards

---

## 🏗️ System Architecture

### Bot Structure (Current - Nov 2025)

```python
slomix/
├── bot/
│   ├── ultimate_bot.py              # Main bot (4,990 lines)
│   ├── config.py                    # Configuration management
│   ├── logging_config.py            # Logging setup
│   ├── image_generator.py           # Graph generation (matplotlib)
│   │
│   ├── cogs/                        # 14 Command Modules
│   │   ├── admin_cog.py             # Database operations (!rebuild, !import)
│   │   ├── stats_cog.py             # Player stats (!stats, !compare)
│   │   ├── leaderboard_cog.py       # Rankings (!top, !leaderboard)
│   │   ├── last_session_cog.py      # Analytics (!last_session) - 111KB
│   │   ├── session_cog.py           # Session viewing (!sessions, !session)
│   │   ├── session_management_cog.py # Session control (!start, !end)
│   │   ├── link_cog.py              # Player linking (!link, !mylink)
│   │   ├── sync_cog.py              # Data sync (!sync, !check)
│   │   ├── team_cog.py              # Team tracking (!team, !teams)
│   │   ├── team_management_cog.py   # Team management (!setteam, !clearteam)
│   │   ├── automation_commands.py   # Automation control
│   │   ├── server_control.py        # Optional RCON commands
│   │   ├── synergy_analytics.py     # Player synergy analysis
│   │   └── synergy_analytics_fixed.py
│   │
│   ├── core/                        # 9 Core Systems
│   │   ├── database_adapter.py      # SQLite/PostgreSQL abstraction
│   │   ├── team_manager.py          # Team detection & tracking
│   │   ├── advanced_team_detector.py # Advanced algorithms
│   │   ├── team_detector_integration.py
│   │   ├── substitution_detector.py # Player sub detection
│   │   ├── team_history.py          # Historical team data
│   │   ├── achievement_system.py    # Achievement tracking
│   │   ├── season_manager.py        # Season management
│   │   └── stats_cache.py           # Query optimization
│   │
│   └── services/automation/         # 4 Automation Services
│       ├── ssh_monitor.py           # Remote file monitoring
│       ├── database_maintenance.py  # DB cleanup tasks
│       ├── health_monitor.py        # System health checks
│       └── metrics_logger.py        # Performance metrics
│
├── tools/
│   ├── stopwatch_scoring.py         # Stopwatch mode calculator
│   └── postgresql_db_manager.py     # DB management utilities
│
├── postgresql_database_manager.py   # Main DB CLI tool
├── community_stats_parser.py        # Stats file parser
└── requirements.txt                 # Python dependencies
```python

### Technology Stack

- **Language:** Python 3.8+
- **Discord API:** discord.py 2.3.0+
- **Database:** PostgreSQL 12+ (primary), SQLite (fallback)
- **Async DB:** asyncpg (PostgreSQL), aiosqlite (SQLite)
- **Graphs:** matplotlib, Pillow
- **Config:** python-dotenv
- **SSH:** paramiko (optional)

---

## 💾 Database Schema

### Core Tables

#### `rounds`

Round-level metadata and scores.

```sql
id                  SERIAL PRIMARY KEY
session_id          VARCHAR(50)     -- YYYY-MM-DD-HHMMSS format
round_num           INTEGER         -- 1 or 2
map_name            VARCHAR(100)
timestamp           TIMESTAMP
duration_seconds    INTEGER
axis_score          INTEGER
allies_score        INTEGER
winning_team        VARCHAR(20)     -- 'axis', 'allies', 'tie'
map_id              VARCHAR(100)    -- Unique map identifier
gaming_session_id   INTEGER         -- Links to gaming_sessions
```text

#### `player_stats`

Player performance per round (50+ columns).

```sql
id                  SERIAL PRIMARY KEY
round_id            INTEGER         -- FK to rounds
player_name         VARCHAR(100)
team                VARCHAR(20)     -- 'axis' or 'allies'

-- Combat Stats
kills               INTEGER
deaths              INTEGER
team_kills          INTEGER
team_deaths         INTEGER
self_kills          INTEGER
headshots           INTEGER
revives             INTEGER

-- Accuracy
shots               INTEGER
hits                INTEGER
accuracy_percent    DECIMAL(5,2)    -- Calculated: hits/shots * 100

-- Damage
damage_given        INTEGER
damage_received     INTEGER
damage_team         INTEGER

-- Objectives
obj_captured        INTEGER
obj_destroyed       INTEGER
obj_returned        INTEGER
obj_taken           INTEGER

-- XP & Score
xp_total            INTEGER
xp_combat           INTEGER
xp_objective        INTEGER
xp_support          INTEGER
xp_misc             INTEGER

-- Time
time_played_seconds INTEGER
time_axis_seconds   INTEGER
time_allies_seconds INTEGER

-- Team Assignment
team_source         VARCHAR(50)     -- 'snapshot', 'tracker', 'vote', etc.
team_confidence     DECIMAL(3,2)    -- 0.0 to 1.0

-- Metadata
is_bot              BOOLEAN
is_differential     BOOLEAN         -- True if R2 cumulative stats
created_at          TIMESTAMP
```text

#### `weapon_stats`

Weapon usage per player per round.

```sql
id                  SERIAL PRIMARY KEY
player_stat_id      INTEGER         -- FK to player_stats
weapon_name         VARCHAR(100)
kills               INTEGER
deaths              INTEGER
headshots           INTEGER
shots               INTEGER
hits                INTEGER
accuracy_percent    DECIMAL(5,2)
```text

#### `gaming_sessions`

Consolidated gaming sessions (groups of rounds).

```sql
id                  SERIAL PRIMARY KEY
session_start       TIMESTAMP
session_end         TIMESTAMP
total_rounds        INTEGER
unique_maps         INTEGER
total_players       INTEGER
duration_seconds    INTEGER
created_at          TIMESTAMP
```text

**Session Logic:** Rounds within 12 hours = same session

#### `processed_files`

Track imported files to prevent duplicates.

```sql
id                  SERIAL PRIMARY KEY
file_path           VARCHAR(500)    -- Full file path
file_hash           VARCHAR(64)     -- SHA256 hash
processed_at        TIMESTAMP
round_id            INTEGER         -- FK to rounds
```text

#### `player_links`

Link ET players to Discord users.

```sql
id                  SERIAL PRIMARY KEY
discord_id          BIGINT          -- Discord user ID
player_name         VARCHAR(100)    -- ET player name
guid                VARCHAR(32)     -- ET player GUID
created_at          TIMESTAMP
```sql

---

## 📊 Field Mapping: What Data We Capture

### Per-Player Fields (50+ fields)

#### Identity

- `player_name` - In-game name
- `guid` - ET player GUID (if available)
- `team` - 'axis' or 'allies'
- `is_bot` - Boolean flag

#### Combat

- `kills` - Enemy kills
- `deaths` - Times killed
- `team_kills` - Friendly fire kills
- `team_deaths` - Deaths by friendly fire
- `self_kills` - Suicide count
- `headshots` - Headshot kills

#### Support

- `revives` - Players revived
- `ammogiven` - Ammo packs given
- `healthgiven` - Health packs given
- `poisoned` - Times poisoned (?)

#### Accuracy

- `shots` - Total shots fired
- `hits` - Total hits landed
- `accuracy_percent` - Calculated (hits/shots * 100)

#### Damage

- `damage_given` - Damage dealt to enemies
- `damage_received` - Damage taken
- `damage_team` - Friendly fire damage dealt

#### Objectives

- `obj_captured` - Objectives captured
- `obj_destroyed` - Objectives destroyed
- `obj_returned` - Objectives returned
- `obj_taken` - Objectives taken

#### XP System

- `xp_total` - Total XP earned
- `xp_combat` - Combat XP
- `xp_objective` - Objective XP
- `xp_support` - Support XP (medic/ammo)
- `xp_misc` - Miscellaneous XP

#### Time Tracking

- `time_played_seconds` - Total play time
- `time_axis_seconds` - Time on Axis
- `time_allies_seconds` - Time on Allies

#### Per-Weapon Stats (nested)

For each weapon used:

- `weapon_name`
- `kills`
- `deaths`
- `headshots`
- `shots`
- `hits`
- `accuracy_percent`

### Round-Level Fields

- `map_name` - Map played
- `timestamp` - When round occurred
- `duration_seconds` - Round length
- `axis_score` - Axis team score
- `allies_score` - Allies team score
- `winning_team` - Winner ('axis'/'allies'/'tie')

---

## 🔁 How Data Flows: Complete Example

### Example: Player joins server, plays 2 rounds

#### Step 1: Game Generates Stats

Player "seareal" joins Axis team on supply map.

- Round 1 ends after 15 minutes
- Server generates: `2025-11-06-210000-supply-round-1.txt`
- File contains stats for all 12 players
- Round 2 starts immediately
- Round 2 ends after 18 minutes
- Server generates: `2025-11-06-213300-supply-round-2.txt`

#### Step 2: Files Collected

- Bot monitors `local_stats/` directory
- OR SSH monitor downloads from server every 30 seconds
- Files copied to `bot/local_stats/`

#### Step 3: Parsing

```python
from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
data = parser.parse_file('2025-11-06-210000-supply-round-1.txt')
# Returns:
{
    'round_info': {
        'map_name': 'supply',
        'timestamp': '2025-11-06 21:00:00',
        'axis_score': 0,
        'allies_score': 1,
        'winning_team': 'allies'
    },
    'players': [
        {
            'player_name': 'seareal',
            'team': 'axis',
            'kills': 15,
            'deaths': 8,
            'accuracy': 28.5,
            ...  # 50+ more fields
            'weapons': [...]
        },
        ... # 11 more players
    ]
}
```text

#### Step 4: Database Import

```python
from postgresql_database_manager import PostgreSQLDatabase

db = PostgreSQLDatabase()
db.import_stats_file('2025-11-06-210000-supply-round-1.txt')
# - Calculates SHA256 hash
# - Checks if already processed
# - Begins transaction
# - Inserts into rounds table
# - Inserts 12 rows into player_stats
# - Inserts ~100 rows into weapon_stats (per player)
# - Marks file as processed
# - Commits transaction
```text

#### Step 5: Bot Query

User types: `!stats seareal`

```python
# In stats_cog.py:
async def get_player_stats(player_name):
    query = """
        SELECT 
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            AVG(accuracy_percent) as avg_accuracy,
            COUNT(DISTINCT round_id) as rounds_played
        FROM player_stats
        WHERE player_name = $1
    """
    return await db.fetch_one(query, player_name)
```text

#### Step 6: Discord Response

Bot sends embedded message:

```text

📊 Stats for seareal
━━━━━━━━━━━━━━━━━━
🎯 K/D: 1.87 (15 kills, 8 deaths)
🎲 Accuracy: 28.5%
🕒 Rounds Played: 1
⏱️ Time Played: 15m

```sql

---

## 🎯 Key Design Decisions

### Why Separate Rounds Table?

- Enables querying by map, date, duration
- Track session metadata independently
- Calculate map-specific statistics

### Why R2 Differential Stats?

ET:Legacy rounds show **cumulative** stats in R2:

- R1: kills=10, deaths=5
- R2: kills=25, deaths=12 (includes R1!)
- **Solution:** Subtract R1 from R2 to get R2-only stats
- Implemented in `calculate_differential()`

### Why Team Detection System?

ET stats files don't always have reliable team info:

- Use multiple algorithms (snapshot, tracker, vote)
- Confidence scoring (0.0 to 1.0)
- Manual override capability
- Historical team tracking

### Why Gaming Sessions?

Group related rounds together:

- Gap threshold: 12 hours
- Enables session analytics (!last_session)
- Track player progression within sessions

---

## 📈 Performance Considerations

### Database Indexes

```sql
CREATE INDEX idx_player_name ON player_stats(player_name);
CREATE INDEX idx_round_id ON player_stats(round_id);
CREATE INDEX idx_timestamp ON rounds(timestamp);
CREATE INDEX idx_session_id ON rounds(gaming_session_id);
```python

### Query Optimization

- Use `stats_cache.py` for frequently accessed data
- Batch inserts during imports
- Async queries prevent blocking Discord bot

### File Processing

- SHA256 hashing prevents duplicate imports
- Transaction safety: rollback on errors
- Parallel processing for bulk imports (optional)

---

## 🔐 Security & Data Integrity

### Duplicate Prevention

- SHA256 hash of entire file
- Stored in `processed_files` table
- Import fails gracefully if duplicate detected

### Transaction Safety

All imports wrapped in database transactions:

```python
async with db.transaction():
    # Import round
    # Import players
    # Import weapons
    # Mark as processed
    # If ANY step fails, entire import rolls back
```

### Data Validation

- Player name sanitization
- Team value validation ('axis'/'allies' only)
- Numeric field bounds checking
- Timestamp format validation

---

## 📝 Additional Resources

- **[bot/services/automation/INTEGRATION_GUIDE.md](../bot/services/automation/INTEGRATION_GUIDE.md)** - Automation setup
- **[DATA_PIPELINE.md](DATA_PIPELINE.md)** - Data pipeline documentation
- **[FIELD_MAPPING.md](FIELD_MAPPING.md)** - Complete field reference
- **Main Bot Code:** `bot/ultimate_bot.py` (4,990 lines)
- **Parser Code:** `bot/community_stats_parser.py` (1,036 lines)
- **Database Manager:** `postgresql_database_manager.py` (1,573 lines)

---

**For detailed technical implementation, review the source code in the `bot/` directory.**
