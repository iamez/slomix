# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Session Memory:** Check `.claude/memories.md` for recent session context across sessions.
> **Infra Handoff:** Read `docs/INFRA_HANDOFF_2026-02-18.md` before making infra/CI/deployment changes.

---

# Slomix - ET:Legacy Discord Bot

**Version**: 1.0.8 | **Language**: Python 3.11+ | **Discord.py**: 2.6.4 (pinned)
**Database**: PostgreSQL 17 (production) / 14 (dev) | **Status**: Production-Ready

---

## CRITICAL RULES

### Database: PostgreSQL (NOT SQLite!)

- **Database**: `etlegacy` on `localhost:5432` (user: `etlegacy_user`, password in `.env`)
- Use `postgresql_database_manager.py` for ALL DB operations (NOT `database_manager.py`)
- Use `?` for query parameters (NOT `{ph}` placeholders)
- Schema: `tools/schema_postgresql.sql` (68 tables, 56 columns in player_comprehensive_stats)
- NEVER use SQLite syntax (`INSERT OR REPLACE`, `AUTOINCREMENT`, etc.)
- `bot/core/database_adapter.py` may expose SQLite fallback paths for local/dev tooling, but production remains PostgreSQL-only.
- See `docs/POSTGRESQL_MIGRATION_INDEX.md` for migration details

### Branch Policy

**NEVER COMMIT DIRECTLY TO MAIN!** Always use feature branches with descriptive names.

### Database Query Rules

- ALWAYS use `gaming_session_id` for session queries (NOT dates)
- ALWAYS group by `player_guid` (NOT `player_name`)
- ALWAYS use 60-minute gap threshold for sessions (NOT 30!)
- ALWAYS use async database calls via `database_adapter.py` in Cogs
- NEVER recalculate R2 differential (parser handles it correctly)

### Terminology

- **ROUND** = One stats file (R1 or R2), one half of a match
- **MATCH** = R1 + R2 together (one complete map played)
- **GAMING SESSION** = Multiple matches within 60-minute gaps

---

## Architecture Overview

```
ET:Legacy Game Server -> SSH Monitor -> Parser -> PostgreSQL -> Discord Bot -> Users
                         (60s poll)    (56 fields)  (68 tables)  (80+ commands)
```

### Key Patterns

- **SSH Monitoring**: Only `endstats_monitor` task loop handles SSH (SSHMonitor disabled - race condition fix)
- **R2 Differential**: Round 2 files contain CUMULATIVE stats; parser subtracts R1 values automatically
- **Lua Webhook** (`vps_scripts/stats_discord_webhook.lua` v1.6.2): Real-time round notification, fixes surrender timing bug. Data stored in `lua_round_teams` table.
- **Cog Pattern**: 18 Cogs in `bot/cogs/`, 16 core modules in `bot/core/`, services in `bot/services/`

### Timing Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `SESSION_GAP_MINUTES` | 60 | Minutes of inactivity before new session |
| `ROUND_MATCH_WINDOW_MINUTES` | 45 | Max gap for R1-R2 matching |
| `MONITORING_GRACE_PERIOD_MINUTES` | 45 | Keep checking after voice empties |

---

## File Locations

### Core Files

- `bot/ultimate_bot.py` - Main bot entry point, loads 18 Cogs, on_ready handler
- `bot/community_stats_parser.py` - R1/R2 differential parser
- `postgresql_database_manager.py` - **ONLY tool for DB operations**
- `bot/core/database_adapter.py` - Async PostgreSQL/SQLite abstraction
- `bot/core/stats_cache.py` - 5-minute TTL query cache

### 18 Cogs (Command Modules)

All in `bot/cogs/`: achievements, admin, admin_predictions, analytics, availability_poll, last_session, leaderboard, link, matchup, permission_management, predictions, proximity, session, session_management, stats, sync, team, team_management.

### 16 Core Modules

All in `bot/core/`: achievement_system, advanced_team_detector, checks, database_adapter, endstats_pagination_view, frag_potential, lazy_pagination_view, match_tracker, pagination_view, round_contract, round_linker, season_manager, stats_cache, substitution_detector, team_manager, utils.

---

## Common Development Tasks

### Building & Running

```bash
pip install -r requirements.txt
python -m bot.ultimate_bot
# Production: screen -r slomix (bot already running in screen session)
```

### Database Operations

```bash
python postgresql_database_manager.py   # Interactive: create/import/rebuild/validate
PGPASSWORD='REDACTED_DB_PASSWORD' psql -h localhost -U etlegacy_user -d etlegacy
```

### Deployment

```bash
sudo ./install.sh --full --auto    # Full VPS setup
./install.sh --env-only            # Dev environment only
```

---

## Environment (.env required)

```bash
DISCORD_BOT_TOKEN=...
GUILD_ID=...
STATS_CHANNEL_ID=...
DATABASE_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=REDACTED_DB_PASSWORD
SSH_ENABLED=true
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot
AUTOMATION_ENABLED=true
```

---

## Infrastructure Services

- **PostgreSQL**: Primary database (17 in production, 14 in dev)
- **Redis**: v7.2.1 (caching, session data) — running on localhost:6379
- **Website**: FastAPI backend on port 8000

---

## NEW FEATURES (February 2026)

### Round Correlation System (Feb 22-26)
- **Table**: `round_correlations` (23 columns, 8 completeness boolean flags)
- **Service**: `bot/services/round_correlation_service.py`
- **Command**: `!correlation_status` (admin only)
- **Purpose**: Tracks data completeness for each match (R1+R2 together)
- **Config**: `CORRELATION_ENABLED`, `CORRELATION_DRY_RUN`, `CORRELATION_WRITE_ERROR_THRESHOLD`
- **Status**: Live mode with guardrails enabled (schema preflight, circuit breaker)

### Proximity v5 Teamplay Analytics (Feb 24)
- **New Tables**: `proximity_spawn_timing`, `proximity_team_cohesion`, `proximity_crossfire_opportunity`, `proximity_team_push`, `proximity_lua_trade_kill`
- **New Commands**: `!pse`, `!pco`, `!pxa`, `!ppu`, `!ptl`
- **Parser**: ProximityParserV4 extended (backward compatible with v4 files)
- **Website**: 5 new HTML panels with canvas cohesion timeline
- **Migration**: `migrations/013_add_proximity_v5_teamplay.sql`

### Round Linkage Anomaly Detection (Feb 26)
- **Service**: `bot/services/round_linkage_anomaly_service.py`
- **API**: `GET /diagnostics/round-linkage` (thresholded anomaly report)
- **Purpose**: Detects and reports linkage drift across lua_round_teams, rounds, round_correlations

### Website Redesign (Feb 23)
- **Framework**: React 19 + TypeScript 5.9 + Tailwind CSS v4 + Framer Motion
- **New Pages**: Sessions, Records, Awards, Activity Calendar (90-day heatmap), Maps
- **Total Pages**: 10 (5 new)
- **Features**: Player autocomplete search, achievement grid, discord badge display

### Objective Coordinate Gates (Feb 26)
- **WS11**: `scripts/proximity_objective_coords_gate.py` — prevents coordinate regressions
- **WS12**: `WEBHOOK_TRIGGER_MODE=stats_ready_only` — enforces single trigger path

### ET Rating / Skill Rating (Mar 23-26)
- **Tables**: `player_skill_ratings` (PK: player_guid), `player_skill_history` (trend tracking)
- **Service**: `website/backend/services/skill_rating_service.py` (9-metric percentile formula)
- **Router**: `website/backend/routers/skill_router.py` (4 endpoints)
- **Endpoints**: `/api/skill/leaderboard`, `/api/skill/player/{id}`, `/api/skill/player/{id}/history`, `/api/skill/formula`
- **Frontend**: `website/frontend/src/pages/SkillRating.tsx`
- **Migration**: `migrations/024_add_skill_ratings.sql`, `migrations/030_add_skill_history_session_scope.sql`
- **Features**: Per-session/map drill-down, confidence indicator, server-side tiers, auto-refresh when stale >1h
- **Status**: Live, 40 players rated

### Deep RCA Audit (Mar 26)
- **Docs**: `docs/DEEP_RCA_AUDIT_PLAN.md`, `docs/DEEP_RCA_PROXIMITY_REVIEW.md`, `docs/DEEP_RCA_SKILL_RATING_REVIEW.md`
- **Fixed**: 20+ error masking issues (silent exceptions, empty catches), retry loop bug, parser file restore
- **Key fix**: `file_tracker.py` now respects `success=FALSE` entries (was causing infinite retry loops)

---

## Common Pitfalls

- Don't use date-based queries for sessions (use `gaming_session_id`)
- Don't group by `player_name` (use `player_guid`)
- Don't assume `headshots` = `headshot_kills` (different stats)
- Don't recalculate R2 differential (parser output is correct)
- Don't provide destructive commands unprompted
- DO read `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` before claiming bugs
- DO test with edge cases: midnight crossovers, name changes, multiple sessions/day

---

## Workflow Rules

- Use [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`
- Types: feat, fix, docs, chore, refactor, test, security, perf
- Scopes: bot, website, proximity, greatshot, ci, db, lua
- Update `docs/CHANGELOG.md` for user-visible changes
- Never commit secrets, logs, backups, or database files

## Documentation

- `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` - Complete system reference
- `docs/COMMANDS.md` - All 80+ bot commands
- `docs/DATA_PIPELINE.md` - Complete data pipeline
- `docs/CHANGELOG.md` - Detailed change history and fix log
- `docs/KNOWN_ISSUES.md` - Known issues and investigations
- `docs/reference/TIMING_DATA_SOURCES.md` - Timing documentation
- `docs/archive/` - Historical bug fixes and audits

## Related Projects

See `docs/WEBSITE_CLAUDE.md` and `docs/PROXIMITY_CLAUDE.md` for sister project documentation.

---

## System Status (Version 1.0.8)

- Parser: 100% functional, R2 differential validated
- Database: PostgreSQL (68 tables), no corruption
- Bot: 80+ commands across 18 Cogs, all functional
- Website: Upload library, availability polls, greatshot, system overview
- Automation: SSH monitoring, voice detection, Lua webhook (v1.6.2)
- Production Ready: Fully tested and validated

---

**Version**: 1.0.9 | **Last Updated**: 2026-03-26 | **Schema Version**: 2.1
