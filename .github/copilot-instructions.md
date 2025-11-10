# ET:Legacy Stats Bot - AI Agent Instructions

## Project Identity
**Enemy Territory: Legacy Discord Stats Bot** - Comprehensive stats tracking for Wolfenstein: ET with PostgreSQL/SQLite hybrid backend. This is a mature, production-ready system (4,990 lines main bot) currently in VPS migration phase.

## Critical Architecture Patterns

### Database: Hybrid SQLite/PostgreSQL with Adapter Pattern
- **Active abstraction layer:** `bot/core/database_adapter.py` provides unified async interface for both backends
- **PostgreSQL is primary:** Use `postgresql_database_manager.py` for all DB operations (NOT `database_manager.py`)
- **Schema validation is critical:** Bot validates 53-column unified schema on startup - wrong schema = silent failures
- **Current branch:** `vps-network-migration` - PostgreSQL migration in progress, SQLite fallback maintained

**Database location conventions:**
```python
# Production DB (DO NOT CHANGE):
SQLITE_DB_PATH = "bot/etlegacy_production.db"  # NOT etlegacy_production.db in root
POSTGRES_DATABASE = "et_stats"  # Configured via bot_config.json or .env
```

### Stats Import Pipeline: Four-Stage Process
**1. File Generation** → ET:Legacy game server writes `YYYY-MM-DD-HHMMSS-mapname-round-N.txt` to `local_stats/`  
**2. Parsing** → `bot/community_stats_parser.py` (C0RNP0RN3StatsParser) extracts 50+ fields per player  
**3. Database Import** → `postgresql_database_manager.py` with SHA256 duplicate detection + transaction safety  
**4. Bot Access** → Cogs query via `database_adapter.py` with 5-min cache (`bot/core/stats_cache.py`)

**Critical parsing detail:** Round 2 files contain CUMULATIVE stats - parser calculates differentials by subtracting Round 1 values. Never treat R2 stats as standalone.

### Discord Bot Architecture: Cog-Based Modular Design
- **Entry point:** `bot/ultimate_bot.py` (4,990 lines but most logic in Cogs)
- **14 Cogs in `bot/cogs/`:** Each handles specific command domain (admin, stats, leaderboards, sessions, teams, etc.)
- **12 Core modules in `bot/core/`:** Shared business logic (team detection, achievements, caching, season management, pagination)
- **4 Automation services:** SSH monitoring, health checks, metrics (in `bot/services/automation/`)

**Always use Cogs for new commands** - never add commands directly to `ultimate_bot.py`

## Essential Developer Workflows

### Database Rebuild (Common Operation)
```powershell
# CORRECT way - uses manager with built-in backup + validation
python postgresql_database_manager.py
# Select: 2 - Rebuild from scratch (prompts for year filter)

# NEVER use these (wrong schema, outdated):
# ❌ python dev/bulk_import_stats.py
# ❌ python tools/nuclear_reset.py  
# ❌ python database_manager.py  # Old SQLite-only version
```

### Running Tests
**No formal test suite** - validation scripts in root directory test specific scenarios:
```powershell
python test_phase1_implementation.py  # Schema validation
python test_parser_fixes.py           # Parser accuracy
python validate_nov2_complete.py      # Data integrity
python tools/phase2_final_validation.py  # Comprehensive checks
```

### Bot Startup Sequence (Critical for Debugging)
1. `bot/logging_config.py` - Sets up comprehensive logging to `logs/`
2. `bot/config.py` - Loads config from `.env` or `bot_config.json` (env vars take precedence)
3. Schema validation - `validate_database_schema()` in `ultimate_bot.py` checks for 53 columns
4. Cog loading - Loads 14 cogs from `bot/cogs/` (failure = missing dependency or syntax error)
5. Cache priming - `stats_cache.py` initializes 5-min TTL query cache
6. Ready event - `on_ready()` logs startup time and connection info

**If bot won't start:** Check `logs/bot.log` for schema mismatch or missing cog dependencies

## Project-Specific Conventions

### File Naming Patterns
- Stats files: `2025-11-06-213045-supply-round-1.txt` (YYYY-MM-DD-HHMMSS-mapname-round-N)
- Backups: `{db_name}_backup_{timestamp}.db` (e.g., `etlegacy_production_backup_20251106_121512.db`)
- Validation scripts: `validate_*.py` or `check_*.py` in root (not organized, historical artifacts)

### Critical Don'ts
1. **Never modify schema without backup** - Use `postgresql_database_manager.py` which auto-backs up
2. **Never bulk-import without duplicate check** - All imports use SHA256 hash in `processed_files` table
3. **Never assume team assignments are accurate** - Team detection is probabilistic (see `bot/core/team_manager.py` confidence scores)
4. **Never use synchronous DB calls in Cogs** - Always use `async with db.acquire()` pattern via adapter

### Team Detection System (Complex Multi-Algorithm)
Located in `bot/core/` - 5 separate modules work together:
- `team_manager.py` - Orchestrates detection, assigns confidence scores (0.0-1.0)
- `advanced_team_detector.py` - Snapshot-based detection (most reliable)
- `substitution_detector.py` - Handles mid-game player switches
- `team_history.py` - Learns player preferences over time
- `team_detector_integration.py` - Fallback chain coordinator

**Key insight:** Teams stored in `session_teams` table as JSON arrays per round. If team data missing, bot falls back to last known assignment from history table.

## Environment Configuration

### Required Environment Variables (`.env` or `bot_config.json`)
```bash
# Discord (required)
DISCORD_TOKEN=your_discord_bot_token

# Database (PostgreSQL primary)
POSTGRES_HOST=localhost:5432
POSTGRES_DATABASE=et_stats
POSTGRES_USER=et_bot
POSTGRES_PASSWORD=secure_password

# Stats Files
LOCAL_STATS_PATH=local_stats  # Relative to project root

# Automation (optional)
AUTOMATION_ENABLED=true       # SSH monitoring, auto-import
SSH_HOST=game_server_ip
SSH_USER=stats_user
SSH_KEY_PATH=~/.ssh/id_rsa
```

**Config priority:** ENV variables > `bot_config.json` > defaults (see `bot/config.py` line 70-90)

## Common Gotchas

### Schema Mismatch Hell
**Symptom:** Bot starts but commands return no data or crash on queries  
**Cause:** Database has wrong number of columns (e.g., 35 = old split schema, not 53 = unified)  
**Fix:** Bot validates on startup - if it starts, schema is correct. If silent failures, check `PRAGMA table_info(player_comprehensive_stats)` count.

### Duplicate Import Detection Not Working
**Symptom:** Same stats imported multiple times  
**Cause:** `processed_files` table empty or file hash changed  
**Fix:** Table is auto-created by `postgresql_database_manager.py` - if missing, recreate schema

### Last Session Command Returns Old Data
**Symptom:** `!last_session` shows stats from weeks ago  
**Cause:** "Gaming sessions" group rounds by 12-hour gaps - if no play for >12h, new session created  
**Fix:** Expected behavior. Use `!sessions` to see all grouped sessions, `!session <N>` for specific one

### Parser Weapon Stats All Zeros
**Symptom:** Weapon table shows 0 kills/accuracy  
**Cause:** Weapon enumeration mismatch - parser expects C0RNP0RN3.lua weapon IDs (0-27, see `community_stats_parser.py` line 15-28)  
**Fix:** Verify game server using correct stats mod version

## Key Files for AI Agent Orientation

**Start here to understand system:**
1. `docs/TECHNICAL_OVERVIEW.md` - Complete data pipeline visualization
2. `bot/ultimate_bot.py` lines 1-200 - Bot initialization, schema validation
3. `bot/community_stats_parser.py` lines 1-100 - Parser setup, weapon enumeration
4. `bot/core/database_adapter.py` - Async DB abstraction layer
5. `postgresql_database_manager.py` lines 1-250 - Import pipeline, transaction safety

**For specific features:**
- Session analytics → `bot/cogs/last_session_cog.py` (111KB, generates 6 matplotlib graphs)
- Team detection → `bot/core/team_manager.py` (orchestrator) + `advanced_team_detector.py`
- Player stats → `bot/cogs/stats_cog.py` (16 commands including !stats, !compare, !top)
- Database admin → `bot/cogs/admin_cog.py` (!rebuild, !import, !check_schema)

## Testing Strategy

**No pytest/unittest framework** - validation is script-based:
- Schema checks: `validate_schema.py`, `check_current_schema.py`
- Data integrity: `validate_nov2_complete.py`, `comprehensive_phase1_validation.py`  
- Parser accuracy: `test_parser_fixes.py`, `validate_raw_vs_db.py`
- Import safety: `test_bulk_import.py`, `check_duplicates.py`

**To validate changes:** Run relevant check/validate script against test data in `local_stats/`

## VPS Deployment Context

Currently migrating to VPS with PostgreSQL (branch: `vps-network-migration`). Key deployment files:
- `DEPLOYMENT_CHECKLIST.md` - Pre-flight checks, systemd service setup
- `tools/setup_postgresql_debian.sh` - Auto DB setup script
- `.env.example` - Production config template

**Deployment blockers resolved:** Parser file was excluded by `.gitignore` (fixed), requirements.txt had merge conflicts (fixed).
