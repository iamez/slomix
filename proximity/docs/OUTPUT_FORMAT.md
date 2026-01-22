# Output Format Specification

The proximity tracker outputs a single text file per round containing all tracking data.

---

## File Naming

```text
{output_dir}/{YYYY-MM-DD-HHMMSS}-{mapname}-round-{N}_engagements.txt
```yaml

Example: `proximity/2026-01-10-193245-supply-round-1_engagements.txt`

---

## File Structure

The file contains these sections in order:

1. **Header** - Configuration and metadata
2. **ENGAGEMENTS** - Combat engagement records
3. **PLAYER_TRACKS** - Full movement paths for all players
4. **KILL_HEATMAP** - Kill locations grid
5. **MOVEMENT_HEATMAP** - Movement density grid

---

## 1. Header Section

Lines starting with `#` are comments/metadata.

```text
# PROXIMITY_TRACKER_V4
# map=supply
# round=1
# crossfire_window=1000
# escape_time=5000
# escape_distance=300
# position_sample_interval=500
```yaml

| Field | Description |
|-------|-------------|
| `map` | Map name |
| `round` | Round number (1 or 2 typically) |
| `crossfire_window` | Crossfire detection window in ms |
| `escape_time` | Time without damage to trigger escape (ms) |
| `escape_distance` | Distance required to confirm escape (units) |
| `position_sample_interval` | How often positions are sampled (ms) |

---

## 2. ENGAGEMENTS Section

### Format Header

```text
# ENGAGEMENTS
# id;start_time;end_time;duration;target_guid;target_name;target_team;outcome;total_damage;killer_guid;killer_name;num_attackers;is_crossfire;crossfire_delay;crossfire_participants;start_x;start_y;start_z;end_x;end_y;end_z;distance_traveled;positions;attackers
```yaml

### Field Delimiter

- **Primary:** Semicolon (`;`) separates fields
- **Nested:** Pipe (`|`) separates items in lists
- **Sub-nested:** Comma (`,`) separates values within items

### Fields

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | id | int | Unique engagement ID within round |
| 2 | start_time | int | Game time of first damage (ms) |
| 3 | end_time | int | Game time of death/escape/round_end (ms) |
| 4 | duration | int | Total engagement duration (ms) |
| 5 | target_guid | string | GUID of player being attacked |
| 6 | target_name | string | Name of player being attacked |
| 7 | target_team | string | `AXIS` or `ALLIES` |
| 8 | outcome | string | `killed`, `escaped`, or `round_end` |
| 9 | total_damage | int | Total damage taken during engagement |
| 10 | killer_guid | string | GUID of killer (empty if escaped) |
| 11 | killer_name | string | Name of killer (empty if escaped) |
| 12 | num_attackers | int | Number of unique attackers |
| 13 | is_crossfire | string | `1` if crossfire, `0` otherwise |
| 14 | crossfire_delay | int | Time between first and second hit (ms) |
| 15 | crossfire_participants | string | Comma-separated GUIDs of crossfire attackers |
| 16-18 | start_x,y,z | float | Position when engagement started |
| 19-21 | end_x,y,z | float | Position when engagement ended |
| 22 | distance_traveled | float | Total distance moved during engagement |
| 23 | positions | string | Position path (see below) |
| 24 | attackers | string | Attacker details (see below) |

### Position Path Format (Field 23)

Pipe-separated list of position samples during the engagement.

```text
time,x,y,z,event|time,x,y,z,event|...
```yaml

| Value | Description |
|-------|-------------|
| time | Game time (ms) |
| x,y,z | Position coordinates |
| event | `hit`, `sample`, `escape`, or `death` |

Example:

```text
15000,1234.5,5678.2,100.0,hit|15500,1240.0,5680.0,100.0,sample|16000,1250.0,5690.0,100.0,death
```text

### Attackers Format (Field 24)

Pipe-separated list of attackers.

```text
guid,name,team,damage,hits,first_hit,last_hit,got_kill,weapons|...
```yaml

| Value | Description |
|-------|-------------|
| guid | Attacker's GUID |
| name | Attacker's name |
| team | `AXIS` or `ALLIES` |
| damage | Total damage dealt |
| hits | Number of hits |
| first_hit | Time of first hit (ms) |
| last_hit | Time of last hit (ms) |
| got_kill | `1` if got killing blow, `0` otherwise |
| weapons | Weapon usage: `weaponid:count;weaponid:count;...` |

Example:

```text
ABC123,Player1,AXIS,85,3,15000,15800,1,8:2;9:1|DEF456,Player2,AXIS,40,2,15100,15500,0,8:2
```yaml

---

## 3. PLAYER_TRACKS Section

### Format Header

```text
# PLAYER_TRACKS
# guid;name;team;class;spawn_time;death_time;first_move_time;samples;path
# path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |
# stance: 0=standing, 1=crouching, 2=prone | sprint: 0=no, 1=yes
```python

### Fields

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | guid | string | Player's GUID |
| 2 | name | string | Player's name |
| 3 | team | string | `AXIS` or `ALLIES` |
| 4 | class | string | `SOLDIER`, `MEDIC`, `ENGINEER`, `FIELDOPS`, `COVERTOPS` |
| 5 | spawn_time | int | Game time when spawned (ms) |
| 6 | death_time | int | Game time when died, or `0` if survived |
| 7 | first_move_time | int | First time speed exceeded 10 units/sec |
| 8 | samples | int | Number of path samples |
| 9 | path | string | Full movement path (see below) |

### Path Format (Field 9)

Pipe-separated list of position samples from spawn to death.

```text
time,x,y,z,health,speed,weapon,stance,sprint,event|...
```yaml

| Value | Type | Description |
|-------|------|-------------|
| time | int | Game time (ms) |
| x,y,z | float | Position coordinates |
| health | int | Current health |
| speed | float | Horizontal movement speed |
| weapon | int | Weapon ID |
| stance | int | 0=standing, 1=crouching, 2=prone |
| sprint | int | 0=not sprinting, 1=sprinting |
| event | string | `spawn`, `sample`, `death`, or `round_end` |

Example:

```text
10000,1500.0,2000.0,100.0,100,0.0,8,0,0,spawn|10500,1520.0,2010.0,100.0,100,45.5,8,0,1,sample|...
```yaml

---

## 4. KILL_HEATMAP Section

### Format Header

```text
# KILL_HEATMAP
# grid_x;grid_y;axis_kills;allies_kills
```yaml

### Fields

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | grid_x | int | Grid cell X coordinate |
| 2 | grid_y | int | Grid cell Y coordinate |
| 3 | axis_kills | int | Kills by Axis players in this cell |
| 4 | allies_kills | int | Kills by Allies players in this cell |

### Grid Calculation

```text
grid_x = floor(x / 512)
grid_y = floor(y / 512)
```text

Example:

```text
2;4;3;1
3;4;5;2
```yaml

---

## 5. MOVEMENT_HEATMAP Section

### Format Header

```text
# MOVEMENT_HEATMAP
# grid_x;grid_y;traversal;combat;escape
```yaml

### Fields

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | grid_x | int | Grid cell X coordinate |
| 2 | grid_y | int | Grid cell Y coordinate |
| 3 | traversal | int | General movement sample count |
| 4 | combat | int | Samples during active engagements |
| 5 | escape | int | Samples during escape detection |

Example:

```text
2;4;150;45;12
3;4;200;30;8
```yaml

---

## Parsing Example (Python)

```python
def parse_proximity_file(filepath):
    engagements = []
    player_tracks = []
    kill_heatmap = []
    movement_heatmap = []
    metadata = {}

    current_section = None

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Parse metadata
            if line.startswith('# map='):
                metadata['map'] = line.split('=')[1]
            elif line.startswith('# round='):
                metadata['round'] = int(line.split('=')[1])

            # Detect section changes
            elif line == '# ENGAGEMENTS':
                current_section = 'engagements'
            elif line == '# PLAYER_TRACKS':
                current_section = 'tracks'
            elif line == '# KILL_HEATMAP':
                current_section = 'kill_heatmap'
            elif line == '# MOVEMENT_HEATMAP':
                current_section = 'movement_heatmap'

            # Skip comment lines
            elif line.startswith('#'):
                continue

            # Parse data lines
            elif current_section == 'engagements':
                fields = line.split(';')
                engagements.append({
                    'id': int(fields[0]),
                    'target_guid': fields[4],
                    'outcome': fields[7],
                    'is_crossfire': fields[12] == '1',
                    # ... parse other fields
                })

            elif current_section == 'tracks':
                fields = line.split(';')
                player_tracks.append({
                    'guid': fields[0],
                    'name': fields[1],
                    'team': fields[2],
                    'class': fields[3],
                    # ... parse other fields
                })

    return {
        'metadata': metadata,
        'engagements': engagements,
        'player_tracks': player_tracks,
        'kill_heatmap': kill_heatmap,
        'movement_heatmap': movement_heatmap
    }
```

---

## Notes

- All times are in milliseconds from round start
- Coordinates use the Quake 3 coordinate system
- Names are sanitized (color codes stripped, special chars replaced)
- Empty fields use empty string, not NULL
- Boolean fields use `1`/`0` string representation
