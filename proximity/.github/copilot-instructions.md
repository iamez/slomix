# Proximity Tracker v3 - AI Agent Instructions

## Project Identity
**ET:Legacy Proximity Tracker** - Engagement-centric combat analytics for Wolfenstein: Enemy Territory. Tracks crossfire coordination, escape events, and generates per-map heatmaps.

## Architecture Overview

### Three Components

1. **Lua Script** (`lua/proximity_tracker.lua`)
   - Runs on ET:Legacy game server
   - Hooks: `et_Damage`, `et_Obituary`, `et_RunFrame`
   - Outputs: `*_engagements.txt` files

2. **Python Parser** (`parser/parser.py`)
   - Parses engagement files
   - Updates aggregated stats in PostgreSQL
   - Class: `ProximityParserV3`

3. **PostgreSQL Schema** (`schema/schema.sql`)
   - 5 tables for engagement data
   - Forever storage (~50MB/year)

## Key Algorithms

### Crossfire Detection
```lua
-- 2+ attackers hit same target within 1 second
crossfire_window_ms = 1000
```

### Escape Detection
```lua
-- 5 seconds no damage AND 300+ units traveled
escape_time_ms = 5000
escape_distance = 300
```

### Position Sampling
```lua
-- Every 2 seconds during active engagement
position_sample_interval = 2000
```

## Database Tables

| Table | Purpose | Growth |
|-------|---------|--------|
| `combat_engagement` | One row per engagement | ~365K/year |
| `player_teamplay_stats` | Aggregated per player | ~200 rows |
| `crossfire_pairs` | Duo coordination | ~200 rows |
| `map_kill_heatmap` | Per-map kill density | ~1K rows |
| `map_movement_heatmap` | Per-map traffic | ~2K rows |

## File Format

Output filename: `YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt`

Sections:
1. `# ENGAGEMENTS` - Combat engagement data (semicolon-delimited)
2. `# KILL_HEATMAP` - Grid-based kill counts
3. `# MOVEMENT_HEATMAP` - Traversal/combat/escape counts

## Integration with Bot

```python
from proximity.parser import ProximityParserV3

parser = ProximityParserV3(db_adapter=self.db, output_dir="gamestats")
await parser.import_file(filepath, session_date)
```

## Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `lua/proximity_tracker.lua` | 641 | Game server module |
| `parser/parser.py` | 666 | DB import & aggregation |
| `schema/schema.sql` | 362 | PostgreSQL tables |

## Conventions

1. **JSONB for complex data** - attackers array, position paths
2. **Aggregated stats** - player_teamplay_stats updated incrementally
3. **Per-map heatmaps** - separate grids per map_name
4. **GUID everywhere** - link to bot's player system

## Testing

```bash
# Parse a file without DB
python parser/parser.py path/to/engagements.txt

# Output shows engagement count, crossfire %, kills/escapes
```

## Config (in Lua)

```lua
config = {
    crossfire_window_ms = 1000,  -- 1 second
    escape_time_ms = 5000,       -- 5 seconds
    escape_distance = 300,       -- 300 units
    position_sample_interval = 2000,  -- 2 seconds
    grid_size = 512,             -- heatmap cell size
    min_damage = 1               -- any damage counts
}
```
