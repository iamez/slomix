# Proximity Tracker Reference

Complete reference of everything the proximity tracker captures.

---

## Player Movement Tracking

Every active player is tracked from spawn to death with samples every 500ms.

### Per-Sample Data

| Field | Type | Description |
|-------|------|-------------|
| `time` | integer | Game time in milliseconds |
| `x`, `y`, `z` | float | Position coordinates (Quake 3 coordinate system) |
| `health` | integer | Current health (0-100+) |
| `speed` | float | Horizontal movement speed (X,Y only, ignoring Z) |
| `weapon` | integer | Currently equipped weapon ID |
| `stance` | integer | 0=standing, 1=crouching, 2=prone |
| `sprint` | integer | 0=not sprinting, 1=sprinting |
| `event` | string | Event type: `spawn`, `sample`, `death`, `round_end` |

### Per-Player Track Metadata

| Field | Type | Description |
|-------|------|-------------|
| `guid` | string | Player's persistent GUID (from CL_GUID or slot-based fallback) |
| `name` | string | Player name (sanitized for CSV safety) |
| `team` | string | `AXIS` or `ALLIES` |
| `class` | string | `SOLDIER`, `MEDIC`, `ENGINEER`, `FIELDOPS`, or `COVERTOPS` |
| `spawn_time` | integer | Game time when player spawned (ms) |
| `death_time` | integer | Game time when player died, or NULL if survived |
| `first_move_time` | integer | First time player moved >10 units/sec after spawn |

### Sampling Strategy

| Phase | Sample Rate | Notes |
|-------|-------------|-------|
| Pre-combat | Every 500ms | Position, health, speed, weapon, stance, sprint |
| During engagement | Every 500ms + on damage | Additional samples on each hit received |
| Escape detection | Every 500ms | Continues until escape criteria met |
| Round end | Final snapshot | `round_end` event for all alive players |

---

## Combat Engagements

An engagement is created when a player takes damage and tracks all combat until death or escape.

### Engagement Data

| Field | Type | Description |
|-------|------|-------------|
| `engagement_id` | integer | Unique ID within the round |
| `start_time` | integer | Game time of first damage (ms) |
| `end_time` | integer | Game time of death/escape/round_end (ms) |
| `duration` | integer | Total engagement duration (ms) |
| `target_guid` | string | GUID of player being attacked |
| `target_name` | string | Name of player being attacked |
| `target_team` | string | Team of target (`AXIS` or `ALLIES`) |
| `outcome` | string | `killed`, `escaped`, or `round_end` |
| `total_damage` | integer | Total damage taken during engagement |
| `distance_traveled` | float | How far target moved during engagement |

### Per-Attacker Data

For each attacker in an engagement:

| Field | Type | Description |
|-------|------|-------------|
| `guid` | string | Attacker's GUID |
| `name` | string | Attacker's name |
| `team` | string | Attacker's team |
| `damage` | integer | Total damage this attacker dealt |
| `hits` | integer | Number of times this attacker hit |
| `first_hit` | integer | Game time of first hit (ms) |
| `last_hit` | integer | Game time of last hit (ms) |
| `got_kill` | boolean | Whether this attacker got the killing blow |
| `weapons` | string | Comma-separated list of weapons used |

### Killer Attribution

| Field | Type | Description |
|-------|------|-------------|
| `killer_guid` | string | GUID of player who got final blow (if killed) |
| `killer_name` | string | Name of killer |

---

## Crossfire Detection

A crossfire is detected when 2+ players damage the same target within a configurable time window (default: 1000ms).

### Crossfire Data

| Field | Type | Description |
|-------|------|-------------|
| `is_crossfire` | boolean | True if 2+ attackers hit within window |
| `crossfire_delay` | integer | Time (ms) between first and second attacker's hits |
| `crossfire_participants` | array | List of GUIDs of all attackers in the crossfire |

### Detection Logic

```
1. When player takes first damage, start engagement
2. Track all attackers with timestamps
3. If second attacker hits within 1000ms of first hit:
   - Mark is_crossfire = true
   - Record delay between first and second hit
   - Add all subsequent attackers within window to participants
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `CROSSFIRE_WINDOW_MS` | 1000 | Time window for crossfire detection |

---

## Escape Detection

An escape is detected when a player survives combat by meeting time and distance thresholds.

### Escape Criteria

| Condition | Default | Description |
|-----------|---------|-------------|
| Time since last damage | 5000ms | Must go 5 seconds without taking damage |
| Distance from last hit | 300 units | Must move 300 units from where last hit occurred |

Both conditions must be met simultaneously.

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ESCAPE_TIME_MS` | 5000 | Time without damage to trigger escape check |
| `ESCAPE_DISTANCE` | 300 | Distance required to confirm escape |

---

## Heatmaps

Two types of heatmaps are generated per round using a grid system.

### Kill Heatmap

Tracks where kills occur on the map.

| Field | Type | Description |
|-------|------|-------------|
| `grid_x` | integer | Grid cell X coordinate |
| `grid_y` | integer | Grid cell Y coordinate |
| `axis_kills` | integer | Kills by Axis players in this cell |
| `allies_kills` | integer | Kills by Allies players in this cell |

### Movement Heatmap

Tracks where players move and under what conditions.

| Field | Type | Description |
|-------|------|-------------|
| `grid_x` | integer | Grid cell X coordinate |
| `grid_y` | integer | Grid cell Y coordinate |
| `traversal_count` | integer | General movement samples |
| `combat_count` | integer | Samples during active engagements |
| `escape_count` | integer | Samples during escape detection |

### Grid Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `GRID_SIZE` | 512 | Grid cell size in game units |

---

## Round/Map Metadata

### Round Information

| Field | Type | Description |
|-------|------|-------------|
| `map_name` | string | Current map name (from server config) |
| `round_number` | integer | Current round (from `g_currentRound` cvar) |
| `start_time` | integer | Game time when round started (ms) |

### Round Detection

- **Round Start:** Detected in `et_InitGame()` callback
- **Round End:** Detected when gamestate transitions from `0` (playing) to `3` (intermission)

---

## Player Identity

### GUID Resolution

Players are identified by GUID in this priority order:

1. **CL_GUID** - Clan client GUID (most reliable)
2. **Slot-based fallback** - If no GUID available, uses `SLOT_{clientnum}`

### Name Sanitization

Player names are sanitized to prevent parsing issues:
- Color codes (^0-^9) are stripped
- Semicolons replaced with underscores
- Pipe characters replaced with underscores
- Control characters removed

---

## ET:Legacy Lua API Used

| Function | Purpose |
|----------|---------|
| `et.gentity_get(clientnum, field)` | Get entity properties (position, health, team, etc.) |
| `et.trap_Milliseconds()` | Get current game time |
| `et.trap_FS_Write()` | Write output to file |
| `et.trap_Cvar_Get()` | Get server cvars (map name, round number) |

### Callbacks Used

| Callback | When Called |
|----------|-------------|
| `et_InitGame()` | Round/map start |
| `et_RunFrame()` | Every server frame (sampling happens here) |
| `et_Damage()` | When player takes damage |
| `et_Obituary()` | When player dies |
| `et_ClientSpawn()` | When player spawns |

---

## Data NOT Currently Captured

The following data is **not** captured by the current tracker:

| Data | Why It's Missing | Impact |
|------|-----------------|--------|
| Round outcome (winner) | No game event for this | Can't track W/L |
| Objective status | Would need objective position configs | Can't measure objective focus |
| "Team" identity | Only tracks Axis/Allies per round | Can't group players across side-switches |
| Damage direction | Not exposed in API | Can't analyze flanking |
| Means of death | Available but not captured | Can't distinguish headshots |
| Respawn timing | Not tracked | Can't analyze respawn waves |

See [GAPS_AND_ROADMAP.md](GAPS_AND_ROADMAP.md) for planned improvements.
