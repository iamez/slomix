# Session Investigation Notes (2026-02-12)
Scope: Live-session follow-up, docs only, no code edits in this session.

## Why "NO LUA DATA" Is Happening Right Now
1. STATS_READY webhooks are arriving and accepted by the bot on real rounds.
2. `lua_round_teams` writes fail at store stage with:
   - `the server expects 24 arguments for this query, 3 were passed`
3. Because that insert fails, timing services correctly report missing Lua timing rows.

Evidence:
1. `logs/webhook.log` and `logs/bot.log` show repeated STATS_READY acceptance on `2026-02-11`.
2. `logs/errors.log` shows repeated store warning with the 24-vs-3 argument mismatch.
3. DB snapshot (`2026-02-12`):
   - `lua_round_teams=1` (latest `2026-01-24 22:00:30+00`)
   - `lua_spawn_stats=78` (latest `2026-02-11 22:48:01+00`)

Interpretation:
1. Lua script transport is not the blocker.
2. Bot insert parameter packing for `_store_lua_round_teams` is the blocker.

## Reconnect Undercount Bug (Player Time/Damage Lost)
Observed case:
1. Player `4/head Jaka.V` (`E587CA5F`) on `etl_sp_delivery`:
   - R1 (`round_id=9824`): `13 kills`, `3039 damage`, `452s`
   - R2 (`round_id=9825`): `1 kill`, `0 damage`, `0s`
2. Raw stats files show R2 had valid activity, but per-player counters were not cumulative for this player after reconnect.

Why it breaks:
1. Parser differential assumes cumulative R2 per player:
   - `R2_only = max(0, R2_cumulative - R1)`
2. If one player's counters reset between rounds, subtraction clamps to zero and loses valid R2 stats.

Relevant code:
1. `bot/community_stats_parser.py:563`
2. `bot/community_stats_parser.py:567`
3. `bot/community_stats_parser.py:595`

## Proximity Status and Gaps
Working:
1. Fresh proximity data exists for `2026-02-11`:
   - `combat_engagement=3506`
   - `player_track=1525`
   - `proximity_trade_event=1647`
   - `proximity_support_summary=13`

Broken/unclear:
1. `sprint_percentage` is all zero (`min=0`, `max=0`, `avg=0`, `1525/1525 rows`).
2. Repeated duplicate-key import failures are caused by parallel legacy+new unique constraints:
   - `player_track` has two UNIQUE constraints (old and new).
   - `proximity_objective_focus` has two UNIQUE constraints (old and new).
3. Timeline/hotzone UI lacks enough context labels for users to interpret charts quickly.

## Greatshot Issues
1. Cross-reference endpoint reports HTTP 500 in UI.
2. Likely failure point:
   - `website/backend/services/greatshot_crossref.py:254`
   - code calls `db_winner.lower()` while DB `winner_team` is numeric in many rows.
3. Per-player section in analysis artifacts often has:
   - `damage_given = 0`
   - `accuracy = null`
   - so the UI is not hiding fields; source artifact is sparse.

## Achievement Spam Context
1. Live achievements can produce message floods when many thresholds unlock at once.
2. Local config/code paths support suppression/aggregation:
   - `LIVE_ACHIEVEMENT_MODE=off|summary|individual`
   - summary mode posts one compact embed instead of many individual posts.

## Execution Order (Doc-Tracked)
1. WS1-006: restore `lua_round_teams` insert path.
2. WS1-007: validate on two fresh rounds and confirm `NO LUA DATA` clears for those rounds.
3. WS0-007: reconnect-safe differential logic for per-player reset cases.
4. WS1C-003 and WS1C-004: clean duplicate constraints and fix sprint pipeline.
5. WS6-001: fix Greatshot crossref 500.
6. WS6-002: expand Greatshot player stats coverage (damage/accuracy/TPM where available).
