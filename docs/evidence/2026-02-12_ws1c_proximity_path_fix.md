# Evidence: WS1C-001 Proximity Remote Path Fix
Date: 2026-02-12  
Workstream: WS1C (Proximity Source Health)  
Task: `WS1C-001`  
Status: `done`

## Goal
Correct the proximity remote source path and confirm fresh 2026-02-11 proximity files are imported into local storage and DB tables.

## Baseline Problem
1. Proximity files were being generated on the game server under:
   - `/home/et/.etlegacy/legacy/proximity`
2. Bot path had previously pointed at an outdated directory, so fresh files were missed.

## Applied Change
1. Updated bot runtime env path:
```text
.env:152
PROXIMITY_REMOTE_PATH=/home/et/.etlegacy/legacy/proximity
```
2. Re-ran proximity import cycle.

## Validation
1. Local file landing check:
```text
local_proximity 2026-02-11 *_engagements.txt count = 16
```
2. DB ingestion check (`session_date = 2026-02-11`):
```text
combat_engagement         3506
player_track              1645
proximity_trade_event     1845
proximity_support_summary 16
```
3. Latest session date check:
```text
combat_engagement         latest_session_date=2026-02-11
player_track              latest_session_date=2026-02-11
proximity_trade_event     latest_session_date=2026-02-11
proximity_support_summary latest_session_date=2026-02-11
```

## Command Log
```bash
rg -n --hidden "^PROXIMITY_REMOTE_PATH=" .env bot/dotenv-example
rg --files local_proximity | rg '2026-02-11-.*_engagements\.txt$' | wc -l
/bin/bash -lc "PGPASSWORD='REDACTED_DB_PASSWORD' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy -F $'\t' -Atc \"SELECT 'combat_engagement' AS tbl, COALESCE(MAX(session_date)::text,'NULL') AS latest_session_date, COUNT(*) FILTER (WHERE session_date=DATE '2026-02-11') AS rows_2026_02_11 FROM combat_engagement UNION ALL SELECT 'player_track', COALESCE(MAX(session_date)::text,'NULL'), COUNT(*) FILTER (WHERE session_date=DATE '2026-02-11') FROM player_track UNION ALL SELECT 'proximity_trade_event', COALESCE(MAX(session_date)::text,'NULL'), COUNT(*) FILTER (WHERE session_date=DATE '2026-02-11') FROM proximity_trade_event UNION ALL SELECT 'proximity_support_summary', COALESCE(MAX(session_date)::text,'NULL'), COUNT(*) FILTER (WHERE session_date=DATE '2026-02-11') FROM proximity_support_summary ORDER BY 1;\""
```

## Decision
1. Remote path correction is effective.
2. Fresh 2026-02-11 proximity files landed locally and persisted in DB.
3. `WS1C-001` is closed.
