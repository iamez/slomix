# 2026-02-06 — Lua Spawn Tracking + Gametimes Debug

## Goal
Add Oksii-style spawn/death tracking to the Lua webhook pipeline and make gametimes output auditable so we can validate time dead/denied against raw Lua timing.

## Changes Made (Local Repo)
### Lua webhook script
File: `vps_scripts/stats_discord_webhook.lua`

- Added **spawn/death tracking** per player (counts, dead seconds, avg/max respawn).
- Added **Lua_SpawnSummary** to the Discord embed.
- Added **spawn_stats JSON** to the gametimes payload under `meta.spawn_stats`.
- Added **debug path logging** at init:
  - `fs_basepath`, `fs_homepath`, `fs_game`
  - `gametimes_enabled`, configured dir, resolved dir
- Added **gametimes meta fields** in the saved JSON:
  - `round_start_unix`, `round_end_unix`
  - `actual_duration_seconds`, `warmup_seconds`, `pause_seconds`, `pause_count`
- Added **write trace logs** for gametimes files and directory creation.

### Bot ingestion
File: `bot/ultimate_bot.py`

- Added `lua_spawn_stats` ingestion from:
  - STATS_READY webhook embed
  - gametimes fallback JSON (`meta.spawn_stats`)
- Stores spawn stats in DB with `match_id`, `round_number`, `round_id` if available.

### Database
File: `migrations/008_add_lua_spawn_stats.sql`

- Creates `lua_spawn_stats` table + indexes for round linkage and audits.

### API
File: `website/backend/routers/api.py`

- Added `GET /api/diagnostics/spawn-audit` to compare Lua spawn timings vs stored round timings.

File: `website/grant_server_activity_permissions.sql`

- Added `lua_spawn_stats` to readonly permissions (needs DB grant).

## Deployment Checklist
### 1) Deploy Lua webhook script (game server)
Copy updated script to:
- `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua`

### 2) Ensure gametimes directory exists
- `/home/et/.etlegacy/legacy/gametimes`

### 3) Reload ET server
- Map restart or server restart so the updated Lua script is loaded.

### 4) Database migration
Run on DB:
- `migrations/008_add_lua_spawn_stats.sql`

### 5) Grant permissions
Run:
- `GRANT SELECT ON TABLE lua_spawn_stats TO website_readonly;`

### 6) Verify after a real round ends
Expected outputs:
- `etconsole.log` shows:
  - `gametimes_enabled`, resolved path
  - `Sending webhook...`
  - `Gametime file written: ...`
- New file in `/home/et/.etlegacy/legacy/gametimes/`
- Bot logs show:
  - `💾 Stored Lua spawn stats` entries
- API checks:
  - `GET /api/diagnostics/lua-webhook`
  - `GET /api/diagnostics/spawn-audit`

## Current Status
- Lua script updated locally; deploy step needs to run on server.
- `lua_spawn_stats` migration present in repo; apply on DB.
- Diagnostics endpoint ready but currently reports **no data** until a fresh round completes.

## Next Validation Steps
- Run a live round and capture:
  - Lua spawn stats in DB
  - gametimes JSON written to disk
- Compare:
  - `dead_seconds` (Lua) vs `time_dead_seconds` in stats file
  - Identify mismatch reasons (round truncation, surrender, missing respawn, etc.)

