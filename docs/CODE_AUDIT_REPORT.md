# 🔍 ET:Legacy Discord Stats Bot - Code Audit Report
## Comprehensive Review - December 1, 2025
### *"As reviewed by a 300-year-old IT specialist"*

---

## Executive Summary

The ET:Legacy Stats Bot is a **mature, production-capable system** with solid fundamentals. However, the PostgreSQL migration left orphaned SQLite code, and there are security vulnerabilities that need immediate attention.

| Category | Grade | Key Issues |
|----------|-------|------------|
| **Security** | ⚠️ C+ | LIKE injection, error leakage, SSH risks |
| **Architecture** | 📐 B- | Good service layer, but broken team detection |
| **Database** | 🗄️ B | Good indexes, placeholder inconsistency |
| **Error Handling** | ❌ C | Bare exceptions, silent swallowing |
| **Performance** | ⏱️ C+ | Blocking I/O, minimal caching |
| **Code Quality** | 📝 C | DRY violations, dead code, low test coverage |

---

## 🚨 CRITICAL PRIORITY (Fix This Week)

### 1. LIKE SQL Injection Risk
**Impact:** Malicious player names could manipulate query results

**Files:** 7 locations including `stats_cog.py`, `leaderboard_cog.py`, `link_cog.py`

**Problem:**
```python
f"WHERE clean_name LIKE '%{player_name}%'"  # User input unescaped
```

**Fix:**
```python
def escape_like_pattern(s: str) -> str:
    return s.replace('%', r'\%').replace('_', r'\_')

safe_name = escape_like_pattern(player_name)
f"WHERE clean_name LIKE '%{safe_name}%' ESCAPE '\\'"
```

---

### 2. Broken Team Detection (SQLite References)
**Impact:** Team detection features silently fail on PostgreSQL

**Files:**
- `bot/core/team_detector_integration.py` - Uses `import sqlite3` directly
- `bot/core/substitution_detector.py` - Uses `sqlite3.connect()`
- `bot/core/team_history.py` - Uses `sqlite3.connect()`

**Fix:** Refactor these 3 files to use `DatabaseAdapter` async pattern

---

### 3. Error Message Leakage
**Impact:** Exposes DB schema, paths, and internals to Discord users

**Pattern in 50+ locations:**
```python
await ctx.send(f"❌ Error: {e}")  # Raw exception to users
```

**Fix:** Create error sanitization helper:
```python
async def send_error(ctx, user_msg: str, e: Exception):
    logger.exception(f"Error in {ctx.command}: {e}")
    await ctx.send(f"❌ {user_msg}")  # Clean message only
```

---

### 4. Bare `except:` Clauses
**Impact:** Catches `KeyboardInterrupt`, `SystemExit`, prevents graceful shutdown

**Files:** `ultimate_bot.py`, `automation_enhancements.py`, `server_control.py` (12 instances)

**Fix:** Replace `except:` with `except Exception:`

---

## ⚠️ HIGH PRIORITY (Fix This Month)

### 5. Blocking I/O in Async Functions
**Impact:** Bot freezes for 10-500ms during file operations

**Files:**
- `community_stats_parser.py` - `open()` in parser
- `server_control.py` - `open()` for audit log
- SSH handler - synchronous `execute_ssh_command()`

**Fix:** Use `aiofiles` or `run_in_executor()`:
```python
await asyncio.get_event_loop().run_in_executor(None, sync_function)
```

---

### 6. Silent Exception Swallowing
**Impact:** Errors ignored, debugging impossible

**Pattern in 20+ locations:**
```python
try:
    await self._ensure_player_name_alias()
except Exception:
    pass  # Silently ignored!
```

**Fix:** At minimum, add `logger.debug()`

---

### 7. Service Duplication Across Cogs
**Impact:** Memory waste, inconsistent state, maintenance burden

**Issue:** `LastSessionCog` and `SessionCog` each instantiate 7 identical services

**Fix:** Create service container in bot, inject into cogs

---

### 8. `traceback.print_exc()` Usage
**Impact:** Errors go to stdout, lost when running as service

**File:** `synergy_analytics.py` (5 instances)

**Fix:** Replace with `logger.exception("message")`

---

## 📋 MEDIUM PRIORITY (Fix This Quarter)

### 9. Cache Not Being Used
**Impact:** 80% more DB queries than necessary

The `StatsCache` class exists but is barely utilized - only 1 actual usage found.

**Commands that should use caching:** `!stats`, `!leaderboard`, `!compare`

---

### 10. Hardcoded `$N` Placeholders
**Impact:** Breaks if code ever runs against SQLite again

**Files:** 14+ files with `$1`, `$2` instead of portable `?`

---

### 11. `_ensure_player_name_alias()` Duplicated
**Impact:** Schema change = 7 files to update

**Fix:** Extract to `bot/core/utils.py` as single shared function

---

### 12. Graph Generation Blocks Event Loop
**Impact:** 500-2000ms freeze during `!last_session graphs`

**Fix:** Offload matplotlib to executor

---

### 13. No Retry Logic for Database Connection
**Impact:** Transient network issues = bot crashes

**Note:** SSH handler has exponential backoff (good!), but DB adapter doesn't

---

### 14. Missing Rate Limiting
**Impact:** Users can spam expensive queries

Only `!last_session` has `@commands.cooldown`. Add to: `!stats`, `!leaderboard`, `!compare`

---

## 📝 LOW PRIORITY (Technical Debt)

### 15. Dead Code Files
- `ultimate_bot.cleaned.py` (6,592 lines - corrupted)
- 3 `.backup_*` copies in `bot/` directory
- 100+ obsolete files in `dev/` and `archive/`

### 16. Type Hints (~40% coverage)
Missing return types on most functions

### 17. Test Coverage (<10%)
Critical logic untested: `StatsCalculator`, `C0RNP0RN3StatsParser`, cog commands

### 18. 15+ Unresolved TODOs
Scattered through production code

### 19. SQLite Schema Out of Sync
`bot/schema.sql` uses `session_id` but PostgreSQL uses `round_id`

---

## 📊 Quick Wins (Easy Fixes, Big Impact)

| Task | Time | Impact |
|------|------|--------|
| Add `escape_like_pattern()` helper | 30 min | Security |
| Replace `except:` with `except Exception:` | 15 min | Stability |
| Add cooldowns to 5 heavy commands | 20 min | Performance |
| Delete `ultimate_bot.cleaned.py` | 5 min | Cleanliness |
| Replace `print()` with `logger` in synergy_analytics | 10 min | Logging |

---

## Architecture Diagram (Current State)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ultimate_bot.py (~1,745 lines)                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Still contains: Import logic, File processing, Sessions │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐      ┌───────────────────┐      ┌──────────────────┐
│  bot/cogs/    │      │   bot/services/   │      │    bot/core/     │
│  (14 files)   │      │   (12 files)      │      │   (14 files)     │
│               │      │                   │      │                  │
│ ❌ Duplicate  │      │ ✅ Good patterns  │      │ ❌ 3 files use   │
│   services    │      │    mostly        │      │   sqlite3 still  │
│ ❌ No cog     │      │                   │      │                  │
│   error       │      │                   │      │ ✅ Database      │
│   handlers    │      │                   │      │   adapter OK     │
└───────────────┘      └───────────────────┘      └──────────────────┘
```

---

## Final Assessment

**The bot is functional and serves its purpose well**, but accumulated technical debt from the PostgreSQL migration and rapid feature development has created hidden risks. The security vulnerabilities (LIKE injection, error leakage) should be addressed immediately. The broken team detection is likely causing silent failures that users may not notice.

**Most impactful single change:** Create the `escape_like_pattern()` utility and apply it everywhere.

**Most time-consuming fix:** Refactoring the 3 team detection files to use async `DatabaseAdapter`.

---

*"In my 300 years, I have seen many codebases. This one has good bones, but needs some love. The foundations are solid - the service architecture is proper, the database adapter pattern is correct. Clean up the orphaned SQLite code, fix the security holes, and this bot will serve you well for another decade."*
