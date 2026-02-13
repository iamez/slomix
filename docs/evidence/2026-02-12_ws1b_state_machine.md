# Evidence: WS1B-004 Ingestion State Machine
Date: 2026-02-13  
Workstream: WS1B (Unified Ingestion Contract)  
Task: `WS1B-004`  
Status: `done`

## Canonical States
1. `seen`
2. `parsed`
3. `linked_round_id`
4. `enriched`
5. `published`

Terminal failure states:
1. `parse_failed`
2. `link_failed`
3. `publish_failed`

## Transition Rules
`seen -> parsed`:
1. Raw artifact accepted from one source.
2. Required envelope fields extracted (at least map + round).

`parsed -> linked_round_id`:
1. Round linker resolves canonical `round_id`.
2. Link evidence stores fingerprint used and confidence.

`parsed -> link_failed`:
1. No candidates for map/round/date window
2. or candidates exist but none inside tolerance window.

`linked_round_id -> enriched`:
1. Source-specific payload attached:
   - Lua timing fields
   - stats fields
   - proximity engagement summary

`enriched -> published`:
1. Consumer output created (Discord/UI/API payload updated).

`enriched -> publish_failed`:
1. Consumer render/post path throws error.

## Required Diagnostic Fields Per Transition
1. `source`
2. `round_fingerprint`
3. `link_status`
4. `confidence`
5. `reason_code` (on failures)

Recommended reason codes:
1. `no_rows_for_map_round`
2. `date_filter_excluded_rows`
3. `time_parse_failed`
4. `all_candidates_outside_window`
5. `resolved`

## Current Code Touchpoints
1. Parsing/metadata normalization:
   - `bot/ultimate_bot.py` (`_fields_to_metadata_map`, `_build_round_metadata_from_map`)
2. Link resolution:
   - `bot/core/round_linker.py`
   - `bot/ultimate_bot.py` (`_resolve_round_id_for_metadata`)
3. Persistence/upsert:
   - `bot/ultimate_bot.py` (`_store_lua_round_teams`, `_store_lua_spawn_stats`)
4. Publish/consume:
   - stats import + round publishing paths in `bot/ultimate_bot.py` and `bot/services/round_publisher_service.py`

## Acceptance
1. Every ingestion path can be mapped to one of these states.
2. Every non-success path records reasoned failure state (not silent drop).
