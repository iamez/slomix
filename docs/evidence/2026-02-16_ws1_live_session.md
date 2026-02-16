# WS1-002 / WS1-003: Live Session Evidence (2026-02-16)

**Date**: 2026-02-16
**Gaming Session ID**: 89
**Players**: 6 (vid, .wajs, squazetest2026, SuperBoyy, bronze., .olz)
**Maps**: 4 (etl_adlernest, supply, etl_sp_delivery, te_escape2)
**Rounds**: 8 (R1+R2 for each map)

---

## WS1-002: Live Triage Pass (R1/R2 Pair)

### STATS_READY Webhook Events Received

| Time (UTC) | Map | Round | Status |
|---|---|---|---|
| 20:20:28 | etl_adlernest | R1 | Stored (winner=2, playtime=249s) |
| 20:37:24 | supply | R1 | Stored (winner=1, playtime=681s, SURRENDER) |
| 20:48:52 | supply | R2 | Stored (winner=2, playtime=612s, SURRENDER) |
| 21:02:48 | etl_sp_delivery | R1 | Stored (winner=1, playtime=719s) |
| 21:12:49 | etl_sp_delivery | R2 | Stored (winner=2, playtime=571s) |
| 21:19:49 | te_escape2 | R1 | Stored (winner=2, playtime=342s) |

### Complete R1+R2 Lua Pairs

- **supply**: R1 (9858) + R2 (9859) — both HAS_LUA, surrender end_reason
- **etl_sp_delivery**: R1 (9861) + R2 (9862) — both HAS_LUA, normal end_reason

### Missing R2 Rounds

- **etl_adlernest R2** (9856): No STATS_READY received, no gametime file written
- **te_escape2 R2** (9865): No STATS_READY received, no gametime file written
- Root cause: Server-side Lua `intermission_handled` flag reset during rapid gamestate transitions on map change. See Known Issues.

### DB Snapshot

```
lua_round_teams: 23 total (6 new from Feb 16 live session)
lua_spawn_stats: 36 new rows for Feb 16
```

---

## WS1-003: Diagnostics Snapshot

### Pipeline Leg Health (Feb 16)

| Leg | Status | Evidence |
|---|---|---|
| Stats file parsing | PASS | 8/8 files processed, 12 rounds (incl. aggregates) |
| R2 differential | PASS | Independent values per round (not cumulative) |
| Lua STATS_READY | PASS | 6/8 rounds stored (R2 miss on 2 maps) |
| Spawn stats | PASS | 36 rows captured |
| Proximity | PASS | 1466 combat engagements, 660 player tracks |
| Sprint percentage | PASS | 652/660 tracks nonzero (max 85%) |
| Kill assists | PASS | All 8 rounds have non-zero kill_assists |
| WS0 contract columns | FAIL | score_confidence/round_stopwatch_state NULL (stale column cache) |

### WS0 Column Fix Applied

Bot's `_rounds_columns` cache was stale (populated before migration 012). Fixed to refresh every 100 imports. Requires bot restart to take effect.

---

## Exit Criteria (from WEBHOOK_TRIAGE_CHECKLIST)

1. Server shows round end + webhook send logs — **PASS**
2. Bot logs STATS_READY accepted — **PASS** (3 live events)
3. `lua_round_teams` row count increases — **PASS** (6 new live rows)
4. Timing embed no longer shows NO LUA DATA — **PASS** (supply/sp_delivery pairs linked)
5. Round correlation evidence — **PASS** (map/round/timing correlated)

**Gate: PASSED**

---

## Known Issue: Lua R2 Map-Transition Race

On certain maps (etl_adlernest, te_escape2), the server-side Lua script fails to send STATS_READY or write gametime files for R2 rounds. Server console shows "Round ended" event fires but no webhook/file output follows.

**Root cause**: The `intermission_handled` flag in `et_RunFrame` resets too aggressively — any frame where `gamestate ~= GS_INTERMISSION` resets the flag. On maps with rapid gamestate transitions during R2 map change, this causes double-trigger where deduplication silently blocks the second send attempt, or the Lua VM is unloaded mid-execution.

**Fix (deferred)**: Change `intermission_handled` reset to only occur on actual round start (`GS_PLAYING` transition), not on any non-INTERMISSION frame. Requires server-side Lua file edit.

**Impact**: 2/8 rounds (25%) miss Lua timing data. All R1 rounds work. R2 works for some maps (supply, etl_sp_delivery) but not others.
