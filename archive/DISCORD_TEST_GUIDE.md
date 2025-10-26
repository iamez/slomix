# 🎮 DISCORD COMMAND TEST GUIDE
**Purpose**: Quick reference for testing bot in Discord  
**Bot Status**: ✅ Running and connected  
**Bot Name**: slomix#3520

---

## ✅ PRE-TEST VERIFICATION

**Bot is currently**:
- ✅ Running (restarted Oct 5, 16:40:55 UTC)
- ✅ Connected to Discord Gateway
- ✅ Schema validated (53 columns)
- ✅ Database connected (12,414 records across 1,456 sessions)
- ✅ **14 commands registered** (Oct 5 - Added !sessions, !list_players, fixed !session)
- ✅ Import script FIXED (Oct 4, 22:15) - Missing rounds recovered

---

## 🧪 COMMANDS TO TEST

### Test #1: Basic Connectivity
```
!ping
```

**Expected Response**:
- Bot responds with "Pong!" or latency info
- Response time < 1 second

**What this tests**:
- Bot is responding to commands
- Discord connection is stable

---

### Test #2: Last Session Command
```
!last_session
```

**Expected Response**:
- Multiple embeds showing:
  - Session summary (map, date, teams)
  - Team statistics (Axis vs Allies)
  - Top players
  - MVP awards
  - Session image (if image generation works)

**What this tests**:
- Database query works
- Unified schema queries (all 53 columns)
- Embed generation
- Multi-message sending
- Rate limiting (sends 8 messages)

---

### Test #3: Player Stats
```
!stats vid
```
*Replace "vid" with any player name from database*

**Expected Response**:
- Player profile embed with:
  - Total kills, deaths, KD ratio
  - Damage given/received, DPM
  - Time played
  - XP and efficiency
  - Objective stats (assists, revives, etc.)

**What this tests**:
- Player lookup
- NULL handling (safe_divide, safe_dpm)
- Objective stats from unified schema
- Calculation accuracy

---

### Test #4: Leaderboard
```
!leaderboard kills
```

**Options**: kills, kd, dpm, acc, hs

**Expected Response**:
- Embed showing top 10 players
- Stats formatted correctly
- Rankings in order

**What this tests**:
- Aggregation queries
- Sorting
- Multiple player records
- Formatting

---

### Test #5: Help Command
```
!help
```

**Expected Response**:
- Embed listing all available commands
- Command descriptions

**What this tests**:
- Command registration
- Help system

---

### Test #6: Sessions List (NEW - Oct 5)
```
!sessions october
```

**Expected Response**:
- Title: "📅 Gaming Sessions - October 2025"
- List of sessions with dates
- Each shows: maps, rounds, players, duration
- Total session count footer

**What this tests**:
- New !sessions command (Session 7)
- Month filtering
- Date aggregation
- Session counting (maps = COUNT/2)

**Additional Tests**:
```
!sessions              # All sessions
!sessions 10           # Month by number
!sessions 2025-10      # Year-month format
!ls october            # Test alias
```

---

### Test #7: List Players (NEW - Oct 5)
```
!list_players
```

**Expected Response**:
- Title: "👥 All Players (X)"
- Player list with link status icons (🔗 or ❌)
- Shows: Name, GUID, Discord mention (if linked), K/D, sessions, last seen
- Total player count

**What this tests**:
- New !list_players command (Session 7)
- player_links JOIN query
- Discord link status display
- "Xd ago" date formatting

**Additional Tests**:
```
!list_players linked    # Filter linked only
!list_players unlinked  # Filter unlinked only
!list_players active    # Active last 30 days
!lp                     # Test alias
```

**What to verify**:
- 🔗 icon for linked players
- ❌ icon for unlinked players
- Discord mentions work for linked
- K/D ratios calculated correctly
- Last seen shows relative time (e.g., "3d ago")

---

### Test #8: Session by Date (UPDATED - Oct 5)
```
!session 2025-08-31
```

**Expected Response**:
- Title: "📊 Session Summary: 2025-08-31"
- Shows: Total maps, total rounds, all unique maps
- Top 5 players with AGGREGATED stats (not single round)
- Footer: "Use !last_session for most recent..."

**What this tests**:
- Fixed !session command (Session 7)
- Full day aggregation (not single round)
- Weighted DPM calculation: `SUM(damage)*60/SUM(time_seconds)`
- Date parsing (hyphenated format)

**Additional Tests**:
```
!session 2025 10 2      # Spaced date format
!session                # Most recent (no args)
```

**CRITICAL - What Changed**:
- **Before**: Showed "Session #1456: te_escape2 Round 2" (single round)
- **After**: Shows full day with ALL maps and aggregated player stats
- **Verify**: Multiple maps listed, stats are totals not single-round

---

## 🔍 WHAT TO CHECK

### For Each Command:

✅ **Response Time**: Should be < 2 seconds  
✅ **No Errors**: No "Error occurred" messages  
✅ **Data Accuracy**: Numbers should make sense  
✅ **Formatting**: Embeds should look good  
✅ **No Crashes**: Bot should keep running  

### Specific Checks:

#### !last_session
- [ ] Shows correct latest session
- [ ] Team stats add up correctly
- [ ] Top players displayed
- [ ] No NULL errors (uses safe_dpm, safe_divide)
- [ ] Sends all messages without rate limit errors

#### !stats <player>
- [ ] Finds player by name
- [ ] Shows kills, deaths, damage
- [ ] DPM calculated correctly (damage * 60 / time_seconds)
- [ ] KD ratio calculated (handles deaths=0)
- [ ] Objective stats shown (assists, dynamites, revives)
- [ ] No crashes on NULL values

#### !leaderboard
- [ ] Shows correct number of players
- [ ] Sorted correctly
- [ ] Stats accurate
- [ ] Formatting clean

#### !sessions (NEW - Oct 5)
- [ ] Lists sessions by date (most recent first)
- [ ] Month filter works (october, 10, 2025-10)
- [ ] Shows correct map count (COUNT/2)
- [ ] Duration calculated correctly
- [ ] Aliases work (!ls, !list_sessions)

#### !list_players (NEW - Oct 5)
- [ ] Shows all players with correct icons
- [ ] 🔗 icon for linked players
- [ ] ❌ icon for unlinked players
- [ ] Discord mentions display for linked
- [ ] Filters work (linked, unlinked, active)
- [ ] K/D ratios calculated correctly
- [ ] "Xd ago" format works for last_seen
- [ ] Aliases work (!lp, !players)

#### !session <date> (UPDATED - Oct 5)
- [ ] Shows FULL DAY summary (not single round)
- [ ] Multiple maps listed if played more than one
- [ ] Stats are AGGREGATED (totals, not single round)
- [ ] Accepts hyphenated format (2025-10-02)
- [ ] Accepts spaced format (2025 10 2)
- [ ] Top 5 players with medals (🥇🥈🥉)
- [ ] Weighted DPM calculated correctly
- [ ] Footer shows hint for !last_session

---

## 🐛 IF SOMETHING FAILS

### Bot doesn't respond:
**Check**:
```powershell
Get-Content bot/logs/ultimate_bot.log -Tail 50
```
**Look for**: Error messages, exceptions

### Command shows zeros:
**Possible causes**:
- Player not in database
- Schema mismatch (shouldn't happen - validated)
- Wrong session queried

**Check**:
```powershell
python verify_all_stats_FIXED.py
```

### Bot crashes:
**Restart**:
```powershell
python bot/ultimate_bot.py
```
**Check logs** for error before crash

---

## 📊 SAMPLE TEST SESSION

```
User: !ping
Bot: Pong! Latency: 45ms
✅ PASS - Bot responding

User: !last_session
Bot: [Session Summary Embed]
Bot: [Team Stats Embed]
Bot: [Top Players Embed]
...
✅ PASS - Multi-message working

User: !stats vid
Bot: [Player Stats Embed showing kills, deaths, DPM, etc.]
✅ PASS - Player lookup working

User: !leaderboard kills
Bot: [Top 10 Players by Kills]
✅ PASS - Leaderboard working

User: !help
Bot: [Command List]
✅ PASS - Help working
```

---

## 🎯 SUCCESS CRITERIA

### Minimum (Required):
- [x] Bot responds to !ping
- [ ] !last_session works without errors
- [ ] !stats finds player and shows data
- [ ] No crashes during testing
- [ ] Logs show no errors

### Ideal (Bonus):
- [ ] All 11 commands tested
- [ ] Rate limiting works (no Discord errors)
- [ ] Data matches database queries
- [ ] Embeds look professional
- [ ] Response times < 2 seconds

---

## 📝 TEST NOTES TEMPLATE

**Copy this to record your test results**:

```
=== DISCORD COMMAND TEST - October 4, 2025 ===

!ping
Result: [ PASS / FAIL ]
Notes: 

!last_session
Result: [ PASS / FAIL ]
Notes:

!stats <player>
Result: [ PASS / FAIL ]
Notes:

!leaderboard kills
Result: [ PASS / FAIL ]
Notes:

Issues Found:
1. 
2. 

Overall Status: [ SUCCESS / NEEDS FIXES ]
```

---

## 🚀 AFTER TESTING

### If All Tests Pass:
✅ Bot is fully operational  
✅ Document results in docs/BOT_DEPLOYMENT_TEST_RESULTS.md  
✅ Consider bot production-ready  
✅ Monitor for 24 hours  

### If Tests Fail:
❌ Check bot logs  
❌ Review error messages  
❌ Re-run validation: `python test_bot_fixes.py`  
❌ Check database: `python verify_all_stats_FIXED.py`  
❌ Report issues for fixing  

---

## 📞 QUICK REFERENCE

**Bot Logs**:
```powershell
Get-Content bot/logs/ultimate_bot.log -Tail 50 -Wait
```

**Restart Bot**:
```powershell
# Stop (Ctrl+C in terminal)
# Start again:
python bot/ultimate_bot.py
```

**Database Check**:
```powershell
python verify_all_stats_FIXED.py
```

**Full Validation**:
```powershell
python test_bot_fixes.py
```

---

**Bot Status**: ✅ RUNNING  
**Ready to Test**: ✅ YES  
**Expected Result**: ✅ ALL TESTS PASS  

**Go ahead and test in Discord! 🎮**
