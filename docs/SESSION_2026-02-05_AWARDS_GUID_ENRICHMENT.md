# Session Report — Awards GUID Enrichment (2026-02-05)

## Goal
Fix `guid: null` in awards leaderboard by enriching award rows with GUIDs derived from alias and stats tables.

## Changes
- Added `resolve_name_guid_map()` helper to map `player_name -> guid` using the latest entry in `player_comprehensive_stats`.
- Applied GUID enrichment in these endpoints:
  - `/rounds/{round_id}/awards`
  - `/rounds/{round_id}/vs-stats`
  - `/awards/leaderboard`
  - `/players/{identifier}/awards`
  - `/awards` list
- Updated SQL to `COALESCE(ra.player_guid, am.guid, nm.player_guid)` wherever possible.

## Files Updated
- `website/backend/routers/api.py`

## Expected Result
- Awards leaderboard should now return non-null GUIDs for most players.
- Any remaining null GUIDs indicate missing mappings in both `player_aliases` and `player_comprehensive_stats`.

## Next Checks
1. Restart `etlegacy-web`.
2. Re-run:
   - `/api/awards/leaderboard`
   - `/api/awards`
   - `/api/rounds/{round_id}/awards`

