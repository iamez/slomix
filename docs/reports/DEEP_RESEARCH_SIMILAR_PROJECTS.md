# Deep Research: Similar Projects to Slomix

> **Generated**: 2026-02-23 | **Purpose**: Competitive landscape & architectural inspiration
> **Scope**: Open-source projects with architecture patterns similar to Slomix's full-stack game community platform

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Tier 1 — Closest Architectural Matches](#tier-1--closest-architectural-matches)
3. [Tier 2 — Strong Partial Matches](#tier-2--strong-partial-matches)
4. [Tier 3 — Single-Component Matches](#tier-3--single-component-matches)
5. [Tier 4 — Game Server Management Platforms](#tier-4--game-server-management-platforms)
6. [Tier 5 — ET:Legacy Ecosystem](#tier-5--etlegacy-ecosystem)
7. [Component-by-Component Comparison Matrix](#component-by-component-comparison-matrix)
8. [What Slomix Can Learn](#what-slomix-can-learn)
9. [What Slomix Does Better](#what-slomix-does-better)
10. [Conclusions](#conclusions)

---

## Executive Summary

After searching 20+ queries across GitHub, web resources, and project documentation, the conclusion is clear: **no single open-source project replicates the full Slomix architecture**. Slomix is unique in combining all 10 of its architectural components (Lua game mod → SSH monitor → stats parser → PostgreSQL → Discord bot → FastAPI website → voice automation → proximity tracking → round correlation → systemd services) into one cohesive system.

The closest matches are **OpenDota** (microservice data pipeline + web dashboard for Dota 2) and **XonStat** (game stats ingestion + web dashboard for Xonotic/Quake Live), but neither includes Discord integration, voice channel automation, or the SSH-based file monitoring pattern.

Most projects cover 2-3 of Slomix's components. The game community space is fragmented — you typically need to stitch together separate tools for server management, stats tracking, Discord integration, and web dashboards.

---

## Tier 1 — Closest Architectural Matches

These projects share the most DNA with Slomix's end-to-end architecture.

### 1. OpenDota (odota/core)

- **URL**: https://github.com/odota/core
- **Stack**: Node.js, PostgreSQL, Redis, Cassandra, Java (replay parser)
- **License**: MIT
- **Stars**: ~1.5k

**Architecture:**
OpenDota is a microservice-based platform for Dota 2 stats:
- **Retriever** → HTTP service that interfaces with Steam Game Coordinator to fetch replay URLs
- **Parser** → Downloads `.dem.bz2` replay files, streams through Java parser (clarity), emits newline-delimited JSON events
- **Worker** → Background task processor, rebuilds player sets, manages state in Redis
- **Web API** → RESTful API serving match/player/hero data
- **Web UI** → React frontend with charts, player profiles, match details

**Similarity to Slomix:**
| Slomix Component | OpenDota Equivalent |
|---|---|
| SSH File Monitor | Retriever service (fetches replays from Steam) |
| Stats Parser | Java replay parser (clarity) |
| PostgreSQL DB | PostgreSQL + Redis + Cassandra |
| FastAPI Website | Express.js API + React frontend |
| Round Correlation | Match reconstruction from replay events |

**What Slomix Can Learn:**
- Microservice separation for scalability (parser can scale independently)
- Redis as intermediate cache/queue between services
- Cassandra for archival storage of high-volume data (could help with old stats)
- Public API documentation strategy

**What Slomix Does Better:**
- Discord bot integration (OpenDota has none)
- Voice channel automation (unique to Slomix)
- Real-time Lua webhook ingestion (OpenDota polls Steam API, doesn't have in-game hooks)
- Proximity/heatmap system (no spatial tracking in OpenDota)
- Single-stack simplicity (Python everywhere vs. Node+Java+multiple databases)

---

### 2. XonStat (Xonotic Stats)

- **URL**: https://github.com/xonotic/xonstat | https://gitlab.com/xonotic/xonstat-go
- **Stack**: Python (Pyramid), PostgreSQL, Nginx; also a Go rewrite (xonstat-go)
- **License**: AGPLv3
- **Live**: https://stats.xonotic.org/

**Architecture:**
XonStat handles the ingestion and presentation of match statistics for Xonotic (a Quake-family FPS):
- **Feeder** → Node.js processes that connect to game servers via ZeroMQ and ingest real-time stats
- **Web Application** → Python Pyramid app with PostgreSQL backend
- **Nginx** → Reverse proxy with SSL, dispatches to backend
- **Database** → PostgreSQL storing players, games, maps, weapons, servers

The system was later forked by PredatH0r as **QLStats** (https://qlstats.net/) for Quake Live, demonstrating the architecture's flexibility.

**Similarity to Slomix:**
| Slomix Component | XonStat Equivalent |
|---|---|
| Lua Webhook | ZeroMQ feeder from game server |
| Stats Parser | Event processing in feeder/web app |
| PostgreSQL DB | PostgreSQL |
| FastAPI Website | Pyramid web application |
| Leaderboards/Stats | Web dashboard with rankings, player profiles |

**What Slomix Can Learn:**
- ZeroMQ for real-time push-based stats (vs. SSH polling)
- The Go rewrite (xonstat-go) shows performance scaling path
- Mature Quake-family stats schema design
- Map image/thumbnail system for web display

**What Slomix Does Better:**
- Discord bot with 80+ commands (XonStat is web-only)
- Voice channel automation
- Session tracking with 60-minute gap detection
- R1/R2 differential parsing (XonStat gets clean per-round data)
- Achievement system, predictions, team management
- Proximity/heatmap tracking

---

### 3. QuakeStats (brabiega/quakestats)

- **URL**: https://github.com/brabiega/quakestats
- **Stack**: Python 3.6+, Flask, MongoDB, Twisted
- **License**: MIT
- **PyPI**: `pip install quakestats`

**Architecture:**
- Processes Quake 3 Arena logs OR Quake Live ZeroMQ event streams
- Translates Q3 logs into QL-compatible events for unified processing
- Stores matches in MongoDB
- Flask web application with charts and custom medals
- Admin system for map configuration

**Similarity to Slomix:**
| Slomix Component | QuakeStats Equivalent |
|---|---|
| Stats Parser | Log parser + event translator |
| Database | MongoDB |
| FastAPI Website | Flask web app with charts |
| Achievements | Custom medal system |

**What Slomix Can Learn:**
- Log format translation layer (Q3→QL event normalization)
- Medal/achievement visualization approach
- PyPI packaging for distribution

**What Slomix Does Better:**
- PostgreSQL (relational, better for complex queries) vs. MongoDB
- Discord integration
- Real-time monitoring (SSH + Lua webhook)
- Session/match/round hierarchy
- 56-field per-player stat depth
- Voice automation, proximity, predictions

---

## Tier 2 — Strong Partial Matches

These projects match 3-5 Slomix components significantly.

### 4. CS2 Rank (Salvatore-Als/cs2-rank)

- **URL**: https://github.com/Salvatore-Als/cs2-rank
- **Stack**: C# (game plugin via CounterStrikeSharp), Node.js (API + Discord bot), PHP (web panel), MySQL
- **License**: GPL-3.0

**Architecture:**
- **Game Plugin** (C#) → Runs inside CS2 server, tracks kills/deaths/events, writes to MySQL
- **API** (Node.js) → REST endpoints for player stats, rankings, map data
- **Discord Bot** (Node.js) → Player rank lookup, global/map rankings
- **Web Panel** (PHP) → Top rankings, player profiles

**Similarity to Slomix:**
This is the closest match for the "game mod → database → Discord bot + website" pattern:
| Slomix Component | CS2 Rank Equivalent |
|---|---|
| Lua Game Mod | C# game plugin (CounterStrikeSharp) |
| PostgreSQL DB | MySQL |
| Discord Bot | Node.js Discord bot |
| FastAPI Website | PHP web panel + Node.js API |

**What Slomix Can Learn:**
- Cross-server ranking via "rank referencing"
- Separate API layer between database and consumers
- Per-map statistics breakdown

**What Slomix Does Better:**
- Far deeper stat tracking (56 fields vs. basic K/D/points)
- Session tracking, round correlation, R1/R2 differential
- Voice channel automation
- Achievement system, predictions, availability polls
- Single language stack (Python) vs. C# + Node.js + PHP
- Proximity/heatmap system

---

### 5. DODS Match Stats (evandrosouza89/dods-match-stats)

- **URL**: https://github.com/evandrosouza89/dods-match-stats
- **Stack**: Java, MySQL, Docker
- **License**: MIT

**Architecture:**
- Receives HL Log Standard events from Day of Defeat: Source server
- Parses game events in real-time to detect match start/end
- Calculates team scores and individual player statistics
- Only stores valid/complete matches in MySQL
- Dockerized deployment

**Similarity to Slomix:**
| Slomix Component | DODS Equivalent |
|---|---|
| Stats Parser | HL Log Standard event parser |
| Round Correlation | Match validity detection |
| PostgreSQL DB | MySQL |
| Systemd Services | Docker containers |

**What Slomix Can Learn:**
- Match validity detection (only store complete matches)
- Docker-based deployment strategy
- HL Log Standard as reference for event parsing design

**What Slomix Does Better:**
- Everything beyond parsing (Discord bot, website, voice automation, etc.)
- Much deeper stat granularity
- Multiple data source correlation (gamestats, gametimes, endstats, Lua webhooks)

---

### 6. DiscordGSM (GameServerMonitor)

- **URL**: https://github.com/DiscordGSM/GameServerMonitor
- **Stack**: Python, discord.py, Docker
- **License**: MIT
- **Stars**: ~300+

**Architecture:**
- Discord bot that polls game servers using various query protocols
- Supports 260+ games via modular protocol handlers
- Displays live server status in Discord embeds
- Tracks player counts, map rotations, uptime
- Docker deployment with web configuration

**Similarity to Slomix:**
| Slomix Component | DiscordGSM Equivalent |
|---|---|
| Discord Bot | Discord bot (server status focus) |
| Server Monitoring | Game server query/polling |
| Systemd Services | Docker deployment |

**What Slomix Can Learn:**
- Protocol-agnostic server query architecture (supports 260+ games)
- Public bot model with per-guild configuration
- Docker-based deployment

**What Slomix Does Better:**
- Deep stats parsing (DiscordGSM only shows live status, no historical stats)
- Website/dashboard
- Voice channel automation
- Achievement system, predictions, session tracking
- Lua game mod integration
- Everything related to data pipeline and analytics

---

### 7. ActionFPS (game-log-parser)

- **URL**: https://github.com/ActionFPS/game-log-parser
- **Stack**: Scala, Play Framework, Akka, PHP
- **Live**: https://actionfps.com/view-stats

**Architecture:**
- Syslog listener receives UDP log messages from AssaultCube servers
- Parses timestamped TSV log lines into structured game events
- Reconstructs games from raw log lines (no native game data format)
- Web application for stats display
- Functional streaming (Scala FS2) for real-time processing

**Similarity to Slomix:**
| Slomix Component | ActionFPS Equivalent |
|---|---|
| SSH Monitor | Syslog UDP listener |
| Stats Parser | Log line → game reconstruction |
| Round Correlation | Game boundary detection from logs |
| Website | Play Framework web app |

**What Slomix Can Learn:**
- Syslog-based real-time log ingestion (vs. SSH polling — lower latency)
- Functional streaming for event processing
- Game reconstruction from raw server logs

**What Slomix Does Better:**
- Discord integration
- Database depth (68 tables vs. simpler schema)
- Voice automation, proximity, predictions, achievements
- Multi-source data correlation

---

## Tier 3 — Single-Component Matches

These projects match 1-2 Slomix components strongly.

### 8. Polly (pacnpal/polly)

- **URL**: https://github.com/pacnpal/polly
- **Stack**: Python, FastAPI, discord.py, HTMX, SQLite
- **License**: MIT

**Architecture:**
- Discord poll bot with admin-only access
- Web dashboard built with FastAPI + HTMX
- Scheduled polls with cron-like scheduling
- Single application deployment

**Similarity to Slomix:** Discord bot + FastAPI website in single Python app (same stack pattern)

**What Slomix Can Learn:**
- HTMX for dynamic UI without JavaScript complexity
- Single-process deployment combining bot + web server
- Scheduled poll patterns

---

### 9. Valorant Stats Bots (various)

- **valorant-stats** (brandon-vo): https://github.com/brandon-vo/valorant-stats — Discord.js + MongoDB
- **VALWATCH** (shaheriar): https://github.com/shaheriar/VALWATCH — Valorant Stats Tracker
- **Radiant**: https://radiantbot.github.io/ — Agent guides, weapon stats, skins, map plans

**Similarity to Slomix:** Discord bots for FPS game stats lookup. None have their own data pipeline — they all query third-party APIs (tracker.gg, Henrik API).

**What Slomix Does Better:** Slomix owns its entire data pipeline end-to-end, from game server to database, giving it full control and no dependency on third-party APIs.

---

### 10. CS:GO/CS2 Discord Bots

- **CounterStrikeBot**: https://github.com/yoinc-development/CounterStrikeBot — Server changes and stat requests
- **CSGO-Bot**: https://github.com/thomson008/CSGO-Bot — Python, Discord.py, Steam API stats
- **CS2 Discord Utilities**: https://github.com/NockyCZ/CS2-Discord-Utilities — Bridge between CS2 server and Discord

**Similarity to Slomix:** Game-specific Discord bots with stat lookup. CS2 Discord Utilities is interesting for its direct game server ↔ Discord bridge pattern.

---

### 11. Chess Pipeline (guidopetri/chess-pipeline)

- **URL**: https://github.com/charlesoblack/chess-pipeline
- **Stack**: Python, PostgreSQL, Lichess API

**Architecture:**
- Pulls games from Lichess API
- Parses into game_clocks, game_evals, game_moves tables
- PostgreSQL storage for analysis

**Similarity to Slomix:** Data pipeline pattern (API → parse → PostgreSQL) mirrors SSH monitor → parser → database.

---

### 12. Game Analytics Heatmap Tools

- **UE4 Gameplay Analytics**: https://github.com/Andze/UE4-GamePlay-Analytics — OpenGL heatmap visualization
- **Soccermatics**: https://github.com/JoGall/soccermatics — Spatial tracking visualization for football
- **libheatmap**: https://github.com/lucasb-eyer/libheatmap — C library created for DOTA2 player position heatmaps

**Similarity to Slomix:** Proximity/heatmap visualization. These are standalone visualization tools — Slomix's proximity system is unique in combining Lua position tracking → database → analysis in one pipeline.

---

## Tier 4 — Game Server Management Platforms

These are not stats platforms but share infrastructure patterns with Slomix.

### 13. Pterodactyl Panel

- **URL**: https://github.com/pterodactyl/panel
- **Stack**: PHP (Laravel), React, Go (Wings daemon)
- **Stars**: ~6.5k+

**Architecture:**
- Web panel for managing game servers
- Wings daemon runs on each node, manages Docker containers
- API-first design
- User/permission management

**Relevance:** Infrastructure pattern for managing game servers. Slomix's server_control cog provides a simpler, Discord-native version of game server management.

---

### 14. Azuriom

- **URL**: https://github.com/Azuriom/Azuriom
- **Stack**: PHP (Laravel), MySQL
- **Stars**: ~800+

**Architecture:**
- Complete game community CMS
- Plugin/theme marketplace
- Shop, forum, and game server integration
- Supports Minecraft, Garry's Mod, Rust, and more

**Relevance:** Community platform pattern. Azuriom focuses on CMS features (shop, forum, permissions) while Slomix focuses on deep stats analytics.

---

### 15. Eventula Manager

- **URL**: https://github.com/Lan2Play/eventula-manager
- **Stack**: PHP (Laravel), Docker

**Architecture:**
- LAN party event management (venue, seating, tickets)
- Tournament system (single/double elimination, round robin)
- RCON integration for game server management
- Automated matchmaking for CS:GO (Get5)
- Credit/shop system

**Relevance:** Tournament management and RCON integration patterns could inspire Slomix's competitive features.

---

### 16. LANager

- **URL**: https://github.com/zeropingheroes/lanager
- **Stack**: PHP (Laravel)

**Architecture:**
- LAN party management web app
- Events, guides, user profiles
- Game library integration

**Relevance:** Community event management pattern.

---

## Tier 5 — ET:Legacy Ecosystem

Projects specifically in the Wolfenstein: Enemy Territory / ET:Legacy ecosystem.

### 17. WolfAdmin

- **URL**: https://github.com/etlegacy/wolfadmin
- **Stack**: Lua (runs inside ET:Legacy server)
- **Author**: timosmit

**Architecture:**
- Lua module loaded by ET:Legacy server
- Admin commands, team balancing, player data logging
- Custom voting system
- Runs entirely server-side

**Similarity to Slomix:** WolfAdmin is the closest ET:Legacy-specific tool. Slomix's `stats_discord_webhook.lua` operates in the same environment (ET:Legacy Lua scripting), but focuses on stats emission rather than server administration.

**Relationship:** Complementary — WolfAdmin handles in-game admin, Slomix handles external stats pipeline.

---

### 18. Trackbase (et.trackbase.net)

- **URL**: https://et.trackbase.net/
- **Stack**: Unknown (closed source web service)

**Architecture:**
- Multi-game server tracker
- Player statistics and server monitoring
- Web-based player search and rankings
- Server browser

**Similarity to Slomix:** Both track ET player statistics. Trackbase is a centralized service; Slomix is self-hosted and community-specific.

**What Slomix Does Better:** Self-hosted, Discord-integrated, deeper per-round analytics, session tracking, voice automation.

---

### 19. SourceBans++ (sbpp/sourcebans-pp)

- **URL**: https://github.com/sbpp/sourcebans-pp
- **Stack**: PHP, MySQL, SourceMod plugin

**Architecture:**
- Admin/ban management for Source engine games
- In-game plugin reports bans to web panel
- Cross-server ban synchronization
- Web-based admin interface

**Relevance:** The "game plugin → database → web panel" pattern is similar to Slomix's "Lua mod → PostgreSQL → web dashboard." SourceBans focuses on moderation, Slomix on statistics.

---

## Component-by-Component Comparison Matrix

| Slomix Component | Best Match | Runner-Up | Unique to Slomix? |
|---|---|---|---|
| **Lua Game Mod** (stats webhook) | WolfAdmin (same environment) | CS2 Rank plugin | Partially — stats emission + denied playtime tracking is unique |
| **SSH File Monitor** (60s poll) | ActionFPS syslog listener | OpenDota retriever | Yes — SSH-based file polling pattern is rare |
| **Custom Stats Parser** (R1/R2 differential) | QuakeStats log parser | DODS Match Stats | Yes — R2 cumulative differential parsing is unique |
| **PostgreSQL Database** (68 tables) | OpenDota (PostgreSQL+Redis+Cassandra) | XonStat (PostgreSQL) | Partially — 68-table depth is exceptional |
| **Discord Bot** (21 cogs, 80+ commands) | DiscordGSM | CS2 Rank Discord bot | Yes — no other game stats bot has this command breadth |
| **FastAPI Website** | Polly (FastAPI+discord.py) | XonStat (Pyramid) | No — common pattern |
| **Voice Channel Automation** | VoiceMaster (temp channels) | None | Yes — voice→server monitoring trigger is unique |
| **Proximity System** (Lua positions→heatmaps) | libheatmap (DOTA2 positions) | UE4 Gameplay Analytics | Yes — integrated Lua→DB→analysis pipeline is unique |
| **Round Correlation Service** | OpenDota match reconstruction | ActionFPS game boundary detection | Yes — multi-source correlation (gamestats+gametimes+endstats+Lua) is unique |
| **Systemd Services** | Pterodactyl (Docker) | Various | No — common deployment pattern |

---

## What Slomix Can Learn

### From OpenDota
1. **Microservice separation** — Parser, retriever, worker, and web as independent services. Could help Slomix scale the parser independently.
2. **Redis as message queue** — Between SSH monitor and parser, Redis could provide better reliability than in-process queuing.
3. **Cassandra for archival** — Old match data could move to a time-series store for better query performance on hot data.
4. **Public API** — OpenDota's well-documented API enables community tools.

### From XonStat
1. **ZeroMQ for real-time stats** — Push-based ingestion instead of SSH polling could reduce latency from 60s to near-instant.
2. **Go rewrite path** — The xonstat-go project shows how to scale a Python stats platform with Go for hot paths.
3. **Map thumbnails** — Web display of map images alongside stats.

### From CS2 Rank
1. **Separate API layer** — Clean REST API between database and all consumers (bot, web, external tools).
2. **Per-map statistics** — Dedicated map-level breakdowns and rankings.
3. **Cross-server ranking** — "Rank referencing" for multi-server communities.

### From Pterodactyl/Azuriom
1. **Docker deployment** — Containerized deployment for easier setup/migration.
2. **Plugin/extension marketplace** — Could enable community contributions (custom stat views, new cog modules).

### From ActionFPS
1. **Syslog-based ingestion** — Lower latency than SSH polling.
2. **Functional streaming** — Stream processing for real-time event handling.

### From Eventula
1. **Tournament bracket system** — Could extend Slomix's team management with bracket/elimination tracking.
2. **RCON integration** — Direct game server control from the platform.

### From DODS Match Stats
1. **Match validity detection** — Only store complete/valid matches.
2. **Docker-first deployment** — Reproducible setup.

---

## What Slomix Does Better

### 1. End-to-End Integration (Unique)
No other project combines ALL of: game mod → file monitoring → stats parsing → database → Discord bot → web dashboard → voice automation → proximity tracking → round correlation in a single system. Every competitor requires stitching together 3-5 separate tools to approach this.

### 2. Data Pipeline Depth (Best-in-Class)
- **56 stats fields per player per round** — Most competitors track 5-15 fields
- **R1/R2 differential parsing** — Unique challenge, unique solution
- **Multi-source correlation** — gamestats + gametimes + endstats + Lua webhooks correlated per match
- **Per-weapon stat breakdowns** — Accuracy, kills, deaths per weapon

### 3. Discord Bot Breadth (Best-in-Class)
- **21 cogs, 80+ commands** — The largest game stats Discord bot architecture found
- **Achievement system** — Dynamic in-game achievement tracking via Discord
- **Prediction system** — Match outcome predictions
- **Availability polls** — Scheduling games through Discord
- **Team management** — Team formation, history, synergy analytics

### 4. Voice Channel Automation (Unique)
No other project automatically starts game server monitoring when players join a Discord voice channel and stops after a grace period. This "humans present → start tracking" pattern is a novel approach to automated stat collection.

### 5. Proximity/Heatmap Pipeline (Unique)
While standalone heatmap tools exist, no other project has an integrated pipeline from in-game Lua position tracking → database storage → engagement analysis within a game community platform.

### 6. Session Intelligence (Best-in-Class)
- **60-minute gap threshold** for session detection
- **Gaming session concept** — Groups multiple matches into logical play sessions
- **Cross-midnight handling** — Properly handles sessions spanning midnight
- **Player name change resilience** — Groups by GUID, not name

### 7. Self-Hosted Sovereignty (Advantage)
Unlike Trackbase, tracker.gg, or other SaaS stat trackers, Slomix gives the community full ownership of their data, customization of features, and independence from third-party services.

---

## Conclusions

### The Landscape
The game community platform space is fragmented. Projects tend to specialize:
- **Server managers** (Pterodactyl, PufferPanel) — manage game servers but don't track stats
- **Stats trackers** (OpenDota, XonStat, QuakeStats) — track stats but lack Discord integration
- **Discord bots** (DiscordGSM, Valorant bots) — Discord interface but shallow data pipelines
- **Community CMS** (Azuriom, Eventula) — community features but no deep analytics
- **Game mods** (WolfAdmin, SourceBans) — in-game tools but no external pipeline

### Slomix's Position
Slomix is the only project found that bridges ALL of these categories for a single game community. This vertical integration is both its greatest strength (seamless experience) and its greatest challenge (more to maintain).

### Recommendations
1. **Consider a public API layer** — Following OpenDota's model, a REST API between the database and consumers would enable future integrations
2. **Evaluate ZeroMQ or WebSocket** for stats ingestion — Could reduce the 60-second SSH polling interval
3. **Docker deployment option** — Would simplify onboarding for other ET:Legacy communities
4. **Document the architecture publicly** — Slomix's unique patterns (R1/R2 differential, voice automation, multi-source correlation) could benefit the broader game community platform space

### Final Assessment
Slomix occupies a unique niche. No single project replicates its full architecture. The closest competitors (OpenDota, XonStat) match perhaps 40-50% of Slomix's functionality, and they serve much larger games. For the ET:Legacy community, Slomix is effectively one-of-a-kind.

---

## Sources

### Tier 1 Projects
- [OpenDota (odota/core)](https://github.com/odota/core)
- [OpenDota Architecture Blog](https://blog.opendota.com/2016/05/15/architecture/)
- [XonStat](https://github.com/xonotic/xonstat) | [Live](https://stats.xonotic.org/)
- [XonStat-Go](https://gitlab.com/xonotic/xonstat-go)
- [QLStats (XonStat fork for Quake Live)](https://qlstats.net/)
- [QuakeStats](https://github.com/brabiega/quakestats) | [PyPI](https://pypi.org/project/quakestats/)

### Tier 2 Projects
- [CS2 Rank](https://github.com/Salvatore-Als/cs2-rank)
- [DODS Match Stats](https://github.com/evandrosouza89/dods-match-stats)
- [DiscordGSM GameServerMonitor](https://github.com/DiscordGSM/GameServerMonitor) | [Website](https://discordgsm.com/)
- [ActionFPS Game Log Parser](https://github.com/ActionFPS/game-log-parser) | [Live](https://actionfps.com/view-stats)

### Tier 3 Projects
- [Polly (FastAPI + discord.py)](https://github.com/pacnpal/polly)
- [valorant-stats](https://github.com/brandon-vo/valorant-stats)
- [CSGO-Bot](https://github.com/thomson008/CSGO-Bot)
- [CS2 Discord Utilities](https://github.com/NockyCZ/CS2-Discord-Utilities)
- [Chess Pipeline](https://github.com/charlesoblack/chess-pipeline)
- [libheatmap](https://github.com/lucasb-eyer/libheatmap)
- [Soccermatics](https://github.com/JoGall/soccermatics)
- [UE4 Gameplay Analytics](https://github.com/Andze/UE4-GamePlay-Analytics)

### Tier 4 Platforms
- [Pterodactyl Panel](https://github.com/pterodactyl/panel)
- [Azuriom](https://github.com/Azuriom/Azuriom) | [Website](https://azuriom.com/en)
- [Eventula Manager](https://github.com/Lan2Play/eventula-manager)
- [LANager](https://github.com/zeropingheroes/lanager)
- [LanOps Manager](https://github.com/LanOps/manager)
- [Awesome LAN Party Software](https://github.com/LANparties/awesome-lanparty-software)

### Tier 5 — ET:Legacy Ecosystem
- [WolfAdmin](https://github.com/etlegacy/wolfadmin) | [Website](https://dev.timosmit.com/wolfadmin/index.html)
- [ET:Legacy](https://github.com/etlegacy/etlegacy) | [Website](https://www.etlegacy.com/)
- [Trackbase](https://et.trackbase.net/)
- [SourceBans++](https://github.com/sbpp/sourcebans-pp)

### Other References
- [Awesome Self-Hosted](https://github.com/awesome-selfhosted/awesome-selfhosted)
- [Python Discord API](https://github.com/python-discord/api)
- [discord.py](https://github.com/Rapptz/discord.py)
- [CS:GO Log Parser](https://github.com/rufus-stone/csgo-log-parser)
- [CS2 Demoparser](https://github.com/LaihoE/demoparser)
- [Google Open Match](https://github.com/googleforgames/open-match)
