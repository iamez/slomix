# Deployed Lua Source Of Truth

This folder mirrors the Lua files currently deployed on the ET:Legacy game server.

## Server mapping

- `deployed_lua/legacy/c0rnp0rn7.lua`
  - remote: `/home/et/etlegacy-v2.83.1-x86_64/legacy/c0rnp0rn7.lua`
- `deployed_lua/legacy/endstats.lua`
  - remote: `/home/et/etlegacy-v2.83.1-x86_64/legacy/endstats.lua`
- `deployed_lua/legacy/luascripts/stats_discord_webhook.lua`
  - remote: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua`
- `deployed_lua/legacy/luascripts/proximity_tracker.lua`
  - remote: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/proximity_tracker.lua`

## Last sync/deploy session

- timestamp: `2026-02-19 15:32` (local)
- host used: `91.185.207.163:48101` (DNS fallback for `puran.hehe.si`)
- backups of pre-sync local files:
  - `docs/reference/live_sync_backups/20260219_153221/stats_discord_webhook.local_before_sync.lua`
  - `docs/reference/live_sync_backups/20260219_153221/proximity_tracker.local_before_sync.lua`

## Canonical local files

These local files are synced to match deployed server versions:

- `vps_scripts/stats_discord_webhook.lua`
- `proximity/lua/proximity_tracker.lua`

## Hashes after sync

- `c0rnp0rn7.lua`: `7f5ef497dd21968c07d3444bb0072bbe3d468123d519e3419cf8c556494763b0`
- `endstats.lua`: `c2e9fdac0fe9390aa4b5e12fd79618c853fa4dd7563860d2ad53c8413973d8af`
- `stats_discord_webhook.lua`: `a59b4bead00a0cad5ba1391e4afec1ce63244be51d078e7a7401f2a0c3756950`
- `proximity_tracker.lua`: `1d2965ccbf19f582c93bca8545111c9a433e93c19b32e06fc285dc0db708ce20`

## Proximity version note

There are multiple local proximity variants (`proximity_tracker.lua`, `proximity_tracker_v2.lua`, `proximity_tracker_v3.lua` at repo root).
The currently deployed version is the one in:

- `proximity/lua/proximity_tracker.lua`
- mirrored in `deployed_lua/legacy/luascripts/proximity_tracker.lua`

The root-level variants are not the deployed server version.

