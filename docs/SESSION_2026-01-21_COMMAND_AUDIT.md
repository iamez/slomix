# Session Notes: Command Audit & Bug Fixes

**Date:** 2026-01-21
**Focus:** Systematic command audit across all bot cogs, bug identification and fixes

---

## Summary

Conducted Priority 1 and Priority 2 command testing, identified and fixed 6 bugs. Priority 3 (admin commands) partially tested - admin permission bug fixed, remaining commands need testing.

---

## Bugs Found & Fixed

### 1. `!teams` - Duplicate Players on Both Teams

**File:** `bot/core/team_manager.py`

**Problem:** Both Team A and Team B showed identical 6 players.

**Root Cause:** Detection algorithm used `round_number` (1 or 2) instead of `round_id` (unique per map). In stopwatch mode, teams swap sides between maps, so aggregating all Round 1s across maps caused players to appear on both teams.

**Fix:** Changed query to use `round_id` for team seeding:
```python
# Before: SELECT p.round_number, p.team, ...
# After:  SELECT p.round_id, p.team, ...
```

Also added validation to detect/clear corrupted session_teams data where both teams have identical GUIDs.

---

### 2. `!lb kd` - Column Alias Error

**File:** `bot/cogs/leaderboard_cog.py`

**Problem:** `column "total_kills" does not exist`

**Root Cause:** PostgreSQL cannot reference SELECT aliases inside ORDER BY expressions like `ORDER BY (CAST(total_kills AS FLOAT) / total_deaths)`.

**Fix:** Replace aliases with actual SUM() expressions:
```python
# Before: ORDER BY (CAST(total_kills AS FLOAT) / total_deaths) DESC
# After:  ORDER BY (CAST(SUM(p.kills) AS FLOAT) / SUM(p.deaths)) DESC
```

Same fix applied to `!lb teamwork` query.

---

### 3. `!season_info` - Wrong Column Name

**File:** `bot/core/season_manager.py`

**Problem:** `column s.session_date does not exist`

**Root Cause:** Query used `s.session_date` but the `rounds` table has `round_date`.

**Fix:**
```python
# Before: AND s.session_date >= ...
# After:  AND s.round_date >= ...
```

---

### 4. `!my_predictions` - Wrong Column Name

**File:** `bot/cogs/predictions_cog.py`

**Problem:** Query failed silently

**Root Cause:** Query used `et_guid` but `player_links` table has `player_guid`.

**Fix:**
```python
# Before: SELECT et_guid FROM player_links
# After:  SELECT player_guid FROM player_links
```

---

### 5. `!prediction_leaderboard` - Wrong Column Name

**File:** `bot/cogs/predictions_cog.py`

**Problem:** `column pl.et_guid does not exist`

**Root Cause:** Same as above - used `pl.et_guid` instead of `pl.player_guid`.

**Fix:** Replace all occurrences of `pl.et_guid` with `pl.player_guid`.

---

### 6. Admin Commands - Permission Check Failing

**File:** `bot/ultimate_bot.py`

**Problem:** All `@is_admin()` commands returned "requires admin permissions" even for bot owner.

**Root Cause:** `owner_user_id` was loaded in config but never copied to bot instance. The `is_admin()` check uses `getattr(ctx.bot, 'owner_user_id', 0)` which returned 0.

**Fix:** Added missing attribute copy:
```python
self.owner_user_id = self.config.owner_user_id
```

---

## Commands Tested

### Priority 1: Core User Commands ✅

| Command | Status | Notes |
|---------|--------|-------|
| `!ping` | ✅ Works | Shows latency, DB status |
| `!stats` | ✅ Works | |
| `!leaderboard` | ✅ Works | |
| `!lb kd` | ✅ Fixed | Was broken |
| `!compare` | ✅ Works | |
| `!season_info` | ✅ Fixed | Was broken |
| `!rounds` | ✅ Works | |
| `!session` | ✅ Works | |
| `!last_session` | ✅ Works | Previously tested |

### Priority 2: Feature Commands ✅

| Command | Status | Notes |
|---------|--------|-------|
| `!teams` | ✅ Fixed | Was showing duplicates |
| `!lineup_changes` | ✅ Works | |
| `!session_score` | ✅ Works | |
| `!team_record` | ✅ Works | Needs team name arg |
| `!head_to_head` | ✅ Works | Needs team args |
| `!team_pool` | ✅ Works | |
| `!synergy` | ⚠️ Disabled | Feature flag off |
| `!best_duos` | ⚠️ Disabled | Feature flag off |
| `!predictions` | ✅ Works | No data yet |
| `!prediction_stats` | ✅ Works | |
| `!my_predictions` | ✅ Fixed | Was broken |
| `!prediction_leaderboard` | ✅ Fixed | Was broken |
| `!achievements medals` | ✅ Works | |

### Priority 3: Admin Commands (Partial)

| Command | Status | Notes |
|---------|--------|-------|
| `!server_status` | ✅ Fixed | Permission was broken |
| `!map_list` | ✅ Works | Shows 42 maps |
| `!rcon status` | ⚠️ Timeout | Server may be offline |
| `!admin_list` | ✅ Fixed | Permission was broken |
| `!sync_today` | ❓ Not tested | |
| `!health` | ❓ Not tested | |
| `!ssh_stats` | ❓ Not tested | |
| `!automation_status` | ❓ Not tested | |
| `!metrics_summary` | ❓ Not tested | |
| `!admin_audit` | ❓ Not tested | |

---

## Files Modified

1. `bot/core/team_manager.py` - Team detection algorithm fix
2. `bot/cogs/leaderboard_cog.py` - ORDER BY alias fixes
3. `bot/core/season_manager.py` - Column name fix
4. `bot/cogs/predictions_cog.py` - Column name fixes (2 locations)
5. `bot/ultimate_bot.py` - Added owner_user_id attribute

---

## Database Changes

- Cleared corrupted `session_teams` data for 2026-01-21 (both teams had identical players)

---

## Still TODO

1. Complete Priority 3 admin command testing
2. Test `!teams` after fix (verify correct team split)
3. Test prediction commands after restart
4. Synergy commands disabled - may need enabling/testing later

---

## Technical Insights

### PostgreSQL vs SQLite Differences
- PostgreSQL cannot reference SELECT aliases in ORDER BY expressions
- Column names must match exactly (no implicit aliasing)

### Stopwatch Mode Complexity
- Teams swap sides between maps (not just R1/R2)
- Team detection must use `round_id` (unique per map) not `round_number`
- First map's R1 provides the "seed" team composition

### Permission System
- `@is_admin()` checks `user_permissions` table OR `owner_user_id`
- `@is_admin_channel()` checks channel ID (different from user permissions)
- Bot must copy config attributes to self for checks to work
