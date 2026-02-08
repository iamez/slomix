# Session: Lua Webhook Timing Fix & Future Roadmap

**Date:** January 27, 2026
**Branch:** `feature/lua-webhook-realtime-stats`
**Status:** Fix deployed, awaiting testing

---

## What We Did This Session

### 1. Built TimingComparisonService (NEW FEATURE)

Created a **separate dev channel display** comparing stats file timing vs Lua webhook timing.

**Files created/modified:**
- `bot/services/timing_comparison_service.py` (NEW)
- `bot/config.py` - added `dev_timing_channel_id`, `timing_comparison_enabled`
- `bot/services/round_publisher_service.py` - wired in new service
- `bot/ultimate_bot.py` - instantiates service
- `.env` - enabled feature

**What it does:**
- After each round, posts comparison embed to dev channel
- Shows stats file duration vs Lua duration
- Shows per-player times with correction factors
- Status indicators: ✅ ALIGNED / ⚡ MINOR DIFF / ⚠️ DISCREPANCY / ❓ NO LUA DATA

### 2. Fixed Lua Webhook Script (CRITICAL BUG)

**The Problem:** Lua webhook was loading but NEVER sending data.

**Root Cause Found by Log Tracing:**
```lua
-- Our script used HARDCODED values:
local GS_INTERMISSION = 3

-- But other working scripts use ET:Legacy API:
if gamestate == et.GS_INTERMISSION then
```

The hardcoded `3` might not equal `et.GS_INTERMISSION`, so the condition never matched!

**The Fix (v1.4.2):**
```lua
-- Now uses proper ET:Legacy constants with fallback:
local GS_INTERMISSION = et.GS_INTERMISSION or 3
```

**Other fixes in v1.4.2:**
- Send webhook immediately (delay=0) instead of 3-second delay
- Fixed gentity validation error at line 689
- Debug logging enabled

**Deployed to:** `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua`

---

## What Needs Testing

### Next Game Session Will Verify:

1. **Lua webhook actually fires** - Look for `[stats_discord_webhook] Sent round notification` in console
2. **Data stored in database** - Check `lua_round_teams` table has new rows
3. **TimingComparisonService shows real data** - Dev channel should show Lua timing, not "NO LUA DATA"

### How to Test Manually:

```bash
# After a game, check server console for webhook activity:
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "grep -E 'stats_discord_webhook|Sent round|Sending webhook' /home/et/.etlegacy/legacy/etconsole.log | tail -30"

# Check database for new Lua data:
psql -h localhost -U etlegacy_user -d etlegacy -c \
  "SELECT id, match_id, map_name, actual_duration_seconds, captured_at FROM lua_round_teams ORDER BY captured_at DESC LIMIT 5;"

# Check bot logs for webhook processing:
grep -i "STATS_READY\|lua_round" /path/to/bot/logs/bot.log | tail -20
```

---

## Architecture Overview

### Data Flow (Two Parallel Pipelines)

```
Pipeline 1: Stats File (existing)
─────────────────────────────────
Game Server → c0rnp0rn7.lua writes .txt file
           → SSH polling (60s) OR webhook trigger
           → Bot downloads file
           → Parser extracts 53+ fields per player
           → Stored in: rounds, player_comprehensive_stats

Pipeline 2: Lua Webhook (new, fixes surrender timing)
─────────────────────────────────────────────────────
Game Server → stats_discord_webhook.lua detects round end
           → Sends STATS_READY to Discord webhook (instant)
           → Bot receives webhook message
           → Parses embed fields
           → Stored in: lua_round_teams

Pipeline 3: Comparison (new this session)
─────────────────────────────────────────
After round processed → TimingComparisonService
                     → Fetches from both tables
                     → Posts comparison to dev channel
```

### Key Tables

| Table | Source | Contains |
|-------|--------|----------|
| `rounds` | Stats file | Round metadata, match_id from filename |
| `player_comprehensive_stats` | Stats file | Per-player stats (53 columns) |
| `lua_round_teams` | Lua webhook | Accurate timing, team composition, surrender info |

### match_id Mismatch Issue

- `rounds` table: match_id from R1 filename timestamp (round START)
- `lua_round_teams`: match_id from round_end_unix (round END)
- **These don't match!** TimingComparisonService uses fuzzy matching on map_name + round_number + time window

---

## Configuration Reference

### .env Settings (Timing Features)

```bash
# Timing debug (round-level comparison)
TIMING_DEBUG_ENABLED=true
TIMING_DEBUG_CHANNEL_ID=1424620499975274496

# Timing comparison (per-player, dev channel)
DEV_TIMING_CHANNEL_ID=1424620499975274496
TIMING_COMPARISON_ENABLED=true

# Webhook trigger (for Lua webhook)
WEBHOOK_TRIGGER_CHANNEL_ID=1424620499975274496
WEBHOOK_TRIGGER_WHITELIST=1449808769725890580,1460874526567956481,1463967551049437356
```

### Lua Script Location

- **Local:** `vps_scripts/stats_discord_webhook.lua`
- **Server:** `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua`

**To deploy updates:**
```bash
scp -P 48101 -i ~/.ssh/etlegacy_bot \
  vps_scripts/stats_discord_webhook.lua \
  et@puran.hehe.si:/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/
```

---

## Future Improvements / Ideas

### Short-term (After Testing)

1. **If Lua timing works:** Compare surrender scenarios - stats file should show full map time, Lua should show actual time
2. **Disable debug logging** once confirmed working (set `debug = false` in Lua script)
3. **Use Lua timing as source of truth** for DPM calculations (corrects surrender timing bug)

### Medium-term Enhancements

1. **Per-player Lua timing** - Currently Lua only captures round-level timing. Could extend to track per-player time_played via game events (player_spawn, player_death)

2. **Pause-aware DPM** - Use Lua pause tracking to calculate DPM excluding paused time

3. **Warmup exclusion** - Lua tracks warmup separately, could display "fighting time" vs "total time"

4. **Match_id alignment** - Fix the mismatch between rounds and lua_round_teams tables for easier joins

### Long-term Vision

1. **Hybrid stats** - Best of both worlds:
   - Per-player stats from c0rnp0rn7.lua (already detailed)
   - Accurate timing from stats_discord_webhook.lua
   - Merge at display time

2. **Real-time dashboard** - Use Lua webhook for instant updates to website

3. **Surrender detection** - Automatically flag rounds that ended by surrender and show corrected stats

---

## Debugging Checklist

### If Lua Data Still Not Showing:

1. **Check script loaded:**
   ```bash
   ssh ... "grep 'stats_discord_webhook.*loaded' etconsole.log | tail -5"
   ```
   Should show: `[stats_discord_webhook] v1.4.2 loaded`

2. **Check webhook sent:**
   ```bash
   ssh ... "grep 'Sent round notification' etconsole.log | tail -5"
   ```
   If missing, gamestate detection still not working.

3. **Check debug output:**
   ```bash
   ssh ... "grep '\[stats_discord_webhook\]' etconsole.log | tail -20"
   ```
   With debug=true, should see internal logging.

4. **Check Discord received:**
   Look in WEBHOOK_TRIGGER_CHANNEL for STATS_READY messages.

5. **Check bot processed:**
   ```bash
   grep "STATS_READY\|_store_lua" bot.log | tail -10
   ```

6. **Check database:**
   ```sql
   SELECT * FROM lua_round_teams ORDER BY captured_at DESC LIMIT 5;
   ```

### Common Issues:

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| No "Sent round notification" | Gamestate detection | Check et.GS_* constants |
| Webhook sent but bot ignores | Whitelist | Check WEBHOOK_TRIGGER_WHITELIST |
| Bot receives but no DB entry | Storage error | Check bot logs for errors |
| DB has data but comparison empty | Query mismatch | Check fuzzy matching logic |

---

## Files Changed This Session

```
Modified:
  .env                                    # Added timing config
  .env.example                            # Documented new settings
  bot/config.py                           # Added dev_timing_channel_id
  bot/services/round_publisher_service.py # Wired TimingComparisonService
  bot/ultimate_bot.py                     # Import and init service
  vps_scripts/stats_discord_webhook.lua   # v1.4.2 with fixes

Created:
  bot/services/timing_comparison_service.py  # New comparison service
  docs/SESSION_2026-01-27_LUA_TIMING_FIX.md  # This file
```

---

## Quick Commands

```bash
# Deploy Lua script to server
scp -P 48101 -i ~/.ssh/etlegacy_bot vps_scripts/stats_discord_webhook.lua et@puran.hehe.si:/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/

# Check server console
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "tail -100 /home/et/.etlegacy/legacy/etconsole.log"

# Check lua_round_teams
psql -h localhost -U etlegacy_user -d etlegacy -c "SELECT * FROM lua_round_teams ORDER BY id DESC LIMIT 5;"

# Restart bot
sudo systemctl restart etlegacy-bot

# Check bot status
sudo systemctl status etlegacy-bot
```

---

**Next Steps:**
1. Wait for next game session
2. Verify Lua webhook fires (check console logs)
3. Verify timing comparison shows real data
4. If working, consider using Lua timing for DPM corrections
