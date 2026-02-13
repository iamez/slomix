# Evidence: WS0-008 Counter-Reset Telemetry
Date: 2026-02-12  
Workstream: WS0 (Score Truth Chain)  
Task: `WS0-008`  
Status: `done`

## Telemetry Added
Code path:
1. `bot/community_stats_parser.py`

New log marker:
1. `[R2 RESET FALLBACK] player=<name> fields=<comma_list> mode=use_r2_raw r1_time=<...> r2_time=<...>`

Purpose:
1. Emit explicit reason when per-player R2 counters are non-cumulative.
2. Show which fields dropped (`R2 < R1`) and triggered fallback.

## Current Validation
1. Unit test path validates fallback behavior (`tests/unit/test_stats_parser.py`).
2. Replay of real reconnect case emitted telemetry line:
   - `[R2 RESET FALLBACK] player=4/head Jaka.V fields=deaths,damage_given,damage_received,objective.damage_given,objective.damage_received mode=use_r2_raw r1_time=7.50 r2_time=7.50`
3. Replay summary confirms selectivity:
   - `players_total=8`
   - `fallback_players=1`
   - `normal_players=7`

## Done Criteria
1. Captured explicit reconnect/reset telemetry line from real replay data.
2. Verified unaffected players remained non-fallback in same replay.
3. WS0-008 is closed.
