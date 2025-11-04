# 🧪 Automation Testing Guide - October 12, 2025

**Purpose:** Step-by-step testing of automation features  
**Time Required:** 2-3 hours  
**Status:** Ready to begin

---

## ✅ Pre-Test Checklist

Before starting, verify:
- [ ] Bot code is at latest version (ultimate_bot.py)
- [ ] Database exists at `bot/etlegacy_production.db`
- [ ] Database has 1,862 sessions imported
- [ ] Discord bot token is valid
- [ ] You have admin access to Discord server

---

## 📋 Test 1: Basic Bot Startup

### Goal
Verify bot starts without errors and connects to Discord.

### Steps

1. **Check current .env settings:**
   ```powershell
   cat .env | Select-String "AUTOMATION|SSH|GAMING"
   ```

2. **Start bot in test mode:**
   ```powershell
   cd g:\VisualStudio\Python\stats
   python bot/ultimate_bot.py
   ```

3. **Check startup logs:**
   Look for:
   ```
   ✅ Bot connected as: [BotName]
   ✅ Database loaded: 1862 sessions
   ⚠️ Automation system DISABLED (expected for now)
   ```

4. **Test basic commands in Discord:**
   ```
   !ping          # Should respond with latency
   !help          # Should show command list
   !stats vid     # Should show player stats
   ```

### Success Criteria
- [ ] Bot connects to Discord without errors
- [ ] Database connection successful
- [ ] Basic commands work
- [ ] No crashes or exceptions

### If It Fails
- Check Discord token is correct in .env
- Verify database path is correct
- Check Python version (should be 3.10+)
- Review logs for specific errors

---

## 📋 Test 2: Enable Automation

### Goal
Enable automation and verify bot recognizes the setting.

### Steps

1. **Backup current .env:**
   ```powershell
   Copy-Item .env .env.backup
   ```

2. **Edit .env file:**
   Add or update these lines:
   ```bash
   AUTOMATION_ENABLED=true
   SSH_ENABLED=false  # Keep disabled for now
   GAMING_VOICE_CHANNELS=  # Leave empty for now
   ```

3. **Restart bot:**
   ```powershell
   # Stop bot (Ctrl+C)
   python bot/ultimate_bot.py
   ```

4. **Check startup logs:**
   Look for:
   ```
   ✅ Automation system ENABLED
   ⚠️ No gaming voice channels configured
   ⚠️ SSH disabled
   ```

### Success Criteria
- [ ] Bot logs show "Automation system ENABLED"
- [ ] No errors during startup
- [ ] Bot still responds to commands
- [ ] No crashes

### If It Fails
- Make sure `AUTOMATION_ENABLED=true` (no quotes!)
- Check for typos in .env
- Verify .env is in root folder (not bot/ subfolder)
- Try with `AUTOMATION_ENABLED=True` (capital T)

---

## 📋 Test 3: Voice Channel Configuration

### Goal
Configure voice channels and test detection logic.

### Steps

1. **Get your voice channel ID:**
   - Enable Developer Mode in Discord (User Settings → Advanced)
   - Right-click your gaming voice channel
   - Click "Copy Channel ID"
   - Example: `1420158097741058130`

2. **Update .env:**
   ```bash
   GAMING_VOICE_CHANNELS=1420158097741058130
   # For multiple channels:
   # GAMING_VOICE_CHANNELS=1420158097741058130,1420158097741058131
   ```

3. **Restart bot:**
   ```powershell
   # Stop bot (Ctrl+C)
   python bot/ultimate_bot.py
   ```

4. **Check startup logs:**
   Look for:
   ```
   ✅ Automation system ENABLED
   🎙️ Voice monitoring enabled for channels: [1420158097741058130]
   🔄 Background task: check_voice_channels started
   ```

5. **Test voice detection:**
   - Join the configured voice channel with 5 friends (6 total)
   - Bot should post: "🎮 Gaming session detected! Monitoring started."
   - Leave voice channel
   - Bot should stop monitoring

### Success Criteria
- [ ] Bot recognizes channel IDs
- [ ] Voice monitoring task starts
- [ ] Bot detects when 6+ join voice (if you can test)
- [ ] No errors or crashes

### If It Fails
- Verify channel ID is correct (no spaces, commas only between IDs)
- Check bot has permission to view voice channel
- Make sure AUTOMATION_ENABLED=true
- Try joining voice yourself to test

---

## 📋 Test 4: SSH Configuration

### Goal
Configure SSH connection for file monitoring.

### Steps

1. **Verify SSH credentials:**
   ```powershell
   # Test SSH connection manually
   ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101
   ```
   
   If successful, you should connect to server.

2. **Update .env:**
   ```bash
   SSH_ENABLED=true
   SSH_HOST=puran.hehe.si
   SSH_PORT=48101
   SSH_USER=et
   SSH_KEY_PATH=~/.ssh/etlegacy_bot
   ETLEGACY_STATS_DIR=/home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats
   ```

3. **Restart bot:**
   ```powershell
   # Stop bot (Ctrl+C)
   python bot/ultimate_bot.py
   ```

4. **Check startup logs:**
   Look for:
   ```
   ✅ Automation system ENABLED
   ✅ SSH enabled
   🔄 Background task: endstats_monitor started
   ```

5. **Test manual sync:**
   In Discord:
   ```
   !sync_stats
   ```
   
   Bot should:
   - Connect to server via SSH
   - Download .stats files
   - Process and import to database
   - Post summary if new rounds found

### Success Criteria
- [ ] SSH connection successful
- [ ] !sync_stats command works
- [ ] Files downloaded to LOCAL_STATS_DIR
- [ ] New sessions imported to database
- [ ] No connection errors

### If It Fails
- Test SSH manually first
- Check SSH_KEY_PATH is absolute path
- Verify key permissions: `chmod 600 ~/.ssh/etlegacy_bot`
- Check ETLEGACY_STATS_DIR path is correct
- Review bot logs for specific SSH errors

---

## 📋 Test 5: Full Automation Test

### Goal
Test complete automation flow from start to finish.

### Prerequisites
- Automation enabled (Test 2 ✅)
- Voice channels configured (Test 3 ✅)
- SSH enabled (Test 4 ✅)
- 6+ people available to join voice (or manual !session_start)

### Steps

**Option A: With Voice Detection (6+ people)**

1. Have 6+ players join configured voice channel
2. Bot should post: "🎮 Gaming session detected! Monitoring started."
3. Play a round on ET:Legacy server
4. Bot should auto-post round summary within 60 seconds
5. Play Round 2
6. Bot should auto-post map summary
7. Everyone leave voice
8. Bot should post final session summary

**Option B: Manual Testing (for now)**

1. Start session manually:
   ```
   !session_start
   ```

2. Place a test .stats file in local_stats/ directory

3. Bot should:
   - Detect new file
   - Import to database
   - Post round summary

4. End session:
   ```
   !session_end
   ```

5. Bot should post session summary

### Success Criteria
- [ ] Session starts (auto or manual)
- [ ] Round summaries post automatically
- [ ] Map summaries post after Round 2
- [ ] Session summaries post when complete
- [ ] All stats imported correctly
- [ ] No crashes during full workflow

### If It Fails
- Check all previous tests passed
- Verify STATS_CHANNEL_ID is set in .env
- Check bot has "Send Messages" permission
- Review logs for errors during import
- Test with manual commands first (!session_start, !sync_stats, !session_end)

---

## 📊 Test Results Template

Copy this to document your results:

```markdown
## Test Results - October 12, 2025

### Test 1: Basic Bot Startup
- Status: [ ] Pass / [ ] Fail
- Notes:

### Test 2: Enable Automation
- Status: [ ] Pass / [ ] Fail
- Notes:

### Test 3: Voice Channel Configuration
- Status: [ ] Pass / [ ] Fail
- Channel ID: 
- Notes:

### Test 4: SSH Configuration
- Status: [ ] Pass / [ ] Fail
- SSH Connection: [ ] Success / [ ] Failed
- !sync_stats: [ ] Works / [ ] Error
- Notes:

### Test 5: Full Automation
- Status: [ ] Pass / [ ] Fail
- Method: [ ] Voice Detection / [ ] Manual
- Round Summaries: [ ] Posted / [ ] Missing
- Round Summary: [ ] Posted / [ ] Missing
- Notes:

### Issues Found
1. 
2. 
3. 

### Next Steps
- [ ] Fix issues
- [ ] Retest failed tests
- [ ] Document final config
- [ ] Update README with results
```

---

## 🐛 Common Issues & Solutions

### Bot Won't Start
```powershell
# Check Python version
python --version  # Should be 3.10+

# Check dependencies
pip install -r requirements.txt

# Check .env location
ls .env  # Should be in root folder
```

### Automation Shows as DISABLED
```bash
# Check .env syntax (no quotes!)
AUTOMATION_ENABLED=true  # ✅ Correct
AUTOMATION_ENABLED="true"  # ❌ Wrong
```

### Voice Detection Not Working
```bash
# Verify channel ID
# Should be long number like: 1420158097741058130
# No spaces, commas only between multiple IDs
GAMING_VOICE_CHANNELS=1234567890,9876543210
```

### SSH Connection Fails
```powershell
# Test manually
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101

# Check key permissions (on server)
chmod 600 ~/.ssh/etlegacy_bot

# Use absolute path in .env
SSH_KEY_PATH=C:/Users/YourName/.ssh/etlegacy_bot  # Windows
```

### !sync_stats Hangs
- File might be too large
- SSH connection slow
- Check bot logs for timeout errors
- Try with smaller test files first

---

## ✅ Success Indicators

You'll know everything is working when:

1. **Bot starts cleanly:**
   ```
   ✅ Automation system ENABLED
   🎙️ Voice monitoring enabled
   🔄 Background tasks started
   ```

2. **Commands work:**
   - !ping responds instantly
   - !stats shows player data
   - !sync_stats downloads files

3. **Automation triggers:**
   - 6+ join voice → bot posts "session started"
   - Round ends → bot posts summary
   - Everyone leaves → bot posts final summary

4. **No errors in logs:**
   - No connection failures
   - No import errors
   - No crashes

---

## 📝 After Testing

1. **Document results** using template above
2. **Update TODO_SPRINT.md** with test outcomes
3. **Fix any issues** found during testing
4. **Commit working .env settings** (without sensitive data!)
5. **Plan next enhancements** from IMPLEMENTATION_ROADMAP.md

---

## 🎯 Next Steps After Testing

Once all tests pass:

**Immediate (Same Day):**
1. Add database indexes (5 minutes)
2. Test query performance improvement

**This Week:**
3. Implement query caching
4. Add achievement notifications
5. Document final config

**Next Week:**
6. Start on visual enhancements (radar charts, heatmaps)

---

*Testing Guide Created: October 12, 2025*  
*Expected Duration: 2-3 hours*  
*Prerequisites: All completed, ready to test*
