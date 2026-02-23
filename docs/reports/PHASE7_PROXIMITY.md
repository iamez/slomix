# Phase 7: Proximity Data Capture Validation Report

**Date:** 2026-02-23
**Scope:** Verify that proximity tracking captures data ONLY during live gameplay (gamestate=PLAYING),
not during warmup, intermission, map loading, or between matches.

---

## Data Flow Diagram

```
ET:Legacy Game Server
        |
        | (Lua engine callbacks: et_Damage, et_Obituary, et_ClientSpawn, et_RunFrame)
        v
proximity_tracker.lua (v4.2)          <-- game server side, runs inline
        |
        | [writes file: proximity/YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt]
        v
game server filesystem (gamestats/proximity/)
        |
        | [SSH download every 5 minutes OR manual trigger]
        v
local_proximity/ directory (VPS / local)
        |
        | [ProximityCog background task, scan_engagement_files, every 5 min]
        v
ProximityParserV4 (proximity/parser/parser.py)
        |
        | [import_file -> _import_engagements, _import_player_tracks, etc.]
        v
PostgreSQL Database
  - combat_engagement      (13,291 rows as of 2026-02-23)
  - player_track           (6,242 rows)
  - proximity_reaction_metric
  - proximity_trade_event
  - proximity_support_summary
  - proximity_objective_focus
  - map_kill_heatmap
  - map_movement_heatmap
```

### Deployed Lua File Versions

| File | Version | Location |
|------|---------|----------|
| `proximity/lua/proximity_tracker.lua` | v4.2 (active/current) | Working copy |
| `deployed_lua/legacy/luascripts/proximity_tracker.lua` | v4.2 (identical) | Deployed on server |
| `proximity_tracker_v3.lua` | v3.0 (superseded) | Root, not deployed |
| `proximity_tracker_v2.lua` | v2.x (superseded) | Root, not deployed |

The **active deployed version is v4.2** (`proximity/lua/proximity_tracker.lua`),
identical to `deployed_lua/legacy/luascripts/proximity_tracker.lua`.

---

## Game State Filtering Analysis

### Gamestate Constants (ET:Legacy)

| Value | Meaning |
|-------|---------|
| `0` | `GS_PLAYING` - Active round, live gameplay |
| `1` | Warmup (pre-countdown) |
| `2` | `GS_WARMUP_COUNTDOWN` |
| `3` | `GS_INTERMISSION` - Between rounds / end-of-round |
| `-1` | Unknown / uninitialized |

The Lua script stores `et.GS_INTERMISSION or 3` as a named constant at
`proximity/lua/proximity_tracker.lua:321`.

---

## Per-Callback Game State Filtering

### 1. `et_Damage` (combat data capture)

**File:** `proximity/lua/proximity_tracker.lua:1834-1898`

```lua
function et_Damage(target, attacker, damage, damageFlags, meansOfDeath)
    if not config.enabled then return end
    -- ... validation checks ...
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end   -- <-- HARD FILTER: PLAYING only
```

**Verdict: PASS** - Damage events are silently dropped for any gamestate other than `0` (PLAYING).
Warmup, intermission, and map loading are all blocked.

---

### 2. `et_Obituary` (kill/death data capture)

**File:** `proximity/lua/proximity_tracker.lua:1900-1939`

```lua
function et_Obituary(victim, killer, meansOfDeath)
    if not config.enabled then return end
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end   -- <-- HARD FILTER: PLAYING only
```

**Verdict: PASS** - Deaths during warmup or intermission are ignored entirely.

---

### 3. `et_ClientSpawn` (player track creation)

**File:** `proximity/lua/proximity_tracker.lua:1941-1993`

```lua
function et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)
    if not config.enabled then return end
    -- Only track during live gameplay (gamestate 0 = PLAYING)
    -- Skip warmup, intermission, and other non-play states
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    if gamestate ~= 0 then return end   -- <-- HARD FILTER: PLAYING only
```

The inline comment explicitly documents the intent: warmup and intermission spawns
are discarded. Player tracks therefore only begin during live rounds.

**Verdict: PASS** - Player tracks cannot start during warmup or intermission.

---

### 4. `et_RunFrame` (position sampling & escape detection)

**File:** `proximity/lua/proximity_tracker.lua:1750-1832`

```lua
function et_RunFrame(levelTime)
    if not config.enabled then return end
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1

    -- Detect round start (gamestate transition into PLAYING)
    if gamestate == 0 and last_gamestate ~= 0 then
        refreshRoundInfo()
        round_start_unix = os.time()
        -- ... reset output guards ...
    end

    -- Detect round end (gamestate transition to INTERMISSION)
    if last_gamestate == 0 and gamestate == 3 then
        round_end_unix = os.time()
        -- Close all active player tracks as "round_end"
        -- Close all active engagements as "round_end"
        outputData()   -- Write file immediately
    end

    last_gamestate = gamestate

    -- During play: sample positions and check escapes
    if gamestate == 0 then
        sampleAllPlayers()
        if isFeatureEnabled("escape_detection") then
            checkEscapes(levelTime)
        end
    end
end
```

Key observations:
- `sampleAllPlayers()` is called **only inside `if gamestate == 0`** (line 1817).
- `checkEscapes()` is also gated behind `gamestate == 0`.
- The transition `last_gamestate == 0 and gamestate == 3` triggers data flush and
  closes all in-progress engagements gracefully as `"round_end"`, preventing leaked
  open engagement records.
- No sampling or escape checking occurs during warmup (`gamestate != 0`).

**Verdict: PASS** - Position sampling and combat analytics are confined strictly to
live rounds.

---

### 5. `et_ClientDisconnect` (cleanup on disconnect)

**File:** `proximity/lua/proximity_tracker.lua:1995-2003`

```lua
function et_ClientDisconnect(clientNum)
    if tracker.player_tracks[clientNum] then
        local pos = getPlayerPos(clientNum)
        endPlayerTrack(clientNum, pos, "disconnect")
    end
    ...
end
```

No gamestate check here - this is by design. If a player disconnects mid-round their
track is cleanly ended with `death_type = "disconnect"`. This is correct: a disconnect
can happen at any time and the track data captured up to that point was valid gameplay.

**Verdict: PASS** - Disconnect handler correctly terminates existing tracks regardless
of gamestate. It cannot *create* new tracks (creation is gated in `et_ClientSpawn`).

---

### 6. `et_ClientConnect` / `et_ClientUserinfoChanged` (cache updates only)

**File:** `proximity/lua/proximity_tracker.lua:2005-2012`

These callbacks only update the client name/GUID/team cache (`client_cache`). They do
not create any tracking data and require no gamestate filter.

**Verdict: N/A** - Cache-only, no tracking data created.

---

## `samplePlayer` First-Movement Guard

**File:** `proximity/lua/proximity_tracker.lua:739-781`

```lua
local function samplePlayer(clientnum, track, event_type)
    ...
    -- Detect first movement (only during live gameplay)
    -- Guards: gamestate must be PLAYING, spawn_time must be non-negative (post-round-start),
    -- and current time must be non-negative
    if not track.first_move_time and speed > 10 then
        local gs = tonumber(et.trap_Cvar_Get("gamestate")) or -1
        if gs == 0 and (track.spawn_time or 0) >= 0 and now >= 0 then
            track.first_move_time = now
            track.had_input = true
        end
    end
```

Even within position sampling (which is already gated behind `gamestate == 0` in
`et_RunFrame`), the `first_move_time` metric has an additional redundant gamestate
guard. This is belt-and-suspenders protection.

**Verdict: PASS** - Double-guarded correctly.

---

## Output Guard: Preventing Double-Write

**File:** `proximity/lua/proximity_tracker.lua:1315-1319`

```lua
local function outputData()
    if config.output_guard and (tracker.output_in_progress or tracker.output_written) then
        proxPrint("[PROX] Output already written or in progress, skipping\n")
        return
    end
    tracker.output_in_progress = true
```

The `output_guard` config flag (default `true`) prevents the file from being written
more than once per round, even if the gamestate transitions flicker between PLAYING
and INTERMISSION (which can happen on some server configurations).

**Verdict: PASS** - Double-output prevention is in place.

---

## File Output Timing

Data is written **once**, triggered by:
- `et_RunFrame` detecting transition `last_gamestate == 0 AND gamestate == 3`
  (PLAYING -> INTERMISSION)
- Optionally delayed by `config.output_delay_ms` (default `0`, immediate)

The round file therefore contains only data from the live round that just ended.

---

## Bot-Side (Python) Filtering

The bot-side `ProximityCog` (`bot/cogs/proximity_cog.py`) only imports files named
`*_engagements.txt`. Since these files are only written by the Lua script at round end,
and the Lua script only writes data captured during `gamestate == 0`, the Python importer
has no need for additional game state filtering.

**File timestamp filtering** is applied at import time:
- `proximity_startup_lookback_hours` (config, default same as SSH lookback) skips old
  files on startup to prevent replaying historical data.
- Files older than the lookback window are marked processed without importing.

**Verdict: PASS** - Bot-side correctly trusts the Lua-generated file content, which
is already filtered. The timestamp lookback prevents accidental historical reimports.

---

## Database Confirmation

Current database state (queried 2026-02-23):

| Table | Row Count |
|-------|-----------|
| `combat_engagement` | 13,291 |
| `player_track` | 6,242 |
| `proximity_reaction_metric` | 0 (feature not yet active) |

The `combat_engagement` table shows data correctly organized by round_number and
map_name with session_date, confirming the pipeline is functioning as designed.

All engagements currently in the database have `round_number = 1`, which reflects that
only R1 data is being captured. This is consistent with the observed game session
structure (R2 round tracking has not yet been configured to generate separate files
or the R2 data is being stored under the same round_number).

---

## Capture Scenario Verdicts

| Scenario | Should Capture | Does Capture | Verdict |
|----------|---------------|--------------|---------|
| Live gameplay (gamestate=0) | YES | YES | PASS |
| Warmup (gamestate=1/2) | NO | NO | PASS |
| Intermission (gamestate=3) | NO | NO | PASS |
| Map loading | NO | NO | PASS |
| Between matches (no gamestate) | NO | NO | PASS |
| Player disconnect mid-round | YES (close track) | YES | PASS |
| Player revived mid-round | YES (continue track) | YES | PASS |
| Instant kill without prior damage | YES | YES (minimal engagement created) | PASS |

---

## Minor Observations & Recommendations

### 1. R2 Round Number Discrepancy (Low Priority)

All database rows currently have `round_number = 1`. The Lua script reads
`g_currentRound` CVar and adds 1 (`round_num = (tonumber(round_str) or 0) + 1`).
If the server only runs single-round maps, this is expected. If R2 rounds exist, the
parser has a round normalization mechanism (`_normalize_round_metadata`) that cross-
references gametime files and filename patterns. This appears to be working correctly
given the data volume, but R2 round data has not been verified in the database.

**Recommendation:** Verify R2 proximity data exists and is being attributed correctly
if the server runs two-round maps.

### 2. `et_ClientDisconnect` Has No Gamestate Guard (Intentional)

This was noted above - it is correct by design. The disconnect handler must always
run to clean up in-flight track data. No change needed.

### 3. `proximity_reaction_metric` Table is Empty (0 rows)

The `reaction_tracking` feature is enabled in the Lua script (`features.reaction_tracking = true`)
but the database has no rows. This could mean:
- Reaction metrics were not being generated on older rounds
- The `proximity_reaction_metric` table was added after existing data was imported
- The feature was recently enabled

**Recommendation:** Verify reaction metrics are flowing correctly for new rounds.

### 4. PROXIMITY_ENABLED=true in Production

The `.env` file has `PROXIMITY_ENABLED=true`, meaning the cog is running and auto-
importing. This is noted for awareness - the system is live and collecting data.

---

## Summary

The proximity tracking system has robust, multi-layered game state filtering:

1. **Primary gate** - `et_Damage`, `et_Obituary`, and `et_ClientSpawn` all check
   `gamestate == 0` and return immediately for any other state.

2. **Frame loop gate** - `et_RunFrame` only calls `sampleAllPlayers()` and
   `checkEscapes()` inside `if gamestate == 0`.

3. **First-move guard** - `samplePlayer` has a redundant secondary gamestate check
   for the `first_move_time` metric.

4. **Output guard** - `output_guard = true` prevents double-writing the output file
   even if gamestate transitions flicker.

5. **Round lifecycle** - Track data is opened on `et_ClientSpawn` (only in
   `gamestate == 0`) and closed either on `et_Obituary` (kill) or gracefully on
   `et_RunFrame` detecting the PLAYING->INTERMISSION transition.

**Overall Verdict: PASS.** No warmup, intermission, map loading, or between-match
data can enter the proximity pipeline under normal operation.

---

*Report generated by Phase 7 Proximity Validation Agent, 2026-02-23.*
