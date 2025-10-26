# 📚 API Reference - Bot Commands & Methods

**Last Updated:** October 6, 2025  
**Purpose:** Complete reference for all FIVEEYES commands and methods

---

## 🤖 Discord Bot Commands

### Phase 1 Commands (Synergy Detection)

#### `!synergy` / `!chemistry` / `!duo`

Show synergy analysis between two players.

**Usage:**
```
!synergy @Player1 @Player2
!synergy PlayerName1 PlayerName2
!chemistry Player1 Player2
```

**Parameters:**
- `player1` (optional): First player (@mention or name)
- `player2` (optional): Second player (@mention or name)

**Output:**
- Overall synergy rating (Excellent/Good/Neutral/Poor)
- Games together statistics
- Win rate when together
- Performance boost percentage
- Synergy score (0-1.0)
- Confidence level

**Example:**
```
!synergy @superboy @oldschoolplayer
```

---

#### `!best_duos` / `!top_duos` / `!best_pairs`

Show top player combinations by synergy score.

**Usage:**
```
!best_duos              # Top 10 duos
!best_duos 20           # Top 20 duos
!top_duos               # Alias
```

**Parameters:**
- `limit` (optional, default=10): Number of duos to show

**Output:**
- Ranked list of player pairs
- Synergy score for each pair
- Win rate together
- Performance boost
- Games played together

---

#### `!team_builder` / `!balance_teams` / `!suggest_teams`

Suggest balanced teams based on synergies.

**Usage:**
```
!team_builder @P1 @P2 @P3 @P4 @P5 @P6
```

**Parameters:**
- 6+ player mentions (required)

**Output:**
- Suggested Team A composition
- Suggested Team B composition
- Team synergy scores
- Balance rating
- Predicted outcome

**Algorithm:**
- Tries all possible team combinations
- Calculates team synergy (sum of pair synergies)
- Finds most balanced split (minimal difference)

---

#### `!player_impact`

Show which teammates a player performs best with.

**Usage:**
```
!player_impact              # Your impact
!player_impact @Player      # Someone else's impact
```

**Parameters:**
- `player` (optional): Player to analyze

**Output:**
- Best teammates (top 5)
- Worst teammates (bottom 5)
- Average synergy score
- Number of unique partners

---

### Phase 2 Commands (Role Normalization)

#### `!leaderboard` / `!lb` / `!top`

Show leaderboards with fair role-normalized scoring.

**Usage:**
```
!leaderboard                 # Overall normalized leaderboard
!leaderboard engineers       # Top engineers
!leaderboard medics          # Top medics
!leaderboard kd              # Traditional K/D leaderboard
!lb normalized 20            # Top 20
```

**Parameters:**
- `stat` (optional, default='normalized'): Leaderboard type
  - `normalized` / `overall` - Role-normalized scores
  - `engineers` / `engineer` - Best engineers
  - `medics` / `medic` - Best medics
  - `fieldops` / `fo` - Best field ops
  - `soldiers` / `soldier` - Best soldiers
  - `covert` - Best covert ops
  - `kd` / `kills` - Traditional K/D
- `limit` (optional, default=10): Number of players

**Output:**
- Ranked list with normalized scores
- Class indicators (💉🔧📡💣🔍)
- Performance scores
- Games played

---

#### `!class_stats` / `!classes` / `!my_classes`

Show player's performance across all classes.

**Usage:**
```
!class_stats                 # Your class stats
!class_stats @Player         # Someone else's stats
```

**Parameters:**
- `player` (optional): Player to analyze (default: self)

**Output:**
- Performance score for each class played
- Best class indicator
- Games played per class
- Percentile ranking per class

---

#### `!compare` / `!vs`

Fairly compare two players even on different classes.

**Usage:**
```
!compare @Player1 @Player2
!vs PlayerName1 PlayerName2
```

**Parameters:**
- `player1` (required): First player
- `player2` (required): Second player

**Output:**
- Normalized performance scores
- Classes played
- Statistical comparison
- Winner determination

---

### Phase 3 Commands (Proximity Tracking - Optional)

#### `!teamwork` / `!proximity` / `!crossfire`

Show teamwork analysis based on proximity tracking.

**Usage:**
```
!teamwork @Player1 @Player2
!proximity Player1 Player2
!crossfire @P1 @P2
```

**Parameters:**
- `player1` (required): First player
- `player2` (required): Second player

**Output:**
- Time spent near each other
- Combat events together (crossfire)
- Teamwork score
- Support rating
- Analysis/interpretation

---

### Admin Commands

#### `!tune_weights`

Adjust role weights based on community feedback. (Admin only)

**Usage:**
```
!tune_weights engineer objectives 3.5
!tune_weights medic revives 2.8
```

**Parameters:**
- `player_class` (required): Class to tune
- `stat` (required): Stat to adjust
- `new_weight` (required): New weight value

**Output:**
- Confirmation of change
- Trigger score recalculation

---

#### `!recalculate_synergies`

Manually trigger synergy recalculation. (Admin only)

**Usage:**
```
!recalculate_synergies
```

**Output:**
- Progress updates
- Number of synergies calculated
- Completion confirmation

---

## 🔧 Python API

### SynergyDetector Class

**Location:** `analytics/synergy_detector.py`

```python
from analytics.synergy_detector import SynergyDetector

detector = SynergyDetector(db_path='etlegacy_production.db')
```

#### Methods

**`calculate_synergy(player_a_guid, player_b_guid)`**

Calculate synergy between two players.

```python
synergy = await detector.calculate_synergy(
    "5C3D0BC7ABC123",
    "D8423F90XYZ456"
)

if synergy:
    print(f"Synergy score: {synergy.synergy_score}")
    print(f"Games together: {synergy.games_together}")
    print(f"Win rate: {synergy.win_rate_together:.1%}")
```

**Returns:** `SynergyMetrics` or `None`

---

**`calculate_all_synergies()`**

Calculate synergies for all player pairs.

```python
count = await detector.calculate_all_synergies()
print(f"Calculated {count} synergies")
```

**Returns:** Number of synergies calculated (int)

---

**`get_player_best_partners(player_guid, limit=5)`**

Get best teammates for a player.

```python
partners = await detector.get_player_best_partners(
    "5C3D0BC7ABC123",
    limit=5
)

for partner in partners:
    print(f"{partner['name']}: {partner['synergy_score']}")
```

**Returns:** List of dicts with partner info

---

### PerformanceNormalizer Class

**Location:** `analytics/performance_normalizer.py`

```python
from analytics.performance_normalizer import PerformanceNormalizer

normalizer = PerformanceNormalizer()
```

#### Methods

**`calculate_performance_score(stats, player_class)`**

Calculate role-normalized performance score.

```python
stats = {
    'kills': 25,
    'deaths': 10,
    'damage_given': 7000,
    'revives_given': 8,
    'time_played_seconds': 900
}

score = normalizer.calculate_performance_score(stats, 'medic')
print(f"Normalized score: {score:.1f}")
```

**Parameters:**
- `stats` (dict): Player statistics
- `player_class` (str): 'medic', 'engineer', 'soldier', 'fieldops', 'covert'

**Returns:** Normalized score (float)

---

**`get_class_rankings(player_guid, db_path)`**

Get player's performance across all classes.

```python
rankings = normalizer.get_class_rankings(
    "5C3D0BC7ABC123",
    "etlegacy_production.db"
)

for class_name, score in rankings.items():
    print(f"{class_name}: {score:.1f}")
```

**Returns:** Dict of {class_name: score}

---

**`compare_players_fairly(player_a_stats, player_a_class, player_b_stats, player_b_class)`**

Fairly compare two players on different classes.

```python
result = normalizer.compare_players_fairly(
    engineer_stats, 'engineer',
    medic_stats, 'medic'
)

print(result)  # "Player A", "Player B", or "Tied"
```

**Returns:** "Player A", "Player B", or "Tied"

---

### ProximityAnalyzer Class (Phase 3)

**Location:** `analytics/proximity_analyzer.py`

```python
from analytics.proximity_analyzer import ProximityAnalyzer

analyzer = ProximityAnalyzer(db_path='etlegacy_production.db')
```

#### Methods

**`calculate_teamwork_score(player_a_guid, player_b_guid)`**

Calculate teamwork based on proximity data.

```python
metrics = await analyzer.calculate_teamwork_score(
    "5C3D0BC7ABC123",
    "D8423F90XYZ456"
)

if metrics:
    print(f"Time together: {metrics.time_together}s")
    print(f"Combat events: {metrics.combat_events}")
    print(f"Teamwork score: {metrics.teamwork_score}")
```

**Returns:** `TeamworkMetrics` or `None`

---

## 📦 Data Structures

### SynergyMetrics (dataclass)

```python
@dataclass
class SynergyMetrics:
    games_together: int          # Total games in same session
    games_same_team: int         # Games on same team
    wins_together: int           # Wins when together
    win_rate_together: float     # 0.0-1.0
    win_rate_boost: float        # Boost vs expected (-1.0 to 1.0)
    performance_boost: float     # Performance boost (-1.0 to 1.0)
    synergy_score: float         # Overall score (-1.0 to 1.0)
    confidence: float            # Statistical confidence (0.0-1.0)
```

---

### PlayerPerformance (dataclass)

```python
@dataclass
class PlayerPerformance:
    kills: float
    deaths: float
    damage: float
    objectives: int
    revives: int
    kd_ratio: float
    dpm: float                   # Damage per minute
    games_played: int
```

---

### RoleWeights (dataclass)

```python
@dataclass
class RoleWeights:
    kills: float = 1.0
    deaths: float = 1.0
    damage: float = 1.0
    objectives: float = 1.0
    revives: float = 1.0
    constructions: float = 1.0
    destructions: float = 1.0
    dynamites: float = 1.0
    survival_time: float = 1.0
```

---

### TeamworkMetrics (dataclass - Phase 3)

```python
@dataclass
class TeamworkMetrics:
    time_together: float         # Seconds near each other
    combat_events: int           # Crossfire setups
    teamwork_score: float        # Calculated score
    crossfire_setups: int        # Combat proximity events
```

---

## 🔄 Background Tasks

### `recalculate_synergies` Task

Runs daily to update all synergy scores.

**Location:** `bot/ultimate_bot.py`

```python
@tasks.loop(hours=24)
async def recalculate_synergies(self):
    """Recalculate all synergies once per day"""
    # Runs at 00:00 UTC daily
```

---

### `update_player_ratings` Task

Runs daily to update normalized ratings.

```python
@tasks.loop(hours=24)
async def update_player_ratings(self):
    """Update player ratings daily"""
    # Runs at 01:00 UTC daily
```

---

## 📊 Database Queries

### Get All Synergies for a Player

```python
async with aiosqlite.connect(db_path) as db:
    cursor = await db.execute('''
        SELECT 
            player_b_guid,
            synergy_score,
            games_same_team,
            win_rate_together
        FROM player_synergies
        WHERE player_a_guid = ?
        ORDER BY synergy_score DESC
        LIMIT 10
    ''', (player_guid,))
    
    rows = await cursor.fetchall()
```

---

### Get Leaderboard (Normalized)

```python
async with aiosqlite.connect(db_path) as db:
    cursor = await db.execute('''
        SELECT 
            player_guid,
            normalized_score,
            games_played,
            overall_rating
        FROM player_ratings
        ORDER BY normalized_score DESC
        LIMIT 10
    ''')
    
    rows = await cursor.fetchall()
```

---

## 🎯 Quick Reference

### Command Summary

| Command | Phase | Purpose |
|---------|-------|---------|
| `!synergy` | 1 | Show duo chemistry |
| `!best_duos` | 1 | Top player pairs |
| `!team_builder` | 1 | Suggest balanced teams |
| `!leaderboard` | 2 | Fair role-normalized rankings |
| `!class_stats` | 2 | Player's class performance |
| `!compare` | 2 | Fair player comparison |
| `!teamwork` | 3 | Proximity-based teamwork |

### Class Indicators

- 💉 Medic
- 🔧 Engineer
- 📡 Field Ops
- 💣 Soldier
- 🔍 Covert Ops

---

**For more details, see phase-specific documentation.**
