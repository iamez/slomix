# SSH Monitor - New vs Existing Explanation

## TL;DR: I Created a New, SEPARATE System

**Short Answer:** I created a **brand new automated monitoring system** that runs independently alongside your existing `!sync_stats` command. They both use the same underlying SSH helper methods but serve different purposes.

---

## 🔄 What You Already Had: `!sync_stats` Command

### Purpose
**Manual, on-demand file synchronization**

### How It Works
1. **You type** `!sync_stats` in Discord
2. Bot connects to SSH server
3. Lists all files (or filtered by time period like `!sync_stats 1week`)
4. Compares with database to find unprocessed files
5. Downloads ALL unprocessed files
6. Processes them in order
7. Reports back with summary

### Location
- **File:** `bot/cogs/sync_cog.py` (existing)
- **Commands:** `!sync_stats`, `!sync_today`, `!sync_week`, `!sync_month`, `!sync_all`
- **Usage:** Manual command when you want to pull files

### Code Flow
```python
# In sync_cog.py
@commands.command(name="sync_stats")
async def sync_stats(self, ctx, period: str = None):
    # 1. List remote files via SSH
    remote_files = await self.bot.ssh_list_remote_files(ssh_config)
    
    # 2. Check which need processing
    files_to_process = []
    for filename in remote_files:
        if await self.bot.should_process_file(filename):
            files_to_process.append(filename)
    
    # 3. Download all files
    for filename in files_to_process:
        local_path = await self.bot.ssh_download_file(ssh_config, filename)
    
    # 4. Process all files
    for filename, local_path in downloaded_files:
        result = await self.bot.process_gamestats_file(local_path, filename)
```

### When to Use
- After multiple rounds have been played
- At end of gaming session
- When you notice files are missing
- Manual catch-up sync

---

## 🤖 What I Created: `SSHFileMonitor` (Automation)

### Purpose
**Automatic, real-time round detection and posting**

### How It Works
1. **Bot automatically polls** SSH directory every 30 seconds
2. Detects NEW files that appeared since last check
3. **Immediately downloads** the new file
4. **Immediately parses** and imports to DB
5. **Immediately posts** round stats to Discord channel
6. Repeats forever while bot is running

### Location
- **File:** `bot/services/automation/ssh_monitor.py` (NEW!)
- **Commands:** `!start_monitoring`, `!stop_monitoring`, `!ssh_stats`
- **Usage:** Runs automatically in the background

### Code Flow
```python
# In ssh_monitor.py
async def _monitoring_loop(self):
    while self.is_monitoring:
        # 1. Check for NEW files every 30 seconds
        new_files = await self._check_for_new_files()
        
        # 2. Process ONLY new files immediately
        for filename in new_files:
            await self._process_new_file(filename)
            
            # 3. Post stats to Discord RIGHT AWAY
            await self._post_round_stats(stats_data)
        
        # 4. Wait 30 seconds, repeat
        await asyncio.sleep(30)

async def _check_for_new_files(self):
    # List remote files
    remote_files = await self._list_remote_files()
    
    # Find files we HAVEN'T seen before
    new_files = [f for f in remote_files if f not in self.processed_files]
    
    return new_files
```

### When It Works
- **Automatically** while bot is running
- Checks every 30 seconds
- Runs 24/7 without human intervention
- As soon as round ends and server creates `.txt` file, bot detects it

---

## 🤝 How They Work Together

### Shared Components (What They Both Use)

Both systems use the **SAME SSH helper methods** from `ultimate_bot.py`:

```python
# In ultimate_bot.py (lines 3096-3250)

async def ssh_list_remote_files(ssh_config):
    """List .txt files on remote SSH server"""
    # Used by BOTH sync_stats and SSHFileMonitor

async def ssh_download_file(ssh_config, filename, local_dir):
    """Download a single file from remote server"""
    # Used by BOTH sync_stats and SSHFileMonitor

async def process_gamestats_file(local_path, filename):
    """Process a gamestats file: parse and import to database"""
    # Used by BOTH sync_stats and SSHFileMonitor
```

### Key Differences

| Feature | `!sync_stats` (Existing) | `SSHFileMonitor` (New) |
|---------|-------------------------|------------------------|
| **Trigger** | Manual command | Automatic loop |
| **Frequency** | When you type it | Every 30 seconds |
| **Scope** | Can sync multiple files | Processes new files only |
| **Time Filter** | Can filter by period | Real-time only |
| **Discord Post** | Summary after all processed | Posts stats after each round |
| **Use Case** | Catch-up, bulk sync | Real-time monitoring |
| **Status** | Active, working | New, needs integration |

---

## 📊 Real-World Example

### Scenario: You Play 3 Rounds on Friday Night

#### With Old System Only (`!sync_stats`)
```
[9:00 PM] Round 1 finishes → file created on server
[9:20 PM] Round 2 finishes → file created on server
[9:45 PM] Round 3 finishes → file created on server
[10:00 PM] You type !sync_stats
[10:01 PM] Bot downloads all 3 files
[10:02 PM] Bot processes all 3 files
[10:03 PM] Bot sends summary: "Processed 3 files"
```

**Result:** You get stats AFTER all rounds are done, when you remember to sync.

#### With New System (`SSHFileMonitor`)
```
[9:00 PM] Round 1 finishes → file created
[9:00:30 PM] ✅ Bot detects new file, downloads, posts Round 1 stats!
[9:20 PM] Round 2 finishes → file created
[9:20:30 PM] ✅ Bot detects new file, downloads, posts Round 2 stats!
[9:45 PM] Round 3 finishes → file created
[9:45:30 PM] ✅ Bot detects new file, downloads, posts Round 3 stats!
```

**Result:** Stats appear automatically ~30 seconds after each round ends!

#### Using Both Together
```
[Friday Night]
- SSHFileMonitor runs automatically, posts stats in real-time

[Sunday Morning]
- You notice bot was offline Saturday
- You type !sync_stats 2days
- Catches up on all Saturday files
- Then SSHFileMonitor takes over again
```

**Result:** Best of both worlds! Auto-posting + manual catch-up.

---

## 🔧 Technical Implementation

### What I Built (New Files)

```
bot/services/automation/
├── ssh_monitor.py         ← NEW! Automatic monitoring
├── metrics_logger.py      ← NEW! Logs all events
├── health_monitor.py      ← NEW! Monitors bot health
└── database_maintenance.py ← NEW! Auto backups

bot/cogs/
└── automation_commands.py ← NEW! Commands to control monitoring
```

### What I Reused (Existing Methods)

The new `SSHFileMonitor` **does NOT duplicate code**. It calls your existing methods:

```python
# In ssh_monitor.py

async def _list_remote_files(self):
    """List files on remote server"""
    # Calls your existing helper method!
    return await self.bot.ssh_list_remote_files(self.ssh_config)

async def _download_file(self, filename):
    """Download a file"""
    # Calls your existing helper method!
    return await self.bot.ssh_download_file(self.ssh_config, filename)

async def _process_file(self, local_path, filename):
    """Process stats file"""
    # Calls your existing helper method!
    return await self.bot.process_gamestats_file(local_path, filename)
```

---

## ✅ Why I Made a New System

### Your Original Request
> "its ssh directory checking, if and when thers a new round/txt file, we paste stats for the round in a new dedicated channel for it... so as the round finishes, bot alredy reading what happend and posting stats for the round"

This is **different** from `!sync_stats` because:
1. **Automatic** vs Manual
2. **Real-time** vs On-demand
3. **Background task** vs Command
4. **Per-round posting** vs Bulk summary

### What Would NOT Work

If I tried to modify `!sync_stats` to do this:
- ❌ Commands run once when called, can't run forever
- ❌ Would need to constantly type `!sync_stats` every 30 seconds
- ❌ Bulk processing doesn't give per-round updates
- ❌ No automatic Discord posting after each round

### What DOES Work

Creating a separate background service that:
- ✅ Runs continuously in a loop
- ✅ Checks every 30 seconds automatically
- ✅ Posts to Discord after EACH round
- ✅ Doesn't interfere with manual `!sync_stats`
- ✅ Can be started/stopped with commands
- ✅ Tracked with metrics for analysis

---

## 🎯 Summary

### What Already Existed
- ✅ `!sync_stats` command (sync_cog.py)
- ✅ SSH helper methods (ultimate_bot.py)
- ✅ Manual file synchronization

### What I Created (New)
- ✨ `SSHFileMonitor` class (ssh_monitor.py)
- ✨ Background monitoring loop
- ✨ Real-time round detection
- ✨ Automatic Discord posting
- ✨ Metrics logging
- ✨ Health monitoring
- ✨ Control commands (!start_monitoring, !ssh_stats)

### They Work Together
```
┌─────────────────┐         ┌──────────────────┐
│  !sync_stats    │         │  SSHFileMonitor  │
│  (Manual)       │         │  (Automatic)     │
└────────┬────────┘         └────────┬─────────┘
         │                           │
         │   Both use these:         │
         └───────┬───────────────────┘
                 │
        ┌────────▼─────────┐
        │ SSH Helper       │
        │ Methods          │
        │                  │
        │ • list_files()   │
        │ • download_file()│
        │ • process_file() │
        └──────────────────┘
```

---

## 🚀 Next Steps

1. **Keep `!sync_stats`** - It's still useful for:
   - Manual catch-up
   - Historical data
   - When bot was offline

2. **Integrate `SSHFileMonitor`** - Adds:
   - Real-time monitoring
   - Automatic posting
   - 24/7 operation

3. **Use Both** - They complement each other perfectly!

---

## ❓ Your Questions Answered

**Q: Did you make a new SSH monitor or expand the current one?**

**A:** I made a **completely new, separate system** that:
- Uses the same underlying SSH methods (no duplication)
- Serves a different purpose (automatic vs manual)
- Runs alongside existing `!sync_stats`
- Adds new capabilities (real-time monitoring, metrics, health checks)

**Q: Why not just modify `!sync_stats`?**

**A:** Because they're fundamentally different:
- `!sync_stats` = Manual command (run once)
- `SSHFileMonitor` = Background service (runs forever)

Think of it like:
- `!sync_stats` = Taking your car to the car wash
- `SSHFileMonitor` = Installing an automatic sprinkler system

Both clean, but different use cases!

---

**Does this make sense?** Let me know if you want me to clarify anything! 😊
