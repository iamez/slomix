# Time Dead / Time Denied Pipeline Fix (2026-02-05)

## Why this was needed
- `time_dead_minutes` coming from Lua (R2-only field) was being overwritten in `bot/ultimate_bot.py` by recomputing from `time_dead_ratio * time_played`.
- The Lua `time_dead_ratio` for R2 is based on cumulative playtime, while we store *differential* time_played for R2. That mismatch caused inflated dead time and incorrect ratios in session summaries.
- `denied_playtime` (Lua seconds) is the authoritative “time denied” and should not be recomputed.

## Root cause
- `bot/ultimate_bot.py` recalculated `time_dead_minutes` from ratio and time_played_seconds, clobbering Lua’s raw minutes.
- Session graphs and summaries were indirectly using those incorrect values.

## Fixes applied
### 1) Preserve Lua’s raw time_dead_minutes
File: `bot/ultimate_bot.py`
- Prefer `objective_stats.time_dead_minutes` (Lua raw minutes).
- Normalize `time_dead_ratio` to percent and only back-fill missing fields.
- Keep existing warnings/validation; no ratio-based override anymore.

### 2) Use Lua raw values in session graphs
File: `website/backend/routers/api.py`
- `/sessions/{date}/graphs` now aggregates:
  - `time_dead_minutes` directly (raw)
  - `denied_playtime` directly (raw seconds)
- Advanced metrics now include:
  - `time_denied_raw_seconds`
  - `time_dead_raw_seconds`

### 3) Expose raw time dead in last session payload
File: `website/backend/routers/api.py`
- `/stats/last-session` now includes `time_dead_seconds_raw` per player (sum of `time_dead_minutes * 60`).
- Keeps capped `time_dead_seconds` for safety and display.

## UI note (map labels)
To avoid losing map-version info, map labels now keep prefixes like `etl_`, `sw_`, `et_`, and `_te`.

Files:
- `website/js/sessions.js`: `mapLabel()` no longer strips prefixes.
- `website/backend/routers/api.py`: player-round labels keep full map names (only truncate length).

## Validation checklist
- Run a live round, then check raw values:
  - `curl -s http://localhost:8000/api/diagnostics | python3 -m json.tool`
  - `curl -s http://localhost:8000/api/stats/last-session | python3 -m json.tool`
  - `curl -s http://localhost:8000/api/sessions/<date>/graphs | python3 -m json.tool`
- Confirm:
  - `time_dead_seconds_raw` aligns with Lua output
  - `denied_playtime` is in seconds (no ratio re-derivation)
  - UI shows map names with full prefixes

## Notes
- Historical rows inserted before this fix may still contain incorrect time_dead_minutes.
- New rounds should now store correct Lua-based time values.

## Additional fix: FragPotential now prefers raw dead time
Files:
- `bot/core/frag_potential.py`
- `bot/services/session_graph_generator.py`

Changes:
- `PlayerMetrics` now accepts `time_dead_minutes` / `time_dead_seconds` and recomputes `time_dead_ratio` when raw values exist.
- Session frag-potential analysis now sums `time_dead_minutes` and derives ratio from `time_played_seconds`.
- `calculate_frag_potential()` can use raw dead time (minutes/seconds) and clamps to time_played for safety.

Impact:
- FragPotential and playstyle detection no longer depend on potentially mismatched stored ratios.

## Validation endpoint added
File: `website/backend/routers/api.py`
- New endpoint: `GET /api/diagnostics/time-audit`
- Audits recent rows for:
  - dead > played
  - ratio mismatch (computed vs stored)
  - negative dead
  - ratio present without playtime
  - denied > played

Example:
- `curl -s "http://localhost:8000/api/diagnostics/time-audit?limit=250&ratio_diff=5" | python3 -m json.tool`

## Update: Keep raw Lua time fields for validation (2026-02-06)
File: `bot/community_stats_parser.py`
- Removed `time_dead_ratio`, `time_dead_minutes`, `denied_playtime` from `R2_ONLY_FIELDS`.
- Added `objective_stats_raw` snapshot for R1/R2 cumulative time values.
- Recomputed R2 `time_dead_ratio` using differential minutes to avoid ratio subtraction.
- Expanded TIME DEBUG logs to include raw R1/R2 values + differential.

This keeps raw values for validation and makes differential time fields consistent.

## Update: 3-way timing validation (Oksii-inspired) (2026-02-06)
We added a third timing anchor (filename timestamp) alongside stats file and Lua webhook.

**Why:** Oksii’s Lua emphasizes independent timing anchors (round_start/end + timestamps).  
We mirror that by comparing:
1) **Stats file duration** (header `actual_time`)  
2) **Lua webhook duration** (`lua_round_teams.actual_duration_seconds`)  
3) **Filename timestamp** (rounds `round_date + round_time`) as a proxy for round end

**Files updated:**
- `bot/services/timing_debug_service.py`
  - Adds a "Filename Timestamp" section to debug embeds.
  - Shows diffs vs Lua round end, wall-clock, warmup if present.
- `bot/services/timing_comparison_service.py`
  - Adds filename timestamp to the comparison embed (third source).

**How to use:**
- Enable timing debug channel (if not already).
- Check the embed for:
  - Stats vs Lua duration diff
  - File timestamp vs Lua round_end diff
  - Warmup + wall-clock values (if Lua data exists)

This gives us a 3‑way cross‑check even when one source is missing.

## Update: Per-player timing validation logs (2026-02-06)
File: `postgresql_database_manager.py`

We now log raw-vs-derived timing mismatches during insert:
- `time_played_minutes` from Lua vs derived minutes from `time_played_seconds`
- `time_dead_ratio` vs ratio derived from raw minutes
- `denied_playtime` > `time_played_seconds`
- ratio > 0 but `time_dead_minutes = 0`, or vice-versa

**Log marker:** `[TIME VALIDATION]`

Example:
```
[TIME VALIDATION] Player time_dead_ratio mismatch: raw_ratio=28.0% vs derived=12.5% ...
```

This doesn’t change data; it gives us a reliable trail for investigating anomalies.

## Update: Spawn tracking (Oksii-inspired) (2026-02-06)
We added per-player spawn/death tracking to the Lua webhook script so we can validate
dead time using **death→spawn intervals**.

**Lua script:** `vps_scripts/stats_discord_webhook.lua` (v1.6.0)

**What it tracks (per round):**
- `spawn_count`
- `death_count`
- `dead_seconds` (sum of death→spawn durations)
- `avg_respawn_seconds`
- `max_respawn_seconds`

**Storage:**
- A short summary is sent in the webhook field `Lua_SpawnSummary`.
- Full per-player stats are written into the gametime JSON (`meta.spawn_stats`).
- Bot ingests that JSON into the `lua_spawn_stats` table.

**DB Migration:**
- `migrations/008_add_lua_spawn_stats.sql`

This gives us an independent way to sanity-check `time_dead_minutes` from the stats file.
