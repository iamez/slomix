# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Infra Handoff:** Read `docs/INFRA_HANDOFF_2026-02-18.md` before making infra/CI/deployment changes.

---

# Slomix - ET:Legacy Discord Bot

**Version**: 1.30.0 <!-- x-release-please-version --> | **Language**: Python 3.11+ | **Discord.py**: 2.6.4 (pinned)
**Database**: PostgreSQL 17 (production) / 14 (dev) | **Status**: Production-Ready

---

## CRITICAL RULES

### Database: PostgreSQL (NOT SQLite!)

- **Database**: `etlegacy` on `localhost:5432` (user: `etlegacy_user`, password in `.env`)
- Use `postgresql_database_manager.py` for ALL DB operations (NOT `database_manager.py`)
- Use `?` for query parameters (NOT `{ph}` placeholders)
- Schema: `tools/schema_postgresql.sql` (101 tables, 57 columns in player_comprehensive_stats)
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
                         (60s poll)    (57 fields)  (101 tables)  (107 commands)
```

### Key Patterns

- **SSH Monitoring**: Only `endstats_monitor` task loop handles SSH (SSHMonitor disabled - race condition fix)
- **R2 Differential**: Round 2 files contain CUMULATIVE stats; parser subtracts R1 values automatically
- **Lua Webhook** (`vps_scripts/stats_discord_webhook.lua` v1.7.0): Real-time round notification, fixes surrender timing bug. Data stored in `lua_round_teams` table.
- **Cog Pattern**: 21 Cogs in `bot/cogs/`, 19 core modules in `bot/core/`, services in `bot/services/`

### Timing Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `SESSION_GAP_MINUTES` | 60 | Minutes of inactivity before new session |
| `ROUND_MATCH_WINDOW_MINUTES` | 45 | Max gap for R1-R2 matching |
| `MONITORING_GRACE_PERIOD_MINUTES` | 45 | Keep checking after voice empties |

---

## File Locations

### Core Files

- `bot/ultimate_bot.py` - Main bot entry point, loads 21 Cogs, on_ready handler
- `bot/community_stats_parser.py` - R1/R2 differential parser
- `postgresql_database_manager.py` - **ONLY tool for DB operations**
- `bot/core/database_adapter.py` - Async PostgreSQL/SQLite abstraction
- `bot/core/stats_cache.py` - 5-minute TTL query cache

### 21 Cogs (Command Modules)

All in `bot/cogs/`: achievements, admin, admin_predictions, analytics, automation_commands, availability_poll, last_session, leaderboard, link, matchup, on_this_day, permission_management, predictions, proximity, server_control, session, session_management, stats, sync, team, team_management.

### 19 Core Modules

All in `bot/core/`: achievement_system, checks, correlation_context, database_adapter, endstats_pagination_view, frag_potential, guid_utils, lazy_pagination_view, match_tracker, pagination_view, round_canonical, round_contract, round_linker, season_manager, stats_cache, stopwatch_pairing, substitution_detector, team_manager, utils.

---

## Common Development Tasks

### Building & Running

```bash
pip install -r requirements.txt
python -m bot.ultimate_bot
# systemd-managed on both the dev box and the production VM, but the UNIT
# NAMES DIFFER PER HOST: dev uses etlegacy-bot/etlegacy-web, the production
# VM uses slomix-bot/slomix-web (scripts/deploy_release.sh restarts the
# slomix-* pair). Discover, never assume — scripts/health_check.sh checks
# both spellings and explains why:
#   systemctl list-units --all 'etlegacy-*' 'slomix-*'
# This matters because `systemctl is-active <nonexistent-unit>` answers
# "inactive", which reads as "not running" and invites starting a second
# instance by hand. Don't: both units are Restart=always, so a hand-started
# copy wins the port race and systemd's own restart then fails with
# EADDRINUSE in a loop (that happened on 2026-08-05).
#   sudo systemctl restart etlegacy-bot.service etlegacy-web.service   # dev
# On the dev box those restarts are NOPASSWD in sudoers; confirm per host
# with `sudo -n -l` rather than assuming it, since sudoers is host-specific.
# (Some historical hosts still run the bot under `screen -r slomix`.)
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
DISCORD_GUILD_ID=...
STATS_CHANNEL_ID=...
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=REDACTED_DB_PASSWORD
SSH_ENABLED=true
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot
AUTOMATION_ENABLED=true
```

> `bot/config.py` reads `POSTGRES_*` only — `DB_HOST/DB_NAME/DB_USER/DB_PASSWORD` names are accepted by `scripts/apply_migrations.py` as a fallback, but the bot itself will not see them. Use the `POSTGRES_*` names shown above and in `.env.example`.

---

## Infrastructure Services

- **PostgreSQL**: Primary database (17 in production, 14 in dev)
- **Redis**: v7.4.2 (caching, session data) — running on localhost:6379; CI uses the same image (`redis:7.4.2-alpine` in `.github/workflows/tests.yml`)
- **Website**: FastAPI backend on port 8000

---

## Feature History

Feb-Mar 2026 feature notes (round correlation, proximity v5, website redesign,
skill rating, RCA audits, Oksii adoption) were removed from this file on
2026-07-29 — they were stale weight every session paid to read. `docs/archive/`
is gitignored (not pushed to GitHub), so the full text isn't duplicated there;
see this file's git history (or `git show <pre-2026-07-29-commit>:docs/CLAUDE.md`)
for the removed section verbatim.

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
- `CHANGELOG.md` (root) is auto-generated by release-please from `feat:`/`fix:`/`perf:` commits — no manual edits needed. `docs/CHANGELOG.md` is the historical long-form notes archive (frozen).
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

## System Status (Version 1.30.0) <!-- x-release-please-version -->

- Parser: 100% functional, R2 differential validated, Oksii fields backward-compatible
- Database: PostgreSQL (101 tables), no corruption
- Bot: 107 commands across 21 Cogs and their mixins, all functional
- Website: Upload library, availability polls, greatshot, storytelling, skill rating, BOX scoring
- Automation: SSH monitoring, voice detection, Lua webhook (v1.7.0)
- Lua: v6.01 with Oksii adoption (killer_health, alive_count, reinf timing)
- Code quality: Ruff 0 errors, 4,200 tests, mypy configured
- Production Ready: Fully tested and validated

---

**Version**: 1.30.0 <!-- x-release-please-version --> | **Last Updated**: 2026-07-29 | **Schema Version**: 2.2
