# 🎯 ET:Legacy Bot - Active Sprint Tasks

**Last Updated:** October 11, 2025  
**Focus:** Documentation updates and automation testing

---

## 🔥 PRIORITY 1 - Critical Fixes (Do First)

### Task 1: Fix Bulk Import Unicode Issues
**Status:** ✅ COMPLETE  
**File:** `dev/bulk_import_stats.py`  
**Issue:** Emoji characters cause `UnicodeEncodeError` in Windows PowerShell  
**Solution:** Replaced all emoji logging with ASCII equivalents  
**Completed:** October 10, 2025

**Changes Needed:**
- Line 476: `🚀` → `[START]`
- Line 497: `🔢` → `[LIMIT]`
- Line 502: `⚠️` → `[WARN]`
- Line 505: `📊` → `[INFO]`
- Line 532: `✅` → `[DONE]`
- Line 542: `📊` → `[STATS]`
- Line 544: `✅` → `[OK]`
- Line 546: `❌` → `[FAIL]`
- Line 568: `⚠️` → `[ERRORS]`
- Line 651: `⚠️` → `[WARN]`

**Test Command:**
```powershell
python dev/bulk_import_stats.py --year 2025 --limit 10
```

---

### Task 2: Import All Historical Stats Files
**Status:** ✅ COMPLETE  
**File:** `dev/bulk_import_stats.py`  
**Goal:** Import all files from `local_stats/`  
**Database:** `bot/etlegacy_production.db`  
**Completed:** October 11, 2025 - 1,862 sessions imported successfully

**Results:**
- ✅ 1,862 sessions from 2025 imported
- ✅ 25 unique player GUIDs tracked
- ✅ UNIFIED 53-column schema with 7 tables
- ✅ All records verified and tested
- ✅ processed_files table tracking all imports

---

### Task 3: SQL Column Bug Fixes
**Status:** ✅ COMPLETE  
**File:** `bot/ultimate_bot.py`  
**Goal:** Fix SQL column reference errors in 5 commands  
**Completed:** October 11, 2025

**Fixed Commands:**
1. ✅ `!stats` - Fixed player_guid column reference
2. ✅ `!link` - Fixed discord_user_id → discord_id
3. ✅ `!leaderboard` - Fixed ORDER BY for all 13 stat types
4. ✅ `!session` - Fixed aggregation column references
5. ✅ `!last_session` - Fixed session_teams table queries

**See:** `BUGFIX_LOG_OCT11.md` for detailed documentation

---

### Task 4: !last_session Command Restructure
**Status:** ✅ COMPLETE  
**File:** `bot/ultimate_bot.py`  
**Goal:** Restructure command with subcommands for better organization  
**Completed:** October 11, 2025

**Improvements:**
- ✅ 7+ embeds with comprehensive analytics
- ✅ Team scoring and MVP calculations
- ✅ Weapon mastery breakdowns per player
- ✅ Special awards system (13 award types)
- ✅ Stopwatch team score integration
- ✅ Modular subcommand structure

**See:** `LAST_SESSION_RESTRUCTURE.md` for details

---

### Task 5: Implement Enhanced MVP Calculation
**Status:** ⏳ Optional - Not Critical  
**File:** `bot/ultimate_bot.py`  
**Goal:** Weight-based MVP scoring using objective stats  
**Priority:** Low (current MVP calculation works)

**Implementation Plan:**

```python
def calculate_mvp_score(player_stats: dict, awards: dict) -> float:
    """
    Calculate weighted MVP score combining combat, objectives, support
    
    Args:
        player_stats: Basic stats (kills, deaths, damage, dpm)
        awards: Objective stats JSON (xp, assists, dynamites, revives, etc.)
    
    Returns:
        Float score (0-100)
    """
    
    # Combat Score (40% weight)
    # - Kills, Headshots, K/D ratio, DPM
    combat_score = calculate_combat_score(player_stats, awards)
    
    # Objective Score (30% weight)
    # - Objectives stolen/returned, Dynamites planted/defused
    objective_score = calculate_objective_score(awards)
    
    # Support Score (20% weight)
    # - Times revived, Kill assists, Team damage prevention
    support_score = calculate_support_score(awards)
    
    # Performance Score (10% weight)
    # - Multikills, Time alive ratio, Accuracy
    performance_score = calculate_performance_score(awards)
    
    # Weighted total
    mvp_score = (
        combat_score * 0.40 +
        objective_score * 0.30 +
        support_score * 0.20 +
        performance_score * 0.10
    )
    
    return mvp_score
```

**Location to Add:**
- New functions: After line 500 in `ultimate_bot.py`
- Update MVP display: Line ~1200 (Team Stats embed)

**Fields to Use:**
```python
# From awards JSON:
- xp (general contribution)
- kill_assists
- objectives_stolen, objectives_returned
- dynamites_planted, dynamites_defused
- times_revived
- headshot_kills
- multikill_2x, multikill_3x, multikill_4x, multikill_5x
- time_dead_ratio (lower is better)
- useful_kills
```

---

### Task 4: Test Bot in Discord
**Status:** ⏳ Blocked (waiting for Task 2)  
**Goal:** Verify all embeds display correctly with real data  
**ETA:** 30 minutes

**Test Checklist:**
- [ ] `!last_session` - All 7 embeds display
- [ ] Objective & Support Stats embed shows data
- [ ] MVP calculation uses new formula (after Task 3)
- [ ] `!stats <player>` - Shows objective stats
- [ ] `!leaderboard xp` - Sorts by XP from awards
- [ ] No errors in bot terminal output
- [ ] Embeds are properly formatted

---

## 📊 PRIORITY 2 - Data Quality Refinements

### Task 5: Perfect Objective Timing Calculations
**Status:** 📝 Design Phase  
**Files:** `bot/community_stats_parser.py`  
**Issue:** Some edge cases with objective completion times  
**ETA:** 2 hours

**Known Issues:**
- Round 2 time calculations sometimes off by a few seconds
- Team switches mid-round can affect timing
- Spectator time included in calculations

**Investigation Needed:**
- Check `analyze_time_calculation.py` findings
- Review `check_time_issue.py` results
- Test with edge case files

---

### Task 6: Complete Grenade AOE Damage Attribution
**Status:** 📝 Design Phase  
**Files:** `bot/community_stats_parser.py`, possibly new field in parser  
**Issue:** Grenade splash damage not fully attributed to thrower  
**ETA:** 3 hours

**Research Files:**
- `analyze_grenade_aoe.py` - Findings on current state
- `check_grenades.py` - Validation script

**Possible Solutions:**
- Parse additional fields from Lua output
- Calculate AOE damage from kill positions
- Add new field: `grenade_damage_dealt`

---

### Task 7: Refine Team Switch Detection
**Status:** 📝 Design Phase  
**Files:** `bot/community_stats_parser.py`  
**Issue:** Mid-round team switches can skew round stats  
**ETA:** 2 hours

**Investigation Files:**
- `check_session_teams.py`
- `check_teams.py`
- `analyze_oct2_with_teams.py`

**Goal:** Track team changes per player per round, attribute stats correctly

---

### Task 8: Weapon Stats Backfill
**Status:** 📝 Design Phase  
**Files:** `backfill_weapon_stats.py`  
**Issue:** Some old sessions missing weapon breakdowns  
**ETA:** 1 hour

**Steps:**
1. Identify sessions with missing weapon stats
2. Re-parse original stat files
3. Update database with weapon data
4. Verify completeness

---

## 📈 Progress Tracking

### Current Sprint Status
- **Completed:** 5/14 tasks (36%)
- **In Progress:** 1/14 tasks (7%)
- **Blocked:** 2/14 tasks (14%)
- **Not Started:** 6/14 tasks (43%)

### Priority 1 Completion
- **Completed:** 0/4 critical tasks (0%)
- **Target Date:** October 11, 2025 (tomorrow)

### Priority 2 Completion
- **Completed:** 0/4 refinement tasks (0%)
- **Target Date:** October 15, 2025 (5 days)

---

## 🚀 Quick Start Commands

### Test the bot:
```powershell
cd bot
python ultimate_bot.py
```

### Fix and run bulk import:
```powershell
# After fixing unicode issues:
python dev/bulk_import_stats.py --year 2025 --limit 10   # Test with 10 files
python dev/bulk_import_stats.py --year all               # Full import
```

### Verify data:
```powershell
python verify_awards.py
python check_database_status.py
```

### Check import results:
```powershell
python check_import_results.py
```

---

## 📝 Notes

- Database in use: `bot/etlegacy_production.db`
- Stats source: `local_stats/` (3,300+ files)
- Parser: `bot/community_stats_parser.py` (33-field extraction)
- Bot: `bot/ultimate_bot.py` (objective stats embed on line 1361)

---

## ✅ Completed Previously

1. ✅ Enhanced parser (33 fields)
2. ✅ Database integration (awards JSON)
3. ✅ Bot display (objective stats embed)
4. ✅ Testing (single file import works)
5. ✅ Verification (data queryable and correct)
