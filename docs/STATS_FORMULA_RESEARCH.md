# Stats Formula Research & Audit

> **Created:** 2026-02-20  
> **Status:** Research findings — no code changes yet  
> **Scope:** All calculated/derived stats across bot, website, and Lua  
> **Related:** `docs/KNOWN_ISSUES.md` (Lua Time Stats Overhaul plan)

---

## Table of Contents

1. [Complete Inventory of Calculated Stats](#1-complete-inventory-of-calculated-stats)
2. [Formula Errors Found](#2-formula-errors-found)
   - [Headshot Percentage — WRONG](#21-headshot-percentage--wrong)
   - [Time Alive — Inconsistent, partially wrong](#22-time-alive--inconsistent-partially-wrong)
   - [Denied Playtime Display — Conceptually questionable](#23-denied-playtime-display--conceptually-questionable)
3. [Cross-System Inconsistencies](#3-cross-system-inconsistencies)
   - [Damage Efficiency — Bot vs Website disagree](#31-damage-efficiency--bot-vs-website-disagree)
   - [FragPotential — Completely different formulas](#32-fragpotential--completely-different-formulas)
   - [Survival Rate — Actual vs heuristic](#33-survival-rate--actual-vs-heuristic)
4. [Data Source Map](#4-data-source-map)
5. [c0rnp0rn Lua Reference](#5-c0rnp0rn-lua-reference)
6. [Recommended Fixes](#6-recommended-fixes)

---

## 1. Complete Inventory of Calculated Stats

Every derived/calculated stat in the codebase, where it's defined, and the formula used.

### Bot — `bot/stats/calculator.py` (StatsCalculator)

| Stat | Method | Formula | Inputs | Notes |
|------|--------|---------|--------|-------|
| DPM | `calculate_dpm()` | `(damage × 60) / time_seconds` | damage_given, time_played_seconds | ✅ Correct |
| K/D Ratio | `calculate_kd()` | `kills / deaths` (or `kills` if 0 deaths) | kills, deaths | ✅ Correct |
| Accuracy | `calculate_accuracy()` | `(hits / shots) × 100` | weapon hits, weapon shots | ✅ Correct |
| Efficiency | `calculate_efficiency()` | `(kills / (kills + deaths)) × 100` | kills, deaths | ✅ Correct |
| Headshot % | `calculate_headshot_percentage()` | `(headshots / kills) × 100` | headshot_kills, total_kills | ❌ **WRONG** — see §2.1 |
| Safe Divide | `safe_divide()` | `numerator / denominator` | any, any | ✅ Utility |
| Safe Percentage | `safe_percentage()` | `(part / total) × 100` | any, any | ✅ Utility |

### Bot — `bot/core/frag_potential.py` (PlayerMetrics + FragPotentialCalculator)

| Stat | Location | Formula | Notes |
|------|----------|---------|-------|
| Time Alive | `PlayerMetrics.calculate_metrics()` | `max(1, time_played_seconds - time_dead_seconds)` | ⚠️ See §2.2 — `time_played_seconds` may be wrong source |
| FragPotential | `calculate_frag_potential()` | `(damage_given / time_alive_seconds) × 60` | ✅ Correct formula, depends on time_alive accuracy |
| K/D Ratio | `PlayerMetrics.calculate_metrics()` | `kills / max(1, deaths)` | ✅ Correct |
| Damage Ratio | `PlayerMetrics.calculate_metrics()` | `damage_given / max(1, damage_received)` | ✅ Correct |
| Headshot % | `PlayerMetrics.calculate_metrics()` | `(headshot_kills / kills) × 100` | ❌ **WRONG** — same issue as calculator.py |
| Playstyle | `determine_playstyle()` | Multi-threshold scoring across 8 categories | ✅ Logic is sound, but depends on corrected inputs |

### Bot — `bot/services/session_graph_generator.py`

| Stat | Formula | Notes |
|------|---------|-------|
| Survival Rate | `100 - (time_dead_minutes / time_played_minutes × 100)` | ⚠️ Depends on time accuracy |
| Damage Efficiency | `damage_given / max(1, damage_received)` | ✅ Ratio-based (>1 = good) |
| Denied Playtime % | `(denied_playtime_sec / max(1, time_played_sec)) × 100` | ⚠️ See §2.3 |
| Time Alive | `max(0, time_played_minutes - time_dead_minutes)` | ⚠️ Same time_played concern |
| K/D Ratio | `kills / max(1, deaths)` | ✅ Correct |

### Bot — `bot/community_stats_parser.py` (embed display)

| Stat | Formula | Notes |
|------|---------|-------|
| Accuracy | `total_hits / total_shots × 100` | ✅ Correct (from weapon stats) |
| HS Rate (embed) | `headshot_kills / total_hits × 100` | ❌ **Mixed units!** headshot_kills ÷ total_hits |
| K/D | `kills / deaths` or `kills` if 0 deaths | ✅ Correct |
| Efficiency | `kills / (kills + deaths) × 100` | ✅ Correct |

### Website — `website/backend/routers/api.py`

| Stat | Line(s) | Formula | Notes |
|------|---------|---------|-------|
| HS Rate (per-weapon) | ~4096 | `total_headshots / total_kills × 100` | ❌ **WRONG** (headshots from weapon table = hits, but divided by kills) |
| HS Rate (per-weapon #2) | ~4292 | `headshots / kills × 100` | ❌ **WRONG** |
| FragPotential | ~4896 | `(kills + assists×0.5) / time_minutes × 10` | ❌ **WRONG** — completely different formula from bot |
| Damage Efficiency | ~4902 | `damage_given / (damage_given + damage_received) × 100` | ⚠️ Different scale from bot (percentage vs ratio) |
| Survival Rate | ~4908 | `min(100, (time_played / (deaths+1)) / 60 × 10)` | ❌ **WRONG** — heuristic approximation |
| Time Denied | ~4912 | `denied_playtime / time_minutes` | Per-minute normalization — acceptable |
| Time Alive | ~5837 | `SUM(time_played_seconds) - SUM(time_dead_minutes × 60)` | ✅ Correct SQL computation |
| Accuracy | ~4195 | `hits / shots × 100` | ✅ Correct |

---

## 2. Formula Errors Found

### 2.1 Headshot Percentage — WRONG

**Current formula (everywhere):**
```
headshot_kills / total_kills × 100
```

**What this measures:** "What percentage of my kills were headshot kills?"

**What it SHOULD measure:** "What percentage of my hits landed on the head?"

**Correct formula:**
```
weapon_headshot_hits / total_hits × 100
```

#### Why the current formula is wrong

In ET:Legacy, the weapon stats system tracks two completely different headshot values:

1. **`aWeaponStats[j][3]`** = headshot **HITS** per weapon — shots that landed on the head hitbox, regardless of whether they killed
2. **`topshots[i][5]`** = headshot **KILLS** — kills where the lethal blow was to the head

**Example:** A player fires 200 shots, 100 hit, 30 hit the head, 20 kills total, 8 of those kills were headshot kills.
- **Current (wrong):** 8/20 = 40% "headshot %"
- **Correct:** 30/100 = 30% headshot accuracy

The current formula is meaningless — kills have nothing to do with accuracy. A player could have terrible aim but still show a high "headshot %" because their few lucky kills happened to hit heads.

#### Data availability (both values exist!)

| Source | Field | What it means | DB Column |
|--------|-------|---------------|-----------|
| `aWeaponStats[j][3]` | Per-weapon headshot HITS | Shots that hit head | `weapon_comprehensive_stats.headshots` |
| `topshots[i][5]` (TAB[14]) | Headshot KILLS | Kills with head final blow | `player_comprehensive_stats.headshot_kills` |
| Sum of weapon headshots | Aggregate headshot HITS | Total head hits | `player_comprehensive_stats.headshots` |
| Sum of weapon hits | Aggregate HITS | Total hits on any body part | Derivable: `SUM(weapon_comprehensive_stats.hits)` |

The parser already correctly distinguishes these (line 1229):
```python
# ⚠️ CRITICAL DISTINCTION - DO NOT CONFUSE THESE TWO:
# 1. player['headshots'] = Sum of all weapon headshot HITS
# 2. objective_stats['headshot_kills'] = TAB field 14 (kills where FINAL BLOW was to head)
```

#### Affected files

| File | Line | Current Code | Fix |
|------|------|-------------|-----|
| `bot/stats/calculator.py` | ~189 | `headshots / kills × 100` | Change to `headshot_hits / total_hits × 100` |
| `bot/core/frag_potential.py` | ~112 | `headshot_kills / kills × 100` | Same |
| `bot/cogs/stats_cog.py` | ~388 | `calculate_headshot_percentage(headshots, kills)` | Pass `SUM(w.headshots)` and `SUM(w.hits)` |
| `bot/community_stats_parser.py` | ~312 | `headshot_kills / total_hits × 100` | Change numerator to weapon headshot HITS |
| `website/backend/routers/api.py` | ~4096 | `total_headshots / total_kills × 100` | `total_headshots / total_hits × 100` |
| `website/backend/routers/api.py` | ~4292 | `headshots / kills × 100` | `headshots / hits × 100` |

#### Consideration: Keep headshot kill rate as separate stat?

The "headshot kill rate" (headshot_kills / kills) IS a valid stat — it measures lethality of head shots. It should be kept as a separate named stat:
- **Headshot Accuracy** = `headshot_hits / total_hits × 100` (aim quality) ← **PRIMARY**
- **Headshot Kill Rate** = `headshot_kills / total_kills × 100` (lethal precision) ← **SECONDARY**

Both should be displayed where relevant. The label "Headshot %" should refer to accuracy.

---

### 2.2 Time Alive — Inconsistent, partially wrong

#### The time_played_seconds problem

The parser sets `time_played_seconds` for ALL players to the round duration from the header:

```python
# community_stats_parser.py, parse_regular_stats_file():
player['time_played_seconds'] = round_time_seconds  # Same for everyone!
```

But the Lua provides **per-player actual play time** in TAB[22]:
```python
# objective_stats['time_played_minutes'] = TAB[22]
# From Lua: roundNum((tp/1000)/60, 1) where tp = timeAxis + timeAllies
```

This means `time_played_seconds` in the DB is the round duration, NOT the player's actual time. For a 10-minute round:
- Player A (full round): time_played = 600s ← ✅ Correct
- Player B (joined 3 min in): time_played = 600s ← ❌ Wrong! Should be ~420s
- Player C (disconnected early): time_played = 600s ← ❌ Wrong!

#### Impact on derived stats

Since `time_alive = time_played - time_dead`, wrong `time_played` means wrong `time_alive`, which cascades to:
- FragPotential (uses time_alive)
- Survival Rate (uses time_dead/time_played ratio)
- DPM (uses time_played)

#### Why stopwatch mode mostly masks this

In competitive stopwatch (the primary mode), teams are locked and everyone plays the full round. So the round duration IS approximately correct for most players. But for:
- Late joiners
- Disconnected players
- Spec-to-team switchers

...the per-player Lua time (TAB[22]) would be more accurate.

#### c0rnp0rn Lua time tracking

```lua
-- Per-player actual time:
tp = timeAxis + timeAllies  -- milliseconds, actual game engine time

-- Time dead tracking (pause-aware):
-- On death: death_time[id] = et.trap_Milliseconds()
-- On spawn: diff = current_time - death_time[id] - pause_overlap
--           death_time_total[id] += diff

-- Output fields:
-- TAB[22] = roundNum((tp/1000)/60, 1)          -- time_played in minutes
-- TAB[24] = (death_time_total / tp) * 100       -- time_dead ratio (%)
-- TAB[25] = roundNum(death_time_total/60000, 1) -- time_dead in minutes
```

The death time tracking is solid — uses actual timestamps, subtracts pause time. The issue is that `time_played_seconds` in the DB doesn't use `tp` from the Lua.

#### Recommended fix

Use TAB[22] (`objective_stats['time_played_minutes']`) as the primary time_played source when available, falling back to header round time:

```python
# In parser, after extracting objective_stats:
lua_time_minutes = objective_stats.get('time_played_minutes', 0)
if lua_time_minutes > 0:
    player['time_played_seconds'] = int(lua_time_minutes * 60)
else:
    player['time_played_seconds'] = round_time_seconds  # fallback
```

---

### 2.3 Denied Playtime Display — Conceptually questionable

#### How c0rnp0rn calculates it (correct)

```lua
-- On normal kill: record killer and death timestamp
denies[victim] = { true, killer, et.trap_Milliseconds() }

-- On victim respawn: credit the KILLER with the time the victim was dead
topshots[killer][16] += (spawn_time - death_time - pause_overlap)

-- On intermission: finalize any pending denies (victim still dead at round end)
topshots[killer][16] += (end_time - death_time - pause_overlap)
```

This means `denied_playtime` = total milliseconds that enemies spent dead because of YOUR kills. It's attributed to the **killer**, not the victim.

**Example:** You kill 5 enemies, each waits ~15s to respawn. Your denied_playtime = ~75 seconds.

#### Current display in session graphs

```python
# session_graph_generator.py
denied_playtime_pct = (denied_seconds / max(1, time_played_seconds)) * 100
```

This divides your denied credit by your OWN play time. Think about what this means:
- 10-minute round, you denied 120 seconds total → 20%
- But 120 denied seconds distributed across multiple enemies is a LOT
- This percentage can theoretically exceed 100% if a player is extremely lethal

**The raw value (seconds) or per-minute rate is more intuitive:**
- "You denied 120 seconds of enemy playtime" — clear
- "You denied 12 seconds per minute" — comparable across game lengths
- "You denied 20%" — 20% of what? Your own time? Confusing.

#### Recommendation

Display denied playtime as:
1. Raw seconds/minutes (primary): "2:00 denied"
2. Per-minute rate (for comparison): "12.0 denied/min"
3. Drop the percentage display or relabel it clearly

---

## 3. Cross-System Inconsistencies

### 3.1 Damage Efficiency — Bot vs Website disagree

| System | Formula | Scale | "Good" value |
|--------|---------|-------|-------------|
| **Bot** (graphs) | `damage_given / damage_received` | Ratio (0 → ∞) | > 1.0 |
| **Website** (API) | `damage_given / (damage_given + damage_received) × 100` | Percentage (0-100%) | > 50% |

These measure the same concept with different scales. A player dealing 2000 damage and receiving 1000:
- Bot shows: **2.0x** damage efficiency
- Website shows: **66.7%** damage efficiency

**Recommendation:** Standardize on the ratio form (`dmg_given / dmg_recv`). It's more intuitive and used in competitive FPS communities. The website should match the bot.

### 3.2 FragPotential — Completely different formulas

| System | Formula | Meaning |
|--------|---------|---------|
| **Bot** | `(damage_given / time_alive_seconds) × 60` | DPM while alive — actual damage rate when not dead |
| **Website** | `(kills + assists × 0.5) / time_minutes × 10` | Scaled kill+assist rate — rough approximation |

The website's "FragPotential" is NOT FragPotential at all. It's a kill-rate-based score with arbitrary scaling.

**Recommendation:** Website must use the same formula as bot:
```python
fp = (damage_given / time_alive_seconds) * 60
```
Where `time_alive_seconds = time_played_seconds - (time_dead_minutes * 60)`.

### 3.3 Survival Rate — Actual vs heuristic

| System | Formula | Notes |
|--------|---------|-------|
| **Bot** | `100 - (time_dead / time_played × 100)` | ✅ Actual time-based |
| **Website** | `min(100, (time_played / (deaths + 1)) / 60 × 10)` | ❌ Heuristic — ignores actual time_dead data, arbitrary `/ 60 × 10` scaling |

The website's formula says: "average seconds alive per life, scaled arbitrarily to 0-100." This has no real-world meaning and ignores the actual time-dead data that exists in the database.

**Recommendation:** Website uses same formula as bot:
```python
survival_rate = 100 - (time_dead_minutes / max(0.01, time_played_minutes) * 100)
```

---

## 4. Data Source Map

How stats flow from Lua → Stats File → Parser → Database → Display.

### Key fields in the stats file (TAB-separated after weapon data)

| TAB Index | Lua Source | Parser Key | DB Column | Type |
|-----------|-----------|------------|-----------|------|
| 0 | `damageGiven` | `damage_given` | `damage_given` | INT |
| 1 | `damageReceived` | `damage_received` | `damage_received` | INT |
| 2 | `teamDamageGiven` | `team_damage_given` | `team_damage_given` | INT |
| 3 | `teamDamageReceived` | `team_damage_received` | `team_damage_received` | INT |
| 4 | `gibs` | `gibs` | `gibs` | INT |
| 5 | `selfkills` | `self_kills` | `self_kills` | INT |
| 6 | `teamkills` | `team_kills` | `team_kills` | INT |
| 7 | `teamgibs` | `team_gibs` | `team_gibs` | INT |
| 8 | `timePlayed` (%) | `time_played_percent` | — | FLOAT (%) |
| 9 | `xp` | `xp` | `xp` | INT |
| 10 | `topshots[1]` | `killing_spree` | `killing_spree_best` | INT |
| 11 | `topshots[2]` | `death_spree` | `death_spree_worst` | INT |
| 12 | `topshots[3]` | `kill_assists` | `kill_assists` | INT |
| 13 | `topshots[4]` | `kill_steals` | `kill_steals` | INT |
| 14 | `topshots[5]` | `headshot_kills` | `headshot_kills` | INT |
| 15 | `topshots[6]` | `objectives_stolen` | `objectives_stolen` | INT |
| 16 | `topshots[7]` | `objectives_returned` | `objectives_returned` | INT |
| 17 | `topshots[8]` | `dynamites_planted` | `dynamites_planted` | INT |
| 18 | `topshots[9]` | `dynamites_defused` | `dynamites_defused` | INT |
| 19 | `topshots[10]` | `times_revived` | `times_revived` | INT |
| 20 | `topshots[11]` | `bullets_fired` | `bullets_fired` | INT |
| 21 | `topshots[12]` | `dpm` | `dpm` | FLOAT |
| 22 | `tp/1000/60` | `time_played_minutes` | `time_played_minutes` | FLOAT (min) |
| 23 | `topshots[13]` | `tank_meatshield` | `tank_meatshield` | FLOAT |
| 24 | `topshots[14]` | `time_dead_ratio` | `time_dead_ratio` | FLOAT (%) |
| 25 | `death_time_total/60000` | `time_dead_minutes` | `time_dead_minutes` | FLOAT (min) |
| 26 | `kd` | `kd_ratio` | `kd_ratio` | FLOAT |
| 27 | `topshots[15]` | `useful_kills` | `most_useful_kills` | INT |
| 28 | `topshots[16]/1000` | `denied_playtime` | `denied_playtime` | INT (sec) |
| 29 | `multikills[1]` | `multikill_2x` | `double_kills` | INT |
| 30 | `multikills[2]` | `multikill_3x` | `triple_kills` | INT |
| 31 | `multikills[3]` | `multikill_4x` | `quad_kills` | INT |
| 32 | `multikills[4]` | `multikill_5x` | `multi_kills` | INT |
| 33 | `multikills[5]` | `multikill_6x` | `mega_kills` | INT |
| 34 | `topshots[17]` | `useless_kills` | `useless_kills` | INT |
| 35 | `topshots[18]` | `full_selfkills` | `full_selfkills` | INT |
| 36 | `topshots[19]` | `repairs_constructions` | `constructions` | INT |
| 37 | `topshots[20]` | `revives_given` | `revives_given` | INT |

### Weapon stats per player (space-separated, per weapon)

| Index | Lua Source | Parser Key | DB Column (weapon table) |
|-------|-----------|------------|--------------------------|
| 0 | `aWeaponStats[j][4]` | hits | `hits` |
| 1 | `aWeaponStats[j][1]` | shots | `shots` |
| 2 | `aWeaponStats[j][5]` | kills | `kills` |
| 3 | `aWeaponStats[j][2]` | deaths | `deaths` |
| 4 | `aWeaponStats[j][3]` | headshots | `headshots` (HITS, not kills!) |

### Aggregate player fields (derived by parser, stored in player table)

| Parser Field | Source | DB Column |
|-------------|--------|-----------|
| `player['headshots']` | SUM of per-weapon `aWeaponStats[j][3]` | `headshots` (head HITS) |
| `player['kills']` | SUM of per-weapon kills | `kills` |
| `player['deaths']` | SUM of per-weapon deaths | `deaths` |
| `player['accuracy']` | total_hits / total_shots × 100 | `accuracy` |
| `player['time_played_seconds']` | **Round duration from header** (not per-player!) | `time_played_seconds` |

---

## 5. c0rnp0rn Lua Reference

### Death Time Tracking (pause-aware)

```lua
-- On death (et_Obituary):
death_time[victim] = et.trap_Milliseconds()

-- On spawn (et_ClientSpawn):
if death_time[id] ~= 0 then
    diff = et.trap_Milliseconds() - death_time[id] 
           - (paused_death[id][2] - paused_death[id][1])  -- subtract pause overlap
    death_time_total[id] = death_time_total[id] + diff
end
death_time[id] = 0

-- On pause start:
if denies[i][1] == true then
    paused_death[i][1] = et.trap_Milliseconds()
end

-- On unpause:
if denies[i][1] == true then
    paused_death[i][2] = et.trap_Milliseconds()
end
```

### Denied Playtime Tracking

```lua
-- On normal kill (different teams):
denies[victim] = { [1]=true, [2]=killer, [3]=et.trap_Milliseconds() }

-- On victim spawn:
if denies[id][1] == true then
    topshots[denies[id][2]][16] += (spawn_time - death_time - pause_overlap)
    denies[id] = { false, -1, 0 }
end

-- On intermission (finalize pending):
for all connected team players:
    if denies[i][1] then
        topshots[denies[i][2]][16] += (end_time - death_time - pause_overlap)
    end
```

### Useful Kills / Useless Kills Logic

```lua
-- On normal kill:
local nextRespawnTime = calculateReinfTime(victim_team)

-- Useful: kill timed when victim must wait a LONG time (>= half of team's limbo time)
if nextRespawnTime >= (limbotime / 1000) / 2 then
    topshots[killer][15] += 1  -- useful_kills

-- Useless: kill timed when victim respawns almost instantly (< 5 seconds)
if nextRespawnTime < 5 and nextRespawnTime > 0 then
    topshots[killer][17] += 1  -- useless_kills
```

**Note:** `calculateReinfTime()` uses the game's reinforcement seed system to determine exact seconds until next wave. This is not a simple countdown — it accounts for team-specific offsets and server configuration.

### timePlayed field (CAUTION: this is a PERCENTAGE!)

```lua
timePlayed = timeAxis + timeAllies == 0 and 0 
             or (100.0 * timePlayed / (timeAxis + timeAllies))
-- This is the engine's timePlayed as a percentage of team time.
-- NOT the actual time in seconds!
-- Stored as TAB[8] in the stats file.

-- Actual play time in milliseconds:
tp = timeAxis + timeAllies  -- this is what gets converted to minutes for TAB[22]
```

---

## 6. Recommended Fixes

### Priority 1: Headshot Percentage (affects all displays)

**Change `calculate_headshot_percentage()` signature:**
```python
# OLD (wrong):
def calculate_headshot_percentage(headshots, kills):
    return (headshots / kills) * 100

# NEW (correct):
def calculate_headshot_accuracy(headshot_hits, total_hits):
    """What % of hits landed on the head."""
    return (headshot_hits / total_hits) * 100

# OPTIONAL (keep as separate stat):
def calculate_headshot_kill_rate(headshot_kills, total_kills):
    """What % of kills were headshot kills."""
    return (headshot_kills / total_kills) * 100
```

**Data source for callers:**
- `headshot_hits` = `player_comprehensive_stats.headshots` (already stored — sum of weapon headshot HITS)
- `total_hits` = `SUM(weapon_comprehensive_stats.hits)` for the player (need to query or add column)
- Consider adding `total_hits` to `player_comprehensive_stats` for convenience

### Priority 2: time_played_seconds (affects FP, DPM, survival)

**In parser, prefer per-player Lua time over round header time:**
```python
# After extracting objective_stats:
lua_time_min = objective_stats.get('time_played_minutes', 0)
if lua_time_min > 0:
    player['time_played_seconds'] = int(lua_time_min * 60)
else:
    player['time_played_seconds'] = round_time_seconds  # fallback to header
```

### Priority 3: Website formula alignment

Unify website formulas with bot:
- FragPotential: `(damage_given / time_alive_seconds) × 60`
- Damage Efficiency: `damage_given / max(1, damage_received)` (ratio, not %)
- Survival Rate: `100 - (time_dead / time_played × 100)` (actual, not heuristic)

### Priority 4: Denied playtime display

- Primary display: raw time (MM:SS format)
- Comparison display: per-minute rate (denied_seconds / time_played_minutes)
- Drop or clearly label the current percentage display

---

## Appendix: File Index

All files containing calculated stats formulas that may need changes:

| File | What it does | Formula issues |
|------|-------------|----------------|
| `bot/stats/calculator.py` | Centralized stat formulas | ❌ Headshot % |
| `bot/core/frag_potential.py` | FP + Playstyle detection | ❌ Headshot %, ⚠️ time source |
| `bot/cogs/stats_cog.py` | `!stats` command | ❌ Headshot % (via calculator) |
| `bot/community_stats_parser.py` | Stats file parsing + embed | ❌ HS rate mixed units |
| `bot/services/session_graph_generator.py` | Session charts | ⚠️ Time source, ⚠️ denied % |
| `website/backend/routers/api.py` | All API endpoints | ❌ Headshot %, ❌ FP, ❌ Survival, ⚠️ DmgEff |
| `website/js/retro-viz.js` | Chart.js visualizations | Consumes API data (fix API, JS is fine) |
