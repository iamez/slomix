# SSH Sync System - Usage Guide

## 🎯 Overview

The intelligent SSH sync system automatically downloads new stat files from the game server and imports them into the database.

## 🚀 Quick Start

### Run Sync
```bash
python tools/sync_stats.py
```

This single command will:
1. Connect to `puran.hehe.si:48101` via SSH
2. Check for new stat files (excluding `*_ws.txt` weapon stats)
3. Download only the NEW files
4. Import ONLY those new files into the database
5. Show you a summary of what was added

## 📋 What It Does

### Smart Detection
- **Compares** remote vs local files
- **Downloads** only what's missing
- **Imports** only what was just downloaded
- **Much faster** than bulk import!

### File Handling
- ✅ Downloads: `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`
- ❌ Ignores: `*_ws.txt` (weapon stats files)
- 📂 Saves to: `./local_stats/`

## 📊 Output Example

```
🚀 INTELLIGENT SSH SYNC & IMPORT
======================================================================
Server: puran.hehe.si:48101
======================================================================

🔌 Connecting to SSH server...
✅ Connected!

📂 Scanning remote directory...
   Found 3238 stat files on server
   Latest: 2025-10-02-232818-erdenberg_t2-round-2.txt

📁 Checking local files...
   Found 3218 local files

🆕 Found 20 NEW files!
   • 2025-10-02-211808-etl_adlernest-round-1.txt
   • 2025-10-02-212249-etl_adlernest-round-2.txt
   ... (18 more) ...

📥 Downloading 20 files...
   20/20 downloaded...

✅ Downloaded 20/20 files
🔌 SSH connection closed

📊 IMPORTING 20 NEW FILES...
   ✅ 18/20 imported (failed: 2)

🎉 SYNC & IMPORT COMPLETE!
Downloaded: 20 files
Imported:   18 files
Failed:     2 files

📅 2025-10-02:
   • braundorf_b4: 2 rounds
   • erdenberg_t2: 2 rounds
   • et_brewdog: 2 rounds
   • etl_adlernest: 2 rounds
   ... (more maps) ...
```

## 🔧 Configuration

All settings are in `.env`:

```bash
# SSH Connection
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot

# Paths
REMOTE_STATS_PATH=/home/et/.etlegacy/legacy/gamestats/
```

## 🔑 SSH Key Setup

The sync requires an SSH key for authentication:

1. **Key location**: `~/.ssh/etlegacy_bot` (Windows: `C:\Users\YourName\.ssh\etlegacy_bot`)
2. **No password**: Key should not require a passphrase
3. **Permissions**: Key should be readable only by you

## 🤖 Automation Ideas

### Scheduled Sync (Every 30 minutes)
You can set up a scheduled task to run this automatically:

**Windows Task Scheduler:**
```powershell
# Action: Start a program
Program: python
Arguments: G:\VisualStudio\Python\stats\tools\sync_stats.py
Start in: G:\VisualStudio\Python\stats
```

**Trigger:** Every 30 minutes

### Manual Sync
Just run it whenever you want to check for new stats:
```bash
python tools/sync_stats.py
```

## 📈 Database Impact

- **Sessions**: Each round creates one session entry
- **Players**: All player stats for each round
- **Weapons**: All weapon usage stats
- **Tracking**: `processed_files` table prevents duplicates

## 🎮 Test The Data

After syncing, test the new data:

```bash
# Check latest session
python -c "from check_oct2 import *"

# Or start the bot and use commands:
python bot/ultimate_bot.py

# Then in Discord:
!last_session
!stats
!leaderboard
```

## 🐛 Troubleshooting

### "SSH Authentication failed"
- Check SSH key exists: `~/.ssh/etlegacy_bot`
- Verify key permissions
- Test manual SSH: `ssh -i ~/.ssh/etlegacy_bot -p 48101 et@puran.hehe.si`

### "No new files" but you expect them
- Files might already be downloaded
- Check `local_stats/` folder
- Verify remote path is correct

### Import fails
- Check database file exists: `etlegacy_production.db`
- Verify stat file format is correct
- Check logs: `dev/bulk_import.log`

## 🔄 Comparison: Old vs New Way

### ❌ Old Way (Slow)
```bash
# Download files manually
python test_ssh_download.py

# Then bulk import EVERYTHING (3000+ files)
python dev/bulk_import_stats.py  # Takes minutes!
```

### ✅ New Way (Fast)
```bash
# Download AND import in one go
python tools/sync_stats.py  # Only processes new files!
```

**Speed improvement**: 
- Old: 2-5 minutes (checks all 3000+ files)
- New: 5-15 seconds (only processes new files)

## 📝 File Naming Convention

Files follow this format:
```
YYYY-MM-DD-HHMMSS-mapname-round-N.txt
│    │  │  │ │ │  │       │     │
│    │  │  │ │ │  │       │     └─ Round number (1 or 2)
│    │  │  │ │ │  │       └─────── Map name
│    │  │  │ │ │  └─────────────── Time (HHMMSS)
│    │  │  └─┴─┴────────────────── Date
└────┴──┴───────────────────────── Year

Example: 2025-10-02-211808-etl_adlernest-round-1.txt
         └─ October 2, 2025, 21:18:08, ET Legacy Adlernest, Round 1
```

## 🎯 Best Practices

1. **Run sync after game sessions** - Get the latest stats
2. **Check the output** - Verify files were imported successfully
3. **Monitor failed imports** - Investigate if > 5% fail
4. **Keep backups** - Database is backed up automatically

## 🚀 Future Enhancements

Possible improvements:
- [ ] Auto-sync background task in Discord bot
- [ ] Discord notification when new stats are imported
- [ ] Web dashboard showing sync status
- [ ] Auto-consolidate player names after import
- [ ] Generate match reports automatically

---

**Last Updated**: October 3, 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready
