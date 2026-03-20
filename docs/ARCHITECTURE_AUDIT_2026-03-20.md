# Architecture Audit Report — 2026-03-20

## Scope

Full architectural audit of slomix_discord repository (~52K lines Python, 68 PostgreSQL tables, React 19 website).
Conducted on commit `6d8b3e0` (main) + cleanup branch `refactor/architecture-audit-cleanup`.

---

## Actions Taken (This Audit)

### Phase 1: Cleanup (DONE)
- **Deleted**: `agents.md`, `ARCHITECTURE.md`, `analytics/` (root-level junk)
- **Deleted**: 7x `.oldbackup.CLAUDE.md`, `*.bak2`, `_temp_detail.py`
- **Removed from git**: `team_history.py`, `team_detector_integration.py` (dead SQLite-only modules, 0 imports)
- **Archived**: 23 historical investigation/audit/handoff docs → `docs/archive/`
- **Tracked**: 4 new SQL migrations (018-021)
- **Gitignored**: `monitoring/`, 9 research/scratch docs

### Phase 2: Bug Fixes (DONE)
- **BaseException → (ValueError, TypeError)** in `community_stats_parser.py:216,1368`
- **logger.debug → logger.error** in `file_tracker.py:307` (mark_processed failures)
- **Removed 126 lines of SQLite branching** across 7 files:
  - `file_tracker.py`, `session_cog.py`, `leaderboard_cog.py`, `file_repository.py`, `ultimate_bot.py`
- **Hardcoded password removed** from `proximity/README.md`, `proximity/docs/FREEZE_RUNBOOK_2026-02-19.md`
- **Stale comments fixed**: "30 minutes" → actual configurable values

---

## Audit Findings

### CRITICAL

| ID | Component | Description | Status |
|----|-----------|-------------|--------|
| C-SEC-001 | Security | Hardcoded DB password `etlegacy_secure_2025` in 2 tracked files | **FIXED** (this audit). Still in git history — rotate password recommended |
| C-IMPORT-001 | DB Import | `time_played_percent` (alive%) parsed & calculated by parser but never stored in PostgreSQL. Column missing from schema | **OPEN** — needs migration + insert update |

### MEDIUM

| ID | Component | Description |
|----|-----------|-------------|
| M-PARSER-002 | Parser | File parsed twice on PostgreSQL path (db_manager + ultimate_bot) |
| M-PARSER-003 | Parser | Orphan R2 stores cumulative stats as if differential — no DB flag |
| M-IMPORT-001 | DB Import | PostgreSQL `_get_or_create_gaming_session_id` uses global latest round, not chronological predecessor. Backfills get wrong session IDs |
| M-IMPORT-004 | DB Import | Rounds `ON CONFLICT` skips updating `time_limit`, `actual_time`, `round_outcome` |
| M-IMPORT-005 | DB Import | Player stats `ON CONFLICT` only updates 5/53 columns on re-import |
| M-PUB-001 | Publisher | "HS" = `headshot_kills` in map summary but `headshots` (hits) in round embed |
| M-PUB-002 | Publisher | `AVG(accuracy)` is unweighted across players with different shot counts |
| M-WEB-001 | Website | `api.py` is 11,031 lines / 88 endpoints — should split into ~8-10 domain routers |
| M-SVC-001 | Services | ~250 lines duplicated between `timing_comparison_service.py` and `timing_debug_service.py` |
| M-MW-001 | Middleware | IP proxy utilities duplicated across `logging_middleware.py` and `rate_limit_middleware.py` |

### LOW

| ID | Component | Description |
|----|-----------|-------------|
| L-SVC-001 | Services | `ws_client.py` (265 lines) permanently disabled — consider archiving |
| L-WEB-001 | Website | 30/34 legacy JS files in `website/js/` likely obsolete post-React migration |
| L-TEST-001 | Testing | No `--cov-fail-under` threshold in CI — coverage not enforced |
| L-TEST-002 | Testing | `team_manager.py` (1,530 lines) and `voice_session_service.py` (1,091 lines) at 0% coverage |
| L-TEST-003 | Testing | All 18 Cogs at 0% test coverage |

### VERIFIED (No Issues Found)

- **SQL injection surfaces**: All parameterized or use hardcoded constant sets
- **File upload security**: OWASP-compliant (extension allowlist, magic bytes, UUID paths, path traversal protection)
- **SSH security**: Strict `RejectPolicy`, filename regex validation, path traversal protection
- **R2 differential calculation**: Correctly subtracts R1 from R2 cumulative data
- **Session gap**: Correctly uses 60 minutes (not 30)
- **File deduplication**: 5-layer check with SHA256 integrity verification
- **Signal/Telegram connectors**: Properly feature-flagged and integrated
- **Round correlation service**: Schema preflight + circuit breaker working correctly
- **All 3 middleware modules**: Production-quality implementations

---

## Test Suite Status

- **357 tests**: 313 passed, 45 skipped, 0 failed
- **Overall coverage**: 19% (21,258 statements, 17,222 missed)
- **Stats parser coverage**: 61%
- **Round correlation coverage**: 45%
- **ultimate_bot.py coverage**: 12%
- **CI pipeline**: 5 workflows (tests, publish-images, release, codeql, repo-hygiene)
- **Docker**: Both `Dockerfile.api` and `Dockerfile.website` functional

---

## Detailed Findings by Area

### Pipeline: Parser (community_stats_parser.py)
- **VERIFIED**: R2 differential (GUID-based, `max(0,...)` clamping), R2_ONLY_FIELDS (24 fields), midnight crossover, color code stripping, bot detection regex, weapon ID mapping (0-27), reconnect detection, DPM calculation
- **M-PARSER-002**: File parsed twice on PostgreSQL path — `db_manager.process_file()` parses internally, then `ultimate_bot.py` parses again for Discord publisher data
- **M-PARSER-003**: Orphan R2 (no R1 found) stores cumulative stats as if differential — no `differential_calculation` flag set in DB

### Pipeline: Database Import (postgresql_database_manager.py)
- **VERIFIED**: 60-min session gap, player_guid grouping, transaction boundaries, ON CONFLICT semantics, R2 match_id derivation, weapon stats dynamic column discovery
- **C-IMPORT-001**: Parser calculates `time_played_percent` (alive%) with proper differential math but PostgreSQL schema lacks the column — value silently discarded
- **M-IMPORT-001**: `_get_or_create_gaming_session_id` queries global latest round instead of chronological predecessor — backfills get wrong session IDs
- **M-IMPORT-005**: Player stats ON CONFLICT updates only `kills, deaths, damage_given, kd_ratio, efficiency` — 48 other fields unchanged on re-import

### Pipeline: SSH Monitor (endstats_monitor)
- **VERIFIED**: Atomicity, 5-layer file deduplication, 168h lookback window, 45-min grace period, error recovery with admin alerts, dead hours optimization (02:00-11:00 CET)
- **M-SSH-002**: Race window between `should_process_file()` and `mark_processed()` — mitigated by in-memory set + ON CONFLICT but theoretically possible

### Pipeline: Round Publisher
- **VERIFIED**: Stats from DB not parser, Lua timing priority chain, error isolation, map completion detection
- **M-PUB-001**: "HS" inconsistency — round embed uses `headshots` (weapon hits), map summary uses `headshot_kills` (lethal headshots)
- **M-PUB-002**: `AVG(accuracy)` unweighted — player with 1 shot weighs same as player with 1000 shots

### Services Layer
- **Timing services**: `timing_comparison_service.py` and `timing_debug_service.py` share 3 identical methods (~250 lines). `session_timing_shadow_service.py` is distinct (different purpose)
- **Dead services**: `ws_client.py` properly gated (WS_ENABLED enforced false), `signal_connector.py` and `telegram_connector.py` properly feature-flagged and integrated
- **New services**: All 5 (proximity_session_score, round_correlation, round_linkage_anomaly, webhook_round_metadata, correlation_context) properly integrated

### Website
- **api.py**: 11,031 lines, 88 endpoints. Suggested split: diagnostics, live_status, player_stats, sessions, leaderboards, weapons_maps, matches, awards, proximity, seasons
- **Legacy JS**: 30/34 files not directly loaded by index.html (loaded dynamically via client-side router). React migration complete (19/19 routes) — these are being phased out
- **Middleware**: All 3 (logging, rate_limit, http_cache) production-quality. Minor duplication of IP proxy utilities across logging + rate_limit
- **Auth**: Discord OAuth2 + PKCE flow in `auth.py` (814 lines)

### Security
- **SQL injection**: All surfaces verified safe (parameterized queries, hardcoded constant sets, int-clamped LIMIT)
- **Upload security**: OWASP-compliant (allowlists, magic bytes, UUID paths, streaming size enforcement, symlink rejection)
- **SSH security**: Strict RejectPolicy (insecure flags intentionally ignored), filename regex, path traversal protection
- **Secrets**: `.env` gitignored, `.env.example` placeholder-only. Password was in 2 tracked docs (now FIXED)

### Testing & CI
- 5 CI workflows: tests (PostgreSQL 14 + Redis 7.4), publish-images, release-please, CodeQL, repo-hygiene
- Docker: Both Dockerfiles functional (Python 3.11-slim + nginx 1.27-alpine), built in CI
- No `--cov-fail-under` threshold — coverage collected but never enforced
- 45 skipped tests: 19 need POSTGRES_TEST_* env vars (available in CI, not locally)

---

## Recommended Next Steps (Priority Order)

1. **Rotate DB password** — `etlegacy_secure_2025` is in git history
2. **Add `time_played_percent` column** to PostgreSQL schema + store in import path (C-IMPORT-001)
3. **Fix PostgreSQL session ID assignment** for backfills (M-IMPORT-001) — port chronological-predecessor query from SQLite path
4. **Expand ON CONFLICT update sets** for rounds and player stats (M-IMPORT-004/005)
5. **Split `api.py`** into domain-specific routers (~8-10 files)
6. **Add `--cov-fail-under=15`** to CI pytest invocation (start low, ratchet up)
7. **Extract timing utilities** to shared module (eliminate 250-line duplication)
8. **Clean up legacy JS** — verify which files are loaded dynamically, archive rest
