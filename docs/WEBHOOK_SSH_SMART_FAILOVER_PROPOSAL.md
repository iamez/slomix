# Webhook/SSH Smart Failover System - Implementation Proposal

> **Status**: PROPOSAL (Not Implemented)
> **Created**: 2026-01-15
> **Author**: Claude Code Session
> **Priority**: Optimization (non-critical)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture](#current-architecture)
3. [Problem Statement](#problem-statement)
4. [Proposed Solution](#proposed-solution)
5. [Detailed Implementation Plan](#detailed-implementation-plan)
6. [Code Changes Required](#code-changes-required)
7. [Edge Cases & Safety](#edge-cases--safety)
8. [Configuration Options](#configuration-options)
9. [Testing Plan](#testing-plan)
10. [Rollback Plan](#rollback-plan)
11. [Future Enhancements](#future-enhancements)

---

## Executive Summary

### What We Have Now

Two redundant systems for detecting and processing game stats files:

| System | Method | Speed | Resource Usage |
|--------|--------|-------|----------------|
| **Webhook** | VPS pushes notification to Discord | Instant (~1-2s) | Minimal |
| **SSH Polling** | Bot polls server every 60s | Up to 60s delay | SSH connections every minute |

Both systems run **simultaneously**, causing unnecessary resource usage when webhooks are healthy.

### What We Want

A **smart failover system** where:
- Webhook is the **primary** method (faster, less overhead)
- SSH polling is **backup** (only activates when webhook fails)
- Automatic switching based on health metrics

### Expected Benefits

- **Reduced server load**: No unnecessary SSH connections every 60 seconds
- **Faster processing**: Webhook is instant vs 60s polling intervals
- **Maintained reliability**: SSH kicks in automatically if webhook fails
- **Better logging**: Clear visibility into which system is active

---

## Current Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GAME SERVER (VPS)                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ET:Legacy Server writes stats files to:                     │   │
│  │  /home/et/.etlegacy/nitmod/stats/                           │   │
│  │                                                              │   │
│  │  Files created:                                              │   │
│  │  - 2026-01-15-222119-te_escape2-round-1.txt     (main)      │   │
│  │  - 2026-01-15-222117-te_escape2-round-1-endstats.txt        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  stats_webhook_notify.py (inotify watcher)                   │   │
│  │  - Watches for new .txt files                                │   │
│  │  - Sends Discord webhook on file creation                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            │                                      │
            ▼ WEBHOOK PATH                         ▼ SSH PATH
┌───────────────────────────┐          ┌───────────────────────────┐
│  Discord Webhook Message  │          │  SSH Polling (every 60s)  │
│  Posted to control channel│          │  Bot connects via SFTP    │
│  with filename in message │          │  Lists remote directory   │
└───────────────────────────┘          └───────────────────────────┘
            │                                      │
            ▼                                      ▼
┌───────────────────────────────────────────────────────────────────┐
│                         DISCORD BOT                                │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  on_message() handler (line 2056)                            │  │
│  │  - Intercepts webhook messages                               │  │
│  │  - Validates webhook ID against whitelist                    │  │
│  │  - Extracts filename from message                            │  │
│  │  - Routes to _handle_webhook_trigger()                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  endstats_monitor() task loop (line 1565)                    │  │
│  │  - Runs every 60 seconds (active) / 10 min (idle)            │  │
│  │  - Connects via SSH/SFTP                                     │  │
│  │  - Lists files, checks against FileTracker                   │  │
│  │  - Downloads and processes new files                         │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  FileTracker (shared instance)                               │  │
│  │  - 4-layer deduplication                                     │  │
│  │  - In-memory set + DB table + local file check               │  │
│  │  - Prevents duplicate processing from both paths             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  process_gamestats_file() / _process_endstats_file()         │  │
│  │  - Parses stats file                                         │  │
│  │  - Imports to database                                       │  │
│  │  - Posts embed to Discord                                    │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

### Webhook System Details

**Location**: `bot/ultimate_bot.py`

| Component | Lines | Function |
|-----------|-------|----------|
| Message handler | 2056-2062 | `on_message()` - intercepts webhook messages |
| Webhook processor | 2219-2296 | `_handle_webhook_trigger()` - validates & routes |
| Stats processor | 2298-2387 | `_process_webhook_triggered_file()` |
| Endstats processor | 2528-2710 | `_process_webhook_triggered_endstats()` |
| Filename validation | 2105-2217 | `_validate_stats_filename()` / `_validate_endstats_filename()` |
| Rate limiting | 2079-2103 | Max 5 triggers per 60 seconds per webhook |

**Webhook Flow**:
```
1. VPS detects new file via inotify
2. VPS sends webhook to Discord control channel
3. Bot's on_message() intercepts (checks webhook ID whitelist)
4. Extracts filename from message content (in backticks)
5. Validates filename format and security
6. Downloads file via SSH/SFTP
7. Routes to appropriate parser (stats vs endstats)
8. Imports to database
9. Posts embed to stats channel
```

**Security Features**:
- Webhook ID whitelist (`WEBHOOK_TRIGGER_WHITELIST`)
- Username validation (`WEBHOOK_TRIGGER_USERNAME`)
- Rate limiting (5 per 60s per webhook)
- Filename validation (path traversal, null bytes, format)

### SSH Polling System Details

**Location**: `bot/ultimate_bot.py`

| Component | Lines | Function |
|-----------|-------|----------|
| Monitor task | 1565-1792 | `endstats_monitor()` - main polling loop |
| SSH check | 1709-1778 | Actual file listing and download |
| Endstats processor | 2388-2526 | `_process_endstats_file()` |
| SSH handler | `bot/automation/ssh_handler.py` | SFTP operations |

**Polling Intervals**:
```python
# Current intervals in endstats_monitor()
DEAD_HOURS = (2, 11)        # 02:00-11:00 CET - no polling
ACTIVE_INTERVAL = 60        # seconds (6+ players in voice)
GRACE_PERIOD = 30 * 60      # 30 minutes after last file
IDLE_INTERVAL = 10 * 60     # 10 minutes (was 6 hours before Dec 2025)
```

**SSH Flow**:
```
1. Task loop triggers every 60 seconds
2. Check if in dead hours (02:00-11:00) → skip
3. Check voice channel player count
4. Determine polling mode (active/idle/grace)
5. Connect via SSH/SFTP to game server
6. List files in remote stats directory
7. For each file, check FileTracker.should_process_file()
8. Download new files
9. Route to appropriate parser
10. Import to database
11. Post embed to Discord
```

### File Tracker (Deduplication)

**Location**: `bot/automation/file_tracker.py`

Both webhook and SSH use the **same FileTracker instance**, preventing duplicate processing.

**4-Layer Deduplication**:
```python
def should_process_file(filename):
    # Layer 1: File age check (7-day lookback window)
    # Layer 2: In-memory cache (self.processed_files set)
    # Layer 3: Local file existence check
    # Layer 4: Database processed_files table
    # Layer 5: rounds table lookup (definitive)
```

**Critical**: Because both systems use the same FileTracker, there's **no risk of duplicate processing** even when both are active.

---

## Problem Statement

### Current Waste

When webhooks are working correctly (which is most of the time):

| Resource | Current Usage | With Smart Failover |
|----------|---------------|---------------------|
| SSH connections | ~60/hour (active) | 0 (webhook healthy) |
| SFTP directory listings | ~60/hour | 0 |
| Network bandwidth | Constant polling | On-demand only |
| Server CPU | SSH handshakes | Minimal |

### Observed Behavior (from logs)

```
21:21:21 - Webhook receives endstats → processes
21:21:24 - Webhook receives main stats → processes
21:21:39 - SSH polls → finds nothing new (wasted connection)
21:21:45 - SSH polls → finds endstats again (already processed)
21:22:39 - SSH polls → finds nothing new (wasted connection)
... continues every 60 seconds ...
```

### Why Both Exist

Historical reasons:
1. **SSH polling was original** - reliable but slow
2. **Webhook added later** - faster but depends on VPS service
3. **Both kept for redundancy** - "belt and suspenders" approach

### The Risk of Disabling SSH Completely

If we permanently disable SSH polling:
- VPS webhook service crashes → **no stats processing**
- VPS server reboots → **missed files until service restarts**
- Network issues to Discord → **webhook delivery fails**

**Solution**: Smart failover maintains redundancy while eliminating waste.

---

## Proposed Solution

### Smart Failover Logic

```
┌─────────────────────────────────────────────────────────────────┐
│                    SMART FAILOVER STATE MACHINE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    2 successes    ┌──────────────┐            │
│  │              │ ────────────────► │              │            │
│  │  SSH ENABLED │                   │ SSH DISABLED │            │
│  │   (startup)  │ ◄──────────────── │  (webhook    │            │
│  │              │    1 failure OR   │   healthy)   │            │
│  └──────────────┘    heartbeat      └──────────────┘            │
│                      timeout                                     │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  COUNTERS:                                                       │
│  - webhook_success_count: consecutive webhook successes          │
│  - webhook_failure_count: consecutive webhook failures           │
│  - last_webhook_success: timestamp of last successful webhook    │
│                                                                  │
│  THRESHOLDS:                                                     │
│  - SUCCESS_THRESHOLD = 2 (disable SSH after 2 webhook successes) │
│  - FAILURE_THRESHOLD = 1 (re-enable SSH after 1 webhook failure) │
│  - HEARTBEAT_TIMEOUT = 15 min (re-enable if no webhook activity) │
└─────────────────────────────────────────────────────────────────┘
```

### State Transitions

| Current State | Event | New State | Action |
|---------------|-------|-----------|--------|
| SSH Enabled | Webhook success #1 | SSH Enabled | Increment counter |
| SSH Enabled | Webhook success #2 | **SSH Disabled** | Log state change |
| SSH Disabled | Webhook success | SSH Disabled | Update timestamp |
| SSH Disabled | Webhook failure | **SSH Enabled** | Log + alert |
| SSH Disabled | 15 min no activity | **SSH Enabled** | Heartbeat failsafe |
| SSH Enabled | Webhook failure | SSH Enabled | Already enabled |

### Why These Thresholds?

**SUCCESS_THRESHOLD = 2**:
- Single success could be fluke (one file happened to work)
- Two consecutive successes = pattern of reliability
- Not too high (don't wait forever to optimize)

**FAILURE_THRESHOLD = 1**:
- Immediate failover on any failure
- Don't wait for multiple failures (could miss files)
- Better safe than sorry for data integrity

**HEARTBEAT_TIMEOUT = 15 minutes**:
- During active gaming, files come every 5-10 minutes
- 15 minutes of silence during active session = something wrong
- Re-enables SSH as precaution even without explicit failure

---

## Detailed Implementation Plan

### Phase 1: Add State Tracking Variables

**File**: `bot/ultimate_bot.py`

**Location**: `__init__` method (around line 180-220)

```python
# Add after existing initialization (around line 220)

# =============================================================================
# WEBHOOK/SSH SMART FAILOVER STATE
# =============================================================================
# These variables track webhook health to enable smart failover between
# webhook-triggered processing (primary) and SSH polling (backup).
#
# The goal: Disable SSH polling when webhooks are healthy to save resources,
# but automatically re-enable SSH if webhooks start failing.
# =============================================================================

self.webhook_success_count: int = 0          # Consecutive webhook successes
self.webhook_failure_count: int = 0          # Consecutive webhook failures
self.last_webhook_success: Optional[datetime] = None  # Timestamp of last success
self.ssh_polling_enabled: bool = True        # SSH polling state (starts enabled)

# Thresholds (could move to config.py later)
self.WEBHOOK_SUCCESS_THRESHOLD: int = 2      # Disable SSH after N successes
self.WEBHOOK_FAILURE_THRESHOLD: int = 1      # Re-enable SSH after N failures
self.WEBHOOK_HEARTBEAT_TIMEOUT: int = 900    # 15 minutes in seconds
```

### Phase 2: Create State Management Methods

**File**: `bot/ultimate_bot.py`

**Location**: Add new methods (suggest around line 2200, before `_handle_webhook_trigger`)

```python
# =============================================================================
# WEBHOOK/SSH SMART FAILOVER METHODS
# =============================================================================

def _record_webhook_success(self) -> None:
    """
    Record a successful webhook-triggered file processing.

    After WEBHOOK_SUCCESS_THRESHOLD consecutive successes, SSH polling
    is disabled to save resources. The webhook system has proven reliable.
    """
    self.webhook_success_count += 1
    self.webhook_failure_count = 0  # Reset failure counter
    self.last_webhook_success = datetime.now()

    if self.ssh_polling_enabled and self.webhook_success_count >= self.WEBHOOK_SUCCESS_THRESHOLD:
        self.ssh_polling_enabled = False
        logger.info(
            f"🔄 FAILOVER: Webhook healthy ({self.webhook_success_count} successes) "
            f"- SSH polling DISABLED to save resources"
        )
        # Optional: Send admin notification
        # asyncio.create_task(self.alert_admins(
        #     "SSH polling disabled - webhook system healthy",
        #     level="info"
        # ))

def _record_webhook_failure(self, reason: str) -> None:
    """
    Record a webhook-triggered file processing failure.

    After WEBHOOK_FAILURE_THRESHOLD failures, SSH polling is re-enabled
    as a fallback to ensure we don't miss any stats files.

    Args:
        reason: Description of why the webhook processing failed
    """
    self.webhook_failure_count += 1
    self.webhook_success_count = 0  # Reset success counter

    if not self.ssh_polling_enabled and self.webhook_failure_count >= self.WEBHOOK_FAILURE_THRESHOLD:
        self.ssh_polling_enabled = True
        logger.warning(
            f"⚠️ FAILOVER: Webhook failed ({reason}) "
            f"- SSH polling RE-ENABLED as backup"
        )
        # Optional: Send admin alert for visibility
        # asyncio.create_task(self.alert_admins(
        #     f"SSH polling re-enabled - webhook failure: {reason}",
        #     level="warning"
        # ))

def _check_webhook_heartbeat(self) -> None:
    """
    Check if webhook system has gone silent for too long.

    Called from SSH polling loop. If no webhook activity for
    WEBHOOK_HEARTBEAT_TIMEOUT seconds during what should be an
    active gaming session, re-enable SSH polling as precaution.

    This catches cases where webhook service dies silently without
    explicit errors.
    """
    if self.ssh_polling_enabled:
        return  # Already enabled, nothing to do

    if self.last_webhook_success is None:
        return  # No baseline yet

    elapsed = (datetime.now() - self.last_webhook_success).total_seconds()

    # Only trigger during active sessions (players in voice)
    voice_players = self._count_voice_players()  # Existing method

    if voice_players >= 4 and elapsed > self.WEBHOOK_HEARTBEAT_TIMEOUT:
        self.ssh_polling_enabled = True
        logger.warning(
            f"⚠️ FAILOVER: No webhook activity for {elapsed/60:.1f} minutes "
            f"during active session ({voice_players} players) "
            f"- SSH polling RE-ENABLED as precaution"
        )

def get_failover_status(self) -> dict:
    """
    Get current failover system status for diagnostics.

    Returns:
        dict with current state information
    """
    return {
        "ssh_polling_enabled": self.ssh_polling_enabled,
        "webhook_success_count": self.webhook_success_count,
        "webhook_failure_count": self.webhook_failure_count,
        "last_webhook_success": self.last_webhook_success.isoformat() if self.last_webhook_success else None,
        "heartbeat_timeout_seconds": self.WEBHOOK_HEARTBEAT_TIMEOUT,
        "success_threshold": self.WEBHOOK_SUCCESS_THRESHOLD,
        "failure_threshold": self.WEBHOOK_FAILURE_THRESHOLD,
    }
```

### Phase 3: Integrate into Webhook Handler

**File**: `bot/ultimate_bot.py`

**Location**: `_process_webhook_triggered_file()` (around line 2298-2387)

**Changes needed**:

```python
async def _process_webhook_triggered_file(self, filename: str) -> bool:
    """Process a webhook-triggered stats file."""
    try:
        # ... existing download and processing code ...

        # At the END of successful processing (before return True):
        # ADD THIS:
        self._record_webhook_success()
        logger.info(f"✅ Successfully processed and posted: {filename}")
        return True

    except Exception as e:
        # In the exception handler:
        # ADD THIS:
        self._record_webhook_failure(f"Exception: {str(e)[:100]}")
        logger.error(f"❌ Webhook processing failed for {filename}: {e}")
        return False
```

**Same changes for**: `_process_webhook_triggered_endstats()` (around line 2528-2710)

### Phase 4: Integrate into SSH Polling Loop

**File**: `bot/ultimate_bot.py`

**Location**: `endstats_monitor()` task (around line 1565)

**Changes needed**:

```python
@tasks.loop(seconds=60)
async def endstats_monitor(self):
    """SSH polling loop with smart failover support."""

    # ADD AT THE START OF THE METHOD:
    # =================================================================
    # Smart Failover Check
    # =================================================================
    if not self.ssh_polling_enabled:
        # Check heartbeat timeout (webhook might have died silently)
        self._check_webhook_heartbeat()

        if not self.ssh_polling_enabled:
            # Still disabled, skip this polling cycle
            logger.debug("🔄 SSH polling skipped (webhook system healthy)")
            return
    # =================================================================

    # ... rest of existing SSH polling code ...
```

### Phase 5: Add Diagnostic Command

**File**: `bot/cogs/admin_cog.py` (or create new `diagnostics_cog.py`)

```python
@commands.command(name='failover-status', aliases=['failover', 'webhook-status'])
@commands.has_permissions(administrator=True)
async def failover_status(self, ctx):
    """Show current webhook/SSH failover system status."""
    status = self.bot.get_failover_status()

    embed = discord.Embed(
        title="🔄 Failover System Status",
        color=discord.Color.green() if not status['ssh_polling_enabled'] else discord.Color.orange()
    )

    # Current mode
    mode = "WEBHOOK (primary)" if not status['ssh_polling_enabled'] else "SSH POLLING (backup active)"
    embed.add_field(name="Current Mode", value=mode, inline=False)

    # Stats
    embed.add_field(name="Webhook Successes", value=status['webhook_success_count'], inline=True)
    embed.add_field(name="Webhook Failures", value=status['webhook_failure_count'], inline=True)
    embed.add_field(name="SSH Enabled", value="Yes" if status['ssh_polling_enabled'] else "No", inline=True)

    # Last activity
    if status['last_webhook_success']:
        embed.add_field(name="Last Webhook Success", value=status['last_webhook_success'], inline=False)

    # Thresholds
    embed.add_field(
        name="Thresholds",
        value=f"Disable SSH after: {status['success_threshold']} successes\n"
              f"Re-enable SSH after: {status['failure_threshold']} failures\n"
              f"Heartbeat timeout: {status['heartbeat_timeout_seconds']/60:.0f} minutes",
        inline=False
    )

    await ctx.send(embed=embed)
```

---

## Code Changes Required

### Summary of Files to Modify

| File | Changes | Lines (approx) |
|------|---------|----------------|
| `bot/ultimate_bot.py` | Add state variables | ~220 |
| `bot/ultimate_bot.py` | Add failover methods | ~2200 (new section) |
| `bot/ultimate_bot.py` | Update `_process_webhook_triggered_file()` | ~2380 |
| `bot/ultimate_bot.py` | Update `_process_webhook_triggered_endstats()` | ~2700 |
| `bot/ultimate_bot.py` | Update `endstats_monitor()` | ~1570 |
| `bot/cogs/admin_cog.py` | Add diagnostic command | New command |
| `bot/config.py` | (Optional) Add thresholds to config | New section |

### Estimated Code Addition

- **New code**: ~150 lines
- **Modified code**: ~20 lines
- **Total impact**: Minimal, well-isolated changes

---

## Edge Cases & Safety

### Edge Case 1: Bot Restart During Active Session

**Scenario**: Bot restarts while players are gaming, webhook service is actually healthy.

**Current behavior**: SSH would poll immediately on restart.

**With failover**: SSH starts enabled (correct), processes any missed files, then disables after 2 webhook successes.

**Safety**: No issue - SSH being enabled on restart is the safe default.

### Edge Case 2: Rapid File Creation

**Scenario**: Two rounds finish within seconds (rare but possible).

**Current behavior**: Webhook sends both notifications, both get processed.

**With failover**: Same behavior - each success increments counter, no issues.

**Safety**: No issue - counter just goes to 2 faster.

### Edge Case 3: Webhook Service Crashes Mid-Session

**Scenario**: VPS webhook notifier crashes, no more webhook messages.

**Current behavior**: SSH would catch files on next poll.

**With failover**:
1. No webhook activity for 15 minutes
2. Heartbeat check triggers
3. SSH re-enabled
4. Files get processed via SSH

**Safety**: Handled by heartbeat timeout.

### Edge Case 4: Discord Webhook Delivery Failure

**Scenario**: Discord has issues, webhook messages don't arrive.

**Current behavior**: SSH catches files.

**With failover**: Same - no webhook messages = no successes = SSH stays enabled.

**Safety**: SSH never gets disabled if webhooks aren't actually working.

### Edge Case 5: Partial Webhook Failure

**Scenario**: Webhook message arrives but file download fails.

**Current behavior**: Error logged, SSH would catch file.

**With failover**:
1. `_record_webhook_failure()` called
2. SSH re-enabled immediately
3. SSH catches the file

**Safety**: Immediate failover on any failure.

### Edge Case 6: Endstats Before Main Stats

**Scenario**: Endstats webhook arrives before main stats (timestamp difference).

**Current behavior**: Endstats fails to link, SSH retry catches it later.

**With failover**:
1. Endstats webhook fails to link → `_record_webhook_failure()` called?

**Decision needed**: Should "round not found" count as failure?
- **Option A**: Yes - conservative, keeps SSH enabled longer
- **Option B**: No - it's not a webhook failure, just timing
- **Recommendation**: Option B - only count actual processing failures

```python
# In _process_webhook_triggered_endstats():
if not round_result:
    # This is NOT a webhook failure - just timing issue
    # Don't call _record_webhook_failure()
    logger.warning(f"⏳ Round not found yet for {filename}")
    return False  # But still return False

# Only record failure for actual exceptions
except Exception as e:
    self._record_webhook_failure(f"Endstats error: {str(e)[:50]}")
```

### Edge Case 7: Dead Hours Transition

**Scenario**: Bot enters dead hours (02:00-11:00 CET) with SSH disabled.

**Current behavior**: SSH polling stops during dead hours anyway.

**With failover**: Same - SSH disabled state persists but polling wouldn't happen anyway.

**Safety**: No issue - state preserved, resumes correctly after dead hours.

---

## Configuration Options

### Recommended Defaults

```python
# bot/config.py

# =============================================================================
# WEBHOOK/SSH SMART FAILOVER CONFIGURATION
# =============================================================================

# Number of consecutive webhook successes before disabling SSH polling
# Lower = faster optimization, Higher = more conservative
WEBHOOK_SUCCESS_THRESHOLD = int(os.getenv('WEBHOOK_SUCCESS_THRESHOLD', '2'))

# Number of consecutive webhook failures before re-enabling SSH polling
# Should almost always be 1 for immediate failover
WEBHOOK_FAILURE_THRESHOLD = int(os.getenv('WEBHOOK_FAILURE_THRESHOLD', '1'))

# Seconds of webhook inactivity during active session before re-enabling SSH
# Should be longer than typical round duration (10-15 minutes)
WEBHOOK_HEARTBEAT_TIMEOUT = int(os.getenv('WEBHOOK_HEARTBEAT_TIMEOUT', '900'))

# Minimum voice channel players to consider "active session" for heartbeat
WEBHOOK_HEARTBEAT_MIN_PLAYERS = int(os.getenv('WEBHOOK_HEARTBEAT_MIN_PLAYERS', '4'))

# Enable/disable the smart failover system entirely
# Set to false to always use both webhook and SSH (current behavior)
SMART_FAILOVER_ENABLED = os.getenv('SMART_FAILOVER_ENABLED', 'true').lower() == 'true'
```

### Environment Variables

```bash
# .env additions

# Smart Failover (optional - defaults are sensible)
WEBHOOK_SUCCESS_THRESHOLD=2      # Disable SSH after N webhook successes
WEBHOOK_FAILURE_THRESHOLD=1      # Re-enable SSH after N failures
WEBHOOK_HEARTBEAT_TIMEOUT=900    # 15 minutes
SMART_FAILOVER_ENABLED=true      # Set to false to disable feature
```

---

## Testing Plan

### Pre-Implementation Testing

1. **Verify current webhook reliability**:
   - Monitor logs for 1 week
   - Count webhook successes vs failures
   - Identify any patterns in failures

2. **Verify SSH polling catches webhook failures**:
   - Temporarily stop VPS webhook service
   - Confirm SSH catches files within 60 seconds

### Post-Implementation Testing

#### Test 1: Normal Operation

```
Steps:
1. Start bot with SSH enabled (default)
2. Play 2 rounds
3. Verify webhook processes both
4. Verify SSH disabled after round 2
5. Play round 3
6. Verify webhook processes it (SSH still disabled)

Expected logs:
Round 1: "✅ Successfully processed" + counter=1
Round 2: "✅ Successfully processed" + "SSH polling DISABLED"
Round 3: "✅ Successfully processed" (SSH skipped in logs)
```

#### Test 2: Webhook Failure Recovery

```
Steps:
1. Start with webhook healthy (SSH disabled)
2. Stop VPS webhook service
3. Play a round
4. Verify no webhook message
5. Wait for heartbeat timeout (15 min) OR manually trigger failure
6. Verify SSH re-enables and catches file

Expected logs:
"⚠️ FAILOVER: ... SSH polling RE-ENABLED"
"📥 NEW FILE DETECTED" (via SSH)
```

#### Test 3: Immediate Failover

```
Steps:
1. Start with webhook healthy (SSH disabled)
2. Cause webhook processing failure (e.g., corrupt file)
3. Verify SSH immediately re-enabled

Expected logs:
"❌ Webhook processing failed"
"⚠️ FAILOVER: Webhook failed - SSH polling RE-ENABLED"
```

#### Test 4: Bot Restart

```
Steps:
1. Restart bot during active session
2. Verify SSH starts enabled
3. Verify webhook processes next round
4. Verify SSH disables after 2 successes

Expected: Same as Test 1
```

#### Test 5: Diagnostic Command

```
Steps:
1. Run !failover-status
2. Verify all fields populated correctly
3. Verify state matches actual behavior
```

### Monitoring After Deployment

Add metrics logging for long-term monitoring:

```python
# Weekly stats (could add to existing metrics)
logger.info(f"📊 FAILOVER WEEKLY: "
    f"SSH disabled {hours_disabled}h, "
    f"Webhook successes: {total_successes}, "
    f"Failovers triggered: {failover_count}")
```

---

## Rollback Plan

### Immediate Rollback

If issues are discovered after deployment:

```python
# Option 1: Disable via environment variable
SMART_FAILOVER_ENABLED=false

# Option 2: Force SSH always enabled
# In ultimate_bot.py, change:
self.ssh_polling_enabled: bool = True  # Force always true

# Option 3: Comment out the check in endstats_monitor()
# if not self.ssh_polling_enabled:
#     ...
#     return
```

### Graceful Rollback

1. Set `SMART_FAILOVER_ENABLED=false` in `.env`
2. Restart bot
3. System reverts to current behavior (both webhook + SSH active)
4. Investigate issues
5. Fix and re-enable

### Signs That Rollback Is Needed

- Files being missed (not processed at all)
- Significant delays in stats posting
- SSH re-enabling too frequently (webhook unreliable)
- Errors in failover state management

---

## Future Enhancements

### Enhancement 1: Metrics Dashboard

Add failover metrics to existing monitoring:

```python
# Track over time:
- Total webhook successes/failures
- Time spent in each state (SSH enabled vs disabled)
- Failover triggers per day/week
- Average time to failover recovery
```

### Enhancement 2: Configurable Per-File-Type

Different thresholds for stats vs endstats:

```python
# Endstats are less critical, could be more aggressive
WEBHOOK_SUCCESS_THRESHOLD_STATS = 2
WEBHOOK_SUCCESS_THRESHOLD_ENDSTATS = 1
```

### Enhancement 3: Gradual SSH Reduction

Instead of binary on/off, gradually reduce SSH polling frequency:

```
Webhook healthy → SSH every 5 minutes (instead of off)
Webhook very healthy (10+ successes) → SSH every 15 minutes
Webhook failure → SSH back to every 60 seconds
```

### Enhancement 4: Health Check Endpoint

Add `/health` endpoint for external monitoring:

```python
@app.route('/health')
def health():
    return {
        "status": "healthy",
        "webhook_mode": not bot.ssh_polling_enabled,
        "last_file_processed": bot.last_processed_timestamp,
        "failover_state": bot.get_failover_status()
    }
```

### Enhancement 5: Alert on Prolonged SSH Mode

If SSH stays enabled for too long, alert admins:

```python
# If SSH has been enabled for 1 hour during active session
# Something is wrong with webhook system
if ssh_enabled_duration > 3600 and voice_players >= 4:
    await self.alert_admins(
        "⚠️ SSH polling active for 1+ hour - check webhook service",
        level="warning"
    )
```

---

## Appendix: Current File Locations Reference

### Webhook System

| File | Purpose |
|------|---------|
| `bot/ultimate_bot.py:2056` | `on_message()` webhook intercept |
| `bot/ultimate_bot.py:2219` | `_handle_webhook_trigger()` |
| `bot/ultimate_bot.py:2298` | `_process_webhook_triggered_file()` |
| `bot/ultimate_bot.py:2528` | `_process_webhook_triggered_endstats()` |
| `bot/ultimate_bot.py:2105` | `_validate_stats_filename()` |
| `bot/ultimate_bot.py:2162` | `_validate_endstats_filename()` |
| `vps_scripts/stats_webhook_notify.py` | VPS-side file watcher |

### SSH System

| File | Purpose |
|------|---------|
| `bot/ultimate_bot.py:1565` | `endstats_monitor()` task loop |
| `bot/ultimate_bot.py:2388` | `_process_endstats_file()` |
| `bot/automation/ssh_handler.py` | SSH/SFTP operations |
| `bot/automation/file_tracker.py` | Deduplication logic |

### Configuration

| File | Purpose |
|------|---------|
| `bot/config.py:197-226` | Webhook & SSH config |
| `.env` | Environment variables |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-15 | Initial proposal created |

---

*End of Proposal Document*
