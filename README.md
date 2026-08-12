# Slomix

**Match statistics and positional telemetry for competitive Enemy Territory: Legacy.**
A Discord bot, a web dashboard, and a Lua tracker that runs on the game server —
built for one 6v6 stopwatch community that has been playing together for two decades.

[![Version](https://img.shields.io/badge/version-1.32.0)](CHANGELOG.md) <!-- x-release-please-version -->
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![PostgreSQL 17 in production](https://img.shields.io/badge/postgresql-17_prod_%7C_14_CI-336791)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/api-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![discord.py 2.6.4](https://img.shields.io/badge/discord.py-2.6.4-5865F2)](https://discordpy.readthedocs.io/)
[![Tests](https://img.shields.io/badge/tests-4200-success)](tests/)

---

## What it is

ET:Legacy writes a stats file at the end of every round. Slomix reads those files,
reconciles them into matches, and keeps them — **2,987 rounds since January 2025**,
57 fields per player per round, 230,343 kills and counting.

That much is ordinary. What makes the dataset unusual is the second source: a Lua
tracker on the game server samples **every player's position, health, weapon, stance
and speed every 200 ms**, alongside per-shot hit regions, engagements, revives and
objective work. A four-minute round produces roughly 3,400 records across 22
sections. There are 63,058 recorded paths in the database.

Stopwatch is what makes this hard. A map is two rounds with the sides swapped, the
second round's stats file is cumulative rather than per-round, sessions cross
midnight, and players change name freely. Most of the code exists to get those four
things right before anything is displayed.

### Scale

| | |
|---|---|
| Rounds parsed | 2,987 since January 2025 |
| Stored per player, per round | 57 fields |
| Telemetry | 29 tables, 1.26 GB, 63,058 player paths |
| Database | 101 tables, 72 migrations |
| Discord | 107 commands across 21 cogs and their mixins |
| Web API | 247 endpoints across 48 routers |
| Code | ~107k lines of Python, ~8.8k of Lua |
| Tests | 4,219 across 304 files |

## What it does

**Reads the game.** SSH polling on a 60-second cycle plus a Lua webhook for
near-real-time round notifications. Round 2 differentials, R1↔R2 pairing, session
grouping on a 60-minute gap, substitution detection, and bot-round exclusion are all
handled by the parser rather than by each query.

**Answers in Discord.** 107 commands across 21 cogs and their mixins: session summaries, per-player
and per-map statistics, head-to-head records, availability polls for the next game
night, and a post-session digest.

**Shows the detail on the web.** A FastAPI backend over 101 tables serving player
profiles, session archives, a record book, a round replay with a 2D map and a
scrubber, rivalries, and a skill rating built from nine percentile metrics.

**Uses the telemetry.** Proximity analytics turn the position stream into
engagements, crossfire geometry, team cohesion, trade kills, spawn timing and
objective runs — scoped to a session, a map, a round, or a single player.

**Handles demos.** Upload a demo, get multi-kills and sprees detected and clips cut
for rendering.

## How it works

A round ends, the server writes a stats file, and about three seconds later the
result is in PostgreSQL and posted to Discord. Two paths feed it: SSH polling on a
60-second cycle, and a Lua webhook that fires as soon as the round ends. Whichever
arrives first wins; the other is skipped because the filename is already recorded as
processed. A SHA-256 of the file is stored alongside that record — not to
deduplicate, but to notice later if a file changed underneath us after it was
imported.

Between the file and the database sit the four problems stopwatch creates. They are
worth spelling out, because most of the parser exists for them.

**Round 2 is cumulative — but not entirely.** ET:Legacy's second-round file reports
totals for the whole map, so the parser subtracts the matched round 1 values field by
field. Except that **23 of the 57 fields are already per-round**: the game's own Lua
resets those variables between rounds, so subtracting would zero them out. XP, kill
assists, headshot kills, death sprees and objectives are in that group. The parser
carries the list; nothing downstream recalculates a differential.

**A map is two files that have to find each other.** Round 1 and round 2 arrive
minutes apart as separate files. Pairing is by map and a 45-minute window, with the
side swap accounted for — the team that defended in round 1 attacks in round 2, so
"winner" means nothing until both halves are known.

**A session is not a date.** An evening that starts at 22:40 and ends at 01:30 is one
session, not two. Grouping is by a 60-minute inactivity gap and stored as
`gaming_session_id`; every session query keys on that id rather than on a calendar
date, which is what keeps midnight crossovers intact.

**A player is a GUID.** Names change mid-evening and are reused. Every aggregate
groups by `player_guid`, never by `player_name`, and display names are resolved
separately at render time.

### The telemetry side

The Lua tracker samples every player's position, health, weapon, stance and speed
every **200 ms**, and team spread every **500 ms**. Around that it records each shot
with origin and view angles, hit regions, engagements and reaction times, aim-lock
traces, spawn timing, kill outcomes with the killer's remaining health, crossfire
geometry, team pushes, revives, trades and objective runs.

That lands in **29 `proximity_*` tables**, currently **1.26 GB** and 63,058 recorded
player paths. Every row is linked back to a round, which is less trivial than it
sounds: the tracker writes before the stats file exists, so rows are matched to their
round afterwards by map, round number and start time.

### Stack

Python 3.11+ with `asyncpg` throughout, PostgreSQL 17 (101 tables, schema managed by
committed migrations with a checksum ledger), FastAPI for the API, `discord.py` for
the bot, Lua on the game server, and a web front end that runs legacy JS as the
production surface with React 19 alongside it. Tests: 4,200, plus Playwright smoke
runs against the real pages.

## Keeping it honest

A dataset is only worth as much as its weakest import, so most of the defensive work
sits between the file and the table rather than in the queries above it.

**Six checkpoints before a row is committed** — download integrity, duplicate
rejection, parser validation, a seven-check aggregate comparison, per-insert
verification, and the database's own constraints. Four of the six block; the
aggregate check warns rather than blocks, deliberately, because a mismatch there is
usually a parser question rather than a corrupt file.

**Schema changes are a ledger, not a habit.** All 72 migrations are recorded with
who applied them and when, and 49 carry a SHA-256 of the file they were applied
from. Editing an applied migration is caught as checksum drift at service startup;
the fix goes in a new migration rather than the old one. A separate contract test
refuses to let a migration exist that no release configuration ships, and another
compares the bootstrap schema dump against what the migrations actually produce —
so a fresh install cannot silently come up missing a column.

**4,219 tests across 304 files**, plus Playwright smoke runs that load the real
pages and fail on a console error, a failed request, an error state, or a loading
placeholder that never resolved. Twelve checks run on every pull request: two Python
versions, JavaScript and shell linting, a React typecheck, dependency audit, static
analysis and a Docker build.

**And a browser is part of the toolchain.** `scripts/audit_website_browser.mjs`
walks every route at four viewport sizes, signed in and signed out, recording
console errors, failed requests, request counts, layout overflow, dead states and
stringified objects that reached the DOM. That last check is not theoretical — it is
how an eighteen-entry map filter was found rendering `[object Object]`, with the
same string as each option's value, which meant the filter had never worked.

## Direction

The project is built for a fixed group of about 65 players, not for growth, and that
shapes what gets built:

- **The session is the unit of interest**, not the all-time table. Most surfaces
  answer "what happened last night" before "who is best ever".
- **Numbers are compared to your own baseline** where possible, rather than ranking
  players against each other.
- **Sample size is respected.** Ratings shrink toward the pool mean until there is
  enough evidence, so nobody reaches the top of a list on one good round.

Deliberately not built: a global all-time K/D ladder, web chat (conversation stays
in Discord), daily streaks or login rewards, and anything that needs manual feeding
to stay current. For a group this size, removing a page is as valuable as adding one.

---

## What is actually in there

Nineteen months of one group's games, not a public dataset. The engineering scale is
in [Scale](#scale) above; these are the games themselves.

| Metric | Value |
|--------|-------|
| **Kills** | 230,343 |
| **Headshot kills** | 49,918 |
| **Damage dealt** | 45.2 million |
| **Revives given** | 26,412 |
| **Rounds** | 2,987 |
| **Unique players** | 65 |
| **Span** | January 2025 — August 2026 |

---

## Ecosystem

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
│                  │  101 Tables   │                             │
│                  └───────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

| Project | Status | Description |
|---------|--------|-------------|
| **Discord Bot** (this repo) | ✅ Production | 107 commands, 21 cogs, full automation, AI predictions |
| **Website** (`/website/`) | ✅ Production | FastAPI + legacy JS + React 19 modern routes: Home, Tonight, sessions/archive, profiles, Record Book, proximity, Greatshot |
| **Lua Webhook** (`vps_scripts/`) | ✅ Production | Real-time round notifications, stopwatch timing, logical-team feed, pause/team capture |
| **Greatshot** (`/greatshot/`) | ✅ Production | Demo upload, highlight detection, clip extraction, render pipeline |
| **Proximity** (`/proximity/`) | ✅ Production telemetry / power-user UI | Lua v6.10+ analytics — engagement, cohesion, crossfire, trade kills, objective intelligence, aim-lock, scoped composite scores, Oksii-adopted fields |

---

## System Architecture

### Data Pipeline Overview

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
│  101 tables  |  57 columns per player per round   │
└──────────────────────┬───────────────────────────┘
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         Discord    Website   Background
          Bot       Dashboard  Workers
        (100+ cmds)(FastAPI)  (Analysis,
                              Render)
```

**Processing Speed:** ~3 seconds per file (download → parse → validate → insert → Discord post)

---

## Data Integrity & Safety Systems

### 6 Layers of Protection

| Layer | Component | What It Protects | Blocking? |
|-------|-----------|------------------|-----------|
| **1** | File Transfer | Download corruption, empty files | ✅ Yes |
| **2** | Duplicate Prevention | Re-processing, bot restarts | ✅ Yes |
| **3** | Parser Validation | Invalid types, impossible stats, R2 differential | ✅ Yes |
| **4** | 7-Check Validation | Aggregate mismatches, data loss | ⚠️ No (warns) |
| **5** | Per-Insert Verification | Silent corruption, type conversion | ✅ Yes |
| **6** | PostgreSQL Constraints | NOT NULL, negative values, orphans | ✅ Yes |

**Result:** Every data point verified at **multiple checkpoints** before commit.

**Security:** Zero `innerHTML` in new code — all dynamic content uses DOM API (`createElement` + `textContent`). 58 Codacy issues resolved with zero suppressions.

**[📖 Full Documentation: SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md)**

### Round 2 Differential Calculation

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

### Stopwatch Scoring

ET:Legacy stopwatch maps have two rounds where teams swap attack/defense. Slomix:

- ✅ Tracks persistent teams across side-swaps using `session_teams`
- ✅ Scores by **map wins** (faster attack time wins), not individual rounds
- ✅ Handles fullholds, double fullholds (1-1 tie), and surrenders
- ✅ Grows teams dynamically as players join (3v3 → 4v4 → 6v6)

---

## Features

### Greatshot — Demo Highlight Scanner

Upload ET:Legacy `.dm_84` demo files through the website. The system will:

1. 📤 **Upload** — Secure upload with extension/MIME/header validation, SHA256 hash
2. 🔍 **Parse** — [UberDemoTools](https://github.com/mightycow/uberdemotools) extracts kills, chats, team changes into unified event timeline
3. 🎯 **Detect** — Multi-kill chains, killing sprees, quick headshot sequences, aim moments
4. ✂️ **Cut** — Extract highlight clips from the demo at exact timestamps
5. 🎥 **Render** — Queue video renders (pipeline ready, configurable backend)

**All results stored in PostgreSQL** — analysis JSON, highlight metadata, clip paths, render status. Full API for listing, detail views, and downloads.

**Based on [greatshot-web](https://github.com/mittermichal/greatshot-web) by Kimi (mittermichal).** We adapted his scanner/highlight/cutter/renderer architecture, integrated it with our auth system and PostgreSQL schema, and built UDT from source with [ET:Legacy protocol 84 support](https://github.com/mightycow/uberdemotools/pull/2).

---

### Proximity Analytics — Teamplay Intelligence

Real-time Lua telemetry (v6.10) tracks every player position, engagement, and objective interaction on the game server. The data flows through a dedicated parser into 30+ database tables, powering deep teamplay analytics:

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

**Website:** Power-user dashboard with session/map/round scope filtering, leaderboard categories, metric tooltips, GUID→name resolution, legacy main page, and React deep routes. Recent hardening made `prox_overall`/composite scores honor the same selected scope instead of silently falling back to a 30-day window.

---

### ET Rating — Skill Rating System

A 9-metric percentile-based skill rating formula that captures the full picture of competitive ET:Legacy performance:

- 🏅 **Percentile Formula** — Combines KD, DPM, accuracy, headshot%, revives, objectives, alive%, efficiency, damage per round
- 📊 **Per-Session Drill-Down** — See how your rating changes across gaming sessions and maps
- 🎯 **Confidence Indicator** — Low/Medium/High based on rounds played
- 🏆 **Server-Side Tiers** — Bronze through Diamond rankings with auto-refresh when stale
- 📈 **History Tracking** — Trend charts showing rating progression over time
- 👥 **50 Players Rated** — Live leaderboard at `/api/skill/leaderboard`

---

### Round Replay Timeline

Relive every round with a full event replay viewer:

- 🎥 **Dual-Pane Viewer** (`/#/replay`) — Event feed on the left, 2D map canvas on the right, synchronized scrubber bar
- 📍 **Player Positions** — Sourced from `player_track.path` JSONB at 200ms precision — see exactly where every player was at every moment
- ⚡ **420+ Events Per Round** — Kills, deaths, revives, objectives, team actions rendered on an interactive timeline
- 🗺️ **2D Map Canvas** — ET:Legacy map overlay with real-time player position dots and event markers
- 🔌 **3 API Endpoints** — Round event feed, player track positions, round metadata

---

### Smart Storytelling Stats

Transform raw numbers into compelling competitive narratives:

- 💥 **Kill Impact Score (KIS)** — Contextual kill scoring with 10+ multipliers: carrier kills (3-5x), push quality, crossfire (1.5x), spawn timing (1-2x), outcome weight (gib/revive), class bonus, distance factor, low-health clutch, graduated reinforcement timing (0.70-1.40x)
- 🎭 **9 Player Archetypes** — Server-side classification using DPM + denied_time + headshot% + KD + trades + revives: Pressure Engine, Medic Anchor, Silent Assassin, Objective Demon, Trade Specialist, Support Fortress, Flanker, All-Rounder, Wildcard
- ⚡ **11 Match Moment Detectors** — Team wipe, multikill, kill streak, carrier chain, focus survival, push success, trade chain, objective secured, objective denied, objective run, multi-revive — each with per-kill breakdown (weapon names, timestamps, duration)
- 📈 **Momentum Chart** — 30-second window momentum scoring with 0.85 decay factor, Canvas 2D dual-line chart (Axis vs Allies), per-round tab navigation
- 📝 **Session Narrative** — Auto-generated paragraph summarizing MVP, player archetype, defining moment, and team synergy comparison
- 🤝 **Team Synergy Score** — 5-axis per-faction comparison: crossfire rate, trade coverage, cohesion quality, push success, medic bonds
- 🔫 **35-Weapon Name Mapping** — Full ET:Legacy weapon name lookup across all moment and archetype displays
- 🎬 **Legacy Story Page** — Cinematic hero, player story cards, moment timeline, KIS breakdown bars, synergy panel at `/#/story`
- 🗄️ **Backend** — `storytelling_kill_impact` DB table, 4 API endpoints, full data access pipeline

---

### Player Rivalries

Deep head-to-head competitive intelligence between any two players:

- 📊 **H2H Stats** — Kills, deaths, KD ratio, accuracy, DPM head-to-head for any player pair
- 🏷️ **Nemesis / Prey / Rival Classification** — Automatically determined from win rate and encounter count
- 🔫 **Weapon Breakdown** — Which weapons each player uses most in this specific matchup
- 🗺️ **Per-Map H2H Drill-Down** — See how the rivalry plays out map by map
- 🏆 **Rivalry Leaderboard** — Top rivalry pairs ranked by total encounters
- 🌐 **Dedicated Page** — Full rivalry dashboard at `/#/rivalries`

---

### Win Contribution (PWC / WIS / WAA)

Quantify exactly how much each player contributed to a round win:

- 📐 **Per-Round Win Contribution (PWC)** — 5-component formula: kills, damage dealt, objectives secured, revives given, survival time
- ⚖️ **Dynamic Weight Redistribution** — When a round has zero objectives, objective weight redistributes automatically to kills and damage
- 📈 **Win Impact Score (WIS)** — avg(PWC in won rounds) − avg(PWC in lost rounds): who actually moves the needle
- 🥇 **MVP Detection** — Highest WIS player flagged as MVP per session
- 📊 **Stacked Bar Visualization** — Per-component breakdown bars for every player in every round

---

### AI Match Predictions

- 🤖 **Automatic Detection** — Detects when players split into team voice channels (3v3, 4v4, 5v5, 6v6)
- 🧠 **4-Factor Algorithm** — H2H (40%), Recent Form (25%), Map Performance (20%), Substitutions (15%)
- 🎯 **Confidence Scoring** — High/Medium/Low based on historical data quality
- 📊 **Real-Time Probability** — Live win probability with sigmoid scaling

**Commands:** `!predictions`, `!prediction_stats`, `!my_predictions`, `!prediction_trends`, `!prediction_leaderboard`, `!map_predictions`

---

### Player Analytics

- 📊 **53+ Statistics Tracked** — K/D, DPM, accuracy, efficiency, headshots, damage, playtime
- 🎯 **Smart Player Lookup** — `!stats vid` or `!stats @discord_user`
- 🔗 **Interactive Linking** — React with emojis to link Discord account to game stats
- 📈 **Deep Dives** — `!consistency`, `!map_stats`, `!playstyle`, `!fatigue`
- ⚔️ **Matchup Analytics** — `!matchup A vs B`, `!duo_perf`, `!nemesis`
- 🏆 **Achievement System** — Dynamic badges for medics, engineers, sharpshooters, rambo, objective specialists
- 🎨 **Custom Display Names** — Linked players can set personalized names

### Leaderboard System

- 🥇 **11 Categories** — K/D, DPM, accuracy, headshots, efficiency, revives, and more
- 📈 **Dynamic Rankings** — Real-time updates as games are played
- 🎮 **Minimum Thresholds** — Prevents stat padding (min 10 rounds, 300 damage, etc.)

### Real-Time Lua Webhook

- 🔔 **Instant Notifications** — ~3s after round end (vs 60s SSH polling)
- 🏳️ **Surrender Timing Fix** — Stats files show wrong duration on surrender; Lua captures actual played time
- 👥 **Team Composition** — Axis/Allies player lists at round end
- ⏸️ **Pause Tracking** — Pause events with timestamps, warmup duration
- 🔄 **Cross-Reference** — Both data sources stored separately for validation

### Full Automation

- 🎙️ **Voice Detection** — Monitors gaming voice channels (6+ users = auto-start)
- 🔄 **SSH Monitoring** — Checks VPS every 60 seconds for new files
- 📥 **Auto-Download** — SFTP transfer with integrity verification
- 🤖 **Auto-Import** — Parse → Validate → Database (6-layer safety)
- 📢 **Auto-Post** — Round summaries posted to Discord automatically
- 🏁 **Session Summaries** — Auto-posted when players leave voice
- 💤 **Voice-Conditional** — Only checks SSH when players are in voice channels

---

## Quick Start

### One-Command Dev Stack (Recommended)

```bash
git clone https://github.com/iamez/slomix.git
cd slomix
make dev
```

This starts:
- PostgreSQL (`localhost:5432`)
- Redis cache (`localhost:6379`)
- FastAPI backend (`localhost:8001` — container's `:8000` published to host `:8001`)
- Website (`http://localhost:7000` — default per `WEBSITE_PUBLIC_PORT` in `docker-compose.yml`)

Optional observability stack:

```bash
docker compose --profile observability up --build
```

This also starts Prometheus (`http://localhost:9090`) and Grafana (`http://localhost:3000`).

### Prerequisites

- Python 3.11+
- PostgreSQL 12 or newer — the schema uses stored generated columns, which is
  where the floor comes from. **CI runs 14 and production runs 17**; those are the
  two versions actually tested.
- Docker + Docker Compose (for `make dev` workflow)
- Discord Bot Token
- (Optional) SSH access to ET:Legacy game server

### Installation

```bash
# Clone & install
git clone https://github.com/iamez/slomix.git
cd slomix
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure
cp .env.example .env
nano .env  # Set DISCORD_BOT_TOKEN, DB credentials, SSH settings

# Setup database (100+ tables)
python postgresql_database_manager.py  # Option 1: Create fresh

# Run
python -m bot.ultimate_bot
```

**Automated installer:** `sudo ./install.sh --full --auto` (PostgreSQL + systemd + bot)

**Website:** `cd website && uvicorn backend.main:app --host 0.0.0.0 --port 8000`

### Configuration

```env
# Required — the bot reads POSTGRES_* names only (see .env.example)
DISCORD_BOT_TOKEN=...
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=...

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
INTERNAL_API_SECRET=<python -c 'import secrets; print(secrets.token_urlsafe(32))'>

# Greatshot (optional)
GREATSHOT_UDT_JSON_BIN=/path/to/UDT_json
GREATSHOT_UDT_CUTTER_BIN=/path/to/UDT_cutter
GREATSHOT_STORAGE_ROOT=data/greatshot
```

See `.env.example` for all options.

---

## Commands

### Player Stats
`!stats <player>` · `!stats @user` · `!compare <p1> <p2>` · `!consistency` · `!map_stats` · `!playstyle` · `!fatigue` · `!find_player`

### Leaderboards
`!leaderboard <category>` (aliases `!lb`, `!top`) — dpm, kd, accuracy, efficiency, revives + more

### Sessions & Scoring
`!last_session` · `!last_session graphs` · `!session` · `!rounds` · `!session_score` · `!awards` · `!season_info`

### Matchups & Predictions (rivalries live on the web at `/#/rivalries`)
`!matchup A vs B` · `!duo_perf p1 p2` · `!nemesis` · `!head_to_head` · `!team_record` · `!predictions` · `!prediction_stats` · `!prediction_trends` · `!prediction_leaderboard` · `!map_predictions`

### Account Management
`!link` · `!unlink` · `!setname` · `!myaliases` · `!achievements` · `!badges`

### Server Control
`!server_status` · `!rcon <cmd>` · `!list_players` · `!list_maps` · `!map_change <name>` · `!server_start` · `!server_stop`

### Admin
`!sync_all` · `!sync_historical` · `!sync_today` · `!assign_teams` · `!correlation_status` · `!backup_db` · `!health` · `!start_monitoring`

**[📖 Full Command Reference: docs/COMMANDS.md](docs/COMMANDS.md)**

---

## Project Structure

```text
slomix/
├── 📊 bot/                          # Discord bot
│   ├── ultimate_bot.py              # Entry point + SSH monitor loop
│   ├── community_stats_parser.py    # Stats parser with R2 differential
│   ├── endstats_parser.py           # EndStats awards parser
│   ├── cogs/                        # 20 command modules
│   │   ├── last_session_cog.py      # Session stats & summaries
│   │   ├── leaderboard_cog.py       # Rankings
│   │   ├── analytics_cog.py         # Player analytics
│   │   ├── matchup_cog.py           # Matchup analytics
│   │   ├── predictions_cog.py       # AI predictions
│   │   ├── admin_predictions_cog.py # Prediction admin
│   │   ├── server_control.py        # RCON, status, map management
│   │   └── ... (13 more cogs)
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
│   │   ├── src/pages/               # 25 route pages (Sessions, Proximity, Maps, etc.)
│   │   └── src/components/          # Shared components (GlassCard, DataTable, etc.)
│   ├── static/modern/               # Built JS/CSS chunks (from npm run build)
│   ├── js/                          # Legacy JS fallback modules
│   └── index.html                   # Main SPA entry point
│
├── 🎯 proximity/                    # Teamplay analytics engine (v6.10)
│   ├── lua/                         # Game server Lua mod (positions, objectives, hit regions)
│   ├── parser/                      # Engagement + objective data parser
│   └── schema/                      # Database schema (30+ tables)
│
├── 🔧 bin/                          # Compiled binaries (UDT_json, UDT_cutter)
├── 📜 vps_scripts/                  # Game server Lua scripts
├── 📚 docs/                         # Documentation (150+ files)
├── 🧪 tests/                        # Test suite
├── postgresql_database_manager.py   # ALL database operations (one tool to rule them all)
└── install.sh                       # Automated VPS installer
```

**Key Files:**

| File | Purpose |
|------|---------|
| `bot/ultimate_bot.py` | Main entry point, SSH monitor, 20 cog loader |
| `bot/community_stats_parser.py` | R1/R2 differential parser (53+ fields) |
| `postgresql_database_manager.py` | All DB operations: create, import, rebuild, validate |
| `bot/core/database_adapter.py` | Async PostgreSQL adapter with connection pooling |
| `bot/services/prediction_engine.py` | AI match prediction engine (4-factor algorithm) |
| `website/backend/main.py` | FastAPI app with auth, routers, greatshot job workers |
| `greatshot/scanner/api.py` | Demo analysis entry point (UDT → events → highlights) |
| `vps_scripts/stats_discord_webhook.lua` | Game server Lua script (v1.7.1) |

---

## Database Schema

### PostgreSQL — 101 Tables

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

## Development

### Database Operations

```bash
python postgresql_database_manager.py
# 1 - Create fresh database (100+ tables + indexes + seed data)
# 2 - Import all files from local_stats/
# 3 - Rebuild from scratch (wipes game data + re-imports)
# 4 - Fix specific date range
# 5 - Validate database (7-check validation)
# 6 - Quick test (10 files)
```

⚠️ **IMPORTANT:** Never create new import/database scripts. This is the **ONLY** tool for database operations.

### Running Tests

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

## Documentation Index

### Getting Started
- [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md) — Deployment guide
- [docs/FRESH_INSTALL_GUIDE.md](docs/FRESH_INSTALL_GUIDE.md) — Fresh installation

### Architecture & Data
- [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) — Complete data pipeline
- [docs/SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md) — 6-layer validation
- [docs/ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt) — Differential calculation
- [docs/reference/TIMING_DATA_SOURCES.md](docs/reference/TIMING_DATA_SOURCES.md) — Stats file vs Lua timing

### Reference
- [docs/COMMANDS.md](docs/COMMANDS.md) — Every visible bot command
- [CHANGELOG.md](CHANGELOG.md) — Version history, generated from commits

---

## Acknowledgments

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

## Contact

**Project Maintainer:** [@iamez](https://github.com/iamez)
**Repository:** [github.com/iamez/slomix](https://github.com/iamez/slomix)

---

<div align="center">

**⭐ Star this repo if it helped you!**

Built with ❤️ for the ET:Legacy community

</div>
