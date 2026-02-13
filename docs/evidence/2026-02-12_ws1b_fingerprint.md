# Evidence: WS1B-002 Round Fingerprint Precedence
Date: 2026-02-13  
Workstream: WS1B (Unified Ingestion Contract)  
Task: `WS1B-002`  
Status: `done`

## Objective
Define deterministic, ordered fingerprint rules so all ingestion sources converge on the same round identity.

## Normalization Rules
Before fingerprinting:
1. `map_name = lower(trim(map_name))`
2. `round_number = int(round_number)`
3. unix timestamps coerced to integer seconds
4. `round_time` normalized to `HHMMSS` (strip `:`)

## Precedence
Preferred fingerprint (`fp_start`):
1. `map_name + "|" + round_number + "|" + round_start_unix`
2. Use when `round_start_unix > 0`

Fallback fingerprint (`fp_end`):
1. `map_name + "|" + round_number + "|" + round_end_unix`
2. Use when `round_start_unix` missing but `round_end_unix > 0`

Last fallback (`fp_clock`):
1. `map_name + "|" + round_number + "|" + round_date + "|" + round_time`
2. Use when unix timestamps are unavailable

## Comparison Policy
1. If both sides have `fp_start`, compare `fp_start` only.
2. Else if both sides have `fp_end`, compare `fp_end`.
3. Else compare `fp_clock`.
4. If keys mismatch at all available levels, mark `link_status=ambiguous`.

## Example (Known R2 Header Drift Case)
Observed on `2026-02-11` supply R2:
1. Proximity header says `round=1` but includes `round_end_unix=1770843722`.
2. Gametime/STATS_READY says `round=2` with the same end timestamp.

Why precedence works:
1. Correlation on `fp_end` (map + normalized round + end_unix) gives deterministic mapping once round normalization is applied.
2. Date/time fallback alone would be weaker and can drift by a few seconds.

## Operational Guidance
1. Persist the fingerprint source used (`start` | `end` | `clock`) as a debug field where possible.
2. Treat `clock` matches as lower confidence than unix-based matches.
3. Use unix-based fingerprints first in WS2/WS3 diagnostics and dashboards.
