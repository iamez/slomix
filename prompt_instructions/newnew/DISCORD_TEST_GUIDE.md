# 🎮 DISCORD COMMAND TEST GUIDE
**Purpose**: Quick reference for testing bot in Discord  
**Bot Status**: ✅ Running and connected  
**Bot Name**: slomix#3520

---

## ✅ PRE-TEST VERIFICATION

**Bot is currently**:
- ✅ Running (started at 21:30:07 UTC)
- ✅ Connected to Discord Gateway
- ✅ Schema validated (53 columns)
- ✅ Database connected (12,414 records across 1,456 sessions)
- ✅ 11 commands registered
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
