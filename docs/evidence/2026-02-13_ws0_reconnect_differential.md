# Evidence: WS0-007 Reconnect-Safe Differential Logic
Date: 2026-02-12  
Workstream: WS0 (Score Truth Chain)  
Task: `WS0-007`  
Status: `done`

## Goal
Prevent false zero `time_played` / `damage` for R2 players when counters are non-cumulative after reconnect/reset.

## Code Changes
1. `bot/community_stats_parser.py`
   - Added per-player reset detection helper:
     - `_detect_player_counter_reset(...)`
   - Added fallback mode for affected players:
     - if any cumulative counter drops (`R2 < R1`), use safe `R2 raw` values instead of `max(0, R2-R1)` subtraction.
   - Added structured telemetry:
     - `[R2 RESET FALLBACK] player=... fields=... mode=use_r2_raw`
   - Applied fallback to:
     - top-level kills/deaths/headshots/damage,
     - `objective_stats` cumulative numeric fields (including `time_played_minutes`),
     - weapon differential stats.
2. `tests/unit/test_stats_parser.py`
   - Added test:
     - `TestRound2CounterResetFallback::test_uses_r2_raw_when_player_counters_drop`
   - Verifies:
     - reset player uses raw R2 time/damage/kills (not zeroed),
     - normal player still uses standard differential subtraction.

## Validation Run
Commands run:
```bash
pytest -q tests/unit/test_stats_parser.py -k "counter_reset_fallback or parse_round_2_with_differential"
pytest -q tests/unit/test_stats_parser.py::TestStatsFileParsing::test_parse_round_2_with_differential
python3 - <<'PY'
from bot.community_stats_parser import C0RNP0RN3StatsParser
p = C0RNP0RN3StatsParser()
r1 = p.parse_regular_stats_file('local_stats/2026-02-11-221100-etl_sp_delivery-round-1.txt')
r2 = p.parse_regular_stats_file('local_stats/2026-02-11-222017-etl_sp_delivery-round-2.txt')
diff = p.calculate_round_2_differential(r1, r2)
...
PY
```

Result:
1. New fallback test passed.
2. Existing differential test passed.
3. Target reconnect replay (`etl_sp_delivery` R1/R2, 2026-02-11) now returns non-zero fallback values for the known affected player:
   - `4/head Jaka.V`: `kills=14`, `damage_given=2872`, `time_played_minutes=7.5`, `time_played_seconds=450`.
4. Differential summary from replay:
   - `players_total=8`
   - `fallback_players=1`
   - `normal_players=7`

## Runtime Replay Status
1. Known `round_id=9825` style reconnect scenario has been replayed from real captured files.
2. Reset-affected player is no longer zeroed by differential subtraction.
3. WS0-007 is closed.
