# Session Report — Alias Search + Leaderboard Units (2026-02-05)

## Goal
- Reduce duplicate player listings caused by alias/name changes.
- Make leaderboard labels/units match what the backend actually returns.

## Changes
### 1) Player Search (Auth + API)
- **`/auth/players/search`** now returns **unique GUIDs** instead of one row per alias.
- Search matches:
  - `player_comprehensive_stats.player_name`
  - `player_comprehensive_stats.clean_name`
  - `player_aliases.alias` (when available)
- Each result now includes:
  - `guid`
  - `name` (resolved display name)
  - `canonical_name` (best raw name for linking)

Backend files:
- `website/backend/routers/auth.py`
- `website/backend/routers/api.py`

Frontend adjustments:
- `website/js/auth.js`
  - Use `player.guid` for hero search profile loading (stable identity).
  - Use `canonical_name` for linking, while displaying `name`.
  - Guard against legacy string-only responses.

### 2) Leaderboard Labels + Units
- Updated labels to match data:
  - `games` stat now labeled **Rounds** (it counts rounds in stats table).
  - Accuracy header now shows **Accuracy (%)**.
- Added formatting for value column:
  - Accuracy -> `xx.x%`
  - DPM -> one decimal
  - K/D -> two decimals
  - Others -> comma-separated numbers

Frontend files:
- `website/js/leaderboard.js`
- `website/index.html`

## Why
- Duplicate aliases were showing up as separate “players” in search results because queries were distinct by name instead of GUID.
- Leaderboard values were accurate but not labeled/formatted correctly, causing confusion for non-dev viewers.

## Next Steps
- Extend GUID-based unification to other lists if duplicates are still visible (e.g., awards or special views that group by player_name).
- Verify that link flows still correctly associate Discord → GUID after backend restart.
