# Codex Full Project Audit - 2026-02-03

This is a comprehensive, long-form audit of the Slomix ET:Legacy stats bot repository. It focuses on correctness, data integrity, runtime reliability, ops/security, and maintainability. The report includes findings by severity, concrete file references, and a prioritized remediation roadmap.

---

## 0) Executive Summary (TL;DR)

**Strengths**
- Strong end-to-end pipeline concept with multiple data sources (stats files + Lua webhook + endstats).
- Significant documentation coverage and operational knowledge captured in `/docs`.
- A real attempt at data integrity (multiple validation layers, defensive SQL, and verification tooling).
- Clear separation into service-style modules for many features (scores, graphs, timing comparison).

**Project maturity**
- The bot is a working prototype (in active development for ~3+ months) with a primary data flow that already works.
- Website and proximity components are early prototypes and not yet production-grade.

**Top Risks**
1. **Webhook timing still missing** ("NO LUA DATA") indicates real-time webhook data isn’t reliably stored or matched, blocking key surrender timing fixes and forcing fallback to stats files.
2. **Multiple sources of truth for timing and scoring** are still inconsistent (independent round scoring vs. map winner scoring; match_id mismatch between stats and Lua webhook).
3. **Session/team data uses date-based keys** in several places despite `gaming_session_id` being the correct grouping abstraction, leading to midnight crossover or repeated-map pairing issues.
4. **Operational secrets are stored in repo** (`.env`, webhook URLs, SSH configs), and multiple large backup/log files are present in the repo, increasing exposure and operational risk.
5. **Large monolith logic in `bot/ultimate_bot.py`** still handles too many responsibilities; tricky to reason about, easy to regress, and complicates testing.

**Overall health**: The project is impressive in scope and functional depth, but still at risk of subtle correctness bugs (teams, scores, timing) and operational exposure (secrets/logs in repo). The architecture is close to robust but needs cleanup to make correctness provable and operations safer.

---

## 1) System Overview (As Implemented)

**Core components**
- **Game server**: ET:Legacy writes stats files; custom Lua scripts (`c0rnp0rn7.lua`, `endstats.lua`, `stats_discord_webhook.lua`).
- **Discord bot**: Python (async), working prototype with services for parsing, aggregation, posting, scoring, and timing comparisons.
- **Database**: PostgreSQL (primary), with legacy SQLite traces; multiple databases and backups in repo.
- **Website**: FastAPI + frontend JS (early prototype), queries PostgreSQL read-only.
- **Proximity**: Optional Lua-based tracking (early prototype).

**Primary data flows**
1. **Stats files (c0rnp0rn7.lua)** → webhook trigger (avoid polling) → SSH download → parser → `rounds` + `player_comprehensive_stats`
2. **Lua webhook (stats_discord_webhook.lua)** → Discord webhook → bot → `lua_round_teams`
3. **Endstats files (endstats.lua)** → parser → awards/VS stats tables
4. **Comparison/validation** → timing debug and comparison services

**Key tension**: Stats files provide per-player data, but have **surrender timing inaccuracies** (wrong time means wrong stats). Lua webhook provides accurate timing but no per-player stats. The system must merge these cleanly.

---

## 2) Findings by Severity

### Critical

**C1) Lua webhook data is not being stored or matched ("NO LUA DATA")**
- Symptom: Discord shows “No Lua data available” and “Webhook may not have triggered”.
- Impact: Surrender timing fixes and round-level timing verification cannot work.
- Evidence: Timing debug/compare embeds show missing Lua data.
- Likely causes:
  - Webhook not firing (gamestate detection still failing or script not loaded).
  - Webhook firing but bot not receiving or storing data (whitelist, channel mismatch, DB error).
  - Stored data exists but matching logic fails (match_id mismatch, map/round/time mismatch).
- Status note: This is still unresolved. The immediate goal is for the Lua webhook to capture and report accurate timing for all phases so comparison can work reliably.
- Files:
  - `vps_scripts/stats_discord_webhook.lua`
  - `bot/ultimate_bot.py` (`_process_stats_ready_webhook`, `_store_lua_round_teams`)
  - `bot/services/timing_comparison_service.py`

**C2) Two competing scoring models are used across the codebase**
- `docs/TEAM_AND_SCORING.md` describes independent per‑round scoring (each round gives 1 point). `docs/STOPWATCH_IMPLEMENTATION.md` describes map winner logic (R2 beats R1 time etc.).
- The runtime scoring in `StopwatchScoringService` now matches independent per‑round scoring, but other docs and older logic expect map-win scoring.
- Impact: Users may see scores that appear “wrong” depending on the stopwatch interpretation.
- Status note: Team confirmed scoring was likely botched in earlier logic; current behavior should be treated as the source of truth until the docs are reconciled.
- Files:
  - `docs/TEAM_AND_SCORING.md`
  - `docs/STOPWATCH_IMPLEMENTATION.md`
  - `bot/services/stopwatch_scoring_service.py`

**C3) Session team data is keyed by date instead of `gaming_session_id` in multiple places**
- This risks wrong team lookup when sessions cross midnight or when multiple sessions occur on same day.
- The correct key is `gaming_session_id` (documented as canonical).
- Files:
  - `bot/services/session_data_service.py` (queries by date)
  - `bot/core/team_manager.py` (stores by date, optional session id)
  - `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` (states gaming_session_id is the right key)

---

### High

**H1) Webhook → stats file matching is brittle for repeated maps**
- `_fetch_latest_stats_file` matches on map+round then picks the newest filename.
- If the same map is played multiple times in a session, the webhook could pair with the wrong file.
- File: `bot/ultimate_bot.py` (`_fetch_latest_stats_file`)

**H2) Match ID mismatch between stats files and Lua webhook is a known structural conflict**
- `rounds.match_id` uses file timestamp (round start). `lua_round_teams.match_id` uses round end timestamp.
- Current match uses fuzzy matching in timing comparison services; this is fragile and potentially wrong.
- Files:
  - `bot/services/timing_comparison_service.py`
  - `docs/reference/TIMING_DATA_SOURCES.md`

**H3) Operational secrets in repo**
- `.env` exists in the repo and appears to contain secrets (webhook URLs, credentials). The Lua webhook file includes an inline Discord webhook URL.
- Public repo risk: anyone with access to repo could post to Discord webhook.
- Status note: This is an accepted risk for now to enable AI agents and SSH workflows. It should remain clearly documented as a conscious tradeoff.
- Files:
  - `.env`
  - `vps_scripts/stats_discord_webhook.lua`

**H4) Monolithic orchestration remains in `bot/ultimate_bot.py`**
- This file handles parsing, DB inserts, webhook logic, file fetching, publishing, etc.
- The size and responsibilities increase regression risk, especially around subtle timing/round behavior.
- File: `bot/ultimate_bot.py`

---

### Medium

**M1) `session_teams` schema variability is handled ad‑hoc**
- Some code assumes `color`/`gaming_session_id` columns exist, others do not.
- The recent local changes made handling safer, but the schema is still inconsistent across environments.
- Files:
  - `bot/core/team_manager.py`
  - `CURRENT_DB_SCHEMA.txt` (shows limited columns)

**M2) Multiple databases and backup artifacts are stored in repo**
- Many `.db` and `.sql` backups are present at repo root (some large). This increases storage and security risk.
- Suggest moving backups to a separate secure storage and `.gitignore` them.

**M3) Two Python virtual environments in repo (`.venv` + `venv`)**
- Confusing for deployments and can lead to wrong dependencies being used.

**M4) Some scripts and services are marked deprecated but still present**
- Deprecated websocket support and monitoring logic are still in code.
- Risk: confusing operational behavior, or accidental re‑enable of deprecated features.
- Files:
  - `bot/config.py`
  - `bot/ultimate_bot.py`

**M5) The Lua webhook script uses `os.execute(curl ...)`**
- No retries, no response parsing, silent failure if curl missing.
- For reliability, consider logging curl exit status or verifying `curl` exists.
- File: `vps_scripts/stats_discord_webhook.lua`

**M6) Pending metadata cache is unused**
- `_pending_round_metadata` is set but never read, which suggests an incomplete design or obsolete feature.
- File: `bot/ultimate_bot.py`

---

### Low

**L1) Hard-coded debug logging**
- Several services log time debug at INFO/DEBUG by default, which can be noisy in production.
- Files: `bot/logging_config.py`, `bot/community_stats_parser.py`, `bot/ultimate_bot.py`.

**L2) Website known TODOs are not tracked outside README**
- There’s a clear TODO list in `website/README.md`, but no formal tracking in issues.

**L3) Multiple copies of config/docs**
- There are multiple versions of guides and overlapping docs; this increases cognitive load but not critical.

---

## 3) Component Review

### 3.1 Bot Ingest & Parsing

**Strengths**
- Parses complex c0rnp0rn format and handles R2 differential values.
- Extensive validation and safety checks described in docs.

**Risks**
- R2 differential logic is sensitive; already required multiple fixes.
- Header data for R2 is missing and requires inheritance, which can fail if matching logic is wrong.
- Parser is large and hard to unit test thoroughly.

**Key Files**
- `bot/community_stats_parser.py`
- `bot/ultimate_bot.py` (import logic, metadata override)

### 3.2 Team Detection & Roster Consistency

**Strengths**
- Dedicated TeamManager logic now supports incremental team tracking.
- Auto assignment from R1 works if data is correct.

**Risks**
- Sessions crossing midnight still risk mis‑matching teams when queried by date.
- Manual override commands exist but bypass auto detection logic if used improperly.

**Key Files**
- `bot/core/team_manager.py`
- `bot/services/session_data_service.py`
- `bot/cogs/team_management_cog.py`

### 3.3 Scoring

**Strengths**
- Scoring logic is centralized in `StopwatchScoringService` for async Postgres.
- Team‑aware scoring attempts to map side to persistent teams.

**Risks**
- Conflicting scoring interpretation (per‑round vs map‑win).
- Team‑aware mapping may still be wrong for repeated maps or team splits.

**Key Files**
- `bot/services/stopwatch_scoring_service.py`
- `docs/TEAM_AND_SCORING.md`
- `docs/STOPWATCH_IMPLEMENTATION.md`

### 3.4 Lua Webhook Timing

**Strengths**
- Captures accurate timing on surrender.
- Captures team composition at round end.

**Risks**
- Still not showing in Discord → likely not firing or storing.
- Relies on `curl` with no fallback or acknowledgment.
- Match ID mismatch makes linking with stats files fragile.

**Key Files**
- `vps_scripts/stats_discord_webhook.lua`
- `bot/ultimate_bot.py`
- `bot/services/timing_comparison_service.py`

### 3.5 Ops & Deployment

**Strengths**
- Extensive deployment and recovery docs.
- Clear runtime checklist in `docs/`.

**Risks**
- Game server is managed via `screen`/scripts, but some docs mention systemd.
- Service names are inconsistent across docs (`et-bot`, `etlegacy-bot`, `et-stats-webhook`).
- Secrets in repo are a real security concern.

**Key Files**
- `docs/GAMESERVER_CLAUDE.md`
- `docs/DEPLOYMENT_GUIDE.md`
- `.env`, `vps_scripts/stats_discord_webhook.lua`

### 3.6 Website/API

**Strengths**
- Clear README, security notes, read‑only DB setup.
- Reasonable performance notes.

**Risks**
- Missing features and incomplete TODOs; some pages are placeholders.
- Large frontend JS file (~1750 lines) may be a maintenance risk.

**Key Files**
- `website/README.md`
- `website/backend/routers/api.py`
- `website/js/app.js`

---

## 4) Security & Secrets

**High Risk Items**
- `.env` file exists in repo root and likely contains tokens/passwords.
- Lua webhook URL is hard‑coded in `vps_scripts/stats_discord_webhook.lua`.
- Multiple DB backups and logs stored in repo (possible sensitive data).

**Recommendations**
- Remove `.env` from repo, rotate all webhook URLs and DB passwords.
- Move backups to secured storage; keep only metadata in repo.
- Add `.env` and backups to `.gitignore` and confirm they’re not committed.

---

## 5) Data Integrity & Schema Consistency

**Observations**
- There are multiple databases, schema dumps, and backups in the repo.
- `session_teams` table schema appears inconsistent across environments.
- Some scripts assume JSONB and asyncpg behavior, others assume SQLite.

**Risks**
- Inconsistent schema leads to runtime errors or silent data loss.
- Manual fixes may diverge from automated imports.

**Recommendations**
- Freeze a single canonical schema and apply migrations systematically.
- Reduce or eliminate SQLite logic if PostgreSQL is the sole backend.

---

## 6) Code Quality & Maintainability

**Strengths**
- Service-based modules for key responsibilities.
- Reasonable naming and structured logic.

**Risks**
- `bot/ultimate_bot.py` is a large monolith (hard to test or refactor safely).
- Many features are “semi-integrated” (deprecated services still present).
- Debug logic is scattered across services.

**Recommendations**
- Continue extracting logic into services and use dependency injection.
- Consolidate debug output toggles in one place.

---

## 7) Testing & Validation

**Strengths**
- Many scripts and validation reports exist.
- Coverage artifacts present.

**Risks**
- Automated test execution isn’t clearly part of deployment.
- Many fixes rely on manual SQL or manual re-import.

**Recommendations**
- Create a minimal regression suite that covers:
  - Team detection correctness
  - Scoring correctness on known sample sessions
  - Lua webhook ingestion matching

---

## 8) Performance & Scalability

**Strengths**
- SSH monitoring was optimized to reduce constant polling.
- Data services generally use aggregated queries.

**Risks**
- Large DB tables with unoptimized queries can degrade as data grows.
- Fuzzy matching in Lua timing comparison is O(N) on recent rows, likely OK but could be optimized.

**Recommendations**
- Ensure proper indices on `rounds`, `player_comprehensive_stats`, and `lua_round_teams`.
- Add query limits with deterministic ordering on any reporting endpoints.

---

## 9) Recommended Roadmap (Prioritized)

### Immediate (Next 1–3 days)
1. Fix Lua webhook reliability (“NO LUA DATA”). Verify logs on server and DB writes.
2. Decide and document scoring model (per‑round vs map‑win). Apply consistently.
3. Remove secrets and rotate webhook URLs.

### Short-Term (1–2 weeks)
1. Replace date-based team lookups with `gaming_session_id`.
2. Improve webhook stats file matching with timestamp tolerance.
3. Consolidate and trim deprecated services/configs.

### Medium-Term (1–2 months)
1. Migrate fully to PostgreSQL (remove SQLite compatibility code).
2. Modularize `ultimate_bot.py` into smaller services.
3. Create a proper regression test suite for teams/scoring/timing.

---

## 10) Local Changes Already Applied (for Revert)

A dedicated log of changes made in this workspace exists here:
- `docs/SESSION_2026-02-03_CHANGELOG_LOCAL.md`

---

## 11) Appendix: Quick Fix Opportunities

- Add a `gametimes/` timing file output in `stats_discord_webhook.lua` (plan already drafted).
- Store webhook metadata with a unique key that includes timestamp + map + round to prevent collisions.
- Add a “debug summary” command in Discord for last Lua webhook seen.

---

## 12) Appendix: Prototype UI + Proximity API Stubs (2026-02-03)

- Added prototype banner support in the SPA so each view can self-label partial data.
- Home and Proximity views now carry prototype banner metadata and render a banner slot.
- Added FastAPI proximity endpoints (`/api/proximity/*`) that return safe placeholder data with `status`, `ready`, and `message`.
- Proximity frontend now respects the readiness flag and displays a prototype state message.

---

## 13) Appendix: Map-Winner Scoring Applied (2026-02-03)

- Stopwatch scoring was switched to **map‑winner by time** to match Superboyy outputs.
- Map wins now score **1 point per map** (tie when no completion/unknown).
- Tie-break for equal completion times goes to Round 1 attackers.
- Round 2 parser now retains header `winner_team` to support header-based map wins.
- Added `!last_session debug` to show per-map side mapping and scoring source.

---

## 14) Appendix: Endstats Pagination (2026-02-03)

- Replaced the single cumulative endstats embed with paginated endstats output.
- Map View (default) shows Round 1 + Round 2 awards per map with top VS lines.
- Round View (toggle) shows per‑round awards with a longer list + VS stats.
- Added `bot/core/endstats_pagination_view.py` for first/prev/next/last + map/round toggle buttons.

---

If you want, I can expand this report further with line‑level notes, schema diagrams, and a dedicated “test checklist” section. I can also generate a "Revert Script" section that lists exact git restore commands by file.
