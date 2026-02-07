# Session Report — Awards GUID Enrichment v2 (2026-02-05)

## Problem
Awards leaderboard still returned `guid: null` after the first enrichment pass. That indicates the advanced SQL either fell back or still failed to match GUIDs for some names.

## Fix v2
- Enhanced name → GUID resolution to use **both** `player_name` and `clean_name` from `player_comprehensive_stats`.
- Added a **post-query enrichment** step for awards leaderboard rows (even if the SQL falls back).
  - If a row is name-only, we now try:
    - `player_aliases` map
    - `player_comprehensive_stats` name/clean_name map
- This ensures GUIDs are filled even when the SQL can’t resolve them directly.

## Files Updated
- `website/backend/routers/api.py`

## Expected Result
`/api/awards/leaderboard` should now show GUIDs for players that exist in stats, even when they appear under aliases.

## Next Check
Restart `etlegacy-web`, then re-run:
```
curl -s http://localhost:8000/api/awards/leaderboard | python3 -m json.tool
```

