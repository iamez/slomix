# 🎮 Slomix - ET:Legacy Competitive Stats Platform

> **PostgreSQL-powered real-time analytics for competitive ET:Legacy — Discord bot, web dashboard, demo highlight scanner, and game server telemetry**

[![Production Status](https://img.shields.io/badge/status-production-brightgreen)](https://github.com/iamez/slomix)
[![Version](https://img.shields.io/badge/version-1.6.0-blue)](CHANGELOG.md)
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL_17-336791)](https://www.postgresql.org/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/web-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Data Integrity](https://img.shields.io/badge/data%20integrity-6%20layers-blue)](docs/SAFETY_VALIDATION_SYSTEMS.md)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-5865F2)](https://discordpy.readthedocs.io/)

A **production-grade** Discord bot + web dashboard + demo analysis pipeline with **6-layer data validation**, **real-time Lua telemetry**, **AI match predictions**, and **demo highlight detection** for ET:Legacy game servers.

---

## 🔥 Recent Updates (April 2026)

### **⚖️ v1.6.0: Fairness Overhaul + Story Expansion (April 20-21)** 🆕

**Bayesian scoring fairness, new story panels, and a storytelling engine that's 2× faster.**

- 🧮 **Bayesian MVP Selection** (PR #76) — MVP now uses Bayesian shrinkage (C=2 prior) so late-joiners and short-sample players get regressed toward session average. No more 1-round wonders stealing MVP. Minimum 50% round eligibility, deterministic tie-breaker
- 📉 **WIS v2 — Harmonic Confidence** — Win Impact Score dampens unbalanced samples (1W/3L halved), returns 0 for all-wins or all-losses (no contrast to measure). Prevents single-match statistical noise from dominating the leaderboard
- 📊 **PWC Fairness Fix** — `max(team_kills, 1)` → `0 when team=0` eliminates 30× score inflation on zero-team-kill edge cases. 20 new unit tests for every formula edge case
- 🎬 **BOX Score Panel** (PR #78) — Stopwatch match scoring on the legacy story page with per-map breakdown, winner badges, fullhold indicators, round time display. 4 parallel Invisible Value fetches (Gravity / Space / Enabler / Lurker) with race-condition guards
- 🧠 **KIS v3 — Graduated Reinforcement** (PR #121) — UTRO-inspired 7-tier reinforcement multiplier (0.70-1.40) replaces binary bonus. Ties kill weight to actual respawn pressure at time of kill
- 🏷️ **Team Synergy "Insufficient Data" Badge** — Sessions where R1 stats are missing (crash between halves, only R2 file captured) now render an explicit amber badge explaining the gap instead of silently showing zero bars. Backend reports `defaulted_players_count` so the UI can surface correlation warnings
- ⚡ **Storytelling Performance Pass** — `asyncio.gather` across 5 synergy axes + 10 proximity metrics. Records overview, hall-of-fame, and awards endpoints batch their `resolve_display_name` lookups (360 → 36 queries). 300s HTTP cache on 14 storytelling endpoints

### **🔧 v1.5.x: Runtime Bug Sweep + Performance RCA (April 19-20)**

**Mandelbrot audit across 4 layers (ingestion → correlation → rounds → API). 14 PRs, every finding fixed.**

- 🧱 **Round Linker Robustness** — Race condition + midnight crossover handled (`round_start_unix BETWEEN` window), sanity bounds reject pre-2020 timestamps, tz-aware normalization fixes production `TypeError`, stale warnings (>1h) emit single summary instead of per-row spam (was 72/hour)
- 🔒 **Round Correlations Serialized** — `asyncio.Lock` on round_correlation_service critical section prevents the race where 4 pipeline events create duplicate rows. Migration 040 dedups existing duplicates + partial UNIQUE index
- 📦 **Schema Drift Zero** — 4 migrations consolidate 14 Python-runtime DDL tables into committed migration files. `schema_postgresql.sql` now matches live DB. Proximity `guid_canonical` columns formalized
- 🏎️ **Hot Path Indexes** — `idx_player_aliases_alias_lower` (functional btree for ILIKE/LOWER prefix queries) + composite `idx_kis_session_killer`. Autocomplete query time 50ms → <1ms
- 🔁 **Parser Reconnect Threshold** — R2-raw fallback triggers on 1 dropped field (was 2), recovers single-field network glitches during differential calculation

### **🛡️ v1.5.0: Security, Performance & Session Detail 2.0 (April 17)**

- 🔐 **Sprint 2 Security** (PR #80) — New `require_admin_user` FastAPI dependency: 10/11 diagnostics endpoints now require admin session (11th stays public as health check). `strip_et_colors()` centralized in `api_helpers` — covers 10+ consumer routers (records, proximity_*, greatshot_topshots). Discord ID masked at INFO log level (`1234****`); full ID+username moved to DEBUG only
- 🎯 **Session Detail 2.0 Matrix** (PR #79) — Player × Map grid with per-round team assignment. Handles stopwatch side swaps (R1 attack = R2 defense — same player in same team cell across maps) + mid-session substitutions (player on both teams appears in both rosters, stats split by rounds). Backend `build_team_matrix()` with majority-vote side-to-team mapping; React component (3 metrics) + legacy JS (7 metrics, heatmap, drill-down, MVP★/sub⚠ badges)
- 🗓️ **Date Bounds Validation** — `storytelling_router._parse_date` rejects dates outside `[2020-01-01, today]` (DoS mitigation on large-interval queries)
- 📊 **Session Matrix Infrastructure** — `round_correlation_service` auto-merges drifted R1/R2 correlations (bot restart no longer orphans data); `stopwatch_scoring_service.build_round_side_to_team_mapping()` with tri-format side normalization (int / string / faction name)

### **🧬 Mandelbrot RCA v2.0 + Oksii Adoption (March 29-30)**

**6-phase audit framework with quantitative metrics: hardcoded creds=0, silent exceptions=0 in critical path, god files (>3000 lines)=0, ruff 2257→0 errors.**

- 🩹 **Oksii Lua v6.01** — `killer_health`, `alive_count`, reinforcement timing. KIS v2 formula with 3 new multipliers (health, alive, reinf) + soft cap at 5.0
- 🏅 **BOX Scoring** — Oksii-style stopwatch map scoring (`box_scoring_service.py`) — per-round win/fullhold points
- 🧱 **God File Decomposition** — `proximity_router.py` 5515 → 14 sub-routers, `records_router.py` 3172 → 10 sub-routers
- 🧹 **Code Quality** — Shared constants in `et_constants.py` (KILL_MOD_NAMES, color strip, weapon names), 23 silent `except: pass` → proper logging, `_compute_locks` memory leak → `BoundedLockDict` (max 64, LRU)
- 📖 **Storytelling Evolution** — Gravity metric, space-created metric, enabler score, lurker profile, invisible value per-player micro-narratives
- 🗺️ **Proximity Pipeline** — STATS_READY webhook + re-linker + 2min polling eliminates 60% of historical linkage failures
- 🧪 **Tests** — 101 new unit tests (476 → 540), end-to-end verified with bots (33 rounds, 2781 positions)

### **🎬 v1.5.0: Round Replay Timeline, Momentum Chart & Codacy Zero (March 28)**

**Visual round analysis, momentum tracking, session narratives, and full Codacy compliance — 53 commits, 58 issues → 0.**

- 🎬 **Round Replay Timeline** (`/#/replay`) — Dual-pane viewer with event feed + 2D map canvas + scrubber. 420+ events per round, player positions from `player_track.path` JSONB (200ms precision). 3 new API endpoints
- 📈 **Momentum Chart** — 30-second window momentum with 0.85 decay, Canvas 2D dual-line chart (Axis vs Allies), per-round tabs
- 📝 **Session Narrative** — Auto-generated paragraph summarizing MVP, archetype, defining moment, team synergy comparison
- ⚡ **11 Moment Detectors** (was 5) — Added team wipe (5★), multikill (2-5★), objective secured/denied/run, multi-revive. Rich kill-by-kill context with 35-weapon mapping
- 🎯 **Objective-Focused Moments** — Carrier interception chains, contested engineer builds, dynamite defuses
- 🛡️ **58 Codacy Issues → 0** — 22 CRITICAL XSS (innerHTML → DOM API), 12 HIGH TypeScript, 7 SQL injection (f-string → whitelists), protocol stubs, stack trace exposure, url-redirect validation. Zero suppressions. CI: 9/9 checks green
- 🐛 **Bug Fixes** — MomentumChart non-null guard, rivalries double `/api/api/` prefix, narrative `gaming_session_id` query fix, `PUSH_MULTIPLIER` import removed, restored `gaming_sessions` diagnostic query

### **⚔️ v1.4.0: Player Rivalries, Win Contribution & Smart Stats Phase 2 (March 27)**

- ⚔️ Player Rivalries — H2H stats, nemesis/prey/rival classification, weapon breakdown, per-map drill-down, rivalry leaderboard at `/#/rivalries`
- 🏆 Win Contribution (PWC/WIS/WAA) — 5-component formula, dynamic weight redistribution, MVP detection
- 🧠 Smart Stats Phase 2 — 11 moment detectors with rich per-kill context, 9 player archetypes, 35-weapon mapping
- 🔬 Mandelbrot Audit — 45 findings, 45 resolved

### **🧠 v1.3.0: Smart Storytelling Stats, Proximity Pipeline & Deep RCA (March 26-27)**

- Kill Impact Score (7 context multipliers), 5 moment detectors, Team Synergy Score (5-axis), Proximity STATS_READY pipeline redesign, 45-finding audit with 100% resolution

### **📊 v1.1.0: Stats Accuracy Audit, React 19 Frontend & Proximity v5 (March 2026)**

- Full stats accuracy audit, R0 double-counting fix, React 19 + TypeScript 5.9, Proximity v5.0, ET Rating system

**[📖 Full Changelog](CHANGELOG.md)**

---

## ✨ What Makes This Special

- 🎬 **Round Replay Timeline** — Dual-pane viewer: event feed + 2D map canvas + scrubber, 420+ events per round, player positions at 200ms precision
- 🧠 **Smart Storytelling** — Kill Impact Score (7 multipliers), 11 moment detectors, 9 player archetypes, auto-generated session narratives
- ⚖️ **Bayesian MVP + WIS v2** — Fairness-first scoring with shrinkage prior and harmonic confidence weighting; late-joiners don't steal MVP
- 🎯 **Proximity Teamplay Analytics** — Lua v6.01 telemetry: engagements, crossfire, cohesion, trade kills, spawn timing, objective intelligence
- ⚔️ **Player Rivalries** — H2H stats, nemesis/prey classification, per-map drill-down, rivalry leaderboard
- 📈 **ET Rating System** — 9-metric percentile skill rating with per-session drill-down and confidence indicator
- 🔮 **AI Match Predictions** — 4-factor algorithm (H2H, form, map performance, substitutions) with auto voice-channel detection
- 🎬 **Demo Highlight Scanner** — Upload demos, detect multi-kills/sprees, cut clips, ready-to-render highlights
- 🔒 **6-Layer Data Integrity** — Transaction safety, ACID guarantees, per-insert verification, schema drift zero
- 🤖 **Full Automation** — SSH monitoring, auto-download, auto-import, auto-post (60s cycle) + real-time Lua webhook (~3s latency)

**[📊 Data Pipeline](docs/DATA_PIPELINE.md)** | **[🔒 Safety & Validation](docs/SAFETY_VALIDATION_SYSTEMS.md)** | **[📖 Changelog](CHANGELOG.md)**

---

## 📈 Production Numbers

| Metric | Value |
|--------|-------|
| **Kills Tracked** | 176,911 |
| **Headshot Kills** | 36,811 |
| **Damage Dealt** | 34.4 million |
| **Revives Given** | 15,111 |
| **Rounds Parsed** | 2,258 |
| **Unique Players** | 57 |
| **Stats Per Player Per Round** | 57 fields |
| **Discord Commands** | ~99 across 20 cogs |
| **Database Tables** | 95 (managed via committed SQL migrations) |
| **Test Coverage** | 530 tests, 9/9 CI green |
| **Data Span** | Jan 2025 — Apr 2026 (16 months) |

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
│                  │  95 Tables    │                             │
│                  └───────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

| Project | Status | Description |
|---------|--------|-------------|
| **Discord Bot** (this repo) | ✅ Production | ~99 commands, 20 cogs, full automation, AI predictions |
| **Website** (`/website/`) | ✅ Production | FastAPI + React 19/TypeScript SPA: profiles, sessions, leaderboards, proximity, greatshot |
| **Lua Webhook** (`vps_scripts/`) | ✅ Production | Real-time round notifications, surrender timing fix, team capture |
| **Greatshot** (`/greatshot/`) | ✅ Production | Demo upload, highlight detection, clip extraction, render pipeline |
| **Proximity** (`/proximity/`) | ✅ Production | Lua v6.01+ teamplay analytics — engagement, cohesion, crossfire, trade kills, objective intelligence, Oksii-adopted fields (killer_health, alive_count, reinf timing) |

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
│  95 tables  |  57 columns per player per round    │
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

**Security:** Zero `innerHTML` in new code — all dynamic content uses DOM API (`createElement` + `textContent`). 58 Codacy issues resolved with zero suppressions.

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

### **🎬 Round Replay Timeline** 🆕

Relive every round with a full event replay viewer:

- 🎥 **Dual-Pane Viewer** (`/#/replay`) — Event feed on the left, 2D map canvas on the right, synchronized scrubber bar
- 📍 **Player Positions** — Sourced from `player_track.path` JSONB at 200ms precision — see exactly where every player was at every moment
- ⚡ **420+ Events Per Round** — Kills, deaths, revives, objectives, team actions rendered on an interactive timeline
- 🗺️ **2D Map Canvas** — ET:Legacy map overlay with real-time player position dots and event markers
- 🔌 **3 API Endpoints** — Round event feed, player track positions, round metadata

---

### **🧠 Smart Storytelling Stats** 🆕

Transform raw numbers into compelling competitive narratives:

- 💥 **Kill Impact Score (KIS)** — Contextual kill scoring with 7 multipliers: carrier kills (3-5x), push kills (2x), crossfire (1.5x), spawn timing (1-2x), outcome weight, class bonus, distance factor
- 🎭 **9 Player Archetypes** — Server-side classification using DPM + denied_time + headshot% + KD + trades + revives: Pressure Engine, Medic Anchor, Silent Assassin, Objective Demon, Trade Specialist, Support Fortress, Flanker, All-Rounder, Wildcard
- ⚡ **11 Match Moment Detectors** — Team wipe, multikill, kill streak, carrier chain, focus survival, push success, trade chain, objective secured, objective denied, objective run, multi-revive — each with per-kill breakdown (weapon names, timestamps, duration)
- 📈 **Momentum Chart** — 30-second window momentum scoring with 0.85 decay factor, Canvas 2D dual-line chart (Axis vs Allies), per-round tab navigation
- 📝 **Session Narrative** — Auto-generated paragraph summarizing MVP, player archetype, defining moment, and team synergy comparison
- 🤝 **Team Synergy Score** — 5-axis per-faction comparison: crossfire rate, trade coverage, cohesion quality, push success, medic bonds
- 🔫 **35-Weapon Name Mapping** — Full ET:Legacy weapon name lookup across all moment and archetype displays
- 🎬 **Legacy Story Page** — Cinematic hero, player story cards, moment timeline, KIS breakdown bars, synergy panel at `/#/story`
- 🗄️ **Backend** — `storytelling_kill_impact` DB table, 4 API endpoints, full data access pipeline

---

### **⚔️ Player Rivalries** 🆕

Deep head-to-head competitive intelligence between any two players:

- 📊 **H2H Stats** — Kills, deaths, KD ratio, accuracy, DPM head-to-head for any player pair
- 🏷️ **Nemesis / Prey / Rival Classification** — Automatically determined from win rate and encounter count
- 🔫 **Weapon Breakdown** — Which weapons each player uses most in this specific matchup
- 🗺️ **Per-Map H2H Drill-Down** — See how the rivalry plays out map by map
- 🏆 **Rivalry Leaderboard** — Top rivalry pairs ranked by total encounters
- 🌐 **Dedicated Page** — Full rivalry dashboard at `/#/rivalries`

---

### **🏆 Win Contribution (PWC / WIS / WAA)** 🆕

Quantify exactly how much each player contributed to a round win:

- 📐 **Per-Round Win Contribution (PWC)** — 5-component formula: kills, damage dealt, objectives secured, revives given, survival time
- ⚖️ **Dynamic Weight Redistribution** — When a round has zero objectives, objective weight redistributes automatically to kills and damage
- 📈 **Win Impact Score (WIS)** — avg(PWC in won rounds) − avg(PWC in lost rounds): who actually moves the needle
- 🥇 **MVP Detection** — Highest WIS player flagged as MVP per session
- 📊 **Stacked Bar Visualization** — Per-component breakdown bars for every player in every round

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

### **⚔️ Matchups, Rivalries & Predictions**
`!matchup A vs B` · `!duo_perf p1 p2` · `!nemesis` · `!rivalry <p1> <p2>` · `!rivalry_leaderboard` · `!predictions` · `!prediction_stats` · `!prediction_trends` · `!prediction_leaderboard`

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
│   ├── cogs/                        # 20 command modules
│   │   ├── last_session_cog.py      # Session stats & summaries
│   │   ├── leaderboard_cog.py       # Rankings
│   │   ├── analytics_cog.py         # Player analytics
│   │   ├── matchup_cog.py           # Matchup analytics
│   │   ├── predictions_cog.py       # AI predictions (7 commands)
│   │   ├── admin_predictions_cog.py # Prediction admin (5 commands)
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
| `bot/ultimate_bot.py` | Main entry point, SSH monitor, 20 cog loader |
| `bot/community_stats_parser.py` | R1/R2 differential parser (53+ fields) |
| `postgresql_database_manager.py` | All DB operations: create, import, rebuild, validate |
| `bot/core/database_adapter.py` | Async PostgreSQL adapter with connection pooling |
| `bot/services/prediction_engine.py` | AI match prediction engine (4-factor algorithm) |
| `website/backend/main.py` | FastAPI app with auth, routers, greatshot job workers |
| `greatshot/scanner/api.py` | Demo analysis entry point (UDT → events → highlights) |
| `vps_scripts/stats_discord_webhook.lua` | Game server Lua script (v1.6.2) |

---

## 🗄️ Database Schema

### **PostgreSQL — 95 Tables**

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
