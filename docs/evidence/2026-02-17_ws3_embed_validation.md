# Evidence: WS3-005 Discord Embed Size Safety
Date: 2026-02-12  
Workstream: WS3 (Team Display Improvements)  
Task: `WS3-005`  
Status: `in_progress`

## Goal
Prevent Discord post failures caused by field-size overflow in high-player round embeds.

## Code Changes
File:
1. `bot/services/round_publisher_service.py`

What changed:
1. Added `_chunk_embed_lines(...)` helper to split preformatted player blocks into Discord-safe field values (`<=1024` chars each).
2. Round stats player rendering now chunks by actual character budget instead of fixed player count.
3. Team grouping + per-team ranking behavior is preserved while ensuring each generated field remains valid for Discord API limits.

## Test Coverage
File:
1. `tests/unit/test_round_publisher_team_grouping.py`

New safety assertion:
1. `test_publish_round_stats_keeps_discord_field_values_within_limit` validates:
   - multi-chunk Axis section is created under load
   - every generated Axis field value length is `<=1024`.

Validation commands:
```bash
pytest -q tests/unit/test_round_publisher_team_grouping.py tests/unit/test_round_publisher_map_scope.py
```

```bash
pytest -q \
  tests/unit/test_round_publisher_team_grouping.py \
  tests/unit/test_round_publisher_map_scope.py \
  tests/unit/test_round_contract.py \
  tests/unit/test_stats_parser.py \
  tests/unit/test_gametime_synthetic_round.py \
  tests/unit/test_lua_round_teams_param_packing.py \
  tests/unit/test_timing_debug_service_session_join.py \
  tests/unit/test_lua_webhook_diagnostics.py \
  tests/unit/test_greatshot_crossref.py \
  tests/unit/test_greatshot_player_stats_enrichment.py \
  tests/unit/test_timing_comparison_service_side_markers.py
```

Results:
1. Focused round-publisher tests: `5 passed`
2. Combined regression batch: `44 passed`

## Remaining Gate
Final WS3-005 closure still requires runtime evidence from real Discord posts:
1. At least 5 real posts render without overflow/errors.
2. WS1 live-ingestion gate must pass before final WS3 closeout.
