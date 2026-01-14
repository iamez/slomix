# Proximity Tracker - Developer's Technical Reference

Complete technical documentation for developers working with the proximity tracking system.

---

## Table of Contents

1. [Lua API Reference](#lua-api-reference)
2. [Python API Reference](#python-api-reference)
3. [Database Schema Details](#database-schema-details)
4. [Configuration Options](#configuration-options)
5. [Extending the System](#extending-the-system)
6. [Debugging Guide](#debugging-guide)

---

## Lua API Reference

### Module Structure

```lua
-- proximity_tracker.lua module structure

local proximity = {
    position_history = {},      -- [clientnum] = {snapshots[], write_index}
    combat_events = {},         -- Array of combat events
    active_engagements = {},    -- Current ongoing fights
    engagement_history = {},    -- Completed engagements
    player_movement = {},       -- Movement tracking per player
    kill_heatmap = {},         -- Grid-based kill density
    nearby_players_cache = {},  -- Cached proximity data
    last_position_snapshot_time = 0,
    game_start_time = 0,
    round_data = {
        round_num = 0,
        map_name = "",
        start_time = 0
    }
}

local config = {
    enabled = true,
    debug = false,
    output_dir = "gamestats/",
    position_update_interval = 1000,
    max_position_snapshots = 600,
    stationary_threshold = 5,
    stationary_duration = 3000,
    proximity_check_distance = 300,
    crossfire_distance = 200,
    engagement_min_damage = 10,
    grid_size = 512
}
```

### Utility Functions

#### `distance3D(pos1, pos2) -> number`
Calculate 3D Euclidean distance between two positions.

```lua
local dist = distance3D({x=0, y=0, z=0}, {x=100, y=100, z=100})
-- Returns: 173.2
```

**Parameters:**
- `pos1` (table) - Position with x, y, z fields
- `pos2` (table) - Position with x, y, z fields

**Returns:** Distance in units (float)

---

#### `getPlayerPos(clientnum) -> table`
Get player's current 3D position.

```lua
local pos = getPlayerPos(0)
-- Returns: {x=1234.5, y=5678.9, z=0.0}
```

**Parameters:**
- `clientnum` (int) - Client ID (0-63)

**Returns:** Position table {x, y, z}

---

#### `getPlayerVelocity(clientnum) -> table`
Get player's velocity vector.

```lua
local vel = getPlayerVelocity(0)
-- Returns: {x=150.0, y=0.0, z=0.0}
```

**Parameters:**
- `clientnum` (int) - Client ID

**Returns:** Velocity vector {x, y, z}

---

#### `getPlayerSpeed(clientnum) -> number`
Calculate movement speed (magnitude of velocity).

```lua
local speed = getPlayerSpeed(0)
-- Returns: 150.0
```

**Parameters:**
- `clientnum` (int) - Client ID

**Returns:** Speed in units/sec (float)

---

#### `getNearbyPlayers(clientnum, distance_threshold, same_team_only) -> table`
Find players near specified client.

```lua
local nearby = getNearbyPlayers(0, 300, false)
-- Returns: {
--   {clientnum=5, name="Player1", team="AXIS", distance=150.5, is_teammate=true},
--   {clientnum=8, name="Player2", team="ALLIES", distance=250.0, is_teammate=false}
-- }
```

**Parameters:**
- `clientnum` (int) - Reference client ID
- `distance_threshold` (int) - Maximum distance in units
- `same_team_only` (bool) - If true, only return teammates

**Returns:** Array of nearby player tables

---

#### `logCombatEvent(event_type, attacker, target, data) -> nil`
Log a combat event (fire, hit, kill).

```lua
logCombatEvent("hit", 0, 3, {
    damage = 25,
    mod = 5,  -- Means of death constant
    distance = 150.5,
    weapon = 10
})
```

**Parameters:**
- `event_type` (string) - "fire", "hit", or "kill"
- `attacker` (int) - Attacking client ID
- `target` (int) - Target client ID (nil for fire events)
- `data` (table) - Event-specific data

**Event Data Fields:**
- `weapon` (int) - Weapon ID
- `distance` (float) - Distance between players
- `damage` (int) - Damage dealt
- `mod` (int) - Means of death
- `hit_region` (int) - Hit region constant

---

#### `analyzeEngagement(attacker, target) -> table`
Analyze fight context and determine engagement type.

```lua
local engagement = analyzeEngagement(0, 3)
-- Returns: {
--   type = "2v1",
--   distance = 150.5,
--   attacker_backup = 1,
--   target_backup = 0
-- }
```

**Parameters:**
- `attacker` (int) - Attacking client ID
- `target` (int) - Target client ID

**Returns:** Engagement analysis table
- `type` (string) - "1v1", "2v1", "1v2", "2v2", etc.
- `distance` (float) - Fight range
- `attacker_backup` (int) - Nearby allies of attacker
- `target_backup` (int) - Nearby allies of target

---

### Engine Callbacks

#### `et_InitGame(levelTime, randomSeed, restart)`
Called when game initializes (map load).

```lua
function et_InitGame(levelTime, randomSeed, restart)
    -- Initialize module
    -- Reset data tables
    -- Load configuration
end
```

---

#### `et_RunFrame(levelTime)`
Called every server frame (~50ms).

```lua
function et_RunFrame(levelTime)
    -- Position snapshot recording
    -- State checking (gamestate)
    -- Proximity analysis
end
```

**Typical Usage:**
```lua
function et_RunFrame(levelTime)
    if gamestate ~= 0 then return end  -- Only during play
    
    if levelTime >= next_update_time then
        updatePositions()
        next_update_time = levelTime + update_interval
    end
end
```

---

#### `et_WeaponFire(clientNum, weapon) -> int`
Called when player fires weapon.

```lua
function et_WeaponFire(clientNum, weapon)
    -- Log fire event
    -- Track ammunition
    -- Detect spray patterns
    
    return 0  -- 0 = allow, 1 = intercept
end
```

**Parameters:**
- `clientNum` (int) - Firing client
- `weapon` (int) - Weapon ID constant

**Returns:** 0 to allow, 1 to prevent

---

#### `et_Damage(target, attacker, damage, damageFlags, meansOfDeath)`
Called when damage is dealt.

```lua
function et_Damage(target, attacker, damage, damageFlags, meansOfDeath)
    -- Log hit event
    -- Record attacker/target positions
    -- Analyze engagement context
    -- Update heatmap
end
```

**Parameters:**
- `target` (int) - Victim client ID
- `attacker` (int) - Attacker client ID (1022=world, 1023=unknown)
- `damage` (int) - Damage amount
- `damageFlags` (int) - Damage type flags
- `meansOfDeath` (int) - MOD_* constant

---

#### `et_Obituary(victim, killer, meansOfDeath)`
Called when player dies.

```lua
function et_Obituary(victim, killer, meansOfDeath)
    -- Log kill event
    -- Record kill location
    -- Update engagement history
    -- Add to heatmap
end
```

**Parameters:**
- `victim` (int) - Killed player ID
- `killer` (int) - Killer ID (1022=world, 1023=unknown)
- `meansOfDeath` (int) - MOD_* constant

---

#### `et_ClientSpawn(clientnum, revived, teamChange, restoreHealth)`
Called when player spawns.

```lua
function et_ClientSpawn(clientnum, revived, teamChange, restoreHealth)
    -- Initialize player tracking
    -- Reset engagement data
    -- Start fresh position history
end
```

---

#### `et_ClientDisconnect(clientnum)`
Called when player disconnects.

```lua
function et_ClientDisconnect(clientnum)
    -- Clean up player data
    -- Remove from position history
    -- Close any active engagements
end
```

---

## Python API Reference

### ProximityDataParser Class

```python
class ProximityDataParser:
    def __init__(self, db_adapter=None, output_dir: str = "gamestats"):
        """Initialize parser"""
    
    def find_proximity_files(self, session_date: str, round_num: int) -> Dict[str, str]:
        """Find proximity tracker output files"""
    
    async def import_proximity_data(self, session_date: str, round_num: int) -> bool:
        """Full import pipeline"""
    
    async def store_in_database(self, session_date: str, round_num: int):
        """Store parsed data in PostgreSQL"""
    
    def get_statistics(self) -> Dict:
        """Generate statistics from parsed data"""
```

#### `find_proximity_files(session_date, round_num) -> Dict`

Find all proximity tracker output files for a session.

```python
files = parser.find_proximity_files('2025-12-20', 1)
# Returns: {
#     'positions': 'gamestats/2025-12-20-120000-supply-round-1_positions.txt',
#     'combat': 'gamestats/2025-12-20-120000-supply-round-1_combat.txt',
#     'engagements': 'gamestats/2025-12-20-120000-supply-round-1_engagements.txt',
#     'heatmap': 'gamestats/2025-12-20-120000-supply-round-1_heatmap.txt'
# }
```

**Parameters:**
- `session_date` (str) - Session date (YYYY-MM-DD)
- `round_num` (int) - Round number (1 or 2)

**Returns:** Dict with file paths or None for missing files

---

#### `parse_positions_file(filepath) -> List[Dict]`

Parse position snapshots file.

```python
positions = parser.parse_positions_file('gamestats/2025-12-20-120000-supply-round-1_positions.txt')
# Returns: [
#     {'clientnum': 0, 'time': 1000, 'x': 1234.5, 'y': 5678.9, 'z': 0.0, ...},
#     {'clientnum': 0, 'time': 2000, 'x': 1240.2, 'y': 5690.1, 'z': 0.0, ...},
#     ...
# ]
```

**Parameters:**
- `filepath` (str) - Path to *_positions.txt file

**Returns:** List of position snapshot dictionaries

---

#### `parse_combat_file(filepath) -> List[Dict]`

Parse combat events file.

```python
events = parser.parse_combat_file('gamestats/2025-12-20-120000-supply-round-1_combat.txt')
# Returns: [
#     {'timestamp': 5000, 'type': 'fire', 'attacker': 0, 'target': None, 'distance': 0.0, ...},
#     {'timestamp': 5100, 'type': 'hit', 'attacker': 0, 'target': 3, 'distance': 150.5, ...},
#     ...
# ]
```

**Parameters:**
- `filepath` (str) - Path to *_combat.txt file

**Returns:** List of combat event dictionaries

---

#### `parse_engagements_file(filepath) -> List[Dict]`

Parse engagement analysis file.

```python
engagements = parser.parse_engagements_file('gamestats/2025-12-20-120000-supply-round-1_engagements.txt')
# Returns: [
#     {'type': '1v1', 'distance': 150.5, 'killer': 'PlayerName1', 'victim': 'PlayerName2'},
#     {'type': '2v1', 'distance': 200.3, 'killer': 'PlayerName3', 'victim': 'PlayerName4'},
#     ...
# ]
```

**Parameters:**
- `filepath` (str) - Path to *_engagements.txt file

**Returns:** List of engagement dictionaries

---

#### `parse_heatmap_file(filepath) -> List[Dict]`

Parse heatmap grid file.

```python
heatmap = parser.parse_heatmap_file('gamestats/2025-12-20-120000-supply-round-1_heatmap.txt')
# Returns: [
#     {'grid_x': 0, 'grid_y': 0, 'axis_kills': 5, 'allies_kills': 3},
#     {'grid_x': 1, 'grid_y': 0, 'axis_kills': 8, 'allies_kills': 2},
#     ...
# ]
```

**Parameters:**
- `filepath` (str) - Path to *_heatmap.txt file

**Returns:** List of heatmap cell dictionaries

---

#### `async import_proximity_data(session_date, round_num) -> bool`

Full import pipeline: find files, parse, store in database.

```python
success = await parser.import_proximity_data('2025-12-20', 1)
if success:
    stats = parser.get_statistics()
    print(f"Imported {stats['total_positions']} position records")
```

**Parameters:**
- `session_date` (str) - Session date (YYYY-MM-DD)
- `round_num` (int) - Round number (1 or 2)

**Returns:** True if successful, False otherwise

---

#### `get_statistics() -> Dict`

Generate statistics from parsed data.

```python
stats = parser.get_statistics()
# Returns: {
#     'total_positions': 12000,
#     'total_combat_events': 450,
#     'total_engagements': 85,
#     'total_heatmap_cells': 64,
#     'combat_by_type': {'fire': 350, 'hit': 400, 'kill': 85},
#     'engagement_type_count': {'1v1': 50, '2v1': 20, '1v2': 15},
#     'average_engagement_distance': 165.5,
#     'hotspots': [
#         {'grid': '(0, 0)', 'axis_kills': 12, 'allies_kills': 8},
#         ...
#     ]
# }
```

**Returns:** Dictionary with statistics

---

## Database Schema Details

### player_positions Table

```sql
CREATE TABLE player_positions (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    clientnum INTEGER NOT NULL,
    timestamp BIGINT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    yaw REAL NOT NULL,
    pitch REAL NOT NULL,
    speed REAL NOT NULL,
    moving INTEGER NOT NULL
);
```

**Indexes:**
- `(session_date, round_number, clientnum, timestamp)` UNIQUE
- `(session_date, round_number)`
- `(clientnum)`
- `(timestamp)`
- `(clientnum, timestamp DESC)`

**Sample Queries:**

```sql
-- Get player's movement path
SELECT * FROM player_positions 
WHERE session_date = '2025-12-20' AND clientnum = 0
ORDER BY timestamp;

-- Find stationary players
SELECT clientnum, COUNT(*) as stationary_count
FROM player_positions
WHERE moving = 0
GROUP BY clientnum;

-- Find fast-moving players
SELECT clientnum, AVG(speed) as avg_speed
FROM player_positions
WHERE session_date = '2025-12-20'
GROUP BY clientnum
ORDER BY avg_speed DESC;
```

---

### combat_events Table

```sql
CREATE TABLE combat_events (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    timestamp BIGINT NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    attacker INTEGER NOT NULL,
    target INTEGER,
    distance REAL,
    nearby_allies INTEGER DEFAULT 0,
    nearby_enemies INTEGER DEFAULT 0,
    damage INTEGER DEFAULT 0
);
```

**Event Types:**
- `fire` - Weapon discharged
- `hit` - Damage dealt
- `kill` - Player killed

**Indexes:**
- `(session_date, round_number)`
- `(event_type)`
- `(attacker)`
- `(target)`
- `(timestamp)`

**Sample Queries:**

```sql
-- Count shots fired per player
SELECT attacker, COUNT(*) as shots_fired
FROM combat_events
WHERE session_date = '2025-12-20' AND event_type = 'fire'
GROUP BY attacker;

-- Find high-damage hits
SELECT * FROM combat_events
WHERE event_type = 'hit' AND damage > 50
ORDER BY damage DESC;

-- Find kills with nearby enemies
SELECT * FROM combat_events
WHERE event_type = 'kill' AND nearby_enemies > 0
ORDER BY timestamp;
```

---

### engagement_analysis Table

```sql
CREATE TABLE engagement_analysis (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    engagement_type VARCHAR(20) NOT NULL,
    distance REAL NOT NULL,
    killer_name VARCHAR(64),
    victim_name VARCHAR(64)
);
```

**Engagement Types:**
- `1v1` - Solo fight
- `2v1` - Two vs one
- `1v2` - One vs two
- `2v2` - Team fight
- `3v1`, `3v2`, etc.

**Sample Queries:**

```sql
-- Count engagement types
SELECT engagement_type, COUNT(*) as count
FROM engagement_analysis
WHERE session_date = '2025-12-20'
GROUP BY engagement_type;

-- Average fight distance by type
SELECT engagement_type, AVG(distance) as avg_distance
FROM engagement_analysis
WHERE session_date = '2025-12-20'
GROUP BY engagement_type
ORDER BY avg_distance;
```

---

### proximity_heatmap Table

```sql
CREATE TABLE proximity_heatmap (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    axis_kills INTEGER DEFAULT 0,
    allies_kills INTEGER DEFAULT 0
);
```

**Unique Index:** `(session_date, round_number, grid_x, grid_y)`

**Sample Queries:**

```sql
-- Top 10 hotspots
SELECT grid_x, grid_y, (axis_kills + allies_kills) as total_kills
FROM proximity_heatmap
WHERE session_date = '2025-12-20'
ORDER BY total_kills DESC
LIMIT 10;

-- Axis-dominated areas
SELECT grid_x, grid_y, axis_kills, allies_kills
FROM proximity_heatmap
WHERE axis_kills > allies_kills * 2
AND session_date = '2025-12-20';
```

---

## Configuration Options

All in `proximity_tracker.lua` `config` table:

```lua
config = {
    -- Master enable/disable
    enabled = true,
    debug = false,
    output_dir = "gamestats/",
    
    -- Position tracking
    position_update_interval = 1000,    -- ms between snapshots
    max_position_snapshots = 600,       -- ~10 min at 1Hz
    stationary_threshold = 5,           -- units/sec
    stationary_duration = 3000,         -- ms to count as stationary
    
    -- Proximity analysis
    proximity_check_distance = 300,     -- units for nearby check
    crossfire_distance = 200,           -- units for crossfire
    engagement_min_damage = 10,         -- minimum damage to log
    
    -- Map heatmap
    grid_size = 512                     -- units per cell
}
```

### Recommended Settings

**High Detail (lots of data):**
```lua
position_update_interval = 500      -- 2 snapshots/sec
proximity_check_distance = 500      -- Further detection
grid_size = 256                     -- Fine granularity
```

**Balanced (default):**
```lua
position_update_interval = 1000     -- 1 snapshot/sec
proximity_check_distance = 300      -- Normal detection
grid_size = 512                     -- Coarse granularity
```

**Low Detail (small files):**
```lua
position_update_interval = 2000     -- 0.5 snapshots/sec
proximity_check_distance = 200      -- Limited detection
grid_size = 1024                    -- Very coarse
```

---

## Extending the System

### Adding New Engagement Types

In `proximity_tracker.lua`, modify `analyzeEngagement()`:

```lua
function analyzeEngagement(attacker, target)
    -- ... existing code ...
    
    local engagement_type = "UNKNOWN"
    
    -- Custom engagement detection
    if attacker_backup == 0 and target_backup == 0 then
        engagement_type = "1v1"
    elseif attacker_backup >= 2 then
        engagement_type = string.format("%dv1", 1 + attacker_backup)
    elseif hasLineOfSight(attacker, target) then
        engagement_type = "SNIPED"  -- NEW
    else
        engagement_type = "COVERED"  -- NEW
    end
    
    return {type = engagement_type, distance = ..., ...}
end
```

Then update the parser to handle new types:

```python
# In proximity_parser.py
'engagement_type_count': {
    '1v1': 50,
    '2v1': 20,
    'SNIPED': 15,  # NEW
    'COVERED': 8    # NEW
}
```

---

### Adding Team Synergy Tracking

Create new function in `proximity_tracker.lua`:

```lua
function trackTeamSynergy(attacker, target)
    local attacker_team = et.gentity_get(attacker, "sess.sessionTeam")
    local nearby_allies = getNearbyPlayers(attacker, config.crossfire_distance, true)
    
    for _, ally in ipairs(nearby_allies) do
        if ally.clientnum ~= attacker then
            local synergy_event = {
                time = et.trap_Milliseconds(),
                ally1 = attacker,
                ally2 = ally.clientnum,
                target = target,
                type = "CROSSFIRE"
            }
            table.insert(proximity.synergy_events, synergy_event)
        end
    end
end
```

---

### Custom Output Format

Modify `outputProximityData()` to add custom file:

```lua
local custom_file = basename .. "_custom.txt"
local fd = et.trap_FS_FOpenFile(custom_file, et.FS_WRITE)

-- Write header
local header = "# CUSTOM_DATA\n"
et.trap_FS_Write(header, string.len(header), fd)

-- Write custom events
for _, event in ipairs(proximity.custom_events) do
    local line = formatCustomLine(event)
    et.trap_FS_Write(line, string.len(line), fd)
end

et.trap_FS_FCloseFile(fd)
```

---

## Debugging Guide

### Enable Debug Mode

```lua
config.debug = true
```

This outputs to server console:
```
[PROX] InitGame: Map=mp_beach, Round=1
[PROX] Combat Event: hit - Attacker: 0, Target: 3
[PROX] Engagement: 2v1 at 150.5 units
[PROX] Round ended - saving data
[PROX] Positions saved: gamestats/2025-12-20-120000-supply-round-1_positions.txt
```

---

### Check File Output

```bash
# Verify files created
ls -lah gamestats/*_*.txt | tail -8

# Check file sizes (should be substantial)
wc -l gamestats/*_positions.txt

# Check format
head -20 gamestats/*_positions.txt
```

---

### Validate Data

```python
# Check for parsing errors
parser = ProximityDataParser()
try:
    positions = parser.parse_positions_file('gamestats/2025-12-20-120000-supply-round-1_positions.txt')
    print(f"✓ Parsed {len(positions)} positions")
except Exception as e:
    print(f"✗ Parse error: {e}")

# Check database integrity
SELECT COUNT(*) FROM player_positions WHERE session_date = '2025-12-20';
SELECT COUNT(*) FROM combat_events WHERE session_date = '2025-12-20';
```

---

### Performance Monitoring

```sql
-- Check database size
SELECT pg_size_pretty(pg_total_relation_size('player_positions'));
SELECT pg_size_pretty(pg_total_relation_size('combat_events'));

-- Slow queries
SELECT query, calls, mean_time FROM pg_stat_statements 
WHERE query LIKE '%proximity%'
ORDER BY mean_time DESC;

-- Index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE tablename LIKE '%position%';
```

---

### Common Issues

**No output files:**
```
Cause: Round didn't complete
Fix: Play full warmup → play → intermission
```

**Parser crashes:**
```
Cause: File format changed or corrupted
Fix: Check file with `head` command, compare to spec
```

**Database import fails:**
```
Cause: Schema not created
Fix: psql -U et_bot -d et_stats < bot/proximity_schema.sql
```

**High memory usage:**
```
Cause: max_position_snapshots too large
Fix: Reduce to 300 (5 minutes) or less
```

---

**End of Developer Reference**
