# Proximity Objectives + Schema Sync Report (2026-02-04)

## Summary
- Synced proximity objective configuration to the **full server map rotation**.
- Added **round_start_unix / round_end_unix** columns + new unique keys to prevent same‑day collisions.
- Added tooling to **sync map rotation → JSON → Lua**.
- Added **objective config sanity logging** on Lua init.
- Added **!proximity_objectives** command to show which maps are configured.
- Attempted **lua_restart via RCON** (timeout). Manual restart still needed.

## Changes Applied
- `proximity/lua/proximity_tracker.lua`
  - Objectives now generated from `proximity/objective_coords_template.json`.
  - Full placeholder coverage for all maps in rotation.
  - Objective config sanity log on init.
- `proximity/objective_coords_template.json`
  - Seeded with all map placeholders from rotation.
- `proximity/map_rotation.txt`
  - Server map rotation list from `legacy3.config`.
- `scripts/sync_objective_placeholders.py`
  - Adds missing maps into the JSON template.
- `scripts/update_proximity_objectives_from_json.py`
  - Rebuilds Lua objectives table from JSON.
- `scripts/objective_coords_to_lua.py`
  - Emits Lua snippet for manual use if needed.
- `scripts/rcon_command.py`
  - One‑off RCON helper for `lua_restart`, `map_restart 0`, etc.
- `bot/cogs/proximity_cog.py`
  - Added `!proximity_objectives` (admin) to show configured vs missing maps.
- `proximity/schema/migrations/2026-02-04_round_start_unix.sql`
  - Migration for round_start_unix / round_end_unix + new unique keys.
- `proximity/schema/schema.sql`
  - Schema updated to match new columns and unique constraints.

## DB Migration
- Migration applied successfully to Postgres:
  - Added `round_start_unix` / `round_end_unix` columns to:
    - `combat_engagement`
    - `player_track`
    - `proximity_objective_focus`
  - Updated unique constraints to include `round_start_unix`.

## Server Ops
- Uploaded updated `proximity_tracker.lua` to:
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/proximity_tracker.lua`
- Attempted RCON `lua_restart` via `scripts/rcon_command.py`.
  - Result: **timeout** (needs manual retry).

## Pending Manual Step
- **Lua reload required** to apply new objective configs.
  - Use one of these:
    - `lua_restart`
    - `map_restart 0`

## How To Update Objective Coords
1. Edit `proximity/objective_coords_template.json`.
2. Run:
   - `python3 scripts/sync_objective_placeholders.py`
   - `python3 scripts/update_proximity_objectives_from_json.py`
3. Reload Lua on server.

## Notable Limitations
- Objective coordinates for many maps are placeholders (TODO) until filled.
- RCON timed out from this environment; retry from a trusted host.

## Files Updated
- `proximity/lua/proximity_tracker.lua`
- `proximity/objective_coords_template.json`
- `proximity/map_rotation.txt`
- `proximity/schema/schema.sql`
- `proximity/schema/migrations/2026-02-04_round_start_unix.sql`
- `scripts/sync_objective_placeholders.py`
- `scripts/update_proximity_objectives_from_json.py`
- `scripts/objective_coords_to_lua.py`
- `scripts/rcon_command.py`
- `bot/cogs/proximity_cog.py`
- `docs/SESSION_2026-02-03_CHANGELOG_LOCAL.md`

