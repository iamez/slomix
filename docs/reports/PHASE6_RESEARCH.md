# Phase 6: Research & Benchmarking Report

**Date**: 2026-02-23
**Author**: Research Agent (Claude Sonnet 4.6)
**Scope**: Similar projects, open source components, and library recommendations for the Slomix ET:Legacy Discord Bot

---

## Executive Summary

This report documents findings from researching similar ET:Legacy / FPS game stat tracking systems, Discord bots, and open source libraries relevant to the Slomix project. The ET:Legacy niche is thin — no direct competitors exist at a comparable feature level. The closest analogues are Quake 3-family stat trackers (VSP, quakestats) and general-purpose Discord game stat bots. Several well-maintained libraries could improve or replace custom implementations in pagination, rating systems, SSH handling, and database migrations.

---

## 6A — Similar Projects

### ET:Legacy / Enemy Territory Specific

| Project | URL | Relevance | What We Can Learn |
|---------|-----|-----------|-------------------|
| **VSP Stats Processor** | https://wolfet.vexer.info/vsp-stats-processor-for-enemy-territory | High | The closest historical analogue to Slomix. PHP+MySQL, reads `games.log`, produces web stats for ET/RTCW/Q3. Features: per-weapon accuracy, ELO skill ranking, player awards, hit-location display, customizable themes. Supports Wolfenstein: Enemy Territory natively. Created 2004, still maintained (PHP 8.2.4 update in 2024). |
| **evilru/quake3-vsp-stats** | https://github.com/evilru/quake3-vsp-stats | Medium | Docker-packaged VSP for Quake 3 / ET. Useful as reference for log format handling and containerisation approach. |
| **mittermichal/greatshot-web** | https://github.com/mittermichal/greatshot-web | Medium | IdTech3 demo analysis app with Python component. Same game engine family. Architecture reference for demo-based stat extraction vs. log-based. |
| **ET:Legacy (main)** | https://github.com/etlegacy/etlegacy | Low-Medium | Official engine. Lua scripting API for mods — relevant to our `stats_discord_webhook.lua` and proximity Lua mod. Could study upstream Lua API changes. |
| **ETe (ETF engine)** | https://github.com/etfdevs/ETe | Low | Improved ET engine, not directly relevant but useful if server-side events change. |

### Quake 3 / IdTech3 Family (Closest Technical Cousins)

| Project | URL | Relevance | What We Can Learn |
|---------|-----|-----------|-------------------|
| **brabiega/quakestats** | https://github.com/brabiega/quakestats | High | Python (MIT), processes Quake 3 and Quake Live logs. Architecture: log parse → transform → store (MongoDB) → web presentation. Has custom medals, charts, multi-server support. 15 stars, actively maintained. Most architecturally similar Python project found. |
| **bad-mushroom/Qubit** | https://github.com/bad-mushroom/Qubit | Medium | Quake III log parser + rankings calculator + web dashboard. Simpler than our stack, but a clean reference for parser-to-DB-to-web pipeline design. |
| **kratt/quake-3-statistics** | https://github.com/kratt/quake-3-statistics | Low | JavaScript-based Q3 log visualiser using Plotly. Scatter plots of damage ratios and accuracies. Useful only as charting inspiration. |
| **marclerodrigues/parser** | https://github.com/marclerodrigues/parser | Low | Minimal Q3 log parser in Ruby. Too simple to be directly useful. |

### Discord Game Server Monitoring

| Project | URL | Relevance | What We Can Learn |
|---------|-----|-----------|-------------------|
| **DiscordGSM/GameServerMonitor** | https://github.com/DiscordGSM/GameServerMonitor | High | Python Discord bot monitoring 260+ game server types, live player counts, map names, server alerts via `/setalert`. Self-hostable. Well-maintained, large community. Directly comparable to our SSH polling loop — could complement or replace our server status display. |
| **EndBug/game-tracker** | https://github.com/EndBug/game-tracker | Medium | Discord bot fetching game stats from game APIs (not self-hosted servers). Different model (API pull vs. log parse) but useful UX patterns. |
| **fourjr/statsy** | https://github.com/fourjr/statsy | Medium | Python Discord bot with realtime stats for popular games (Clash Royale, etc.). Good reference for multi-game stat embed design and async data fetching. |
| **factorsofx/StatTrack** | https://github.com/factorsofx/StatTrack | Low | Java-based Discord stat tracking bot. Architecture too different. |

### Full-Stack FastAPI + PostgreSQL Templates

| Project | URL | Relevance | What We Can Learn |
|---------|-----|-----------|-------------------|
| **fastapi/full-stack-fastapi-template** | https://github.com/tiangolo/full-stack-fastapi-postgresql | Medium | FastAPI + React + SQLModel + PostgreSQL + Docker template. Well-structured auth, migrations, Docker Compose. Our website already uses FastAPI; this is a reference for maturing the stack. |
| **mkbeh/fastapi-admin-panel** | https://github.com/mkbeh/fastapi-admin-panel | Low-Medium | FastAPI + PostgreSQL + SQLAlchemy admin panel reference. |

---

## 6B — Open Source Libraries

### Rating / Skill Systems

| Library | URL | What It Replaces/Improves | Maturity |
|---------|-----|--------------------------|----------|
| **openskill.py** | https://github.com/vivekjoshy/openskill.py | Could add proper skill rating to leaderboards and predictions. Open-license alternative to TrueSkill. Supports asymmetric multi-team games (e.g., 4v4 ET matches). 3x faster than TrueSkill Python impl. | Active, PyPI, arxiv paper (2024) |
| **trueskill** | https://github.com/sublee/trueskill | Same use case as openskill. Microsoft's TrueSkill algorithm, well-known. Supports partial play weighting (useful for players who joined late). | Stable, PyPI, 1.5k+ stars |
| **multielo / multi-elo** | https://github.com/djcunningham0/multielo | Extends standard Elo to multiplayer. Simpler than TrueSkill but easy to integrate. | Moderate, PyPI |
| **elote** | https://github.com/wdm0006/elote | Wraps multiple rating systems (Elo, Glicko, etc.) in a single API for comparison. | Moderate, PyPI |
| **EloPy** | https://github.com/HankSheehan/EloPy | Simple 1v1 Elo only. Too limited for team play. | Low activity |
| **Open-ELO** | https://github.com/BeniaminC/Open-ELO | Multiple Elo variants in one package. | Low-Medium |

### Discord Bot Pagination

| Library | URL | What It Replaces/Improves | Maturity |
|---------|-----|--------------------------|----------|
| **Defxult/reactionmenu** | https://github.com/Defxult/reactionmenu | Could replace our custom `lazy_pagination_view.py` and `pagination_view.py`. Supports buttons, reactions, select menus, text+embed combos, timeout handling. discord.py 2.0+. | Active, PyPI |
| **soosBot-com/Pagination** | https://github.com/soosBot-com/Pagination | Simpler embed paginator for discord.py 2.0. Less feature-rich than reactionmenu. | Low-Medium |
| **FaddyManatee/embed-pagination** | https://github.com/FaddyManatee/embed-pagination | Fork of above with delete-on-timeout. | Low |
| **thegamecracks/discord-ext-pager** | PyPI: `discord-ext-pager` | discord-ext-menus style interface, familiar API. | Low-Medium |

### SSH / Remote Monitoring

| Library | URL | What It Replaces/Improves | Maturity |
|---------|-----|--------------------------|----------|
| **AsyncSSH** | https://github.com/ronf/asyncssh | Our SSH monitoring currently uses paramiko (or custom). AsyncSSH is a full asyncio-native SSH implementation. 15x faster than paramiko in multi-host benchmarks. Cleaner integration with our async bot event loop. | Very active, PyPI, 2.22.0 |
| **Paramiko** | https://github.com/paramiko/paramiko | Current likely dependency. Blocking I/O, requires `run_in_executor` for async. No native asyncio support (open issue since 2018). | Stable but not async-native |

### Database Migrations

| Library | URL | What It Replaces/Improves | Maturity |
|---------|-----|--------------------------|----------|
| **Alembic** | https://alembic.sqlalchemy.org/ | Would replace our manual `schema_postgresql.sql` + `postgresql_database_manager.py` migration approach. Industry-standard Python DB migration tool. Auto-generates migration scripts from SQLAlchemy model diffs. Async support via `alembic -t async`. | Very mature, SQLAlchemy team |
| **asyncpg-migrate** | https://github.com/kornicameister/asyncpg-migrate | Async-native alternative to Alembic for asyncpg users (no SQLAlchemy). Younger, less widely adopted. | Low, PyPI |

### Real-Time Data Pipelines

| Library | URL | What It Replaces/Improves | Maturity |
|---------|-----|--------------------------|----------|
| **FastStream** | https://github.com/ag2ai/faststream | If we ever add a queue/broker layer (see `DATA_INGEST_QUEUE_DESIGN.md`). Async Python framework for Kafka, RabbitMQ, NATS, Redis Streams. Auto-generates AsyncAPI docs. | Active, 2.5k+ stars |
| **aiokafka** | https://github.com/aio-libs/aiokafka | Async Kafka client if we move to event-driven ingest. | Stable, aio-libs org |
| **redis-py (asyncio)** | Built-in async support in redis-py 4+ | For caching layer beyond our current 5-minute TTL in `stats_cache.py`. Redis pub/sub could drive real-time Discord notifications without polling. | Very mature |

### Game Stats / Log Parsing

| Library | URL | What It Replaces/Improves | Maturity |
|---------|-----|--------------------------|----------|
| **quakestats (PyPI)** | https://pypi.org/project/quakestats/ | Reference architecture for IdTech3 log parsing. Not directly usable (Quake-specific), but worth studying for parser design patterns. | Low (15 stars), MIT |

---

## Specific Recommendations

### Priority 1 — High Impact, Low Effort

**1. Replace paramiko with AsyncSSH for SSH monitoring**
- File: `bot/core/` (SSH monitor task in `bot/ultimate_bot.py`)
- Why: Our `endstats_monitor` task loop uses SSH polling every 60 seconds. AsyncSSH integrates natively with asyncio, eliminating `run_in_executor` wrappers and potential thread-pool blocking. Especially valuable if we ever poll multiple servers.
- Action: `pip install asyncssh`, refactor SSH connection logic.

**2. Add Alembic for database schema migrations**
- Currently: Schema managed via `tools/schema_postgresql.sql` and manual `postgresql_database_manager.py` operations.
- Why: As schema grows (68 tables), Alembic provides versioned, reversible migrations, auto-diff generation, and team-safe deployment. Reduces risk of `DROP TABLE` accidents.
- Action: `pip install alembic`, `alembic init`, integrate with existing asyncpg setup using async template.

**3. Adopt openskill.py for player/team skill ratings**
- Currently: No formal skill rating system. Predictions cog uses custom logic.
- Why: ET matches are team-based and asymmetric (different team sizes possible). openskill handles this natively, is MIT-licensed (unlike TrueSkill's restrictive MS license), and is faster. Could power: leaderboard rankings, prediction accuracy, matchup balance scores, team synergy ratings.
- Action: `pip install openskill`, integrate into `bot/cogs/predictions.py` and `bot/cogs/leaderboard.py`.

### Priority 2 — Medium Impact, Moderate Effort

**4. Evaluate reactionmenu for pagination replacement**
- Currently: Custom `lazy_pagination_view.py`, `pagination_view.py`, `endstats_pagination_view.py` in `bot/core/`.
- Why: Three separate pagination implementations suggest divergent evolution. `reactionmenu` supports buttons, selects, text+embed, and category navigation — potentially consolidating all three into one dependency.
- Caveat: Our lazy pagination has custom "load on demand" behavior for large datasets; verify reactionmenu can replicate this before migrating.
- Action: Prototype one command with reactionmenu; if it fits, migrate progressively.

**5. Study DiscordGSM/GameServerMonitor architecture**
- Our server control cog (`bot/cogs/server_control.py`) handles ET server management. DiscordGSM supports 260+ game types with a clean polling abstraction layer.
- Learn: How they abstract per-game query protocols, handle server-down alerts, and present live status embeds efficiently.
- Not a replacement (DiscordGSM doesn't parse game logs), but a UI/UX reference.

**6. Study VSP Stats Processor feature set for award ideas**
- VSP has been doing ET stat awards since 2004. Features we may be missing or could improve:
  - Hit-location displays (headshots by body part)
  - Per-weapon accuracy breakdowns in web UI
  - Server-side ELO ranking (complement to openskill recommendation above)
  - Customisable award thresholds
- Action: Review VSP's award list at https://wolfet.vexer.info/vsp-stats-processor-for-enemy-territory against our achievement system.

### Priority 3 — Long-Term / If Architecture Evolves

**7. FastStream for event-driven ingest pipeline**
- Relevant if `DATA_INGEST_QUEUE_DESIGN.md` design is implemented.
- FastStream would sit between the Lua webhook / SSH parser and PostgreSQL, providing reliable async message queuing with retry logic.
- More complex to deploy (requires broker), but solves data loss during bot downtime.

**8. Redis pub/sub for real-time Discord notifications**
- Currently: Bot polls via 60-second SSH loop.
- Alternative: Lua webhook → Redis Streams → Bot subscriber → Discord. Eliminates polling delay entirely.
- Pairs well with FastStream if adopted.

---

## Key Takeaways

1. **No direct ET:Legacy Python Discord bot competitor exists.** Slomix is a novel project in this niche. The closest comparison is VSP (PHP, 2004), which shows the feature landscape but not the architecture.

2. **quakestats (Python) is the best architectural reference** for how to structure a Python-based IdTech3 log parser with web presentation. Worth reading its source even though it targets Quake, not ET.

3. **openskill.py is the most actionable immediate addition** — it would unlock proper skill-based rankings, improve predictions, and is trivially pip-installable.

4. **AsyncSSH is a clean improvement** to our SSH monitoring that reduces threading risk in the async bot context.

5. **Alembic migration adoption is increasingly important** as the schema (68 tables) continues to grow — manual SQL migrations don't scale safely.

6. **Our custom pagination is reasonable** given the lazy-load requirement, but reactionmenu is worth a prototype to reduce maintenance burden.

---

## Sources

- [ET:Legacy GitHub](https://github.com/etlegacy/etlegacy)
- [VSP Stats Processor for ET](https://wolfet.vexer.info/vsp-stats-processor-for-enemy-territory)
- [evilru/quake3-vsp-stats](https://github.com/evilru/quake3-vsp-stats)
- [mittermichal/greatshot-web](https://github.com/mittermichal/greatshot-web)
- [brabiega/quakestats](https://github.com/brabiega/quakestats)
- [bad-mushroom/Qubit](https://github.com/bad-mushroom/Qubit)
- [DiscordGSM/GameServerMonitor](https://github.com/DiscordGSM/GameServerMonitor)
- [EndBug/game-tracker](https://github.com/EndBug/game-tracker)
- [fourjr/statsy](https://github.com/fourjr/statsy)
- [fastapi/full-stack-fastapi-template](https://github.com/tiangolo/full-stack-fastapi-postgresql)
- [vivekjoshy/openskill.py](https://github.com/vivekjoshy/openskill.py)
- [OpenSkill arxiv paper](https://arxiv.org/abs/2401.05451)
- [sublee/trueskill](https://github.com/sublee/trueskill)
- [djcunningham0/multielo](https://github.com/djcunningham0/multielo)
- [wdm0006/elote](https://github.com/wdm0006/elote)
- [Defxult/reactionmenu](https://github.com/Defxult/reactionmenu)
- [soosBot-com/Pagination](https://github.com/soosBot-com/Pagination)
- [ronf/asyncssh](https://github.com/ronf/asyncssh)
- [asyncpg-migrate](https://github.com/kornicameister/asyncpg-migrate)
- [ag2ai/faststream](https://github.com/ag2ai/faststream)
- [aio-libs/aiokafka](https://github.com/aio-libs/aiokafka)
- [McLeopold/PythonSkills](https://github.com/McLeopold/PythonSkills)
- [BeniaminC/Open-ELO](https://github.com/BeniaminC/Open-ELO)
