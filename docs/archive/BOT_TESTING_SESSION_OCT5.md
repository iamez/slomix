# 🧪 BOT TESTING GUIDE - October 5, 2025

## ✅ BOT STATUS: RUNNING!

**Bot Name**: slomix#3520  
**Status**: Connected to Discord Gateway  
**Commands**: 12 available  
**Database**: Connected (12,414 records)  
**Schema**: Validated (53 columns - UNIFIED)  
**Automation**: DISABLED (safe for testing)

---

## 📋 TEST COMMANDS (In This Order)

### **Test 1: Basic Connectivity** ⚡
```
!ping
```
**Expected**: Bot responds with "Pong!" or latency
**Tests**: Bot is responding to commands

---

### **Test 2: Help Command** 📖
```
!help
```
**Expected**: List of all available commands
**Tests**: Command registration working

---

### **Test 3: Player Stats** 📊
```
!stats vid
```
**Expected**: 
- Player profile embed
- Kills, deaths, K/D ratio
- DPM, accuracy, headshots
- Objective stats (revives, assists, dynamites)
- GUID in footer

**Tests**: 
- Database queries work
- Unified schema (53 columns)
- NULL handling (safe_divide methods)
- Calculation accuracy

---

### **Test 4: Self Stats (If Linked)** 👤
```
!stats
```
**Expected**:
- If linked: Your stats
- If not linked: Helpful message about linking

**Tests**: Player linking system

---

### **Test 5: Last Session** 🎮
```
!last_session
```
**Expected**: Multiple embeds showing:
1. Session summary (map, date, teams)
2. Top 5 players with 2-line stats
3. Team comparison + MVPs
4. DPM leaderboard
5. Weapon mastery (top 6 players, top 2 weapons each)

**⚠️ IMPORTANT**: This sends MULTIPLE messages with delays between them (rate limit protection). Give it ~5-10 seconds to send all embeds.

**Tests**:
- Complex database queries
- Multi-message sending
- Rate limiting (sends with delays)
- Embed generation
- Objective stats display

---

### **Test 6: Leaderboard** 🏆
```
!leaderboard kills
```
**Options**: kills, kd, dpm, acc, hs

**Expected**: 
- Embed with top 10 players
- Stats formatted correctly
- Rankings in order

**Tests**: 
- Aggregation queries
- Sorting
- Multiple player records

---

### **Test 7: Linking System** 🔗
```
!link
```
**Expected** (if not linked):
- Shows top 3 players matching your activity
- Reaction buttons (1️⃣2️⃣3️⃣)
- Stats preview for each option

**Tests**: 
- Interactive linking
- Reaction buttons
- Alias display
- Self-linking flow

---

### **Test 8: Name Search Stats** 🔍
```
!stats olz
```
**Expected**:
- Finds player by name
- Shows complete stats
- Displays aliases in footer

**Tests**:
- Name search functionality
- Alias matching
- Player not found handling

---

### **Test 9: Admin Linking (If Admin)** 🔐
```
!link @user D8423F90
```
**Expected** (if you have Manage Server permission):
- Confirmation embed
- Shows player stats
- Reaction buttons for confirmation

**Tests**: Permission checking, admin features

---

## 🎯 WHAT TO WATCH FOR

### ✅ **Good Signs**:
- Bot responds quickly (< 2 seconds)
- Embeds look clean and formatted
- No error messages
- Stats show reasonable numbers
- Objective stats (revives, assists) are NOT zero
- Multiple messages sent with delays (rate limit protection)

### ❌ **Bad Signs**:
- Error messages in Discord
- Stats showing all zeros
- Bot doesn't respond
- Embeds broken/missing fields
- Command crashes bot

---

## 📊 EXPECTED STATS (From Database)

**Top Player**: vid
- 15,383 kills
- 1,462 games played
- K/D ratio: ~1.46
- Should have objective stats (not zeros)

**Database Stats**:
- 12,414 player records
- 1,456 sessions
- 53 columns per record

---

## 🐛 IF SOMETHING FAILS

### **Bot Doesn't Respond**:
```powershell
# Check bot logs
Get-Content bot/logs/ultimate_bot.log -Tail 50
```

### **Stats Show Zeros**:
```powershell
# Verify schema
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(player_comprehensive_stats)'); print(f'Columns: {len(cursor.fetchall())}'); # Should be 53"
```

### **Command Crashes**:
- Check terminal output for Python errors
- Check Discord for error messages
- Note which command failed

---

## 📝 TESTING NOTES

**Remember**:
- ⏱️ **!last_session sends MULTIPLE messages** - wait 5-10 seconds
- 🔄 Bot has rate limit protection (delays between messages)
- 🤖 Automation is OFF (no voice detection running)
- 📊 All tests use existing database data
- ✅ Bot should handle NULL values gracefully

---

## ✅ SUCCESS CRITERIA

**After testing all commands**:
- [ ] Bot responds to all commands
- [ ] No error messages
- [ ] Stats look accurate
- [ ] Embeds formatted correctly
- [ ] Objective stats show (not zeros)
- [ ] Multiple messages sent properly
- [ ] No bot crashes

---

## 🎉 NEXT STEPS AFTER TESTING

**If all tests pass**:
✅ Existing functionality confirmed working
✅ Safe to enable automation (when ready)
✅ Can configure SSH monitoring
✅ Ready for voice detection testing

**If tests fail**:
❌ Document which command failed
❌ Check logs for errors
❌ Report back for debugging

---

**Testing Started**: October 5, 2025, 10:51 AM UTC  
**Bot Status**: Running (Terminal ID: 46dd2061-0a05-485b-a353-3579cb0564e9)  
**Ready for Discord Testing**: ✅ YES!

---

## 🚀 GO TEST IN DISCORD!

The bot is running and waiting for your commands. Test them in order and see how it performs!

Remember: **!last_session will send multiple embeds with delays - be patient!** 😊
