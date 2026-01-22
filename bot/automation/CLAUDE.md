# Bot Automation Package - CLAUDE.md

## Overview

Automation components for the ET:Legacy Statistics Bot.
Handles SSH file monitoring, health checks, and scheduled tasks.

## Architecture

```python
Game Server (VPS)
    │
    │ SSH (every 60s)
    ▼
FileTracker (file_tracker.py)
    │
    │ New files detected
    ▼
endstats_monitor (ultimate_bot.py)
    │
    ├── Download file
    ├── Parse stats
    ├── Import to PostgreSQL
    └── Post to Discord
```python

## Module Reference

| Module | Purpose |
|--------|---------|
| `file_tracker.py` | Tracks processed files, deduplication |
| `ssh_handler.py` | SSH connection management |

### Services Subdirectory (bot/services/automation/)

| Module | Purpose |
|--------|---------|
| `database_maintenance.py` | Scheduled DB maintenance |
| `health_monitor.py` | System health checks |
| `metrics_logger.py` | Performance metrics |
| `ssh_monitor.py` | SSH monitoring service (DISABLED) |
| `ws_client.py` | WebSocket client for VPS notifications |

## Critical: Single System Design

**IMPORTANT**: Only `endstats_monitor` task loop handles SSH operations.
The `SSHMonitor` service is initialized but NOT auto-started.

### Why?

Previously, two systems competed:

1. SSHMonitor processed files first
2. Marked files as "processed" before Discord posting
3. Result: Files imported but never posted to Discord

### Current Flow (Fixed Dec 2025)

```python
# ultimate_bot.py - endstats_monitor task
@tasks.loop(seconds=60)
async def endstats_monitor():
    # 1. SSH check for new files
    # 2. Download new files
    # 3. Parse and import to database
    # 4. Post to Discord channel
    # All in one atomic flow
```python

## FileTracker (file_tracker.py)

Multi-layer deduplication system:

```python
# Deduplication layers (checked in order)
1. File age check (lookback window - default 7 days)
2. In-memory cache (processed_files set)
3. Local filesystem check
4. Database processed_files table
5. Rounds table (definitive source)
```text

### Lookback Window (Dec 2025 Fix)

```python
# Files from 7 days before bot startup are considered
# Prevents data loss from bot downtime
STARTUP_LOOKBACK_HOURS = 168  # 7 days
```python

## SSH Handler (ssh_handler.py)

Manages SSH connections to the game server VPS.

```python
# Configuration (.env)
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot

# Remote path
REMOTE_STATS_PATH=/home/et/.etlegacy/nitmod/stats/
```python

## Timeout Values (CRITICAL)

There's a mismatch that needs attention:

| Component | Value | Purpose |
|-----------|-------|---------|
| `community_stats_parser.py:384` | 30 min | R1-R2 matching window |
| `ultimate_bot.py:1636` | 30 min | Grace period |
| `config.py` | 60 min | Session gap threshold |

**Risk**: Edge cases at 45-minute mark may behave unexpectedly.

## Adding New Automation

1. Create task in `ultimate_bot.py` using `@tasks.loop()`
2. Start task in `on_ready()` event
3. Add error tracking with `bot.track_error()`
4. Log to `logs/` directory

```python
@tasks.loop(hours=24)
async def daily_cleanup():
    try:
        await cleanup_old_files()
        self.reset_error_tracking("daily_cleanup")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        await self.track_error("daily_cleanup", str(e))
```text

## Monitoring & Alerts

Use the admin notification system:

```python
await self.bot.alert_admins(
    "SSH Connection Failed",
    f"Could not connect to {host}:{port}\nError: {error}",
    severity="error"  # "info", "warning", "error", "critical"
)
```
