# Proximity Tracker v3 - Engagement-Centric Combat Analytics

ET:Legacy module for tracking combat engagements, crossfire coordination, and escape detection.

## Design Philosophy

**NOT tracking:** Every bullet, every position, every frame  
**Tracking:** Combat engagements (start→outcome), crossfire windows, escape events

## Data Volume

| Metric | Per Round | Per Year |
|--------|-----------|----------|
| Engagements | ~100 | ~365K |
| Player stats | aggregated | ~200 rows |
| Heatmap cells | per-map | ~3K rows |

**Total: ~370K rows/year = ~50MB = Forever storable**

## Key Algorithms

### Crossfire Detection
- 2+ attackers hit same target within **1 second** window
- Tracks delay between attackers (lower = better coordination)

### Escape Detection  
- **5 seconds** no damage received AND
- **300 units** distance from last hit position

### Position Sampling
- Every **2 seconds** during active engagement
- Plus events: start, hit, death, escape

## Project Structure

```
proximity/
├── lua/
│   └── proximity_tracker.lua    # Game server module
├── parser/
│   └── parser.py                # Parse engagement files
├── schema/
│   └── schema.sql               # PostgreSQL tables
└── README.md
```

## Installation

1. Copy `lua/proximity_tracker.lua` to game server's lua_modules
2. Add to server config: `lua_modules "c0rnp0rn.lua proximity_tracker.lua"`
3. Run `schema/schema.sql` on PostgreSQL database
4. Import parser in bot code:

```python
from proximity.parser import ProximityParserV3

# Or full path:
from proximity.parser.parser import ProximityParserV3

parser = ProximityParserV3(db_adapter=self.db, output_dir="gamestats")
await parser.import_file(filepath, session_date)
```

## Output Files

Format: `YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt`

Contains:
- Combat engagements with attackers, positions, outcomes
- Kill heatmap (grid-based)
- Movement heatmap (traversal/combat/escape counts)

## Database Tables

- `combat_engagement` - One row per engagement, JSONB for attackers/positions
- `player_teamplay_stats` - Aggregated forever stats per player
- `crossfire_pairs` - Duo coordination tracking
- `map_kill_heatmap` - Per-map kill/death density
- `map_movement_heatmap` - Per-map traffic patterns
