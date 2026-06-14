# 🎓 Slomix — Architecture Onboarding Guide

**Created:** December 2, 2025
**Last updated:** June 14, 2026 (whole-platform rewrite — added website, proximity, greatshot, Lua webhook, VISION_2026)
**Purpose:** Complete system understanding for new developers
**Reading time:** ~50 minutes for the full document

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [The Platform at a Glance](#2-the-platform-at-a-glance)
3. [Data Flow Pipeline](#3-data-flow-pipeline)
4. [Architecture Style](#4-architecture-style)
5. [Component Breakdown — The Bot](#5-component-breakdown--the-bot)
6. [Component Breakdown — The Website](#6-component-breakdown--the-website)
7. [Component Breakdown — Proximity & Greatshot](#7-component-breakdown--proximity--greatshot)
8. [Execution Flows](#8-execution-flows)
9. [Design Decisions Explained](#9-design-decisions-explained)
10. [Key Patterns & Anti-Patterns](#10-key-patterns--anti-patterns)
11. [Database Schema](#11-database-schema)
12. [Complete File Reference](#12-complete-file-reference)
13. [Next Steps for Learning](#13-next-steps-for-learning)

---

## 1. What This Project Is

### In Plain English

Slomix is the **operating system of a 20-year ET:Legacy community**. It started as a
Discord bot that tracks game statistics for Wolfenstein: Enemy Territory (a team-based
multiplayer shooter from 2003 with a still-active competitive scene) — and it has grown
into a full platform: a Discord bot, a web dashboard, a real-time game-server telemetry
layer, and a demo-highlight pipeline.

**The product philosophy (VISION_2026):** *the evening is the product; the website is its
memory.* Discord stays the **river** (conversation, triggers, the morning digest); the
**website** is the **library** (identity, depth, the permanent record). The bot is
increasingly the **pipeline** that feeds both. See [`docs/VISION_2026.md`](VISION_2026.md).

**The problem it solves:** before Slomix, game stats were lost after every match. Now:

- Players query `!stats myname` (Discord) or open a rich profile (web) for lifetime + per-session stats
- A **morning digest** recaps each game night (winner, MVP, new personal bests, narrative)
- Deep teamplay analytics (proximity), skill ratings, rivalries, predictions, and demo highlights
- Seasons, peer-voted awards, and valueless-points betting keep the whole roster engaged

### What It Does (end-to-end)

1. **Generates** stats on the game server (Lua mods write stats files + send a real-time webhook)
2. **Collects** them — SSH polling for stats files, a Discord webhook for instant round metadata
3. **Parses** raw text into structured data (57 fields per player per round, R2 differential)
4. **Correlates** every data source for a match (R1+R2 stats, Lua teams, proximity, endstats)
5. **Stores** everything in PostgreSQL (101 tables) with transaction safety
6. **Presents** it through 100+ Discord commands **and** a FastAPI + JS web dashboard
7. **Tells the story** — morning digests, narratives, momentum charts, season awards

Think of it as a **sports-analytics platform** for a video game — delivered through both
Discord and the web.

---

## 2. The Platform at a Glance

```text
                         ET:Legacy GAME SERVER (VPS)
        c0rnp0rn8.lua (stats files)  ·  stats_discord_webhook.lua (real-time)
                    proximity_tracker.lua (player positions/teamplay)
                                       │
        ┌──────────────────────────────┼───────────────────────────────┐
        │ SSH poll (60s)               │ Discord webhook (~1s)          │ SSH poll (2min)
        ▼                              ▼                                ▼
  stats .txt files            lua_round_teams                  proximity .txt files
        │                              │                                │
        └──────────────┬───────────────┴────────────────┬──────────────┘
                       ▼                                  ▼
            ┌─────────────────────┐            ┌─────────────────────┐
            │   DISCORD BOT       │  shares    │   WEBSITE (FastAPI) │
            │   bot/ (Python)     │◄──────────►│   website/backend/  │
            │   100+ cmds,20 cogs │  one DB    │   + React / legacy  │
            └─────────┬───────────┘            └──────────┬──────────┘
                      │                                    │
                      └──────────────┬─────────────────────┘
                                     ▼
                          ┌──────────────────────┐
                          │   PostgreSQL (101)    │
                          │   shared by both      │
                          └──────────────────────┘
                                     ▲
                          ┌──────────┴───────────┐
                          │  GREATSHOT pipeline   │  demo → highlights → clips
                          │  greatshot/ (UDT+Py)  │
                          └──────────────────────┘
```

| Subsystem | Lives in | Language | Role |
|-----------|----------|----------|------|
| **Discord bot** | `bot/` | Python 3.11 / discord.py 2.6.4 | Ingest pipeline + 100+ commands |
| **Website backend** | `website/backend/` | FastAPI (Python) | REST API over the shared DB |
| **Website frontend** | `website/` (legacy JS) + `website/frontend/` (React) | JS / React 19 + TS 5.9 | Dashboard — **legacy JS is production**, React is the parallel migration |
| **Proximity engine** | `proximity/` | Lua (v6.10) + Python parser | Player-position teamplay analytics (30+ tables) |
| **Greatshot** | `greatshot/` | Python + UberDemoTools | Demo upload → highlight detection → clip render |
| **Game-server Lua** | `vps_scripts/` | Lua | `c0rnp0rn8.lua` (stats), `stats_discord_webhook.lua` v1.7.1 (real-time) |

**Critical mental model:** the bot and the website are **two codebases that share one
PostgreSQL database**. The website does not call the bot; it reads/writes the same tables.
The bot owns ingestion; the website owns presentation + the VISION_2026 community features
(account, planning room, seasons, betting).

---

## 3. Data Flow Pipeline

There are **two ingest paths** into the database (the bot used to have only the first):

### Path A — Stats files over SSH (the 60-second loop)

```text
Game round ends → c0rnp0rn8.lua writes  2026-06-09-213045-supply-round-1.txt
        │
        │ endstats_monitor task loop (every 60s, only while players are in voice)
        ▼
SSHHandler downloads new files → local_stats/
        │
        ▼
file_tracker dedup (SHA256 in processed_files) — skip already-imported
        │
        ▼
CommunityStatsParser — extracts 57 fields/player; R2 = cumulative, so R2_only = R2 − R1
        │
        ▼
PostgreSQL: rounds · player_comprehensive_stats · weapon_comprehensive_stats · session_teams
        │
        ▼
RoundPublisherService auto-posts the round embed to Discord
```

### Path B — Real-time Lua webhook (~1 second after round end)

```text
Round ends → stats_discord_webhook.lua (v1.7.1) POSTs a Discord webhook
        │   carries: accurate timing (fixes the surrender-duration bug), team rosters,
        │   spawn-stat array, pause events, surrender votes, Axis/Allies score
        │   (persistent retry buffer on disk if Discord is unreachable)
        ▼
Bot webhook handler (WebhookHandlerMixin / StatsReadyMixin)
        ▼
lua_round_teams (+ lua_spawn_stats), linked to a round within a 45-min window
```

### Then: correlation + proximity (the "STATS_READY" trigger)

```text
A data source arrives  →  RoundCorrelationService updates round_correlations
        │   (10 completeness flags: has_{r1,r2}_{stats,lua_teams,gametime,endstats,proximity})
        │   status → pending | complete
        ▼
STATS_READY also triggers a proximity scan → proximity_tracker.lua files imported
        ▼
round_linker resolves each row to a round via round_canonical_id
        =  sha256(round_start_unix : map_name : round_number)[:16]
        ▼
A re-linker cron fixes any NULL round_id links (back-to-back same-map matches)
```

### Pipeline stages (quick reference)

| Stage | Owner | What happens |
|-------|-------|--------------|
| 1. Generation | `vps_scripts/c0rnp0rn8.lua` | Writes `YYYY-MM-DD-HHMMSS-map-round-N.txt` |
| 2. Collection | `bot/automation/ssh_handler.py` | SSH downloads new files to `local_stats/` |
| 3. Dedup | `bot/automation/file_tracker.py` | SHA256 check vs `processed_files` |
| 4. Parse | `bot/community_stats_parser.py` | R1/R2 differential → structured dict |
| 5. Import | `bot/services/stats_import_mixin.py` | Insert rows + compute `gaming_session_id` |
| 6. Real-time | `vps_scripts/stats_discord_webhook.lua` → webhook mixins | `lua_round_teams` |
| 7. Correlate | `bot/services/round_correlation_service.py` | `round_correlations` completeness |
| 8. Proximity | `proximity/` + STATS_READY trigger | 30+ proximity tables, re-linked |
| 9. Publish | `bot/services/round_publisher_service.py` | Discord embed |
| 10. Present | `bot/cogs/*` + `website/backend/*` | Commands + REST API + web UI |

### Terminology (used everywhere — learn these)

- **ROUND** = one stats file (R1 or R2), one half of a map.
- **MATCH** = R1 + R2 together (one complete map). Identified by a `match_id`.
- **GAMING SESSION** = consecutive matches within **60-minute** gaps (`gaming_session_id`).
- **R2 differential** = Round-2 files are **cumulative** (R1+R2); the parser subtracts R1.
- **Stopwatch** = teams swap attack/defense between R1 and R2; the `team` column is the
  *side* played, not the persistent team (resolved via `session_teams` + `round_contract`).

---

## 4. Architecture Style

### Layered, modular, two-process

```text
┌──────────────────────────────────────────────────────────────┐
│ BOT PROCESS (bot/)                                            │
│  Entry        ultimate_bot.py  (composes 8 behavior mixins)   │
│  Cogs         bot/cogs/        (20 command modules)           │
│  Services     bot/services/    (39 modules: pipeline, scoring)│
│  Core         bot/core/        (20 modules: adapter, linker…) │
│  Automation   bot/automation/  (ssh_handler, file_tracker)    │
│  Repositories bot/repositories/(file_repository)              │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ WEB PROCESS (website/backend/)                                │
│  Entry        main.py          (FastAPI, ~20 routers)         │
│  Routers      routers/         (god-files split into families)│
│  Services     services/        (skill, box-score, storytelling)│
│  Adapter      local_database_adapter.py (reuses the bot's)    │
└──────────────────────────────────────────────────────────────┘
            both talk to → PostgreSQL (one shared database)
```

### Patterns used (see §10 for detail)

- **Mixin composition** — `ultimate_bot.py` inherits 8 focused mixins instead of one god-file
- **Configuration object** — `BotConfig` centralizes every setting
- **Adapter pattern** — `DatabaseAdapter` hides PostgreSQL/asyncpg behind `?`-placeholder calls
- **Repository pattern** — DB queries live behind repository methods, not inline in cogs
- **Service layer** — complex logic lives in single-responsibility service classes
- **Cog pattern** — Discord commands grouped into modular cogs
- **Router families** — large FastAPI routers split into many sub-routers (records_*, proximity_*)
- **Background tasks** — `@tasks.loop()` for SSH polling, re-linking, cache refresh

---

## 5. Component Breakdown — The Bot

### Layer 1: Entry point & configuration

#### `bot/ultimate_bot.py` (~2,116 lines)

Main bot class. **After the mega-audit it is a coordinator** that composes 8 mixins (down
from a 6,000-line god-file). It loads cogs, wires services, and runs background tasks.

The 8 composed mixins (all in `bot/services/`):

| Mixin | File | Responsibility |
|-------|------|----------------|
| `MonitorTasksMixin` | `monitor_tasks_mixin.py` | `endstats_monitor` SSH loop (60s) + grace period |
| `StatsImportMixin` | `stats_import_mixin.py` | R1/R2 import orchestration, `is_valid` gating |
| `StatsReadyMixin` | `stats_ready_mixin.py` | Lua `STATS_READY` webhook gating |
| `WebhookHandlerMixin` | `webhook_handler_mixin.py` | Incoming Lua webhook intake |
| `WebhookMetadataMixin` | `webhook_metadata_mixin.py` | Webhook → DB metadata enrichment (stale gate) |
| `EndstatsPipelineMixin` | `endstats_pipeline_mixin.py` | Endstats / canonical-id pipeline |
| `LuaRoundStorageMixin` | `lua_round_storage_mixin.py` | `lua_round_teams` row writes |
| `AdminAlertMixin` | `admin_alert_mixin.py` | `alert_admins()` + `track_error()` |

#### `bot/config.py` (~715 lines)

Centralized config. Priority: ENV → `bot_config.json` → defaults. **Reads `POSTGRES_*`
names** (`postgres_host/port/database/user/password`), `ssh_*`, `*_channel_id`, session
thresholds. (`DB_*` names are *not* read by the bot — only by `scripts/apply_migrations.py`.)

### Layer 2: Database access

#### `bot/core/database_adapter.py` (~536 lines)

Async PostgreSQL interface (asyncpg). Methods: `fetch_one`, `fetch_all`, `fetch_val`,
`execute`, `executemany`, `connection()`, and **`transaction()`** — a context manager that
binds all subsequent calls to one connection (used for `FOR UPDATE` locking, e.g. parimutuel
settlement). Auto-translates `?` placeholders → `$1, $2, …`. A SQLite fallback exists for
local/dev tooling, but production is PostgreSQL-only.

#### `postgresql_database_manager.py` (root, ~3,200 lines)

The **only** sanctioned CLI for DB administration: create, import, rebuild, validate, fix.

### Layer 3: Data-import pipeline

- `bot/community_stats_parser.py` (~1,452 lines) — parses stats files; handles the R2
  differential (R2 is cumulative; `R2_only = R2 − R1`).
- `bot/automation/ssh_handler.py` — SSH connect / list / download (used by `endstats_monitor`).
  *(Note: this is active. A separate `SSHMonitor` class was disabled for a race-condition fix;
  the live ingest is the `endstats_monitor` task loop, not `SSHMonitor`.)*
- `bot/automation/file_tracker.py` — duplicate prevention (file age → memory cache →
  `processed_files` → round existence).

### Layer 4: Services (business logic) — 39 modules

Notable ones (with line counts where large):

| Service | Purpose |
|---------|---------|
| `voice_session_service.py` (~1,102) | Detect gaming sessions via Discord voice |
| `round_publisher_service.py` (~930) | Auto-post round embeds |
| `prediction_engine.py` (~744) | 4-factor match predictions |
| `session_digest_service.py` (~302) | VISION_2026 morning digest |
| `round_correlation_service.py` | R1+R2 completeness tracking |
| `round_linkage_anomaly_service.py` | Detect linkage drift |

### Layer 5: Cogs (Discord commands) — 20 cogs, 100+ commands

`bot/cogs/`: achievements, admin, admin_predictions, analytics, automation_commands,
availability_poll, last_session, leaderboard, link, matchup, permission_management,
predictions, proximity, server_control, session, session_management, stats, sync, team,
team_management.

| Cog | Primary commands |
|-----|------------------|
| `stats_cog.py` | `!stats`, `!compare`, `!consistency`, `!playstyle`, `!map_stats` |
| `leaderboard_cog.py` | `!leaderboard` (aliases `!lb`, `!top`) |
| `last_session_cog.py` | `!last_session` (rich graphs) |
| `matchup_cog.py` | `!matchup`, `!duo_perf`, `!nemesis`, `!head_to_head` |
| `predictions_cog.py` | `!predictions`, `!prediction_stats`, `!prediction_leaderboard` |
| `link_cog.py` | `!link`, `!unlink`, `!setname`, `!myaliases` |
| `sync_cog.py` | `!sync_all`, `!sync_today`, `!sync_historical` |
| `server_control.py` | `!server_status`, `!rcon`, `!map_change`, `!list_players` |

The canonical command reference is [`docs/COMMANDS.md`](COMMANDS.md).

### Layer 6: Core utilities — 20 modules

`bot/core/`: `database_adapter`, `stats_cache` (5-min TTL), `team_manager` (team detection),
`round_canonical` (content-addressed round id), `round_contract` (stopwatch side/confidence),
`round_linker` (links Lua + stats files), `correlation_context`, `season_manager`,
`substitution_detector`, `match_tracker`, and more.

---

## 6. Component Breakdown — The Website

The website is a **separate FastAPI codebase** in `website/backend/` plus a frontend in
`website/` (legacy JS) and `website/frontend/` (React). It shares the bot's PostgreSQL DB.

### Backend

- **Entry:** `website/backend/main.py` (~475 lines) — wires CORS, GZip, sessions, rate-limit,
  HTTP cache, request logging, and registers ~20 routers.
- **Routers** (`website/backend/routers/`, ~47 files). Two large routers were **split into
  families** (god-file decomposition) — know this or you'll hunt for endpoints in the wrong file:
  - `records_router.py` → `records_*` (9 files: awards, maps, matches, overview, player, seasons, trends, weapons)
  - `proximity_router.py` → `proximity_*` (14 files: combat, competitive, dashboard, events, movement, objectives, player, positions, round, scoring, support, teamplay, trades)
  - Others: `players_router`, `sessions_router`, `skill_router`, `storytelling_router`,
    `rivalries_router`, `replay_router`, `auth`, `predictions`, `greatshot`, `uploads`,
    `availability`, `planning`, `challenges_router`, `season_awards_router`, `bets_router`,
    `diagnostics_router`.
- **DB adapter:** `local_database_adapter.py` reuses the bot's `DatabaseAdapter` (via
  `shared.database_adapter`); SQLite fallback for local dev. `get_db()` yields a shared pool.
- **Auth:** `dependencies.py` — `require_user`, `require_admin` / `require_tier(...)`, `get_db`;
  CSRF via `middleware/auth_helpers.py::require_ajax_csrf_header`. **`website_users.id` mirrors
  the Discord ID** (so the same int is both the session id and the `player_links.discord_id` join key).
  `SESSION_SECRET` and `CORS_ORIGINS` are required env vars (no defaults).
- **Services** (`website/backend/services/`): `skill_rating_service` (ET Rating),
  `box_scoring_service` (stopwatch), `season_awards_service`, `storytelling/*`,
  `website_session_data_service`, `greatshot_jobs`/`greatshot_store`/`greatshot_crossref`,
  `upload_store`/`upload_validators`.

### Frontend (two stacks, one is production)

- **Legacy JS (`website/js/`, ~36 modules) is the PRODUCTION site**, served via
  `website/index.html`. Key modules: `home.js`, `availability.js`, `hall-of-fame.js`,
  `session-detail.js`, `matches.js`, `proximity*.js`, `records.js`.
- **React (`website/frontend/src/`, 25 pages)** — React 19 + TypeScript 5.9 + Vite 7 +
  Tailwind v4. A parallel/forward migration that builds to `website/static/modern/`. Not yet
  the production runtime. **Do not run a React build as verification of legacy changes.**
- **Serving:** nginx serves static files and proxies `/api/` + `/auth/` to FastAPI. Ports:
  **dev = 8000, production/slomix_vm = 7000.**

### Two migration directories (important!)

| Dir | Applied by | Latest | Domain |
|-----|-----------|--------|--------|
| `migrations/` (root) | `scripts/apply_migrations.py` + `schema_migrations` table | ~058 | bot/core/proximity schema |
| `website/migrations/` | **manually via psql** | ~010 | website-domain (mvp votes, challenges, season awards, parimutuel) |

---

## 7. Component Breakdown — Proximity & Greatshot

### Proximity engine (`proximity/`)

Real-time teamplay analytics from a dedicated game-server Lua mod.

- `proximity/lua/proximity_tracker.lua` (**v6.10**) — samples player positions (~200ms),
  engagements, crossfire, objective events. Layered: v4 tracks/engagements → v5 teamplay
  (spawn timing, cohesion, crossfire, team push, trade kills) → v6.01 objective intelligence
  (carrier/construction/vehicle/objective-run) → v6.02 SHOT_FIRED (aim) → v6.10 dormant v7
  sections (all OFF by config).
- `proximity/parser/` — `ProximityParserV4` parses tracks + engagement records.
- **30+ database tables** (`proximity_*`, `combat_engagement`, `crossfire_pairs`).
- **Ingest:** STATS_READY trigger + a 2-minute polling loop; a re-linker cron fixes NULL
  `round_id`s.

### Greatshot demo pipeline (`greatshot/`)

Upload an ET:Legacy `.dm_84` demo on the website; the pipeline turns it into highlights:

```text
Upload → scanner/ (UberDemoTools parse → events) → highlights/ (multi-kill, spree,
         headshot detectors) → cutter/ (extract clip) → renderer/ (ffmpeg → MP4)
         orchestrated by worker/ (background queue)
```

- Entry: `greatshot/scanner/api.py`. Config: `greatshot/config.py` (timeouts, thresholds,
  UDT binary paths via `GREATSHOT_UDT_*` env).
- DB tables: `greatshot_demos`, `greatshot_analysis`, `greatshot_highlights`, `greatshot_renders`.
- Based on Kimi (mittermichal)'s greatshot-web; we built UDT from source with ET:Legacy
  protocol-84 support.

---

## 8. Execution Flows

### Flow 1: Bot startup

```text
1. main() in ultimate_bot.py
2. BotConfig() loads from .env → bot_config.json → defaults
3. create_adapter() → PostgreSQL adapter connects (pool)
4. validate_database_schema() → verify required columns exist (PCS has 57 columns; additive OK)
5. setup_hook(): load 20 cogs, init automation services, start background tasks
6. bot.run(token) → connect to Discord
```

### Flow 2: A new stats file arrives (Path A)

```text
1. endstats_monitor loop (60s) → SSH list remote files
2. New file? → download to local_stats/
3. file_tracker: already processed (SHA256)? → skip
4. CommunityStatsParser → dict (R2 differential applied)
5. stats_import_mixin → INSERT rounds / player_comprehensive_stats / weapon_*; compute gaming_session_id
6. round_correlation_service updates round_correlations
7. round_publisher_service posts the Discord embed
```

### Flow 3: A round-end webhook arrives (Path B)

```text
1. stats_discord_webhook.lua POSTs metadata to a Discord webhook (~1s after round end)
2. WebhookHandlerMixin / StatsReadyMixin parse the embed (timing, rosters, spawn stats, score)
3. LuaRoundStorageMixin writes lua_round_teams (+ lua_spawn_stats), linked within a 45-min window
4. STATS_READY triggers a proximity scan + correlation update
```

### Flow 4: `!stats playername` (Discord) / a web profile request

```text
Discord:  stats_cog → stats_cache (5-min TTL) → DatabaseAdapter → embed
Web:      players_router → DatabaseAdapter (shared pool) → JSON → legacy JS renders the profile
```

---

## 9. Design Decisions Explained

### Why a `BotConfig` class instead of scattered `os.getenv()`?

Centralizes every setting (testable, documented, validated at startup, IDE-autocompletable).
Cogs use `self.config.<property>`, never `os.getenv()` directly.

### Why compose `ultimate_bot.py` from mixins?

The entry point was once a 6,000-line god-file. The mega-audit split each behavior
(SSH monitoring, webhook intake, stats import, endstats pipeline, admin alerts…) into a
focused mixin. `ultimate_bot.py` now **coordinates**; each mixin has one responsibility and
is independently readable/testable. (Same spirit as extracting services.)

### Why the Repository pattern for DB access?

SQL lives in one place; schema changes touch one file; queries are mockable in tests.

### Why the Adapter pattern for the database?

A uniform `?`-placeholder async interface regardless of backend. The website reuses the very
same adapter, so a `transaction()` + `FOR UPDATE` pattern works identically on both sides.

### Why one shared database for bot + website?

No RPC layer, no sync lag, one source of truth. The bot owns ingestion; the website owns
presentation and community features — but both read/write the same tables. The tradeoff is
discipline: schema changes must consider both consumers, and two migration dirs exist.

---

## 10. Key Patterns & Anti-Patterns

| Pattern | Example | When to use |
|---------|---------|-------------|
| Configuration object | `BotConfig` | Centralize settings |
| Mixin composition | `ultimate_bot.py` + 8 mixins | Split a god-file by behavior |
| Repository | `FileRepository` | Abstract DB queries |
| Adapter | `DatabaseAdapter` | Uniform async DB interface |
| Service layer | `VoiceSessionService` | Complex business logic |
| Cog | `StatsCog` | Modular Discord command groups |
| Router family | `proximity_*`, `records_*` | Split a huge FastAPI router |
| Transaction + FOR UPDATE | `bets_router.settle_market` | Atomic, race-safe writes |
| Background task | `@tasks.loop()` | SSH poll, re-link, cache refresh |

| ❌ Don't | ✅ Do instead |
|----------|---------------|
| `os.getenv()` scattered in code | `self.config.property` |
| SQL in cogs | Repository / service methods |
| Add commands to `ultimate_bot.py` | New cog in `bot/cogs/` |
| Sync DB calls in async code | Always the async adapter |
| `player_name` for aggregation | Group by `player_guid` |
| Date-range session queries | `gaming_session_id` |
| Recompute the R2 differential | Trust the parser output |
| `?`/SQLite syntax assumptions | PostgreSQL (`ON CONFLICT`, not `INSERT OR REPLACE`) |
| Run a React build to verify legacy JS | Legacy JS (`website/js/`) is production |

---

## 11. Database Schema

**PostgreSQL — 101 tables** (canonical DDL: `tools/schema_postgresql.sql`; migrations in
`migrations/` + `website/migrations/`). `player_comprehensive_stats` has **57 columns**.

| Group | Count | Representative tables |
|-------|-------|-----------------------|
| **Core stats** | 7 | `rounds`, `player_comprehensive_stats` (57 cols), `weapon_comprehensive_stats`, `processed_files`, `player_links`, `player_aliases`, `session_teams` |
| **Lua webhook** | 2 | `lua_round_teams`, `lua_spawn_stats` |
| **Correlation / endstats** | 3 | `round_correlations` (10 completeness flags), `round_awards`, `round_vs_stats` |
| **Predictions** | 1 | `match_predictions` |
| **Website / identity / engagement** | ~15 | `website_users`, `user_permissions`, `player_skill_ratings`, `player_skill_history`, `session_mvp_votes`, `weekly_challenges`, `season_awards`, `user_points`, `parimutuel_markets`, `parimutuel_bets`, `availability_*` |
| **Greatshot** | 4 | `greatshot_demos`, `greatshot_analysis`, `greatshot_highlights`, `greatshot_renders` |
| **Proximity** | 30+ | `combat_engagement`, `crossfire_pairs`, `proximity_spawn_timing`, `proximity_team_cohesion`, `proximity_crossfire_opportunity`, `proximity_team_push`, `proximity_lua_trade_kill`, `proximity_carrier_*`, `proximity_hit_region*`, `player_track` |
| **Infrastructure / misc** | ~39 | planning_*, session_results, map_performance, heatmaps, voice_members, storytelling_kill_impact, audit ledgers, `schema_migrations` |

**Round identity:** `round_canonical_id = sha256(round_start_unix : map_name : round_number)[:16]`
gives a stable cross-source key; `round_linker` resolves stats/Lua/proximity rows to the same round.

---

## 12. Complete File Reference

```text
slomix_discord/
├── bot/                              # DISCORD BOT (Python)
│   ├── ultimate_bot.py               # Entry point (~2,116 lines; composes 8 mixins)
│   ├── config.py                     # BotConfig (~715 lines; reads POSTGRES_*)
│   ├── community_stats_parser.py     # Stats parser (~1,452 lines; R2 differential)
│   ├── cogs/                         # 20 command modules (100+ commands)
│   ├── core/                         # 20 modules (database_adapter, round_linker, …)
│   ├── services/                     # 39 modules (incl. the 8 *_mixin.py)
│   ├── automation/                   # ssh_handler.py, file_tracker.py
│   └── repositories/                 # file_repository.py
│
├── website/                          # WEB DASHBOARD
│   ├── backend/                      # FastAPI
│   │   ├── main.py                   # App + ~20 routers (~475 lines)
│   │   ├── routers/                  # records_* (9), proximity_* (14), auth, bets, …
│   │   ├── services/                 # skill_rating, box_scoring, season_awards, greatshot_*
│   │   ├── local_database_adapter.py # Reuses the bot's DatabaseAdapter
│   │   └── dependencies.py           # require_user / require_admin / get_db
│   ├── js/                           # 36 legacy JS modules — PRODUCTION
│   ├── frontend/src/                 # React 19 + TS 5.9 (25 pages) — parallel migration
│   └── index.html                    # Production SPA entry
│
├── proximity/                        # TEAMPLAY ANALYTICS
│   ├── lua/proximity_tracker.lua     # v6.10
│   ├── parser/                       # ProximityParserV4
│   └── schema/                       # 30+ proximity tables
│
├── greatshot/                        # DEMO HIGHLIGHT PIPELINE
│   ├── scanner/ highlights/ cutter/ renderer/ contracts/ worker/
│   └── config.py
│
├── vps_scripts/                      # GAME-SERVER LUA
│   ├── c0rnp0rn8.lua                 # Stats file generator
│   └── stats_discord_webhook.lua     # Real-time webhook (v1.7.1)
│
├── migrations/                       # Root schema migrations (apply_migrations.py)
├── website/migrations/               # Website-domain migrations (manual psql)
├── tools/schema_postgresql.sql       # Canonical DDL (101 tables)
├── postgresql_database_manager.py    # The only DB admin CLI
├── local_stats/                      # Downloaded stats files
└── docs/                             # Documentation (incl. VISION_2026.md, COMMANDS.md)
```

---

## 13. Next Steps for Learning

1. **Day 1:** This document + [`docs/VISION_2026.md`](VISION_2026.md) — understand the platform + direction
2. **Day 2:** `bot/config.py` and `bot/core/database_adapter.py` — config + DB access
3. **Day 3:** One cog (`bot/cogs/stats_cog.py`) — command flow
4. **Day 4:** `bot/community_stats_parser.py` + `stats_import_mixin.py` — ingestion + R2 differential
5. **Day 5:** `ultimate_bot.py` mixins + `monitor_tasks_mixin.py` — startup + the SSH loop
6. **Day 6:** `website/backend/main.py` + one router family (`records_*`) — the web side
7. **Day 7:** `proximity/` + `greatshot/` — the analytics and demo pipelines

**Reference docs:** [`docs/COMMANDS.md`](COMMANDS.md) · [`docs/DATA_PIPELINE.md`](DATA_PIPELINE.md) ·
[`docs/SAFETY_VALIDATION_SYSTEMS.md`](SAFETY_VALIDATION_SYSTEMS.md) ·
[`docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md`](AI_COMPREHENSIVE_SYSTEM_GUIDE.md)

---

**Questions?** Re-read the relevant section or trace the code flow. When in doubt, the
canonical sources of truth are `tools/schema_postgresql.sql` (schema), `docs/COMMANDS.md`
(commands), and the code itself — not older docs.
