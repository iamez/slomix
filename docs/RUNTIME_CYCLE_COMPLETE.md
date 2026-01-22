# Complete Bot Runtime Cycle - slomix_discord

**Last Updated**: December 17, 2025
**Status**: Production System Documentation

---

## Quick Summary

**Architecture**:

- **Bot**: Local Linux (samba) running Discord.py bot
- **Game Server**: VPS (puran) running ET:Legacy
- **Notification**: Discord Webhook (Dec 2025) → WebSocket deprecated
- **Database**: PostgreSQL 14 (system service)

**Key Flow**:

```python
Game finishes → VPS webhook → Discord control channel → Bot downloads via SSH →
Parse → PostgreSQL import → Post to production channel → Users see stats
```python

---

## 1. Bot Startup Sequence

### Entry Point

**File**: `bot/ultimate_bot.py`
**Command**: `python -m bot.ultimate_bot`

### Initialization Order

```python
main() [Line 2131]
  ↓
__init__() [Line 169-296]
  ├─ Load config (.env → PostgreSQL/SQLite)
  ├─ Create database adapter (connection pool)
  ├─ Initialize core systems:
  │   ├─ StatsCache (300s TTL)
  │   ├─ SeasonManager
  │   ├─ AchievementSystem
  │   └─ FileTracker (5-layer deduplication)
  ├─ Initialize services:
  │   ├─ VoiceSessionService (gaming session detection)
  │   ├─ RoundPublisherService (Discord auto-posting)
  │   └─ FileRepository (data access)
  └─ Configure automation flags
  ↓
setup_hook() [Line 404-638]
  ├─ Connect database
  ├─ Validate schema (54 columns)
  ├─ Load 15+ cogs (commands)
  ├─ Initialize automation services
  ├─ Start background tasks:
  │   ├─ endstats_monitor (60s loop - SSH + posting)
  │   └─ cache_refresher (30s loop - sync)
  └─ WebSocket client (DEPRECATED, disabled by default)
  ↓
on_ready() [Line 2016-2045]
  ├─ Log bot status
  ├─ Validate webhook security
  ├─ Clear old slash commands
  └─ Auto-resume voice sessions (if players present)
```python

---

## 2. File Notification System

### Current: Discord Webhook (Dec 2025)

#### VPS Side

**File**: `vps_scripts/stats_webhook_notify.py`
**Service**: `et-stats-webhook.service` (systemd)

**What it does**:

1. Watches `/home/et/.etlegacy/legacy/gamestats/` (inotify)
2. Detects new `.txt` file creation
3. Validates filename format
4. Waits 3 seconds (file write completion)
5. POSTs webhook to Discord **control channel**
6. Marks file as processed (state JSON)

**Webhook Payload**:

```text
Content: "📊 `2025-12-17-201530-supply-round-1.txt`"
Embed: Minimal (map name, round number)
```python

#### Bot Side

**File**: `ultimate_bot.py`
**Handler**: `_handle_webhook_trigger()` [Line 1847-1915]

**Security**:

1. Webhook ID whitelist (WEBHOOK_TRIGGER_WHITELIST)
2. Rate limiting (5 triggers per 60s per webhook)
3. Filename validation (regex, no path traversal)
4. Channel isolation (control vs production)

**Flow**:

```python
on_message() receives webhook
  ↓
Validate webhook ID (whitelist check)
  ↓
Rate limit check
  ↓
Extract filename from backticks
  ↓
Launch background task: _process_webhook_triggered_file()
  ├─ Check if already processed (5-layer dedup)
  ├─ Download file via SSH
  ├─ Wait 2s for file settling
  ├─ Parse + import to database
  ├─ Post to production stats channel
  └─ Delete trigger message (cleanup)
```python

### Deprecated: WebSocket (Pre-Dec 2025)

**Why deprecated**: Added complexity, webhook is simpler/more reliable

**VPS**: `vps_scripts/ws_notify_server.py` (WebSocket server, port 8765)
**Bot**: `bot/services/automation/ws_client.py` (WebSocket client)

---

## 3. Background Automation Tasks

### Task 1: endstats_monitor (Main Loop)

**File**: `ultimate_bot.py` [Line 1427-1633]
**Interval**: Variable (60s active, 10min idle)
**Purpose**: SSH polling fallback + Discord posting

**Intelligence**:

- **Dead Hours**: 02:00-11:00 CET → No checks (save SSH calls)
- **Active Mode**: 6+ voice players OR <30min since last file → 60s interval
- **Idle Mode**: No activity → 10min interval
- **Voice Detection**: Monitors gaming_voice_channels for player count

**Why it exists**:

- Fallback if webhook fails
- Handles historical sync (one-time operations)
- Posts to Discord (webhook only triggers, doesn't post)

### Task 2: cache_refresher

**Interval**: 30 seconds
**Purpose**: Sync in-memory `processed_files` set with database

### Task 3: voice_session_monitor (DISABLED)

**Status**: Replaced by event-driven `on_voice_state_update()`
**Purpose**: Session end timer (5-minute countdown)

---

## 4. File Processing Pipeline

### Stage 1: Detection (4 Methods)

```text
Priority 1: Discord Webhook (CURRENT)
  VPS webhook → Discord control → Bot handler

Priority 2: WebSocket Push (DEPRECATED)
  VPS WebSocket → Bot client

Priority 3: SSH Polling (FALLBACK)
  endstats_monitor → SSH list → Compare → Download

Priority 4: Manual Import
  Admin command → File selection
```python

### Stage 2: Download via SSH

**Handler**: `bot/automation/ssh_handler.py` [Line 163-238]
**Config**:

```python
{
  "host": SSH_HOST,           # VPS hostname
  "port": SSH_PORT,           # 22 or custom
  "user": SSH_USER,           # SSH username
  "key_path": SSH_KEY_PATH,   # ~/.ssh/etlegacy_bot
  "remote_path": REMOTE_STATS_PATH  # /home/et/.etlegacy/legacy/gamestats
}
```python

**Security**:

- Key-based auth (no passwords)
- Host key verification (configurable)
- 30s timeout on SFTP operations
- Path sanitization (shlex.quote)

**Output**: `local_stats/<filename>`

### Stage 3: Deduplication (5 Layers)

**File**: `bot/automation/file_tracker.py` [Line 65-132]

```sql

Layer 1: File Age Check

- Parse datetime from filename
- Skip if created BEFORE bot startup
- WHY: Prevents re-importing on every restart
- SKIPPED: If ignore_startup_time=True (manual sync)

Layer 2: In-Memory Cache

- Check bot.processed_files set (O(1))
- Fastest layer

Layer 3: Local File Exists

- Check if local_stats/<filename> exists
- Fast filesystem check

Layer 4: Database - processed_files Table

- SELECT WHERE filename=?
- Indexed query

Layer 5: Database - rounds Table

- Parse filename → Check rounds
- Definitive source of truth

```python

### Stage 4: Parsing

**File**: `bot/community_stats_parser.py`
**Format**: c0rnp0rn3.lua TAB-delimited

**Round 2 Intelligence**:

- Detects `-round-2.txt` files
- Finds matching Round 1 file (same timestamp)
- Calculates R2-only stats: `R2_cumulative - R1`
- Rejects R1 files >60min old (different session)
- Creates match_summary (R1 + R2 combined, round_number=0)

**Extracted Data**:

- **Round Metadata**: map, time, outcome, winner
- **Player Stats**: 54 fields (kills, deaths, damage, accuracy, headshots, revives, multikills, time_dead, denied_playtime, etc.)
- **Weapon Stats**: Per-weapon kills, deaths, accuracy, headshots (27 weapons)

### Stage 5: Database Import

**Primary**: PostgreSQL (production)
**Fallback**: SQLite (dev)

**Flow**:

```sql

process_gamestats_file() [Line 801]
  ↓
PostgreSQLDatabase.process_file()
  ├─ BEGIN TRANSACTION
  ├─ Parse filename → match_id
  ├─ Calculate gaming_session_id (60min gap logic)
  ├─ INSERT rounds
  ├─ For each player:
  │   ├─ INSERT player_comprehensive_stats (54 fields)
  │   ├─ INSERT weapon_comprehensive_stats (per-weapon)
  │   └─ UPDATE player_aliases (for !stats/!link)
  ├─ If R2: INSERT match_summary (round_number=0)
  ├─ INSERT processed_files
  └─ COMMIT

```python

**Session Grouping**:

- Uses chronologically PREVIOUS round (not latest in DB)
- Allows out-of-order imports without breaking sessions
- 60-minute gap = new session

### Stage 6: Discord Posting

**File**: `bot/services/round_publisher_service.py` [Line 47-200]

**Flow**:

```sql

publish_round_stats()
  ↓
Fetch FULL data from database (not parser!)
  ├─ rounds table (time, winner, outcome)
  └─ player_comprehensive_stats (all 54 fields)
  ↓
Build Discord Embed
  ├─ Title: "🎮 Round N Complete - mapname"
  ├─ Color: Blue (R1) or Red (R2)
  ├─ For each player (ranked by kills):
  │   ├─ Line 1: Medal + Name + Badges
  │   ├─ Line 2: K/D/G, DPM, Damage, Accuracy, HS
  │   └─ Line 3: UK, Revives, Times, Multikills, Denied
  └─ Footer: Filename + timestamp
  ↓
Send to PRODUCTION stats channel

```python

**Why query database instead of using parser output?**

- Parser might have been run hours ago (manual import)
- Database is source of truth
- Ensures consistency with what users see in !stats

---

## 5. Voice Session Detection

**File**: `bot/services/voice_session_service.py`
**Trigger**: Event-driven (`on_voice_state_update`)

### Session Lifecycle

```sql

Players join voice → 6+ players → start_session()
  ├─ Set session_active = True
  ├─ Track session_participants (Discord IDs)
  ├─ Enable SSH monitoring (optional)
  └─ Post "Gaming session started!" to general channel

Players leave → <2 players → delayed_end() (5-minute timer)
  ├─ Wait 300 seconds
  ├─ Recheck player count
  └─ If still <2 → end_session()

end_session()
  ├─ Set session_active = False
  ├─ Disable SSH monitoring
  ├─ Clear session_participants
  └─ Post "Gaming session ended!" to general channel

```yaml

**Startup Recovery**:

- `check_startup_voice_state()` called during `on_ready()`
- Scans gaming_voice_channels for active players
- If 6+ found → auto-resume session
- Prevents session loss on bot restart

**WHY**:

- Triggers active monitoring mode (60s SSH checks)
- Provides session context for stats
- Allows voice-based session detection (no game server needed)

---

## 6. Command Handling

### Flow

```python

User types !command in Discord
  ↓
bot_check() [Line 383-402]

- Global channel filter
- Only respond in configured channels
- Silently ignore other channels
  ↓
Discord.py routes to Cog
- Based on command name
  ↓
Cog command handler
- Execute business logic
- Query database via db_adapter
- Build response (embed/text)
  ↓
on_command_completion() [Line 2062]
- Log execution time
- Warn if >5 seconds
OR
on_command_error() [Line 2078]
- Handle errors (not found, cooldown, etc.)
- Sanitize error messages (security)

```sql

### Major Command Groups

**Stats** (StatsCog, LeaderboardCog):

- `!stats <player>` - Player statistics
- `!leaderboard` - Top players
- `!compare <p1> <p2>` - Player comparison

**Session** (SessionCog, LastSessionCog):

- `!session <id>` - View specific session
- `!last_session` - Last session with graphs

**Linking** (LinkCog):

- `!link <player>` - Link Discord to ET player
- `!find_player <name>` - Search

**Team** (TeamCog):

- `!teams <session>` - Team compositions

**Admin** (AdminCog):

- Database operations, maintenance, sync

---

## 7. Performance Optimizations

### SSH Call Reduction

**Old**: ~2,880 SSH checks/day (every 30s)
**New**: ~200 SSH checks/day

**How**:

1. Dead hours (02:00-11:00 CET) - No checks
2. Voice-triggered active mode - 60s when 6+ players
3. Grace period - 30min after last file
4. Idle mode - 10min when no activity
5. Webhook primary, SSH fallback

### Deduplication Efficiency

**5-Layer Check** (fastest to slowest):

1. String parsing (free)
2. In-memory set O(1)
3. Filesystem check (fast I/O)
4. Database indexed query
5. Database definitive query

Only goes to next layer if previous says "process"

### Database

- Connection pooling (PostgreSQL)
- Parameterized queries (security + performance)
- Indexes on: round_date, map_name, player_guid, gaming_session_id
- Batch operations where possible

---

## 8. Security Features

### Webhook Security (CRITICAL)

```text

1. Webhook ID Whitelist
   - WEBHOOK_TRIGGER_WHITELIST env var
   - Only whitelisted webhooks can trigger
   - Prevents unauthorized execution

2. Rate Limiting
   - 5 triggers per 60s per webhook
   - Prevents DoS

3. Filename Validation
   - Strict regex: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
   - No path traversal (/, \, .., null bytes)
   - Length limit (255 chars)
   - Component validation (year, month, day ranges)

4. Channel Isolation
   - Webhook → control channel
   - Stats → production channel
   - Trigger messages deleted after processing

```text

### SSH Security

```text

1. Key-Based Auth
   - No passwords, SSH key only
   - SSH_KEY_PATH configurable

2. Host Key Verification
   - Default: AutoAddPolicy (trusted VPS)
   - Strict: SSH_STRICT_HOST_KEY=true

3. Command Injection Prevention
   - Path sanitization (shlex.quote)
   - Parameterized SFTP

4. Timeouts
   - SSH connect: 10s
   - SFTP operations: 30s

```text

### Discord Command Security

```text

1. Channel Restrictions
   - Global bot_check() filter
   - Silent ignore for unauthorized channels

2. Permission System
   - Discord role checks
   - Whitelist (PermissionManagementCog)
   - Admin audit logging

3. Input Sanitization
   - Error message sanitization
   - Color code stripping
   - Embed field length limits (1024)

```yaml

---

## 9. Configuration Reference

### Critical Environment Variables

```bash
# Discord
DISCORD_BOT_TOKEN=<bot_token>
PRODUCTION_CHANNEL_ID=<stats_channel>
WEBHOOK_TRIGGER_CHANNEL_ID=<control_channel>
WEBHOOK_TRIGGER_WHITELIST=<webhook_id_1>,<webhook_id_2>

# SSH
SSH_ENABLED=true
SSH_HOST=<vps_hostname>
SSH_PORT=22
SSH_USER=<ssh_username>
SSH_KEY_PATH=~/.ssh/etlegacy_bot
REMOTE_STATS_PATH=/home/et/.etlegacy/legacy/gamestats

# Database
DATABASE_TYPE=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=<db_user>
POSTGRES_PASSWORD=<db_password>

# Automation
AUTOMATION_ENABLED=true
SESSION_GAP_MINUTES=60
SESSION_START_THRESHOLD=6
SESSION_END_THRESHOLD=2
SESSION_END_DELAY=300

# WebSocket (DEPRECATED - leave disabled)
WS_ENABLED=false
```yaml

---

## 10. Complete Flow Diagram

### Happy Path: Game Finishes → Discord Post

```python

┌─────────────────────────────────────────┐
│ 1. GAME SERVER (VPS)                    │
│ ET:Legacy finishes round                │
│   ↓                                     │
│ c0rnp0rn3.lua writes stats file         │
│   → /home/et/.etlegacy/legacy/gamestats│
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ 2. VPS NOTIFICATION                     │
│ stats_webhook_notify.py (watchdog)      │
│   ↓                                     │
│ Detects file (inotify)                  │
│   ↓                                     │
│ Wait 3s (file completion)               │
│   ↓                                     │
│ POST webhook → Discord control channel  │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ 3. BOT WEBHOOK HANDLER                  │
│ on_message() receives webhook           │
│   ↓                                     │
│ Security validation (ID, rate, filename)│
│   ↓                                     │
│ Launch_process_webhook_triggered_file()│
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ 4. FILE DOWNLOAD (SSH)                  │
│ 5-layer deduplication check             │
│   ↓                                     │
│ SSH + SFTP download                     │
│   → local_stats/<filename>              │
│   ↓                                     │
│ Wait 2s (settling)                      │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ 5. PARSING                              │
│ C0RNP0RN3StatsParser                    │
│   ↓                                     │
│ Parse map metadata                      │
│ Parse player stats (54 fields)          │
│ Parse weapon stats (27 weapons)         │
│ Calculate derived metrics               │
│   ↓                                     │
│ If R2: Calculate differential (R2-R1)   │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ 6. DATABASE IMPORT (PostgreSQL)         │
│ Transaction BEGIN                       │
│   ↓                                     │
│ Calculate gaming_session_id (60min gap) │
│   ↓                                     │
│ INSERT rounds, player_stats, weapons    │
│   ↓                                     │
│ UPDATE player_aliases                   │
│   ↓                                     │
│ Transaction COMMIT                      │
└─────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────┐
│ 7. DISCORD POSTING                      │
│ RoundPublisherService                   │
│   ↓                                     │
│ Fetch data from database (not parser)   │
│   ↓                                     │
│ Build rich embed (3-line per player)    │
│   ↓                                     │
│ Post to PRODUCTION stats channel        │
│   ↓                                     │
│ Delete trigger message (cleanup)        │
└─────────────────────────────────────────┘
                ↓
             [DONE]

```text

### Fallback: SSH Polling

```text

endstats_monitor (60s loop)
  ↓
Dead hours check (02:00-11:00 CET) → Skip
  ↓
Voice detection (6+ players?) → Active mode
  ↓
SSH list files
  ↓
For each new file:
  ├─ 5-layer dedup check
  ├─ Download via SSH
  ├─ Parse + Import
  └─ Post to Discord

```

---

## Why This Architecture?

### Webhook vs WebSocket

**Webhook (Current)**:

- ✅ Simpler (standard Discord feature)
- ✅ More reliable (no persistent connection)
- ✅ Easier to debug (HTTP request logs)
- ✅ No port forwarding needed
- ✅ Built-in retry logic (Discord)

**WebSocket (Deprecated)**:

- ❌ Complex (persistent connection)
- ❌ Requires port forwarding or reverse tunnel
- ❌ Connection drops require reconnection
- ❌ More points of failure

### Why Not Direct File Access?

Game server (VPS) and bot (local) are separate machines.
SSH is the secure bridge between them.

### Why 5-Layer Deduplication?

- Layer 1 (age): Prevents restart spam
- Layer 2 (memory): Fastest for recent checks
- Layer 3 (filesystem): Catches manual downloads
- Layer 4 (processed_files): Persistent tracking
- Layer 5 (rounds): Definitive truth

Each layer catches different edge cases.

### Why Post from Database Not Parser?

- Manual imports may be hours old
- Database is source of truth
- Ensures consistency with !stats commands
- Allows re-posting without re-parsing

---

## Troubleshooting Guide

### Stats Not Posting

1. Check webhook trigger:
   - Look in control channel for webhook messages
   - Verify webhook ID in WEBHOOK_TRIGGER_WHITELIST

2. Check SSH connection:
   - `!ssh_check` command
   - Verify SSH_KEY_PATH, SSH_HOST, SSH_PORT

3. Check deduplication:
   - File might be marked as processed
   - Check `processed_files` table

4. Check endstats_monitor:
   - `!automation_status` command
   - Look for SSH errors

### Duplicate Stats Posts

- Should not happen (5-layer deduplication)
- If it does: Check processed_files table
- Race condition between webhook and SSH polling?

### Missing Stats

- Check VPS: `ls /home/et/.etlegacy/legacy/gamestats/`
- Check local: `ls local_stats/`
- Compare counts
- Use manual import if needed

### Voice Session Not Starting

- Check GAMING_VOICE_CHANNELS config
- Verify AUTOMATION_ENABLED=true
- Need 6+ players (SESSION_START_THRESHOLD)
- Check `!automation_status`

---

## Maintenance Tasks

### Daily

- Monitor `!automation_status` for errors
- Check production channel for normal posting

### Weekly

- Review logs for SSH errors
- Check disk space (local_stats/, database)
- Verify processed_files count matches local_stats

### Monthly

- Backup database (`pg_dump`)
- Rotate logs
- Review performance metrics

---

**End of Documentation**
