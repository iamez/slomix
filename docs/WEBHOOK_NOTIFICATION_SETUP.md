# Discord Webhook Stats Notification System

## Overview

This document describes the new webhook-based notification system that replaces the WebSocket approach for live stats posting.

**Why the change?**

- WebSocket server was unreliable (connection refused errors)
- Required open port on VPS (security concern)
- Complex connection management (reconnect loops)
- New approach: VPS posts directly to Discord, bot polls via SSH only

## Architecture

```sql
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────┐
│ ET:Legacy Game  │───▶│ stats_webhook_notify │───▶│   Discord   │
│    Server       │    │     (VPS script)     │    │   Webhook   │
└─────────────────┘    └──────────────────────┘    └─────────────┘
        │                                                 │
        │                                                 ▼
        │                                          ┌─────────────┐
        │                                          │   Discord   │
        │                                          │   Channel   │
        ▼                                          └─────────────┘
┌─────────────────┐                                       ▲
│  Stats Files    │                                       │
│ (.txt in stats/)│                                       │
└─────────────────┘                                       │
        │                                                 │
        ▼                                                 │
┌─────────────────┐    ┌──────────────────────┐          │
│  Bot (SSH Poll) │───▶│   PostgreSQL DB      │──────────┘
│  ultimate_bot   │    │   (stats storage)    │   Rich embeds
└─────────────────┘    └──────────────────────┘   from bot commands
```python

## Components

### 1. VPS Script: `stats_webhook_notify.py`

**Location:** `/home/et/scripts/stats_webhook_notify.py`

**Function:** Watches the stats directory for new files and sends Discord webhook notifications.

**Features:**

- Uses `watchdog` for filesystem monitoring
- Tracks processed files in state file (survives restarts)
- Validates stats file format before notifying
- Sends rich embeds with map/round info

### 2. Bot Changes

**File:** `bot/ultimate_bot.py`

**Changes:**

- WebSocket client disabled (`WS_ENABLED=false` in `.env`)
- SSH polling continues as primary mechanism
- No code changes needed for webhook reception (Discord handles it)

## Setup Instructions

### Step 1: Create Discord Webhook

1. Go to your Discord server
2. Navigate to Channel Settings → Integrations → Webhooks
3. Click "New Webhook"
4. Name it "ET:Legacy Stats" (or similar)
5. Copy the Webhook URL (looks like: `https://discord.com/api/webhooks/123.../abc...`)

### Step 2: Deploy VPS Script

```bash
# SSH to VPS
ssh et@puran.hehe.si -p 48101

# Create directories
mkdir -p /home/et/scripts/state

# Copy script (from local machine)
scp -P 48101 vps_scripts/stats_webhook_notify.py et@puran.hehe.si:/home/et/scripts/

# Install dependencies
pip3 install watchdog requests

# Test the script
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
export STATS_PATH="/home/et/server/legacy/stats"
python3 /home/et/scripts/stats_webhook_notify.py
```text

### Step 3: Create Systemd Service

```bash
sudo nano /etc/systemd/system/et-stats-webhook.service
```text

Contents:

```ini
[Unit]
Description=ET:Legacy Stats Webhook Notifier
After=network.target

[Service]
Type=simple
User=et
WorkingDirectory=/home/et/scripts
Environment="STATS_PATH=/home/et/server/legacy/stats"
Environment="DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
Environment="STATE_DIR=/home/et/scripts/state"
ExecStart=/usr/bin/python3 /home/et/scripts/stats_webhook_notify.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```text

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable et-stats-webhook
sudo systemctl start et-stats-webhook
sudo systemctl status et-stats-webhook
```sql

### Step 4: Update Bot Configuration

In `.env` on bot machine:

```bash
# WebSocket DISABLED
WS_ENABLED=false
#WS_HOST=puran.hehe.si
#WS_PORT=8765
```text

No bot restart needed if already running with WS disabled.

## How It Works

1. **Game ends round** → ET:Legacy writes stats file to `/home/et/server/legacy/stats/`

2. **Webhook script detects file** → `watchdog` triggers `on_created` event

3. **Script validates file** → Checks format: `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`

4. **Script sends webhook** → Posts to Discord with embed containing:
   - Filename
   - Map name
   - Round number
   - File size
   - Timestamp

5. **Discord displays notification** → Channel shows the embed immediately

6. **Bot polls SSH (parallel)** → Downloads file, imports to DB, posts detailed stats

## Troubleshooting

### Webhook Not Sending

```bash
# Check service status
sudo systemctl status et-stats-webhook

# Check logs
journalctl -u et-stats-webhook -f

# Test webhook manually
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"content":"Test message"}'
```text

### Files Not Detected

```bash
# Check if watchdog is monitoring correct path
ls -la /home/et/server/legacy/stats/

# Check state file
cat /home/et/scripts/state/processed_files.json
```text

### Permission Issues

```bash
# Ensure et user owns the scripts directory
sudo chown -R et:et /home/et/scripts/

# Check stats directory is readable
ls -la /home/et/server/legacy/stats/
```python

## Migration Notes

### Old System (WebSocket)

Files:

- `vps_scripts/ws_notify_server.py` - WebSocket server (deprecated)
- `bot/services/automation/ws_client.py` - WebSocket client

Config:

```bash
WS_ENABLED=true
WS_HOST=puran.hehe.si
WS_PORT=8765
```python

### New System (Webhook)

Files:

- `vps_scripts/stats_webhook_notify.py` - Webhook notifier

Config:

```bash
WS_ENABLED=false
# Webhook URL configured on VPS only
```

## Security

- **No open ports:** Webhook uses outbound HTTPS only
- **Discord rate limits:** Script includes delays to avoid hitting limits
- **State persistence:** Processed files tracked to prevent duplicates
- **Validation:** Only valid stats files trigger notifications
