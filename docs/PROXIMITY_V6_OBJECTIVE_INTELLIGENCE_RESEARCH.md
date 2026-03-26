# Proximity v6.0: Objective Intelligence — Research Document

**Date**: 2026-03-24
**Contributors**: Seareal (idea), Aciz (engine confirmation), c0rnn (objtrack.lua reference)
**Status**: Research Complete — Ready for Implementation Design

---

## Table of Contents

1. [Origin & Requirements](#1-origin--requirements)
2. [ET:Legacy Lua API — Objective Capabilities](#2-etlegacy-lua-api--objective-capabilities)
3. [Reference Implementation: c0rnn objtrack.lua](#3-reference-implementation-c0rnn-objtracklu)
4. [Reference Implementation: Oksii game-stats-web.lua](#4-reference-implementation-oksii-game-stats-weblua)
5. [ET:Legacy Engine Source Analysis](#5-etlegacy-engine-source-analysis)
6. [Our Existing Infrastructure (Proximity v5.0)](#6-our-existing-infrastructure-proximity-v50)
7. [Map Objective Taxonomy](#7-map-objective-taxonomy)
8. [Feasibility Matrix](#8-feasibility-matrix)
9. [Design Concepts for v6.0](#9-design-concepts-for-v60)
10. [Links & References](#10-links--references)

---

## 1. Origin & Requirements

### Discord conversation (2026-03-24, ~20:50)

**Seareal** asked:
1. Can we know if a player is next to a moving objective (tank/truck)?
2. Can we know when a player carries documents?
3. Can we detect if an opponent fragged a flag/doc carrier, and did it lead to a secure?
4. How far did someone push the tank on Goldrush?
5. For Radar: how far did someone carry parts? Halfway? Fullway? Was it taken back immediately?

**Aciz** confirmed: "carrying obj is just a playerstate field (`powerups[PW_RED/BLUEFLAG]`), I guess you can track when a player gets them and log positions each frame to count total distance"

**c0rnn** shared: https://github.com/x0rnn/etlegacy-lua-scripts/blob/master/objtrack.lua — "Za tank, truck itd. ne vem. Za obj pa je objtrack.lua"

### External references shared:
- ET:Legacy Lua docs: https://etlegacy-lua-docs.readthedocs.io/en/latest/standard.html
- Oksii's configs: https://github.com/Oksii/legacy-configs/tree/main/luascripts

---

## 2. ET:Legacy Lua API — Objective Capabilities

### 2.1 Carrier Detection (CONFIRMED)

```lua
-- PW_REDFLAG = 5 (Axis objective), PW_BLUEFLAG = 6 (Allied objective)
local carrying = tonumber(et.gentity_get(clientNum, "ps.powerups", 5)) or 0
if carrying > 0 then
    -- Player is carrying Axis objective (docs, gold, radar parts, keycard, etc.)
    -- Engine sets value to INT_MAX (never expires)
end
```

**Works for ALL carry objectives**: documents, gold crates, radar parts, keycards, relics, etc.

### 2.2 Tank/Truck Entity Access

```lua
-- Find vehicles by scanning entities 64-1023
for i = 64, 1023 do
    local classname = et.gentity_get(i, "classname")
    if classname == "script_mover" then
        local name = et.gentity_get(i, "scriptName")     -- "tank", "truck"
        local pos = et.gentity_get(i, "r.currentOrigin")  -- vec3 {x, y, z}
        local health = et.gentity_get(i, "health")
        local mounted = et.gentity_get(i, "tankLink")     -- clientNum or -1
    end
end

-- Movement detection via trajectory
local traj = et.gentity_get(tankEnt, "s.pos")
local is_moving = traj.trType ~= 0  -- 0 = TR_STATIONARY

-- Mounted player detection (bidirectional)
local player_in_tank = et.gentity_get(tankEnt, "tankLink")   -- returns clientNum
local tank_of_player = et.gentity_get(clientNum, "tankLink")  -- returns tank entNum
```

**EF_TAGCONNECT = EF_MOUNTEDTANK = 0x8000** — same flag! Cannot distinguish mounted from tag-connected.

### 2.3 Objective Events via et_Print

| Message | Source | Event |
|---------|--------|-------|
| `Item: <clientNum> team_CTF_redflag` | g_items.c:740 | Player picked up Axis objective |
| `Item: <clientNum> team_CTF_blueflag` | g_items.c:740 | Player picked up Allied objective |
| `legacy popup: ^7allies^7 stole "Documents"` | g_script.c:740 | Steal announcement |
| `legacy popup: ^7axis^7 returned "Documents"` | g_script.c:745 | Return announcement |
| `legacy announce: "^7Allied team has transmitted..."` | g_script_actions.c:3869 | Secure/deliver (NO player ID!) |
| `Dynamite_Plant: <clientNum> <trackName>` | g_weapon.c:2131 | Dynamite planted |
| `Dynamite_Diffuse: <clientNum> <trackName>` | g_weapon.c:2332 | Dynamite defused (engine typo!) |
| `Objective_Destroyed: <clientNum> <trackName>` | g_missile.c:437 | Objective destroyed |
| `Repair: <clientNum>` | g_weapon.c:1227 | Construction complete (NO track name!) |

### 2.4 Callbacks Available

| Callback | Fires When | Relevant For |
|----------|-----------|--------------|
| `et_RunFrame(levelTime)` | Every server frame (~50Hz) | Position polling, powerup checking |
| `et_Print(text)` | Server console print | Objective event detection |
| `et_Obituary(target, attacker, mod)` | Player killed | Carrier kill detection |
| `et_Damage(target, attacker, dmg, flags, mod)` | Player damaged | NOT for entity damage! |
| `et_ClientSpawn(clientNum, revived, ...)` | Player spawns | Spawn tracking |
| `et_MountedMGFire(clientNum)` | Tank MG fired | Vehicle engagement |

### 2.5 Key Entity Fields

| Field | Type | Access | Notes |
|-------|------|--------|-------|
| `ps.powerups` | int_array | rw | Index 5=PW_REDFLAG, 6=PW_BLUEFLAG |
| `ps.origin` | vec3 | rw | Player position |
| `ps.eFlags` | int | ro | 0x8000 = EF_TAGCONNECT/MOUNTEDTANK |
| `ps.velocity` | vec3 | rw | Player movement velocity |
| `r.currentOrigin` | vec3 | rw | Entity world position (non-clients) |
| `s.pos` | trajectory | rw | trType, trBase, trDelta, trDuration |
| `tankLink` | entity | rw | Bidirectional player↔tank link |
| `tagParent` | entity | rw | Parent entity for tag attachment |
| `health` | int | rw | Entity health |
| `classname` | string | rw | Entity type identifier |
| `scriptName` | string | ro | Map script name (e.g. "tank") |
| `s.eType` | int | rw | ET_MOVER=4, ET_CONSTRUCTIBLE=33 |

### 2.6 Data Output Options

- **File I/O**: `et.trap_FS_FOpenFile/Write/Close` (our current approach)
- **LuaSQL SQLite3**: Built into ET:Legacy
- **Standard Lua io**: `io.open()` works with absolute paths
- **No native HTTP** — must use file I/O or `os.execute()`

---

## 3. Reference Implementation: c0rnn objtrack.lua

**Source**: https://github.com/x0rnn/etlegacy-lua-scripts/blob/master/objtrack.lua
**Lines**: 1,369 | **Maps**: 26 | **Output**: Real-time chat messages only

### Architecture

3 callbacks: `et_Print` (main detection), `et_Obituary` (carrier death cleanup), `et_ClientDisconnect` (cleanup)

### Detection Method

- **Pickup**: Intercept `"team_CTF_redflag"` in et_Print, extract clientNum, check `sess.sessionTeam`
  - Attacking team touching flag = STEAL
  - Defending team touching flag = RETURN
- **Secure**: Match map-specific announce strings, iterate carriers, check `ps.powerups[5]==0` to find who delivered
- **Death**: Remove from carrier tables in et_Obituary

### Carrier State

```lua
goldcarriers = {}       -- {[clientNum] = true}
goldcarriers_id = {}    -- ordered list for iteration
doccarriers = {}
doccarriers_id = {}
objcarriers = {}
objcarriers_id = {}
```

### Phase Tracking for Multi-Objective Maps

| Map | Phases | Mechanism |
|-----|--------|-----------|
| radar | 2 simultaneous (East + West parts) | `firstflag`/`secondflag` booleans |
| goldrush/pirates | 2 sequential (1st + 2nd crate) | `firstflag` + carrier count |
| frostbite | 2 sequential (Supply → Deciphered) | `second_obj` boolean |
| decay | 3 sequential (Codes → Gold 1 → Gold 2) | `second_obj` + `firstflag` |
| etl_warbell | 4 sequential (Book → Shoe → Chest → Sword) | `second_obj` + `third_obj` + `fourth_obj` |

### Reversed Team Maps

- `et_ice`, `warbell`, `etl_warbell`: Axis attacks, uses `team_CTF_blueflag` instead of redflag

### Maps Covered (26)

radar, goldrush, frostbite, missile, sp_delivery, sw_goldrush_te, bremen_b3, adlernest, et_beach, venice, library_b3, pirates, karsiah_te2, karsiah_te3, et_ufo_final, sos_secret_weapon, falkenstein_b3, decay, te_escape2, radar_phx_b_3, et_village, 1944_beach, et_brewdog, et_ice, warbell, etl_warbell

### Limitations

- No tank/truck/vehicle tracking
- No persistence (in-memory only, resets per map)
- No statistics or distance tracking
- Hardcoded per-map logic (~1370 lines of if/else)
- No GUID tracking (uses slot IDs)

---

## 4. Reference Implementation: Oksii game-stats-web.lua

**Source**: https://github.com/Oksii/legacy-configs/blob/main/luascripts/game-stats-web.lua
**Lines**: 3,068 (v1.2.7) | **Config**: config.toml (761 lines, 17 maps) | **Output**: JSON → HTTP API

### 11 Objective Event Types

| Event | Detection Method | Attribution |
|-------|-----------------|-------------|
| `obj_taken` | et_Print: `legacy popup:` steal_pattern + `Item:` within 1000ms | Direct (clientNum from Item message) |
| `obj_secured` | et_Print: text with "secure"/"escap"/"transmit" matching secured_pattern | Carrier state lookup |
| `obj_returned` | et_Print: `legacy popup:` matching return_pattern | Carrier state (attributed to carrier, not returner) |
| `obj_carrierkilled` | et_Obituary: check if victim is in carrier state | Direct (victim=carrier, killer stored in data) |
| `obj_flagcaptured` | et_Print: `legacy announce:` matching flag_pattern | Coordinate proximity (nearest player within 500u) |
| `obj_escort` | et_Print: `legacy announce:` matching escort_pattern | Coordinate proximity |
| `obj_misc` | et_Print: `legacy announce:` matching misc_pattern | Coordinate proximity |
| `obj_planted` | et_Print: `Dynamite_Plant:` message | Direct (clientNum in message) |
| `obj_destroyed` | et_Print: `Objective_Destroyed:` or announce matching destruct_pattern | Planter GUID → single covert ops fallback → unattributed |
| `obj_defused` | et_Print: `Dynamite_Diffuse:` message | Direct (clientNum in message) |
| `obj_repaired` | et_Print: `Repair:` message + `check_recent_construction()` within 2000ms | Direct (clientNum) + announce correlation for name |

### Carrier Time Tracking

```lua
-- Per-frame in trackPlayerStanceAndMovement():
local redFlagTime = tonumber(et.gentity_get(clientNum, "ps.powerups", 5)) or 0
local blueFlagTime = tonumber(et.gentity_get(clientNum, "ps.powerups", 6)) or 0
if redFlagTime > 0 or blueFlagTime > 0 then
    stanceStats.in_objcarrier = stanceStats.in_objcarrier + (timeDelta / 1000)
end
```

**Does NOT track carrier position or distance** — only seconds.

### Escort Time Tracking

```lua
local isVehicleConnected = (eFlags & 0x00008000) ~= 0  -- EF_TAGCONNECT
if isVehicleConnected then
    stanceStats.in_vehiclescort = stanceStats.in_vehiclescort + (timeDelta / 1000)
end
```

**Does NOT track tank position or distance** — only seconds.

### Dynamic Flag Coordinate Detection

```lua
-- At map init: scan entities 64-1021 for team_WOLF_checkpoint
for i = 64, 1021 do
    if et.gentity_get(i, "classname") == "team_WOLF_checkpoint" then
        local coords = getEntityCoordinates(i)
        -- Store as flag_coordinates for proximity attribution
    end
end
```

### Per-Map Config (config.toml structure)

```toml
[maps.adlernest.objectives.documents]
steal_pattern = "allies stole \"the documents\""
secured_pattern = "allied team has transmitted the documents"
return_pattern = "axis returned the documents"

[maps.supply.escort.truck]
escort_pattern = "allies have escaped with the gold crate"
escort_coordinates = "2720 1376 192"

[maps.supply.misc.crane_controls]
misc_pattern = "allies have used the crane"
misc_coordinates = "656 -1360 372"
```

### Maps Covered (17 + bobika variants)

adlernest, braundorf_b4, bremen_b3, decay, erdenberg_t2, et_brewdog, et_operation, et_ufo_final, frostbite, ice, sp_delivery, karsiah_te2, missile, radar, reactor_final, supply, sw_goldrush_te, te_escape2

---

## 5. ET:Legacy Engine Source Analysis

### 5.1 Flag/Document Mechanics

**Pickup** (g_team.c:329): `cl->ps.powerups[PW_REDFLAG] = INT_MAX;`
- Sets level.flagIndicator and redFlagCounter
- Fires script events: `"trigger" "stolen"` on flag entity, `"allied_object_stolen"` on gameManager
- Logs: `Item: <clientNum> team_CTF_redflag`

**Drop on death** (g_items.c:884-899):
- Creates dropped flag entity with `FL_DROPPED_ITEM` flag
- 30-second timeout before auto-return (`Team_DroppedFlagThink`)
- Fires: `"trigger" "dropped"`, `"allied_object_dropped"` on gameManager

**Return** (g_team.c:208-267):
- Only defending team can return (same team as flag)
- Only when flag has `FL_DROPPED_ITEM` state
- Fires: `"trigger" "returned"`, `"axis_object_returned"` on gameManager

**Delivery** (g_trigger.c:1247-1403):
- `trigger_flagonly` (single-use) or `trigger_flagonly_multiple` (reusable) zones
- Checks `ps.powerups[PW_REDFLAG]` on touching player
- Fires: `"death"` on trigger, `"trigger" "captured"` on flag spawner
- If KILL_FLAG spawnflag: clears powerup

### 5.2 Tank/Truck Mechanics

**Entity**: `script_mover` (g_script.c:1107-1273)
- Spawnflags: TRIGGERSPAWN(1), SOLID(2), EXPLOSIVEDAMAGEONLY(4), RESURRECTABLE(8), COMPASS(16), ALLIED(32), AXIS(64), MOUNTED_GUN(128)
- Movement via `gotomarker <target> <speed> [accel/deccel]` (g_script_actions.c:1365-1575)
- Sets trajectory: `TR_LINEAR_STOP`, `TR_ACCELERATE`, or `TR_DECCELERATE`

**NO engine escort system!** Tank movement is 100% map-script driven:
1. `trigger_multiple` brushes around tank path
2. Map script checks player count in trigger
3. If enough → `gotomarker` command on script_mover
4. **Trigger state NOT accessible from Lua**

**Mounting** (g_cmds.c:4147): Player activates mountable script_mover:
- `ent->tagParent = traceEnt->nextTrain` (mount point)
- `ent->tankLink = traceEnt; traceEnt->tankLink = ent` (bidirectional link)
- Sets EF_TAGCONNECT flag on player

**Health/Death/Rebuild**:
- `health` field readable/writable
- `s.dl_intensity` = health % for client healthbar (0-255)
- Death: fires `"death"` script event, ejects mounted player
- Rebuild: `script_mover_use()` restores health, fires `"rebirth"` event

### 5.3 Construction Mechanics

**Build progress**: `constructible->s.angles2[0]` (0 to 250 scale)
- Each frame an engineer builds: `+= 255.f / (duration / FRAMETIME)`
- At ≥250: construction complete, transitions to STATE_DEFAULT
- Decay after 30 seconds of inactivity (resets to 0)

**Messages**: `G_LogPrintf("Repair: %d\n", clientNum)` — note: NO track name for construction!

### 5.4 Destruction Mechanics

**Dynamite**: `G_LogPrintf("Dynamite_Plant: %d %s\n", clientNum, trackName)`
- Script event: `"dynamited" "axis"/"allies"` on target entity
- 30-second fuse, defusable by defending engineers

**Destruction**: `G_LogPrintf("Objective_Destroyed: %d %s\n", clientNum, trackName)`

### 5.5 Complete G_LogPrintf Messages for Objectives

```
Item: <id> team_CTF_redflag             -- flag pickup
Item: <id> team_CTF_blueflag            -- flag pickup
Dynamite_Plant: <id> <track>            -- dynamite planted
Dynamite_Diffuse: <id> <track>          -- dynamite defused (engine typo!)
Objective_Destroyed: <id> <track>       -- objective blown up
Repair: <id>                            -- construction complete
legacy popup: ^7<team>^7 stole "<obj>"  -- steal announcement
legacy popup: ^7<team>^7 returned "<obj>"  -- return
legacy popup: ^7<team>^7 planted "<obj>"   -- planted
legacy popup: ^7<team>^7 defused "<obj>"   -- defused
legacy announce: "^7<text>"             -- map-specific announcements
```

---

## 6. Our Existing Infrastructure (Proximity v5.0)

### 6.1 Lua Tracker — 17 Output Sections

| Section | Description | Polling |
|---------|-------------|---------|
| ENGAGEMENTS | Combat events with position paths | Event-driven |
| PLAYER_TRACKS | Full movement per life | 200ms |
| KILL_HEATMAP | Grid kill counts | On kill |
| MOVEMENT_HEATMAP | Traffic patterns | 200ms |
| OBJECTIVE_FOCUS | Player proximity to objectives | 200ms |
| REACTION_METRICS | Return fire timing | Event-driven |
| WEAPON_ACCURACY | Per-weapon stats | On fire/hit |
| REVIVES | Medic actions | Event-driven |
| SPAWN_TIMING | Kill timing vs spawn waves | On kill |
| TEAM_COHESION | Team formation snapshots | 500ms |
| CROSSFIRE_OPPORTUNITIES | LOS-based crossfire | 1000ms |
| FOCUS_FIRE | Multi-attacker coordination | Event-driven |
| TEAM_PUSHES | Coordinated movement + `toward_objective` | 1000ms |
| TRADE_KILLS | Revenge kills within 5s | On kill |
| KILL_OUTCOME | Kill permanence (gibbed/revived/expired) | On kill |
| HIT_REGIONS | Per-damage body region | On damage |
| COMBAT_POSITIONS | Kill XYZ positions | On kill |

### 6.2 Objective Infrastructure Already In Place

- `config.objectives` table: 40+ maps, but only 4 with coordinates (supply, sw_goldrush_te)
- `proximity_objective_focus` DB table: per-player nearest objective, avg_distance, time_within_radius
- `proximity_team_push.toward_objective` column: push direction vs objective direction
- `objective_coords_template.json`: 39 maps, 18 with full coordinates
- `objective_coords_from_etmain.json`: 13 maps, 77 objectives from BSP extraction
- `objective_coords_gate_config.json`: Gate validation for 8 static guard maps

### 6.3 What We DON'T Have

- No `et_Print` handler in proximity tracker (critical gap!)
- No carrier state tracking
- No vehicle entity scanning or tracking
- No construction/destruction event capture
- No per-map event pattern configuration

### 6.4 Data Pipeline

```
ET:Legacy Server → proximity_tracker.lua (v5.0)
    → <date>-<time>-round-<N>_engagements.txt (17 sections)
    → ProximityParserV4 (parser.py)
    → PostgreSQL (26 proximity tables)
    → Discord Bot (proximity_cog.py) + React Website
```

---

## 7. Map Objective Taxonomy

### 7.1 Objective Types

| Type | Entity | Detection | Example Maps |
|------|--------|-----------|--------------|
| **Carry** | team_CTF_redflag/blueflag | ps.powerups[5/6] + et_Print | adlernest, radar, goldrush, frostbite |
| **Escort** | script_mover | r.currentOrigin polling | goldrush (tank+truck), supply (truck), fueldump (tank) |
| **Construct** | func_constructible | et_Print "Repair:" + s.angles2 | command post, MG nest, bridge, fence |
| **Destruct** | func_explosive | et_Print "Dynamite_Plant/Objective_Destroyed" | doors, walls, gates, gun controls |
| **Capture** | team_WOLF_checkpoint | et_Print + entity scan | supply flag, radar flag |
| **Multi-Phase** | combination | mapscript announce | goldrush (3), supply (3), decay (3) |

### 7.2 Slomix Map Pool (35 maps)

**With BSP-extracted coordinates (13)**: adlernest, braundorf_b4, bremen_b3, erdenberg_t2, etl_adlernest, etl_ice, etl_sp_delivery, frostbite, supply, sw_battery, sw_goldrush_te, sw_oasis_b3, te_escape2

**Without coordinates (22)**: battery, dubrovnik_final, et_beach, et_ice, et_ufo_final, etl_frostbite, fueldump, goldrush, karsiah_te2, mp_sillyctf, mp_sub_rc1, oasis, pha_chateau, radar, railgun, reactor_final, sp_delivery_te, supplydepot2, tc_base, the_station, warbell, wolken1_b1

### 7.3 Multi-Phase Maps in Slomix Pool

| Map | Phases | Description |
|-----|--------|-------------|
| sw_goldrush_te | 3 | Tank to bank → Steal gold → Truck with gold to exit |
| supply | 3 | Destroy gate → Escort truck to crane → Truck to exit |
| fueldump | 3 | Build bridge → Escort tank → Destroy fuel depot |
| radar | 2 | Breach entrance → Steal 2 radar parts |
| frostbite | 2 | Breach entrances → Steal + transmit documents |
| adlernest | 2 | Destroy door controls → Steal + transmit documents |

---

## 8. Feasibility Matrix

### What's Possible

| Feature | Method | Confirmed By |
|---------|--------|-------------|
| Carrier detection | ps.powerups[5/6] polling | Aciz, Oksii, c0rnn, engine source |
| Carrier time | Frame-by-frame accumulation | Oksii (in_objcarrier) |
| **Carrier path + distance** | ps.origin polling while carrying | **NEW — nobody does this** |
| **Carrier efficiency** | beeline / actual distance | **NEW — nobody does this** |
| Carrier kill attribution | et_Obituary + carrier state | Oksii (obj_carrierkilled) |
| Tank/truck position | r.currentOrigin on script_mover | Engine source confirmed |
| **Tank push distance** | Cumulative position delta | **NEW — nobody does this** |
| Mounted player detection | tankLink field (bidirectional) | Engine source confirmed |
| **Non-mounted escort attribution** | Proximity to moving tank | **NEW — nobody does this** |
| Tank movement detection | s.pos trajectory trType check | Engine source confirmed |
| Tank health tracking | health field polling | Engine source confirmed |
| Dynamite plant/defuse | et_Print "Dynamite_Plant/Diffuse" | Engine source (g_weapon.c) |
| Objective destruction | et_Print "Objective_Destroyed" | Engine source (g_missile.c) |
| Construction complete | et_Print "Repair:" | Engine source (g_weapon.c) |
| Flag capture | et_Print + team_WOLF_checkpoint scan | Oksii (dynamic detection) |

### What's NOT Possible

| Feature | Why |
|---------|-----|
| Read map script accum variables | Not exposed to Lua API |
| Read trigger_multiple occupancy | Brush trigger state not accessible |
| Engine-level escort zone detection | Doesn't exist — map script only |
| et_Damage for entities | Only fires for player damage |
| et_ObjectiveEvent callback | Doesn't exist |
| Distinguish EF_TAGCONNECT from EF_MOUNTEDTANK | Same flag (0x8000) |
| Player ID in announce messages | Not included — need carrier state or proximity |
| Track name in Repair: message | Only clientNum logged |

---

## 9. Design Concepts for v6.0

### Phase 1: Carrier Intelligence (~200 new Lua lines)

**Core idea**: Track carrier position path every 200ms, calculate cumulative distance, record lifecycle.

- New `et_Print()` callback (tracker currently has none!)
- Carrier state machine: `startCarrierTracking()` → `sampleCarrierPosition()` → `endCarrierTracking(outcome)`
- Dual detection: et_Print for precise timing + powerup polling as safety net
- New metrics: `carry_distance`, `beeline_distance`, `efficiency` (distance ratio)
- Output: `CARRIER_EVENTS` + `CARRIER_KILLS` sections
- DB: `proximity_carrier_event` + `proximity_carrier_kill` tables
- Commands: `!pca` (carrier leaderboard), `!pck` (carrier killer leaderboard), `!pcd` (carry detail)

### Phase 2: Vehicle/Escort Intelligence (~300 new Lua lines)

**Core idea**: Scan script_mover entities at map init, poll position, attribute escort credit.

- Entity scanner at round start (classname == "script_mover")
- Position polling: track r.currentOrigin deltas while tank moves
- Attribution: mounted (tankLink check) + proximity (within 500u while tank moves)
- Output: `VEHICLE_PROGRESS` + `ESCORT_CREDIT` sections
- Commands: `!pes` (escort leaderboard), `!pve` (vehicle progress)

### Phase 3: Construction/Destruction Intelligence (~150 new Lua lines)

**Core idea**: Parse et_Print for construction/destruction events with player attribution.

- Capture: Dynamite_Plant, Dynamite_Diffuse, Objective_Destroyed, Repair messages
- Output: `CONSTRUCTION_EVENTS` section
- Commands: `!pen` (engineer leaderboard), `!pot` (objective timeline)

### Phase 4: Map Config System

**Core idea**: Replace hardcoded per-map logic with config-driven system.

- Expand config.objectives with BSP-extracted coordinates (13 maps → all)
- Add config.objective_meta for attack_team, carry_items per map
- Build script: `scripts/generate_lua_objective_config.py` converts JSON → Lua config
- Future: per-map event patterns (steal_pattern, secured_pattern)

### Comparison: What's New vs. Existing

| Metric | c0rnn | Oksii | Our v5 | **Our v6** |
|--------|-------|-------|--------|------------|
| Carrier detection | Yes | Yes | No | **Yes** |
| Carrier time | No | Yes | No | **Yes** |
| **Carrier path** | No | No | No | **YES — NEW** |
| **Carrier distance** | No | No | No | **YES — NEW** |
| **Carrier efficiency** | No | No | No | **YES — NEW** |
| **Tank push distance** | No | No | No | **YES — NEW** |
| **Escort attribution (distance)** | No | No | No | **YES — NEW** |
| **Carrier kill impact** | No | No | No | **YES — NEW** |
| Obj lifecycle | Yes (3 events) | Yes (11 events) | No | **Yes** |
| Construction tracking | No | Yes | No | **Yes** |
| Persistence | None | JSON→HTTP | N/A | **PostgreSQL** |
| Distance while escorting | No | No | No | **YES — NEW** |

---

## 10. Links & References

### ET:Legacy Documentation
- Lua API: https://etlegacy-lua-docs.readthedocs.io/en/latest/standard.html
- Entity fields: https://etlegacy-lua-docs.readthedocs.io/en/latest/gentity_get.html

### Reference Implementations
- c0rnn objtrack.lua: https://github.com/x0rnn/etlegacy-lua-scripts/blob/master/objtrack.lua
- c0rnn endstats.lua: https://github.com/x0rnn/etlegacy-lua-scripts/blob/master/endstats.lua
- Oksii game-stats-web.lua: https://github.com/Oksii/legacy-configs/blob/main/luascripts/game-stats-web.lua
- Oksii config.toml: https://github.com/Oksii/legacy-configs/blob/main/luascripts/config.toml

### ET:Legacy Engine Source
- g_team.c (flag mechanics): https://github.com/etlegacy/etlegacy/blob/master/src/game/g_team.c
- g_items.c (item pickup): https://github.com/etlegacy/etlegacy/blob/master/src/game/g_items.c
- g_script_actions.c (gotomarker): https://github.com/etlegacy/etlegacy/blob/master/src/game/g_script_actions.c
- g_weapon.c (dynamite/construction): https://github.com/etlegacy/etlegacy/blob/master/src/game/g_weapon.c
- g_missile.c (objective destroy): https://github.com/etlegacy/etlegacy/blob/master/src/game/g_missile.c
- bg_public.h (constants): https://github.com/etlegacy/etlegacy/blob/master/src/game/bg_public.h

### Our Files
- Proximity tracker Lua: `proximity/lua/proximity_tracker.lua` (v5.0, 2981 lines)
- Proximity parser: `proximity/parser/parser.py` (2942 lines)
- Objective coordinates: `proximity/objective_coords_template.json`, `proximity/objective_coords_from_etmain.json`
- DB schema: `tools/schema_postgresql.sql`
- Discord cog: `bot/cogs/proximity_cog.py`

---

*Research compiled 2026-03-24 by Claude Code based on community input from Seareal, Aciz, and c0rnn.*
