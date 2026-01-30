# Lua Webhook Gamestate Bug Fix - 2026-01-30

**Issue:** STATS_READY webhooks never firing during actual gameplay
**Status:** FIXED - Awaiting test during next game session

---

## Problem Summary

The `stats_discord_webhook.lua` script was loading successfully but never detecting round ends. Bot always showed "NO LUA DATA" in timing comparisons despite the script being correctly installed and configured.

---

## Root Cause

**The `et.GS_PLAYING` constant does not exist in ET:Legacy's Lua API!**

Our script used:
```lua
local GS_PLAYING = et.GS_PLAYING or 2  -- Falls back to 2
```

But the actual playing state in ET:Legacy is `gamestate == 0`, not `2`.

The round end detection checked:
```lua
if new_gamestate == GS_INTERMISSION and old_gamestate == GS_PLAYING then
```

This was checking `old_gamestate == 2`, but the playing state is actually `0`, so the condition **never matched**.

---

## How We Found It

1. **Checked console logs** - Script loaded correctly, showed "v1.4.2 loaded"
2. **Checked webhook logs** - Jan 24 had test webhooks, but Jan 27 actual games had none
3. **Compared with working scripts** - c0rnp0rn7.lua and endstats.lua work correctly
4. **Found the pattern** - Working scripts check `gamestate == 0` for playing, not `et.GS_PLAYING`

Key evidence from c0rnp0rn7.lua:
```lua
if gamestate == 0 or gamestate == et.WARMUP or gamestate == et.GS_WARMUP_COUNTDOWN then
    -- This is warmup/playing detection
```

They check `gamestate == 0` directly, proving that's the playing state value.

---

## The Fix

### File: `vps_scripts/stats_discord_webhook.lua`

**Change 1 - Lines 136-142 (Constants):**
```lua
-- OLD (BUGGY):
local GS_PLAYING = et.GS_PLAYING or 2

-- NEW (FIXED):
local GS_PLAYING = 0  -- HARDCODED: Playing state is 0!
```

**Change 2 - Line 567 (Round end detection):**
```lua
-- OLD (BUGGY):
if new_gamestate == GS_INTERMISSION and old_gamestate == GS_PLAYING then

-- NEW (FIXED):
if new_gamestate == GS_INTERMISSION and old_gamestate ~= GS_INTERMISSION then
```

The new condition detects ANY transition TO intermission, which is more robust.

---

## Deployment

- Fixed script saved to: `/home/samba/share/slomix_discord/vps_scripts/stats_discord_webhook.lua`
- Uploaded to server: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua`
- Script will reload on next map change

---

## Verification Steps

1. Wait for next game session on the server
2. When a round ends, check server console for: `[stats_discord_webhook] Round ended at...`
3. Check Discord webhook channel for STATS_READY message
4. Check bot logs for: `Received STATS_READY webhook with metadata`
5. Timing comparison should show Lua data instead of "NO LUA DATA"

---

## ET:Legacy Gamestate Constants Reference

Based on analysis of working scripts (c0rnp0rn7.lua, endstats.lua):

| Constant | Value | Notes |
|----------|-------|-------|
| Playing state | `0` | Not exposed as `et.GS_PLAYING` |
| `et.GS_WARMUP_COUNTDOWN` | Unknown | Exposed, use directly |
| `et.GS_INTERMISSION` | Unknown | Exposed, use directly |
| `et.WARMUP` | Unknown | May exist, different from countdown |

**Key lesson:** Always check working code in the same environment. Don't assume API constants exist without verification.

---

## Related Files

- **Script:** `vps_scripts/stats_discord_webhook.lua` (v1.4.2)
- **Config:** `/home/et/etlegacy-v2.83.1-x86_64/etmain/configs/legacy3.config`
- **Load order:** team-lock.lua → c0rnp0rn7.lua → endstats.lua → stats_discord_webhook.lua

---

**Fixed:** 2026-01-30
**Tested:** Pending (next game session)
**Confidence:** High - matches pattern used by working scripts
