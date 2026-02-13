# Evidence: WS6-002 Greatshot Player Stats Enrichment
Date: 2026-02-13  
Workstream: WS6 (Greatshot Reliability)  
Task: `WS6-002`  
Status: `done`

## Goal
Expand Greatshot player-stat payload/visibility so detail views include:
1. damage
2. accuracy
3. TPM (time played minutes)

when analysis data provides those fields.

## Code Changes
Files:
1. `greatshot/scanner/api.py`
2. `website/backend/services/greatshot_crossref.py`
3. `website/js/greatshot.js`

Summary:
1. Scanner extraction now accepts additional aliases from UDT/playerStats payloads:
   - `damageGiven`/`damageReceived`
   - `timePlayedMinutes`, `timePlayedSeconds`, `timePlayedMs`
   - fallback accuracy from `shotsHit` + `shotsFired`
2. Scanner payload now emits:
   - `time_played_seconds`
   - `time_played_minutes`
   - `tpm` (time played minutes)
3. DB crossref enrichment now emits:
   - `time_played_minutes`
   - `tpm`
4. Greatshot UI now renders TPM in:
   - detail player stats table
   - crossref comparison table
   and also surfaces demo/db damage + accuracy side-by-side.

## Synthetic/Unit Validation
Added tests:
1. `tests/unit/test_greatshot_player_stats_enrichment.py`
   - alias extraction + TPM fields
   - timeline fallback behavior retained
2. `tests/unit/test_greatshot_crossref.py`
   - `enrich_with_db_stats` now verified for `time_played_minutes` + `tpm`

Validation run:
```bash
pytest -q \
  tests/unit/test_greatshot_player_stats_enrichment.py \
  tests/unit/test_greatshot_crossref.py \
  tests/unit/test_gametime_synthetic_round.py \
  tests/unit/test_lua_round_teams_param_packing.py
```

Result:
1. `8 passed`

Compile check:
```bash
python3 -m py_compile \
  greatshot/scanner/api.py \
  website/backend/services/greatshot_crossref.py \
  tests/unit/test_greatshot_player_stats_enrichment.py \
  tests/unit/test_gametime_synthetic_round.py \
  tests/unit/test_greatshot_crossref.py
```

Result:
1. no syntax errors

## Notes / Residual Risk
1. Browser-level manual smoke check is still recommended for final UX verification.
2. Existing `tests/test_greatshot_scanner_golden.py` is already out of date from earlier highlight-schema changes and remains unrelated to this task.
