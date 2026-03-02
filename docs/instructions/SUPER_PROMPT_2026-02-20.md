run/enable teams, agentic teams, sub agents, agents to execute this prompt, its a big one so read it carefully, this is basicly what we need to fix, gl: 

# SUPER PROMPT: Slomix ET:Legacy Discord Bot — Master Fix-It Guide

> **Generated**: 2026-02-20 | **Updated**: 2026-02-21 (rev3) | **Sources**: 51 documentation files + KNOWN_ISSUES.md | **Version**: 1.0.6
> **Verified**: Cross-checked against actual codebase by 5 parallel verification agents
> **Purpose**: Single authoritative document for an AI agent to understand the ENTIRE system state
> and execute ALL remaining fixes in priority order.
>
> **Verification Notes**: Line numbers, formulas, and file paths have been verified against
> the actual codebase. Key corrections applied: Lua webhook pcall already exists (not missing),
> parser field 9 already implemented (Phase 3 removed), endstats.lua line numbers corrected
> (+78 offset), greatshot skill_rating handling already exists (investigate remaining error path).
>
> **Important**: Also consult `docs/KNOWN_ISSUES.md` for additional historical investigations,
> edge cases, and timing-related findings that may inform fixes in this document.

---

## TABLE OF CONTENTS

1. [System Identity & Architecture](#1-system-identity--architecture)
2. [The Story So Far](#2-the-story-so-far)
3. [Current System Health](#3-current-system-health)
4. [Master Issue Registry](#4-master-issue-registry)
5. [Critical Fix Queue (Ordered)](#5-critical-fix-queue-ordered)
6. [Formula Correction Guide](#6-formula-correction-guide)
7. [Lua Pipeline Fix Guide](#7-lua-pipeline-fix-guide)
8. [Website Fix Guide](#8-website-fix-guide)
9. [Infrastructure & Ops Guide](#9-infrastructure--ops-guide)
10. [Git/Branch Cleanup Guide](#10-gitbranch-cleanup-guide)
11. [Future Features (Planned, Not Started)](#11-future-features-planned-not-started)
12. [Validation Playbook](#12-validation-playbook)
13. [Critical Rules (Never Violate)](#13-critical-rules-never-violate)

---

## 1. SYSTEM IDENTITY & ARCHITECTURE

### What Is Slomix?

A Discord bot + website ecosystem that tracks player statistics for the ET:Legacy
(Enemy Territory) FPS game. It ingests endgame stats files from the game server,
parses them, stores them in PostgreSQL, and serves them through Discord commands
and a web dashboard.

### Architecture Diagram

```
ET:Legacy Game Server (puran.hehe.si:48101)
├── Stats Files (.txt)          → SSH Monitor (60s poll) → Parser → PostgreSQL
├── Lua Webhook (v1.6.2)        → HTTP POST → Bot webhook handler → PostgreSQL
├── Lua Proximity (v4.2, active) → _engagements.txt → SSH Monitor → ProximityParserV4 → PostgreSQL
└── Lua Endstats (endstats.lua) → Stats Files → SSH Monitor → Parser → PostgreSQL

PostgreSQL (localhost:5432, db: etlegacy, user: etlegacy_user)
├── 41 tables, 53+ columns in player_comprehensive_stats
├── Key tables: rounds, player_comprehensive_stats, weapon_comprehensive_stats,
│   lua_round_teams, lua_spawn_stats, gaming_sessions, endstats
└── Schema: tools/schema_postgresql.sql

Discord Bot (bot/ultimate_bot.py)
├── 21 Cogs in bot/cogs/
├── 18 Core modules in bot/core/
├── Services in bot/services/
├── 80+ slash commands
└── Runs in screen session "slomix" (or systemd slomix-bot on VM)

Website (website/)
├── FastAPI backend (port 7000 on VM, port 8000 on Samba)
├── Vanilla JS SPA frontend (27 JS files)
├── Cloudflare Tunnel → https://www.slomix.fyi
└── Discord OAuth for authentication
```

### Key Infrastructure

| Component | Location | Access |
|-----------|----------|--------|
| Game Server | `puran.hehe.si:48101` (IP: `91.185.207.163`) | SSH as `et`, key: `~/.ssh/etlegacy_bot` |
| VM (Production) | `192.168.64.159` | SSH as `samba`, key: Ed25519 |
| Samba (Dev) | Local network share `/home/samba/share/slomix_discord` | Direct filesystem |
| Database | `localhost:5432` on both VM and Samba | User: `etlegacy_user` |
| GitHub | `iamez/slomix_discord` | Main branch protected |
| Domain | `https://www.slomix.fyi` | Cloudflare Tunnel |

### File Map (Critical Files)

| Purpose | File |
|---------|------|
| Bot entry point | `bot/ultimate_bot.py` (~4,941 lines) |
| Stats parser | `bot/community_stats_parser.py` |
| DB manager | `postgresql_database_manager.py` |
| DB adapter (async) | `bot/core/database_adapter.py` |
| Lua webhook (game server) | `vps_scripts/stats_discord_webhook.lua` |
| Lua stats writer (game server) | Game server's `c0rnp0rn7.lua` (916 lines, deployed) |
| Lua stats test (repo) | `c0rnp0rn-testluawithtimetracking.lua` (843 lines, NOT deployed) |
| Lua endstats (game server) | `endstats.lua` |
| Website API | `website/backend/routers/api.py` |
| Website admin | `website/js/admin-panel.js` (~5,624 lines) |
| Timing shadow service | `bot/services/session_timing_shadow_service.py` |
| Session embed builder | `bot/services/session_embed_builder.py` |
| Greatshot crossref | `website/backend/services/greatshot_crossref.py` |
| FragPotential calc | `bot/core/frag_potential.py` |
| Stats cache | `bot/core/stats_cache.py` (5-min TTL) |

---

## 2. THE STORY SO FAR

### Timeline

**Oct-Nov 2025**: Bot created, SQLite database, basic stats parsing.
**Dec 2025**: Migrated from SQLite to PostgreSQL. 41 tables.
**Jan 2026**: Website created. FastAPI + vanilla JS SPA. Upload library, availability polls.
**Feb 1-10 2026**: Expanded to 21 cogs, 80+ commands. Lua webhook v1.6.0 deployed.
**Feb 11-16 2026**: Two-week sprint executed. 43/43 tasks completed (9 days early).
  - WS0 Score Truth Chain, WS1 Webhook Pipeline, WS1B Contract, WS1C Proximity,
    WS2 Timing, WS3 Team Display, WS4 Security, WS5 Docs, WS6 Greatshot, WS7 Kill-Assists.
**Feb 16 2026**: Live session validation (gaming_session_id=89). Found 3 bugs, fixed all.
  - Column cache stale, false restart detection, Lua row mislinked.
**Feb 18 2026**: Deep investigation day.
  - Discovered R2 webhook crash root cause (fractional timelimit `%d` format).
  - Discovered endstats file splitting bug (timestamp-per-call in `send_table()`).
  - System log audit: 15 bot restarts, DNS failures, greatshot schema drift.
  - Timing shadow service implemented and deployed (dual OLD/NEW display).
  - PR #37 merged. CI/Docker/Release-Please foundation in place.
  - 9 investigation documents produced.
**Feb 19 2026**: Availability system completed (stages 0-5). Line-by-line audit closed
  14/14 findings. C0RNP0RN7 LuaJIT patching done (8 issues fixed). Proximity closeout.
**Feb 20 2026**: VM migration completed (192.168.64.159). Deep dive audit.
  - Formula research: headshot %, FragPotential, survival rate, damage efficiency all wrong on website.
  - Pipeline gap analysis: 7 gaps identified with 6-phase fix plan.
  - VM healthy: all endpoints working, Discord OAuth functional, HTTPS via Cloudflare.

### Current State Summary

- **Parser**: 100% functional. R2 differential validated. Field 9 (actual playtime) already parsed but not used.
- **Database**: PostgreSQL, 41 tables, no corruption. 1,034 rounds, 32 players, 90 sessions.
- **Bot**: 80+ commands, 21 cogs, all functional. Timing shadow service running.
- **Website**: Operational on VM. Most endpoints working. Formula bugs in display layer.
- **Lua Pipeline**: R1 works perfectly. R2 crashes on fractional timelimit (CRITICAL).
- **Git**: Main branch behind. Feature branch months ahead. Merge conflicts exist.
- **VM**: Healthy, deployed, accessible. First proper GitHub-based deploy not yet done.

---

## 3. CURRENT SYSTEM HEALTH

### What's Working

- Stats file parsing (R1 and R2 differential) ✅
- PostgreSQL database (41 tables, no corruption) ✅
- All 80+ Discord commands ✅
- Website API endpoints (status, stats, sessions, uploads, proximity, hall-of-fame) ✅
- Discord OAuth login/logout ✅
- HTTPS via Cloudflare Tunnel ✅
- Timing shadow service (dual display) ✅
- Availability system (stages 0-5) ✅
- Lua webhook R1 delivery ✅
- Proximity data pipeline (SSH download + auto-import) ✅ (fixed 2026-02-21)
- Proximity tracker v4.2 FULL deployed to game server ✅ (2026-02-21, REACTION_METRICS now active)
- CI pipeline (ruff, pytest, JS lint, CodeQL) ✅

### What's Broken or Degraded

| Issue | Severity | Impact |
|-------|----------|--------|
| R2 Lua webhook crash | CRITICAL | 50% of rounds lose metadata |
| Website formula bugs (4 metrics) | HIGH | Users see wrong numbers |
| Headshot leaderboard mixed units | HIGH | Rankings meaningless |
| Greatshot demo upload broken | HIGH | Feature non-functional |
| Endstats file splitting | HIGH | R2 achievements lost |
| Bot retry progression deadlocked | HIGH | Unresolved endstats stuck |
| Greatshot `skill_rating` schema drift | HIGH | Silent data loss |
| Auto debug time comparison post missing | RESOLVED | Requires `!last_session graphs` command — not automatic |
| Proximity SSH download filter bug | NEEDS AUDIT | Fixed `_engagements` suffix 2026-02-21 — audit for other missing suffixes/patterns in allowlist |
| Proximity tracker REACTION_METRICS | NEEDS AUDIT | Full v4.2 deployed 2026-02-21 — verify data populates after next session; audit parser, DB table, website endpoint end-to-end |
| gametime-*.json SSH allowlist rejection | CRITICAL | 100% of gametime files silently rejected — all per-player time data lost since deployment |
| Proximity round_number always stored as 1 | HIGH | All proximity R2s mislabeled as R1 — breaks per-round proximity queries |
| Round linker timing race (endstats before import) | MEDIUM | First pass always fails, resolves on retry — noisy logs, no data loss |
| Webhook ghost round (7s te_escape2) | MEDIUM | Real 7s round, dedup handled it correctly — junk row remains in lua_round_teams |
| ~~erdenberg_t2 R2 stats file missing~~ | RESOLVED | Was a query bug — R2 is in DB as round_date=2026-02-21 (after midnight) |
| ~~Supply timing discrepancy vs demo~~ | RESOLVED | Internal sources correct — surrenders at 659s/753s confirmed in logs; demo measures wall-clock not round time |
| Git branches out of sync | MEDIUM | Deploy risk |
| Samba+VM dual bot responses | INTENTIONAL | Two instances expected — dev (Samba) + prod (VM) |
| Deprecated `et-stats-webhook.service` | MEDIUM | Race conditions |
| Duplicate `log_monitor.sh` processes | MEDIUM | Resource waste |
| time_played_seconds per-player wrong | MEDIUM | Partial players inaccurate |
| Bot restart churn (15/day) | MEDIUM | Unknown root cause |
| DNS/SSH resilience | LOW | Transient, self-recovering |
| Warning fatigue (174 warnings/day) | LOW | Noise obscures real issues |

---

## 4. MASTER ISSUE REGISTRY

### Issue ID Format: `[SEVERITY]-[CATEGORY]-[NUMBER]`

#### CRIT-LUA-001: R2 Webhook Crash on Fractional Timelimit
- **File**: `vps_scripts/stats_discord_webhook.lua`
- **Root Cause**: Multiple `%d` format specifiers used with potentially fractional values:
  - **Line 827**: `string.format("...%d...", time_limit_seconds)` — `time_limit_seconds = time_limit * 60` (line 822), fractional when timelimit is fractional (e.g., `7.374583` in stopwatch R2)
  - **Line 910**: `%d` used with `total_pause_seconds` — accumulated from fractional `pause_duration` calculations (line 1087)
- **Impact**: ALL R2 webhook data lost. No `STATS_READY`, no `lua_round_teams` row, no `lua_spawn_stats`.
- **Evidence**: Rounds 9874, 9877 confirmed missing. Server log: `bad argument #9 to 'format'`
- **NOTE**: The webhook function already HAS a `pcall()` wrapper (line 804) and properly resets `send_in_progress` (line 989). The crash occurs INSIDE the pcall, so the flag resets correctly, but the webhook data is still lost for that round.
- **Fix**: Wrap all `%d` arguments in `math.floor()` — specifically `time_limit_seconds` (line 827) and `total_pause_seconds` (line 910). Do NOT add redundant pcall or flag reset (already exist).
- **Blocks**: All R2 Lua-dependent improvements

#### HIGH-LUA-002: Endstats File Splitting (Timestamp-per-Call)
- **File**: `endstats.lua` (repo root: `/home/samba/share/slomix_discord/endstats.lua`)
- **Line**: 1459 in `send_table()` (NOT 1380 as some docs claim — line numbers are ~78 higher than originally documented)
- **Root Cause**: Each `send_table()` call generates filename from `os.date('%Y-%m-%d-%H%M%S-')` at line 1459. If wall-clock second changes between calls, files split.
- **Key lines**: Awards `send_table()` at line 714, per-player VS `send_table()` at line 762, file write at lines 1460-1473
- **Impact**: Bot processes smaller file first, loses awards/achievements for that round.
- **Evidence**: Round 9874 (etl_adlernest R2) produced two files: 39-line (27 awards) + 6-line (0 awards). Bot used 6-line file.
- **Fix**: Generate one stable filename per round, append all data to it.

#### HIGH-LUA-003: Endstats Generation Fragility (Surrender)
- **File**: `endstats.lua` (repo root: `/home/samba/share/slomix_discord/endstats.lua`)
- **Lines**: 874-892 (NOT 796-807 as some docs claim — offset +78)
- **Root Cause**: Exact string matching for exit condition at line 874-885 (`text == "Exit: Timelimit hit.\n"`, `text == "Exit: Allies Surrender\n"`, etc.). Sets `kendofmap = true` at line 885.
- **Impact**: supply R2 on 2026-02-18 had stats file but NO endstats file.
- **2026-02-20 Session Findings (server-file-checker agent, 2026-02-21)**:
  - **supply R1 (21:08 match, match #2 of the session)**: c0rnp0rn stats file exists on server. Endstats file does NOT exist on server. Endstats generation failed for this round — likely a surrender that `kendofmap` missed.
  - **sw_goldrush_te R1 (23:05 match)**: Same — c0rnp0rn stats file exists. Endstats file does NOT exist. Same root cause.
  - These 2 rounds are missing endstats/awards data permanently (files were never generated on the server, so bot could never download them).
  - **Aborted supply match #1** (session start, ~20:27): A single R1 file exists, 632 bytes (~72-second match). No R2, no endstats. Server-side abort (barely started). Not a pipeline failure — game was cut short before completion.
- **Fix**: Replace exact string matching with robust pattern matching; add structured logging.

#### HIGH-LUA-004: Lua File Split (Time Tracking Not Deployed)
- **Files**:
  - `c0rnp0rn7.lua` (deployed, 916 lines, LuaJIT-compatible via `ensure_bit_compat()`, NO time tracking)
  - `c0rnp0rn7new.lua.lua` (repo root, 843 lines, developer-provided 2026-02-21, HAS time tracking + field 9, uses Lua 5.3 operators `>>` `<<` `|` `&` — NOT LuaJIT-compatible, will crash on game server as-is)
- **What the new dev file adds**: `roundStart`, `roundEnd`, `pausedTime[]` globals; field 9 in header (`roundEnd-roundStart-(pausedTime[3] or 0)`); pause detection via `cs` bitmask `(1 << 4)`
- **Impact**: Per-player time tracking (header field 9, pause awareness) not in production.
- **Fix**: Merge `c0rnp0rn7new.lua.lua` (time tracking) with LuaJIT patches from deployed `c0rnp0rn7.lua`. Replace all Lua 5.3 operators with `bit.*` calls from `ensure_bit_compat()`.
- **LuaJIT Patches Needed**: In new file, replace `>>` → `bit.rshift()`, `<<` → `bit.lshift()`, `|` → `bit.bor()`, `&` → `bit.band()`. Keep `ensure_bit_compat()`, `ensure_max_clients()`, `to_int()` from deployed version.
- **CRITICAL**: Do NOT deploy `c0rnp0rn7new.lua.lua` as-is — it will crash LuaJIT on the game server.
- **Output target**: Merged file deployed as `/home/et/etlegacy-v2.83.1-x86_64/legacy/c0rnp0rn7.lua`

#### HIGH-BOT-001: Webhook Retry Self-Block
- **File**: `bot/ultimate_bot.py` (lines 4721-4754, 4815)
- **Root Cause**: Active task marker + re-schedule pattern creates deadlock. Retry never advances past 1/5.
- **Impact**: Unresolved endstats may only attempt once.
- **Fix**: Fix active task marker logic; allow retry progression 1/5 → 2/5 → 3/5 → 4/5 → 5/5.

#### HIGH-BOT-002: Same-Round Duplicate Quality Selection
- **File**: `bot/ultimate_bot.py`
- **Root Cause**: When split endstats files exist (HIGH-LUA-002), bot dedupes by round_id and uses whichever succeeds first, not whichever is richer.
- **Impact**: Sparse 6-line file overwrites rich 39-line file with awards.
- **Fix**: Compare candidate payloads (awards count + VS count + bytes); prefer richer.

#### HIGH-WEB-001: Website Formula Divergence (4 Metrics)
- **File**: `website/backend/routers/api.py`
- **Details**: See [Section 6: Formula Correction Guide](#6-formula-correction-guide)
- **Impact**: Bot and website show different numbers for same stats. Users confused.

#### HIGH-WEB-002: Headshot Leaderboard Mixed Units
- **File**: `bot/cogs/leaderboard_cog.py:587, 824`
- **Root Cause**: Sorts by `headshot_kills / weapon_hits` (kills ÷ hits = mixed units = meaningless).
- **Fix**: Use `headshot_kills / NULLIF(kills, 0)` consistently.

#### HIGH-WEB-003: Greatshot Feature Broken
- **Files**: `website/js/greatshot.js`, `website/backend/services/greatshot_crossref.py`
- **Issues**: (a) Demo upload form not wired (b) `skill_rating` column doesn't exist in DB schema
- **NOTE on skill_rating**: The code ALREADY handles this gracefully via `_OPTIONAL_STATS_COLUMNS` (line 60) and `_resolve_optional_stat_columns()` (lines 100-104), using NULL fallback at line 449. However, historical error logs showed `UndefinedColumnError` — there may be an older code path that bypasses the optional column check. Investigate before changing.
- **Fix**: (a) Wire upload form in greatshot.js (b) Verify all query paths use the optional column mechanism; investigate any remaining `UndefinedColumnError` occurrences in logs.

#### HIGH-WEB-004: Session Graph Headshot COALESCE Bug
- **File**: `bot/services/session_graph_generator.py:504`
- **Root Cause**: `SUM(COALESCE(p.headshots, p.headshot_kills, 0))` — `headshots` = hit count, `headshot_kills` = kill count. COALESCE picks whichever is non-null, changing meaning.
- **Fix**: Use `SUM(p.headshot_kills)` explicitly.

#### MED-BOT-001: time_played_seconds Per-Player Inaccuracy
- **File**: `bot/community_stats_parser.py:989`
- **Root Cause**: Uses round duration for ALL players. Lua TAB[22] has actual per-player time but is ignored.
- **Impact**: Late joiners and disconnects show wrong time, cascading to DPM/FragPotential/Survival.
- **Fix**: Override with `objective_stats['time_played_minutes']` when available, after line 1005.

#### ~~MED-BOT-002~~: Parser Field 9 — ALREADY IMPLEMENTED ✅
- **File**: `bot/community_stats_parser.py` (lines 973-980)
- **Status**: VERIFIED COMPLETE. Parser already uses field 9 for `round_time_seconds`:
  ```python
  if actual_playtime_seconds is not None:
      round_time_seconds = int(actual_playtime_seconds)  # NEW FORMAT
  else:
      round_time_seconds = self.parse_time_to_seconds(actual_time)  # OLD FORMAT fallback
  ```
- **No fix needed.** Remove from fix queue.

#### MED-OPS-001: Deprecated `et-stats-webhook.service` Still Running
- **Location**: Game server
- **Impact**: Duplicate `STATS_READY` triggers, race conditions.
- **Fix**: `systemctl disable --now et-stats-webhook.service`

#### MED-OPS-002: Duplicate `log_monitor.sh` Processes
- **Location**: Game server
- **Impact**: Resource waste, potential duplicate processing.
- **Fix**: Kill duplicates, add process lock.

#### ~~MED-OPS-003~~: Samba + VM Dual Bot Responses — INTENTIONAL ✅
- **Status**: Not a bug. Two bot instances (Samba dev + VM prod) running simultaneously is expected and desired.
- **No fix needed.**

#### MED-OPS-004: Bot Restart Churn (15/day)
- **Evidence**: 15 startup events on 2026-02-18.
- **Root Cause**: Unknown. Possibly systemd restart policy + test DB probe collision.
- **Fix**: Investigate logs; separate test DB probes from production path.

#### MED-GIT-001: Git Branches Out of Sync
- **`wip/forgot-push`**: 5 merge conflicts (availability files).
- **`feat/availability-multichannel-notifications`**: Months ahead of main.
- **Fix**: Resolve conflicts, merge both to main.

#### LOW-OPS-001: DNS/SSH Resilience
- **Evidence**: 36 `Temporary failure in name resolution` on 2026-02-18.
- **Fix**: Add fallback host behavior, DNS retry/backoff.

#### LOW-OPS-002: Warning Fatigue
- **Evidence**: 52 round linker + 122 time-validation warnings daily.
- **Fix**: Classify and filter; reduce noise.

#### HIGH-OPS-001: Auto Debug Time Comparison Post Missing
- **Date Discovered**: 2026-02-21
- **Issue**: Daily automated debug/comparison post failed to generate. Scheduled task or cron entry did not execute.
- **Last Success**: 2026-02-20
- **Impact**: Missing visibility into time-tracking data and debug comparisons (likely related to Lua time tracking feature)
- **Investigation Required**:
  - Check cron/scheduler logs for failed executions
  - Verify cron entry exists and is properly formatted
  - Check for permissions issues on log files
  - Check if task ran but failed silently (check logs for errors)
  - Verify database connectivity during scheduled run time
- **Related**: HIGH-LUA-004 (time tracking not deployed), MED-BOT-001 (time_played_seconds inaccuracy)
- **Fix**: Investigate scheduler logs, identify root cause, add alerting for future failures

#### LOW-WEB-001: Proximity Data Not Showing on slomix.fyi — DB Split Issue

**Status**: Proximity data exists on Samba DB but NOT on VM DB (the one the website uses).

**Two separate databases:**
| Host | IP | Used by | Proximity data? |
|------|----|---------|----------------|
| Samba postgres | `192.168.64.116` | Samba bot + Samba website | ✅ 82 rounds, 6891 trade events, 78 objective focus rows |
| VM postgres | `192.168.64.159:5432` | slomix.fyi website + VM bot | ❌ Unknown — likely 0 or stale |

**Proximity tables** (confirmed on Samba DB):
- `proximity_support_summary` — 82 rows
- `proximity_trade_event` — 6891 rows
- `proximity_objective_focus` — 78 rows
- `proximity_reaction_metric` — 0 rows (tracker just deployed, awaiting next session)

**To fix slomix.fyi**: Proximity data needs to be exported from Samba DB and imported into VM DB.

**Options**:
1. `pg_dump` specific proximity tables from Samba, `pg_restore` into VM — requires VM SSH access
2. Run the proximity importer on the VM directly against the `local_proximity/` files (they need to be synced to VM first, or re-downloaded from game server on VM side)
3. Set up DB replication between Samba and VM for proximity tables

**Blocker**: No SSH key configured for `samba@192.168.64.159` from the Samba dev machine. Access requires either:
- Adding Samba's public key to VM's `~/.ssh/authorized_keys`
- Or manually running import on VM via console

**VM SSH access**: Per `docs/INFRA_HANDOFF_2026-02-18.md`, VM is accessed as user `samba` at `192.168.64.159`. Key needs to be set up.

**Also fixed 2026-02-21**: `SAFE_STATS_FILENAME_PATTERN` in `ssh_handler.py` was blocking all `_engagements.txt` downloads. Fix applied and backfill completed (82 files, on Samba only so far).

**Needs deeper audit**:
- Are there other filename suffixes/patterns the SSH allowlist might be missing?
- Does `ProximityParserV4` correctly parse `# REACTION_METRICS` sections end-to-end?
- Does the website endpoint correctly read and display reaction data once rows exist?
- Are there edge cases in engagement file pairing (R1/R2 matching) that could silently drop data?
- Check whether `_lifecycle.txt` files from proximity tracker could interfere with processing

#### ~~HIGH-TIMING-001~~: erdenberg_t2 R2 — RESOLVED ✅ (Was a Query Bug)
- **Originally thought**: R2 missing from DB
- **Actual finding** (confirmed via log investigation 2026-02-21): erdenberg_t2 R2 was **fully processed** at 00:06:52 UTC and imported as **round_id=9941** with 6 players, 56 weapons
- **Why it appeared missing**: The stats file was named `2026-02-21-000640-erdenberg_t2-round-2.txt` (generated just after midnight). The DB query used `WHERE round_date = '2026-02-20'` which excluded it — it's stored under **round_date = 2026-02-21**
- **Full pipeline confirmed working**: Webhook received at 00:06:38 → file downloaded 00:06:43 → parsed 00:06:51 → imported 00:06:52 → posted to Discord 00:06:52 → endstats resolved with 30 awards + 18 vs_rows
- **Lesson**: Cross-date rounds (session starts 2026-02-20, ends after midnight on 2026-02-21) must be queried with a session window, not a single date filter

#### CRIT-SSH-001: gametime-*.json Files Rejected by SSH Allowlist — 100% Data Loss
- **Discovered**: 2026-02-21 via bot log investigation
- **Evidence**: Every single `gametime-*.json` file download fails with `❌ SSH download failed: Unexpected stats filename format`. This spam appears for EVERY map, EVERY 60-second poll cycle, throughout the entire session. Examples:
  - `gametime-erdenberg_t2-R1-1771628290.json`
  - `gametime-te_escape2-R1-1771620553.json`
  - `gametime-supply-R1-1771615656.json`
- **Root Cause**: `SAFE_STATS_FILENAME_PATTERN` in `bot/automation/ssh_handler.py` only matches `.txt` files with a specific date-based naming pattern. The `gametime-*.json` format (different prefix, `.json` extension, unix timestamp suffix) is completely unrecognized and rejected by the security allowlist.
- **Impact**: ALL gametime JSON files have NEVER been downloaded since this feature was deployed. The gametime data (per-player time tracking from the server) is being generated on the server but silently lost. This is likely the root cause of `MED-BOT-001` (time_played_seconds per-player inaccuracy) — we don't have the actual per-player time data because we can't download the files that contain it.
- **Fix**: Add gametime pattern to `SAFE_STATS_FILENAME_PATTERN` in `bot/automation/ssh_handler.py`:
  ```python
  # Current pattern only matches: YYYY-MM-DD-HHMMSS-mapname-round-N[suffix].txt
  # Need to also allow: gametime-MAPNAME-R1-UNIXTIMESTAMP.json
  SAFE_GAMETIME_FILENAME_PATTERN = re.compile(
      r"^gametime-[A-Za-z0-9_.+-]+-R\d+-\d+\.json$"
  )
  ```
  Or extend the existing pattern to handle both formats. Also need to add a download handler for `.json` files in the proximity/gametime pipeline.
- **Secondary impact**: Warning log spam — hundreds of `❌ SSH download failed` lines per session pollute the logs, making real errors harder to spot (contributes to LOW-OPS-002 warning fatigue).

#### HIGH-PROXIMITY-001: Proximity round_number Always Stored as 1 — ROOT CAUSE FOUND
- **Discovered**: 2026-02-21 | **Root cause confirmed**: 2026-02-21 via tracker-proximity-checker agent
- **Evidence**: All 82 files in `local_proximity/` are named `round-1_engagements.txt`. Both filename AND `# round=1` header are wrong for R2 files.
- **Root Cause**: `proximity_tracker.lua` line ~547 in `refreshRoundInfo()`:
  ```lua
  local round_num = tonumber(round_str) or 1
  if round_num < 1 then
      round_num = 1   -- BUG: clamps to 1, but g_currentRound is 0-indexed!
  end
  ```
  ET:Legacy `g_currentRound` is **0-indexed**: R1=0, R2=1. The clamp `if round_num < 1 then round_num = 1` means:
  - R1: `g_currentRound=0` → clamped to 1 → stored as round 1 ✅ (correct by accident)
  - R2: `g_currentRound=1` → passes clamp → stored as round 1 ❌ (should be 2)
- **Fix** (one line in `proximity/lua/proximity_tracker.lua`):
  ```lua
  -- BEFORE (line ~547):
  local round_num = tonumber(round_str) or 1
  if round_num < 1 then round_num = 1 end
  -- AFTER:
  local round_num = (tonumber(round_str) or 0) + 1  -- convert 0-indexed to 1-indexed
  ```
- **Parser fallback**: `proximity/parser/parser.py` `_normalize_round_metadata()` tries gametime files first, then filename, then header — but since both filename and header say round=1, the parser cannot recover the correct value without gametime files (which also can't be downloaded due to CRIT-SSH-001).
- **Data safety**: Existing rows are NOT overwritten between R1/R2 because `round_start_unix` differs. Data is mislabeled but not lost.
- **Impact**: All proximity round-level analytics are wrong. R2 data appears as a second R1, not as R2.
- **Fix priority**: Fix Lua (one line) → re-deploy → backfill existing 82 files from `local_proximity/` by re-importing with corrected parser

#### MED-TIMING-002: Webhook Ghost Round — 7-Second te_escape2 Entry
- **Discovered**: 2026-02-21
- **Confirmed via log investigation**: Real Lua webhook at 23:39:54 UTC — `STATS_READY: te_escape2 R2 (winner=1, playtime=7s)` with real player lists (vid, olz, Proner / wajs, SuperBoyy, bronze)
- **Root Cause**: Appears to be a genuine game event — a very quick R2 round (possibly instant surrender or restart at round start). NOT a false map-transition trigger.
- **Bot handling**: Bot received it, looked for closest stats file, found `2026-02-20-233901-te_escape2-round-2.txt` (Δ=51s) but it was **already processed** from the previous real te_escape2. Correctly skipped (`⏭️ File already processed`). Lua team data WAS stored in `lua_round_teams`.
- **Impact**: Junk row in `lua_round_teams`. No duplicate stats import occurred — dedup worked correctly. Low actual impact.
- **Fix**: Add minimum duration filter (e.g., < 30s) in both webhook processing and `lua_round_teams` inserts to prevent storing ghost rounds.

#### ~~HIGH-TIMING-003~~: Supply Round Duration — RESOLVED, Internal Sources are CORRECT ✅
- **Originally thought**: Internal sources (659s/753s) were wrong, demo (720s/658s) was authoritative
- **Actual finding** (confirmed via bot log investigation 2026-02-21):
  - Supply R1 (match 2): `surrender=Allies (by .olz)` at **659s** — the Allies actually surrendered at 659s. This is correct.
  - Supply R2 (match 2): `surrender=Allies (by c^aarniee)` at **753s** — second surrender. Also correct.
  - Bot log: `"📋 Surrender detected! Stats said 0s, actual was 659s (saved 659s of fake time)"` — the surrender correction mechanism worked
- **Why superboyy's demo shows different values**: Demo files record from when the player starts/joins, which may include pre-round freeze time, warmup overlap, or inter-round intermission. Demo duration ≠ actual round playtime.
- **Superboyy's R1=720** = exactly 12:00 timelimit. This was probably the demo recording period from the start of the map (including freeze time before round start) to surrender point.
- **Conclusion**: c0rnp0rn, webhook, and proximity are all correct. Surrender happened at 659s and 753s. No bug here.
- **Note**: For sessions with SURRENDER rounds, demo file durations are NOT reliable for cross-referencing — they measure wall-clock recording time, not game round time.

#### MED-BOT-003: Round Linker `all_candidates_outside_window` on Every Round (Timing Race)
- **Discovered**: 2026-02-21 via bot log investigation
- **Evidence**: Every single round on 2026-02-20 initially triggers `all_candidates_outside_window` with `best_diff` values of 100,000–1,557,389 seconds (~18 days). Example: `round_linker: all_candidates_outside_window map=erdenberg_t2 rn=1 best_diff=1557389s`
- **Root Cause**: The endstats webhook fires and the round linker runs BEFORE the stats file has been imported into the DB. On the first pass, no matching round exists in `rounds` table yet (within the 45-min window). It resolves on retry after the stats file is imported (usually within 2-10 seconds).
- **Impact**: Noisy log spam on every round. Low actual impact — all rounds resolved correctly on retry. But indicates the round linker's first pass is always wasted. `best_diff=1,557,389s` (18 days) means it's finding rounds from a completely different session as "candidates".
- **Fix**: Add a short delay (5-10s) before the first round linker pass, or trigger it only after stats file import confirmation rather than immediately on webhook receipt.

#### LOW-TIMING-005: Surrender Correction Working Correctly ✅
- **Confirmed**: 2026-02-21 via bot log investigation
- The bot correctly detects surrender rounds and saves the actual playtime from the Lua webhook, overriding the 0s that c0rnp0rn reports for surrendered rounds
- Log pattern: `"📋 Surrender detected! Stats said 0s, actual was Xs (saved Xs of fake time)"`
- Appeared ~30+ times across the 2026-02-20 session for supply, te_escape2, sw_goldrush_te, etl_frostbite
- No action needed — working as designed

#### LOW-TIMING-004: All Sources Agree Except Supply — Cross-Reference Validation (2026-02-20)
- **Discovered**: 2026-02-21
- **Result**: 13/14 maps validated ✅. c0rnp0rn, webhook, and proximity agree on all non-supply rounds within ±1s (integer truncation). The ±1s difference is expected rounding between sources (c0rnp0rn truncates, proximity uses unix delta which can differ by 1s).
- **Conclusion**: Timing pipeline is solid across all three sources for normal rounds.

#### REFERENCE: Superboyy Demo Scan — 2026-02-20 Session (Authoritative)
Demo durations from `.dm_84` files scanned by superboyy. These are considered correct in most cases.
Format: `Map,R1_seconds,R2_seconds,Total_seconds`

```
2026-02-20-204051-etl_adlernest.dm_84,413,336,749
2026-02-20-205730-supply.dm_84,720,658,1378        ← supply discrepancy (see HIGH-TIMING-003)
2026-02-20-212322-etl_sp_delivery.dm_84,550,111,661
2026-02-20-213737-te_escape2.dm_84,682,362,1044
2026-02-20-215639-te_escape2.dm_84,233,174,407
2026-02-20-220445-te_escape2.dm_84,175,175,350
2026-02-20-221245-et_brewdog.dm_84,305,305,610
2026-02-20-222433-et_brewdog.dm_84,192,192,384
2026-02-20-223559-etl_adlernest.dm_84,512,404,916
2026-02-20-225257-sw_goldrush_te.dm_84,705,709,1414
2026-02-20-231840-etl_frostbite.dm_84,247,241,488
2026-02-20-232857-te_escape2.dm_84,274,274,548
2026-02-20-233932-te_escape2.dm_84,240,240,480
2026-02-20-235007-erdenberg_t2.dm_84,470,470,940   ← R2 missing from c0rnp0rn (see HIGH-TIMING-001)
```

**Validation summary vs internal sources (c0rnp0rn / webhook / proximity):**
- ✅ 13/14 maps: all three internal sources match demo within ±1s (rounding)
- ❌ supply: internal sources wrong — all three agree with each other but disagree with demo
- ❌ erdenberg_t2 R2: missing from c0rnp0rn only; webhook + proximity have it correctly

#### CROSS-REFERENCE METHODOLOGY (for future validation)
```sql
-- Compare c0rnp0rn vs webhook for any date
SELECT
    r.map_name, r.round_number,
    r.actual_duration_seconds as cornporn_s,
    lrt.actual_duration_seconds as webhook_s,
    (r.actual_duration_seconds - lrt.actual_duration_seconds) as diff
FROM rounds r
JOIN lua_round_teams lrt ON r.id = lrt.round_id
WHERE r.round_date = '2026-02-20'
ORDER BY r.id;

-- Check proximity round_number bug
SELECT map_name, round_number, COUNT(*)
FROM proximity_support_summary
GROUP BY map_name, round_number
ORDER BY map_name;
-- If all rows show round_number=1, bug confirmed

-- Find ghost webhook rounds (< 30 seconds)
SELECT * FROM lua_round_teams
WHERE actual_duration_seconds < 30
ORDER BY captured_at DESC;
```

#### REFERENCE: 2026-02-20 Session File Inventory (server-file-checker agent, 2026-02-21)

**Session started**: ~20:27 UTC | **Session ended**: ~00:07 UTC (crossed midnight to 2026-02-21)
**Total matches**: 15 complete + 1 aborted | **Total stats files on server**: ~52

File inventory summary (c0rnp0rn stats files + endstats on game server):

| Match | Map | R1 stats | R2 stats | R1 endstats | R2 endstats | Notes |
|-------|-----|----------|----------|-------------|-------------|-------|
| Aborted | supply (~20:27) | ✅ 632B | ❌ | ❌ | ❌ | 72s, game cut short |
| Match 1 | supply (~20:42) | ✅ | ✅ | ✅ | ✅ | |
| Match 2 | etl_adlernest | ✅ | ✅ | ✅ | ✅ | |
| Match 3 | supply (21:08) | ✅ | ✅ | ❌ MISSING | ✅ | R1 endstats not generated (HIGH-LUA-003) |
| Match 4 | etl_sp_delivery | ✅ | ✅ | ✅ | ✅ | |
| Match 5 | te_escape2 (21:49) | ✅ | ✅ | ✅ | ✅ | |
| Match 6 | te_escape2 (22:00) | ✅ | ✅ | ✅ | ✅ | |
| Match 7 | te_escape2 (22:07) | ✅ | ✅ | ✅ | ✅ | |
| Match 8 | et_brewdog (22:17) | ✅ | ✅ | ✅ | ✅ | |
| Match 9 | et_brewdog (22:23) | ✅ | ✅ | ✅ | ✅ | |
| Match 10 | etl_adlernest (22:44) | ✅ | ✅ | ✅ | ✅ | |
| Match 11 | sw_goldrush_te | ✅ | ✅ | ❌ MISSING | ✅ | R1 endstats not generated (HIGH-LUA-003) |
| Match 12 | etl_frostbite | ✅ | ✅ | ✅ | ✅ | |
| Match 13 | te_escape2 (23:27) | ✅ | ✅ | ✅ | ✅ | |
| Match 14 | te_escape2 (23:39) | ✅ | ✅ | ✅ | ✅ | Ghost 7s R2 (MED-TIMING-002) |
| Match 15 | erdenberg_t2 | ✅ | ✅ (after midnight) | ✅ | ✅ | R2 file dated 2026-02-21 |

**Pipeline status**: All stats files were downloaded and processed by the bot. The 2 missing endstats R1 files were never generated on the server — pipeline worked correctly for everything that existed.

**erdenberg_t2 DB confirmation** (tracker-proximity-checker agent):
- R1 `2026-02-20-235635-erdenberg_t2-round-1.txt` → in `processed_files` ✅, round_id=9940, processed ~23:58
- R2 `2026-02-21-000640-erdenberg_t2-round-2.txt` → in `processed_files` ✅, round_id=9941, processed ~00:07
- 299 proximity rows imported in bulk at 01:36 (proximity backfill run)
- Both rounds correctly stored under their respective `round_date` values (R1=2026-02-20, R2=2026-02-21)

#### LOW-SEC-001: SSH PasswordAuthentication Still Enabled on VM
- **Fix**: Set `PasswordAuthentication no` in `/etc/ssh/sshd_config.d/90-hardening.conf` after verifying all devs have key access.

#### LOW-SEC-002: Hardcoded Credentials in Local Config Files
- **Files**: `config.json`, `backups/2025-11/.../config.json`
- **Fix**: Delete; rely on `.env` as canonical source.

#### LOW-CFG-001: matplotlib Config Directory Read-Only on VM
- **Fix**: Add `MPLCONFIGDIR=/tmp/matplotlib_cache` to `/opt/slomix/.env`

#### LOW-DOC-001: SQLite References in Documentation
- **Files**: `POSTGRESQL_MIGRATION_INDEX.md`, `ADVANCED_TEAM_DETECTION.md`
- **Fix**: Update to clarify PostgreSQL-only.

---

## 5. CRITICAL FIX QUEUE (Ordered)

Execute these in order. Each phase gates the next unless marked "parallel-safe".

### Phase 0: Operational Cleanup (No Code Changes) — 15 minutes

```bash
# 0.1: Disable deprecated service on game server
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "sudo systemctl disable --now et-stats-webhook.service && systemctl is-active et-stats-webhook.service"

# 0.2: Singleton log_monitor.sh
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "pkill -f log_monitor.sh; sleep 1; nohup bash /home/et/scripts/log_monitor.sh >/home/et/scripts/log_monitor.log 2>&1 &"

# 0.3: Snapshot current state
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "ls -la /home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/*.lua"

# 0.4: Check timing dual flag
grep SHOW_TIMING_DUAL .env

# 0.5: Stop Samba bot (prevent double responses)
# On Samba: screen -r slomix → Ctrl+C → Ctrl+A D
```

**Gate**: All 5 steps verified before Phase 1.

---

### Phase 1: Fix R2 Webhook Crash — HIGHEST PRIORITY — 30 minutes

**File**: `vps_scripts/stats_discord_webhook.lua`

**IMPORTANT**: The webhook function already has `pcall()` wrapping (line 804) and properly resets `send_in_progress = false` (line 989). Do NOT add redundant error handling. The fix is ONLY to ensure all `%d` format arguments are integers.

**Change 1 — Line 822** (timelimit seconds calculation):
```lua
-- BEFORE:
local time_limit_seconds = time_limit * 60
-- AFTER:
local time_limit_seconds = math.floor(time_limit * 60 + 0.5)
```

**Change 2 — Line 910** (total_pause_seconds in payload format):
Ensure `total_pause_seconds` is integer before use in `%d` format. Near line 1087 where pause durations accumulate, or at usage site:
```lua
-- Wrap at usage point (line 910 area):
math.floor(total_pause_seconds)
```

**Change 3 — Add guardrail logging** (before the format call, around line 825):
```lua
et.G_Print(string.format("[stats_discord_webhook] timelimit raw=%s seconds=%s\n",
    tostring(time_limit), tostring(time_limit_seconds)))
```

**Audit all other `%d` usages**: Lines 591-592 (spawn stats — already safe, uses `math.floor()`), lines 616-617 (pause events — already safe), line 886 (playtime — safe, unix timestamp arithmetic). Only lines 827 and 910 are vulnerable.

**Deploy**: SCP fixed file to game server, wait for map change (hot-reload).

**Gate**: Play one full R1+R2 stopwatch round. Verify:
- No `bad argument` errors in server console
- STATS_READY webhook fired for BOTH R1 and R2
- `lua_round_teams` has rows for both round numbers
- `lua_spawn_stats` has rows for both

---

### Phase 2: Merge Lua Time Tracking + LuaJIT Patches — 1-2 hours

**Goal**: Create single merged file combining `c0rnp0rn7.lua` (LuaJIT patches) + `c0rnp0rn7new.lua.lua` (developer's time tracking update, 2026-02-21).

**Source files**:
- **Base**: `c0rnp0rn7.lua` (repo root, 916 lines, deployed version — has LuaJIT compat, no time tracking)
- **New dev file**: `c0rnp0rn7new.lua.lua` (repo root, 843 lines, has time tracking + field 9, uses Lua 5.3 operators)
- **Do NOT use**: `c0rnp0rn-testluawithtimetracking.lua` (older test version — superseded by new dev file)

**From `c0rnp0rn7new.lua.lua`, bring in**:
- `roundStart = et.trap_Milliseconds()` (et_RunFrame ~line 443-444)
- `roundEnd = et.trap_Milliseconds()` (et_RunFrame ~line 393)
- `pausedTime[1,2,3]` pause tracking (et_RunFrame ~lines 481, 496-497)
- Header field 9 = `roundEnd - roundStart - (pausedTime[3] or 0)` (SaveStats ~line 351)

**From c0rnp0rn7, keep**:
- `ensure_bit_compat()` function (LuaJIT fallback)
- All `bit.rshift()`, `bit.bor()`, `bit.band()`, `bit.lshift()` calls
- `ensure_max_clients()` safety wrapper
- `to_int()` utility function

**Critical**: Replace ALL Lua 5.3 operators from test file:
- `>>` → `bit.rshift()`
- `<<` → `bit.lshift()`
- `|` → `bit.bor()`
- `&` → `bit.band()`

**Output**: `c0rnp0rn3.lua` (or whatever naming convention is chosen)

**Gate**: LuaJIT compatibility scan clean + parser reads 9-field header sample.

---

### ~~Phase 3~~: Parser Field 9 — ALREADY IMPLEMENTED ✅ (SKIP)

**File**: `bot/community_stats_parser.py` (lines 973-980)

**This is already done.** The parser already conditionally uses field 9:
```python
if actual_playtime_seconds is not None:
    round_time_seconds = int(actual_playtime_seconds)  # Field 9 (accurate)
else:
    round_time_seconds = self.parse_time_to_seconds(actual_time)  # Header fallback
```

**No action needed. Proceed directly to Phase 4.**

---

### Phase 4: Deploy Merged Lua to Game Server — 20 minutes

1. Backup current: `ssh ... "cp c0rnp0rn7.lua c0rnp0rn7.lua.bak"`
2. Deploy merged file
3. Wait for map change (hot-reload)
4. Verify 9-field header in fresh stats file: `ssh ... "head -1 /path/to/latest-stats.txt"`
5. Verify parser processes correctly (check bot logs)
6. Verify no LuaJIT errors in server console

**Rollback**: `ssh ... "cp c0rnp0rn7.lua.bak c0rnp0rn7.lua"` + map change

---

### Phase 5: Bot Fixes — 2-3 hours (parallel-safe with Phase 6)

#### 5a: Fix Retry Progression (HIGH-BOT-001)
**File**: `bot/ultimate_bot.py`
- Fix active task marker + re-schedule deadlock at lines 4721-4754
- Allow retry count to advance: 1/5 → 2/5 → 3/5 → 4/5 → 5/5
- Add explicit logging for each retry attempt

#### 5b: Fix Duplicate Quality Selection (HIGH-BOT-002)
**File**: `bot/ultimate_bot.py`
- Before final publish for a round, compare candidate payloads
- Prefer richer file: `max(candidates, key=lambda c: (c.awards_count, c.vs_count, c.bytes))`
- Log: `"Selecting richer endstats: {winner.filename} ({winner.bytes}b, {winner.awards_count} awards)"`

#### 5c: Fix time_played_seconds (MED-BOT-001)
**File**: `bot/community_stats_parser.py`
After line ~1005:
```python
lua_time_min = objective_stats.get('time_played_minutes', 0)
if lua_time_min > 0:
    player['time_played_seconds'] = int(lua_time_min * 60)
```

#### 5d: Fix Session Graph Headshot COALESCE (HIGH-WEB-004)
**File**: `bot/services/session_graph_generator.py:504`
Change: `SUM(COALESCE(p.headshots, p.headshot_kills, 0))` → `SUM(p.headshot_kills)`

#### 5e: Fix Headshot Leaderboard (HIGH-WEB-002)
**File**: `bot/cogs/leaderboard_cog.py:587`
Change: `SUM(p.headshot_kills) / SUM(w.hits)` → `SUM(p.headshot_kills) / NULLIF(SUM(p.kills), 0)`
Also fix display at line 824.

---

### Phase 6: Website Formula Alignment — 1 hour (parallel-safe with Phase 5)

**File**: `website/backend/routers/api.py`

#### 6a: FragPotential (lines ~4896-4897)
```python
# WRONG: (kills + assists * 0.5) / time_minutes * 10
# RIGHT: (damage_given / max(1, time_alive_seconds)) * 60  # DPM while alive
frag_potential = (damage_given / max(1, time_alive_seconds)) * 60
```

#### 6b: Survival Rate (lines ~4906-4909)
```python
# WRONG: min(100, (time_played / (deaths + 1)) / 60 * 10)
# RIGHT: 100 - (time_dead_minutes / max(0.01, time_played_minutes) * 100)
survival_rate = max(0, 100 - (time_dead_minutes / max(0.01, time_played_minutes) * 100))
```

#### 6c: Damage Efficiency (lines ~4900-4903)
```python
# WRONG: dmg_given / (dmg_given + dmg_received) * 100  (percentage 0-100)
# RIGHT: dmg_given / max(1, dmg_received)  (ratio, >1 is good)
damage_efficiency = damage_given / max(1, damage_received)
```

#### 6d: Headshot % (lines ~4096, ~4292)
Verify these are using the correct formula for their context:
- Weapon-level stats: `headshot_hits / total_hits * 100` (accuracy) ✅ if using weapon table
- Player-level summary: `headshot_kills / total_kills * 100` (kill rate) — label clearly

#### 6e: Additional Formula Location — classify_playstyle()
**File**: `website/backend/routers/api.py:4988`
```python
# This function has a DIFFERENT efficiency metric:
"efficiency": min(100, (stats["damage_given"] / max(1, stats["damage_received"])) * 25)
```
This is a scaled damage ratio (not percentage), used only in playstyle classification. Review whether this should also be aligned.

#### 6f: Greatshot Schema Investigation (HIGH-WEB-003)
**File**: `website/backend/services/greatshot_crossref.py`
- The optional column mechanism ALREADY EXISTS (lines 60, 100-104, 449)
- Investigate: find the code path that triggered `UndefinedColumnError` in historical error logs
- Check ALL query functions in this file — there may be one that doesn't use the optional column check
- If found, add the optional column mechanism to that code path too

---

### Phase 7: Endstats Lua Fixes — 2-3 hours

#### 7a: Atomic File Generation (HIGH-LUA-002)
**File**: `endstats.lua` (repo root: `/home/samba/share/slomix_discord/endstats.lua`)
- The `send_table()` function generates a new filename via `os.date()` at **line 1459** on each call
- Awards `send_table()` is called at **line 714**, per-player VS `send_table()` at **line 762**
- Fix: Generate filename ONCE per round at start of finalization, pass to all `send_table()` calls
- File write logic at **lines 1460-1473** (uses `et.trap_FS_FOpenFile`, loops, writes, closes)
- All data must append to same file

#### 7b: Surrender Handling (HIGH-LUA-003)
**File**: `endstats.lua` (same file as above)
- Exit condition matching at **lines 874-892** (NOT 796-807)
- Exact strings: `"Exit: Timelimit hit.\n"`, `"Exit: Wolf EndRound.\n"`, `"Exit: Allies Surrender\n"`, `"Exit: Axis Surrender\n"` → sets `kendofmap = true` at line 885
- Replace exact string matching with robust pattern matching (e.g., `string.find(text, "^Exit:")`)
- Add fallback: if `kendofmap` not triggered but stats file exists, still generate endstats
- Add structured logging for state machine variables (`kendofmap`, `tblcount`, `endplayerscnt`, `eomap_done`)

---

### Phase 8: Git/Branch Cleanup — 2-3 hours

1. **Resolve `wip/forgot-push` conflicts** (5 files: availability_poll_cog, test_availability_router, website routers __init__, availability.js, utils.js)
2. **Merge `feat/availability-multichannel-notifications` to main** (months of work, 3 new routers + cogs)
3. **First proper GitHub-based deploy to VM** using git checkout + tag
4. **Delete stale branches** after merge

---

### Phase 9: Minor Fixes & Cleanup — 1 hour (parallel-safe)

- [ ] Add `MPLCONFIGDIR=/tmp/matplotlib_cache` to VM `.env` (LOW-CFG-001)
- [ ] Set SSH `PasswordAuthentication no` on VM after verifying key access (LOW-SEC-001)
- [ ] Delete hardcoded credential files (LOW-SEC-002)
- [ ] Update SQLite references in docs (LOW-DOC-001)
- [ ] Wire Greatshot demo upload form (HIGH-WEB-003)
- [ ] Configure Cloudflare HTTP→HTTPS redirect

---

## 6. FORMULA CORRECTION GUIDE

### Headshot Statistics: Two Valid Definitions

The codebase has TWO meanings of "headshot %":

| Metric | Formula | Meaning | Use When |
|--------|---------|---------|----------|
| **Headshot Accuracy** | `headshot_hits / total_hits × 100` | What % of shots land on heads | Weapon-level stats, aim analysis |
| **Headshot Kill Rate** | `headshot_kills / total_kills × 100` | What % of kills are headshots | Player summary, lethality metric |

**Data Source Mapping**:
- `headshot_hits` = `player_comprehensive_stats.headshots` (already in DB, sum of weapon headshot hits)
- `headshot_kills` = `player_comprehensive_stats.headshot_kills` (TAB[14], final blow to head)
- `total_hits` = `SUM(weapon_comprehensive_stats.hits)` per player
- `total_kills` = `player_comprehensive_stats.kills`

**Decision**: Standardize on Headshot Kill Rate as primary display. Label as "HS Kill %" or "Headshot Kill Rate". Add Headshot Accuracy where weapon-level detail is shown.

### Files Requiring Headshot Formula Audit

| File | Line(s) | Current | Action |
|------|---------|---------|--------|
| `bot/cogs/leaderboard_cog.py` | 587, 824 | `headshot_kills / hits` (WRONG - mixed units) | Change to `headshot_kills / kills` |
| `bot/services/session_graph_generator.py` | 504 | `COALESCE(headshots, headshot_kills)` (WRONG) | Use `headshot_kills` explicitly |
| `bot/services/session_embed_builder.py` | 223 | `hs / hits` (accuracy - actually correct for its context) | Keep or relabel |
| `bot/core/frag_potential.py` | ~112 | Uses headshot_kills | Verify consistent |
| `bot/cogs/stats_cog.py` | ~388 | Uses headshot_kills | Verify consistent |
| `website/backend/routers/api.py` | ~4096, ~4292 | Context-dependent | Verify per-context |

### Complete Formula Reference (Bot = Source of Truth)

| Metric | Correct Formula | Unit | File |
|--------|----------------|------|------|
| FragPotential | `(damage_given / time_alive_seconds) × 60` | DPM | `bot/core/frag_potential.py` |
| Survival Rate | `100 - (time_dead_min / time_played_min × 100)` | % | `bot/services/session_embed_builder.py` |
| Damage Efficiency | `damage_given / max(1, damage_received)` | ratio | Bot cogs |
| Headshot Kill Rate | `headshot_kills / kills × 100` | % | Player-level summaries |
| Headshot Accuracy | `headshot_hits / total_hits × 100` | % | Weapon-level detail |
| DPM (Damage/Min) | `damage_given / time_played_minutes` | dmg/min | Bot cogs |
| KDR | `kills / max(1, deaths)` | ratio | Bot cogs |

---

## 7. LUA PIPELINE FIX GUIDE

### Understanding the Lua Ecosystem

Three Lua scripts run on the game server:

1. **`c0rnp0rn7.lua`** (stats writer): Writes per-round stats files. Currently deployed. Has LuaJIT patches but NO time tracking.
2. **`stats_discord_webhook.lua`** v1.6.2 (webhook): Sends HTTP POST to bot on round end. Has R2 crash bug.
3. **`endstats.lua`** (endgame stats): Writes endstats files (awards, per-player VS tables). Has file-splitting bug.

### R2 Crash Mechanics (Why It Happens)

```
Stopwatch Mode:
  R1: timelimit = 20.000000 (clean integer) → %d works ✅
  R2: timelimit = 7.374583 (fractional, time left from R1) → %d crashes ❌

stats_discord_webhook.lua execution:
  Line 681: get_time_limit() returns tonumber(et.trap_Cvar_Get("timelimit")) -- float
  Line 802: send_in_progress = true
  Line 804: pcall wrapper begins (error handling EXISTS)
  Line 822: time_limit_seconds = time_limit * 60  -- fractional!
  Line 827: string.format("...%d...", time_limit_seconds)  -- CRASH (inside pcall)
  Line 910: string.format("...%d...", total_pause_seconds)  -- ALSO VULNERABLE
  Line 989: send_in_progress = false  -- DOES reset (after pcall)
  -- pcall catches the error, flag resets, but webhook data for this round is LOST
```

### Endstats Split Mechanics (Why Awards Get Lost)

```
endstats.lua execution (NOTE: line numbers ~78 higher than some docs claim):
  Round ends → kendofmap trigger (lines 874-892)
  Line 714: send_table(awards_table)        -- generates filename from os.date() at 21:51:11
  Line 762: send_table(player_vs_tables)    -- generates NEW filename from os.date() at 21:51:12
  Line 1459: filename = os.date('%Y-%m-%d-%H%M%S-') .. mapname  -- INSIDE send_table()
  -- If second boundary crossed: TWO FILES created
  -- Bot processes whichever arrives first (often the smaller one)
```

### Game Server Lua File Locations

```
/home/et/etlegacy-v2.83.1-x86_64/legacy/
├── c0rnp0rn7.lua                    (stats writer - deployed, 916 lines, LuaJIT-safe, NO time tracking)
└── luascripts/
    ├── stats_discord_webhook.lua    (webhook v1.6.2 - deployed, has R2 crash bug CRIT-LUA-001)
    ├── proximity_tracker.lua        (proximity v4.2 FULL - deployed 2026-02-21, 72528 bytes, HAS REACTION_METRICS)
    └── endstats.lua                 (endgame stats - deployed, has file-split bug HIGH-LUA-002)

# Loaded by: set lua_modules "luascripts/team-lock c0rnp0rn7.lua endstats.lua luascripts/stats_discord_webhook.lua"
# Config: /home/et/etlegacy-v2.83.1-x86_64/etmain/legacy.cfg
# proximity_tracker.lua is loaded separately by the game (NOT in lua_modules line above)
# proximity output dir: /home/et/.etlegacy/legacy/proximity/
```

### Game Server Stats File Paths (CORRECTED 2026-02-21)

```
# c0rnp0rn stats files (NOT nitmod/stats — that path does NOT exist):
/home/et/.etlegacy/legacy/gamestats/        ← CORRECT path for stats files

# Proximity engagement files:
/home/et/.etlegacy/legacy/proximity/        ← engagement + gametime files

# etconsole log:
/home/et/.etlegacy/legacy/etconsole.log
```

**IMPORTANT**: Many docs and the super prompt previously referenced `/home/et/.etlegacy/nitmod/stats/` — **this path does not exist**. Correct path is `/home/et/.etlegacy/legacy/gamestats/`.

### Repo Lua File Locations

```
/home/samba/share/slomix_discord/
├── c0rnp0rn7.lua                             (LuaJIT-patched, matches deployed version)
├── c0rnp0rn7new.lua.lua                      (⚠️ NEW from developer 2026-02-21, 843 lines)
│                                              HAS time tracking + field 9 header
│                                              NOT LuaJIT-compatible (uses >> << | & operators)
│                                              DO NOT DEPLOY AS-IS — must merge LuaJIT patches first
├── c0rnp0rn7real.lua                         (alternate version)
├── c0rnp0rnMAYBEITSTHISONE.lua               (candidate version)
├── c0rnp0rn-testluawithtimetracking.lua      (older time tracking test, NOT LuaJIT-compatible)
├── endstats.lua                              (endstats script)
├── vps_scripts/stats_discord_webhook.lua     (webhook script - source of truth for server)
├── proximity/lua/proximity_tracker.lua       (full v4.2 with REACTION_METRICS - deployed 2026-02-21)
└── deployed_lua/legacy/                      (snapshot of deployed copies)
    ├── c0rnp0rn7.lua
    ├── proximity_tracker.lua
    └── endstats.lua
```

### Deploying Lua to Game Server

```bash
# Stats writer (c0rnp0rn7.lua) — loads from /legacy/ NOT /legacy/luascripts/
scp -i ~/.ssh/etlegacy_bot -P 48101 <file> et@puran.hehe.si:/home/et/etlegacy-v2.83.1-x86_64/legacy/c0rnp0rn7.lua

# Webhook / proximity tracker — loads from /legacy/luascripts/
scp -i ~/.ssh/etlegacy_bot -P 48101 <file> et@puran.hehe.si:/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/<name>.lua

# ALWAYS backup first:
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@puran.hehe.si \
  "cp /path/to/file.lua /path/to/file.lua.bak_$(date +%Y%m%d_%H%M%S)"

# Lua hot-reloads on map change — no server restart needed
```

---

## 8. WEBSITE FIX GUIDE

### Current Website State

- **URL**: https://www.slomix.fyi (Cloudflare Tunnel → VM port 7000)
- **Backend**: FastAPI, `website/backend/`
- **Frontend**: Vanilla JS SPA, `website/js/` (27 files)
- **Auth**: Discord OAuth working
- **Main issues**: Formula divergence, Greatshot broken, some UI edge cases

### Greatshot Fix Checklist

1. **Schema drift** (`website/backend/services/greatshot_crossref.py`):
   - `skill_rating` column doesn't exist in production DB schema
   - **ALREADY HANDLED**: Code has `_OPTIONAL_STATS_COLUMNS = ("skill_rating", "dpm")` at line 60
   - `_resolve_optional_stat_columns()` at lines 100-104 feature-detects columns
   - Line 449: `skill_rating_expr = "skill_rating" if optional_columns.get("skill_rating") else "NULL AS skill_rating"`
   - **Investigate**: Historical error logs showed `UndefinedColumnError` — there may be an older code path that bypasses this mechanism. Check ALL query functions in the file, not just `enrich_with_db_stats()`.

2. **Demo upload form** (`website/js/greatshot.js`):
   - Functions exposed at window level (lines 981, 986)
   - Submit handler may not be wired to form
   - Debug with browser DevTools → Network tab
   - Verify `loadGreatshotView()` called from app.js router

3. **Upload download behavior** (`website/backend/uploads.py:376`):
   - Videos served with `Content-Disposition: inline` (streams in browser)
   - Fix: Add `Content-Disposition: attachment` for download action
   - Or add `?force_download=true` query param

### Availability System Status

- Stages 0-5: COMPLETE ✅
- DB migrations 006/007/008 applied ✅
- 33 tests passing ✅
- Gap: Stage 4 E2E verification requires non-sandbox Discord host
- UI could use engagement improvements (player names/avatars, progress bars)

---

## 9. INFRASTRUCTURE & OPS GUIDE

### VM Details (Production)

```
IP: 192.168.64.159
OS: Debian 13.3 (Proxmox)
Python: 3.13.5
Disk: 55 GB free (6% used of 61 GB)
Services:
  - slomix-bot.service (python3 -m bot.ultimate_bot)
  - slomix-web.service (uvicorn, port 7000)
  - postgresql (port 5432)
Code: /opt/slomix/ (git clone from GitHub, commit 8dca0e1)
Logs: /opt/slomix/logs/ (bot.log, webhook.log, errors.log, web.log)
Env: /opt/slomix/.env (46 keys)
```

### Deployment Runbook (First GitHub Deploy)

Pre-deploy checklist:
1. All PRs merged to main
2. CI green (ruff, pytest, JS lint, CodeQL)
3. `git tag v1.0.7` (or appropriate version)
4. Backup current VM state

Deploy steps:
```bash
ssh samba@192.168.64.159
cd /opt/slomix
sudo systemctl stop slomix-bot slomix-web
git fetch origin
git checkout v1.0.7  # or: git pull origin main
source venv/bin/activate && pip install -r requirements.txt
sudo systemctl start slomix-bot slomix-web
# Verify:
curl http://localhost:7000/api/status
curl http://localhost:7000/health
journalctl -u slomix-bot --since "5 min ago" --no-pager
```

### Game Server Access

```bash
# SSH to game server
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si

# Key paths on game server
/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/  # Lua scripts
/home/et/.etlegacy/legacy/etconsole.log               # Server console log
/home/et/stats/                                        # Stats files directory
/home/et/scripts/log_monitor.sh                        # Log monitor script
```

### Service Management

| Service | Where | Start | Stop | Logs |
|---------|-------|-------|------|------|
| Bot (VM) | VM | `systemctl start slomix-bot` | `systemctl stop slomix-bot` | `journalctl -u slomix-bot` |
| Web (VM) | VM | `systemctl start slomix-web` | `systemctl stop slomix-web` | `journalctl -u slomix-web` |
| Bot (Samba) | Samba | `screen -S slomix` | `screen -r slomix` → Ctrl+C | `logs/bot.log` |
| Web (Samba) | Samba | `screen -S website` | `screen -r website` → Ctrl+C | `website/logs/` |
| PostgreSQL | Both | `systemctl start postgresql` | `systemctl stop postgresql` | `journalctl -u postgresql` |

---

## 10. GIT/BRANCH CLEANUP GUIDE

### Current Branch State

| Branch | Status | Action |
|--------|--------|--------|
| `main` | Protected, behind | Target for all merges |
| `reconcile/merge-local-work` | Current | Working branch |
| `wip/forgot-push` | 5 merge conflicts | Resolve → merge to main |
| `feat/availability-multichannel-notifications` | Months ahead of main | Rebase → merge to main |
| `docs/readme-roadmap-workflow-updates` | PR #35 open | Merge or close |
| `fix/codebase-review-findings` | Recent work | Merge to main |

### Conflict Files in `wip/forgot-push`

1. `bot/cogs/availability_poll_cog.py`
2. `tests/test_availability_router.py`
3. `website/backend/routers/__init__.py`
4. `website/js/availability.js`
5. `website/js/utils.js`

### Merge Strategy

1. Start fresh from main
2. Cherry-pick or merge `wip/forgot-push` (resolve conflicts)
3. Merge `feat/availability-multichannel-notifications` (big merge, test thoroughly)
4. Merge `fix/codebase-review-findings`
5. Close PR #35 or merge
6. Tag as `v1.0.7`
7. Deploy tag to VM

---

## 11. FUTURE FEATURES (Planned, Not Started)

### Lua Time Stats Overhaul (10-Step, Major)

Per-player time tracking with 8 new columns:
- `time_played_ms`, `time_alive_ms`, `time_dead_ms`, `denied_playtime_ms`
- `spawn_count`, `avg_respawn_ms`, `longest_life_ms`, `longest_death_ms`

Touches: Lua, parser, DB schema, bot commands/graphs, website backend/frontend.
Status: Planning phase. Blocked on prioritization.

### OmniBot Integration (Dry-Run Plan)

Server-side bot AI enhancement. Has detailed project doc (`docs/OMNIBOT_PROJECT.md`).
Status: Dry-run plan only. Not started.

### Proximity Tracker Enhancement — Player Round Summary

**Goal**: Add per-player, per-round summary stats to proximity engagement files.

**What to add** (new `# PLAYER_ROUND_SUMMARY` section in proximity output):

#### Time Alive / Time Dead (per round, per team side)
- **What exists**: `proximity_tracker.lua` already records `spawn_time` and `death_time` per life in PLAYER_TRACKS. `gameTime()` uses `et.trap_Milliseconds() - tracker.round.start_time` — so ALL times are relative to round start (warmup excluded ✅).
- **Time alive** = sum of `(death_time - spawn_time)` across all lives for a player in the round
- **Time dead** = sum of `(next_spawn_time - prev_death_time)` across all deaths — i.e. the gap between death and next spawn (includes limbo queue wait). Final death to round end is also dead time if player didn't respawn.
- **Per team** = track which team side the player was on (already in PLAYER_TRACKS: `team` field, "allies"/"axis")
- **Map summary** = sum of R1 + R2 values (done at display layer, not Lua level)

#### Stance Time Breakdown (per round)
- **What exists**: Every 200ms sample already records `stance` (0=standing, 1=crouching, 2=prone) and `sprint` (0/1). Sprint is detected via stamina delta + `MIN_SPRINT_SPEED=140`.
- **What to add**: Accumulators updated per sample during life:
  - `time_standing_ms` (stance=0, sprint=0, speed > ~30)
  - `time_running_ms` (stance=0, sprint=0, speed >= ~80, not sprinting)
  - `time_sprinting_ms` (stance=0, sprint=1)
  - `time_crouching_ms` (stance=1)
  - `time_prone_ms` (stance=2)
  - `time_still_ms` (speed < ~30, not dead) — waiting/AFK
- **Note**: Each sample represents 200ms of game time. Accumulate per sample: `time_X_ms += 200`

#### Denied Playtime (enemy time denied by this player)
- **What exists in c0rnp0rn7.lua**: `topshots[i][16]` = ms of enemy time denied. Tracked via `denies[]` table: when player A kills player B, `denies[B] = {true, A, kill_timestamp}`. When B respawns, A gets credited `respawn_time - kill_time - pause_time`. Written to stats file as field 29 (seconds). **Already in `player_comprehensive_stats.denied_playtime_seconds`.**
- **What to add to proximity**: Mirror the same deny logic inside `proximity_tracker.lua` so it's also in the proximity pipeline. Cross-reference kill events (et_Obituary already fires) with respawn (et_ClientSpawn). This avoids needing to join proximity data with stats file data at query time.

#### Implementation Plan (Lua side — `proximity/lua/proximity_tracker.lua`)
```lua
-- Per-player accumulators (reset on each spawn)
local stance_time = {}  -- stance_time[clientnum] = {standing=0, running=0, sprinting=0, crouching=0, prone=0, still=0}
local dead_since = {}   -- dead_since[clientnum] = gameTime() when they died
local deny_tracking = {} -- deny_tracking[victim] = {killer=clientnum, kill_time=gameTime()}

-- In samplePlayer() after stance/sprint detection:
--   stance_time[clientnum][mode] += config.position_sample_interval

-- In et_Obituary:
--   dead_since[victim] = gameTime()
--   deny_tracking[victim] = {killer=killer, kill_time=gameTime()}

-- In et_ClientSpawn:
--   if dead_since[clientnum] then time_dead += gameTime() - dead_since[clientnum] end
--   if deny_tracking[clientnum] then credit killer with denied time end

-- Output in new section:
-- # PLAYER_ROUND_SUMMARY
-- # guid;name;team;time_alive_ms;time_dead_ms;time_standing_ms;time_running_ms;time_sprinting_ms;time_crouching_ms;time_prone_ms;time_still_ms;denied_playtime_ms
```

#### Parser side (`proximity/parser/` or `ProximityParserV4`)
- Parse new `# PLAYER_ROUND_SUMMARY` section
- Write to new DB table: `proximity_player_round_summary`
- Schema: `(round_id, guid, player_name, team, time_alive_ms, time_dead_ms, time_standing_ms, time_running_ms, time_sprinting_ms, time_crouching_ms, time_prone_ms, time_still_ms, denied_playtime_ms)`

#### Key constraints
- Warmup excluded automatically (gameTime() starts at round start, spawn_time < 0 = warmup, ignored)
- Do NOT deploy Lua changes without LuaJIT compatibility check (no `>>` `<<` `|` `&` operators)
- Stance accumulators must reset on each spawn (not carry across lives)
- Dead time between last death and round end: if player never respawns after final death, `time_dead += round_end_time - last_death_time`

**Status**: Planned. Not started. Requires Lua + parser + DB schema + website changes.

### Promotions System

Campaign-based promotion tools for growing the player community.
See `docs/PROMOTE_CAMPAIGNS.md`, `docs/PROMOTIONS_SYSTEM.md`.
Status: Documented, not started.

### Planning Room

In-game session planning and scheduling tool.
See `docs/PLANNING_ROOM.md`, `docs/PLANNING_ROOM_MVP.md`.
Status: MVP documented, not started.

---

## 12. VALIDATION PLAYBOOK

### After Phase 1 (R2 Webhook Fix)
```sql
-- Check R2 Lua coverage for today
SELECT r.round_id, r.round_number, r.map_name,
       lrt.id AS lua_id, lrt.actual_duration_seconds
FROM rounds r
LEFT JOIN lua_round_teams lrt ON r.round_id = lrt.round_id
WHERE r.round_date >= CURRENT_DATE
ORDER BY r.round_id;

-- Should see lua_id NOT NULL for BOTH round_number=1 AND round_number=2
```

```bash
# Check server console for errors
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "grep -n 'bad argument' /home/et/.etlegacy/legacy/etconsole.log | tail -5"
# Should return nothing after fix
```

### After Phase 5 (Bot Fixes)
```bash
# Check retry progression in bot logs
grep "retry" logs/bot.log | tail -20
# Should see "retry 1/5", "retry 2/5", etc. (not stuck at 1/5)

# Check duplicate quality selection
grep "Selecting richer" logs/bot.log | tail -10
```

### After Phase 6 (Website Formula Fix)
```bash
# Compare bot vs website for same player
# Bot: /stats @player → note FragPotential, Survival Rate
# Website: https://www.slomix.fyi → same player → should match

# API spot check
curl -s https://www.slomix.fyi/api/stats/overview | python3 -m json.tool | head -30
```

### General Health Check
```bash
# VM services
ssh samba@192.168.64.159 "systemctl is-active slomix-bot slomix-web postgresql"

# API endpoints
curl -s https://www.slomix.fyi/api/status | python3 -m json.tool
curl -s https://www.slomix.fyi/health

# Database
PGPASSWORD='...' psql -h localhost -U etlegacy_user -d etlegacy -c "SELECT COUNT(*) FROM rounds;"
```

---

## 13. CRITICAL RULES (Never Violate)

### Database Rules
- **PostgreSQL ONLY** — never SQLite syntax (`INSERT OR REPLACE`, `AUTOINCREMENT`)
- Use `postgresql_database_manager.py` for ALL DB operations
- Use `?` for query parameters (NOT `{ph}` placeholders)
- ALWAYS use `gaming_session_id` for session queries (NOT dates)
- ALWAYS group by `player_guid` (NOT `player_name`)
- ALWAYS use 60-minute gap threshold for sessions
- ALWAYS use async database calls via `database_adapter.py` in Cogs
- NEVER recalculate R2 differential (parser handles it correctly)

### Git Rules
- **NEVER commit directly to main** — always use feature branches
- Use Conventional Commits: `<type>(<scope>): <description>`
- Types: feat, fix, docs, chore, refactor, test, security, perf
- Never commit secrets, logs, backups, or database files

### Terminology
- **ROUND** = One stats file (R1 or R2), one half of a match
- **MATCH** = R1 + R2 together (one complete map played)
- **GAMING SESSION** = Multiple matches within 60-minute gaps

### Parser Rules
- `headshots` ≠ `headshot_kills` (different stats, different meanings)
- R2 files contain CUMULATIVE stats; parser subtracts R1 values
- Only `endstats_monitor` task loop handles SSH (SSHMonitor disabled)

### Architecture Rules
- Bot runs in screen session `slomix` on Samba, systemd `slomix-bot` on VM
- Website runs on port 7000 (VM) or 8000 (Samba)
- Lua webhook is v1.6.2 — canonical real-time data source
- `et-stats-webhook.service` is DEPRECATED — must be disabled

---

## TOTAL EFFORT ESTIMATE

| Phase | Effort | Dependencies |
|-------|--------|-------------|
| Phase 0: Ops cleanup | 15 min | None |
| Phase 1: R2 webhook fix | 30 min | Phase 0 |
| Phase 2: Lua merge | 1-2 hrs | Phase 1 |
| ~~Phase 3~~: Parser field 9 | **SKIP** (already implemented) | — |
| Phase 4: Deploy merged Lua | 20 min | Phase 2 |
| Phase 5: Bot fixes | 2-3 hrs | Phase 0 (parallel with Phase 6) |
| Phase 6: Website formulas | 1 hr | None (parallel with Phase 5) |
| Phase 7: Endstats Lua fixes | 2-3 hrs | Phase 0 |
| Phase 8: Git cleanup | 2-3 hrs | After code fixes |
| Phase 9: Minor fixes | 1 hr | After Phase 8 |
| **TOTAL** | **~9-13 hours** | — |

---

> **This document is the single source of truth for all remaining work.**
> **Execute phases in order. Validate at each gate. Never skip Phase 0.**
>
> Generated from 51 documentation files by 5 parallel reader agents.
> Date: 2026-02-20

---

## EXECUTION STRATEGY: USE AGENT TEAMS

**CRITICAL: You MUST use Claude Code's Agent Teams feature to parallelize work.**

Agent Teams allows you to spawn multiple specialized teammate agents that work
simultaneously in separate tmux panes. This is essential for completing ~9-13 hours
of work efficiently.

### How to Use Agent Teams

1. **Create a team** with `TeamCreate` at the start of your session
2. **Create tasks** with `TaskCreate` for each phase/sub-phase
3. **Spawn teammates** with the `Task` tool using `team_name` and `name` parameters
4. **Assign tasks** with `TaskUpdate` to give work to idle teammates
5. **Coordinate** via `SendMessage` and the shared task list

### Recommended Team Structure

| Agent Name | Type | Assigned Work |
|------------|------|---------------|
| `lua-fixer` | general-purpose | Phase 1 (R2 webhook), Phase 2 (Lua merge), Phase 7 (endstats) |
| `bot-fixer` | general-purpose | Phase 5a-5e (bot fixes) |
| `web-fixer` | general-purpose | Phase 6a-6f (website formula alignment) |
| `git-ops` | general-purpose | Phase 0 (ops cleanup), Phase 8 (git/branch), Phase 9 (minor fixes) |
| `validator` | general-purpose | Runs validation queries after each phase completes |

### Parallelization Rules

- **Phase 0** must complete before anything else (ops cleanup, safety)
- **Phase 1** must complete before Phase 2 and Phase 4 (Lua dependency chain)
- **Phase 5 and Phase 6** are parallel-safe (bot fixes + website fixes)
- **Phase 7** can run in parallel with Phase 5/6 (endstats is independent)
- **Phase 8** should run after code fixes are done (git cleanup)
- **Phase 9** can run in parallel with Phase 8

### Agent Spawn Example

```
TeamCreate: team_name="slomix-fixathon"
TaskCreate: "Phase 0: Operational cleanup" → assign to git-ops
TaskCreate: "Phase 1: Fix R2 webhook crash" → assign to lua-fixer
TaskCreate: "Phase 5: Bot fixes" → assign to bot-fixer (blocked by Phase 0)
TaskCreate: "Phase 6: Website formulas" → assign to web-fixer (parallel with Phase 5)
TaskCreate: "Phase 7: Endstats Lua fixes" → assign to lua-fixer (after Phase 1)
```

**Do NOT work sequentially as a single agent. Spawn the team and delegate.**
