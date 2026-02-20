# Pipeline Time-Tracking Gap Analysis

> **Date:** 2026-02-20
> **Scope:** Dependency map, code touchpoints, and docs-vs-code comparison for time-tracking pipeline migration
> **Status:** Analysis only - no code changes

---

## 1. Dependency Map: Where Timing Data Flows

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GAME SERVER (puran.hehe.si)                        │
│                                                                             │
│  c0rnp0rn Lua (stats file writer)      stats_discord_webhook.lua (webhook) │
│  ┌─────────────────────────┐           ┌───────────────────────┐           │
│  │ Writes: per-player      │           │ Sends: round-level    │           │
│  │  - time_played (TAB[22])│           │  - Lua_Playtime       │           │
│  │  - time_dead (TAB[25])  │           │  - Lua_RoundStart/End │           │
│  │  - denied_play (TAB[28])│           │  - Lua_Pauses         │           │
│  │  - death_time tracking  │           │  - Spawn stats (v1.6) │           │
│  │  - Header field 9 (NEW) │           │  - Team composition   │           │
│  │    = actual playtime ms  │           │  - end_reason         │           │
│  └───────────┬─────────────┘           └──────────┬────────────┘           │
│              │ file on disk                       │ Discord webhook POST   │
│              │ gamestats/*.txt                     │ STATS_READY message    │
└──────────────┼────────────────────────────────────┼────────────────────────┘
               │                                    │
    ┌──────────▼──────────┐              ┌──────────▼──────────┐
    │  SSH POLLING (60s)  │              │  DISCORD MESSAGE     │
    │  endstats_monitor   │              │  on_message handler  │
    │  bot/ultimate_bot.py│              │  bot/ultimate_bot.py │
    └──────────┬──────────┘              └──────────┬──────────┘
               │                                    │
    ┌──────────▼──────────┐              ┌──────────▼──────────┐
    │  PARSER             │              │  METADATA EXTRACTOR  │
    │  community_stats_   │              │  _build_round_       │
    │  parser.py          │              │  metadata_from_map() │
    └──────────┬──────────┘              └──────────┬──────────┘
               │                                    │
    ┌──────────▼──────────┐              ┌──────────▼──────────┐
    │  DATABASE WRITES    │              │  DATABASE WRITES     │
    │  rounds             │              │  lua_round_teams     │
    │  player_comp_stats  │              │  lua_spawn_stats     │
    │  weapon_comp_stats  │              │                      │
    └──────────┬──────────┘              └──────────┬──────────┘
               │                                    │
               └────────────────┬───────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  ROUND LINKER         │
                    │  _link_lua_round_teams│
                    │  Matches by map +     │
                    │  round + time window  │
                    └───────────┬───────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
    ┌──────────▼──┐  ┌─────────▼───┐  ┌─────────▼──────────┐
    │ BOT DISPLAY │  │ WEBSITE API │  │ TIMING SHADOW SVC  │
    │ Cogs/embeds │  │ api.py      │  │ session_timing_    │
    │ graphs      │  │             │  │ shadow_service.py  │
    └─────────────┘  └─────────────┘  └────────────────────┘
```

---

## 2. Code Touchpoints (Files + Functions Impacted by Migration)

### 2.1 Game Server Lua (Would Change)

| File | Function/Section | Current Role | Migration Impact |
|------|-----------------|--------------|------------------|
| `c0rnp0rn-testluawithtimetracking.lua` | `SaveStats()` header line | Writes 9-field header (incl. actual playtime ms) | **SOURCE OF CHANGE** - new file to deploy |
| `c0rnp0rn-testluawithtimetracking.lua` | `et_RunFrame()` pause tracking | Tracks `pausedTime[1,2,3]` and `roundStart/roundEnd` | New pause-aware round timing |
| `c0rnp0rn7.lua` | Current deployed version | Writes 8-field header, has LuaJIT patches | **REPLACED** by merged version |
| `vps_scripts/stats_discord_webhook.lua` | `send_webhook()` line 830 | Uses `%d` for timelimit | **MUST FIX** `%d` crash on fractional timelimit |

### 2.2 Bot Parser (Would Change)

| File | Function/Line | Current Role | Migration Impact |
|------|--------------|--------------|------------------|
| `bot/community_stats_parser.py:963-980` | Header parsing | Extracts 8 fields; field 9 handled if present (`actual_playtime_seconds`) | Verify graceful handling of 9-field headers |
| `bot/community_stats_parser.py:989` | `time_played_seconds` assignment | Sets to `round_time_seconds` (shared for all players) | Could use field 9 for more accurate round duration |
| `bot/community_stats_parser.py:996-998` | DPM calculation | Uses shared `round_time_seconds` | Could benefit from field 9 accuracy |

### 2.3 Bot Webhook Handler (May Change)

| File | Function/Line | Current Role | Migration Impact |
|------|--------------|--------------|------------------|
| `bot/ultimate_bot.py:3503-3559` | STATS_READY processing | Extracts webhook fields, stores metadata | No change needed unless webhook adds new fields |
| `bot/ultimate_bot.py:3703-3843` | `_build_round_metadata_from_map()` | Maps embed fields to metadata dict | Add mapping for any new webhook fields |
| `bot/ultimate_bot.py:4122-4341` | `_store_lua_round_teams()` | INSERT/UPSERT to `lua_round_teams` | Add columns if per-player time data added to webhook |

### 2.4 Bot Services (Would Change If Timing Overhaul Proceeds)

| File | Function | Current Role | Migration Impact |
|------|----------|--------------|------------------|
| `bot/services/session_graph_generator.py:504` | Headshot COALESCE | Uses `COALESCE(p.headshots, p.headshot_kills)` | Pre-existing bug, unrelated to timing but should fix |
| `bot/services/session_graph_generator.py:586-605` | Survival rate / denied playtime | Uses `time_played_seconds` and `time_dead_minutes` | Would benefit from more accurate timing data |
| `bot/services/session_timing_shadow_service.py` | Dual timing display | Computes OLD vs NEW timing from `lua_spawn_stats` | May need update to consume new header field 9 data |
| `bot/services/timing_comparison_service.py` | Timing comparison | Compares stats-file vs webhook timing | May need update for new header field |
| `bot/core/frag_potential.py:126-130` | FragPotential | Uses `time_alive_seconds` from `time_played - time_dead` | More accurate with better time sources |

### 2.5 Website API (Would Change)

| File | Function/Line | Current Role | Migration Impact |
|------|--------------|--------------|------------------|
| `website/backend/routers/api.py:4896-4909` | Advanced metrics | FragPotential, Survival Rate, Damage Efficiency | **PRE-EXISTING BUG**: Wrong formulas (separate from timing) |
| `website/backend/routers/api.py:5837` | Time alive SQL | `SUM(time_played_seconds) - SUM(time_dead_minutes * 60)` | Would benefit from more accurate source data |

### 2.6 Database Schema (Would Change)

| Table | Current State | Potential Migration |
|-------|---------------|---------------------|
| `lua_round_teams` | 24 columns; timing from webhook | May add per-player time columns if webhook expanded |
| `lua_spawn_stats` | 13 columns; spawn/death from webhook | Already has `dead_seconds`, `avg_respawn_seconds` |
| `player_comprehensive_stats` | 52 columns; `time_played_seconds` from header | No schema change needed for field 9 (parser just uses it better) |
| `rounds` | Has `actual_duration_seconds` from webhook | Could also store field 9 value from stats file header |

---

## 3. Docs vs Code Comparison Table

| # | Doc Claim / Requirement | Current Implementation Reality | Gap / Mismatch | Proposed Resolution |
|---|------------------------|-------------------------------|----------------|---------------------|
| 1 | **KNOWN_ISSUES.md**: "Planned: Lua Time Stats Overhaul" with 10 new per-player time fields in webhook | `stats_discord_webhook.lua` v1.6.1 has `lua_spawn_stats` with 5 fields (spawn_count, death_count, dead_seconds, avg_respawn, max_respawn). No per-player time_alive, time_played, denied_playtime, etc. | **LARGE GAP** - Only 5 of 10 planned fields exist. The overhaul described in KNOWN_ISSUES is NOT started. | Phase the overhaul: use what exists (spawn_stats) first, add remaining fields incrementally |
| 2 | **KNOWN_ISSUES.md**: "Write `-timestats.txt` files to gamestats/" | No such file writer exists in any Lua script | **MISSING** - Planned feature, not implemented | Defer to Phase 2; use webhook payload for new fields instead of separate file |
| 3 | **LUA_R2_MISSING_ROOT_CAUSE**: "Replace `%d` with `math.floor()` wrapping" | `vps_scripts/stats_discord_webhook.lua:830` still uses `%d` for timelimit | **NOT DEPLOYED** - Fix plan documented but code unchanged | Apply fix to webhook Lua before any other Lua changes |
| 4 | **LUA_R2_MISSING_ROOT_CAUSE**: "Wrap payload in `pcall`" | No `pcall` wrapping in `send_webhook()` function | **NOT DEPLOYED** - Same as above | Apply with the `%d` fix |
| 5 | **STATS_FORMULA_RESEARCH**: "Parser should use TAB[22] for time_played_seconds" | Parser extracts TAB[22] into `objective_stats['time_played_minutes']` but assigns `round_time_seconds` (header) to `player['time_played_seconds']` | **DESIGN CHOICE** - Comment at line 983 says "In stopwatch: everyone plays full round" | Use field 9 (from new Lua) for round duration; keep TAB[22] as per-player fallback for partial players |
| 6 | **c0rnp0rn-testluawithtimetracking.lua**: Uses Lua 5.3 operators | `c0rnp0rn7.lua` (deployed) has LuaJIT-compatible `bit.*` operators | **INCOMPATIBLE** - Test file cannot be deployed as-is on LuaJIT builds | Merge LuaJIT patches from c0rnp0rn7 into test file before deployment |
| 7 | **Closeout Report**: "et-stats-webhook.service must be disabled" | Service documented as active on game server | **UNKNOWN** - No evidence it was disabled | Verify via SSH and disable if still active |
| 8 | **TIMING_DATA_SOURCES**: "Recommended: lua_round_teams.actual_duration_seconds for round duration" | Bot parser still uses stats file header for round duration (`round_time_seconds`) | **ACCEPTABLE GAP** - Parser runs before webhook arrives; webhook joins later via `_link_lua_round_teams` | Parser uses what's available at parse time; shadow service corrects later |
| 9 | **TIMING_SHADOW_HANDOFF**: "Switch to NEW-only after 2 weeks if coverage stable" | `SHOW_TIMING_DUAL=true` was enabled Feb 18; 2-week window ends ~Mar 3 | **DECISION PENDING** - Window is still open | Check coverage metrics; make cutover decision after Mar 3 |
| 10 | **Pipeline Deep Dive**: "Deprecated watcher service creates overlapping triggers" | `et-stats-webhook.service` produces duplicate STATS_READY events | **OPERATIONAL RISK** - Duplicate processing wastes resources and can cause confusion | Disable as P0 before any other changes |
| 11 | **c0rnp0rn-testluawithtimetracking.lua**: Adds field 9 to stats header | Parser at line 963 already handles field 9 when present (`actual_playtime_seconds`) | **ALIGNED** - Parser ready for the new field | Confirm with test: parse a 9-field header file |
| 12 | **KNOWN_ISSUES.md**: "`time_played_seconds` for all players = round duration" | Confirmed at `community_stats_parser.py:989` | **KNOWN LIMITATION** - By design for stopwatch; wrong for partial players | New Lua header field 9 gives better round duration; TAB[22] gives per-player time. Use both. |

---

## 4. What's Aligned, Missing, Ambiguous, and Risky

### Aligned (Working as Documented)

- Parser handles 8-field and 9-field headers (field 9 = `actual_playtime_seconds`)
- Webhook pipeline stores to `lua_round_teams` + `lua_spawn_stats` correctly
- `round_id`-based joins work for timing consumers
- Shadow timing service provides dual OLD/NEW comparison
- R2 differential logic handles 26 R2-only fields correctly
- LuaJIT compatibility patches are documented and tested

### Missing (Not Yet Implemented)

- **R2 timelimit crash fix** in `stats_discord_webhook.lua` (planned, not deployed)
- **Merged c0rnp0rn with time tracking + LuaJIT patches** (two source files exist, not combined)
- **Per-player time fields in webhook** (only spawn_stats exist, not full time tracking)
- **`-timestats.txt` file writer** (planned in KNOWN_ISSUES, not started)
- **`proximity_reaction_metric` table** (endpoint exists as stub, schema missing)

### Ambiguous (Needs Decision)

- **Should field 9 replace `round_time_seconds` in parser?** The parser comment says stopwatch is correct, but field 9 would be more accurate for ALL modes.
- **Should per-player time go in webhook or stats file?** KNOWN_ISSUES plans it in webhook, but stats file already has TAB[22]. Dual source creates reconciliation burden.
- **When to cut over from dual timing to NEW-only?** 2-week window ends ~Mar 3; need coverage metrics.
- **Which Lua file is canonical?** `c0rnp0rn7.lua` is deployed with LuaJIT patches; test file has time tracking. Need to merge.

### Could Break If We Migrate

| Risk | Trigger | Impact | Mitigation |
|------|---------|--------|------------|
| Header field count mismatch | Deploy new Lua without parser verification | Parser rejects new stats files | Test with sample 9-field file first |
| LuaJIT crash | Deploy test Lua without bit.* patches | Stats file generation fails entirely | Merge LuaJIT patches BEFORE deployment |
| Round timing regression | Switch from header time to field 9 | DPM/FP calculations change for historical data | Use field 9 for NEW data only; don't recompute historical |
| Webhook + stats file timing disagreement | Both sources provide different durations for same round | Confusing display or shadow mismatch | Use each source self-consistently; document which source each display uses |
| `send_in_progress` deadlock | Deploy webhook fix but miss edge case in pcall | R2 webhook silently fails | Test with forced fractional timelimit |

---

*See companion docs:*
- *Research Synthesis: `docs/PIPELINE_TIMETRACKING_RESEARCH_SYNTHESIS.md`*
- *Next Steps Plan: `docs/PIPELINE_TIMETRACKING_NEXT_STEPS_PLAN.md`*
