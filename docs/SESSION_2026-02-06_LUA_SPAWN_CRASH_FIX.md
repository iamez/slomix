# 2026-02-06 — Lua Spawn Tracking Crash Fix

## Issue
Server crashed / spammed logs when a neutral damage event occurred.
Logs showed:
```
Lua 5.4 API: et_RunFrame error running lua script:
[string "luascripts/stats_discord_webhook.lua"]:457: tried to get invalid gentity field "pers.connected"
```

## Root Cause
Spawn tracking loop iterated `0..63` regardless of actual `sv_maxclients`.
On a 16-slot server, indices > 15 don't have a valid `gentity` with `pers.connected`, causing repeated Lua errors.

## Fix
Updated `stats_discord_webhook.lua` to:
- Use `sv_maxclients` to bound iteration.
- Add `safe_gentity_get()` wrapper with throttled error logging.
- Apply safe wrapper to spawn tracking, team collection, obituary, and surrender vote tracking.

## Files Updated
- `vps_scripts/stats_discord_webhook.lua`

## Deploy Command
```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@91.185.207.163 \
"cat > /home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua" \
< /home/samba/share/slomix_discord/vps_scripts/stats_discord_webhook.lua
```

Restart map/server after deploy.

## Verify
```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@91.185.207.163 \
"grep -n 'et_RunFrame error running lua script' /home/et/.etlegacy/legacy/etconsole.log | tail -n 20"
```

Expect no new errors after reload.
