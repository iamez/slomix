# Slomix

**ET:Legacy competitive stats platform** - Discord bot, web dashboard, and game server analytics.

[![Version](https://img.shields.io/badge/version-1.0.6-blue)](docs/CHANGELOG.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14-336791)](https://www.postgresql.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-5865F2)](https://discordpy.readthedocs.io/)

---

## Overview

Slomix tracks player statistics from an ET:Legacy game server and makes them available through Discord commands and a web dashboard. It parses round stats files, handles ET:Legacy's cumulative Round 2 stats with differential calculation, and groups rounds into gaming sessions automatically.

```
ET:Legacy Game Server
├── Stats files (written every round)
│   └── SSH polling (60s) ──→ Parser ──→ PostgreSQL ──→ Discord Bot
│                                                       └── Web Dashboard
└── Lua scripts (real-time)
    ├── stats_discord_webhook.lua ──→ Discord webhook ──→ Bot (timing override)
    └── proximity_tracker.lua ──→ Combat engagement data (prototype)
```

### Key numbers

| Metric | Value |
|--------|-------|
| Rounds tracked | 1,657 |
| Unique players | 32 |
| Gaming sessions | 87 |
| Stats per player per round | 53+ fields |
| Discord commands | ~99 across 21 cogs |
| Database tables | 38 |

---

## Features

### Discord Bot (production)

- **Session stats** - `!last_session` shows full gaming session with per-player stats, team scores, map breakdowns
- **Player analytics** - `!stats`, `!consistency`, `!map_stats`, `!playstyle`, `!fatigue`
- **Leaderboards** - 11 categories: DPM, K/D, accuracy, headshots, efficiency, etc.
- **Matchup analytics** - `!matchup A vs B`, `!duo_perf`, `!nemesis`
- **Match predictions** - AI-powered predictions when teams split into voice channels
- **Achievements** - Badge system for lifetime accomplishments
- **Server control** - RCON commands, server status, map management
- **Full automation** - SSH monitoring, voice detection, auto-posting round stats

### Website (prototype)

FastAPI backend + vanilla JS SPA at `website/`. Player profiles, session browser, leaderboards, live server status.

### Proximity Tracker (prototype)

Lua mod (`proximity/`) that tracks combat engagements, crossfires, and trade kills on the game server.

---

## Architecture

### Data pipeline

1. **Game server** writes stats files per round (`YYYY-MM-DD-HHMMSS-mapname-round-N.txt`)
2. **SSH monitor** polls every 60s, downloads new files
3. **Parser** extracts 53+ fields per player. For Round 2 files (cumulative stats), subtracts matching Round 1 to get differential
4. **PostgreSQL** stores everything with 6-layer validation (file integrity, duplicate prevention, schema validation, cross-field checks, transaction safety, DB constraints)
5. **Discord bot** serves data via commands with 5-minute TTL cache
6. **Lua webhook** (optional) sends real-time round-end data for accurate surrender timing

### Stopwatch mode scoring

ET:Legacy stopwatch maps have two rounds where teams swap sides. The bot:
- Tracks persistent teams across side-swaps using `session_teams`
- Scores by **map wins** (faster attack time wins the map), not individual rounds
- Handles fullholds, double fullholds (1-1 tie), and surrenders

### Key files

| File | Purpose |
|------|---------|
| `bot/ultimate_bot.py` | Main entry point, SSH monitor loop |
| `bot/community_stats_parser.py` | Stats parser with R2 differential |
| `postgresql_database_manager.py` | All DB operations (create, import, rebuild, validate) |
| `bot/core/database_adapter.py` | Async PostgreSQL adapter |
| `bot/cogs/` | 21 command modules |
| `bot/services/` | Business logic layer |
| `vps_scripts/stats_discord_webhook.lua` | Game server Lua script (v1.6.0) |

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Discord bot token

### Install

```bash
git clone https://github.com/iamez/slomix.git
cd slomix
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Discord token, DB credentials, SSH settings
```

### Setup database

```bash
python postgresql_database_manager.py
# Option 1: Create fresh database
# Option 2: Import files from local_stats/
```

### Run

```bash
python -m bot.ultimate_bot
```

Or use the automated installer: `sudo ./install.sh --full --auto`

---

## Configuration

All settings via `.env` file:

```env
# Required
DISCORD_BOT_TOKEN=...
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=...

# Automation (optional)
SSH_ENABLED=true
SSH_HOST=your.server.com
SSH_PORT=22
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot

# Voice monitoring (optional)
AUTOMATION_ENABLED=true
GAMING_VOICE_CHANNELS=channel_id_1,channel_id_2
```

See `.env.example` for all options.

---

## Commands

### Player stats
`!stats <player>` | `!compare <p1> <p2>` | `!consistency <player>` | `!map_stats <player>` | `!playstyle <player>` | `!fatigue <player>`

### Sessions
`!last_session` | `!last_session graphs` | `!sessions` | `!awards`

### Leaderboards
`!top_dpm` | `!top_kd` | `!top_accuracy` | `!top_efficiency` | + 7 more

### Matchups
`!matchup A vs B` | `!duo_perf p1 p2` | `!nemesis <player>`

### Predictions
`!predictions` | `!prediction_stats` | `!prediction_trends` | `!prediction_leaderboard`

### Account linking
`!link` | `!unlink` | `!whoami` | `!set_display_name`

### Server control
`!server_status` | `!rcon <cmd>` | `!players` | `!map <name>`

### Admin
`!sync_all` | `!sync_historical` | `!rebuild_sessions` | `!health`

Full reference: [docs/COMMANDS.md](docs/COMMANDS.md)

---

## Project Structure

```
slomix/
├── bot/                          # Discord bot
│   ├── ultimate_bot.py           # Entry point + SSH monitor
│   ├── community_stats_parser.py # Stats file parser
│   ├── cogs/                     # 21 command modules
│   ├── core/                     # Business logic (team detection, achievements, cache)
│   └── services/                 # Service layer (analytics, scoring, graphs)
├── website/                      # Web dashboard (FastAPI + vanilla JS)
│   ├── backend/                  # API routers and services
│   ├── js/                       # SPA frontend
│   └── assets/                   # Map SVGs, icons
├── proximity/                    # Combat engagement tracker (Lua + Python)
│   ├── lua/                      # Game server mod
│   ├── parser/                   # Engagement data parser
│   └── schema/                   # Database schema
├── vps_scripts/                  # Game server scripts
│   └── stats_discord_webhook.lua # Real-time round notifications
├── docs/                         # Documentation
├── tests/                        # Test suite
├── postgresql_database_manager.py # DB operations tool
└── install.sh                    # Automated installer
```

---

## Database

PostgreSQL with 38 tables. Core tables:

- **`rounds`** - Round metadata, gaming session IDs, match linking
- **`player_comprehensive_stats`** - 53 columns per player per round
- **`weapon_comprehensive_stats`** - Per-weapon breakdown
- **`session_teams`** - Persistent team assignments across side-swaps
- **`lua_round_teams`** - Real-time data from Lua webhook
- **`matchup_history`** - Lineup vs lineup tracking
- **`match_predictions`** - AI prediction tracking with accuracy

Gaming sessions are defined by 60-minute gaps between rounds.

---

## Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](docs/CHANGELOG.md) | Version history |
| [COMMANDS.md](docs/COMMANDS.md) | All bot commands |
| [DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | How data flows through the system |
| [SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md) | 6-layer validation details |
| [TIMING_DATA_SOURCES.md](docs/reference/TIMING_DATA_SOURCES.md) | Stats file vs Lua timing |
| [CLAUDE.md](docs/CLAUDE.md) | AI assistant guide / full technical reference |

---

## Acknowledgments

- [x0rnn](https://github.com/x0rnn) for **gamestats.lua** and **endstats** - the Lua mods that make this possible
- [ET:Legacy](https://www.etlegacy.com/) team for keeping the game alive
- [discord.py](https://github.com/Rapptz/discord.py) and [asyncpg](https://github.com/MagicStack/asyncpg)

---

**Maintainer:** [@iamez](https://github.com/iamez) | **License:** Private
