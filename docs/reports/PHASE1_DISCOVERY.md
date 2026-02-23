# Phase 1: Project Discovery Report

**Date**: 2026-02-23
**Agent**: discovery-agent
**Scope**: Full project structure mapping, CLAUDE.md audit, memories.md staleness check, dev environment review

---

## 1. Project Structure Map

### Root Directory Overview

The project root (`/home/samba/share/slomix_discord`) is **severely cluttered** with non-source artifacts mixed in with production code. This is a major housekeeping issue.

#### Top-Level Directories (meaningful)

| Directory | Purpose | Has CLAUDE.md? |
|-----------|---------|----------------|
| `bot/` | Main Discord bot package | YES |
| `website/` | FastAPI backend + vanilla JS frontend | Partial (backend only) |
| `gemini-website/` | New React/TypeScript frontend (WIP) | NO |
| `proximity/` | Combat proximity tracker (disabled by default) | NO |
| `greatshot/` | Highlight clip detection/processing | NO |
| `tools/` | DB utilities, migration scripts | NO |
| `vps_scripts/` | Lua webhook + deployment scripts | NO |
| `tests/` | Test suite | YES |
| `docs/` | Documentation | YES |
| `archive/` | Old/deprecated code | NO |
| `backups/` | Historical backups (large, should be gitignored) | NO |
| `analytics/` | Analytics scripts (purpose unclear) | NO |
| `migrations/` | DB migration files (at root level) | NO |
| `scripts/` | Miscellaneous scripts | NO |
| `docker/` | Docker configuration | NO |
| `bin/` | Binary/script utilities | NO |
| `monitoring/` | Monitoring configuration | NO |
| `dev/` | Dev tooling | NO |
| `dev_tools/` | More dev tooling (redundant with dev/) | NO |

#### [CRITICAL] Root Directory Clutter

The root contains dozens of files that should not be there:
- **SQLite database files**: `etlegacy_production.db`, `backup.db`, `game_stats.db`, `stats.db`, `etlegacy_stats.db`, `slomix_stats.db`, `BACKUP_BEFORE_DEPLOYMENT_20251104_121158.db`, `test_import.db` — these should be gitignored or deleted
- **SQL backup dumps**: `etlegacy_backup.sql`, `postgresql_backup_*.sql`, `etlegacy_backup_before_time_dead_fix_*.sql`
- **Image files**: `banned.jpg`, `bigbug.jpg`, `brokenhomepage.jpg`, `claudekilled.jpg`, etc. (15+ screenshot images)
- **Old Lua files**: `c0rnp0rn7.lua`, `c0rnp0rn.lua`, `c0rnp0rn8.lua`, `endstats.lua`, and multiple variants — should be in `vps_scripts/` or `archive/`
- **Log files**: `nohup.out`, `*.log`, `database_manager.log`, `postgresql_manager.log`, `firebase-debug.log`
- **Validation/report artifacts**: Dozens of `stats_validation_*` JSON/HTML/TXT files
- **Old demo files**: `.dm_84` replay files, various `.png`/`.jpg` screenshots
- **Temp dev scripts**: `check_*.py`, `debug_*.py`, `test_*.py`, `show_*.py` (20+ ad-hoc scripts at root)
- **Old zip archives**: `website.zip`, `website (2).zip`, `slomix-review.zip`
- **Markdown litter**: `chatgptresearch.md`, `zac0rna.md`, `cmon.txt`, `untrue.jpg` etc.
- **Version string artifacts**: Files named `=0.21.0`, `=0.29.0`, `=2.2.0` etc. (pip error artifacts)

---

## 2. CLAUDE.md Audit

### Existing CLAUDE.md Files (9 found)

| File | Last Updated (approx) | Status |
|------|----------------------|--------|
| `/CLAUDE.md` (root) | 2026-02-22 | Current - accurate |
| `/docs/CLAUDE.md` | 2026-02-22 | Duplicate of root - redundant |
| `/bot/CLAUDE.md` | ~Feb 2026 | Mostly accurate, minor drift |
| `/bot/cogs/CLAUDE.md` | ~Feb 2026 | STALE - says 20 cogs, actual is 21 |
| `/bot/core/CLAUDE.md` | ~Feb 2026 | Accurate |
| `/bot/services/CLAUDE.md` | ~Feb 2026 | Partially stale - missing new services |
| `/bot/automation/CLAUDE.md` | ~Feb 2026 | Has known issue noted (30 min mismatch) |
| `/tests/CLAUDE.md` | ~Feb 2026 | Accurate |
| `/website/backend/CLAUDE.md` | ~Feb 2026 | Mostly accurate, missing `planning.py` router |

### Accuracy Findings Per CLAUDE.md

#### `/CLAUDE.md` (root) — [MINOR] One inaccuracy
- States "21 Cogs" — CONFIRMED correct (21 .py files excluding `__init__.py`)
- States "18 core modules" — CONFIRMED correct
- States "68 tables" — matches memories.md audit
- States "Lua webhook v1.6.2" — correct
- **Issue**: `pyproject.toml` says version `1.0.8` but CLAUDE.md says version `1.0.6`

#### `/docs/CLAUDE.md` — [IMPORTANT] Pure duplicate
- Identical content to root `CLAUDE.md`
- Two CLAUDE.md files with identical content creates confusion about which is authoritative
- **Recommendation**: `docs/CLAUDE.md` should contain docs-specific guidance, not a copy of root

#### `/bot/CLAUDE.md` — [MINOR] Accuracy issues
- "20 cogs" — STALE, actual count is 21
- "30-minute window for R1-R2 matching (line 384)" — should now be 45 minutes per config
- Code blocks use malformed triple-backtick fences mixed with `python`/`text`/`sql` language tags mid-block (formatting bug)

#### `/bot/cogs/CLAUDE.md` — [IMPORTANT] Stale count
- States "20 total" cogs in header
- Lists only 20 cogs — missing `availability_poll_cog.py` in the table

#### `/bot/services/CLAUDE.md` — [IMPORTANT] Missing services
- Lists ~11 services but actual directory has **24 services**
- Missing from CLAUDE.md:
  - `availability_notifier_service.py`
  - `endstats_aggregator.py`
  - `matchup_analytics_service.py`
  - `monitoring_service.py`
  - `player_analytics_service.py`
  - `prediction_embed_builder.py`
  - `round_correlation_service.py` (new, Feb 2026)
  - `session_timing_shadow_service.py`
  - `signal_connector.py`
  - `telegram_connector.py`
  - `timing_comparison_service.py`
  - `timing_debug_service.py`

#### `/bot/automation/CLAUDE.md` — [MINOR] Acknowledged issue
- Correctly flags the 30-min vs 60-min mismatch as a known risk
- `bot/services/automation/` exists and is documented but listed as subdirectory content (correct)

#### `/bot/core/CLAUDE.md` — [OK] Accurate
- Lists 18 modules correctly
- Content matches actual files

#### `/tests/CLAUDE.md` — [MINOR] Directory structure outdated
- References `test_database_adapter.py` in `tests/unit/` — verify this file exists
- Overall guidance is accurate

#### `/website/backend/CLAUDE.md` — [MINOR] Missing router
- Does not mention `planning.py` router that exists in `website/backend/routers/`
- Missing service: `contact_handle_crypto.py`, `http_cache_backend.py`, `planning_discord_bridge.py`

### Directories MISSING a CLAUDE.md

| Directory | Priority | Rationale |
|-----------|----------|-----------|
| `gemini-website/` | [IMPORTANT] | Active new frontend project, no guidance at all |
| `proximity/` | [IMPORTANT] | Sister project with its own architecture |
| `greatshot/` | [IMPORTANT] | Sister project with its own architecture |
| `tools/` | [IMPORTANT] | 70+ scripts, complex, needs orientation |
| `vps_scripts/` | [IMPORTANT] | Lua scripts critical to pipeline |
| `website/` (root) | [MINOR] | Frontend JS has no CLAUDE.md |
| `tests/unit/` | [MINOR] | Subfolder of tests with own content |

---

## 3. memories.md Staleness Audit

**File**: `/home/samba/share/slomix_discord/.claude/memories.md`
**Last Updated**: 2026-02-20 (header says 2026-02-20, but content extends to 2026-02-23)

### Stale Entries

| Entry | Status | Issue |
|-------|--------|-------|
| "Cogs: 20" (Architecture Quick Facts, Feb 15 section) | [IMPORTANT] STALE | Actual count is 21 |
| "Tables: 42" (Architecture Quick Facts, Feb 15 section) | [IMPORTANT] STALE | Actual count is 68 (confirmed in Feb 22 section) |
| "Lua webhook version: v1.6.0" (Architecture Quick Facts) | STALE | Now v1.6.2 (Feb 22 section confirms) |
| "Bot entry: ~4,941 lines" | STALE | bot/CLAUDE.md says ~4,990 lines |
| "PR #35 is still OPEN" (Feb 15 section) | Likely stale | Sprint completed, status unknown |
| "Current branch: docs/readme-roadmap-workflow-updates" (Feb 15 section) | STALE | Current branch is `reconcile/merge-local-work` |
| "42 tables" (Key Decisions > Database) | STALE | Now 68 tables |
| "20 cogs" (Key Decisions > Bot Architecture) | STALE | Now 21 cogs |
| Running Services: "Bot: Screen" | [IMPORTANT] Check | memories says `screen -r slomix` but CLAUDE.md says systemd |
| "Agent Teams experimental feature is ENABLED" | [MINOR] | Still accurate based on settings.json |

### Current/Accurate Entries

| Entry | Status |
|-------|--------|
| PostgreSQL v17 (Feb 20 section) | Current |
| 67-68 tables (Feb 20 + Feb 22 sections) | Current |
| VM details (192.168.64.159, Debian 13) | Current |
| Round correlation system (Feb 22 section) | Current |
| Gemini website redesign (Feb 23 section) | Current |
| SSH: `ssh -i ~/.ssh/slomix_vm_ed25519 slomix@192.168.64.159` | Current |

### Missing Context in memories.md

- No entry documenting that `bot_config.json` contains a live Discord token (security concern)
- No entry for `gemini-website/` React project setup or local dev URL
- `docs/CLAUDE.md` vs root `CLAUDE.md` duplication issue not noted
- Round correlation service is in DRY-RUN mode — not noted in current status

---

## 4. Development Environment Audit

### Python Environment

| Component | Pinned in requirements.txt | Actually Installed | Status |
|-----------|--------------------------|-------------------|--------|
| `discord.py` | 2.3.2 | 2.3.2 | OK |
| `asyncpg` | 0.29.0 | **0.30.0** | [IMPORTANT] Drift |
| `aiosqlite` | 0.19.0 | (not checked) | — |
| `fastapi` | 0.110.3 | 0.110.3 | OK |
| `uvicorn[standard]` | 0.29.0 | **0.38.0** | [IMPORTANT] Drift |
| `httpx` | 0.27.2 | 0.27.2 | OK |
| `paramiko` | 3.4.1 | **4.0.0** | [IMPORTANT] Drift - major version |
| `matplotlib` | 3.9.2 | **3.10.7** | [MINOR] Drift |
| `watchdog` | 4.0.2 | **3.0.0** | [IMPORTANT] Drift - older than pinned |
| `trueskill` | 0.4.5 | 0.4.5 | OK |
| `aiofiles` | 24.1.0 | 24.1.0 | OK |
| `Pillow` | 12.1.1 | (not checked) | — |
| `redis` | 5.1.1 | (not checked) | — |
| `prometheus-client` | 0.21.0 | (not checked) | — |
| `websockets` | 12.0 | (not checked) | — |

**Key findings**:
- `paramiko` 4.0.0 installed vs 3.4.1 pinned — this is a major version bump with API changes
- `watchdog` 3.0.0 installed vs 4.0.2 pinned — installed is OLDER than pinned (environment mismatch)
- `asyncpg` 0.30.0 vs 0.29.0 — minor, but pins exist for reproducibility
- `pyproject.toml` requires `python>=3.11,<3.12` but dev `venv` may be running Python 3.10 (website venv uses 3.10)

### pyproject.toml

- **Version**: `1.0.8` — **differs from CLAUDE.md which says 1.0.6** [IMPORTANT]
- `requires-python = ">=3.11,<3.12"` — correct for bot
- Linting config present (flake8, pycodestyle)
- No build system defined (no `[build-system]` table)

### bot_config.json — [CRITICAL] SECURITY ISSUE

`bot_config.json` at the project root contains:
- A **live Discord bot token** in plaintext
- PostgreSQL password in plaintext (`etlegacy_secure_2025`)

This file **must not be committed to git** and should be added to `.gitignore` immediately. The Discord token should be rotated if this file has ever been committed.

### .claude/settings.json

- Model: `opus-4-6-1m` (latest)
- Permissions allowlist: appropriately scoped (git, pip, pytest, screen, ls, mkdir, curl)
- No agents directory configured
- `enabledPlugins`: `frontend-design@claude-code-plugins: true`

### README Coverage Check

| Project | Has README? | Quality |
|---------|-------------|---------|
| Root (`README.md`) | YES | Present |
| `bot/` | NO | Missing — only has CLAUDE.md |
| `website/` | YES | Present |
| `proximity/` | YES | Has `README.md` and `SLOMIX_PROJECT_BRIEF.md` |
| `greatshot/` | YES | Has `README.md` |
| `gemini-website/` | YES | Has `README.md` |
| `tools/` | NO | Missing |
| `vps_scripts/` | NO | Missing |

---

## 5. Full Directory Tree (Key Paths Only)

```
/home/samba/share/slomix_discord/
├── CLAUDE.md                          # Root guidance (accurate)
├── bot_config.json                    # [CRITICAL] Contains live credentials
├── pyproject.toml                     # version 1.0.8
├── requirements.txt                   # Pinned deps (drift noted above)
├── requirements-dev.txt               # Dev deps
├── pytest.ini                         # Test config
├── install.sh                         # Installation script
├── Makefile                           # Build tasks
├── bot/                               # Main bot package
│   ├── CLAUDE.md                      # Minor drift (20→21 cogs)
│   ├── ultimate_bot.py                # Main entry (~4,990 lines)
│   ├── community_stats_parser.py      # R1/R2 differential parser
│   ├── cogs/                          # 21 cogs (CLAUDE.md says 20 — stale)
│   │   └── CLAUDE.md                  # Stale: missing availability_poll_cog
│   ├── core/                          # 18 core modules
│   │   └── CLAUDE.md                  # Accurate
│   ├── services/                      # 24 services
│   │   └── CLAUDE.md                  # Stale: only lists ~11 services
│   ├── automation/                    # SSH + file tracking
│   │   └── CLAUDE.md                  # Has known-issue noted
│   ├── repositories/                  # Data access layer
│   ├── diagnostics/                   # Debug utilities
│   └── local_stats/                   # Downloaded stats files
├── website/                           # Web frontend/backend
│   ├── backend/                       # FastAPI
│   │   └── CLAUDE.md                  # Minor: missing planning.py router
│   ├── js/                            # Vanilla JS frontend
│   ├── index.html                     # SPA entry
│   └── README.md
├── gemini-website/                    # NEW React/TS frontend (WIP)  [NO CLAUDE.md]
│   ├── src/
│   │   ├── pages/                     # 10 pages
│   │   ├── components/
│   │   └── api/
│   └── vite.config.ts
├── proximity/                         # Proximity tracker   [NO CLAUDE.md]
├── greatshot/                         # Highlight clips     [NO CLAUDE.md]
├── tools/                             # 70+ DB utility scripts [NO CLAUDE.md]
│   ├── schema_postgresql.sql          # Canonical schema (68 tables)
│   └── migrations/                    # 5 migration files
├── vps_scripts/                       # Lua webhook scripts [NO CLAUDE.md]
│   └── stats_discord_webhook.lua      # v1.6.2
├── tests/                             # Test suite
│   └── CLAUDE.md                      # Accurate
├── docs/                              # 100+ documentation files
│   ├── CLAUDE.md                      # Duplicate of root CLAUDE.md
│   ├── archive/                       # Historical docs
│   ├── reference/                     # Reference docs
│   ├── evidence/                      # Session evidence files
│   └── reports/                       # Agent reports (this file)
├── .claude/
│   ├── memories.md                    # Partially stale (noted above)
│   ├── settings.json                  # Model + permissions config
│   └── settings.local.json            # Local overrides
├── analytics/                         # Purpose unclear
├── archive/                           # Old code/scripts
├── backups/                           # Large backup tree (should be gitignored)
└── [50+ miscellaneous root files]     # [CRITICAL] Major clutter
```

---

## 6. Prioritized Recommendations

### [CRITICAL]

1. **Rotate the Discord bot token** — `bot_config.json` contains a live token in plaintext. Check `git log` to determine if this has ever been committed. If so, the token is compromised and must be rotated via Discord Developer Portal immediately.

2. **Add `bot_config.json` to `.gitignore`** — This file contains credentials and must never be committed. Verify it is currently gitignored.

3. **Root directory cleanup** — The project root has 50+ artifact files that do not belong there (SQLite DB files, screenshots, old logs, ad-hoc scripts, validation artifacts, old Lua variants). These need to be moved to appropriate subdirectories or deleted/gitignored.

### [IMPORTANT]

4. **Version number reconciliation** — `pyproject.toml` says `1.0.8`, CLAUDE.md says `1.0.6`. Pick one source of truth and update the other.

5. **Update `/bot/cogs/CLAUDE.md`** — Add `availability_poll_cog.py` to the table; update count from 20 to 21.

6. **Update `/bot/services/CLAUDE.md`** — Add the 13 undocumented services to the reference table.

7. **Add CLAUDE.md for `gemini-website/`** — Active development happening here with no guidance. Should document: React 19 + TypeScript 5.9 + Vite 7 + Tailwind v4 stack, vite proxy config (port 3000 → 8000), current implementation status, and what endpoints are wired vs placeholder.

8. **Add CLAUDE.md for `tools/`** — 70+ scripts with no orientation. Critical scripts (`schema_postgresql.sql`, migration files) need documentation.

9. **Add CLAUDE.md for `vps_scripts/`** — Lua webhook is a critical pipeline component with no directory-level guidance.

10. **Dependency drift** — `paramiko` 4.0.0 installed vs 3.4.1 pinned is a major version bump. Validate no breaking API changes are affecting SSH operations. Update `requirements.txt` to match actual tested versions.

11. **Update memories.md** — The Feb 15 "Architecture Quick Facts" section has multiple stale values (20 cogs, 42 tables, v1.6.0 Lua). Should be updated to reflect Feb 22 confirmed values (21 cogs, 68 tables, v1.6.2 Lua).

### [MINOR]

12. **Resolve `docs/CLAUDE.md` duplication** — Currently identical to root `CLAUDE.md`. Either make it docs-specific guidance or remove it and have only the root CLAUDE.md.

13. **Fix code block formatting in `/bot/CLAUDE.md`** — Mixed language tag/fence issues make code examples hard to read.

14. **Add CLAUDE.md for `proximity/` and `greatshot/`** — Both are sister projects with their own architecture. Directory-level CLAUDE.md would help AI agents orient quickly.

15. **`bot/` missing README.md** — Only has CLAUDE.md. A README visible on GitHub would help contributors.

16. **`tools/` missing README.md** — 70+ scripts need basic documentation of what they do and whether they're still relevant.

17. **`backups/` directory** — Contains large historical backup trees (2025-10, 2025-11, etc.). Should be gitignored if not already.

18. **Round correlation service is in DRY-RUN mode** — Not documented anywhere except commit history. `memories.md` notes it was implemented but does not state it is not yet active. This should be prominently noted.

---

## 7. Summary Table

| Area | Issues Found | Critical | Important | Minor |
|------|-------------|----------|-----------|-------|
| Root clutter | 50+ artifact files | 1 | 1 | 0 |
| Credentials exposure | bot_config.json | 1 | 0 | 0 |
| CLAUDE.md accuracy | 9 files audited | 0 | 3 | 4 |
| CLAUDE.md missing | 7 directories | 0 | 4 | 3 |
| memories.md staleness | Multiple stale entries | 0 | 2 | 3 |
| Dep version drift | 4 packages drifted | 0 | 1 | 2 |
| Version number mismatch | pyproject vs CLAUDE.md | 0 | 1 | 0 |
| **TOTAL** | | **2** | **12** | **12** |

---

*Report generated: 2026-02-23 by discovery-agent (Phase 1)*
