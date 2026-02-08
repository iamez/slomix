<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.7-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PostgreSQL-14-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/discord.py-2.0+-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord.py">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
</p>

<h1 align="center">Slomix</h1>

<p align="center">
  <strong>A love letter to competitive ET:Legacy, written in Python and PostgreSQL.</strong>
</p>

<p align="center">
  Discord bot. Web dashboard. Demo highlight scanner. Real-time game telemetry.<br>
  Built by players, for players &mdash; because every frag deserves to be remembered.
</p>

---

## The Story

It started the way most side projects do: *"I just want to see who had the best K/D last night."*

Thirteen months later, there are **131,000+ kills** tracked across **1,657 rounds** and **87 gaming sessions**. The system parses stats files, cross-references them with real-time Lua telemetry from the game server, detects highlights in demo recordings, and tells you exactly who dominated &mdash; and who got dominated &mdash; in every session since January 2025.

What was once a single Python script reading a text file is now a platform with **37 database tables**, **~99 Discord commands**, a full web dashboard, an AI match prediction engine, and a demo analysis pipeline that can find your triple headshot from last Tuesday.

This is Slomix.

---

## What It Does

```
                         ET:Legacy Game Server
                        /         |          \
                       /          |           \
              Stats Files    Lua Telemetry    Demo Files (.dm_84)
                  |               |                |
             SSH Monitor     Discord Webhook    Web Upload
              (60s poll)      (~3s real-time)       |
                  |               |            Greatshot
                  v               v            Scanner
               Parser ──> PostgreSQL <──────────┘
              (53+ fields     (37 tables)
               per player)      |
                  |        _____|_____
                  |       |           |
                  v       v           v
             Discord Bot        Web Dashboard
            (~99 commands)    (FastAPI + JS SPA)
```

### Discord Bot (production)

The heart of the system. 21 cogs, 99 commands, always watching.

- **Session stats** &mdash; `!last_session` renders a full gaming session: per-player stats, map-based stopwatch scores, team compositions, timing breakdowns
- **Player analytics** &mdash; `!stats`, `!consistency`, `!map_stats`, `!playstyle`, `!fatigue` &mdash; deep dives into how you play and how you're trending
- **Leaderboards** &mdash; 11 categories: DPM, K/D, accuracy, headshots, revives, efficiency, and more
- **Matchup analytics** &mdash; `!matchup sWat vs S*F`, `!duo_perf`, `!nemesis` &mdash; lineup vs lineup history with confidence scoring
- **Match predictions** &mdash; AI-powered win probability when teams split into voice channels, based on historical matchup data, recent form, map performance, and substitution impact
- **Achievements** &mdash; badge system for lifetime milestones (medic, sharpshooter, engineer, rambo, objective specialist)
- **Server control** &mdash; RCON commands, live player list, map management
- **Full automation** &mdash; SSH monitoring, voice channel detection, auto-posting round stats the moment they happen

### Web Dashboard (production)

FastAPI backend serving a vanilla JS single-page app. Player profiles, session browser, leaderboards, season stats, live server status, admin panel, proximity heatmaps, and now &mdash; greatshot.

### Greatshot &mdash; Demo Highlight Scanner (new)

This one deserves its own section.

**Greatshot** is a demo analysis pipeline that scans ET:Legacy `.dm_84` recordings, detects highlight-worthy moments, and prepares them for clip extraction and rendering.

Upload a demo through the website. The system will:
1. **Parse** it using [UberDemoTools](https://github.com/mightycow/uberdemotools) (ET:Legacy protocol 84 support via [ryzyk-krzysiek's PR](https://github.com/mightycow/uberdemotools/pull/2))
2. **Normalize** the raw parser output into a unified event timeline (kills, chats, team changes)
3. **Detect highlights** &mdash; multi-kills, killing sprees, quick headshot chains, aim moments
4. **Cut clips** from the demo file at the exact timestamps
5. **Queue renders** for video output (pipeline ready, render backend configurable)

The original greatshot was developed by **[Kimi (mittermichal)](https://github.com/mittermichal/greatshot-web)** as a standalone demo analysis tool. We reverse-engineered his architecture, adapted the scanner/highlight/cutter/renderer pipeline to our codebase, wired it into our PostgreSQL database (4 new tables), integrated it with the website's auth system and background job workers, built the UDT parser from source with ET:Legacy protocol support (3 compilation fixes required), and gave it a home inside our existing infrastructure. The highlight detection algorithms, event normalization patterns, and pipeline design philosophy are Kimi's &mdash; we just made them talk to our database and our website.

Thank you, Kimi. Seriously.

### Proximity Tracker (prototype)

Lua mod running on the game server that tracks real-time combat engagements &mdash; who fought who, at what range, crossfires, trade kills. Data feeds into 8 database tables and the website's proximity visualization page.

---

## By The Numbers

These are live production numbers, not demo data:

| | |
|---|---|
| **131,648** kills tracked | **149,022** headshots recorded |
| **26 million** damage dealt | **4,725** revives given |
| **1,657** rounds parsed | **87** gaming sessions |
| **32** unique players | **37** database tables |
| **~99** Discord commands | **21** command modules (cogs) |
| **53+** stats per player per round | **13 months** of data (Jan 2025 &mdash; Feb 2026) |

---

## The Data Pipeline

This is the part we're most proud of. Six layers of validation, zero data loss.

### 1. Stats File Parsing

ET:Legacy writes a stats file after every round. The parser extracts 53+ fields per player: kills, deaths, headshots, damage, accuracy, revives, objectives, time played, and much more.

**The Round 2 problem:** ET:Legacy Round 2 stats files contain *cumulative* totals (R1 + R2), not R2-only performance. The parser automatically finds the matching Round 1 file, validates the time gap (must be <60 minutes), and calculates the differential. This happens transparently on every import.

### 2. Lua Webhook (real-time)

A Lua script on the game server fires a Discord webhook the instant a round ends (~3 seconds vs 60-second SSH polling). It captures:
- Accurate round timing (fixes the surrender timing bug where stats files show full map duration)
- Team compositions at round end
- Pause events with timestamps
- Warmup duration
- Surrender detection

Both data sources are stored separately (`rounds` table + `lua_round_teams` table) and cross-referenced for validation.

### 3. Stopwatch Scoring

ET:Legacy stopwatch maps have two rounds where teams swap attack/defense. Slomix:
- Tracks persistent teams across side-swaps
- Scores by **map wins** (faster attack wins), not individual rounds
- Handles fullholds, double fullholds (1-1 tie), surrenders
- Grows teams dynamically as players join (3v3 &rarr; 4v4 &rarr; 6v6)

### 4. Six-Layer Validation

Every stats file import passes through:
1. **File integrity** &mdash; SHA256 hash stored and verified
2. **Duplicate prevention** &mdash; filename + round_time unique constraint
3. **Schema validation** &mdash; 53-column check on bot startup
4. **Cross-field validation** &mdash; headshots <= kills, time_dead <= time_played, etc.
5. **Transaction safety** &mdash; atomic commits, rollback on any failure
6. **Database constraints** &mdash; foreign keys, NOT NULL, type enforcement

---

## Architecture

### Key Files

| File | What it does |
|------|-------------|
| `bot/ultimate_bot.py` | Main entry point. SSH monitor loop, 21 cog loader, event handlers |
| `bot/community_stats_parser.py` | Stats parser with R2 differential calculation |
| `postgresql_database_manager.py` | All DB operations: create, import, rebuild, validate, wipe |
| `bot/core/database_adapter.py` | Async PostgreSQL adapter with connection pooling |
| `bot/cogs/` | 21 command modules (session stats, leaderboards, analytics, predictions, admin...) |
| `bot/services/` | Business logic: scoring, predictions, graphs, matchups, badges |
| `website/backend/main.py` | FastAPI app with auth, API routers, greatshot job workers |
| `greatshot/` | Demo scanner, highlight detection, clip cutter, render pipeline |
| `proximity/` | Combat engagement tracker (Lua + Python + 8 DB tables) |
| `vps_scripts/stats_discord_webhook.lua` | Game server Lua script (v1.6.0) |

### Project Structure

```
slomix/
├── bot/                          # Discord bot
│   ├── ultimate_bot.py           # Entry point + SSH monitor
│   ├── community_stats_parser.py # Stats file parser
│   ├── cogs/                     # 21 command modules
│   ├── core/                     # Team detection, achievements, cache, adapters
│   └── services/                 # Analytics, scoring, predictions, graphs
├── website/                      # Web dashboard
│   ├── backend/                  # FastAPI routers, services, greatshot workers
│   ├── js/                       # SPA frontend modules
│   └── assets/                   # Map SVGs, icons
├── greatshot/                    # Demo analysis pipeline
│   ├── scanner/                  # UDT parser adapter + demo header sniffing
│   ├── highlights/               # Multi-kill, spree, headshot chain detectors
│   ├── cutter/                   # UDT_cutter wrapper for clip extraction
│   ├── renderer/                 # Video render interface
│   ├── contracts/                # Shared types, profiles, game-specific mappings
│   └── worker/                   # Background job runner
├── proximity/                    # Combat engagement tracker
│   ├── lua/                      # Game server Lua mod
│   ├── parser/                   # Engagement data parser
│   └── schema/                   # Database schema
├── bin/                          # Compiled binaries (UDT_json, UDT_cutter)
├── vps_scripts/                  # Game server scripts
├── docs/                         # Documentation (30+ files)
├── tests/                        # Test suite
├── postgresql_database_manager.py # The one database tool to rule them all
└── install.sh                    # Automated VPS installer
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Discord bot token
- (Optional) SSH access to ET:Legacy game server

### Install

```bash
git clone https://github.com/iamez/slomix.git
cd slomix
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Discord token, DB credentials, SSH settings
```

### Setup Database

```bash
python postgresql_database_manager.py
# Option 1: Create fresh database (all 37 tables)
# Option 2: Import stats files from local_stats/
# Option 3: Full rebuild (wipe + re-import)
# Option 5: Validate database integrity (7 checks)
```

### Run

```bash
# Discord bot
python -m bot.ultimate_bot

# Website (separate process)
cd website && uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Or use the automated installer for full VPS setup
sudo ./install.sh --full --auto
```

---

## Configuration

All settings via `.env`:

```env
# Required
DISCORD_BOT_TOKEN=...
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=...

# Automation (optional but recommended)
SSH_ENABLED=true
SSH_HOST=your.server.com
SSH_PORT=22
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot

# Voice monitoring
AUTOMATION_ENABLED=true
GAMING_VOICE_CHANNELS=channel_id_1,channel_id_2

# Website
SESSION_SECRET=<generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'>

# Greatshot (optional)
GREATSHOT_UDT_JSON_BIN=/path/to/UDT_json
GREATSHOT_UDT_CUTTER_BIN=/path/to/UDT_cutter
GREATSHOT_STORAGE_ROOT=data/greatshot
```

See `.env.example` for all options.

---

## Commands at a Glance

### Player Stats
`!stats <player>` &middot; `!compare <p1> <p2>` &middot; `!consistency` &middot; `!map_stats` &middot; `!playstyle` &middot; `!fatigue`

### Sessions & Scoring
`!last_session` &middot; `!last_session graphs` &middot; `!sessions` &middot; `!awards`

### Leaderboards
`!top_dpm` &middot; `!top_kd` &middot; `!top_accuracy` &middot; `!top_efficiency` &middot; + 7 more

### Matchups & Predictions
`!matchup A vs B` &middot; `!duo_perf p1 p2` &middot; `!nemesis` &middot; `!predictions` &middot; `!prediction_stats`

### Account Linking
`!link` &middot; `!unlink` &middot; `!whoami` &middot; `!set_display_name`

### Server Control
`!server_status` &middot; `!rcon <cmd>` &middot; `!players` &middot; `!map <name>`

### Admin
`!sync_all` &middot; `!sync_historical` &middot; `!rebuild_sessions` &middot; `!health`

Full reference: **[docs/COMMANDS.md](docs/COMMANDS.md)**

---

## Version History

### v1.0.7 (Feb 2026)
- **Greatshot integration** &mdash; demo upload, analysis, highlight detection, clip extraction via website
- **Database manager overhaul** &mdash; schema creation now covers all 37 tables (was 7), rebuild wipes all game data tables (was 7), 4 new column migrations
- **UDT parser built from source** with ET:Legacy protocol 84 support

### v1.0.6 (Feb 2026)
- **Player analytics** &mdash; consistency, map stats, playstyle, fatigue analysis
- **Matchup system** &mdash; lineup vs lineup historical tracking with confidence scoring
- **Map-based stopwatch scoring** &mdash; session scores count map wins, not rounds
- **Real-time team tracking** &mdash; teams grow dynamically as players join
- **Website SPA overhaul** &mdash; sessions, matches, profiles, leaderboards, admin, badges, proximity, season stats

### v1.0.5 (Jan 2026)
- **Lua webhook v1.3.0** &mdash; pause timestamps, warmup tracking, timing legend

### v1.0.4 (Jan 2026)
- **Lua webhook** &mdash; real-time round notifications (~3s), surrender timing fix, team composition capture

### v1.0.3 (Jan 2026)
- **EndStats processing** &mdash; round awards, player VS stats, 7 award categories

### v1.0.0 (Nov 2025)
- Production release. 63 commands, 6-layer validation, PostgreSQL, full automation, achievements.

Full changelog: **[docs/CHANGELOG.md](docs/CHANGELOG.md)**

---

## Documentation

| Document | What you'll find |
|----------|-----------------|
| **[CHANGELOG.md](docs/CHANGELOG.md)** | Every version, every fix, every feature |
| **[COMMANDS.md](docs/COMMANDS.md)** | All ~99 bot commands with usage |
| **[DATA_PIPELINE.md](docs/DATA_PIPELINE.md)** | How data flows from game server to Discord |
| **[SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md)** | The 6-layer validation system in detail |
| **[TIMING_DATA_SOURCES.md](docs/reference/TIMING_DATA_SOURCES.md)** | Stats file vs Lua timing &mdash; why we need both |
| **[CLAUDE.md](docs/CLAUDE.md)** | Full technical reference (the AI reads this) |

---

## Acknowledgments

This project wouldn't exist without the people who keep ET:Legacy alive and the tools they build.

- **[x0rnn](https://github.com/x0rnn)** &mdash; for `gamestats.lua` and the endstats system that generates the stats files this entire platform is built on
- **[Kimi (mittermichal)](https://github.com/mittermichal/greatshot-web)** &mdash; for developing Greatshot, the demo analysis tool whose architecture we studied, adapted, and integrated into our system. The highlight detection, event normalization, and pipeline design are his work. We built the bridge; he built the engine.
- **[ryzyk-krzysiek](https://github.com/mightycow/uberdemotools/pull/2)** &mdash; for adding ET:Legacy protocol 84/284 support to UberDemoTools, making demo parsing possible for our game
- **[mightycow](https://github.com/mightycow/uberdemotools)** &mdash; for UberDemoTools itself
- **[ET:Legacy](https://www.etlegacy.com/)** team &mdash; for keeping the game alive after 22 years
- **[discord.py](https://github.com/Rapptz/discord.py)** and **[asyncpg](https://github.com/MagicStack/asyncpg)** &mdash; the async foundations everything runs on

---

<p align="center">
  <strong>Maintainer:</strong> <a href="https://github.com/iamez">@iamez</a> &middot; <strong>License:</strong> Private
</p>

<p align="center">
  <em>Built with late nights, too much coffee, and the belief that a 22-year-old game still deserves world-class tooling.</em>
</p>
