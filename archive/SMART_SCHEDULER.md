# Smart Sync Scheduler - Documentation

## 🎯 Overview

The **Smart Sync Scheduler** automatically syncs stats from the game server with intelligent timing based on typical gaming patterns. It checks **frequently during prime time** (20:00-23:00 CET) and **less frequently during off-hours**.

## ⏰ Sync Strategy

### Prime Time (20:00-23:00 CET)
**Active gaming hours** - Games typically start around 20:00-21:00 CET

| Scenario | Interval | Reason |
|----------|----------|--------|
| **New files found** | 1 minute | Active session - check frequently for new rounds |
| **No files (1st check)** | 1 minute | Might be between rounds |
| **No files (2-9 checks)** | 10 minutes | Session might be ending |
| **No files (10+ checks)** | 30 minutes | Session over, reduce checks |

### Before Prime Time (19:30-20:00 CET)
**Ramp-up period** - Prepare for incoming games

| Scenario | Interval |
|----------|----------|
| Any | 5 minutes |

### Off-Hours (00:00-19:30 CET & 23:00-00:00 CET)
**Low activity period** - Rare or no games

| Scenario | Interval | Reason |
|----------|----------|--------|
| **New files found** | 5 minutes | Unexpected session - monitor it |
| **No files (1-5 checks)** | 10 minutes | Give it a chance |
| **No files (6+ checks)** | Until 19:30 next day | Deep sleep - wake before prime time |

## 🚀 Usage

### Start the Scheduler

```bash
python tools/smart_scheduler.py
```

This will:
1. Start immediately with a sync check
2. Determine the best interval based on time and results
3. Run continuously, adapting to game activity
4. Log everything to `logs/smart_sync.log`

### Run as Background Process (Windows)

**Option 1: PowerShell Background Job**
```powershell
Start-Job -ScriptBlock { 
    cd "G:\VisualStudio\Python\stats"
    python tools\smart_scheduler.py 
}

# Check if it's running
Get-Job

# Stop it later
Stop-Job -Name Job1
```

**Option 2: Task Scheduler (Recommended)**
1. Open **Task Scheduler**
2. Create Basic Task
   - Name: "ET Legacy Smart Sync"
   - Trigger: "When I log on"
   - Action: "Start a program"
   - Program: `python`
   - Arguments: `G:\VisualStudio\Python\stats\tools\smart_scheduler.py`
   - Start in: `G:\VisualStudio\Python\stats`
3. Properties → Conditions:
   - ✅ Start only if on AC power (if laptop)
   - ✅ Start only if computer is on
4. Properties → Settings:
   - ✅ If task fails, restart every 1 minute (3 times)

**Option 3: Run Hidden with pythonw**
```powershell
Start-Process pythonw -ArgumentList "tools\smart_scheduler.py" -WindowStyle Hidden
```

## 📊 Monitoring

### Check Logs

```powershell
# View last 20 lines
Get-Content logs\smart_sync.log -Tail 20

# Follow in real-time (like tail -f)
Get-Content logs\smart_sync.log -Wait -Tail 10
```

### Log Output Examples

```
2025-10-03 20:15:30 - INFO - 🔄 Sync check at 20:15:30 CET (PRIME TIME)
2025-10-03 20:15:31 - INFO - ✅ New files synced and imported
2025-10-03 20:15:31 - INFO - Downloaded: 2 files
2025-10-03 20:15:31 - INFO - Imported:   2 files
2025-10-03 20:15:31 - INFO - 📊 Active session - next check in 1 minute
2025-10-03 20:15:31 - INFO - ⏰ Next sync in 60s (1.0 min)
```

```
2025-10-03 03:00:00 - INFO - 🔄 Sync check at 03:00:00 CET (off-hours)
2025-10-03 03:00:01 - INFO - ✅ No new files found
2025-10-03 03:00:01 - INFO - 😴 Deep sleep until 19:30 CET (16.5 hours)
```

## 🔧 Configuration

Edit `tools/smart_scheduler.py` to customize:

```python
# Prime time hours (CET)
self.prime_time_start = 20  # 8 PM
self.prime_time_end = 23    # 11 PM

# Ramp-up time before prime
minutes_before = 30  # Start checking 30 min before prime time
```

## 🎮 Typical Day Flow

```
00:00 - 19:00  💤 Deep sleep (checked at midnight, sleeping until 19:30)
19:30 - 20:00  ⏰ Ramp-up (checks every 5 minutes)
20:00 - 20:15  📊 First game detected! (1 min checks)
20:15 - 22:45  🎮 Active gaming (1 min during rounds, 10 min between maps)
22:45 - 23:15  ⏸️  Winding down (10 min checks, then 30 min checks)
23:15 - 00:00  💤 Post-prime time (10 min checks, then sleep)
```

## 📈 Performance

### Resource Usage
- **CPU**: Minimal (mostly sleeping)
- **Memory**: ~30-40 MB
- **Network**: Only during sync (few KB - MB depending on files)
- **Disk**: Log file grows ~1-5 MB per day

### Efficiency vs Polling
**Old approach**: Check every 5 minutes = **288 checks/day**  
**Smart scheduler**: 
- Prime time: ~180 checks (3 hours × 60 checks/hour)
- Off-hours: ~10 checks
- **Total**: ~190 checks/day (34% fewer!)

But more importantly: **Checks when it matters!**

## 🐛 Troubleshooting

### Scheduler Not Finding New Files

```bash
# Manually test sync
python tools/sync_stats.py

# Check SSH connection
python test_ssh_download.py
```

### Scheduler Stops Running

Check logs for errors:
```powershell
Get-Content logs\smart_sync.log -Tail 50 | Select-String "ERROR"
```

Common issues:
- SSH key expired or moved
- Network connectivity
- Disk full
- Python process killed

### Test Without Waiting

Temporarily modify intervals for testing:
```python
# In smart_scheduler.py, change all returns to:
return 10  # Test with 10 second intervals
```

## 🔄 Integration with Discord Bot

The scheduler and bot can run together:

**Terminal 1**: Bot
```bash
python bot/ultimate_bot.py
```

**Terminal 2**: Scheduler
```bash
python tools/smart_scheduler.py
```

They share the same database, so:
1. Scheduler syncs new files
2. Database gets updated
3. Bot commands immediately show new data

## 🎯 Future Enhancements

Possible improvements:
- [ ] Discord notification when new sessions imported
- [ ] Auto-post match results to Discord channel
- [ ] Web dashboard showing scheduler status
- [ ] ML-based prediction of game times
- [ ] Multiple server support

## 📝 Notes

- Scheduler uses CET timezone (Europe/Paris)
- All times logged in CET for consistency
- SSH credentials from `.env` file
- Logs rotate automatically (not implemented yet - add if logs get huge)
- Scheduler is crash-resistant (5 min wait on errors)

---

**Status**: ✅ Production Ready  
**Version**: 1.0  
**Last Updated**: October 3, 2025
