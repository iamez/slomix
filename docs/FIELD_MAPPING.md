# Field Mapping Reference

Complete reference of all stats fields captured by the ET:Legacy Stats Bot.

---

## 📊 Player Stats Fields (50+ fields per player)

### Core Identity Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `player_name` | VARCHAR(100) | In-game player name | `seareal` |
| `guid` | VARCHAR(32) | ET player GUID | `ABC123...` |
| `team` | VARCHAR(20) | Team assignment | `axis` or `allies` |
| `is_bot` | BOOLEAN | Bot player flag | `true`/`false` |

---

### Combat Statistics

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `kills` | INTEGER | Enemy kills | `15` |
| `deaths` | INTEGER | Times killed | `8` |
| `team_kills` | INTEGER | Friendly fire kills | `0` |
| `team_deaths` | INTEGER | Deaths by friendly fire | `0` |
| `self_kills` | INTEGER | Suicide count | `0` |
| `headshots` | INTEGER | Headshot kills | `3` |

**Calculation Examples:**

- K/D Ratio: `kills / deaths` → `15 / 8 = 1.87`
- Headshot %: `headshots / kills * 100` → `3 / 15 * 100 = 20%`

---

### Accuracy Statistics

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `shots` | INTEGER | Total shots fired | `450` |
| `hits` | INTEGER | Total hits landed | `128` |
| `accuracy_percent` | DECIMAL(5,2) | Hit percentage | `28.44` |

**Calculation:**

```text
accuracy_percent = (hits / shots) * 100
Example: (128 / 450) * 100 = 28.44%
```sql

---

### Damage Statistics

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `damage_given` | INTEGER | Damage dealt to enemies | `1850` |
| `damage_received` | INTEGER | Damage taken from enemies | `1200` |
| `damage_team` | INTEGER | Friendly fire damage | `0` |

**Damage Efficiency:**

```text
damage_ratio = damage_given / damage_received
Example: 1850 / 1200 = 1.54
```yaml

---

### Support & Objectives

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `revives` | INTEGER | Players revived (medic) | `8` |
| `ammogiven` | INTEGER | Ammo packs given | `12` |
| `healthgiven` | INTEGER | Health packs given | `15` |
| `obj_captured` | INTEGER | Objectives captured | `2` |
| `obj_destroyed` | INTEGER | Objectives destroyed | `1` |
| `obj_returned` | INTEGER | Objectives returned | `0` |
| `obj_taken` | INTEGER | Objectives taken | `1` |

---

### Experience Points (XP)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `xp_total` | INTEGER | Total XP earned | `380` |
| `xp_combat` | INTEGER | Combat XP | `150` |
| `xp_objective` | INTEGER | Objective XP | `120` |
| `xp_support` | INTEGER | Support XP (medic/ammo) | `90` |
| `xp_misc` | INTEGER | Miscellaneous XP | `20` |

**XP Breakdown:**

```text
xp_total = xp_combat + xp_objective + xp_support + xp_misc
Example: 150 + 120 + 90 + 20 = 380
```yaml

---

### Time Tracking

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `time_played_seconds` | INTEGER | Total play time in seconds | `900` |
| `time_axis_seconds` | INTEGER | Time on Axis team | `900` |
| `time_allies_seconds` | INTEGER | Time on Allies team | `0` |

**Time Conversions:**

```text
Minutes = seconds / 60
Hours = seconds / 3600

Example: 900 seconds = 15 minutes
```python

---

### Team Assignment Metadata

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `team_source` | VARCHAR(50) | How team was determined | `snapshot` |
| `team_confidence` | DECIMAL(3,2) | Confidence level (0-1) | `0.95` |

**Team Sources:**

- `snapshot` - End-of-round team snapshot
- `tracker` - Time-based team tracking
- `vote` - Majority vote from multiple sources
- `manual` - Manual override

---

## 🔫 Weapon Stats Fields (per weapon per player)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `weapon_name` | VARCHAR(100) | Weapon identifier | `thompson` |
| `kills` | INTEGER | Kills with this weapon | `8` |
| `deaths` | INTEGER | Deaths while holding weapon | `3` |
| `headshots` | INTEGER | Headshots with weapon | `2` |
| `shots` | INTEGER | Shots fired | `180` |
| `hits` | INTEGER | Hits landed | `58` |
| `accuracy_percent` | DECIMAL(5,2) | Weapon accuracy | `32.22` |

**Common Weapons:**

- `thompson` - Thompson SMG (Allies)
- `mp40` - MP40 SMG (Axis)
- `panzerfaust` - Rocket launcher
- `k43` - K43 rifle (Axis)
- `garand` - M1 Garand (Allies)
- `fg42` - FG42 (Axis)
- `knife` - Melee weapon
- `grenade` - Grenades

---

## 🗺️ Round Metadata Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `session_id` | VARCHAR(50) | Session identifier | `2025-11-06-210000` |
| `round_num` | INTEGER | Round number (1 or 2) | `1` |
| `map_name` | VARCHAR(100) | Map played | `supply` |
| `map_id` | VARCHAR(100) | Unique map identifier | `supply_v2` |
| `timestamp` | TIMESTAMP | When round occurred | `2025-11-06 21:00:00` |
| `duration_seconds` | INTEGER | Round duration | `900` |
| `axis_score` | INTEGER | Axis team score | `0` |
| `allies_score` | INTEGER | Allies team score | `1` |
| `winning_team` | VARCHAR(20) | Winner | `allies` |
| `gaming_session_id` | INTEGER | Session group ID | `42` |

---

## 📁 Processed Files Tracking

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `file_path` | VARCHAR(500) | Full file path | `/stats/2025-11-06-210000-supply-round-1.txt` |
| `file_hash` | VARCHAR(64) | SHA256 hash | `a3f5...` |
| `processed_at` | TIMESTAMP | Import timestamp | `2025-11-06 21:05:00` |
| `round_id` | INTEGER | Associated round | `249` |

---

## 🎮 Gaming Session Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `session_start` | TIMESTAMP | Session start time | `2025-11-06 19:00:00` |
| `session_end` | TIMESTAMP | Session end time | `2025-11-06 23:30:00` |
| `total_rounds` | INTEGER | Rounds in session | `18` |
| `unique_maps` | INTEGER | Different maps played | `6` |
| `total_players` | INTEGER | Unique players | `12` |
| `duration_seconds` | INTEGER | Total session time | `16200` |

**Session Logic:**

- Rounds within 12 hours = same session
- Gap > 12 hours = new session

---

## 🔗 Player Links (Discord Integration)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `discord_id` | BIGINT | Discord user ID | `123456789012345678` |
| `player_name` | VARCHAR(100) | ET player name | `seareal` |
| `guid` | VARCHAR(32) | ET player GUID | `ABC123...` |
| `created_at` | TIMESTAMP | Link creation time | `2025-11-01 12:00:00` |

---

## 📊 Data Types & Ranges

### Integer Fields

```sql
INTEGER: -2,147,483,648 to 2,147,483,647
Typical range: 0 to 1000 for most stats
```text

### Decimal Fields

```sql
DECIMAL(5,2): 000.00 to 999.99
Used for: accuracy_percent, team_confidence
```text

### Text Fields

```sql
VARCHAR(N): Variable-length text up to N characters
player_name: up to 100 chars
weapon_name: up to 100 chars
```text

### Timestamp Fields

```sql
TIMESTAMP: Date and time
Format: YYYY-MM-DD HH:MM:SS
Example: 2025-11-06 21:30:45
```yaml

---

## 🎯 Field Validation Rules

### Player Name

- Length: 1-100 characters
- Sanitized for SQL safety
- Case-sensitive

### Team

- Must be: `axis` or `allies`
- Lowercase only
- Required for all players

### Numeric Fields

- Non-negative integers (≥ 0)
- Kills, deaths, shots, hits, etc.
- Exception: Can be 0

### Accuracy

- Range: 0.00 to 100.00
- Calculated: `(hits / shots) * 100`
- Null if shots = 0

### Team Confidence

- Range: 0.00 to 1.00
- 1.00 = 100% confident
- 0.50 = 50% confident

---

## 📈 Calculated Fields

### K/D Ratio

```sql
ROUND(CAST(kills AS FLOAT) / NULLIF(deaths, 0), 2) AS kd_ratio
```text

### Headshot Percentage

```sql
ROUND((headshots * 100.0) / NULLIF(kills, 0), 2) AS headshot_percent
```text

### Damage Efficiency

```sql
ROUND(CAST(damage_given AS FLOAT) / NULLIF(damage_received, 0), 2) AS damage_ratio
```text

### Kills Per Minute

```sql
ROUND((kills * 60.0) / NULLIF(time_played_seconds, 0), 2) AS kills_per_minute
```text

### Average XP Per Round

```sql
ROUND(AVG(xp_total), 0) AS avg_xp
```yaml

---

## 🔍 Common Queries

### Player Total Stats

```sql
SELECT 
    player_name,
    SUM(kills) as total_kills,
    SUM(deaths) as total_deaths,
    ROUND(AVG(accuracy_percent), 2) as avg_accuracy,
    COUNT(DISTINCT round_id) as rounds_played
FROM player_stats
WHERE player_name = 'seareal'
GROUP BY player_name;
```text

### Top Players by K/D

```sql
SELECT 
    player_name,
    SUM(kills) as kills,
    SUM(deaths) as deaths,
    ROUND(CAST(SUM(kills) AS FLOAT) / NULLIF(SUM(deaths), 0), 2) as kd
FROM player_stats
GROUP BY player_name
HAVING SUM(deaths) > 0
ORDER BY kd DESC
LIMIT 10;
```text

### Weapon Usage

```sql
SELECT 
    weapon_name,
    SUM(kills) as total_kills,
    ROUND(AVG(accuracy_percent), 2) as avg_accuracy
FROM weapon_stats
GROUP BY weapon_name
ORDER BY total_kills DESC;
```yaml

---

## 📝 Field Presence

**Always Present (Required):**

- ✅ player_name
- ✅ team
- ✅ kills
- ✅ deaths
- ✅ round_id

**Usually Present:**

- ✅ shots, hits, accuracy
- ✅ damage_given, damage_received
- ✅ time_played_seconds
- ✅ xp_total

**Sometimes Present (Class-Dependent):**

- 🔶 revives (medic only)
- 🔶 ammogiven (field ops only)
- 🔶 healthgiven (medic only)

**Rarely Present:**

- 🔸 team_kills, team_deaths (hopefully 0!)
- 🔸 self_kills (accidents happen)

---

## 🎮 Example: Complete Player Record

```json
{
  "player_name": "seareal",
  "team": "axis",
  "is_bot": false,
  
  "combat": {
    "kills": 15,
    "deaths": 8,
    "team_kills": 0,
    "team_deaths": 0,
    "self_kills": 0,
    "headshots": 3
  },
  
  "accuracy": {
    "shots": 450,
    "hits": 128,
    "accuracy_percent": 28.44
  },
  
  "damage": {
    "damage_given": 1850,
    "damage_received": 1200,
    "damage_team": 0
  },
  
  "support": {
    "revives": 8,
    "ammogiven": 12,
    "healthgiven": 15
  },
  
  "objectives": {
    "obj_captured": 2,
    "obj_destroyed": 1,
    "obj_returned": 0,
    "obj_taken": 1
  },
  
  "xp": {
    "xp_total": 380,
    "xp_combat": 150,
    "xp_objective": 120,
    "xp_support": 90,
    "xp_misc": 20
  },
  
  "time": {
    "time_played_seconds": 900,
    "time_axis_seconds": 900,
    "time_allies_seconds": 0
  },
  
  "weapons": [
    {
      "weapon_name": "thompson",
      "kills": 8,
      "deaths": 3,
      "headshots": 2,
      "shots": 180,
      "hits": 58,
      "accuracy_percent": 32.22
    },
    {
      "weapon_name": "mp40",
      "kills": 7,
      "deaths": 5,
      "headshots": 1,
      "shots": 270,
      "hits": 70,
      "accuracy_percent": 25.93
    }
  ]
}
```

---

## 🔗 Related Documentation

- [DATA_PIPELINE.md](DATA_PIPELINE.md) - How data flows through the system
- [TECHNICAL_OVERVIEW.md](TECHNICAL_OVERVIEW.md) - Complete system architecture
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Historical documentation

---

**Total Fields Tracked:** 50+ per player per round  
**Total Weapons:** 10-15 common weapons  
**Database Size:** Scales to 100,000+ rounds  
**Query Performance:** <50ms with proper indexes
