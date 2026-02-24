# Handoff: Remaining TODO Items

**Date**: 2026-02-24
**Session**: Mega cleanup execution + deep research + formula fixes
**Branch**: `reconcile/merge-local-work`

---

## What Was DONE This Session (5 commits)

1. `cb5ea19` — Mega cleanup & hardening (34 files)
2. `aa116a6` — Formula fixes: headshot %, denied playtime display (6 files)
3. `ac9369a` — ADR/KPR/DPR standard metrics + remaining SQLite cleanup (3 files)
4. `2deceb8` — Untrack 36 non-essential files from git
5. `5a1d018` — Skill rating implementation plan doc

Plus 3 deep research reports written to `docs/reports/`.

---

## REMAINING: Code Fixes

### 1. Stats Formula Fixes — Partially Done

**Done:**
- [x] Headshot % corrected everywhere (bot + website)
- [x] Denied playtime display changed to per-minute rate
- [x] Website headshot rate fixed (2 locations in api.py)
- [x] time_played_seconds already uses per-player Lua time
- [x] Website FragPotential, Damage Efficiency, Survival Rate already aligned with bot

**Not done:**
- [ ] **Headshot % callers audit** — verify ALL commands/embeds that display headshot stats are passing the correct values (headshot_hits vs headshot_kills). Search `headshot` across all cogs.
- [ ] **Add `total_hits` column to `player_comprehensive_stats`** — currently needs `SUM(weapon_comprehensive_stats.hits)` subquery. Adding a pre-computed column would simplify queries. See `docs/STATS_FORMULA_RESEARCH.md` §2.1.

### 2. Remaining SQLite Dead Code

**Done:**
- [x] link_cog.py — 7 SQLite branches removed (3 INSERT + 4 query branches)
- [x] team_history.py — f-string fixed + deprecation comment
- [x] team_detector_integration.py — deprecation comment added

**Not done:**
- [ ] **Full SQLite purge audit** — Search entire codebase for remaining `sqlite`, `INSERT OR REPLACE`, `AUTOINCREMENT`, `database_type == 'sqlite'` patterns. There may be more in other cogs or core modules.
- [ ] **Consider deleting** `team_history.py` and `team_detector_integration.py` entirely (they're SQLite-only and deprecated, not just commented).

### 3. Print Statements in api.py

- [ ] **~25+ remaining `print()` calls in `website/backend/routers/api.py`** — Only the ones at lines 1568/1575 were converted to `logger`. Lines 1240, 1519, 2235, 2242, 2317, 2930, 3019, 3259, etc. still use `print()`. Convert all to `logger.warning()` or `logger.info()`.

---

## REMAINING: GitHub Cleanup

### Done:
- [x] .gitignore v2.0 with comprehensive patterns
- [x] 36 non-essential files untracked via `git rm --cached`
- [x] 8 AI instruction docs moved to `docs/instructions/`
- [x] SAFETY_VALIDATION_SYSTEMS.md encoding fixed
- [x] Version aligned to v1.0.8

### Not done:
- [ ] **PLANNING_ROOM duplicate** — `docs/PLANNING_ROOM.md` and `docs/PLANNING_ROOM_MVP.md` are byte-identical. Delete one (or both if outdated).
- [ ] **More files to untrack?** — The .gitignore patterns may not catch everything. Run `git ls-files -ci --exclude-standard` periodically to check for new matches.
- [ ] **CONTRIBUTING.md** — Add commit policy (what to commit, what not to commit). Referenced in Phase 5 report but not created yet.

---

## REMAINING: Research Recommendations (from Phase 6 + Deep Research)

### Priority 1: Quick Wins

| Item | Effort | Details |
|------|--------|---------|
| **Add ADR/KPR/DPR to commands** | Low | Functions exist in `calculator.py` now. Wire into `!stats`, `!leaderboard`, website API. |
| **Promote Denied Playtime + Useful Kills** | Low | These are Slomix's most original metrics. Make them headline stats in embeds and website. |
| **Skill Rating (Option C)** | Medium | See `docs/SKILL_RATING_IMPLEMENTATION_PLAN.md`. Individual ET Rating, no win/loss needed. |

### Priority 2: Libraries to Adopt

| Library | Purpose | Effort | File |
|---------|---------|--------|------|
| **openskill** | Skill ratings (Option A/B from plan) | Medium | `pip install openskill` |
| **AsyncSSH** | Replace paramiko in SSH monitoring | Medium | `bot/automation/ssh_handler.py` |
| **Alembic** | Versioned DB migrations | Medium | 68 tables need version control |
| **reactionmenu** | Replace 3 custom pagination views | Low | `bot/core/pagination_view.py`, `lazy_pagination_view.py`, `endstats_pagination_view.py` |

### Priority 3: Architecture Improvements

- [ ] **Redis as message queue** between SSH monitor and parser (from OpenDota pattern)
- [ ] **Separate API layer** — REST API between database and all consumers
- [ ] **Docker deployment option** — for other ET:Legacy communities
- [ ] **Pipeline reliability** — dead letter queue table for failed imports, SSH retry with backoff, health check endpoint

---

## REMAINING: Documentation

### Done:
- [x] memories.md updated (21 cogs, 68 tables, v1.6.2)
- [x] AI_COMPREHENSIVE_SYSTEM_GUIDE.md counts fixed
- [x] COMPLETE_SYSTEM_RUNDOWN.md deprecation notice
- [x] CLAUDE.md aligned to v1.0.8

### Not done:
- [ ] **Add CLAUDE.md to 8 directories** — Listed in handoff but not created:
  - `gemini-website/` (has some docs but no CLAUDE.md)
  - `proximity/` (has PROXIMITY_CLAUDE.md but could use standard CLAUDE.md)
  - `greatshot/`
  - `tools/`
  - `vps_scripts/`
  - `scripts/`
  - `docker/`
  - `migrations/`
- [ ] **Update stale docs**:
  - `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` — partially updated, may still have stale sections beyond the counts
  - `docs/COMMANDS.md` — verify it lists all 80+ commands across 21 cogs

---

## REMAINING: Infrastructure (Phase F — Separate Session)

These require VPS access and should be done carefully:

| Item | Doc | Risk |
|------|-----|------|
| **Apply VM firewall rules** | `docs/VM_FIREWALL_RULES_2026-02-20.md` | Medium — could lock out SSH if wrong |
| **Apply Fail2Ban configuration** | `docs/FAIL2BAN_SETUP_2026-02-21.md` | Low-Medium |
| **Lua Time Stats Overhaul** | `docs/KNOWN_ISSUES.md` (10-step plan) | High — server-side Lua changes |
| **Flip round_correlation_service to LIVE** | `bot/services/round_correlation_service.py` | Low — just change DRY_RUN flag |
| **Fix stats formula inconsistencies** | `docs/STATS_FORMULA_RESEARCH.md` | Mostly done now (headshot %, FP, etc.) |
| **Upload Library 3 known bugs** | `docs/KNOWN_ISSUES.md` | Medium |

---

## REMAINING: Gemini Website

From memories.md (session 2026-02-23):
- [ ] Test with live backend (dev server on port 3000 → proxy to 8000)
- [ ] Season page (`/api/seasons/current`)
- [ ] Recharts integration (installed but unused)
- [ ] Verify all new API endpoints return expected shapes
- [ ] Mobile responsive testing
- [ ] Auth integration (Discord OAuth)

---

## REMAINING: Data Ingest Queue

From `docs/BRAINSTORM_SESSION_2026-02-21.md` and `docs/DATA_INGEST_QUEUE_DESIGN.md`:
- [ ] Review the 8 brainstorm questions (queue backend, timeout, required sources, etc.)
- [ ] Implement `bot/services/ingest/queue.py` beyond skeleton
- [ ] Wire into webhook handlers and stats parser
- [ ] Create background correlation task (every 5 seconds)
- [ ] Test end-to-end with real data

---

## Reports Generated This Session

| Report | Lines | Content |
|--------|-------|---------|
| `docs/reports/DEEP_RESEARCH_SIMILAR_PROJECTS.md` | 646 | 20+ similar projects across 5 tiers, component comparison matrix |
| `docs/reports/DEEP_RESEARCH_ALGORITHMS_AND_QUALITY.md` | 856 | HLTV 2.0/3.0, KAST, ADR, code quality scorecard (6.8/10), top 5 improvements |
| `docs/reports/DEEP_RESEARCH_ALGORITHMS.md` | 782 | FPS metrics deep dive, skill rating systems, session detection |
| `docs/SKILL_RATING_IMPLEMENTATION_PLAN.md` | 225 | Three-option plan for ET:Legacy skill ratings |

All phase audit reports from the mega cleanup are in `docs/reports/PHASE1-7_*.md`.

---

## Suggested Execution Order for Next Session

1. **Wire ADR/KPR/DPR into commands** (quick win, functions already exist)
2. **Full SQLite purge audit** (search and destroy remaining dead code)
3. **Convert remaining print() to logger in api.py** (25+ locations)
4. **Add CLAUDE.md to key directories** (8 directories)
5. **Flip round_correlation_service to LIVE** (one flag change)
6. **Start Skill Rating Option C** (individual ET Rating prototype)
7. **Evaluate AsyncSSH** (replace paramiko in SSH monitor)

---

*Generated 2026-02-24 from mega cleanup session context.*
