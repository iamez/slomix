# Proximity Tracker v2 - Kill-Centric Design

## Why v2?

v1 had critical design flaws that would cause database explosion:

| Issue | v1 Problem | v2 Solution |
|-------|-----------|-------------|
| Position tracking | 24,000 rows/round | **0** (only at kills) |
| Fire events | 400+ useless rows/round | **Removed entirely** |
| No GUID | Can't track players across sessions | **GUID on every record** |
| No map_name | Heatmaps unusable | **Map on every record** |
| No retention | Database grows forever | **Built-in archival function** |

## Data Volume Comparison

| Metric | v1 | v2 | Reduction |
|--------|-----|-----|-----------|
| Rows per round | ~24,500 | ~70 | **350x smaller** |
| Rows per day (10 rounds) | ~245,000 | ~700 | 350x |
| Rows per month | ~7,350,000 | ~21,000 | 350x |
| Rows per year | **88,000,000** | 250,000 | 350x |

## Files

```
proximity_tracker_v2.lua      # Game server Lua script
bot/proximity_schema_v2.sql   # PostgreSQL schema + retention
bot/proximity_parser_v2.py    # Python parser
```

## Quick Start

### 1. Deploy Lua Script
```bash
cp proximity_tracker_v2.lua /path/to/et_legacy/legacy/
```

### 2. Update server.cfg
```
seta lua_modules "c0rnp0rn.lua proximity_tracker_v2.lua"
```

### 3. Create Database Tables
```bash
psql -d et_stats -f bot/proximity_schema_v2.sql
```

### 4. Restart Server
```
map_restart
```

## Output Format

Single file per round: `YYYY-MM-DD-HHMMSS-mapname-round-N_proximity.txt`

```
# PROXIMITY_TRACKER_V2
# map=goldrush
# round=1
# FORMAT: game_time|killer_slot|killer_guid|killer_name|killer_team|...
12345|3|ABC123|SlomiX|AXIS|1234.5|5678.9|100.0|7|DEF456|Target|ALLIES|...|1v1|0|0|NONE
23456|5|GHI789|Teammate|AXIS|1230.0|5670.0|100.0|7|DEF456|Target|ALLIES|...|2v1|1|0|SlomiX

# HEATMAP
# grid_x|grid_y|axis_kills|allies_kills
2|11|5|3
3|11|2|1
```

## Database Tables

### kill_context
Core table - one row per kill with full spatial context.

| Column | Type | Purpose |
|--------|------|---------|
| killer_guid | VARCHAR(32) | Cross-session player tracking |
| map_name | VARCHAR(64) | Heatmap context |
| engagement_type | VARCHAR(10) | 1v1, 2v1, 1v2, etc. |
| supporting_allies | JSONB | Names of nearby allies |

### kill_heatmap
Grid-based kill density per map.

### player_proximity_stats
Per-player aggregated stats (solo kills, ganked deaths, etc.)

### teammate_synergy
Track which player pairs work well together.

## Retention Policy

```sql
-- Delete detailed data older than 30 days
SELECT archive_old_proximity_data(30);

-- Check data volume
SELECT * FROM proximity_data_stats();
```

**Kept forever:** player_proximity_stats, teammate_synergy (small, aggregated)
**Archived after 30 days:** kill_context, kill_heatmap (detailed data)

## Analytics Queries

### Engagement Breakdown
```sql
SELECT * FROM engagement_breakdown 
WHERE session_date = CURRENT_DATE;
```

### Player 1v1 Performance
```sql
SELECT player_name, solo_kills, solo_deaths,
       ROUND(100.0 * solo_kills / NULLIF(solo_kills + solo_deaths, 0), 1) as win_rate
FROM player_proximity_stats 
WHERE player_guid = 'ABC123';
```

### Hottest Kill Zones
```sql
SELECT grid_x, grid_y, total_kills 
FROM heatmap_by_map 
WHERE map_name = 'goldrush' 
ORDER BY total_kills DESC LIMIT 10;
```

### Best Duo Partners
```sql
SELECT player2_name, kills_within_range, simultaneous_kills
FROM teammate_synergy
WHERE player1_guid = 'ABC123'
ORDER BY kills_within_range DESC LIMIT 5;
```

## What's Tracked

✅ **Kill Context**
- Killer/victim positions at kill moment
- Kill distance
- Engagement type (1v1, 2v1, etc.)
- Supporting allies within 300 units
- Weapon and means of death

✅ **Heatmaps**
- Grid-based kill density per map
- Axis vs Allies breakdown

✅ **Player Stats (Aggregated)**
- Solo kills vs assisted kills
- Ganked deaths (outnumbered)
- Crossfire participation
- Kill distance stats

❌ **NOT Tracked (by design)**
- Position every second (waste)
- Fire events (useless noise)
- Hit events without kills (no value)
- Spectator data

## Integration with Existing Bot

```python
from bot.proximity_parser_v2 import ProximityParserV2

# In your stats import pipeline
parser = ProximityParserV2(db_adapter=self.db)
files = parser.find_proximity_files(session_date)
for f in files:
    await parser.import_file(f, session_date)
```

## Comparison: What We Lost vs Gained

### Lost (intentionally)
- Continuous position tracking
- Fire event logging
- Detailed hit-by-hit damage tracking
- Per-round position playback capability

### Gained
- **350x smaller database**
- Player tracking across sessions (GUID)
- Heatmaps that work (map_name)
- Built-in data retention
- Actually usable analytics
- Sustainable long-term storage
