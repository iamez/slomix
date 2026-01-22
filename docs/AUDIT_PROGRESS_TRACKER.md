# 📋 Code Audit Progress Tracker

## ET:Legacy Discord Stats Bot - Fix Tracking

### Last Updated: December 1, 2025

---

## How to Use This Document

This document tracks our progress on fixing issues identified in the code audit.
After each session, update the status of completed items and note any blockers.

**Status Legend:**

- ⬜ Not Started
- 🔄 In Progress
- ✅ Completed
- ⏸️ Blocked/On Hold
- ❌ Won't Fix (with reason)

---

## 🚨 CRITICAL PRIORITY (Week 1)

### Security Fixes

| # | Issue | Status | Notes | Date Completed |
|---|-------|--------|-------|----------------|
| 1.1 | Create `escape_like_pattern()` helper in `bot/core/utils.py` | ✅ | Also added sanitize_error_message | Dec 1, 2025 |
| 1.2 | Apply LIKE escaping in `stats_cog.py` | ✅ | 2 queries fixed | Dec 1, 2025 |
| 1.3 | Apply LIKE escaping in `leaderboard_cog.py` | ✅ | 1 query fixed | Dec 1, 2025 |
| 1.4 | Apply LIKE escaping in `link_cog.py` | ✅ | 2 queries fixed | Dec 1, 2025 |
| 1.5 | Apply LIKE escaping in other affected files | ⬜ | Check predictions_cog.py | |
| 2.1 | Refactor `team_detector_integration.py` to async | ❌ | Dead code - not imported anywhere | Dec 1, 2025 |
| 2.2 | Refactor `substitution_detector.py` to async | ❌ | Dead code - not imported anywhere | Dec 1, 2025 |
| 2.3 | Refactor `team_history.py` to async | ❌ | Dead code - not imported anywhere | Dec 1, 2025 |
| 2.4 | **Rewrite `team_cog.py` to async** | ✅ | Was using sqlite3 directly - ACTUAL broken file | Dec 1, 2025 |
| 3.1 | Create `send_safe_error()` helper | ✅ | Already in bot/core/utils.py | Dec 1, 2025 |
| 3.2 | Replace raw error messages in cogs | ✅ | 50+ locations across 13 files | Dec 1, 2025 |
| 4.1 | Replace bare `except:` in `ultimate_bot.py` | ✅ | Lines 1345-1349 | Dec 1, 2025 |
| 4.2 | Replace bare `except:` in `automation_enhancements.py` | ✅ | Lines 227, 231, 265, 269 | Dec 1, 2025 |
| 4.3 | Replace bare `except:` in `server_control.py` | ✅ | Lines 284, 382 | Dec 1, 2025 |

---

## ⚠️ HIGH PRIORITY (Week 2-3)

### Performance & Error Handling

| # | Issue | Status | Notes | Date Completed |
|---|-------|--------|-------|----------------|
| 5.1 | Add `aiofiles` to requirements.txt | ⬜ | | |
| 5.2 | Convert file I/O in `community_stats_parser.py` | ⬜ | | |
| 5.3 | Convert file I/O in `server_control.py` | ⬜ | audit log | |
| 5.4 | Wrap SSH handler sync methods | ⬜ | | |
| 6.1 | Add logging to silent exception handlers | ⬜ | 20+ locations | |
| 7.1 | Create service container class | ⬜ | | |
| 7.2 | Refactor `LastSessionCog` to use container | ⬜ | | |
| 7.3 | Refactor `SessionCog` to use container | ⬜ | | |
| 8.1 | Replace `traceback.print_exc()` in `synergy_analytics.py` | ✅ | 5 instances → logger.error | Dec 1, 2025 |
| 8.2 | Refactor `StopwatchScoring` to async PostgreSQL | ✅ | Created StopwatchScoringService | Dec 1, 2025 |

---

## 📋 MEDIUM PRIORITY (Week 4+)

### Optimization & Code Quality

| # | Issue | Status | Notes | Date Completed |
|---|-------|--------|-------|----------------|
| 9.1 | Implement cache in `stats_cog.py` | ⬜ | | |
| 9.2 | Implement cache in `leaderboard_cog.py` | ⬜ | | |
| 10.1 | Convert hardcoded `$N` to `?` placeholders | ⬜ | 14+ files | |
| 11.1 | Extract `_ensure_player_name_alias()` to shared util | ⬜ | 7 copies exist | |
| 12.1 | Offload matplotlib to executor | ⬜ | `session_graph_generator.py` | |
| 13.1 | Add retry logic to database adapter | ⬜ | | |
| 14.1 | Add cooldown to `!stats` command | ⬜ | | |
| 14.2 | Add cooldown to `!leaderboard` command | ⬜ | | |
| 14.3 | Add cooldown to `!compare` command | ⬜ | | |

---

## 📝 LOW PRIORITY (Technical Debt)

### Cleanup & Documentation

| # | Issue | Status | Notes | Date Completed |
|---|-------|--------|-------|----------------|
| 15.1 | Delete `ultimate_bot.cleaned.py` | ✅ | 6,592 lines dead code | Dec 1, 2025 |
| 15.2 | Delete `.backup_*` files in `bot/` | ✅ | 2 files removed | Dec 1, 2025 |
| 15.3 | Archive/remove obsolete `dev/` files | ⬜ | | |
| 16.1 | Add type hints to cog public methods | ⬜ | ~40% coverage | |
| 17.1 | Create unit tests for `StatsCalculator` | ⬜ | | |
| 17.2 | Create unit tests for parser | ⬜ | | |
| 18.1 | Resolve or remove TODO comments | ⬜ | 15+ items | |
| 19.1 | Update `bot/schema.sql` to match PostgreSQL | ⬜ | session_id vs round_id | |

---

## 🎯 Quick Wins (Can Do Anytime)

| Task | Time Est. | Status | Date |
|------|-----------|--------|------|
| Delete `ultimate_bot.cleaned.py` | 5 min | ✅ | Dec 1, 2025 |
| Replace `print()` with `logger` in synergy_analytics | 10 min | ⬜ | |
| Add cooldowns to heavy commands | 20 min | ⬜ | |
| Replace bare `except:` clauses | 15 min | ✅ | Dec 1, 2025 |

---

## 📅 Session Log

### December 1, 2025 - Session 3 (Continuation)

- ✅ Fixed `traceback.print_exc()` in `synergy_analytics.py` (5 instances → logger.error)
- ✅ Created `bot/services/stopwatch_scoring_service.py` - async PostgreSQL scorer
- ✅ Updated `team_cog.py` to use new async `StopwatchScoringService`
- ✅ **SECURITY FIX:** Sanitized error messages in 13 files (50+ locations):
  - `admin_cog.py` (3), `automation_commands.py` (9), `link_cog.py` (6)
  - `leaderboard_cog.py` (2), `last_session_cog.py` (1), `server_control.py` (12)
  - `session_cog.py` (2), `session_management_cog.py` (2), `stats_cog.py` (4)
  - `sync_cog.py` (1), `synergy_analytics.py` (1), `team_management_cog.py` (2)
  - `ultimate_bot.py` (2), `automation_enhancements.py` (4), `last_session_redesigned_impl.py` (1)
- All `{e}` and `{error}` in `ctx.send()` now use `sanitize_error_message()`

### December 1, 2025 - Session 2

- ✅ Fixed bare `except:` clauses in 3 files (5 instances total)
- ✅ Deleted dead code files (ultimate_bot.cleaned.py + 2 backups)
- ✅ **MAJOR FIX:** Rewrote `team_cog.py` from sqlite3 to async PostgreSQL
- ✅ Discovered team detector files (2.1-2.3) are dead code - not imported anywhere
- ✅ Created `bot/core/utils.py` with security helpers:
  - `escape_like_pattern()` - LIKE SQL injection prevention
  - `escape_like_pattern_for_query()` - Ready-to-use wrapped pattern
  - `sanitize_error_message()` - Remove sensitive info from errors
  - `send_safe_error()` - Safe error messages to users
  - `normalize_player_name()` - Remove ET color codes
- ✅ **SECURITY FIX:** Applied LIKE escaping to 5 vulnerable queries:
  - `stats_cog.py` - 2 queries
  - `leaderboard_cog.py` - 1 query
  - `link_cog.py` - 2 queries
- 🔄 Identified `StopwatchScoring` needs async refactor (used by team_cog.py)
- Note: predictions_cog.py LIKE queries are safe (use internal GUIDs, not user input)
- Note: StopwatchScoring temporarily wrapped with asyncio.to_thread()

### December 1, 2025 - Session 1

- ✅ Completed comprehensive code audit
- ✅ Created `CODE_AUDIT_REPORT.md`
- ✅ Created this progress tracker
- ✅ Fixed `CommandNotFound` responding to other bots' commands (ultimate_bot.py line 1685)

### [Next Session Date]

- [ ] Tasks completed...
- [ ] Blockers encountered...
- [ ] Notes...

---

## 🔧 Environment Notes

**VPS Details:**

- Host: `samba@192.168.64.116`
- Path: `/home/samba/share/slomix_discord/`
- Database: PostgreSQL `et_stats`

**Local Development:**

- Path: `z:\slomix_discord`
- Samba share mounted

**Bot Status:**

- Running on VPS since ~November 28, 2025
- Branch: `vps-network-migration`

---

## 📚 Related Documents

- `docs/CODE_AUDIT_REPORT.md` - Full audit findings
- `docs/TECHNICAL_OVERVIEW.md` - System architecture
- `.github/copilot-instructions.md` - AI agent context

---

## Notes & Blockers

*Add any blockers, dependencies, or notes here:*

- ~~Team detection refactor (2.1-2.3) is interdependent~~ - **RESOLVED: Files are dead code**
- Service container (7.x) is a larger refactor - may want to plan architecture first
- Some files may need VPS restart to test changes
- `StopwatchScoring` (tools/stopwatch_scoring.py) needs full async refactor - currently uses sqlite3
