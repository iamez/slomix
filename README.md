# 🎮 Slomix - ET:Legacy Competitive Stats Platform

> **PostgreSQL-powered real-time analytics for competitive ET:Legacy — Discord bot, web dashboard, demo highlight scanner, and game server telemetry**

[![Production Status](https://img.shields.io/badge/status-production-brightgreen)](https://github.com/iamez/slomix)
[![Version](https://img.shields.io/badge/version-1.0.8-blue)](CHANGELOG.md)
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL_14-336791)](https://www.postgresql.org/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/web-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Data Integrity](https://img.shields.io/badge/data%20integrity-6%20layers-blue)](docs/SAFETY_VALIDATION_SYSTEMS.md)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-5865F2)](https://discordpy.readthedocs.io/)

A **production-grade** Discord bot + web dashboard + demo analysis pipeline with **6-layer data validation**, **real-time Lua telemetry**, **AI match predictions**, and **demo highlight detection** for ET:Legacy game servers.

---

## 🔥 Recent Updates (February 2026)

### **🎬 v1.0.8: Greatshot Highlight Enrichment & Database Cross-Reference (February 8, 2026)** 🆕

**Richer fragmovie scout data with ET:Legacy stats database integration!**

- 🎯 **Enriched Highlight Metadata** — Kill sequences (victim, weapon, HS per kill), weapon usage breakdowns, kill timing rhythm (avg/fastest gaps)
- 👤 **Player Match Stats** — Attacker's overall performance (kills, deaths, KDR, accuracy, damage) attached to each highlight
- 🔗 **Database Cross-Reference** — Auto-match demos to rounds by map/duration/winner/scores (confidence scoring)
- 📊 **Stats Validation** — Side-by-side comparison of demo kills vs DB stats for data health
- 🎨 **Scout-Friendly UI** — Kill sequences, weapon badges, rhythm stats, DB crossref panel in frontend
- 📝 **Enhanced Reports** — Victims, weapons, timing rhythm in text reports
- 🔧 **New Service** — `greatshot_crossref.py` with round matching + DB enrichment

---

### **🎬 v1.0.7: Greatshot Demo Pipeline & Database Overhaul (February 8, 2026)**

**Demo upload, analysis, highlight detection, and clip extraction — now integrated!**

- 🎬 **Greatshot Pipeline** — Upload `.dm_84` demos via the website, auto-analyze with highlight detection
- 🔍 **Highlight Detection** — Multi-kills, killing sprees, quick headshot chains, aim moments
- ✂️ **Clip Extraction** — Cut highlight clips from demos at exact timestamps via UDT_cutter
- 🎥 **Render Queue** — Pipeline ready for video rendering (configurable render backend)
- 🛠️ **UDT Parser Built from Source** — ET:Legacy protocol 84 support via [ryzyk-krzysiek's fork](https://github.com/mightycow/uberdemotools/pull/2), 3 compilation fixes applied
- 🗄️ **4 New Tables** — `greatshot_demos`, `greatshot_analysis`, `greatshot_highlights`, `greatshot_renders`
- 🔧 **Database Manager Overhaul** — Schema creation now covers all 37 tables (was 7), rebuild wipes 20 tables in FK-safe order (was 7), 4 new column migrations

**Origin:** Based on [mittermichal/greatshot-web](https://github.com/mittermichal/greatshot-web) by **Kimi**. We reverse-engineered his architecture, adapted the scanner/highlight/cutter/renderer pipeline to our codebase, wired it into our PostgreSQL database, integrated it with the website's auth system and background job workers, and built the UDT parser from source with ET:Legacy protocol support. The highlight detection algorithms and pipeline design are his — we made them talk to our database and our website. Big thanks to Kimi! 🙏

---

### **📊 v1.0.6: Analytics, Matchups & Website Overhaul (February 1, 2026)**

- 📊 **Player Analytics Commands** — `!consistency`, `!map_stats`, `!playstyle`, `!awards`, `!fatigue`
- ⚔️ **Matchup Analytics** — `!matchup A vs B`, `!duo_perf`, `!nemesis` — lineup vs lineup stats with confidence scoring
- 🏆 **Map-Based Stopwatch Scoring** — Session scores now count MAP wins (not round wins), with full map breakdown + timing
- 👥 **Real-Time Team Tracking** — Teams created on R1, grow dynamically as players join (3v3 → 4v4 → 6v6)
- 🌐 **Website SPA Overhaul** — Sessions, matches, profiles, leaderboards, admin, badges, proximity, season stats pages
- 🎮 **Server Control Cog** — RCON, server status, map management, player list
- 🔫 **Lua Webhook v1.6.0** — Spawn/death tracking, safe gentity access (crash fix)
- 🔴 **Proximity Tracker v3** — Crossfire detection, trade kill support

### **⏱️ v1.0.5: Lua Webhook Enhancements (January 25, 2026)**

- ⏸️ **Lua Webhook v1.3.0** — Pause event timestamps (`Lua_Pauses_JSON`), warmup end tracking, timing legend in Discord embed
- 🔥 **Lua Webhook v1.2.0** — Warmup phase tracking (`Lua_Warmup`, `Lua_WarmupStart`)

### **🚀 v1.0.4: Real-Time Lua Webhook (January 22, 2026)**

- ⚡ **Instant Round Notifications** — Lua webhook fires ~3s after round end (vs 60s SSH polling)
- 🏳️ **Surrender Timing Fix** — Stats files show full map duration on surrender; Lua captures actual played time
- 👥 **Team Composition Capture** — Axis/Allies player lists at round end
- ⏸️ **Pause Tracking** — Game pause detection and timing
- 🗄️ **`lua_round_teams` Table** — Separate storage for Lua-captured data, cross-referenced with stats files

### **🏅 v1.0.3: EndStats & Awards System (January 14, 2026)**

- 🏅 **EndStats Processing** — Parses `-endstats.txt` files for round awards and player VS stats
- 🎖️ **7 Award Categories** — Combat, Deaths & Mayhem, Skills, Weapons, Teamwork, Objectives, Timing
- 📊 **VS Stats Tracking** — Player-vs-player kill/death records per round
- 💬 **Discord Follow-Up Embeds** — Awards posted automatically after round stats
- 🗄️ **3 New Tables** — `round_awards`, `round_vs_stats`, `processed_endstats_files`

**[📖 Full Changelog](CHANGELOG.md)**

---

## ✨ What Makes This Special

- 🔒 **6-Layer Data Integrity** — Transaction safety, ACID guarantees, per-insert verification
- 🤖 **Full Automation** — SSH monitoring, auto-download, auto-import, auto-post (60s cycle)
- ⚡ **Real-Time Lua Telemetry** — Game server webhook fires ~3s after round end
- 🧮 **Differential Calculation** — Smart Round 2 stats (subtracts Round 1 for accurate team-swap metrics)
- 📊 **53+ Statistics** — K/D, DPM, accuracy, efficiency, headshots, damage, playtime, and more
- 🔮 **AI Match Predictions** — 4-factor algorithm (H2H, form, map performance, substitutions)
- 🎬 **Demo Highlight Scanner** — Upload demos, detect multi-kills/sprees, cut clips
- 🏆 **EndStats Awards** — Post-round awards with 7 categories
- 🌐 **Web Dashboard** — FastAPI + vanilla JS SPA with auth, profiles, leaderboards, admin panel

**[📊 Data Pipeline](docs/DATA_PIPELINE.md)** | **[🔒 Safety & Validation](docs/SAFETY_VALIDATION_SYSTEMS.md)** | **[📖 Changelog](CHANGELOG.md)**

---

## 📈 Production Numbers

| Metric | Value |
|--------|-------|
| **Kills Tracked** | 131,648 |
| **Headshots Recorded** | 149,022 |
| **Damage Dealt** | 26 million |
| **Revives Given** | 4,725 |
| **Rounds Parsed** | 1,657 |
| **Gaming Sessions** | 87 |
| **Unique Players** | 32 |
| **Stats Per Player Per Round** | 53+ fields |
| **Discord Commands** | ~99 across 21 cogs |
| **Database Tables** | 37 |
| **Data Span** | Jan 2025 — Feb 2026 (13 months) |

---

## 🔮 Ecosystem

```text
┌─────────────────────────────────────────────────────────────────┐
│                       SLOMIX ECOSYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  DISCORD    │  │   WEB       │  │  GREATSHOT  │            │
│  │  BOT        │  │   DASHBOARD │  │  SCANNER    │            │
│  │  (Python)   │  │  (FastAPI)  │  │  (UDT+Py)   │            │
│  │  ✅ PROD    │  │  ✅ PROD    │  │  🔶 NEW     │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                │                │                    │
│  ┌──────┴──────┐         │         ┌──────┴──────┐            │
│  │ LUA WEBHOOK │         │         │  PROXIMITY  │            │
│  │ (Real-time) │         │         │  TRACKER    │            │
│  │  ✅ PROD    │         │         │  🔶 PROTO   │            │
│  └──────┬──────┘         │         └──────┬──────┘            │
│         │                │                │                    │
│         └────────────────┼────────────────┘                    │
│                          │                                     │
│                  ┌───────▼───────┐                             │
│                  │  PostgreSQL   │                             │
│                  │  37 Tables    │                             │
│                  └───────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

| Project | Status | Description |
|---------|--------|-------------|
| **Discord Bot** (this repo) | ✅ Production | ~99 commands, 21 cogs, full automation, AI predictions |
| **Website** (`/website/`) | ✅ Production | FastAPI + JS SPA: profiles, sessions, leaderboards, admin, greatshot |
| **Lua Webhook** (`vps_scripts/`) | ✅ Production | Real-time round notifications, surrender timing fix, team capture |
| **Greatshot** (`/greatshot/`) | 🔶 New | Demo upload, highlight detection, clip extraction, render pipeline |
| **Proximity** (`/proximity/`) | 🔶 Prototype | Lua combat engagement & heatmap tracking |

---

## 🏗️ System Architecture

### **Data Pipeline Overview**

```text
┌─────────────────────────────────────────────────────────────────┐
│                    ET:Legacy Game Server (VPS)                   │
│  Stats files (.txt)  |  Lua telemetry  |  Demo files (.dm_84)  │
└──────┬───────────────┼─────────────────┼────────────────────────┘
       │               │                 │
       │ SSH/SFTP      │ Discord         │ Web Upload
       │ (60s poll)    │ Webhook (~3s)   │
       ▼               ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Layer 1-2:   │ │ Lua Webhook  │ │ Greatshot    │
│ Download &   │ │ Processing   │ │ Scanner      │
│ Dedup Check  │ │ (timing,     │ │ (UDT_json    │
│              │ │  teams,      │ │  → highlights │
│              │ │  pauses)     │ │  → clips)    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │               │                 │
       ▼               ▼                 ▼
┌──────────────────────────────────────────────────┐
│  Layer 3-4: Parser Validation & Differential     │
│  ✓ R2 differential  ✓ Cross-field checks         │
│  ✓ Time-gap matching  ✓ 7-check pre-insert       │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  Layer 5-6: PostgreSQL (ACID) + Constraints      │
│  ✓ Transaction safety  ✓ FK/NOT NULL/UNIQUE      │
│  37 tables  |  53+ columns per player per round  │
└──────────────────────┬───────────────────────────┘
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         Discord    Website   Background
          Bot       Dashboard  Workers
        (~99 cmds) (FastAPI)  (Analysis,
                              Render)
```

**Processing Speed:** ~3 seconds per file (download → parse → validate → insert → Discord post)

---

## 🔒 Data Integrity & Safety Systems

### **6 Layers of Protection**

| Layer | Component | What It Protects | Blocking? |
|-------|-----------|------------------|-----------|
| **1** | File Transfer | Download corruption, empty files | ✅ Yes |
| **2** | Duplicate Prevention | Re-processing, bot restarts | ✅ Yes |
| **3** | Parser Validation | Invalid types, impossible stats, R2 differential | ✅ Yes |
| **4** | 7-Check Validation | Aggregate mismatches, data loss | ⚠️ No (warns) |
| **5** | Per-Insert Verification | Silent corruption, type conversion | ✅ Yes |
| **6** | PostgreSQL Constraints | NOT NULL, negative values, orphans | ✅ Yes |

**Result:** Every data point verified at **multiple checkpoints** before commit.

**[📖 Full Documentation: SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md)**

### **Round 2 Differential Calculation**

ET:Legacy Round 2 stats files show **cumulative totals** (R1 + R2), not per-round performance. The parser automatically:

1. ✅ Detects Round 2 files by filename
2. ✅ Searches for matching Round 1 file (same map, <60min gap)
3. ✅ Rejects old Round 1 files (different session)
4. ✅ Calculates differential: `R2_actual = R2_cumulative - R1`

```text
Round 1 (21:31): Player vid = 20 kills
Round 2 (23:41): Stats file = 42 kills (cumulative)
         ❌ REJECTED: 21:31 Round 1 (135.9 min gap - different session)
         ✅ MATCHED: 23:41 Round 1 (5.8 min gap - same session)
         Result: vid Round 2 stats = 22 kills (42 - 20)
```

**[📖 Full Documentation: ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt)**

### **Stopwatch Scoring**

ET:Legacy stopwatch maps have two rounds where teams swap attack/defense. Slomix:

- ✅ Tracks persistent teams across side-swaps using `session_teams`
- ✅ Scores by **map wins** (faster attack time wins), not individual rounds
- ✅ Handles fullholds, double fullholds (1-1 tie), and surrenders
- ✅ Grows teams dynamically as players join (3v3 → 4v4 → 6v6)

---

## 🌟 Features

### **🎬 Greatshot — Demo Highlight Scanner** 🆕

Upload ET:Legacy `.dm_84` demo files through the website. The system will:

1. 📤 **Upload** — Secure upload with extension/MIME/header validation, SHA256 hash
2. 🔍 **Parse** — [UberDemoTools](https://github.com/mightycow/uberdemotools) extracts kills, chats, team changes into unified event timeline
3. 🎯 **Detect** — Multi-kill chains, killing sprees, quick headshot sequences, aim moments
4. ✂️ **Cut** — Extract highlight clips from the demo at exact timestamps
5. 🎥 **Render** — Queue video renders (pipeline ready, configurable backend)

**All results stored in PostgreSQL** — analysis JSON, highlight metadata, clip paths, render status. Full API for listing, detail views, and downloads.

**Based on [greatshot-web](https://github.com/mittermichal/greatshot-web) by Kimi (mittermichal).** We adapted his scanner/highlight/cutter/renderer architecture, integrated it with our auth system and PostgreSQL schema, and built UDT from source with [ET:Legacy protocol 84 support](https://github.com/mightycow/uberdemotools/pull/2).

---

### **🔮 AI Match Predictions**

- 🤖 **Automatic Detection** — Detects when players split into team voice channels (3v3, 4v4, 5v5, 6v6)
- 🧠 **4-Factor Algorithm** — H2H (40%), Recent Form (25%), Map Performance (20%), Substitutions (15%)
- 🎯 **Confidence Scoring** — High/Medium/Low based on historical data quality
- 📊 **Real-Time Probability** — Live win probability with sigmoid scaling

**Commands:** `!predictions`, `!prediction_stats`, `!my_predictions`, `!prediction_trends`, `!prediction_leaderboard`, `!map_predictions`

---

### **📊 Player Analytics**

- 📊 **53+ Statistics Tracked** — K/D, DPM, accuracy, efficiency, headshots, damage, playtime
- 🎯 **Smart Player Lookup** — `!stats vid` or `!stats @discord_user`
- 🔗 **Interactive Linking** — React with emojis to link Discord account to game stats
- 📈 **Deep Dives** — `!consistency`, `!map_stats`, `!playstyle`, `!fatigue`
- ⚔️ **Matchup Analytics** — `!matchup A vs B`, `!duo_perf`, `!nemesis`
- 🏆 **Achievement System** — Dynamic badges for medics, engineers, sharpshooters, rambo, objective specialists
- 🎨 **Custom Display Names** — Linked players can set personalized names

### **🏆 Leaderboard System**

- 🥇 **11 Categories** — K/D, DPM, accuracy, headshots, efficiency, revives, and more
- 📈 **Dynamic Rankings** — Real-time updates as games are played
- 🎮 **Minimum Thresholds** — Prevents stat padding (min 10 rounds, 300 damage, etc.)

### **⚡ Real-Time Lua Webhook**

- 🔔 **Instant Notifications** — ~3s after round end (vs 60s SSH polling)
- 🏳️ **Surrender Timing Fix** — Stats files show wrong duration on surrender; Lua captures actual played time
- 👥 **Team Composition** — Axis/Allies player lists at round end
- ⏸️ **Pause Tracking** — Pause events with timestamps, warmup duration
- 🔄 **Cross-Reference** — Both data sources stored separately for validation

### **🤖 Full Automation**

- 🎙️ **Voice Detection** — Monitors gaming voice channels (6+ users = auto-start)
- 🔄 **SSH Monitoring** — Checks VPS every 60 seconds for new files
- 📥 **Auto-Download** — SFTP transfer with integrity verification
- 🤖 **Auto-Import** — Parse → Validate → Database (6-layer safety)
- 📢 **Auto-Post** — Round summaries posted to Discord automatically
- 🏁 **Session Summaries** — Auto-posted when players leave voice
- 💤 **Voice-Conditional** — Only checks SSH when players are in voice channels

---

## 🚀 Quick Start

### **One-Command Dev Stack (Recommended)**

```bash
git clone https://github.com/iamez/slomix.git
cd slomix
make dev
```

This starts:
- PostgreSQL (`localhost:5432`)
- Redis cache (`localhost:6379`)
- FastAPI backend (`localhost:8001`)
- Website (`http://localhost:8000`)

Optional observability stack:

```bash
docker compose --profile observability up --build
```

This also starts Prometheus (`http://localhost:9090`) and Grafana (`http://localhost:3000`).

### **Prerequisites**

- Python 3.11+
- PostgreSQL 12+
- Docker + Docker Compose (for `make dev` workflow)
- Discord Bot Token
- (Optional) SSH access to ET:Legacy game server

### **Installation**

```bash
# Clone & install
git clone https://github.com/iamez/slomix.git
cd slomix
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure
cp .env.example .env
nano .env  # Set DISCORD_BOT_TOKEN, DB credentials, SSH settings

# Setup database (all 37 tables)
python postgresql_database_manager.py  # Option 1: Create fresh

# Run
python -m bot.ultimate_bot
```

**Automated installer:** `sudo ./install.sh --full --auto` (PostgreSQL + systemd + bot)

**Website:** `cd website && uvicorn backend.main:app --host 0.0.0.0 --port 8000`

### **Configuration**

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
SESSION_SECRET=<python -c 'import secrets; print(secrets.token_urlsafe(32))'>

# Greatshot (optional)
GREATSHOT_UDT_JSON_BIN=/path/to/UDT_json
GREATSHOT_UDT_CUTTER_BIN=/path/to/UDT_cutter
GREATSHOT_STORAGE_ROOT=data/greatshot
```

See `.env.example` for all options.

---

## 📋 Commands

### **🎯 Player Stats**
`!stats <player>` · `!stats @user` · `!compare <p1> <p2>` · `!consistency` · `!map_stats` · `!playstyle` · `!fatigue`

### **🏆 Leaderboards**
`!top_dpm` · `!top_kd` · `!top_accuracy` · `!top_efficiency` · + 7 more categories

### **📊 Sessions & Scoring**
`!last_session` · `!last_session graphs` · `!sessions` · `!awards` · `!last_round`

### **⚔️ Matchups & Predictions**
`!matchup A vs B` · `!duo_perf p1 p2` · `!nemesis` · `!predictions` · `!prediction_stats` · `!prediction_trends` · `!prediction_leaderboard`

### **🔗 Account Management**
`!link` · `!unlink` · `!whoami` · `!set_display_name` · `!achievements`

### **🎮 Server Control**
`!server_status` · `!rcon <cmd>` · `!players` · `!map <name>`

### **🔧 Admin**
`!sync_all` · `!sync_historical` · `!rebuild_sessions` · `!health` · `!suggest_teams`

**[📖 Full Command Reference: docs/COMMANDS.md](docs/COMMANDS.md)**

---

## 📁 Project Structure

```text
slomix/
├── 📊 bot/                          # Discord bot
│   ├── ultimate_bot.py              # Entry point + SSH monitor loop
│   ├── community_stats_parser.py    # Stats parser with R2 differential
│   ├── endstats_parser.py           # EndStats awards parser
│   ├── cogs/                        # 21 command modules
│   │   ├── last_session_cog.py      # Session stats & summaries
│   │   ├── leaderboard_cog.py       # Rankings
│   │   ├── analytics_cog.py         # Player analytics
│   │   ├── matchup_cog.py           # Matchup analytics
│   │   ├── predictions_cog.py       # AI predictions (7 commands)
│   │   ├── admin_predictions_cog.py # Prediction admin (5 commands)
│   │   ├── server_control_cog.py    # RCON, status, map management
│   │   └── ... (14 more cogs)
│   ├── core/                        # Team detection, achievements, cache
│   └── services/                    # Analytics, scoring, predictions, graphs
│
├── 🎬 greatshot/                    # Demo analysis pipeline (NEW)
│   ├── scanner/                     # UDT parser adapter + demo sniffing
│   ├── highlights/                  # Multi-kill, spree, headshot detectors
│   ├── cutter/                      # UDT_cutter wrapper for clip extraction
│   ├── renderer/                    # Video render interface
│   ├── contracts/                   # Shared types, profiles, game mappings
│   └── worker/                      # Background job runner
│
├── 🌐 website/                      # Web dashboard
│   ├── backend/                     # FastAPI routers, services, greatshot workers
│   │   ├── routers/                 # api, auth, predictions, greatshot
│   │   └── services/                # greatshot_store, greatshot_jobs
│   ├── js/                          # SPA frontend modules
│   └── index.html                   # Main SPA entry point
│
├── 🎯 proximity/                    # Combat engagement tracker
│   ├── lua/                         # Game server Lua mod
│   ├── parser/                      # Engagement data parser
│   └── schema/                      # Database schema
│
├── 🔧 bin/                          # Compiled binaries (UDT_json, UDT_cutter)
├── 📜 vps_scripts/                  # Game server Lua scripts
├── 📚 docs/                         # Documentation (30+ files)
├── 🧪 tests/                        # Test suite
├── postgresql_database_manager.py   # ALL database operations (one tool to rule them all)
└── install.sh                       # Automated VPS installer
```

**Key Files:**

| File | Purpose |
|------|---------|
| `bot/ultimate_bot.py` | Main entry point, SSH monitor, 21 cog loader |
| `bot/community_stats_parser.py` | R1/R2 differential parser (53+ fields) |
| `postgresql_database_manager.py` | All DB operations: create, import, rebuild, validate |
| `bot/core/database_adapter.py` | Async PostgreSQL adapter with connection pooling |
| `bot/services/prediction_engine.py` | AI match prediction engine (4-factor algorithm) |
| `website/backend/main.py` | FastAPI app with auth, routers, greatshot job workers |
| `greatshot/scanner/api.py` | Demo analysis entry point (UDT → events → highlights) |
| `vps_scripts/stats_discord_webhook.lua` | Game server Lua script (v1.6.0) |

---

## 🗄️ Database Schema

### **PostgreSQL — 37 Tables**

```sql
-- Core Tables (7)
rounds                          -- Round metadata, gaming_session_id, match_id
player_comprehensive_stats      -- 53 columns per player per round
weapon_comprehensive_stats      -- Per-weapon breakdown
processed_files                 -- File tracking with SHA256 hash
player_links                    -- Discord ↔ game account links
player_aliases                  -- Name change tracking
session_teams                   -- Persistent team assignments

-- Lua Webhook (2)
lua_round_teams                 -- Real-time data from game server Lua
lua_spawn_stats                 -- Per-player spawn/death timing

-- Round Detail (3)
round_awards                    -- EndStats awards (7 categories)
round_vs_stats                  -- Player VS player kill/death records
processed_endstats_files        -- EndStats file tracking

-- Competitive Analytics (3)
match_predictions               -- AI predictions (35 columns, 6 indexes)
session_results                 -- Session outcomes with team compositions
map_performance                 -- Player per-map rolling averages

-- Permission & Team Config (3)
user_permissions                -- 3-tier permission system
permission_audit_log            -- Permission change audit trail
team_pool                       -- Team names (sWat, S*F, etc.)

-- Matchup (1)
matchup_history                 -- Lineup vs lineup analytics (JSONB)

-- Greatshot (4) 🆕
greatshot_demos                 -- Uploaded demo files with status tracking
greatshot_analysis              -- Parsed analysis (metadata, stats, events)
greatshot_highlights            -- Detected highlights with scores
greatshot_renders               -- Video render jobs and output paths

-- Website (4)
server_status_history           -- Server status snapshots
voice_members / voice_status_history -- Voice channel tracking
live_status                     -- Real-time server state

-- Proximity (8)
combat_engagement               -- Combat encounter tracking
crossfire_pairs                 -- Crossfire detection
player_teamplay_stats           -- Teamplay metrics
player_track                    -- Movement data
proximity_* / map_*_heatmap     -- Heatmap data
```

**Gaming Session ID:** Automatically calculated — 60-minute gap between rounds = new session.

---

## 🛠️ Development

### **Database Operations**

```bash
python postgresql_database_manager.py
# 1 - Create fresh database (all 37 tables + indexes + seed data)
# 2 - Import all files from local_stats/
# 3 - Rebuild from scratch (wipes game data + re-imports)
# 4 - Fix specific date range
# 5 - Validate database (7-check validation)
# 6 - Quick test (10 files)
```

⚠️ **IMPORTANT:** Never create new import/database scripts. This is the **ONLY** tool for database operations.

### **Running Tests**

```bash
# Parser test
python bot/community_stats_parser.py local_stats/sample-round-1.txt

# Database validation
python postgresql_database_manager.py  # Option 5

# Greatshot tests
pytest tests/test_greatshot_highlights.py
pytest tests/test_greatshot_scanner_golden.py

# Discord bot health
!ping    # Latency
!health  # System health check
```

---

## 📚 Documentation Index

### **Getting Started**
- [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md) — Deployment guide
- [docs/FRESH_INSTALL_GUIDE.md](docs/FRESH_INSTALL_GUIDE.md) — Fresh installation

### **Architecture & Data**
- [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) — Complete data pipeline
- [docs/SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md) — 6-layer validation
- [docs/ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt) — Differential calculation
- [docs/reference/TIMING_DATA_SOURCES.md](docs/reference/TIMING_DATA_SOURCES.md) — Stats file vs Lua timing

### **Reference**
- [docs/COMMANDS.md](docs/COMMANDS.md) — All ~99 bot commands
- [CHANGELOG.md](CHANGELOG.md) — Version history (canonical)
- [docs/CLAUDE.md](docs/CLAUDE.md) — Full technical reference

---

## 🙏 Acknowledgments

**Built With:**

- [discord.py](https://github.com/Rapptz/discord.py) — Discord API wrapper
- [asyncpg](https://github.com/MagicStack/asyncpg) — PostgreSQL async driver
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [PostgreSQL](https://www.postgresql.org/) — Production database
- [UberDemoTools](https://github.com/mightycow/uberdemotools) — Demo parser

**Special Thanks:**

- **[x0rnn (c0rn)](https://github.com/x0rnn)** — for `gamestats.lua` and the endstats system that generates the stats files this entire platform is built on
- **[Kimi (mittermichal)](https://github.com/mittermichal/greatshot-web)** — for developing Greatshot, the demo analysis tool whose architecture we studied, adapted, and integrated into our system. The highlight detection, event normalization, and pipeline design are his work. We built the bridge; he built the engine.
- **[ryzyk-krzysiek](https://github.com/mightycow/uberdemotools/pull/2)** — for adding ET:Legacy protocol 84/284 support to UberDemoTools
- **[mightycow](https://github.com/mightycow/uberdemotools)** — for UberDemoTools itself
- **[ET:Legacy](https://www.etlegacy.com/)** team — for keeping the game alive after 22 years

---

## 📞 Contact

**Project Maintainer:** [@iamez](https://github.com/iamez)
**Repository:** [github.com/iamez/slomix](https://github.com/iamez/slomix)

---

<div align="center">

**⭐ Star this repo if it helped you!**

Built with ❤️ for the ET:Legacy community

</div>
