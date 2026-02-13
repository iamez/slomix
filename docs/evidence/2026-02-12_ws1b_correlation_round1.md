# Evidence: WS1B-005 One-Round Cross-Source Correlation
Date: 2026-02-13  
Workstream: WS1B (Unified Ingestion Contract)  
Task: `WS1B-005`  
Status: `done`

## Correlated Round
Reference round:
1. map: `supply`
2. logical round: `R2`
3. canonical end timestamp: `round_end_unix=1770843722`
4. date/time window: `2026-02-11 22:02 UTC`

## Source Evidence
Filename trigger path:
1. `logs/webhook.log` line `1599`:
   - `Webhook trigger validated: 2026-02-11-220205-supply-round-2.txt`
2. `logs/webhook.log` line `1601`:
   - downloaded `local_stats/2026-02-11-220205-supply-round-2.txt`

STATS_READY path:
1. `logs/webhook.log` line `1582`:
   - `STATS_READY: supply R2 (...)`

Gametime fallback path:
1. `logs/webhook.log` line `1611`:
   - `GAMETIME: supply R2 (...)`
2. `local_gametimes/gametime-supply-R2-1770843722.json`:
   - `meta.round=2`
   - `meta.round_end_unix=1770843722`
   - embed fields include `Lua_RoundEnd=1770843722`

Proximity path:
1. `local_proximity/2026-02-11-220202-supply-round-1_engagements.txt` header:
   - `# map=supply`
   - `# round=1` (legacy/misaligned header value)
   - `# round_end_unix=1770843722`

## Correlation Result
Even with proximity `# round=1` header drift, all three active sources align on the same round end fingerprint:
1. `map_name=supply`
2. `round_end_unix=1770843722`
3. trigger filename timestamp in same event window (`220202` to `220205`)

This is the exact case used by WS1C-002 normalization to prevent R1/R2 collapse.

## Synthetic Validation (No Live Round Required)
Added synthetic replay guard:
1. `tests/unit/test_gametime_synthetic_round.py`

What it proves:
1. A synthetic gametime JSON payload is parsed into canonical metadata.
2. Round metadata and spawn stats are routed through the same ingestion method.
3. `_pending_round_metadata` key is populated deterministically (`map_Rround`).

Command:
```bash
pytest -q tests/unit/test_gametime_synthetic_round.py
```

Result:
1. pass

## Commands Used for Evidence
```bash
rg -n "STATS_READY: supply R2|GAMETIME: supply R2|2026-02-11-220205-supply-round-2.txt" logs/webhook.log
sed -n '1,35p' local_proximity/2026-02-11-220202-supply-round-1_engagements.txt
sed -n '1,70p' local_gametimes/gametime-supply-R2-1770843722.json
sed -n '1,35p' local_stats/2026-02-11-220205-supply-round-2.txt
```
