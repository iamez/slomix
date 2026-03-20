# Repeated Map Timing Fix - 2026-03-06

## Scope

This note documents the repeated-map timing drift investigation for the dual-bot setup:

- `samba`
- `slomix_vm`

The main failure case was `te_escape2` being played multiple times in the same session.

## Root Cause

Two separate problems combined:

1. `STATS_READY` was allowed to link Lua timing to an older same-day replay of the same map/round before the new stats file existed locally.
2. `slomix_vm` was not ingesting `gametime-*.json` fallback files, so it never got the later corrective Lua upsert that samba received.

Result:

- both bots could briefly choose the wrong older replay
- samba later corrected the Lua row linkage
- `slomix_vm` kept stale `lua_round_teams.round_id` values

## Code Fixes

Patched files:

- `bot/ultimate_bot.py`
- `bot/automation/file_tracker.py`
- `bot/config.py`
- `tools/slomix_backfill.py`

Behavior changes:

1. Live Lua round linking rejects implausibly large time deltas with `LUA_ROUND_LINK_MAX_DIFF_SECONDS` (default `90`).
2. `STATS_READY` file selection now:
   - parses filenames exactly
   - matches exact `map_name` and `round_number`
   - retries when the nearest same-day candidate is still too far away
   - skips direct fetch instead of attaching metadata to an old replay
3. File claiming is now atomic for key regular-stats paths so webhook/poller races do not both process the same filename.
4. `tools/slomix_backfill.py relink-lua` now uses current `lua_round_teams` timing columns instead of the removed `timestamp` column.

## Runtime Status

### samba

- patched code is active
- bot process was restarted via systemd auto-restart after forced termination

### slomix_vm

- patched code is copied to `/opt/slomix`
- `bot_config.json` now stages:
  - `GAMETIMES_ENABLED=true`
  - `REMOTE_GAMETIMES_PATH=/home/et/.etlegacy/legacy/gametimes`
  - `LOCAL_GAMETIMES_PATH=/opt/slomix/local_gametimes`
  - `GAMETIMES_STARTUP_LOOKBACK_HOURS=24`
  - `LUA_ROUND_LINK_MAX_DIFF_SECONDS=90`
- current `te_escape2` stale Lua rows were repaired in PostgreSQL
- `slomix-bot.service` still needs a privileged restart to activate the staged code/config

## Verified DB Repair

On `slomix_vm`, March 5 `te_escape2` Lua rows now resolve as:

- `215 -> round_id 10030`
- `177 -> round_id 10031`
- `380 -> round_id 10033`
- `211 -> round_id 10034`
- `265 -> round_id 10036`
- `181 -> round_id 10037`

This now matches samba.

## Remaining Operational Step

`slomix-bot.service` restart was blocked by host policy for the `slomix` user (`systemctl restart slomix-bot.service` returned `Access denied`).

Once a privileged restart is performed on `slomix_vm`, the repeated-map runtime behavior should match samba:

- gametime fallback enabled
- stale same-day replay selection rejected
- atomic regular-file claiming active
