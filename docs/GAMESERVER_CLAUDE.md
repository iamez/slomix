# Game Server - CLAUDE.md

> **Status**: Production | **Location**: puran.hehe.si
> **Last Documented**: 2026-01-26
> **Management**: crontab + bash scripts (no systemd)

## Overview

The ET:Legacy game server runs on a VPS container and uses **screen sessions**, **bash scripts**, and **crontab** for process management instead of systemd services.

**Why this matters**: When troubleshooting or making changes, understand that there's no `systemctl` - everything is managed via scripts and screen.

---

## Quick Reference

| What | Value |
|------|-------|
| **Host** | puran.hehe.si |
| **SSH** | `ssh -p 48101 et@puran.hehe.si` |
| **SSH Key** | `~/.ssh/etlegacy_bot` |
| **Game Version** | ET:Legacy v2.83.1-x86_64 |
| **Screen Session** | `vektor` |
| **Game Port** | UDP 27960 (default) |
| **OS** | Debian 5.10 (LXC container) |
| **Disk** | 100GB (3% used) |
| **RAM** | 94GB available |

---

## Directory Structure

```
/home/et/
├── start.sh                    # Main startup script (@reboot)
├── start_servers.log           # Startup log file
├── etdaemon.log                # Daemon output log
│
├── etlegacy-v2.83.1-x86_64/    # Game server installation
│   ├── etlded.x86_64           # Dedicated server binary
│   ├── etdaemon.sh             # Watchdog daemon script
│   ├── etmain/
│   │   ├── vektor.cfg          # Server config (loaded on start)
│   │   └── legacy.cfg          # Mod configuration
│   └── legacy/                 # Mod files
│       ├── c0rnp0rn7.lua       # Stats tracking Lua
│       ├── endstats.lua        # End-round stats
│       └── luascripts/
│           └── stats_discord_webhook.lua  # Real-time webhook
│
├── scripts/                    # Utility scripts
│   ├── log_monitor.sh          # Watches logs, sends webhooks
│   ├── stats_webhook_notify.py # Python webhook notifier
│   └── ws_notify_server.py     # WebSocket notification server
│
├── .etlegacy/legacy/           # Runtime data
│   ├── gamestats/              # Stats files (bot downloads these)
│   ├── legacy3.log             # Main game log (130MB+)
│   └── etconsole.log           # Console output
│
└── backups/                    # Manual backups
```

---

## Process Management

### Complete Automation Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    GAME SERVER AUTOMATION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─── SYSTEMD (1 service) ───┐                                  │
│  │                           │                                  │
│  │  et-stats-webhook.service │ ← Watches gamestats/             │
│  │  └── stats_webhook_notify.py   → Discord webhook on new file │
│  │      (watchdog library)   │                                  │
│  │                           │                                  │
│  └───────────────────────────┘                                  │
│                                                                  │
│  ┌─── CRONTAB + BASH ────────┐                                  │
│  │                           │                                  │
│  │  @reboot start.sh         │                                  │
│  │    ├── log_monitor.sh     │ ← Tail logs → curl webhooks      │
│  │    │   (voice events)     │                                  │
│  │    └── etdaemon.sh        │ ← Watchdog loop                  │
│  │        └── screen vektor  │                                  │
│  │            └── etlded.x86_64  ← Game server                  │
│  │                           │                                  │
│  │  0 20 * * * kill etlded   │ ← Daily restart at 20:00         │
│  │                           │                                  │
│  └───────────────────────────┘                                  │
│                                                                  │
│  ┌─── LUA (in-game) ─────────┐                                  │
│  │                           │                                  │
│  │  c0rnp0rn7.lua            │ ← Per-player stats               │
│  │  endstats.lua             │ ← Round aggregation              │
│  │  stats_discord_webhook.lua│ ← Real-time Discord notification │
│  │                           │                                  │
│  └───────────────────────────┘                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Running Processes Summary
| Process | Type | Started | Purpose |
|---------|------|---------|---------|
| `etlded.x86_64` | Screen | Jan 25 | Game server |
| `etdaemon.sh` | Bash | Jan 25 | Watchdog (restarts server) |
| `log_monitor.sh` | Bash | 2025 | Voice event webhooks |
| `stats_webhook_notify.py` | ~~Systemd~~ | ❌ DISABLED | ~~File watcher~~ **DEPRECATED** |

### Systemd Service (DEPRECATED)

**`et-stats-webhook.service`** - **KEEP DISABLED** - Replaced by Lua webhook:
```ini
[Unit]
Description=ET:Legacy Stats Webhook Notifier
After=network.target

[Service]
Type=simple
User=et
WorkingDirectory=/home/et/scripts
Environment="STATS_PATH=/home/et/.etlegacy/legacy/gamestats"
Environment="DISCORD_WEBHOOK_URL=<webhook_url>"
Environment="STATE_DIR=/home/et/scripts/state"
ExecStart=/usr/bin/python3 /home/et/scripts/stats_webhook_notify.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Status**: DISABLED (keep it this way)

**Why deprecated?** The Lua webhook (`stats_discord_webhook.lua`) replaced this:
- Lua fires INSTANTLY at round end (before file fully written)
- Lua includes timing/pause/team metadata (Python just sent filename)
- Lua fixes surrender timing bug (stats files show wrong time)
- Bot's `endstats_monitor` provides 60s polling fallback

**Do NOT re-enable** - completely redundant with Lua + bot polling

### Crontab Entries
```bash
# Start everything on reboot
@reboot /bin/bash /home/et/start.sh > /dev/null 2>&1

# Kill server daily at 20:00 (daemon auto-restarts it)
0 20 * * * kill $(pidof /home/et/etlegacy-v2.83.1-x86_64/etlded.x86_64)
```

### Scripts Detail

#### start.sh (Boot Entry Point)
- Runs on system boot via crontab @reboot
- Sleeps 5 seconds, then starts:
  1. `log_monitor.sh` - voice event webhooks
  2. `etdaemon.sh` - game server watchdog
- Uses `pgrep` to avoid duplicate processes

#### etdaemon.sh (Game Server Watchdog)
- Starts game server in screen session `vektor`
- Loops every 1 minute checking if server is running
- Auto-restarts if crashed
- CPU affinity: `taskset -c 0,1` (pins to cores 0,1)

#### log_monitor.sh (Voice Event Webhooks)
- Tails all `legacy*.log` files
- Greps for "voice" events
- Sends curl requests to bot webhook endpoints:
  - `voice_common` → general voice events
  - `voice_teams` → team voice events
  - `voice_set_teams` → team set events

#### stats_webhook_notify.py (File Watcher) ❌ DEPRECATED
- Uses Python `watchdog` library
- Monitors `~/.etlegacy/legacy/gamestats/` for new files
- Waits 3 seconds for file to complete writing
- Sends Discord webhook with filename
- Tracks processed files in `state/processed_files.json`
- **STATUS**: DISABLED - Replaced by Lua webhook (Jan 2026)
- **DO NOT RE-ENABLE** - Lua webhook is superior (instant + metadata)

### Unused/Inactive Scripts
| Script | Purpose | Status |
|--------|---------|--------|
| `stats_webhook_notify.py` | File watcher → Discord | ❌ DEPRECATED (Lua replaced) |
| `ws_notify_server.py` | WebSocket notification server | Not running |
| `unused_file_monitor.sh` | inotifywait → SCP to webserver | Not running |

---

## Server Configuration

### vektor.cfg (Main Server Config)
```
sv_hostname         "^a#^7p^au^7rans^a.^7only"
sv_maxclients       16
sv_privateclients   1
g_password          "glhf"
rconpassword        "glavni123"
refereePassword     "glavni"
g_customConfig      "legacy3"
sv_fps              40
omnibot_enable      0
```

### Lua Modules (from legacy.cfg)
```
lua_modules "luascripts/team-lock c0rnp0rn7.lua endstats.lua luascripts/stats_discord_webhook.lua"
```

| Module | Purpose |
|--------|---------|
| `team-lock` | Team locking functionality |
| `c0rnp0rn7.lua` | Main stats tracking (per-player stats) |
| `endstats.lua` | End-round stats aggregation |
| `stats_discord_webhook.lua` | Real-time Discord notifications |

---

## Common Operations

### Connect to Server
```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@puran.hehe.si
```

### Check Server Status
```bash
# Is server running?
screen -ls  # Look for "vektor"

# Attach to server console
screen -r vektor
# Detach: Ctrl+A D

# Check processes
ps aux | grep etl
```

### Restart Server
```bash
# Option 1: Kill and let daemon restart
kill $(pidof /home/et/etlegacy-v2.83.1-x86_64/etlded.x86_64)
# Daemon will restart within 1 minute

# Option 2: Manual restart
screen -S vektor -X quit  # Kill screen
cd ~/etlegacy-v2.83.1-x86_64
./etdaemon.sh &  # Start daemon
```

### View Logs
```bash
# Console log (live)
tail -f ~/.etlegacy/legacy/etconsole.log

# Game log (large file)
tail -f ~/.etlegacy/legacy/legacy3.log

# Startup log
tail -f ~/start_servers.log
```

### RCON Commands (In-Game Admin)
```
# From server console (screen -r vektor)
rcon status
rcon map supply
rcon exec vektor.cfg
```

---

## Data Flow (Stats)

```
Game Round Ends (PLAYING → INTERMISSION)
    ↓
┌───────────────────────────────────────────────────────┐
│ PARALLEL:                                             │
│   c0rnp0rn7.lua / endstats.lua → Write stats file    │
│   stats_discord_webhook.lua → POST "STATS_READY"      │
└───────────────────────────────────────────────────────┘
    ↓
~/.etlegacy/legacy/gamestats/
    YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    ↓
Discord Bot sees "STATS_READY" message (with embeds)
    ↓ SSH to server
    ↓ Downloads stats file
    ↓ Parses and imports to PostgreSQL
    ↓ Posts stats to Discord channel
```

### Notification Systems (Jan 2026)

| System | Type | Status | Trigger |
|--------|------|--------|---------|
| **Lua webhook** | In-game | ✅ ACTIVE | Round ends → instant |
| **endstats_monitor** | Bot polling | ✅ FALLBACK | Every 60 seconds via SSH |
| **stats_webhook_notify.py** | File watcher | ❌ DEPRECATED | File created (redundant) |

**Why two active systems?**
- Lua webhook: Instant notification + timing/pause/team metadata
- endstats_monitor: Safety net if Lua fails (also handles bot restarts)

The Python file watcher is redundant - Lua fires BEFORE the file is even fully written.

---

## Migration to Systemd (Future)

### Proposed Service Files

**etlegacy-server.service** (replaces etdaemon.sh + screen):
```ini
[Unit]
Description=ET:Legacy Game Server
After=network.target

[Service]
Type=simple
User=et
WorkingDirectory=/home/et/etlegacy-v2.83.1-x86_64
ExecStart=/usr/bin/taskset -c 0,1 /home/et/etlegacy-v2.83.1-x86_64/etlded.x86_64 +exec vektor.cfg
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**etlegacy-logmonitor.service** (replaces log_monitor.sh):
```ini
[Unit]
Description=ET:Legacy Log Monitor
After=etlegacy-server.service

[Service]
Type=simple
User=et
ExecStart=/home/et/scripts/log_monitor.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

### Migration Steps (When Ready)
1. Create service files in `/etc/systemd/system/`
2. Remove crontab entries
3. `systemctl daemon-reload`
4. `systemctl enable etlegacy-server etlegacy-logmonitor`
5. Test: `systemctl start etlegacy-server`
6. Verify: `systemctl status etlegacy-server`

### Benefits of Systemd
- Auto-restart on crash (built-in)
- Proper logging via journald
- Service dependencies
- `systemctl status` for quick health check
- Boot ordering guarantees

---

## Version Management & Updates

### Current Version
```
ET:Legacy v2.83.1-34-ga127043
PK3: legacy_v2.83.1-34-ga127043.pk3
```

### Versioning Philosophy
The **competitive community uses stable releases**, not bleeding-edge snapshots:
- Snapshots drop frequently from ET:Legacy dev team
- Comp community stays on proven stable versions (often ~1 year old)
- Only update when a comp-significant fix is released
- Current stable: v2.83.1 (been stable for competitive play)

### Update Scripts
| Script | Location | Purpose |
|--------|----------|---------|
| `etlupdate.sh` | `~/` | Original update script (v2.82.0) |
| `etlupdate3.sh` | `~/etlegacy-v2.83.1-x86_64/` | **Latest** - single-command update |

### Update Process (etlupdate3.sh)
```bash
# Usage: ./etlupdate3.sh <url_or_file.tar.gz>

# Example with GitHub snapshot URL:
./etlupdate3.sh https://github.com/HeDo88TH/etlegacy-snapshots/raw/main/snapshots/etlegacy-v2.83.2-33-gb3a1f63-x86_64.tar.gz
```

**What it does:**
1. Downloads/extracts update archive
2. Stops server screens (vektor, aim)
3. Backs up old pk3 files to `~/legacyupdate/backup/`
4. Copies new files to game directory
5. Uploads new pk3 to webserver (`/var/www/html/legacy/`) for fast client downloads
6. Logs everything to `~/legacyupdate/backup/logs/update.log`

### Snapshot Sources
- **Official**: https://www.etlegacy.com/workflow-files/
- **GitHub Mirror**: https://github.com/HeDo88TH/etlegacy-snapshots

### When to Update
- ✅ Security fixes
- ✅ Game-breaking bug fixes
- ✅ When comp community agrees on new stable version
- ❌ Don't chase every snapshot
- ❌ Avoid mid-season updates (can affect balance)

### Rollback Procedure
```bash
# Old pk3 files are backed up to:
ls ~/legacyupdate/backup/*.pk3

# To rollback:
# 1. Stop server
screen -S vektor -X quit

# 2. Restore old pk3
cp ~/legacyupdate/backup/legacy_v2.83.1-XX.pk3 ~/etlegacy-v2.83.1-x86_64/legacy/

# 3. Restart
cd ~/etlegacy-v2.83.1-x86_64 && ./etdaemon.sh &
```

---

## Maintenance Notes

### Backup Before Changes
```bash
# Create backup
mkdir -p ~/backups/$(date +%Y-%m-%d)
cp ~/etlegacy-v2.83.1-x86_64/etdaemon.sh ~/backups/$(date +%Y-%m-%d)/
cp ~/etlegacy-v2.83.1-x86_64/etmain/*.cfg ~/backups/$(date +%Y-%m-%d)/
```

### Update Lua Scripts
```bash
# From local machine (samba)
scp -P 48101 -i ~/.ssh/etlegacy_bot \
  vps_scripts/stats_discord_webhook.lua \
  et@puran.hehe.si:~/etlegacy-v2.83.1-x86_64/legacy/luascripts/

# Then restart server to reload Lua
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "kill \$(pidof /home/et/etlegacy-v2.83.1-x86_64/etlded.x86_64)"
```

### Disk Space Check
```bash
df -h /home/et
du -sh ~/.etlegacy/legacy/gamestats/
du -sh ~/.etlegacy/legacy/*.log
```

### Clean Old Logs (if needed)
```bash
# Archive old game logs
gzip ~/.etlegacy/legacy/legacy*.log.old

# Remove very old stats files (older than 90 days)
find ~/.etlegacy/legacy/gamestats/ -mtime +90 -delete
```

---

## Troubleshooting

### Server Not Starting
```bash
# Check if already running
pgrep -f etlded.x86_64

# Check daemon log
tail -50 ~/start_servers.log

# Check screen
screen -ls

# Manual start for debugging
cd ~/etlegacy-v2.83.1-x86_64
./etlded.x86_64 +exec vektor.cfg
```

### Webhook Not Working
```bash
# Check log_monitor is running
pgrep -f log_monitor

# Check webhook log
tail -f ~/scripts/webhook.log

# Test webhook manually
curl -X POST http://161.35.72.7:8000/webhook/event/voice_common
```

### Stats Files Not Generating
```bash
# Check gamestats directory
ls -lt ~/.etlegacy/legacy/gamestats/ | head

# Check Lua is loading
grep -i "lua" ~/.etlegacy/legacy/etconsole.log | tail

# Check for Lua errors
grep -i "error\|fail" ~/.etlegacy/legacy/etconsole.log | tail
```

---

## Quick Commands Cheatsheet

```bash
# Connect
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si

# Server status
screen -ls

# Attach to server console
screen -r vektor

# Restart server
kill $(pidof ~/etlegacy-v2.83.1-x86_64/etlded.x86_64)

# View logs
tail -f ~/.etlegacy/legacy/etconsole.log

# Check recent stats files
ls -lt ~/.etlegacy/legacy/gamestats/ | head

# Upload Lua script
scp -P 48101 script.lua et@puran.hehe.si:~/etlegacy-v2.83.1-x86_64/legacy/luascripts/
```

---

**Current Setup**: crontab + bash + screen
**Recommended Migration**: systemd services for better reliability
