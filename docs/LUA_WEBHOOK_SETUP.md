# Lua Stats Webhook Setup Guide

Real-time round notifications from ET:Legacy game server to Discord bot.

**Current Version:** v1.3.0

## Overview

This feature allows the game server to instantly notify the bot when rounds complete, providing:
- **Instant notifications** (~1-3 seconds vs 60-second SSH polling)
- **Accurate timing on surrenders** (fixes the surrender duration bug)
- **Pause tracking** with individual pause timestamps (v1.3.0)
- **Warmup duration tracking** (v1.2.0+)
- **Winner/team detection** from game engine data
- **Timing legend** explaining Playtime vs Warmup vs Wall-clock (v1.3.0)

## Architecture

```
Game Server (Lua) → POST to Discord Webhook → Bot sees message → SSH fetch → Process
```

The bot's LAN machine remains outbound-only (no ports exposed). Discord acts as the relay.

## Prerequisites

- ET:Legacy game server with Lua support
- Discord webhook in your control channel
- Existing SSH-based stats monitoring (as fallback)

## Setup Steps

### 1. Database Migrations (One-Time)

Run all migrations in order:

```bash
cd /home/samba/share/slomix_discord

# Core timing columns
psql -d etlegacy -f tools/migrations/001_add_timing_metadata_columns.sql

# Lua round teams table (for webhook data)
psql -d etlegacy -f tools/migrations/002_add_lua_round_teams_table.sql

# Warmup tracking (v1.2.0+)
psql -d etlegacy -f tools/migrations/003_add_warmup_columns.sql

# Pause events (v1.3.0+)
psql -d etlegacy -f tools/migrations/004_add_pause_events.sql
```

**Migrations explained:**
| Migration | Purpose |
|-----------|---------|
| 001 | Timing columns on `rounds` table |
| 002 | Create `lua_round_teams` table for webhook data |
| 003 | Add `lua_warmup_seconds`, `lua_warmup_start_unix` columns |
| 004 | Add `lua_pause_events` JSONB column for pause timestamps |

### 2. Create Discord Webhook

1. Go to your **control channel** (same channel used for existing webhook triggers)
2. Click the gear icon → Integrations → Webhooks → New Webhook
3. Name it "ET:Legacy Stats Lua" (or similar)
4. Copy the webhook URL (format: `https://discord.com/api/webhooks/ID/TOKEN`)
5. **Add the webhook ID** to your `.env` file's `WEBHOOK_TRIGGER_WHITELIST`

### 3. Install Lua Script on Game Server

1. Copy the Lua script to your game server:
   ```bash
   scp vps_scripts/stats_discord_webhook.lua user@gameserver:/path/to/etlegacy/luascripts/
   ```

2. Edit the script and configure the webhook URL:
   ```lua
   local configuration = {
       discord_webhook_url = "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN",
       enabled = true,
       debug = false,
       send_delay_seconds = 3
   }
   ```

3. Add the script to your server's Lua loading:
   - In `server.cfg`: `set lua_modules "stats_discord_webhook"`
   - Or in `lua_modules.cfg` if you use one

4. Restart the game server

### 4. Verify Setup

1. Start a test round on your game server
2. Complete the round (or surrender)
3. Check your Discord control channel - you should see an embed like:
   ```
   Round Complete: supply R1

   **Timing Legend:**
   • Playtime = actual gameplay (pauses excluded)
   • Warmup = waiting before round
   • Wall-clock = WarmupStart→RoundEnd

   Lua_Playtime: 847 sec
   Lua_Warmup: 45 sec
   Lua_Pauses: 0 (0 sec)
   Lua_EndReason: time_expired
   Lua_RoundStart: 1737830400
   Lua_RoundEnd: 1737831247
   Lua_WarmupStart: 1737830355
   Lua_WarmupEnd: 1737830400
   ```
4. The bot should then fetch the stats file and post to your stats channel

**v1.3.0 Webhook Fields:**
| Field | Description |
|-------|-------------|
| `Lua_Playtime` | Actual gameplay time (pauses excluded) |
| `Lua_Warmup` | Pre-round warmup duration |
| `Lua_Pauses` | Count and total duration |
| `Lua_Pauses_JSON` | Detailed pause timestamps (if pauses occurred) |
| `Lua_WarmupStart` | When warmup began |
| `Lua_WarmupEnd` | When warmup ended (= round start) |
| `Lua_RoundStart` | When gameplay began |
| `Lua_RoundEnd` | When round ended |
| `Lua_EndReason` | objective/surrender/time_expired |

## Troubleshooting

### Webhook not appearing in Discord
- Check the Lua script has the correct webhook URL
- Check server console for `[stats_discord_webhook]` messages
- Ensure `curl` is available on the game server
- Enable debug mode in the Lua script: `debug = true`

### Bot not processing the webhook
- Check the webhook ID is in `WEBHOOK_TRIGGER_WHITELIST`
- Check bot logs for "STATS_READY webhook" messages
- Verify the webhook is in `WEBHOOK_TRIGGER_CHANNEL_ID` channel

### Timing data not being saved
- Run the database migration
- Check bot logs for "Applied Lua metadata" messages
- The bot gracefully handles missing columns (logs warning, continues)

## How It Works

### Gamestate Tracking

The Lua script monitors ET:Legacy's gamestate cvar:
- `GS_WARMUP` (0) - Warmup period
- `GS_WARMUP_COUNTDOWN` (1) - Countdown before match
- `GS_PLAYING` (2) - Active gameplay
- `GS_INTERMISSION` (3) - Between rounds/end of match

When transitioning from PLAYING → INTERMISSION, the script:
1. Records `round_end_unix` (accurate even on surrender!)
2. Calculates actual duration
3. Reads winner from `CS_MULTI_MAPWINNER` config string
4. POSTs all metadata to Discord webhook

### Pause Detection

The script detects pauses by monitoring frame time deltas. If more than 2 seconds pass between frames, the game is considered paused. This is a heuristic but works well in practice.

### Surrender Timing Fix

The key insight: when teams surrender, the stats file still shows the full map time limit. But the Lua script captures the actual `round_end_unix` when the gamestate changes. The bot uses this accurate timestamp instead of the broken stats file value.

## Configuration Options

In `stats_discord_webhook.lua`:

| Option | Default | Description |
|--------|---------|-------------|
| `discord_webhook_url` | (required) | Your Discord webhook URL |
| `enabled` | `true` | Enable/disable webhook notifications |
| `debug` | `false` | Log debug messages to server console |
| `send_delay_seconds` | `3` | Wait time before sending (allows stats file to be written) |

## Fallback Behavior

SSH polling continues to run as a fallback. If the Lua webhook fails:
- Stats file is still written normally
- SSH polling picks it up within 60 seconds
- No data is lost

The webhook just provides faster notification and accurate timing metadata.

## Files Reference

| File | Purpose |
|------|---------|
| `vps_scripts/stats_discord_webhook.lua` | Lua script for game server |
| `bot/ultimate_bot.py` | Bot webhook handler (enhanced) |
| `migrations/001_add_timing_metadata_columns.sql` | Database migration |
| `.env.example` | Configuration documentation |
