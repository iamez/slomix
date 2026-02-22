# ET:Legacy Server & Data Pipeline Research
## For Round Correlation System Implementation

**Date**: 2026-02-22
**Purpose**: Document how ET:Legacy generates round data, so the correlation system is built on real understanding rather than guesswork.

---

## Table of Contents

1. [ET:Legacy Stopwatch Mode Architecture](#1-etlegacy-stopwatch-mode-architecture)
2. [Stats File Generation (c0rnp0rn7.lua)](#2-stats-file-generation-c0rnp0rn7lua)
3. [Discord Webhook (stats_discord_webhook.lua v1.6.2)](#3-discord-webhook-stats_discord_webhooklua-v162)
4. [Complete Round Lifecycle Timeline](#4-complete-round-lifecycle-timeline)
5. [Data Arrival Order & Timing](#5-data-arrival-order--timing)
6. [File Naming & match_id Implications](#6-file-naming--match_id-implications)
7. [The g_currentRound Inversion](#7-the-g_currentround-inversion)
8. [ET:Legacy Lua API Reference](#8-etlegacy-lua-api-reference)
9. [Implications for Correlation System](#9-implications-for-correlation-system)

---

## 1. ET:Legacy Stopwatch Mode Architecture

### Game Engine Level

ET:Legacy is a fork of Wolfenstein: Enemy Territory. In stopwatch mode (`g_gametype = GT_WOLF_STOPWATCH`):

- **Two teams** play the same map **twice** (R1 and R2), once on each side
- Winner is the team that **completes objectives faster**
- If both teams' defenses hold ("full hold"), the match is a **tie**
- **Team-switching is NOT allowed** during a stopwatch match

### Key Engine CVars

| CVar | Values | Purpose |
|------|--------|---------|
| `g_gametype` | 2 = Stopwatch | Game mode selector |
| `g_currentRound` | 0 or 1 | Round tracker (inverted - see Section 7) |
| `g_altStopwatchMode` | 0=ABBA, 1=ABAB | Team swap pattern |
| `g_nextTimeLimit` | "M:SS" | R1's completion time (for R2 comparison) |
| `g_intermissionTime` | 30 | Seconds between rounds |
| `g_intermissionReadyPercent` | 60 | % of players needed to ready-up |
| `gamestate` | GS_WARMUP, GS_WARMUP_COUNTDOWN, GS_PLAYING, GS_INTERMISSION | Current game phase |

### Source Code References

- `src/game/g_main.c` - Main game loop, round state management
- `src/game/g_match.c` - Match control, round sequencing, team mechanics
- `src/game/g_stats.c` - Statistics tracking, `G_BuildEndgameStats()`
- `src/game/g_local.h` - Structures, constants, `NO_STOPWATCH = 2` flag
- GitHub: https://github.com/etlegacy/etlegacy

### Key Engine Functions

- `BeginIntermission()` - Initiates round transition
- `MoveClientToIntermission()` - Moves players to spectator during intermission
- `ExitLevel()` - Has special `GT_WOLF_STOPWATCH` case for round sequencing
- `G_BuildEndgameStats()` - Compiles end-of-round awards (frags, accuracy, etc.)

---

## 2. Stats File Generation (c0rnp0rn7.lua)

### Overview

**CRITICAL**: ET:Legacy does NOT generate stats files natively. A Lua mod (`c0rnp0rn7.lua` aka "oksii-game-stats") running on the server handles ALL stats file creation.

**Location**: `deployed_lua/legacy/c0rnp0rn7.lua` (v3.0)
**Server path**: `/home/et/.etlegacy/legacy/luascripts/c0rnp0rn7.lua`

### How Stats Are Collected

The mod uses ET:Legacy's embedded Lua VM to hook into game events:

```lua
-- Initialization: et_InitGame() resets all tracking arrays
-- Continuous: et_RunFrame(levelTime) monitors game state every frame
-- Kill events: et_Obituary() tracks kills/deaths/gibs
-- Damage: et_Damage() accumulates damage given/received
-- Shutdown: et_ShutdownGame() saves stats if map changes unexpectedly
```

### Stats Collection Flow

1. `et_InitGame()` (line 164) - Resets all per-player arrays (killing_sprees, death_sprees, multikills, etc.)
2. `et_RunFrame()` (line 458) - Runs every server frame, calls `StoreStats()` every 5 seconds
3. `StoreStats()` - Iterates all connected players, reads `sess.*` fields via `et.gentity_get()`
4. On `GS_INTERMISSION` detection (line 469):
   - Sets 3-second delay (`saveDelay = levelTime + 3000`)
   - After delay, calls `SaveStats()` (line 499-501)

### SaveStats() Function (line 358-447)

```lua
function SaveStats()
    local mapname = et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_SERVERINFO), "mapname")
    local round = tonumber(et.trap_Cvar_Get("g_currentRound")) == 0 and 2 or 1
    local fileName = string.format("gamestats\\%s%s-round-%d.txt",
        os.date('%Y-%m-%d-%H%M%S-'), mapname, round)
    -- ...writes header + player stats to file
end
```

### File Format

**Filename**: `YYYY-MM-DD-HHMMSS-<mapname>-round-<N>.txt`
**Example**: `2026-02-22-213045-supply-round-1.txt`

**Header** (backslash-separated):
```
servername\mapname\config\round\defender_team\winner_team\timelimit\next_timelimit
```

**Player lines** (tab-separated, 40+ fields per player):
```
GUID_8char\name\rounds\team\weaponMask <TAB> damageGiven <TAB> damageReceived <TAB> ...
```

Fields include: damage_given, damage_received, team_damage, gibs, selfkills, teamkills, teamgibs, time_played, xp, killing_spree, death_spree, kill_assists, kill_steals, headshot_kills, objectives, multikills (2x-6x), and more.

### R2 Cumulative Stats Problem

**CRITICAL**: Round 2 stats files contain **CUMULATIVE** data (R1 + R2 combined). This is because the game engine's `sess.*` fields are cumulative across the entire map session and are NOT reset between rounds.

The bot's `community_stats_parser.py` handles this by:
1. Finding the matching R1 file (within 45-minute window)
2. Calculating `R2_only = R2_cumulative - R1` for each field
3. Attaching `r1_filename` to the R2 result for match_id generation

### et_ShutdownGame Fallback (line 449)

```lua
function et_ShutdownGame(restart)
    if restart == 0 then  -- map change (not round restart)
        if saved_stats == false and round_started == true then
            StoreStats()
            SaveStats()
        end
    end
end
```

This ensures stats are saved even if the map changes before intermission completes.

---

## 3. Discord Webhook (stats_discord_webhook.lua v1.6.2)

### Overview

A **second** Lua script running alongside c0rnp0rn7.lua that provides:
- **Instant notification** (~1 second after round end, vs 60s SSH polling)
- **Accurate surrender timing** (the stats file has a bug showing full map time)
- **Team composition capture** at exact round end
- **Pause tracking** with event-level timestamps
- **Surrender vote tracking** (who called, which team)
- **Match score tracking** (running win count)
- **Spawn/death statistics** per player

**Location**: `vps_scripts/stats_discord_webhook.lua`
**Server path**: `/home/et/.etlegacy/legacy/luascripts/stats_discord_webhook.lua`

### Configuration

```lua
local configuration = {
    discord_webhook_url = "https://discord.com/api/webhooks/...",
    enabled = true,
    send_delay_seconds = 0,  -- No delay (Lua reloads during map transitions)
    gametimes_enabled = true,
    gametimes_dir = "/home/et/.etlegacy/legacy/gametimes",
    spawn_tracking_enabled = true,
    spawn_check_interval_ms = 500,
    curl_retry = 3, curl_retry_delay = 1, curl_retry_max_time = 15
}
```

### Webhook Payload Format

Sends a Discord webhook with:
- **Content**: `"STATS_READY"`
- **Author**: `"ET:Legacy Stats"`
- **Embed fields**: All timing/team data (see below)
- **Footer**: `"Slomix Lua Webhook v1.6.2"`

### Data Fields Captured

| Field | Format | Description |
|-------|--------|-------------|
| `Lua_Playtime` | "847 sec" | Actual gameplay time (pauses excluded) |
| `Lua_Warmup` | "45 sec" | Pre-round warmup duration |
| `Lua_Pauses` | "2 (120 sec)" | Pause count + total seconds |
| `Lua_Pauses_JSON` | JSON array | `[{n, start, end, sec}, ...]` |
| `Lua_Timelimit` | "20 min" | Map time limit |
| `Lua_EndReason` | string | "surrender", "objective", "time_expired" |
| `Lua_WarmupStart` | Unix timestamp | Warmup phase start |
| `Lua_RoundStart` | Unix timestamp | GS_PLAYING transition |
| `Lua_RoundEnd` | Unix timestamp | GS_INTERMISSION transition |
| `Lua_SurrenderCaller` | GUID (32 chars) | Who called surrender vote |
| `Lua_SurrenderCallerName` | string | Name of surrender caller |
| `Lua_SurrenderTeam` | 1 or 2 | Which team surrendered (1=Axis, 2=Allies) |
| `Lua_AxisScore` | integer | Running match wins for Axis |
| `Lua_AlliesScore` | integer | Running match wins for Allies |
| `Axis_JSON` | JSON array | `[{"guid":"...", "name":"..."}, ...]` |
| `Allies_JSON` | JSON array | `[{"guid":"...", "name":"..."}, ...]` |
| `Lua_SpawnSummary` | string | "Players:X | Spawns:Y | AvgRespawn:Zs" |

### Delivery Method

```bash
# Async curl POST (fire-and-forget, runs in background)
curl -X POST \
  -H 'Content-Type: application/json' \
  --data-binary @{payload_file} {webhook_url} \
  --compressed --connect-timeout 2 --max-time 10 \
  --retry 3 --retry-delay 1 --retry-max-time 15 > /dev/null 2>&1 &
```

### Fallback: Gametime JSON Files

When `gametimes_enabled = true`, also writes JSON files to disk:
```
/home/et/.etlegacy/legacy/gametimes/gametime-<map>-R<N>-<timestamp>.json
```

These can be fetched via SSH if the webhook POST fails.

### match_id Generation in Webhook

The webhook generates match_id differently than the stats file:
```lua
local timestamp = datetime.fromtimestamp(round_end)
local match_id = timestamp.strftime('%Y-%m-%d-%H%M%S')
```
This uses the **round END time**, not the same timestamp as the stats filename. This is why lua_round_teams match_ids don't naturally align with rounds table match_ids.

---

## 4. Complete Round Lifecycle Timeline

### Stopwatch Match: R1 + R2

```
T=0s        MAP LOADS
            ├── et_InitGame(levelTime, randomSeed, restart=0) fires
            ├── c0rnp0rn7: resets all tracking arrays
            ├── stats_discord_webhook: records warmup_start_unix
            └── gamestate = GS_WARMUP

T=~30s      WARMUP ENDS, ROUND 1 STARTS
            ├── gamestate → GS_WARMUP_COUNTDOWN → GS_PLAYING
            ├── webhook: round_start_unix = os.time()
            ├── webhook: warmup_seconds = round_start_unix - warmup_start_unix
            └── c0rnp0rn7: begins frame-by-frame stat collection

T=30-900s   ROUND 1 GAMEPLAY
            ├── c0rnp0rn7: StoreStats() every 5 seconds
            ├── webhook: track_spawns() every 500ms
            ├── webhook: detect_pause() monitors frame gaps > 2 sec
            └── All kills/deaths/damage accumulated in sess.* fields

T=~900s     ROUND 1 ENDS
            ├── gamestate → GS_INTERMISSION
            ├── [WEBHOOK - INSTANT]: ~1 second
            │   ├── Detects GS_INTERMISSION in et_RunFrame()
            │   ├── round_end_unix = os.time()
            │   ├── collect_team_data() snapshots Axis/Allies
            │   ├── Async curl POST to Discord webhook
            │   └── Optional: write gametime-<map>-R1-<ts>.json
            │
            ├── [STATS FILE - 3 SECOND DELAY]:
            │   ├── c0rnp0rn7 detects GS_INTERMISSION
            │   ├── R1: saves per-player damage to cvars (line 471-479)
            │   ├── saveDelay = levelTime + 3000 (3 second wait)
            │   ├── After delay: SaveStats() writes stats file
            │   └── File: YYYY-MM-DD-HHMMSS-<map>-round-1.txt
            │
            └── [BOT RECEIVES WEBHOOK - ~1 second]:
                ├── Discord delivers to WEBHOOK_TRIGGER_CHANNEL
                ├── Bot on_message() → _handle_webhook_trigger()
                ├── Validates channel/webhook ID/username
                ├── Parses embed fields into round_metadata
                ├── Queues as _pending_round_metadata
                └── _store_lua_round_teams() → lua_round_teams table

T=~930s     INTERMISSION (30 seconds default)
            ├── Players see scoreboard
            ├── Engine: g_intermissionReadyPercent check
            └── Teams prepare for side swap

T=~960s     ROUND 2 STARTS
            ├── et_InitGame(levelTime, randomSeed, restart=1) fires
            │   └── restart=1 means map_restart (R2 starting), NOT new map
            ├── c0rnp0rn7: resets tracking arrays for R2
            ├── webhook: resets state for R2
            ├── Teams have swapped sides
            └── gamestate → GS_WARMUP → GS_PLAYING

            NOTE: sess.* fields are NOT reset - they're CUMULATIVE
            This is why R2 stats files contain R1+R2 data.

T=960-1800s ROUND 2 GAMEPLAY
            └── Same tracking as R1

T=~1800s    ROUND 2 ENDS (or surrender earlier)
            ├── Same webhook + stats file flow as R1
            ├── Stats file: YYYY-MM-DD-HHMMSS-<map>-round-2.txt
            │   └── Contains CUMULATIVE R1+R2 stats
            │
            ├── [SSH POLLING - ~30-60 seconds]:
            │   ├── endstats_monitor polls every 60 seconds
            │   ├── Downloads new files from /gamestats/ via SCP
            │   ├── Stores in bot/local_stats/
            │   └── Triggers community_stats_parser.py
            │
            └── [PARSER - R2 Differential]:
                ├── Finds matching R1 file (45-min window)
                ├── Calculates R2_only = R2_cumulative - R1
                ├── Attaches r1_filename to result
                └── Passes to postgresql_database_manager.py for import

T=~1850s    MAP CHANGES
            ├── et_ShutdownGame(restart=0) fires
            └── Next map loads
```

---

## 5. Data Arrival Order & Timing

For a single round, data arrives from multiple sources at different times:

| Source | Arrival Time | Data | Stored In |
|--------|-------------|------|-----------|
| **Lua Webhook** | ~1 sec after round end | Timing, teams, surrender info | `lua_round_teams`, `lua_spawn_stats` |
| **Gametime JSON** (fallback) | Same as webhook | Same as webhook | Same tables |
| **Stats file** (via SSH) | ~30-60 sec after round end | Per-player stats (50+ fields) | `rounds`, `player_comprehensive_stats` |
| **Endstats file** (via SSH) | ~30-60 sec after round end | Awards, VS stats | `round_awards`, `round_vs_stats` |

### Arrival Order (typical):

```
1. Webhook arrives     (T + 1s)   → lua_round_teams populated
2. Stats file polled   (T + 60s)  → rounds + player_comprehensive_stats populated
3. Endstats file polled (T + 60s) → round_awards + round_vs_stats populated
```

### Arrival Order (webhook fails):

```
1. Gametime JSON polled (T + 60s) → lua_round_teams populated
2. Stats file polled    (T + 60s) → rounds + player_comprehensive_stats populated
3. Endstats file polled (T + 60s) → round_awards + round_vs_stats populated
```

---

## 6. File Naming & match_id Implications

### Stats File Naming

Generated by `c0rnp0rn7.lua` at line 363:
```lua
local fileName = string.format("gamestats\\%s%s-round-%d.txt",
    os.date('%Y-%m-%d-%H%M%S-'), mapname, round)
```

**Result**: `2026-02-22-213045-supply-round-1.txt`

**Key insight**: The timestamp comes from `os.date()` called at the moment `SaveStats()` runs (3 seconds into intermission). R1 and R2 get **different timestamps** because they're saved at different times.

### How match_id Should Work

For R1 and R2 to share the same match_id:
- **R1 match_id**: `{R1_date}-{R1_time}` (e.g., `2026-02-22-213045`)
- **R2 match_id**: Also `{R1_date}-{R1_time}` (R2 inherits R1's timestamp)

The parser handles this: `community_stats_parser.py` line 563 attaches `r1_filename` to R2 results. `ultimate_bot.py` line 1744-1755 extracts R1's timestamp from it.

### The Broken Path (postgresql_database_manager.py)

Line 2112: `match_id = filename.replace('.txt', '')`

This produces:
- R1: `2026-02-22-213045-supply-round-1` (unique)
- R2: `2026-02-22-214530-supply-round-2` (unique, DIFFERENT from R1)

**Result**: R1 and R2 never share the same match_id → they can't be correlated.

### The Working Path (ultimate_bot.py)

Lines 1744-1755 correctly use R1's timestamp:
```python
if stats_data.get('r1_filename'):
    r1_filename = stats_data['r1_filename']
    r1_parts = r1_filename.split("-")
    r1_date = "-".join(r1_parts[:3])
    r1_time = r1_parts[3] if len(r1_parts) > 3 else "000000"
    match_id = f"{r1_date}-{r1_time}"
```

**Result**: Both R1 and R2 get `2026-02-22-213045` → they share match_id.

### Timestamp Differences Between Sources

| Source | Timestamp | Based On |
|--------|-----------|----------|
| Stats filename | `os.date()` at SaveStats() | Server clock at file write time |
| Webhook `Lua_RoundEnd` | `os.time()` at GS_INTERMISSION | Server clock at round end |
| Gametime filename | Webhook's round_end_unix | Same as webhook |

The stats file timestamp and webhook timestamp differ by ~3 seconds (the `saveDelay`). This is why the bot can't naively match them by timestamp.

---

## 7. The g_currentRound Inversion

### The Confusing Part

In `c0rnp0rn7.lua` line 362:
```lua
local round = tonumber(et.trap_Cvar_Get("g_currentRound")) == 0 and 2 or 1
```

This means:
- `g_currentRound = 0` → file gets `round-2` in filename
- `g_currentRound = 1` → file gets `round-1` in filename

### Why It's Inverted

ET:Legacy uses `g_currentRound` to track the **stopwatch swap state**:
- `g_currentRound = 1` → "We are in the first round" (teams in initial positions)
- `g_currentRound = 0` → "We are in the second round" (teams have swapped)

The Lua mod inverts this for the filename because from the players' perspective:
- First half played = Round 1 (file should say round-1)
- Second half played = Round 2 (file should say round-2)

### How et_InitGame Reads It

In `c0rnp0rn7.lua` line 170:
```lua
round = tonumber(et.trap_Cvar_Get("g_currentRound")) --if 1 then round 2
```

The comment `--if 1 then round 2` confirms the inversion: when the engine says `g_currentRound=1`, the mod considers this as preparing for/being in round 2.

### Impact on Correlation

When `et_InitGame` fires with `restart=1` (round 2 starting):
- `g_currentRound` is already set to 0 (swap applied)
- The mod reads 0 and writes `round-2` in the filename
- This is **correct** - the second round file gets `round-2`

---

## 8. ET:Legacy Lua API Reference

### Callbacks Used by Our Mods

| Callback | Parameters | When Fired |
|----------|-----------|------------|
| `et_InitGame(levelTime, randomSeed, restart)` | restart: 0=new map, 1=round restart | Map load or round transition |
| `et_RunFrame(levelTime)` | levelTime: ms since map start | Every server frame |
| `et_ShutdownGame(restart)` | restart: 0=map change, 1=round restart | Map unload |
| `et_ClientConnect(clientNum, firstTime, isBot)` | | Player connects |
| `et_ClientDisconnect(clientNum)` | | Player disconnects |
| `et_ClientBegin(clientNum)` | | Player enters gameworld |
| `et_ClientCommand(clientNum, command)` | Return 1 to block | Player command (e.g., surrender vote) |
| `et_ClientUserinfoChanged(clientNum)` | | Name/config change |
| `et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)` | | Player spawns |
| `et_Obituary(victim, attacker, meansOfDeath)` | | Player dies |
| `et_Damage(target, attacker, damage, damageFlags, meansOfDeath)` | | Damage dealt |

### Key Functions

| Function | Purpose |
|----------|---------|
| `et.trap_Cvar_Get(name)` | Read cvar value |
| `et.trap_Cvar_Set(name, value)` | Set cvar value |
| `et.trap_GetConfigstring(index)` | Get server config string |
| `et.Info_ValueForKey(infostring, key)` | Parse key from info string |
| `et.gentity_get(entNum, field)` | Read entity/player field |
| `et.gentity_get(entNum, "sess.kills")` | Player kill count |
| `et.gentity_get(entNum, "sess.deaths")` | Player death count |
| `et.gentity_get(entNum, "sess.damage_given")` | Player damage dealt |
| `et.gentity_get(entNum, "sess.sessionTeam")` | Current team (1=Axis, 2=Allies) |
| `et.gentity_get(entNum, "sess.aWeaponStats", idx)` | Weapon stats [shots, deaths, headshots, hits, kills] |
| `et.trap_FS_FOpenFile(path, mode)` | Open file for writing |
| `et.trap_FS_Write(data, len, handle)` | Write to file |
| `et.trap_FS_FCloseFile(handle)` | Close file |
| `et.trap_Milliseconds()` | Current level time (ms) |
| `et.RegisterModname(name)` | Register mod for identification |

### Gamestate Constants

| Constant | Value | Meaning |
|----------|-------|---------|
| `et.GS_WARMUP` | (varies) | Pre-round warmup |
| `et.GS_WARMUP_COUNTDOWN` | (varies) | Countdown before round starts |
| `et.GS_PLAYING` | (varies) | Active gameplay |
| `et.GS_INTERMISSION` | (varies) | Between rounds or end of match |

### Player Session Fields (via `et.gentity_get`)

| Field | Type | Description |
|-------|------|-------------|
| `sess.kills` | int | Total kills |
| `sess.deaths` | int | Total deaths |
| `sess.gibs` | int | Total gibs |
| `sess.self_kills` | int | Self-kills |
| `sess.team_kills` | int | Team kills |
| `sess.team_gibs` | int | Team gibs |
| `sess.damage_given` | int | Damage dealt |
| `sess.damage_received` | int | Damage taken |
| `sess.team_damage_given` | int | Team damage dealt |
| `sess.team_damage_received` | int | Team damage taken |
| `sess.time_axis` | int | Time on Axis |
| `sess.time_allies` | int | Time on Allies |
| `sess.time_played` | int | Total time played |
| `sess.sessionTeam` | int | Current team (1=Axis, 2=Allies) |
| `sess.aWeaponStats[N]` | int[5] | Per-weapon [shots, deaths, headshots, hits, kills] |
| `sess.skill[N]` | int | Skill levels |

**NOTE**: All `sess.*` fields are **CUMULATIVE** across the entire map session. They are NOT reset between R1 and R2 in stopwatch mode. This is why R2 stats files contain R1+R2 data.

---

## 9. Implications for Correlation System

### What We Now Know

1. **Stats files are generated by Lua, not the engine** - `c0rnp0rn7.lua` writes files using `et.trap_FS_*` functions
2. **R1 and R2 get different timestamps** - because `SaveStats()` runs at different times
3. **The webhook arrives first** (~1s) and the stats file arrives later (~30-60s via SSH)
4. **Webhook match_id ≠ stats file match_id** - webhook uses round_end_unix, stats uses os.date() at write time (3s difference)
5. **R2 stats are cumulative** - parser subtracts R1 to get R2-only values
6. **The parser attaches r1_filename to R2 results** - this is how R1+R2 share match_id

### Correlation Challenges

| Challenge | Description | Solution |
|-----------|-------------|----------|
| **Different timestamps** | Webhook, stats file, and endstats all have slightly different timestamps | Match by map_name + round_number within time window |
| **Webhook arrives before stats** | lua_round_teams row exists before rounds row | UPSERT pattern - create correlation on first arrival, update on subsequent |
| **Broken match_ids** | postgresql_database_manager.py uses filename as match_id | Fix Phase 1 of plan |
| **g_currentRound confusion** | 0=R2, 1=R1 in engine terms | Already handled by c0rnp0rn7.lua's inversion |

### What the Correlation Service Needs to Handle

1. **Webhook arrives first** → Create correlation with `has_r1_lua_teams=TRUE`, `status=pending`
2. **Stats file arrives** → Update correlation with `has_r1_stats=TRUE`, link `r1_round_id`
3. **If both R1+R2 stats arrive** → Set `status=complete`
4. **Endstats arrives** → Update correlation with `has_r1_endstats=TRUE`
5. **Match key**: Use `match_id` (date-time format) + `map_name` for correlation lookup

### Validation Queries (Post-Implementation)

```sql
-- Verify new match_ids are correct format
SELECT match_id, round_number, map_name
FROM rounds
WHERE round_date >= '2026-02-23'
ORDER BY created_at DESC LIMIT 20;

-- Verify R1+R2 pairs share match_id
SELECT match_id, COUNT(*), array_agg(round_number ORDER BY round_number)
FROM rounds
WHERE round_date >= '2026-02-23'
GROUP BY match_id
HAVING COUNT(*) >= 2;

-- Check correlation completeness
SELECT status, COUNT(*)
FROM round_correlations
GROUP BY status;
```

---

## External References

- [ET:Legacy GitHub](https://github.com/etlegacy/etlegacy)
- [ET:Legacy Lua API Documentation](https://etlegacy-lua-docs.readthedocs.io/en/latest/)
- [ET:Legacy Lua API - Callbacks](https://etlegacy-lua-docs.readthedocs.io/en/latest/callbacks.html)
- [ET:Legacy Lua API - Fields](https://etlegacy-lua-docs.readthedocs.io/en/latest/fields.html)
- [ET:Legacy CVars Reference](https://etlegacy.readthedocs.io/en/latest/cvars.html)
- [ET:Legacy Lua Scripts Repo](https://github.com/etlegacy/etlegacy-lua-scripts)
- [ET:Legacy Game Manual](https://etlegacy.readthedocs.io/en/latest/manual.html)

---

## Local Codebase References

| File | Purpose |
|------|---------|
| `deployed_lua/legacy/c0rnp0rn7.lua` | Stats file generator (v3.0) |
| `vps_scripts/stats_discord_webhook.lua` | Discord webhook (v1.6.2) |
| `bot/community_stats_parser.py` | R2 differential parser |
| `bot/ultimate_bot.py` | Webhook handler, SSH monitor, data pipeline |
| `postgresql_database_manager.py` | DB import (match_id bug at line 2112) |
| `tools/schema_postgresql.sql` | DB schema (41 tables) |
| `docs/reference/TIMING_DATA_SOURCES.md` | Timing data comparison |
| `docs/DATA_PIPELINE.md` | Full pipeline documentation |
| `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` | Comprehensive system guide |
