# 🎮 ET:Legacy Bot - Command Cheat Sheet

**Quick reference for testing and operations**  
**Date:** October 12, 2025

---

## 📝 Testing Commands

### Test 1: Basic Bot Startup

```powershell
# Check .env settings
cat .env | Select-String "AUTOMATION|SSH|GAMING"

# Start bot
cd g:\VisualStudio\Python\stats
python bot/ultimate_bot.py
```

**Discord commands to test:**
```
!ping
!help
!stats vid
```

---

### Test 2: Enable Automation

```powershell
# Backup .env
Copy-Item .env .env.backup

# Edit .env - Add these lines:
# AUTOMATION_ENABLED=true
# SSH_ENABLED=false
# GAMING_VOICE_CHANNELS=

# Restart bot
python bot/ultimate_bot.py
```

**Expected log:**
```
✅ Automation system ENABLED
```

---

### Test 3: Voice Channel Config

**Your voice channel IDs:**
- Channel 1: `1029097483697143938`
- Channel 2: `947583652957659166`

```bash
# Add to .env:
GAMING_VOICE_CHANNELS=1029097483697143938,947583652957659166
```

```powershell
# Restart bot
python bot/ultimate_bot.py
```

**Expected log:**
```
🎙️ Voice monitoring enabled for channels: [1029097483697143938, 947583652957659166]
```

---

### Test 4: SSH Configuration

```powershell
# Test SSH manually first
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101
```

```bash
# Add to .env:
SSH_ENABLED=true
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot
ETLEGACY_STATS_DIR=/home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats
```

```powershell
# Restart bot
python bot/ultimate_bot.py
```

**Discord command to test:**
```
!sync_stats
```

---

### Test 5: Full Automation

```
# Manual session control
!session_start
!sync_stats
!session_end

# Check recent imports
!last_session
!stats <playername>
```

---

## 🛠️ Database Commands

### Add Performance Indexes

```powershell
# Open database
cd g:\VisualStudio\Python\stats
sqlite3 bot/etlegacy_production.db
```

```sql
-- Copy-paste all 9 indexes:
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_players_guid ON player_comprehensive_stats(guid);
CREATE INDEX IF NOT EXISTS idx_players_session ON player_comprehensive_stats(session_id);
CREATE INDEX IF NOT EXISTS idx_players_kd ON player_comprehensive_stats(kd_ratio DESC);
CREATE INDEX IF NOT EXISTS idx_players_dpm ON player_comprehensive_stats(dpm DESC);
CREATE INDEX IF NOT EXISTS idx_aliases_guid ON player_aliases(guid);
CREATE INDEX IF NOT EXISTS idx_aliases_alias ON player_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_weapons_session ON weapon_comprehensive_stats(session_id);
CREATE INDEX IF NOT EXISTS idx_weapons_player ON weapon_comprehensive_stats(player_name);

-- Verify indexes created
.indexes

-- Exit
.quit
```

---

## 🔍 Diagnostic Commands

### Check Bot Status

```powershell
# Check if bot is running
Get-Process python

# View recent logs (if logging to file)
Get-Content bot.log -Tail 50
```

### Check Database

```powershell
cd g:\VisualStudio\Python\stats
sqlite3 bot/etlegacy_production.db
```

```sql
-- Check session count
SELECT COUNT(*) FROM sessions;

-- Check player count
SELECT COUNT(DISTINCT guid) FROM player_comprehensive_stats;

-- Check recent sessions
SELECT session_id, map_name, session_date 
FROM sessions 
ORDER BY session_date DESC 
LIMIT 5;

-- Exit
.quit
```

### Check .env Configuration

```powershell
# View all settings
cat .env

# Check specific settings
cat .env | Select-String "AUTOMATION"
cat .env | Select-String "SSH"
cat .env | Select-String "CHANNEL"
```

---

## 🎯 Discord Bot Commands Reference

### Admin Commands

```
!sync_stats              # Download and process stats files
!session_start           # Manually start session tracking
!session_end             # Manually end session and post summary
!import_legacy <path>    # Import old stats files
!rebuild_aliases         # Rebuild player alias database
```

### Player Commands

```
!stats <player>          # Show player statistics
!link <player>           # Link Discord account to player
!leaderboard [category]  # Show top players
!compare <p1> <p2>       # Compare two players
!last_session            # Show most recent session details
!player_sessions <p>     # Show player's recent sessions
```

### Info Commands

```
!ping                    # Check bot latency
!help                    # Show command list
!stats_info              # Show database statistics
!maps                    # List all maps with stats
!weapons                 # Show weapon statistics
```

### Future Commands (Not Yet Implemented)

```
!export <player>         # Export player stats to CSV
!trend <player> [days]   # Show performance trends
!activity heatmap        # Show activity patterns
!achievements            # View your achievements
```

---

## 🐛 Troubleshooting Commands

### Bot Won't Start

```powershell
# Check Python version
python --version

# Reinstall dependencies
pip install -r requirements.txt

# Check for syntax errors
python -m py_compile bot/ultimate_bot.py
```

### Database Issues

```powershell
# Backup database
Copy-Item bot/etlegacy_production.db bot/etlegacy_production.db.backup

# Check database integrity
sqlite3 bot/etlegacy_production.db "PRAGMA integrity_check;"
```

### SSH Connection Issues

```powershell
# Test SSH manually
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101

# Check key permissions (on Linux/WSL)
chmod 600 ~/.ssh/etlegacy_bot

# Test with verbose output
ssh -vvv -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101
```

### Voice Detection Not Working

```
# In Discord, check:
1. Bot has "View Channel" permission for voice channels
2. Channel IDs are correct (right-click → Copy Channel ID)
3. AUTOMATION_ENABLED=true in .env
4. Bot logs show voice monitoring enabled
```

---

## 📊 Performance Testing

### Before Adding Indexes

```sql
-- Time a query (note the time)
.timer on
SELECT * FROM player_comprehensive_stats WHERE guid = 'someGUID';
```

### After Adding Indexes

```sql
-- Same query should be 10x faster
.timer on
SELECT * FROM player_comprehensive_stats WHERE guid = 'someGUID';
```

---

## 🔄 Quick Restart Procedure

```powershell
# Stop bot (Ctrl+C in terminal)

# Edit .env if needed
notepad .env

# Restart bot
cd g:\VisualStudio\Python\stats
python bot/ultimate_bot.py
```

---

## 📝 .env Template (Your Config)

```bash
# Discord
DISCORD_TOKEN=your_token_here
STATS_CHANNEL_ID=your_channel_id

# Database
DB_PATH=bot/etlegacy_production.db

# Automation (keep disabled for now)
AUTOMATION_ENABLED=false
SSH_ENABLED=false
GAMING_VOICE_CHANNELS=1029097483697143938,947583652957659166

# SSH Config (for later)
# SSH_HOST=puran.hehe.si
# SSH_PORT=48101
# SSH_USER=et
# SSH_KEY_PATH=~/.ssh/etlegacy_bot
# ETLEGACY_STATS_DIR=/home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats

# Paths
LOCAL_STATS_DIR=local_stats
PROCESSED_FILES_LOG=bot/processed_files.txt
```

---

## 🎯 Today's Testing Checklist

- [ ] Test 1: Basic bot startup - Bot connects and commands work
- [ ] Test 2: Enable automation - Logs show "ENABLED"
- [ ] Test 3: Voice config - Keep disabled, IDs ready for later
- [ ] Test 4: SSH config - Test !sync_stats command
- [ ] Test 5: Manual session - !session_start → !sync_stats → !session_end

**Time Required:** 2-3 hours  
**Current Status:** Ready to begin Test 1

---

*Cheat Sheet Created: October 12, 2025*  
*Voice Channels: Ready (disabled for now)*  
*SSH: Configured and ready to test*
