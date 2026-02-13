# Evidence: WS1B-001 Canonical `round_event` Contract
Date: 2026-02-13  
Workstream: WS1B (Unified Ingestion Contract)  
Task: `WS1B-001`  
Status: `done`

## Purpose
Define one canonical envelope for all round-related ingest paths so timing/score/endstats/proximity can be correlated using the same language.

## Canonical Envelope
Required fields:
1. `source`
2. `map_name`
3. `round_number`
4. `received_at`
5. `parse_status`
6. `link_status`
7. `confidence`

Optional but strongly recommended fields:
1. `round_start_unix`
2. `round_end_unix`
3. `round_date`
4. `round_time`
5. `filename`
6. `webhook_id`
7. `round_id`
8. `match_id`
9. `details` (source-specific payload fragments)

Enums:
1. `source`: `filename_trigger` | `stats_ready` | `proximity_file` | `gametime_fallback`
2. `parse_status`: `ok` | `partial` | `failed`
3. `link_status`: `unlinked` | `linked_round_id` | `ambiguous`
4. `confidence`: `high` | `medium` | `low`

## Source Mapping
`filename_trigger`:
1. Primary identifiers from file name (`YYYY-MM-DD-HHMMSS-map-round-N.txt`)
2. Map/round/time available early
3. Usually strongest for round_date/round_time

`stats_ready`:
1. Primary identifiers from Lua embed fields (`Map`, `Round`, `Lua_RoundStart`, `Lua_RoundEnd`)
2. Timing metadata includes pause/warmup/end_reason/winner/defender
3. Highest quality for actual end timestamp

`proximity_file`:
1. Primary identifiers from header (`# map=`, `# round=`, `# round_start_unix=`, `# round_end_unix=`)
2. Known risk: some R2 files still emit `# round=1` and require normalization

`gametime_fallback`:
1. Same metadata content as `stats_ready`, serialized on server side
2. Used when live Discord leg is unavailable
3. Good fallback for correlation with filename/proximity

## Contract Compliance Notes (Current Codebase)
1. Shared linker expects map + round and then resolves by nearest timestamp/date window:
   - `bot/core/round_linker.py`
2. Metadata ingestion paths normalize fields into one dict shape before storage:
   - `bot/ultimate_bot.py` (`_fields_to_metadata_map`, `_build_round_metadata_from_map`)
3. Proximity parser now normalizes round number precedence using gametime before header:
   - `proximity/parser/parser.py`

## Minimal JSON Example
```json
{
  "source": "stats_ready",
  "map_name": "supply",
  "round_number": 2,
  "round_start_unix": 1770843143,
  "round_end_unix": 1770843722,
  "round_date": "2026-02-11",
  "round_time": "220205",
  "filename": "2026-02-11-220205-supply-round-2.txt",
  "webhook_id": "123456789012345678",
  "parse_status": "ok",
  "link_status": "unlinked",
  "confidence": "high",
  "details": {
    "winner_team": 2,
    "defender_team": 1
  }
}
```
