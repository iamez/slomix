# Proximity Tracker - Quick Start Guide

## What Is It?

**Proximity Tracker** is a standalone ET:Legacy Lua module that runs alongside c0rnp0rn.lua to track:
- **Player Positions** - 3D coordinates every second throughout the round
- **Combat Events** - Every shot, hit, and kill with spatial context
- **Engagement Analysis** - Fight types (1v1, 2v1, 2v2, etc.)
- **Teammate Coordination** - Crossfire, baiting, support fire patterns
- **Kill Heatmaps** - Grid-based kill density for map visualization

## Output

4 files per round saved to `gamestats/`:
- `*_positions.txt` - Position snapshots
- `*_combat.txt` - Combat events with nearby player counts
- `*_engagements.txt` - Engagement type summary
- `*_heatmap.txt` - Kill density grid

## Installation (5 minutes)

### 1. Copy Lua Script
```bash
cp proximity_tracker.lua /path/to/et_legacy/legacy/
```

### 2. Update Server Config
```cfg
seta lua_modules "c0rnp0rn.lua proximity_tracker.lua"
```

### 3. Restart Server
```
map_restart
```

### 4. Verify
Check server console for: `>>> Proximity Tracker v1.0 loaded successfully`

## Python Integration

### 1. Copy Parser
```bash
cp bot/proximity_parser.py /path/to/discord_bot/bot/
```

### 2. Create Database Tables
```bash
psql -U et_bot -d et_stats < bot/proximity_schema.sql
```

### 3. Update Stats Parser
Add to `community_stats_parser.py`:
```python
from bot.proximity_parser import ProximityDataParser

async def import_stats():
    # ... existing c0rnp0rn import ...
    
    # Import proximity data
    prox = ProximityDataParser(db_adapter)
    await prox.import_proximity_data(session_date, round_num)
```

## Usage Examples

### Query Kill Heatmap
```sql
SELECT grid_x, grid_y, axis_kills, allies_kills 
FROM proximity_heatmap 
WHERE session_date = '2025-12-20'
ORDER BY (axis_kills + allies_kills) DESC 
LIMIT 10;
```

### Find 1v1 Statistics
```sql
SELECT COUNT(*) as count, AVG(distance) as avg_distance 
FROM engagement_analysis 
WHERE session_date = '2025-12-20' AND engagement_type = '1v1';
```

### Player Engagement Performance
```sql
SELECT player_name, total_engagements, solo_kills, team_kills 
FROM player_engagement_stats 
WHERE session_date = '2025-12-20'
ORDER BY solo_kills DESC;
```

## Configuration

Edit in `proximity_tracker.lua`:

```lua
config = {
    position_update_interval = 1000,  -- 1 snapshot per second
    proximity_check_distance = 300,   -- Units for nearby player detection
    crossfire_distance = 200,         -- Units for crossfire detection
    grid_size = 512                   -- Units per heatmap cell
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No output files | Play complete round (warm up → play → end) |
| "Module not loading" | Verify c0rnp0rn.lua loads first |
| Parser fails | Check file format with: `head gamestats/*_combat.txt` |
| DB import fails | Run schema: `psql < bot/proximity_schema.sql` |

## Key Concepts

### Engagement Types
- `1v1` - Solo fight
- `2v1` - Two allies vs one enemy
- `1v2` - One player vs two enemies
- `2v2` - Team fight
- Higher numbers supported (3v1, 3v3, etc.)

### Proximity Events
- **Crossfire** - 2+ teammates damage same enemy
- **Baiting** - Ally retreats while teammate attacks same enemy
- **Clustering** - Team moves together (<100 units)
- **Spreading** - Team disperses

### Grid Coordinates
Each map is divided into cells (default 512×512 units):
- Grid (0,0) = bottom-left corner
- Positive X = toward right
- Positive Y = toward top
- Z coordinate stored separately (height)

## File Formats

**Positions:** `clientnum\ttime\tx\ty\tz\tyaw\tpitch\tspeed\tmoving`

**Combat:** `time\ttype\tattacker\ttarget\tdistance\tnearby_allies\tnearby_enemies\tdamage`

**Engagements:** `engagement_type\tdistance\tkiller\tvictim`

**Heatmap:** `grid_x\tgrid_y\taxis_kills\tallies_kills`

## Performance Notes

- **Server:** No measurable impact (<5% CPU, negligible memory)
- **Files:** ~150-200KB per 20-minute round
- **Database:** ~1000 position records per player per round

## Next Steps

1. **Test** - Run server, play a map, verify output files
2. **Import** - Load data into PostgreSQL
3. **Visualize** - Create heatmap Discord commands
4. **Analyze** - Build crossfire/baiting detection

## See Also

- [PROXIMITY_DEPLOYMENT_GUIDE.md](PROXIMITY_DEPLOYMENT_GUIDE.md) - Full deployment instructions
- [proximity_schema.sql](bot/proximity_schema.sql) - Database schema
- [proximity_parser.py](bot/proximity_parser.py) - Parser implementation
