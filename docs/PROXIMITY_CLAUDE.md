# Proximity Tracker - CLAUDE.md

> **Status**: Early Prototype | **Version**: 3.0 (Engagement-Centric)
> **Last Updated**: 2026-01-26
> **Move to**: `proximity/CLAUDE.md` after permissions restart

## Overview

The **Proximity Tracker** is an advanced analytics system for tracking player combat engagements, teamplay synergy, and spatial patterns in ET:Legacy. It captures real-time data from the game server to provide insights into:

- **Crossfire Detection** - Who synergizes well together (2+ attackers within 1 second)
- **Engagement Analysis** - 1v1, 2v1, 2v2 fight breakdowns with full context
- **Escape Tracking** - Players who survive focus fire (5s no damage + 300 units moved)
- **Heatmaps** - Kill/death density and movement patterns per map
- **Teamplay Metrics** - Solo vs assisted kills, support roles, baiting detection

---

## Architecture

```
Game Server (ET:Legacy)
    ↓ Lua script captures combat events
proximity_tracker_v3.lua (RECOMMENDED)
    ↓ Outputs to gamestats/
*_engagements.txt files
    ↓ Bot scans every 5 minutes
proximity_parser_v3.py
    ↓ Parses and imports
PostgreSQL (proximity tables)
    ↓ Queried by
proximity_cog.py → Discord commands
website API → Web visualizations (planned)
```

---

## Version Comparison

| Version | Focus | Data Volume | Recommended |
|---------|-------|-------------|-------------|
| v1 | Full tracking (positions, combat, engagements) | ~24,500 rows/round | No - too large |
| v2 | Kill-centric (one row per kill) | ~70 rows/round | Backup option |
| **v3** | **Engagement-centric (combat interactions)** | **~100 rows/round** | **YES** |

**Use v3** - It's forever-storable (~600K rows/year) while capturing the richest analytics data.

---

## Key Files

### Lua Scripts (Game Server - root directory)
| File | Lines | Purpose |
|------|-------|---------|
| `proximity_tracker.lua` | 709 | v1 - Full reference implementation |
| `proximity_tracker_v2.lua` | 361 | v2 - Kill-centric, 350x smaller |
| `proximity_tracker_v3.lua` | 640 | **v3 - Engagement-centric (RECOMMENDED)** |

### Python Parsers (bot/)
| File | Lines | Purpose |
|------|-------|---------|
| `bot/proximity_parser.py` | 474 | v1 parser |
| `bot/proximity_parser_v2.py` | 432 | v2 parser |
| `bot/proximity_parser_v3.py` | 711 | **v3 parser (RECOMMENDED)** |

### Database Schemas (bot/)
| File | Lines | Tables |
|------|-------|--------|
| `bot/proximity_schema.sql` | 259 | 7 tables (v1) |
| `bot/proximity_schema_v2.sql` | 300 | 4 tables (v2) |
| `bot/proximity_schema_v3.sql` | 362 | **5 tables (v3)** |

### Discord Integration
| File | Lines | Purpose |
|------|-------|---------|
| `bot/cogs/proximity_cog.py` | 298 | Background scanner + admin commands |

---

## Database Schema (v3)

### Tables

**`combat_engagement`** - Core table, one row per engagement
```sql
id, round_id, engagement_id
start_time, end_time, duration
target_guid, target_name, target_team
outcome (killed/escaped/round_end)
total_damage, killer_guid, killer_name, num_attackers
is_crossfire, crossfire_delay, crossfire_participants
start_x/y/z, end_x/y/z, distance_traveled
position_path (JSON), attackers (JSON)
```

**`player_teamplay_stats`** - Aggregated lifetime stats
```sql
player_guid, player_name
-- Offensive
crossfire_participations, crossfire_kills, crossfire_damage
crossfire_final_blows, avg_crossfire_delay_ms, solo_kills
-- Defensive
times_targeted, times_focused, focus_escapes, focus_deaths
solo_escapes, solo_deaths, avg_escape_distance
-- General
avg_engagement_duration_ms, total_damage_taken
```

**`crossfire_pairs`** - Duo coordination metrics
```sql
player1_guid, player2_guid
crossfire_count, crossfire_kills, total_damage
avg_delay_ms, last_seen
```

**`map_kill_heatmap`** / **`map_movement_heatmap`** - Spatial data per map

---

## Configuration

```bash
# In .env
PROXIMITY_ENABLED=false              # Master enable/disable
PROXIMITY_AUTO_IMPORT=true           # Auto-import vs manual only
PROXIMITY_DEBUG_LOG=false            # Verbose logging
PROXIMITY_DISCORD_COMMANDS=false     # Enable Discord admin commands
```

**Currently disabled by default** - Enable carefully as it requires Lua script running on game server.

---

## Game Server Deployment (Lua)

### Step 1: Upload Lua Script
```bash
# Copy to game server's Lua modules directory
scp proximity_tracker_v3.lua user@gameserver:/path/to/etlegacy/lua/
```

### Step 2: Enable in Server Config
```
// In etl_server.cfg or equivalent
set lua_modules "qagame c0rnp0rn.lua proximity_tracker_v3.lua"
```

### Step 3: Configure Output Directory
In `proximity_tracker_v3.lua`, verify:
```lua
local config = {
    output_dir = "gamestats/",  -- Where files are written
    position_sample_interval = 2,  -- Seconds between position samples
    escape_time_threshold = 5,  -- Seconds without damage = escape
    escape_distance_threshold = 300,  -- Units moved to confirm escape
    crossfire_window = 1.0,  -- Seconds to detect coordinated attack
}
```

### Step 4: Verify Output
After a round ends, check for:
```
gamestats/2026-01-26-143022-goldrush-round-1_engagements.txt
```

### Step 5: Enable Bot Import
```bash
# In .env
PROXIMITY_ENABLED=true
PROXIMITY_AUTO_IMPORT=true
```

---

## Data Flow Example

```
Round: goldrush, 2026-01-26

1. Player A damages Player B (150 units away)
2. Player C damages Player B (0.8 seconds later) → CROSSFIRE DETECTED
3. Player A kills Player B

Lua captures:
- Engagement ID: 1
- Duration: 2300ms
- Target: Player B
- Attackers: [Player A (got_kill=true), Player C]
- is_crossfire: true
- crossfire_delay: 800ms
- outcome: killed

Parser imports to combat_engagement table

Stats updated:
- Player A: +1 crossfire_kill, +1 crossfire_participation
- Player C: +1 crossfire_participation
- Player B: +1 times_targeted, +1 focus_death
- Pair (A,C): +1 crossfire_count
```

---

## Current Discord Commands

```
!proximity_status  - Show tracker status, file counts, DB stats
!proximity_scan    - Force manual scan for new files
!proximity_import <filename>  - Manually import specific file
```

---

## Vision: Future Features

### Phase 1: Core Tracking ✅ COMPLETE
- Engagement tracking with full spatial/temporal data
- Crossfire, escape, 1v1 detection
- Forever-storable data volume

### Phase 2: Discord Commands (Planned)
```
!my_crossfire_partners     - Who do I synergize with?
!best_duo                  - Top player pairs by kills
!teamplay_leaderboard      - Crossfire participation rankings
!engagement_stats <player> - Detailed engagement breakdown
!escape_artists            - Best escape ratios
```

### Phase 3: Website Visualizations (Planned)
- Interactive kill heatmaps per map
- Movement pattern overlays
- Engagement timeline replay
- Player synergy graphs

### Phase 4: Team Recommendations (Planned)
- Suggest balanced teams based on synergy data
- Predict which combinations will work well
- "Teamplay score" in player profiles

---

## Integration Options (Undecided)

**Option A: Merge into Main Bot**
- Proximity becomes another cog
- Shares same database tables
- Unified player stats view

**Option B: Keep Separate**
- Proximity stays isolated module
- Only shares DB connection
- Separate analytics dashboard

*Decision pending based on production usage patterns.*

---

## Quick Reference

| What | Where |
|------|-------|
| Enable tracking | `.env` → `PROXIMITY_ENABLED=true` |
| Lua script (recommended) | `proximity_tracker_v3.lua` |
| Parser (recommended) | `bot/proximity_parser_v3.py` |
| Schema (recommended) | `bot/proximity_schema_v3.sql` |
| Discord cog | `bot/cogs/proximity_cog.py` |
| Output files | `gamestats/*_engagements.txt` |

---

**Status**: Early Prototype - Core tracking complete, user-facing features planned
