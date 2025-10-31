# 🧪 ET:LEGACY BOT - COMPREHENSIVE TESTING CHECKLIST

**Purpose:** Verify bot stability after code cleanup fixes  
**Date Created:** October 30, 2025  
**Last Updated:** After ruff/black/isort cleanup

---

## 📋 INSTRUCTIONS FOR AGENT

Please run **Phase 1** (automated tests) and report the results with full command output. After Phase 1 passes, the user will manually test Phase 2-5 in Discord.

---

## PHASE 1: AUTOMATED TESTS ✅

Run these commands and paste the full output:

```bash
# 1. Run the alias fallback test
pytest tests/test_alias_fallback.py -v

# 2. Run all tests (if more exist)
pytest tests/ -v

# 3. Check for syntax errors
python -m py_compile bot/ultimate_bot.py

# 4. Run linter for remaining issues
python -m ruff check bot/ultimate_bot.py
```

### Expected Results:
- ✅ All pytest tests should PASS
- ✅ No syntax errors in py_compile
- ✅ Ruff should show minimal warnings (mostly style/line-length)

### If Tests Fail:
- Document the exact error message
- Note which test failed
- Check if it's a critical bug or just a warning

---

## PHASE 2: BOT STARTUP TEST (User will test)

```bash
python bot/ultimate_bot.py
```

### Success Indicators:
```
🚀 Initializing Ultimate ET:Legacy Bot...
✅ Database schema validated: 53 columns (UNIFIED)
✅ Ultimate Bot initialization complete!
📋 Commands available: ['stats', 'leaderboard', 'last_session', ...]
```

### Watch For:
- ❌ Duplicate command errors → Still needs fixing
- ❌ Database schema mismatch → Wrong database version
- ❌ Import errors → Missing dependencies
- ❌ Discord connection failure → Check token

---

## PHASE 3: DISCORD COMMAND TESTS (User will test)

### 3.1 - Basic Commands
```
!ping
!help
!stats
```
**Expected:** All respond without errors

---

### 3.2 - Last Session Commands (CRITICAL - These had bugs!)

**Main Command:**
```
!last_session
```

**Watch for these specific errors:**
- ❌ `NameError: name '_log_and_send' is not defined` → Line 3592 issue
- ❌ `NameError: name 'total_maps' is not defined` → Line 4156 issue  
- ❌ `NameError: name 'session_date' is not defined` → Line 5932 issue
- ✅ Shows session data correctly → All good!

**Compact Version:**
```
!last_session_compact
```
**Expected:** Shows compact view (renamed old command)

**Aliases:**
```
!last
!latest
!recent
```
**Expected:** All work (aliases for `last_session_compact`)

---

### 3.3 - Stats Command
```
!stats vid
!stats @YourDiscordUser
```

**Watch for:**
- ✅ Shows player stats with K/D ratio
- ❌ Crashes on NULL values → Need safe_divide helpers
- ⚠️ K/D ratio missing from display → Cosmetic bug (line 7222)

---

### 3.4 - Leaderboard Commands
```
!leaderboard kills
!lb kd
!lb dpm
!lb accuracy
```
**Expected:** All show top 10 players without crashes

---

## PHASE 4: EDGE CASE TESTS (User will test)

### 4.1 - Empty Database Test
```
!last_session
!stats randomname
!leaderboard
```
**Expected:** Friendly error messages, NOT crashes

---

### 4.2 - Invalid Input Test
```
!stats
!stats @NonexistentUser  
!leaderboard invalidtype
```
**Expected:** Helpful error messages, NOT crashes

---

### 4.3 - Rate Limiting Test
Spam commands rapidly (5+ times fast):
```
!last_session
!last_session
!last_session
!last_session
!last_session
```
**Expected:** All complete without Discord API rate limit errors

---

## PHASE 5: CRITICAL BUG VERIFICATION (User will test)

### 5.1 - `_log_and_send` Function (Line 3592)
**Test:** Run `!last_session` command  
**If Error:** `NameError: name '_log_and_send' is not defined`

**Quick Fix:**
```python
# Find line ~3592 and replace:
await _log_and_send(embed, "combat")

# With:
await ctx.send(embed=embed)
```

---

### 5.2 - `total_maps` Variable (Line 4156)
**Test:** Run `!last_session` command  
**If Error:** `NameError: name 'total_maps' is not defined`

**Quick Fix:**
```python
# Add before line ~4156:
total_maps = len(map_list) if map_list else 0

# Then use it:
description=f"Best performers from {total_maps} maps • {player_count} total players"
```

---

### 5.3 - `session_date` Variable (Line 5932)
**Test:** Run `!last_session` with various parameters  
**If Error:** `NameError: name 'session_date' is not defined`

**Quick Fix:**
```python
# Ensure session_date is defined before use
# Check the conditional at line ~5932:
title = (
    session_date if "session_date" in locals() else "Latest Session"
)
```

---

### 5.4 - `kd` Variable Not Displayed (Line 7222)
**Test:** Run command showing top 3 players  
**Issue:** K/D is calculated but never shown to users

**Enhancement (Non-critical):**
```python
# Find line ~7227 and modify to include kd:
value=f"**GUID:** {guid}\n{kills:,} kills | K/D: {kd:.2f} | {games:,} games | Last: {last_seen}"
```

---

## 📝 TESTING REPORT TEMPLATE

```
=== ET:LEGACY BOT TESTING REPORT ===
Date: [DATE]
Tester: [NAME]

PHASE 1 - Automated Tests
[ ] pytest passed
[ ] No syntax errors  
[ ] Ruff check passed
Issues found: _______________

PHASE 2 - Bot Startup
[ ] Bot started successfully
[ ] No duplicate command errors
[ ] Database validation passed
Issues found: _______________

PHASE 3 - Command Tests  
[ ] !last_session works
[ ] !last_session_compact works
[ ] !stats works
[ ] !leaderboard works
Issues found: _______________

PHASE 4 - Edge Cases
[ ] Empty database handled
[ ] Invalid inputs handled
[ ] Rate limiting works
Issues found: _______________

PHASE 5 - Critical Bugs
[ ] _log_and_send works
[ ] total_maps defined
[ ] session_date defined
[ ] kd displayed to users
Issues found: _______________

OVERALL STATUS: [PASS/FAIL]
Critical blockers: _______________
Non-critical issues: _______________
```

---

## 🚨 CRITICAL ISSUES CHECKLIST

If ANY of these occur, bot needs immediate fixes:

- [ ] Bot crashes on startup
- [ ] `NameError: _log_and_send`
- [ ] `NameError: total_maps`
- [ ] `NameError: session_date`
- [ ] Division by zero errors
- [ ] Discord rate limit errors

---

## ✅ SUCCESS CRITERIA

Bot is **READY FOR PRODUCTION** when:

### Must Have (Blockers):
- ✅ All pytest tests pass
- ✅ Bot starts without errors
- ✅ `!last_session` works completely
- ✅ `!stats` shows data without crashes
- ✅ `!leaderboard` works for all types
- ✅ No crashes on empty database
- ✅ No crashes on invalid input

### Nice to Have (Non-blockers):
- ⚡ K/D ratio shown in player displays
- ⚡ Perfect line length formatting (79 chars)
- ⚡ 100% code coverage in tests
- ⚡ All type hints properly defined

---

## 🔧 QUICK DEBUG COMMANDS

If something breaks during testing:

```bash
# Check bot logs
tail -f bot.log

# Check database schema
sqlite3 etlegacy_production.db "PRAGMA table_info(player_comprehensive_stats);"

# Count sessions in database
sqlite3 etlegacy_production.db "SELECT COUNT(*) FROM sessions;"

# Check stats files
ls -lh local_stats/ | tail -10

# Validate a stats file
python -c "from bot.community_stats_parser import C0RNP0RN3StatsParser; \
p = C0RNP0RN3StatsParser(); \
print(p.parse_stats_file('local_stats/2025-10-23-221845-te_escape2-round-1.txt'))"

# Check for remaining bare excepts
grep -n "except:" bot/ultimate_bot.py

# Check for duplicate function definitions
grep -n "def last_session" bot/ultimate_bot.py
```

---

## 📞 AGENT INSTRUCTIONS

### Step 1: Run Phase 1 Tests
Execute all commands in **PHASE 1** and provide:
- Full command output (copy/paste)
- Pass/Fail status for each test
- Any error messages or warnings

### Step 2: Report Results
Format your response like this:

```
PHASE 1 RESULTS:

1. pytest tests/test_alias_fallback.py -v
[PASTE FULL OUTPUT HERE]
Status: PASS/FAIL

2. python -m py_compile bot/ultimate_bot.py  
[PASTE FULL OUTPUT HERE]
Status: PASS/FAIL

3. python -m ruff check bot/ultimate_bot.py
[PASTE FULL OUTPUT HERE]
Status: PASS/FAIL

SUMMARY:
- Tests passed: X/3
- Critical issues: [LIST ANY]
- Non-critical issues: [LIST ANY]
- Ready for Phase 2 manual testing: YES/NO
```

### Step 3: Wait for User Feedback
After Phase 1, wait for user to complete manual testing (Phase 2-5) in Discord and report back any issues found.

### Step 4: Address Issues
Based on user's manual testing report, fix any critical issues found in Phase 2-5.

---

## 🎯 EXPECTED TIMELINE

- **Phase 1 (Agent):** 5-10 minutes - Automated tests
- **Phase 2-5 (User):** 15-30 minutes - Manual Discord testing
- **Phase 6 (Agent):** If issues found, 30-60 minutes to fix

---

## 📋 KNOWN ISSUES FROM ORIGINAL RUFF REPORT

These were flagged in the original linting and may still need fixes:

1. **F811:** Redefinition of `last_session` → ✅ FIXED (renamed to `last_session_compact`)
2. **F821:** Undefined `_log_and_send` → ⚠️ VERIFY IN TESTING
3. **F821:** Undefined `total_maps` → ⚠️ VERIFY IN TESTING
4. **F821:** Undefined `session_date` → ⚠️ VERIFY IN TESTING
5. **F841:** Unused `kd` variable → ⚠️ COSMETIC (calculated but not displayed)
6. **E722:** Bare except clauses → ✅ FIXED (replaced with `except Exception:`)

---

## 🚀 DEPLOYMENT CHECKLIST (After All Tests Pass)

Before deploying to production:

- [ ] All Phase 1-5 tests passed
- [ ] Database backup created
- [ ] `.env` configured correctly
- [ ] Discord bot token valid
- [ ] SSH credentials working (if enabled)
- [ ] Stats files accessible
- [ ] Bot has proper Discord permissions
- [ ] Tested with real game data
- [ ] Error logging configured
- [ ] Documented any known limitations

---

**END OF TESTING CHECKLIST**

*Generated for ET:Legacy Discord Bot - October 30, 2025*
