# Backlog Review - Tasks To Consider

**Generated:** 2026-01-16
**Purpose:** Consolidated list of forgotten/pending tasks from documentation review

---

## Priority 1: Security Issues (CRITICAL)

These should be addressed first for production safety:

| Issue | Location | Effort |
|-------|----------|--------|
| LIKE SQL injection (7 locations) | `CODE_AUDIT_REPORT.md` lines 26-46 | 30 min |
| Error message leakage (50+ locations) | `CODE_AUDIT_REPORT.md` lines 64-80 | 1-2 hours |
| AutoAddPolicy() accepts ANY SSH server | `SECURITY_AUDIT_COMPREHENSIVE.md` | 15 min |
| Admin checks only verify channel, not role | `SECURITY_AUDIT_COMPREHENSIVE.md` | 30 min |
| Webhook verification only checks ID, no HMAC | `SECURITY_AUDIT_COMPREHENSIVE.md` | 30 min |

---

## Priority 2: Code Quality Quick Wins

Low effort, high impact cleanup:

| Task | Location | Effort |
|------|----------|--------|
| Replace `print()` with `logger` | `AUDIT_PROGRESS_TRACKER.md` | 10 min |
| Add cooldowns to heavy commands | `AUDIT_PROGRESS_TRACKER.md` items 14.1-14.3 | 20 min |
| Resolve 15+ TODO comments | `AUDIT_PROGRESS_TRACKER.md` item 18.1 | 1 hour |
| Remove dead `post_round_summary()` code (79 lines) | `POSTING_SYSTEMS_INVESTIGATION.md` | 5 min |

---

## Priority 3: Known Bugs (Unsolved)

| Bug | Status | File Reference |
|-----|--------|----------------|
| 13 records: `time_dead > time_played` | Low priority - rare edge case | `CLAUDE.md` line 197 |
| Website `navigateTo()` function broken | Needs investigation | `WEBSITE_APPJS_CHANGES_2025-11-28.md` |
| Live session query broken | Needs fix | `WEBSITE_FIX_SESSION_2025-11-29.md` |

---

## Priority 4: Technical Debt

| Task | Details | Effort |
|------|---------|--------|
| Add async file I/O (`aiofiles`) | Blocking I/O freezes bot | 2-3 hours |
| Silent exception handlers (20+ locations) | Add logging | 1 hour |
| Duplicate service instantiation in Cogs | DRY violation | 2 hours |
| Extract `_ensure_player_name_alias()` | 7 duplicate copies exist | 30 min |
| Offload matplotlib to executor | `session_graph_generator.py` | 1 hour |
| Add retry logic to database adapter | Resilience improvement | 1 hour |
| Add type hints to cog public methods | ~40% coverage currently | 2-3 hours |

---

## Priority 5: Missing Features (Roadmap)

### From IMPLEMENTATION_PROGRESS_TRACKER.md:

| Feature | Phase | Status |
|---------|-------|--------|
| Form analysis (enhanced) | Phase 5 | Missing - needs session results data |
| Map performance analysis | Phase 5 | Missing - needs historical data |
| Substitution impact analysis | Phase 5 | Missing |
| Live match scoring | Phase 4 | Future - not started |
| Fine-tune prediction weights | Phase 5 | 86% complete, 1 hour remaining |

### From ENHANCEMENT_IDEAS.md (Nice to Have):

- Player trend analysis (K/D, DPM over time)
- Advanced stat filtering (by weapon, map, time period)
- More granular achievement badge tiers
- Clan/team statistics
- Match replay link integration

### Season System Enhancement (SEASON_SYSTEM.md lines 91-98):

- Current: Leaderboards show all-time stats
- Planned: `!leaderboard kills` → Current season, `!leaderboard kills all` → All-time

---

## Priority 6: Testing Gaps

| Gap | Details |
|-----|---------|
| Unit tests for StatsCalculator | Not implemented |
| Unit tests for parser | Not implemented |
| pytest for website backend | Not implemented |
| Current status: 62 passed, 20 skipped (DB tests) | Some tests auto-skip |

---

## Priority 7: Documentation Updates

| Task | File |
|------|------|
| Update `bot/schema.sql` to match PostgreSQL | `AUDIT_PROGRESS_TRACKER.md` item 19.1 |
| Schema mismatch: session_id vs round_id | Current schema doesn't match production |

---

## Completed Recently (Jan 15, 2026)

For reference - these were done in today's session:

- [x] Cumulative endstats in `!last_session`
- [x] Endstats double-posting race condition fix
- [x] VS Stats explanation for readers
- [x] Voice session end crash fix (bot restart)
- [x] Endstats file routing fix
- [x] PostgreSQL adapter API mismatch fix in MonitoringService
- [x] Created `processed_endstats_files` table

---

## Recommendation

**Start with Priority 1 (Security)** - these are critical for production.

Then **Priority 2 (Quick Wins)** - low effort improvements that clean up the codebase.

The rest can be tackled based on available time and interest.

---

## Key Reference Files

- `docs/AUDIT_PROGRESS_TRACKER.md` - Central tracking document
- `docs/CODE_AUDIT_REPORT.md` - Detailed issue list with line numbers
- `docs/IMPLEMENTATION_PROGRESS_TRACKER.md` - Feature roadmap
- `docs/ENHANCEMENT_IDEAS.md` - Future feature ideas
- `docs/SECURITY_AUDIT_COMPREHENSIVE.md` - Security findings
