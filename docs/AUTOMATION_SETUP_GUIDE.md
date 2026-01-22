# 🤖 Automation Setup Guide

> **Complete guide to enabling fully autonomous Discord bot operation**

Last Updated: October 11, 2025

---

## 📋 Overview

The ET:Legacy Stats Bot has **complete automation features built-in** that enable fully autonomous operation:

- 🎙️ **Voice Channel Detection** - Automatically starts monitoring when 6+ players join voice
- 📊 **Real-Time Stats** - Posts round summaries and session analytics automatically
- 🏁 **Auto Session Summaries** - Posts comprehensive session breakdown when everyone leaves
- 🔄 **SSH Monitoring** - Automatically syncs and processes new stats files from server

**Status:** ✅ All features are fully implemented and ready to use  
**Requirements:** SSH access to your ET:Legacy game server

---

## 🚀 Quick Enable (TL;DR)

```bash
# 1. Edit your .env file
AUTOMATION_ENABLED=true
SSH_ENABLED=true
GAMING_VOICE_CHANNELS=1234567890,9876543210  # Your voice channel IDs

# 2. Restart the bot
python bot/ultimate_bot.py
```sql

That's it! Bot will now automatically monitor voice channels and post stats.

---

## 📖 Detailed Setup

### Step 1: Prerequisites

Before enabling automation, ensure you have:

- ✅ Discord bot configured and running
- ✅ SSH access to your ET:Legacy server
- ✅ SSH private key configured (see `.env.template`)
- ✅ Voice channel IDs from your Discord server
- ✅ Database initialized (`bot/etlegacy_production.db`)

### Step 2: Get Voice Channel IDs

You need the Discord channel IDs for voice channels you want to monitor:

**Method 1: Enable Developer Mode**

1. Discord → User Settings → Advanced → Enable "Developer Mode"
2. Right-click your gaming voice channel → "Copy Channel ID"
3. Save this ID for the next step

**Method 2: Use Bot Command**

```text

!channel_info

```sql

The bot will list all voice channels with their IDs.

**Example Channel IDs:**

- Gaming Voice 1: `1420158097741058130`
- Gaming Voice 2: `1420158097741058131`

### Step 3: Configure .env File

Edit your `.env` file and add/update these settings:

```bash
# ========== AUTOMATION CONFIGURATION ==========
# Enable fully autonomous operation
AUTOMATION_ENABLED=true

# Enable SSH file monitoring (required for automation)
SSH_ENABLED=true

# Voice channels to monitor (comma-separated, no spaces)
GAMING_VOICE_CHANNELS=1420158097741058130,1420158097741058131

# ========== SSH CONFIGURATION (REQUIRED) ==========
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot

# ========== SERVER PATHS ==========
ETLEGACY_STATS_DIR=/home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats
```text

**Important Notes:**

- `GAMING_VOICE_CHANNELS` must be comma-separated with NO SPACES
- SSH credentials must be valid and tested
- Stats directory path must match your server installation

### Step 4: Test SSH Connection

Before enabling automation, verify SSH access works:

```bash
# Test SSH connection manually
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101

# Once connected, verify stats directory exists
ls /home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats
```text

You should see `.stats` files in the directory.

### Step 5: Start the Bot

```bash
# Start with logging to see automation messages
python bot/ultimate_bot.py
```text

**Expected Startup Messages:**

```text

✅ Automation system ENABLED
🎙️ Voice monitoring enabled for channels: [1420158097741058130, 1420158097741058131]
🔄 Background task: endstats_monitor started

```sql

If you see `⚠️ Automation system DISABLED`, check your `.env` file settings.

### Step 6: Test Voice Detection

**Test Scenario:**

1. Have 6+ players join one of the configured voice channels
2. Bot should automatically detect and post: "🎮 Gaming session detected! Monitoring started."
3. Play a match and complete a round
4. Bot should auto-post round summary within 30 seconds
5. When everyone leaves voice, bot posts comprehensive session summary

**Manual Override Commands:**

- `!session_start` - Manually start monitoring
- `!session_end` - Manually stop monitoring
- `!sync_stats` - Manually trigger stats file sync

---

## 🎯 How It Works

### Voice Channel Detection

```sql

1. Bot monitors configured voice channels every 30 seconds
2. When 6+ users join a gaming voice channel:
   → Sets session_active = True
   → Starts SSH monitoring
   → Posts "Gaming session detected" message
3. When all users leave:
   → Processes final stats
   → Posts comprehensive session summary
   → Sets session_active = False

```text

### SSH File Monitoring

```text

1. Background task checks server every 60 seconds
2. Downloads new .stats files via SSH/SCP
3. Verifies file integrity (not empty, correct format)
4. Parses stats and imports to database
5. Posts round summaries and session updates
6. Marks files as processed to avoid duplicates

```yaml

### Auto-Posting Behavior

**Round Summary (after each round):**

- Top 5 players by kills
- Team scores and winner
- Average DPM and accuracy
- Posted within 30 seconds of round end

**Session Summary (when everyone leaves):**

- Full session analytics with multiple embeds
- Team breakdown and MVP calculations
- Weapon mastery and special awards
- Posted automatically when session ends

---

## 🛠️ Troubleshooting

### Automation Not Starting

**Symptom:** Bot says "Automation system DISABLED"

**Solutions:**

```bash
# 1. Check .env file has correct values (no quotes)
AUTOMATION_ENABLED=true  # ✅ Correct
AUTOMATION_ENABLED="true"  # ❌ Wrong (remove quotes)

# 2. Restart the bot after editing .env
pkill -f ultimate_bot.py
python bot/ultimate_bot.py
```sql

### Voice Detection Not Working

**Symptom:** Bot doesn't react when 6+ join voice

**Solutions:**

1. **Check Channel IDs:** Verify `GAMING_VOICE_CHANNELS` has correct IDs

   ```bash
   # In Discord, enable Developer Mode and copy channel ID
   # Should be a long number like: 1420158097741058130
   ```text

2. **Check Bot Permissions:** Bot needs "View Channels" permission for voice channels

3. **Check Logs:** Look for voice detection messages

   ```bash
   grep "voice" logs/bot.log
   ```text

### SSH Connection Fails

**Symptom:** Bot says "SSH connection failed" or "Cannot download stats"

**Solutions:**

1. **Test SSH Manually:**

   ```bash
   ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101
   ```text

2. **Check SSH Key Permissions:**

   ```bash
   chmod 600 ~/.ssh/etlegacy_bot
   ```text

3. **Verify SSH Key Path in .env:**

   ```bash
   SSH_KEY_PATH=~/.ssh/etlegacy_bot  # Use absolute path if this fails
   SSH_KEY_PATH=/home/youruser/.ssh/etlegacy_bot
   ```text

4. **Check Stats Directory Path:**

   ```bash
   # Connect via SSH and verify path exists
   ls /home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats
   ```text

### Stats Not Posting

**Symptom:** Bot is monitoring but not posting stats

**Solutions:**

1. **Check Database:** Verify files are being processed

   ```bash
   python -c "import sqlite3; conn=sqlite3.connect('bot/etlegacy_production.db'); print(conn.execute('SELECT COUNT(*) FROM processed_files').fetchone())"
   ```text

2. **Check Stats Channel:** Verify `STATS_CHANNEL_ID` in .env is correct

3. **Check Bot Permissions:** Bot needs "Send Messages" and "Embed Links" permissions

4. **Check Logs for Errors:**

   ```bash
   tail -f logs/bot.log
   ```text

### Files Processing Multiple Times

**Symptom:** Same stats posted multiple times

**Solutions:**

1. **Clear Processed Files (if testing):**

   ```bash
   python -c "import sqlite3; conn=sqlite3.connect('bot/etlegacy_production.db'); conn.execute('DELETE FROM processed_files'); conn.commit()"
   ```text

2. **Check File Timestamps:** Bot tracks files by filename and timestamp

   ```sql
   SELECT filename, processed_at FROM processed_files ORDER BY processed_at DESC LIMIT 10;
   ```python

---

## 🔧 Advanced Configuration

### Adjust Monitoring Intervals

Edit `bot/ultimate_bot.py` to change monitoring frequency:

```python
# Line ~4622: Voice channel check interval
@tasks.loop(seconds=30)  # Check every 30 seconds (change as needed)
async def check_voice_channels(self):

# Line ~5483: SSH monitoring interval  
@tasks.loop(seconds=60)  # Check server every 60 seconds
async def endstats_monitor(self):
```text

### Custom Voice Thresholds

Change minimum players required for auto-start:

```python
# Line ~4644: Minimum players for session start
if len(members) >= 6:  # Change '6' to your preferred threshold
```text

### Disable Specific Auto-Posts

**Disable Round Summaries:**

```python
# Comment out post_round_summary() call in endstats_monitor()
# Line ~5567
# await self.post_round_summary(data)  # Disabled
```text

**Disable Session Summaries:**

```python
# Comment out post_map_summary() call
# await self.post_map_summary(round_id)  # Disabled
```yaml

---

## 📊 Monitoring Automation

### Check Automation Status

**Discord Commands:**

```text

!ping          # Shows automation enabled status
!status        # Shows current session state
!last_round  # Verify latest session was auto-imported

```text

**Check Logs:**

```bash
# Watch real-time logs
tail -f logs/bot.log

# Search for automation events
grep "Automation" logs/bot.log
grep "Gaming session detected" logs/bot.log
grep "SSH" logs/bot.log
```text

### Database Queries

**Check Recent Sessions:**

```sql
SELECT 
  round_date,
  map_name,
  COUNT(*) as player_count
FROM rounds 
WHERE round_date >= date('now', '-1 day')
GROUP BY round_date, map_name
ORDER BY round_date DESC;
```text

**Check Processed Files:**

```sql
SELECT 
  filename,
  processed_at,
  round_count
FROM processed_files 
ORDER BY processed_at DESC 
LIMIT 10;
```yaml

---

## 🎮 Usage Examples

### Example 1: Nightly Gaming Session

**Scenario:** Regular gaming night with 8 players

```sql

7:00 PM - 8 players join "ET Legacy Gaming" voice channel
7:00 PM - 🎮 Bot: "Gaming session detected! Monitoring started."
7:15 PM - Round 1 ends
7:15 PM - 📊 Bot posts round summary (top players, scores, stats)
7:30 PM - Round 2 ends  
7:30 PM - 📊 Bot posts map summary (full session, MVP, awards)
8:00 PM - New map starts (bot continues monitoring)
10:00 PM - Everyone leaves voice
10:00 PM - 🏁 Bot posts comprehensive session summary

```text

**Result:** Zero manual commands needed, complete stats coverage!

### Example 2: Manual Override

**Scenario:** Want to track stats but <6 players online

```text

!session_start  # Manually start monitoring
!sync_stats     # Manually sync stats files after each map
!session_end    # Post final summary when done

```text

### Example 3: Testing Automation

**Scenario:** First time setup, want to verify it works

```sql

# Step 1: Join voice with 6 people

# Wait for: "🎮 Gaming session detected!"

# Step 2: Play one round

# Wait for: Round summary post

# Step 3: Check logs

tail -f logs/bot.log | grep "session\|SSH\|voice"

# Step 4: Leave voice

# Wait for: Session summary post

# Success! Automation is working ✅

```

---

## 🔒 Security Notes

### SSH Key Security

- **Never commit SSH keys** to git repositories
- Store keys with restrictive permissions: `chmod 600 ~/.ssh/etlegacy_bot`
- Use read-only SSH access when possible
- Consider using SSH agent for key management

### Environment Variables

- Keep `.env` file out of version control (add to `.gitignore`)
- Never share `.env` file with Discord tokens or SSH credentials
- Use `.env.example` or `.env.template` for documentation

### Bot Permissions

**Minimum Required Permissions:**

- Read Messages/View Channels
- Send Messages
- Embed Links
- Read Message History
- Add Reactions (for !link_me feature)

**Optional Permissions:**

- Manage Messages (for cleaning up bot messages)
- Attach Files (for future features)

---

## 📞 Support

### Still Having Issues?

1. **Check AUTOMATION_COMPLETE.md:** Detailed development documentation in `archive/`
2. **Review Bot Code:** See `bot/ultimate_bot.py` lines 4428-4733 for automation logic
3. **Database Issues:** See `BUGFIXES_OCT11.md` for recent fixes
4. **General Setup:** See main `README.md`

### Testing Checklist

Before reporting issues, verify:

- [ ] `AUTOMATION_ENABLED=true` in .env (no quotes)
- [ ] `SSH_ENABLED=true` in .env
- [ ] `GAMING_VOICE_CHANNELS` has valid channel IDs
- [ ] SSH connection works manually
- [ ] Bot has correct Discord permissions
- [ ] Database exists at `bot/etlegacy_production.db`
- [ ] Stats directory path is correct in .env
- [ ] Bot logs show "Automation system ENABLED" on startup

---

## 🎉 Success Criteria

You'll know automation is working correctly when:

✅ Bot startup shows "Automation system ENABLED"  
✅ Bot detects when 6+ join voice channel  
✅ Round summaries post automatically after each round  
✅ Session summaries post when everyone leaves voice  
✅ No manual commands needed for normal gameplay  
✅ Stats are accurate and complete in database  

**Congratulations! You now have a fully autonomous ET:Legacy stats bot! 🎮📊**

---

**Last Updated:** October 11, 2025  
**Bot Version:** Production (5000+ lines)  
**Database Schema:** UNIFIED 53 columns, 7 tables  
**Total Sessions Tracked:** 1,862 sessions, 25 unique players
