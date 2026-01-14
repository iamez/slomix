# Integration Status

How the proximity tracker connects to the broader SLOMIX ecosystem.

---

## Data Flow Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ET:Legacy Game Server                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              proximity_tracker.lua (in-game module)           │   │
│  │                                                               │   │
│  │  • Samples player positions every 500ms                       │   │
│  │  • Tracks combat engagements, crossfires, escapes            │   │
│  │  • Generates heatmaps                                         │   │
│  │  • Writes output file at round end                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│        proximity/{timestamp}-{map}-round-{N}_engagements.txt        │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        parser/parser.py                              │
│                                                                      │
│  • Watches for new files in proximity/ directory                    │
│  • Parses engagement, track, and heatmap data                       │
│  • Inserts into PostgreSQL database                                 │
│  • Calculates derived stats (crossfire pairs, teamplay stats)       │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        PostgreSQL Database                           │
│                                                                      │
│  Tables populated by proximity data:                                │
│  ├── combat_engagement      (per engagement record)                 │
│  ├── player_track           (per player per spawn)                  │
│  ├── player_teamplay_stats  (aggregated per player)                 │
│  ├── crossfire_pairs        (duo coordination stats)                │
│  ├── map_kill_heatmap       (spatial kill data)                     │
│  └── map_movement_heatmap   (spatial movement data)                 │
└─────────────────────────────────────────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│      Discord Bot          │      │      Web Dashboard        │
│                           │      │                           │
│  • Stats commands         │      │  • Player profiles        │
│  • Session tracking       │      │  • Engagement charts      │
│  • Voice monitoring       │      │  • Heatmap visualizations │
│  • Team detection         │      │  • Live status            │
└──────────────────────────┘      └──────────────────────────┘
```

---

## Database Tables

### Tables Populated by Proximity Data

| Table | Source | Description |
|-------|--------|-------------|
| `combat_engagement` | ENGAGEMENTS section | One row per combat engagement |
| `player_track` | PLAYER_TRACKS section | One row per player per spawn |
| `player_teamplay_stats` | Derived | Aggregated crossfire/combat stats per player |
| `crossfire_pairs` | Derived | Coordination stats for player pairs |
| `map_kill_heatmap` | KILL_HEATMAP section | Kill locations per map |
| `map_movement_heatmap` | MOVEMENT_HEATMAP section | Movement density per map |

### Schema Location

Database schema definitions are in:
- `proximity/schema/schema.sql` - Proximity-specific tables
- `bot/database/` - Bot database utilities

---

## Parser (parser.py)

Located at: `proximity/parser/parser.py`

### Functions

| Function | Purpose |
|----------|---------|
| `parse_proximity_file()` | Parse a single output file |
| `insert_engagement()` | Insert engagement record to DB |
| `insert_player_track()` | Insert player track to DB |
| `update_crossfire_pairs()` | Update crossfire pair aggregates |
| `process_new_files()` | Scan for and process new files |

### How It Runs

The parser can be run:
1. **Manually** - `python parser/parser.py`
2. **Via bot** - Background task scans every 5 minutes
3. **On demand** - Triggered by bot commands

---

## Integration with Discord Bot

### How Bot Uses Proximity Data

| Bot Feature | Proximity Data Used |
|-------------|---------------------|
| Crossfire stats | `crossfire_pairs` table |
| Engagement analysis | `combat_engagement` table |
| Player teamplay rating | `player_teamplay_stats` table |
| Map heatmaps | `map_kill_heatmap`, `map_movement_heatmap` |

### Bot Background Tasks

| Task | Interval | Purpose |
|------|----------|---------|
| File scanner | 5 minutes | Check for new proximity files |
| Stats aggregation | On new data | Update teamplay stats |

---

## Integration with Web Dashboard

### Current Integrations

| Feature | Status | Data Source |
|---------|--------|-------------|
| Engagement charts | Prototype | `combat_engagement` |
| Crossfire stats | Prototype | `crossfire_pairs` |
| Heatmap visualizations | Not started | `map_*_heatmap` tables |
| Player movement replay | Not started | `player_track` |

---

## What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| Lua tracker output | ✅ Working | Writes files per round |
| Parser reading files | ✅ Working | Parses all sections |
| Database inserts | ✅ Working | All tables populated |
| Crossfire pair calculation | ✅ Working | Aggregates updated |
| Bot file scanning | ✅ Working | 5-minute background task |

---

## Known Issues

### Upstream: Team Tracking (Bot/Database)

The proximity tracker correctly captures player data, but **upstream systems** have issues:

| Issue | Severity | Location | Impact |
|-------|----------|----------|--------|
| `session_results` never populated | CRITICAL | No INSERT code exists | Can't track team W/L |
| Team detector uses SQLite API | CRITICAL | `team_detector_integration.py` | Incompatible with PostgreSQL bot |
| `get_team_record()` unimplemented | HIGH | `team_manager.py:374` | Can't query team history |
| `get_map_performance()` unimplemented | HIGH | `team_manager.py:437` | No per-map team stats |

These issues affect the ability to:
- Track which "team" (not Axis/Allies) a player was on
- Calculate team win/loss records
- Build team chemistry metrics

See [GAPS_AND_ROADMAP.md](GAPS_AND_ROADMAP.md) for the full roadmap.

### Data Flow Gap

```
Proximity Tracker → Parser → Database ✅ WORKING
                                 ↓
                    Team Assignment ❌ BROKEN
                                 ↓
                    Team Chemistry Analysis ❌ BLOCKED
```

---

## Player Identity Linking

### Current Flow

```
Game Player (GUID) ←→ player_links table ←→ Discord User (discord_id)
```

| Table | Fields | Purpose |
|-------|--------|---------|
| `player_links` | `discord_id`, `et_guid`, `et_name` | Links Discord to game identity |
| `player_aliases` | `guid`, `alias`, `times_seen` | Tracks name changes |

### How Linking Works

1. Player authenticates via Discord OAuth on web dashboard
2. Dashboard links their Discord ID to their game GUID
3. Bot can now associate Discord user with game stats

---

## File Locations

| File | Purpose |
|------|---------|
| `proximity/lua/proximity_tracker.lua` | In-game Lua module |
| `proximity/parser/parser.py` | Output file parser |
| `proximity/schema/schema.sql` | Database table definitions |
| `bot/services/` | Bot services that use proximity data |
| `website/backend/` | Web API endpoints |
