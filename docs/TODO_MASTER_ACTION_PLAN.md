# Master TODO Action Plan

**Created:** 2026-01-16
**Status:** 📚 REFERENCE DOCUMENT (No immediate action needed)

> **Decision (Jan 16, 2026):** Bot is working fine. These are "nice-to-haves" for a community gaming bot, not critical fixes. Keep as reference for future improvements if needed.
>
> **User confirmed:** No website issues, no bot freezes, everything working. No action required.

---

## ⚠️ CRITICAL RESEARCH FINDINGS

### Finding 1: LIKE SQL Fix - ORIGINAL PLAN WAS WRONG!
- **Data format:** `team_a_guids` stores JSON arrays like `'["guid1", "guid2"]'`
- **`string_to_array` won't work** - it treats JSON as comma-separated, leaving quotes/brackets
- **CORRECT FIX:** Use PostgreSQL JSON functions: `jsonb_array_elements_text()`

### Finding 2: Admin Auth Fix - HIGH RISK OF BREAKING ADMINS!
- Bot uses database-backed permission system (`user_permissions` table)
- Existing `@is_admin()` decorator in `checks.py` already handles this properly
- Adding `guild_permissions.administrator` would **lock out database-backed admins**
- **CORRECT FIX:** Use existing `@is_admin()` decorator, not Discord role check

### Finding 3: Already Implemented Items
| Item | Status | Notes |
|------|--------|-------|
| `aiofiles` | Installed but UNUSED | In requirements.txt, 0 imports |
| `ensure_player_name_alias` | ALREADY CENTRALIZED | In database_adapter.py, imported by 5 cogs |
| Cooldowns | 35% done | 7/20 cogs have them |
| Webhook rate limiting | DONE | 5 per 60s limit exists |
| JSON array pattern | EXISTS | In team_manager.py - can copy |

---

## Sprint 1: Security Fixes (FOCUSED) - ~45 min

### 1.1 ~~LIKE SQL → JSON Array Fix~~ - DEFERRED ⏸️
**Status:** Working correctly, not a real injection risk (data from trusted table)
**Action:** Skip for now - only performance/polish concern
**Revisit:** If prediction_leaderboard becomes slow

### 1.2 Error Message Leakage (4 locations) ✅ DO THIS
**Files & Lines:**
- `bot/cogs/admin_predictions_cog.py:246, 314, 435`
- `bot/cogs/predictions_cog.py:712`

**Fix:** Import and use existing `sanitize_error_message()`:
```python
from bot.core.utils import sanitize_error_message
await ctx.send(f"❌ Failed to update prediction: {sanitize_error_message(e)}")
```
**Risk:** LOW - Function already used in server_control.py
**Time:** 15 min

### 1.3 Admin Channel Authorization - USE EXISTING DECORATOR
**File:** `bot/cogs/admin_predictions_cog.py` lines 45-55
**Issue:** Channel check bypasses role verification

**WRONG Fix (would break admins):**
```python
# DON'T DO THIS - locks out database-backed admins
if ctx.author.guild_permissions.administrator:
```

**CORRECT Fix:** Use existing `@is_admin()` decorator pattern:
```python
async def cog_check(self, ctx):
    """Use database-backed permission system like other admin cogs."""
    # Check owner
    owner_id = getattr(self.bot, 'owner_user_id', 0)
    if ctx.author.id == owner_id:
        return True

    # Check database for admin/moderator tier
    try:
        result = await self.bot.db_adapter.fetch_one(
            "SELECT tier FROM user_permissions WHERE discord_id = $1",
            (ctx.author.id,)
        )
        if result and result['tier'] in ['admin', 'moderator']:
            return True
    except Exception:
        pass

    # Fallback: admin channel (backward compatibility)
    if ctx.channel.id in self.config.admin_channels:
        return True

    return False
```
**Risk:** LOW - Matches pattern in 7 other admin cogs
**Time:** 20 min

### 1.4 SSH AutoAddPolicy (Documentation Only)
**File:** `bot/automation/ssh_handler.py` line 63
**Fix:** Add to deployment docs, not code change
**Risk:** NONE
**Time:** 10 min

---

## Sprint 2: Quick Wins - ~1 hour

### 2.1 Resolve TODO Comments (4 items)
| File | Line | Comment | Action |
|------|------|---------|--------|
| `bot/cogs/link_cog.py` | 1477 | `TODO: Implement persistent selection state` | Evaluate if needed or remove |
| `bot/services/voice_session_service.py` | 411 | `TODO: Use last_session logic to generate embeds` | Already using SessionEmbedBuilder - update comment |
| `bot/services/prediction_engine.py` | 410 | `TODO: Get actual winner from session results (Phase 4)` | Mark as future enhancement |
| `bot/core/team_manager.py` | 417 | `TODO: Implement` | Check context and implement or remove |

**Time:** 30 min

### 2.2 Fix Print Statement
**File:** `bot/retro_text_stats.py` line 203
```python
print(f"Error parsing player: {e}")  # → logger.error(f"Error parsing player: {e}")
```
**Time:** 2 min

### 2.3 Add Command Cooldowns (Priority Commands)
Add `@commands.cooldown(1, 5, commands.BucketType.user)` to heavy commands:

**High Priority (database-heavy):**
- `bot/cogs/synergy_analytics.py` - 6 commands (lines 217, 289, 399, 525, 730, 894)
- `bot/cogs/session_cog.py:278` - `list_sessions()`
- `bot/cogs/team_cog.py:68` - `teams_command()`

**Server Control (admin, longer cooldown):**
- `bot/cogs/server_control.py` - 11 commands (add 30s cooldown)

**Time:** 20 min

---

## Sprint 3: Silent Exception Handlers - ~1 hour

### 3.1 Add Logging to Silent Handlers (17 locations)

**`bot/ultimate_bot.py` (11 locations):**
Lines: 2036, 2046, 2314, 2342, 2378, 2387, 2561, 2573, 2600, 2616, 2657, 2745

Pattern: Replace `except Exception: pass` with:
```python
except Exception as e:
    logger.debug(f"Non-critical error (context): {e}")
```

**`bot/endstats_parser.py` (2 locations):**
Lines 216, 225 - ValueError during parsing (can stay silent, add comment)

**`bot/proximity_parser_v3.py` (2 locations):**
Lines 258, 273 - ValueError during parsing (can stay silent, add comment)

**`bot/retro_viz.py` line 79:**
Add logging or comment explaining why silent

**`bot/services/monitoring_service.py` line 68:**
`asyncio.CancelledError` - OK to stay silent (normal cancellation)

**Time:** 45 min

---

## Sprint 4: Technical Debt - ~1.5 hours (REVISED)

### 4.1 ~~Consolidate `_ensure_player_name_alias()`~~ - ALREADY DONE ✅
**Status:** Already centralized in `database_adapter.py`, imported by 5 cogs
**Action:** SKIP - No work needed

### 4.2 Fix Blocking I/O in Async (4 locations)
| File | Line | Issue | Fix |
|------|------|-------|-----|
| `bot/ultimate_bot.py` | 888 | `stdout.read()` in async | Use `await asyncio.to_thread()` |
| `bot/cogs/server_control.py` | 202 | `open()` for audit log | Use `aiofiles` |
| `bot/cogs/server_control.py` | 228-229 | `stdout.read()` in sync func | Make `execute_ssh_command()` async |
| `bot/cogs/server_control.py` | 533 | `open()` for file read | Use `aiofiles` |

**Time:** 1 hour

### 4.3 ~~Add `aiofiles` Dependency~~ - ALREADY DONE ✅
**Status:** Already in `requirements.txt:13` as `aiofiles>=23.2.0`
**Action:** SKIP - Just need to start using it

---

## Sprint 5: Website Bugs - ~1 hour

### 5.1 Investigate `navigateTo()` Function
**File:** `website/js/app.js`
**Issue:** Function referenced but possibly not defined
**Action:** Search for definition, fix or implement

### 5.2 Fix Live Session Query
**File:** Referenced in `WEBSITE_FIX_SESSION_2025-11-29.md`
**Action:** Investigate and fix

**Time:** 1 hour

---

## Sprint 6: Testing & Documentation - ~2 hours

### 6.1 Update Schema Documentation
**File:** `bot/schema.sql`
**Issue:** Doesn't match production PostgreSQL schema
**Action:** Sync with `tools/schema_postgresql.sql`

### 6.2 Add Unit Tests (Future)
- StatsCalculator tests
- Parser tests
- Website backend tests

---

## Summary by Priority (FOCUSED)

| Sprint | Focus | Time | Items | Notes |
|--------|-------|------|-------|-------|
| 1 | Security | 45min | 2 fixes | Error sanitization + Admin auth only |
| 2 | Quick Wins | 1h | TODOs, print, cooldowns | Cooldowns 35% done already |
| 3 | Exception Handlers | 1h | 17 silent handlers | Low risk |
| 4 | Technical Debt | 1h | Blocking I/O only | 2 items already done! |
| 5 | Website Bugs | 1h | 2 known issues | Needs investigation |
| 6 | Documentation | 2h | Schema, tests | Lower priority |

**Total Estimated Time:** ~6.75 hours

### Sprint 1 Scope (What We're Doing Now):
1. ✅ **Error sanitization** - 4 locations, LOW risk
2. ✅ **Admin auth fix** - Use existing `@is_admin()` pattern, LOW risk
3. ⏸️ ~~JSON array fix~~ - Deferred (working fine)
4. ⏸️ ~~SSH AutoAddPolicy~~ - Docs only, can do anytime

---

## Files to Modify (Complete List)

### Security (Sprint 1)
- `bot/cogs/predictions_cog.py` - lines 615-616, 712
- `bot/cogs/admin_predictions_cog.py` - lines 48-49, 246, 314, 435
- `bot/automation/ssh_handler.py` - line 63 (docs only)

### Quick Wins (Sprint 2)
- `bot/cogs/link_cog.py` - line 1477
- `bot/services/voice_session_service.py` - line 411
- `bot/services/prediction_engine.py` - line 410
- `bot/core/team_manager.py` - line 417
- `bot/retro_text_stats.py` - line 203
- `bot/cogs/synergy_analytics.py` - add cooldowns
- `bot/cogs/session_cog.py` - add cooldowns
- `bot/cogs/team_cog.py` - add cooldowns
- `bot/cogs/server_control.py` - add cooldowns

### Exception Handlers (Sprint 3)
- `bot/ultimate_bot.py` - 11 locations
- `bot/endstats_parser.py` - 2 locations
- `bot/proximity_parser_v3.py` - 2 locations
- `bot/retro_viz.py` - 1 location

### Technical Debt (Sprint 4)
- `bot/ultimate_bot.py` - remove duplicate function
- `bot/core/achievement_system.py` - remove duplicate function
- `bot/cogs/server_control.py` - async I/O fixes
- `requirements.txt` - add aiofiles

### Website (Sprint 5)
- `website/js/app.js`
- Website backend files TBD

---

## Verification Plan (DETAILED)

### Sprint 1 Testing:
1. **JSON Array Fix (1.1):**
   ```sql
   -- Test BEFORE change: Count predictions matching a known GUID
   SELECT COUNT(*) FROM match_predictions mp
   CROSS JOIN player_links pl
   WHERE team_a_guids::text LIKE '%' || pl.et_guid || '%'
   AND pl.et_guid = 'known_guid_here';

   -- Test AFTER change: Same query with new JSON syntax
   -- Results should be IDENTICAL
   ```

2. **Error Sanitization (1.2):**
   - Trigger an error condition intentionally
   - Verify sanitized message doesn't leak paths/credentials
   - Check logs still have full error

3. **Admin Auth (1.3):**
   - Test with user in `user_permissions` table (database admin)
   - Test with Discord admin role user
   - Test with regular user in admin channel (should FAIL now)

### After Each Sprint:
1. `python3 -m py_compile <modified_files>`
2. `python -m pytest tests/ -v`
3. Bot restart and live command testing
4. Check bot logs for errors

---

## Risk Assessment Summary

| Fix | Risk Level | Reason |
|-----|------------|--------|
| 1.1 JSON Array | MEDIUM | Query logic change - must verify results match |
| 1.2 Error Sanitize | LOW | Already used in other cogs successfully |
| 1.3 Admin Auth | LOW | Uses existing proven pattern from 7 other cogs |
| 1.4 SSH Docs | NONE | Documentation only |
| 2.x Quick Wins | LOW | Decorator additions, minor changes |
| 3.x Exception Handlers | LOW | Adding logging, not changing logic |
| 4.x Blocking I/O | MEDIUM | Async changes need careful testing |

---

## Notes

- Dead code `post_round_summary()` - NOT FOUND (already removed)
- Bare `except:` clauses - NONE FOUND (good!)
- Duplicate function count was 3, not 7 as documented
- `aiofiles` already in requirements - just unused
- `ensure_player_name_alias` already centralized - no work needed
- Cooldowns 35% implemented already (7/20 cogs)
