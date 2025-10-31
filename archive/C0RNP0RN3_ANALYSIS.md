# 🎮 C0RNP0RN3.lua - Complete Analysis

**Version:** 3.0  
**Last Updated:** October 3, 2025  
**Author:** iamez (https://github.com/iamez/etlegacy-scripts)  
**License:** GPL-3.0  
**Status:** Production ✅

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [Data Collection](#data-collection)
4. [File Output](#file-output)
5. [Field Reference](#field-reference)
6. [Integration](#integration)
7. [Known Issues](#known-issues)

---

## 🎯 Overview

`c0rnp0rn3.lua` is a comprehensive ET:Legacy Lua script that tracks detailed game statistics and writes them to text files at the end of each round. It runs on the ET:Legacy game server and hooks into game events to collect data.

### Purpose

- ✅ Track player combat stats (kills, deaths, damage, accuracy)
- ✅ Track weapon usage (per-weapon kills, hits, shots, headshots)
- ✅ Track objective stats (dynamites, revives, objective captures)
- ✅ Track advanced stats (killing sprees, multikills, denied playtime)
- ✅ Output data to parseable text files
- ✅ Support for Round 1 and Round 2 with cumulative tracking

### Key Features

- **37+ Player Fields** - Comprehensive stat tracking per player
- **28 Weapon Types** - Individual weapon statistics
- **Multikill Tracking** - Double, triple, quad, multi, mega kills
- **Spree Tracking** - Killing sprees and death sprees
- **Objective Tracking** - Dynamites, flags, revives, repairs
- **Time Tracking** - Accurate time played in seconds
- **Round Differential** - Tracks Round 2 as cumulative (R1 + R2)

---

## ⚙️ How It Works

### Game Server Integration

The script runs as a Lua mod on the ET:Legacy game server:

```
┌─────────────────────────────────────────────────────────┐
│              ET:Legacy Game Server                       │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ Lua API Calls
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 c0rnp0rn3.lua Script                     │
│  • et_InitGame()        - Initialize on server start    │
│  • et_RunFrame()        - Called every frame             │
│  • et_Obituary()        - Called on player death         │
│  • et_Damage()          - Called on damage event         │
│  • et_ClientSpawn()     - Called when player spawns      │
│  • et_ClientDisconnect()- Called when player leaves      │
│  • et_Print()           - Called on game events          │
│  • et_ShutdownGame()    - Called on server shutdown      │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Write Files
                     ▼
┌─────────────────────────────────────────────────────────┐
│          /gamestats/*.txt Files                          │
│  YYYY-MM-DD-HHMMSS-mapname-round-N.txt                  │
└─────────────────────────────────────────────────────────┘
```

### Event Hooks

**1. `et_InitGame()` - Server Startup**
- Registers the mod
- Initializes player data arrays
- Sets up reinforcement time calculations

**2. `et_RunFrame(levelTime)` - Every Frame (~50fps)**
- Stores stats periodically (every 5 seconds)
- Tracks multikills with 3-second windows
- Handles intermission (end of round)
- Saves stats to file at intermission

**3. `et_Obituary(victim, killer, mod)` - On Death**
- Tracks kills, deaths, team kills
- Detects killing sprees and death sprees
- Tracks multikills (double, triple, etc.)
- Calculates "useful kills" (before enemy respawn)
- Tracks "useless kills" (right before respawn)
- Records denied playtime (time enemy is dead)

**4. `et_Damage(target, attacker, damage, flags, mod)` - On Damage**
- Tracks hit regions (head, body, arms, legs)
- Records hitters for kill assist calculations
- Detects headshot kills

**5. `et_ClientSpawn(id, revived)` - On Spawn**
- Resets killing sprees
- Tracks death time (for denied playtime)
- Clears hit region data

**6. `et_Print(text)` - Game Event Messages**
- Captures objective events (dynamite plant/defuse)
- Captures flag captures (stolen/returned)
- Captures medic revives
- Captures repair/construction events

---

## 📊 Data Collection

### Core Data Structures

**Global Arrays:**
```lua
killing_sprees[clientNum] = 0          -- Current killing spree
death_sprees[clientNum] = 0            -- Current death spree
topshots[clientNum] = {1=0, 2=0, ...}  -- 20 tracked stats
denies[clientNum] = {1=false, 2=-1, 3=0} -- Denied playtime tracking
kmulti[clientNum] = {1=0, 2=0}         -- Multikill tracking
multikills[clientNum] = {1=0, 2=0, 3=0, 4=0, 5=0} -- 2x, 3x, 4x, 5x, 6x
hitters[clientNum] = {...}             -- Recent damage dealers
```

**Topshots Array (20 fields):**
```lua
topshots[id] = {
    [1]  = killing_spree_best,
    [2]  = death_spree_worst,
    [3]  = kill_assists,
    [4]  = kill_steals,
    [5]  = headshot_kills,
    [6]  = objectives_stolen,
    [7]  = objectives_returned,
    [8]  = dynamites_planted,
    [9]  = dynamites_defused,
    [10] = times_revived,
    [11] = bullets_fired,
    [12] = dpm,
    [13] = tank_meatshield,
    [14] = time_dead_ratio,
    [15] = most_useful_kills,
    [16] = denied_playtime (milliseconds),
    [17] = useless_kills,
    [18] = full_selfkills,
    [19] = repairs_constructions,
    [20] = revives_given
}
```

### Weapon Stats Collection

**ET:Legacy Weapon IDs:**
```lua
WeaponStats_t = {
    WS_KNIFE = 0,           WS_KNIFE_KBAR = 1,
    WS_LUGER = 2,           WS_COLT = 3,
    WS_MP40 = 4,            WS_THOMPSON = 5,
    WS_STEN = 6,            WS_FG42 = 7,
    WS_PANZERFAUST = 8,     WS_BAZOOKA = 9,
    WS_FLAMETHROWER = 10,   WS_GRENADE = 11,
    WS_MORTAR = 12,         WS_MORTAR2 = 13,
    WS_DYNAMITE = 14,       WS_AIRSTRIKE = 15,
    WS_ARTILLERY = 16,      WS_SATCHEL = 17,
    WS_GRENADELAUNCHER = 18,WS_LANDMINE = 19,
    WS_MG42 = 20,           WS_BROWNING = 21,
    WS_CARBINE = 22,        WS_KAR98 = 23,
    WS_GARAND = 24,         WS_K43 = 25,
    WS_MP34 = 26,           WS_SYRINGE = 27
}
```

**Stats Retrieved from ET:Legacy:**
```lua
for weaponId = 0, 27 do
    local stats = et.gentity_get(clientNum, "sess.aWeaponStats", weaponId)
    -- stats[1] = atts   (shots fired)
    -- stats[2] = deaths (deaths with this weapon equipped)
    -- stats[3] = headshots
    -- stats[4] = hits
    -- stats[5] = kills
end
```

### DPM Calculation (Lua Version)

**Lua calculates DPM with ROUNDED time:**

```lua
local timeAxis = et.gentity_get(id, "sess.time_axis")      -- milliseconds
local timeAllies = et.gentity_get(id, "sess.time_allies")  -- milliseconds
local tp = timeAxis + timeAllies                            -- total ms
local damageGiven = et.gentity_get(id, "sess.damage_given")

local dpm = 0
if round == 0 then  -- Round 2 intermission
    -- Subtract Round 1 damage
    local r1_dmg = tonumber(et.trap_Cvar_Get("round1_dmg" .. id)) or 0
    dpm = (damageGiven - r1_dmg) / ((tp / 1000) / 60)
elseif round == 1 then  -- Round 1 intermission
    dpm = damageGiven / ((tp / 1000) / 60)
end

topshots[id][12] = roundNum(dpm, 1)  -- Round to 1 decimal
```

**Time Rounding Issue:**
```lua
-- Field 23: Time in minutes with 1 decimal (causes rounding)
local time_minutes = roundNum((tp / 1000) / 60, 1)  -- 3.85 → 3.9

-- This causes the "45 vs 48 values" issue SuperBoyy reported!
-- 3:51 (231 seconds) → 3.85 minutes → rounded to 3.9 → confusing!
```

### Reinforcement Time Calculation

Used to determine "useful kills" and "useless kills":

```lua
function calculateReinfTime(team)
    -- Calculate seconds until team's next respawn
    local levelStartTime = et.trap_GetConfigstring(et.CS_LEVEL_START_TIME)
    local dwDeployTime
    
    if team == et.TEAM_AXIS then
        dwDeployTime = tonumber(et.trap_Cvar_Get("g_redlimbotime"))
    elseif team == et.TEAM_ALLIES then
        dwDeployTime = tonumber(et.trap_Cvar_Get("g_bluelimbotime"))
    end
    
    return (dwDeployTime - ((aReinfOffset[team] + gameFrameLevelTime - levelStartTime) % dwDeployTime)) * 0.001
end
```

**Usage:**
```lua
local nextRespawnTime = calculateReinfTime(victim_team)

-- Useful Kill: Killed when >50% of respawn time remaining
if nextRespawnTime >= (limbotime / 1000) / 2 then
    topshots[killer][15] = topshots[killer][15] + 1  -- most_useful_kills
end

-- Useless Kill: Killed <5 seconds before respawn
if nextRespawnTime < 5 then
    topshots[killer][17] = topshots[killer][17] + 1  -- useless_kills
end
```

### Multikill Detection

```lua
function checkMultiKill(killer, mod)
    local lvltime = et.trap_Milliseconds()
    
    -- Check if within 3-second window of last kill
    if (lvltime - kmulti[killer][1]) < 3000 then
        kmulti[killer][2] = kmulti[killer][2] + 1  -- Increment kill count
        
        -- Schedule multikill award after 3.1 seconds
        if kmulti[killer][2] == 2 then
            wait_table[killer] = {lvltime, 2}  -- Double kill
        elseif kmulti[killer][2] == 3 then
            wait_table[killer] = {lvltime, 3}  -- Triple kill
        -- ... up to 6 kills
        end
    else
        kmulti[killer][2] = 1  -- Reset to 1 kill
    end
    
    kmulti[killer][1] = lvltime  -- Update last kill time
end

-- Later in et_RunFrame, award multikills after 3.1 second confirmation
for id, arr in pairs(wait_table) do
    local startpause = arr[1]
    local whichkill = arr[2]
    
    if whichkill == 2 and (startpause + 3100) < currentTime then
        multikills[id][1] = multikills[id][1] + 1  -- Award double kill
        wait_table[id] = nil
    end
    -- ... similar for 3x, 4x, 5x, 6x
end
```

---

## 📄 File Output

### File Naming

```
gamestats/YYYY-MM-DD-HHMMSS-mapname-round-N.txt

Example:
gamestats/2025-10-02-211808-etl_adlernest-round-1.txt
```

**Lua Code:**
```lua
function SaveStats()
    local mapname = et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_SERVERINFO), "mapname")
    local round = tonumber(et.trap_Cvar_Get("g_currentRound")) == 0 and 2 or 1
    local fileName = string.format("gamestats\\%s%s-round-%d.txt", 
                                   os.date('%Y-%m-%d-%H%M%S-'), mapname, round)
    -- Write to file...
end
```

### Header Line

```
servername\mapname\config\round\defenderteam\winnerteam\timelimit\nexttimelimit\actualtime_seconds
```

**Lua Code:**
```lua
local servername = et.trap_Cvar_Get("sv_hostname")
local config = et.trap_Cvar_Get("g_customConfig")
local defenderteam = tonumber(et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_MULTI_INFO), "d")) + 1
local winnerteam = tonumber(et.Info_ValueForKey(et.trap_GetConfigstring(et.CS_MULTI_MAPWINNER), "w")) + 1
local timelimit = ConvertTimelimit(et.trap_Cvar_Get("timelimit"))
local nextTimeLimit = ConvertTimelimit(et.trap_Cvar_Get("g_nextTimeLimit"))
local actualtime_seconds = (round_end_time - round_start_time) / 1000  -- ⭐ SECONDS!

local header = string.format("%s\\%s\\%s\\%d\\%d\\%d\\%s\\%s\\%s\n",
    servername, mapname, config, round, defenderteam, winnerteam,
    timelimit, nextTimeLimit, actualtime_seconds)
```

### Player Line

```
GUID\Name\Round\Team\WeaponMask [weapon_stats] \t [37 objective fields]
```

**Lua Code:**
```lua
local guid = string.upper(et.Info_ValueForKey(et.trap_GetUserinfo(id), "cl_guid"))
local name = et.gentity_get(id, "pers.netname")
local round = et.gentity_get(id, "sess.rounds")
local team = et.gentity_get(id, "sess.sessionTeam")
local dwWeaponMask = 0  -- Bitmask of weapons used
local weaponStats = ""

-- Build weapon stats string
for weaponId = 0, 27 do
    local stats = et.gentity_get(id, "sess.aWeaponStats", weaponId)
    local hits = stats[4]
    local atts = stats[1]
    local kills = stats[5]
    local deaths = stats[2]
    local headshots = stats[3]
    
    if atts ~= 0 or hits ~= 0 or deaths ~= 0 or kills ~= 0 then
        weaponStats = string.format("%s %d %d %d %d %d", weaponStats,
                                    hits, atts, kills, deaths, headshots)
        dwWeaponMask = dwWeaponMask | (1 << weaponId)
    end
end

-- Build objective stats (37 fields)
local objectiveStats = string.format("\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%0.1f\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n",
    damageGiven, damageReceived, teamDamageGiven, teamDamageReceived,
    gibs, selfkills, teamkills, teamgibs,
    timePlayed,  -- % (field 8)
    xp,          -- field 9
    topshots[id][1], topshots[id][2], topshots[id][3], topshots[id][4],
    topshots[id][5], topshots[id][6], topshots[id][7], topshots[id][8],
    topshots[id][9], topshots[id][10], topshots[id][11],
    topshots[id][12],  -- DPM (field 22)
    roundNum((tp/1000)/60, 1),  -- time_minutes (field 23) ⭐
    topshots[id][13], topshots[id][14],
    roundNum((death_time_total[id] / 60000), 1),  -- field 26
    kd,  -- field 27
    topshots[id][15], math.floor(topshots[id][16]/1000),  -- fields 28-29
    multikills[id][1], multikills[id][2], multikills[id][3],
    multikills[id][4], multikills[id][5],  -- fields 30-34
    topshots[id][17], topshots[id][18], topshots[id][19], topshots[id][20])

-- Combine everything
stats[guid] = string.format("%s\\%s\\%d\\%d\\%d%s%s",
    string.sub(guid, 1, 8), name, round, team, dwWeaponMask,
    weaponStats, objectiveStats)
```

---

## 📚 Field Reference

### 37 Objective Fields (After Tab)

| Field | Name | Type | Description | Lua Source |
|-------|------|------|-------------|------------|
| 0 | damage_given | INT | Total damage dealt | sess.damage_given |
| 1 | damage_received | INT | Total damage received | sess.damage_received |
| 2 | team_damage_given | INT | Friendly fire damage | sess.team_damage_given |
| 3 | team_damage_received | INT | FF damage received | sess.team_damage_received |
| 4 | gibs | INT | Gib kills | sess.gibs |
| 5 | self_kills | INT | Suicide deaths | sess.self_kills |
| 6 | team_kills | INT | Team kills | sess.team_kills |
| 7 | team_gibs | INT | Team gibs | sess.team_gibs |
| 8 | time_played_percent | REAL | Time % (not used) | calculated % |
| 9 | xp | INT | Experience points | ps.persistant[PERS_SCORE] |
| 10 | killing_spree | INT | Best killing spree | topshots[1] |
| 11 | death_spree | INT | Worst death spree | topshots[2] |
| 12 | dpm_lua | REAL | DPM from Lua | topshots[12] |
| 13 | kill_assists | INT | Assisted kills | topshots[3] |
| 14 | kill_steals | INT | Stolen kills | topshots[4] |
| 15 | headshot_kills | INT | Kills by headshot | topshots[5] |
| 16 | objectives_stolen | INT | Objectives stolen | topshots[6] |
| 17 | objectives_returned | INT | Objectives returned | topshots[7] |
| 18 | dynamites_planted | INT | Dynamites planted | topshots[8] |
| 19 | dynamites_defused | INT | Dynamites defused | topshots[9] |
| 20 | times_revived | INT | Times revived | topshots[10] |
| 21 | bullets_fired | INT | Total shots fired | topshots[11] |
| 22 | dpm_recalc | REAL | DPM (same as 12) | topshots[12] |
| 23 | time_minutes | REAL | **TIME IN MINUTES** ⭐ | (tp/1000)/60 rounded |
| 24 | tank_meatshield | REAL | Tank/meatshield score | topshots[13] |
| 25 | time_dead_ratio | REAL | Time dead ratio % | topshots[14] |
| 26 | time_dead_minutes | REAL | Time dead (minutes) | calculated |
| 27 | kd_ratio | REAL | Kill/death ratio | kills/deaths |
| 28 | most_useful_kills | INT | Most useful kills | topshots[15] |
| 29 | denied_playtime | INT | **Denied playtime (sec)** | topshots[16]/1000 |
| 30 | double_kills | INT | 2x multikills | multikills[1] |
| 31 | triple_kills | INT | 3x multikills | multikills[2] |
| 32 | quad_kills | INT | 4x multikills | multikills[3] |
| 33 | multi_kills | INT | 5x multikills | multikills[4] |
| 34 | mega_kills | INT | 6x multikills | multikills[5] |
| 35 | useless_kills | INT | Useless kills | topshots[17] |
| 36 | full_selfkills | INT | Full selfkills | topshots[18] |
| 37 | repairs_constructions | INT | Repairs/constructions | topshots[19] |
| 38 | revives_given | INT | Revives given | topshots[20] |

---

## 🔗 Integration with Parser

### Parser Must Handle:

1. **Time Field (#23)** - Rounded minutes → convert to seconds
   ```python
   # Lua outputs: 3.9 (rounded from 3.85)
   # Parser must use header's actual_time_seconds: 231
   ```

2. **Round 2 Differential** - Lua outputs cumulative
   ```python
   # Round 2 file contains: R1 + R2 combined
   # Parser must subtract Round 1 data
   ```

3. **DPM Recalculation** - Use accurate seconds
   ```python
   # Lua uses rounded minutes → 3.9 min → DPM slightly off
   # Parser should recalculate: (damage * 60) / actual_seconds
   ```

4. **Denied Playtime** - Convert milliseconds to seconds
   ```python
   # Field 29: topshots[16]/1000 (Lua divides by 1000)
   # Already in seconds, store as INTEGER
   ```

---

## 🐛 Known Issues

### 1. Time Rounding

**Problem:** Field #23 outputs rounded minutes (1 decimal)
- Real time: 3:51 (231 seconds)
- Lua outputs: 3.9 minutes
- Causes confusion: "45 values but SQL expects 48"

**Solution:** Parser uses header's `actual_time_seconds` instead

### 2. Round 2 Cumulative

**Problem:** Round 2 file contains R1 + R2 combined stats

**Solution:** Parser detects Round 2, finds Round 1 file, subtracts

### 3. Header Date Bug

**Problem:** Header shows `1970-01-01` for dates

**Solution:** Parser extracts date from filename instead

### 4. DPM Precision

**Problem:** Lua calculates DPM with rounded minutes
- Lua: `damage / (3.9 minutes)` = 340.51 DPM
- Accurate: `damage * 60 / 231 seconds` = 344.94 DPM

**Solution:** Parser recalculates DPM with exact seconds

---

## 🎓 Best Practices

### For Server Admins:

1. **Regular File Collection**
   - Files saved to `gamestats/` directory
   - Collect and archive regularly (use rsync/scp)
   - Each file ~5-20 KB

2. **Backup Configuration**
   - Keep c0rnp0rn3.lua in version control
   - Test after ET:Legacy updates
   - Monitor for Lua errors in server logs

3. **File Rotation**
   - Old files can be archived/compressed
   - Keep at least 30 days online for parser

### For Developers:

1. **Always use `actual_time_seconds` from header**
2. **Handle Round 2 differential correctly**
3. **Recalculate DPM with accurate seconds**
4. **Validate all fields before database insert**
5. **Log parse errors for debugging**

---

**Script Version:** 3.0  
**Last Updated:** October 3, 2025  
**Repository:** https://github.com/iamez/etlegacy-scripts  
**License:** GPL-3.0 ✅
