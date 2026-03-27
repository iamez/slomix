# 🎮 Slomix - ET:Legacy Competitive Stats Platform

> **PostgreSQL-powered real-time analytics for competitive ET:Legacy — Discord bot, web dashboard, demo highlight scanner, and game server telemetry**

[![Production Status](https://img.shields.io/badge/status-production-brightgreen)](https://github.com/iamez/slomix)
[![Version](https://img.shields.io/badge/version-1.2.0-blue)](CHANGELOG.md)
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL_17-336791)](https://www.postgresql.org/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/web-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Data Integrity](https://img.shields.io/badge/data%20integrity-6%20layers-blue)](docs/SAFETY_VALIDATION_SYSTEMS.md)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-5865F2)](https://discordpy.readthedocs.io/)

A **production-grade** Discord bot + web dashboard + demo analysis pipeline with **6-layer data validation**, **real-time Lua telemetry**, **AI match predictions**, and **demo highlight detection** for ET:Legacy game servers.

---

## 🔥 Recent Updates (March 2026)

### **🔬 v1.2.0: Deep RCA Audit, Proximity Pipeline Overhaul & Smart Analytics (March 26-27)** 🆕

**Mandelbrot-depth root cause analysis — 26 fixes, proximity pipeline redesign, website overhaul, smart storytelling architecture.**

- 🔬 **Deep RCA Audit** — 26 fixes across bot, website, proximity (all CRITICAL and HIGH resolved)
- 🔄 **Proximity Pipeline Redesign** — STATS_READY webhook trigger + re-linker task eliminates 60% linkage failures
- 🌐 **Proximity Website Overhaul** — Default scope auto-selection, all 7 leaderboard categories scoped, HTML render fixes, GUID→name resolution, metric tooltips
- 🐛 **Infinite Retry Loop Fix** — `file_tracker.py` now respects `success=FALSE` entries (was retrying forever)
- ⚡ **Skill Rating Optimization** — Merged dual GROUP BY into single pass (~50% less DB load)
- 🛡️ **API Rate Limiting** — slowapi on 3 heavy proximity endpoints
- 🎬 **Upload Fix** — MP4 download now forces `Content-Disposition: attachment`
- 📊 **!last_session Graph Fix** — Decimal*float TypeError resolved (16 conversions)
- 🧠 **Smart Storytelling Stats** — Architecture designed: KIS (Kill Impact Score), 8 Player Archetypes, Match Moments, Team Synergy, Momentum Charts

### **📊 v1.1.0: Stats Accuracy Audit, React 19 Frontend & Proximity v5 (March 2026)**

**Full stats accuracy audit — fixed critical data bugs, modernized frontend, expanded proximity analytics.**

- 🔍 **Stats Accuracy Audit** — Comprehensive review of every stat formula across API, bot, and parser
- 🐛 **R0 Double-Counting Fix** — Match summary rows were inflating kills by 94% and DPM by 32% across 7+ API endpoints
- 🎯 **Accuracy Weighted Average** — Session graph stats now weighted by shots fired (not naive per-round average)
- ⚡ **React 19 + TypeScript 5.9** — Full frontend modernization: Vite 7, Tailwind CSS v4, Framer Motion
- 🗺️ **Proximity v5.0** — Team pushes, trade kills, spawn timing, team cohesion, crossfire opportunities
- 🔧 **ET Rating System** — 9-metric percentile formula, per-session/map drill-down, 40 players rated

**[📖 Full Changelog](CHANGELOG.md)**

---

## ✨ What Makes This Special

- 🔒 **6-Layer Data Integrity** — Transaction safety, ACID guarantees, per-insert verification
- 🤖 **Full Automation** — SSH monitoring, auto-download, auto-import, auto-post (60s cycle)
- ⚡ **Real-Time Lua Telemetry** — Game server webhook fires ~3s after round end
- 🧮 **Differential Calculation** — Smart Round 2 stats (subtracts Round 1 for accurate team-swap metrics)
- 📊 **57 Statistics** — K/D, DPM, accuracy, alive%, efficiency, headshots, damage, playtime, and more
- 🔮 **AI Match Predictions** — 4-factor algorithm (H2H, form, map performance, substitutions)
- 🎬 **Demo Highlight Scanner** — Upload demos, detect multi-kills/sprees, cut clips
- 🏆 **EndStats Awards** — Post-round awards with 7 categories
- 🌐 **Web Dashboard** — FastAPI + React 19 SPA with auth, profiles, leaderboards, proximity analytics

**[📊 Data Pipeline](docs/DATA_PIPELINE.md)** | **[🔒 Safety & Validation](docs/SAFETY_VALIDATION_SYSTEMS.md)** | **[📖 Changelog](CHANGELOG.md)**

---

## 📈 Production Numbers

| Metric | Value |
|--------|-------|
| **Kills Tracked** | 79,303 |
| **Headshot Kills** | 15,474 |
| **Damage Dealt** | 15.7 million |
| **Revives Given** | 5,655 |
| **Rounds Parsed** | 1,320 |
| **Gaming Sessions** | 103+ |
| **Unique Players** | 40+ |
| **Stats Per Player Per Round** | 57 fields |
| **Discord Commands** | ~99 across 21 cogs |
| **Database Tables** | 80 |
| **Data Span** | Jan 2025 — Mar 2026 (15 months) |

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
│  │  ✅ PROD    │         │         │  ✅ PROD    │            │
│  └──────┬──────┘         │         └──────┬──────┘            │
│         │                │                │                    │
│         └────────────────┼────────────────┘                    │
│                          │                                     │
│                  ┌───────▼───────┐                             │
│                  │  PostgreSQL   │                             │
│                  │  80 Tables    │                             │
│                  └───────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

| Project | Status | Description |
|---------|--------|-------------|
| **Discord Bot** (this repo) | ✅ Production | ~99 commands, 21 cogs, full automation, AI predictions |
| **Website** (`/website/`) | ✅ Production | FastAPI + React 19/TypeScript SPA: profiles, sessions, leaderboards, proximity, greatshot |
| **Lua Webhook** (`vps_scripts/`) | ✅ Production | Real-time round notifications, surrender timing fix, team capture |
| **Greatshot** (`/greatshot/`) | ✅ Production | Demo upload, highlight detection, clip extraction, render pipeline |
| **Proximity** (`/proximity/`) | ✅ Production | Lua v6.01 teamplay analytics — engagement, cohesion, crossfire, trade kills, objective intelligence |

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
│  80 tables  |  57 columns per player per round    │
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

### **🎯 Proximity Analytics — Teamplay Intelligence** 🆕

Real-time Lua telemetry (v6.01) tracks every player position, engagement, and objective interaction on the game server. The data flows through a dedicated parser into 22+ database tables, powering deep teamplay analytics:

- 📍 **Combat Engagements** — Every 1v1/NvN encounter with distance, duration, and outcome
- 🔥 **Crossfire Detection** — LOS-verified crossfire angles with execution tracking
- 👥 **Team Cohesion** — Periodic team shape snapshots (centroid, dispersion, buddy pairs)
- ⚡ **Team Pushes** — Coordinated movement detection with objective orientation
- 💀 **Trade Kills** — Server-side trade kill detection with reaction timing
- ⏱️ **Spawn Timing** — Per-kill spawn wave efficiency scoring
- 🎯 **Kill Outcomes** — Gib/revive/tap-out tracking with Kill Permanence Rate (KPR)
- 🗺️ **Combat Heatmaps** — Grid-binned kill/death hotzones with map overlay
- 🦴 **Hit Regions** — HEAD/ARMS/BODY/LEGS hit distribution per weapon
- 🏗️ **Objective Intelligence** — Carrier tracking, construction events, vehicle progress

**Pipeline:** STATS_READY webhook triggers proximity import → re-linker task fixes orphaned data → 2min fallback polling. Eliminates 60% of historical linkage failures.

**Website:** Full React dashboard with scope filtering (session/map/round), 7 leaderboard categories, metric tooltips, and GUID→name resolution.

---

### **📈 ET Rating — Skill Rating System** 🆕

A 9-metric percentile-based skill rating formula that captures the full picture of competitive ET:Legacy performance:

- 🏅 **Percentile Formula** — Combines KD, DPM, accuracy, headshot%, revives, objectives, alive%, efficiency, damage per round
- 📊 **Per-Session Drill-Down** — See how your rating changes across gaming sessions and maps
- 🎯 **Confidence Indicator** — Low/Medium/High based on rounds played
- 🏆 **Server-Side Tiers** — Bronze through Diamond rankings with auto-refresh when stale
- 📈 **History Tracking** — Trend charts showing rating progression over time
- 👥 **40 Players Rated** — Live leaderboard at `/api/skill/leaderboard`

---

### **🧠 Smart Storytelling Stats** *(Coming Soon)*

Transform raw numbers into compelling competitive narratives:

- 💥 **Kill Impact Score (KIS)** — Weights kills by context (clutch kills, opening picks, trade kills)
- 🎭 **8 Player Archetypes** — Aggressive Fragger, Support Anchor, Objective Specialist, Lurker, and more
- ⚡ **Match Moments** — Auto-detect clutch rounds, comeback streaks, dominant pushes
- 🤝 **Team Synergy Score** — Measures duo effectiveness beyond individual stats
- 📉 **Momentum Charts** — Visualize team momentum swings across a match

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
│   │   ├── routers/                 # api, auth, predictions, greatshot, proximity
│   │   └── services/                # greatshot_store, greatshot_jobs
│   ├── frontend/                    # React 19 + TypeScript 5.9 + Vite 7
│   │   ├── src/pages/               # 19 route pages (Sessions, Proximity, Maps, etc.)
│   │   └── src/components/          # Shared components (GlassCard, DataTable, etc.)
│   ├── static/modern/               # Built JS/CSS chunks (from npm run build)
│   ├── js/                          # Legacy JS fallback modules
│   └── index.html                   # Main SPA entry point
│
├── 🎯 proximity/                    # Teamplay analytics engine (v6.01)
│   ├── lua/                         # Game server Lua mod (positions, objectives, hit regions)
│   ├── parser/                      # Engagement + objective data parser
│   └── schema/                      # Database schema (22+ tables)
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
| `vps_scripts/stats_discord_webhook.lua` | Game server Lua script (v1.6.2) |

---

## 🗄️ Database Schema

### **PostgreSQL — 80 Tables**

```sql
-- Core Stats (7)
rounds                          -- Round metadata, gaming_session_id, match_id
player_comprehensive_stats      -- 57 columns per player per round
weapon_comprehensive_stats      -- Per-weapon breakdown
processed_files                 -- File tracking with SHA256 hash
player_links                    -- Discord ↔ game account links
player_aliases                  -- Name change tracking
session_teams                   -- Persistent team assignments

-- Lua Webhook (2)
lua_round_teams                 -- Real-time data from game server Lua
lua_spawn_stats                 -- Per-player spawn/death timing

-- Round Detail (4)
round_awards                    -- EndStats awards (7 categories)
round_vs_stats                  -- Player VS player kill/death records
round_correlations              -- R1+R2 data completeness tracking (23 cols)
processed_endstats_files        -- EndStats file tracking

-- Competitive Analytics (3)
match_predictions               -- AI predictions (35 columns, 6 indexes)
session_results                 -- Session outcomes with team compositions
map_performance                 -- Player per-map rolling averages

-- Greatshot (4)
greatshot_demos                 -- Uploaded demo files with status tracking
greatshot_analysis              -- Parsed analysis (metadata, stats, events)
greatshot_highlights            -- Detected highlights with scores
greatshot_renders               -- Video render jobs and output paths

-- Proximity (12+)
combat_engagement               -- Combat encounter tracking
crossfire_pairs                 -- Crossfire detection
proximity_spawn_timing          -- Spawn wave timing analysis
proximity_team_cohesion         -- Team cohesion timeline
proximity_crossfire_opportunity -- Crossfire setups
proximity_team_push             -- Coordinated pushes
proximity_lua_trade_kill        -- Trade kill detection
player_teamplay_stats           -- Teamplay metrics
player_track                    -- Movement data + heatmaps

-- Website & Infrastructure (20+)
server_status_history, voice_members, availability_*, uploads_*
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
