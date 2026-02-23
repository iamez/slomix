# Mega Cleanup & Hardening Prompt

**Created**: 2026-02-23
**Status**: Ready to execute
**Estimated Scope**: Large (multi-agent, multi-phase)

---

## Context

This prompt was distilled from a brainstorm session. It covers project hygiene, architecture mapping, GitHub cleanup, code quality, research, and feature verification. **Nothing gets deleted from local/network drives** — cleanup targets the Git-tracked repository only (via `.gitignore`).

---

## Phase 1: Project Discovery & Environment Setup

### 1A — Explore the full project structure
- Map every directory and subdirectory in the repo
- Identify which folders are missing a `CLAUDE.md` — every meaningful folder should have one
- Audit existing `CLAUDE.md` files for accuracy and completeness
- Check `.claude/memories.md` — is it current? Trim stale entries, add missing context

### 1B — Optimize the development environment
- Verify `.env`, `requirements.txt`, `pyproject.toml` / config files are correct and complete
- Check that all Claude Code settings (`.claude/` directory) are optimal for the project
- Ensure MCP tools, hooks, and any custom agents are properly configured
- Verify the bot, website, proximity, and greatshot subprojects each have proper setup docs

---

## Phase 2: Documentation Audit & Reorganization

### 2A — Full docs review
- Read **every file** in `docs/` (currently 142 files!) and `docs/archive/`
- Identify any forgotten TODOs, unimplemented features, or stale action items
- Flag docs that are outdated, redundant, or contradictory
- Check `docs/KNOWN_ISSUES.md` and `docs/CHANGELOG.md` for completeness

### 2B — Separate AI/Claude instructions from project docs
- Find all files that are primarily AI/Claude/Codex instructions (audit prompts, agent launch cards, system audit prompts, etc.)
- Move them into a new `docs/instructions/` subfolder — these are operational, not project documentation
- Extract any genuinely useful patterns or rules from those instruction files and merge them into `CLAUDE.md` and `.claude/memories.md`

### 2C — Identify docs needed for GitHub README
- Determine which docs are linked from `README.md` or needed for onboarding
- Only those docs should remain Git-tracked (Phase 5 handles the `.gitignore` changes)

---

## Phase 3: Architecture Mapping & Essential Files Inventory

### 3A — Map every feature to its required files
Create a manifest that answers: "Which files are needed for X to work?"

- **Bot**: `bot/ultimate_bot.py`, all 21 cogs, 18 core modules, services, parser, database adapter, etc.
- **Website**: `website/` backend and frontend files
- **Greatshot**: greatshot feature files
- **Proximity**: `proximity/` module files
- **Automation**: SSH monitor, Lua webhook scripts, systemd services
- **Database**: schema files, migration scripts, `postgresql_database_manager.py`
- **Config/Infra**: `.env.example`, `requirements.txt`, `install.sh`, systemd units

### 3B — Identify non-essential files in the repo
- Everything NOT in the manifest from 3A is a candidate for `.gitignore`
- Categories to flag: scratch files, screenshots/images, backup DBs, log files, one-off scripts, analysis outputs, personal notes, `.lua` experiments in root

---

## Phase 4: Technical Debt & Code Quality Scan

### 4A — Full codebase audit
- Scan every Python file for:
  - Dead code / unused imports / unused functions
  - Code duplication that could be consolidated
  - Functions that are too long or too complex (cyclomatic complexity)
  - Missing error handling at system boundaries
  - Hardcoded values that should be config
  - Any remaining SQLite syntax or patterns (should be PostgreSQL only)

### 4B — Security audit
- Check for OWASP top 10 vulnerabilities (SQL injection, XSS, command injection, etc.)
- Verify no secrets/credentials are committed (scan git history too)
- Review CSP headers, auth flows, input validation
- Check SSH key handling and bot token management

### 4C — Performance review
- Database query efficiency (missing indexes, N+1 queries, unnecessary full-table scans)
- Caching effectiveness (`stats_cache.py` — is the 5-min TTL optimal?)
- Bot startup time and memory usage patterns
- Any blocking calls in async code paths

### 4D — Algorithm & pipeline improvements
- Look for functions that could be replaced with better algorithms
- Check the data pipeline (SSH → Parser → DB → Bot → Discord) for bottlenecks
- Review the round-matching logic, session detection, and R2 differential calculation
- Suggest any architectural improvements

---

## Phase 5: GitHub Repository Cleanup

### 5A — Clean up `.gitignore`
- Build a comprehensive `.gitignore` based on the Phase 3 manifest
- Ignore: all scratch files, images/screenshots, backup DBs, logs, one-off scripts, analysis outputs, personal notes, `.lua` experiments, build artifacts
- Keep tracked: only files required for the project to build and run, plus README-linked docs
- **DO NOT delete anything from local/network drive** — only untrack from Git

### 5B — Prevent future clutter
- Set up pre-commit hooks or CI checks that warn on commits of non-essential files
- Document the "what to commit" policy in `CONTRIBUTING.md`
- Consider a root-level `PROJECT_FILES.md` manifest that lists every tracked file and its purpose

---

## Phase 6: Research & Benchmarking

### 6A — Similar projects on GitHub
- Search for ET:Legacy stat tracking bots / Discord integrations
- Search for game stats parsers, round/match tracking systems
- Search for similar website dashboards for game stats
- Look at how similar projects handle: database schemas, stat parsing, team detection

### 6B — Open source components
- Are there existing libraries/tools for any of our features?
  - Stats parsing, CSV/log ingestion
  - Discord bot frameworks with built-in pagination, caching, etc.
  - Web dashboard templates for game stats
  - Database management / migration tools
- Can we extract better patterns or more efficient implementations from these?

---

## Phase 7: Feature-Specific Verification

### 7A — Proximity data capture validation
- **Critical check**: Verify proximity is ONLY capturing data during live gameplay rounds
- Must NOT capture during: intermission, warmup, map loading, or between rounds
- Trace the data flow from game server → proximity capture → database
- Verify the filtering logic and timestamps

---

## Execution Notes

- **Agent teams**: Use multiple specialized agents in parallel where phases are independent (e.g., Phase 4 and Phase 6 can run simultaneously)
- **Local drive safety**: NOTHING gets deleted from the local filesystem. All cleanup is Git-level only (`.gitignore` + `git rm --cached`)
- **Output**: Each phase should produce a findings report. Critical issues get filed as TODOs in `docs/KNOWN_ISSUES.md`
- **Incremental commits**: Each phase's changes should be on a feature branch, committed separately with conventional commit messages
