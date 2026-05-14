# 🎓 ET:Legacy Stats Bot - Architecture Onboarding Guide

**Created:** December 2, 2025  
**Purpose:** Complete system understanding for developers  
**Reading Time:** ~45 minutes for full document

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [Data Flow Pipeline](#2-data-flow-pipeline)
3. [Architecture Style](#3-architecture-style)
4. [Component Breakdown (Detailed)](#4-component-breakdown-detailed)
5. [Execution Flows](#5-execution-flows)
6. [Design Decisions Explained](#6-design-decisions-explained)
7. [Key Patterns](#7-key-patterns)
8. [Anti-Patterns to Avoid](#8-anti-patterns-to-avoid)
9. [Database Schema](#9-database-schema)
10. [Complete File Reference](#10-complete-file-reference)

---

## 1. What This Project Is

### In Plain English

A **Discord bot that tracks game statistics** for Wolfenstein: Enemy Territory (ET:Legacy) - a team-based multiplayer shooter from 2003 that still has an active community.

**The problem it solves:**

Before this bot existed, game stats were completely lost after each match. Players had no persistent way to:

- Track their performance over time
- Compare themselves to others
- See who the best players are
- Analyze their last gaming session

**After this bot:**

- Players query `!stats myname` to see lifetime statistics
- Communities see `!leaderboard` rankings for who's the best
- `!last_session` shows beautiful graphs of the most recent gaming session
- Session grouping means you can compare "last night's 3-hour session" vs "last week's session"
- `!compare player1 player2` creates radar charts comparing two players

### What It Does (Step by Step)

1. **Fetches** stats files from remote game server via SSH connection
2. **Stores** them locally in `local_stats/` directory on the bot's machine
3. **Parses** raw text files into structured data (50+ fields per player)
4. **Imports** everything into PostgreSQL with transaction safety
5. **Presents** analytics via Discord commands (`!stats`, `!leaderboard`, `!last_session`)
6. **Auto-posts** round results to Discord when games finish
7. **Detects** gaming sessions by monitoring Discord voice channels

Think of it like a **sports statistics tracking system** - but for a video game, delivered through Discord.

---

## 2. Data Flow Pipeline

```python
┌─────────────────────────────────────────────────────────────────┐
│                     ET:LEGACY GAME SERVER (VPS)                 │
│                                                                 │
│  Game round ends → c0rnp0rn3.lua mod writes stats file          │
│  File: 2025-12-01-213045-supply-round-1.txt                     │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  │ SSH Connection
                                  │ (endstats_monitor task, every 60s)
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BOT SERVER (VPS or Local)                   │
│                                                                 │
│  ┌─────────────────┐                                            │
│  │  SSH Handler    │ Downloads new files from game server       │
│  │  ssh_handler.py │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │  local_stats/   │ Files stored locally for processing        │
│  │  (directory)    │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │  Stats Parser   │ Extracts 50+ fields per player             │
│  │  community_     │ Handles R2 differential calculation        │
│  │  stats_parser.py│                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │  PostgreSQL DB  │ Transaction-safe import                    │
│  │  via adapter    │ SHA256 duplicate detection                 │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │  Discord Bot    │ 20 Cogs, 80+ commands                      │
│  │  ultimate_bot.py│ Real-time analytics                        │
│  └────────┬────────┘                                            │
└───────────┼─────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DISCORD CHANNEL                             │
│                                                                 │
│  User sees: graphs, stats, leaderboards                         │
│  Commands: !stats, !last_session, !top, !compare                │
└─────────────────────────────────────────────────────────────────┘
```python

### Key Pipeline Stages

| Stage | File | What Happens |
|-------|------|--------------|
| 1. Generation | Game server | c0rnp0rn3.lua writes `YYYY-MM-DD-HHMMSS-map-round-N.txt` |
| 2. Collection | `ssh_handler.py` | SSH downloads new files to `local_stats/` |
| 3. Deduplication | `file_tracker.py` | Checks if file already processed |
| 4. Parsing | `community_stats_parser.py` | Extracts structured data from text |
| 5. Import | `postgresql_database_manager.py` | Inserts into PostgreSQL with transactions |
| 6. Discord | `round_publisher_service.py` | Posts embed to Discord channel |
| 7. Commands | `bot/cogs/*.py` | Users query with `!stats`, `!top`, etc. |

---

## 3. Architecture Style

### Layered Modular Architecture

```python
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                           │
│  Discord commands, embeds, graphs                               │
│  Files: bot/cogs/*.py (14 modules)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                                │
│  Business logic, session detection, predictions                 │
│  Files: bot/services/*.py                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CORE LAYER                                   │
│  Database adapter, cache, configuration                         │
│  Files: bot/core/*.py, bot/config.py                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                   │
│  PostgreSQL database                                            │
│  Tables: rounds, player_stats, weapon_stats, etc.               │
└─────────────────────────────────────────────────────────────────┘
```python

### Patterns Used

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Configuration Object** | `bot/config.py` | Centralize all settings |
| **Repository Pattern** | `bot/repositories/` | Abstract database queries |
| **Adapter Pattern** | `bot/core/database_adapter.py` | Support multiple DB backends |
| **Service Layer** | `bot/services/*.py` | Complex business logic |
| **Cog Pattern** | `bot/cogs/*.py` | Discord.py's plugin system |
| **Background Tasks** | `@tasks.loop()` | Scheduled operations |

---

## 4. Component Breakdown

### Layer 1: Entry Point & Configuration

#### `bot/ultimate_bot.py` (~2,100 lines (post mega-audit cog-mixin split))

- **Purpose:** Main bot class. Handles Discord connection, loads Cogs, runs background tasks.
- **Key sections:**
  - Lines 160-280: `__init__()` - loads config, creates database adapter
  - Lines 370-520: `setup_hook()` - loads all 20 Cogs
  - Lines 1300-1500: `endstats_monitor` - SSH file monitoring task
- **Dependencies:** All Cogs access `self.bot` to reach database, config, cache

#### `bot/config.py` (~680 lines)

- **Purpose:** Centralized configuration object
- **Priority:** ENV vars → `bot_config.json` → hardcoded defaults
- **Key attributes:**
  - `postgres_*` - Database connection
  - `ssh_*` - SSH connection to game server
  - `*_channel_id` - Discord channel routing
  - `session_*_threshold` - Voice detection settings

---

### Layer 2: Database Access

#### `bot/core/database_adapter.py` (~540 lines)

- **Purpose:** Async interface for PostgreSQL
- **Key methods:**

  ```python
  await db.fetch_one(query, params)   # Single row
  await db.fetch_all(query, params)   # All rows
  await db.fetch_val(query, params)   # Single value
  await db.execute(query, params)     # INSERT/UPDATE
  ```python

- **Auto-translation:** `?` placeholders → `$1, $2, $3` for PostgreSQL

#### `postgresql_database_manager.py` (~3,200 lines)

- **Purpose:** CLI tool for database administration
- **Location:** Root directory (runs standalone)
- **Operations:** Backup, rebuild, import, schema check

---

### Layer 3: Data Import Pipeline

#### `bot/community_stats_parser.py` (~1,450 lines)

- **Purpose:** Parse raw stats files into Python dicts
- **Critical detail:** Round 2 files contain CUMULATIVE stats

  ```yaml
  R1: kills=10
  R2: kills=25 (includes R1!)
  Parser calculates: 25 - 10 = 15 kills in R2 only
  ```python

#### `bot/automation/file_tracker.py` (~390 lines)

- **Purpose:** Prevent duplicate imports
- **Logic:**
  1. Check file age (skip old files on restart)
  2. Check in-memory cache
  3. Check `processed_files` database table
  4. Check if round already exists

#### `bot/automation/ssh_handler.py`

- **Purpose:** SSH operations - connect, list files, download
- **Used by:** `endstats_monitor` background task

---

### Layer 4: Services (Business Logic)

#### `bot/services/voice_session_service.py` (~1,090 lines)

- **Purpose:** Detect gaming sessions via Discord voice channels
- **Logic:**
  - 6+ players join voice → session starts
  - <2 players for 5 minutes → session ends
  - Triggers session summaries and predictions

#### `bot/services/round_publisher_service.py` (~920 lines)

- **Purpose:** Auto-post round stats to Discord after processing
- **Flow:** File processed → service builds embed → posts to channel

#### `bot/services/prediction_engine.py` (~740 lines)

- **Purpose:** Predict match outcomes using historical data
- **Output:** "Based on history, Team A has 62% win chance"

---

### Layer 5: Cogs (Discord Commands)

| Cog | Commands | Purpose |
|-----|----------|---------|
| `stats_cog.py` | `!stats`, `!compare` | Individual player stats |
| `leaderboard_cog.py` | `!top`, `!leaderboard` | Rankings by various metrics |
| `last_session_cog.py` | `!last_session` | Rich analytics with graphs (111KB file!) |
| `admin_cog.py` | `!rebuild`, `!import` | Database operations |
| `link_cog.py` | `!link`, `!unlink` | Connect Discord user to game player |
| `session_cog.py` | `!sessions`, `!session N` | View gaming sessions |
| `team_cog.py` | `!teams` | Team composition tracking |
| `predictions_cog.py` | `!predictions` | Match prediction history |
| `achievements_cog.py` | `!achievements` | Badge system |
| `server_control.py` | `!restart` | RCON server commands (optional) |

---

### Layer 6: Core Utilities

#### `bot/core/stats_cache.py`

- **Purpose:** In-memory cache (5-minute TTL)
- **Why:** Database queries are slow; cache speeds up repeated requests

#### `bot/core/team_manager.py` + related files

- **Purpose:** Determine which team each player is on
- **Why:** Raw stats files don't always have reliable team data
- **Methods:** Multiple detection algorithms with confidence scores

---

## 5. Execution Flows

### Flow 1: Bot Startup

```python
1. main() in ultimate_bot.py
   │
   ├── 2. BotConfig() loads from .env → bot_config.json → defaults
   │
   ├── 3. create_adapter() → PostgreSQLAdapter connects to DB
   │
   ├── 4. validate_database_schema() → Checks 54 columns exist
   │
   ├── 5. setup_hook():
   │   ├── Load 20 Cogs from bot/cogs/
   │   ├── Initialize automation services
   │   └── Start background tasks
   │
   └── 6. bot.run(token) → Connect to Discord
```text

### Flow 2: New Stats File Arrives

```sql

1. endstats_monitor task loop (every 60s)
   │
   ├── 2. SSH: List remote files on game server
   │
   ├── 3. file_tracker.should_process_file()?
   │   └── Skip if already processed
   │
   ├── 4. SSH: Download new file to local_stats/
   │
   ├── 5. Parser: Extract 50+ fields per player
   │
   ├── 6. Database: Insert round + player_stats + weapon_stats
   │
   └── 7. round_publisher: Post embed to Discord channel

```text

### Flow 3: User Types `!stats playername`

```text

1. Discord message received
   │
   ├── 2. bot.on_message() → process_commands()
   │
   ├── 3. StatsCog.stats() command handler
   │   │
   │   ├── Check stats_cache first
   │   │
   │   ├── If cache miss → Query database via db_adapter
   │   │
   │   ├── Calculate aggregates (total kills, avg accuracy, etc.)
   │   │
   │   └── Build Discord embed
   │
   └── 4. ctx.send(embed) → User sees stats card

```python

---

## 6. Design Decisions Explained

### Why `BotConfig` class instead of scattered `os.getenv()`?

**Before (anti-pattern):**

```python
class SomeCog:
    def __init__(self, bot):
        self.ssh_host = os.getenv('SSH_HOST', 'localhost')  # Hidden dependency!
```text

**After (centralized):**

```python
class SomeCog:
    def __init__(self, bot):
        self.config = bot.config  # Single source of truth
        # Use: self.config.ssh_host
```yaml

**Benefits:**

1. Testable - inject mock configs in tests
2. Documented - all options in one file
3. Validated - `config.validate()` catches missing values at startup
4. Autocomplete - IDE knows all config properties

---

### Why Repository Pattern for database access?

**Before (SQL in Cogs):**

```python
class SomeCog:
    async def check_file(self, filename):
        rows = await self.db.fetch_all(
            "SELECT * FROM processed_files WHERE filename = ?", 
            (filename,)
        )
```text

**After (Repository):**

```python
class SomeCog:
    async def check_file(self, filename):
        return await self.file_repo.get_processed_filenames()
```sql

**Benefits:**

1. SQL centralized in one place
2. Change schema → update one file
3. Easy to mock for tests

---

### Why Adapter Pattern for database?

**Purpose:** Uniform interface regardless of database backend.

```python
# Cog doesn't care if it's SQLite or PostgreSQL:
await self.db.fetch_one("SELECT * FROM players WHERE name = ?", (name,))
```python

The adapter:

- Translates `?` → `$1, $2` for PostgreSQL
- Handles connection pooling
- Provides async interface

---

### Why extract services from `ultimate_bot.py`?

**Before:** 5,000+ lines in one file. Too much.

**After:** Each class has ONE responsibility:

- `VoiceSessionService` → voice channel logic only
- `RoundPublisherService` → Discord posting only
- `PredictionEngine` → predictions only

`ultimate_bot.py` becomes a **coordinator** - wires services together but doesn't implement their logic.

---

## 7. Key Patterns

| Pattern | Example | When to Use |
|---------|---------|-------------|
| **Configuration Object** | `BotConfig` | Centralize all settings |
| **Repository Pattern** | `FileRepository` | Abstract database queries |
| **Adapter Pattern** | `DatabaseAdapter` | Support multiple backends |
| **Service Layer** | `VoiceSessionService` | Complex business logic |
| **Cog Pattern** | `StatsCog` | Modular command groups |
| **Background Tasks** | `@tasks.loop()` | Scheduled operations |

---

## 8. Anti-Patterns to Avoid

| ❌ Don't | ✅ Do Instead |
|----------|---------------|
| `os.getenv()` scattered in code | Use `self.config.property` |
| SQL queries in Cogs | Use repository methods |
| 5,000-line files | Extract services |
| Sync DB calls in async bot | Always use async adapter |
| Add commands to `ultimate_bot.py` | Create new Cog in `bot/cogs/` |

---

## Quick Reference: File Locations

```python

slomix_discord/
├── bot/
│   ├── ultimate_bot.py           # Main entry point (~2,100 lines (post mega-audit cog-mixin split))
│   ├── config.py                 # Configuration object
│   ├── community_stats_parser.py # Stats file parser
│   │
│   ├── cogs/                     # 14 Discord command modules
│   │   ├── stats_cog.py
│   │   ├── leaderboard_cog.py
│   │   ├── last_session_cog.py   # 111KB - biggest cog
│   │   └── ...
│   │
│   ├── core/                     # Infrastructure
│   │   ├── database_adapter.py   # PostgreSQL interface
│   │   ├── stats_cache.py        # Query caching
│   │   └── team_manager.py       # Team detection
│   │
│   ├── services/                 # Business logic
│   │   ├── voice_session_service.py
│   │   ├── round_publisher_service.py
│   │   └── prediction_engine.py
│   │
│   ├── automation/               # Background operations
│   │   ├── file_tracker.py
│   │   └── ssh_handler.py
│   │
│   └── repositories/             # Data access layer
│       └── file_repository.py
│
├── postgresql_database_manager.py  # DB admin CLI tool
├── local_stats/                    # Downloaded stats files
└── docs/                           # Documentation

```

---

## Next Steps for Learning

1. **Day 1:** Read this document, understand the data flow
2. **Day 2:** Read `bot/config.py` - understand configuration
3. **Day 3:** Read `bot/core/database_adapter.py` - understand DB access
4. **Day 4:** Read one Cog (start with `stats_cog.py`) - understand command flow
5. **Day 5:** Read `community_stats_parser.py` - understand data extraction
6. **Day 6:** Read `ultimate_bot.py` setup_hook and endstats_monitor - understand startup and monitoring

---

**Questions?** Re-read the relevant section or trace the code flow.
