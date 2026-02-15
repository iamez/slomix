# Proximity Tracker

ET:Legacy Lua module + Python parser for tracking player movement, combat engagements, and team coordination analytics.

**Part of the [Slomix](../README.md) Team Chemistry Analytics Platform.**

---

## What It Does

The Proximity system captures **per-round player behavior data** from the ET:Legacy game server and transforms it into actionable analytics:

- **Combat Engagements** - Who fought whom, crossfire detection, engagement duration, attacker damage breakdown
- **Trade Opportunities** - Could a teammate have traded back? Isolation deaths vs supported deaths
- **Team Support Uptime** - Percentage of round time with a teammate in support range
- **Movement Profiles** - Distance traveled, sprint percentage, average speed, full position paths
- **Spawn Reaction Time** - Milliseconds from spawn to first movement (`time_to_first_move_ms`)
- **Kill Heatmaps** - Spatial density of kills/deaths per map for hotzone visualization

---

## Architecture

```
ET:Legacy Server                     PostgreSQL
    │                                    ▲
    ▼                                    │
proximity_tracker.lua  ──►  .txt files  ──►  parser.py  ──►  5 DB tables
    (v4, runs in-game)       (per-round)      (Python)        (queryable)
                                                                  │
                                                                  ▼
                                                          Website API + UI
                                                        (proximity.js views)
```

### Data Flow

1. **Lua tracker** runs on game server, hooks spawn/death/damage/position events
2. Outputs engagement + player track data to `{MAP}-round-{N}_engagements.txt` files
3. **Python parser** reads files, validates data, computes derived metrics
4. Stores into **5 PostgreSQL tables** with full round context
5. **Website API** (`/api/proximity/*`) queries tables for visualization

---

## Quick Start

```bash
# 1. Deploy Lua module to game server
cp proximity/lua/proximity_tracker.lua /path/to/etlegacy/lua_modules/

# 2. Add to server config (alongside existing modules)
# lua_modules "c0rnp0rn.lua proximity_tracker.lua"

# 3. Create database tables
psql -d etlegacy -f proximity/schema/schema.sql

# 4. Apply migrations (if upgrading)
psql -d etlegacy -f proximity/schema/migrations/2026-02-04_round_start_unix.sql
psql -d etlegacy -f proximity/schema/migrations/2026-02-12_ws1c_constraint_cleanup.sql

# 5. Import proximity data files
python -m proximity.parser.parser /path/to/proximity/output/files/
```

---

## Database Tables

| Table | Purpose | ~Rows/Year |
|-------|---------|------------|
| `combat_engagement` | Individual fight records (attacker, target, crossfire, duration) | ~100K |
| `player_track` | Per-round movement profile (path, speed, sprint, reaction time) | ~73K |
| `player_teamplay_stats` | Aggregated crossfire/coordination stats per player | ~200 |
| `proximity_trade_event` | Trade opportunity analysis (could teammate have helped?) | ~50K |
| `proximity_support_summary` | Team support uptime percentage per round | ~73K |

Additional tables for heatmap visualization:
- `map_kill_heatmap` - Spatial kill density bins per map (~1K rows)

---

## Metrics Explained

### Spawn Reaction Time ("Fastest Reaction")

Displayed as "Fastest Reaction" in the website UI. Measures **time from character spawn until first movement**:

```
time_to_first_move_ms = first_move_time - spawn_time
```

- Lower = faster/better
- Averaged across all rounds for leaderboard ranking
- **Not** reaction to damage or enemy contact - purely spawn responsiveness

### Crossfire Detection

Two or more attackers engaging the same target within a 1-second window:

- `is_crossfire: true` on engagement record
- `crossfire_delay_ms` - gap between first and second attacker

### Trade Analysis

When a player dies, the system checks if teammates were in range to retaliate:

- `opportunity_count` - teammates who could have traded
- `success_count` - teammates who actually killed the attacker
- `is_isolation_death` - player had no nearby teammates

### Support Uptime

Percentage of round time a player had at least one teammate within support distance:

- `support_uptime_pct` - 0-100%
- High uptime = playing with team; low = lone-wolfing

---

## Project Structure

```
proximity/
├── lua/
│   └── proximity_tracker.lua       # Game server module (v4, production)
├── parser/
│   └── parser.py                   # Parse output files → PostgreSQL (711 lines)
├── schema/
│   ├── schema.sql                  # PostgreSQL table definitions (5 tables)
│   └── migrations/                 # Schema evolution scripts
│       ├── 2026-02-04_round_start_unix.sql
│       └── 2026-02-12_ws1c_constraint_cleanup.sql
├── docs/                           # Detailed documentation
│   ├── README.md                   # Documentation index
│   ├── TRACKER_REFERENCE.md        # What the tracker captures
│   ├── OUTPUT_FORMAT.md            # File format specification
│   ├── INTEGRATION_STATUS.md       # System integration status
│   ├── GAPS_AND_ROADMAP.md         # Known gaps and roadmap
│   ├── IMPLEMENTATION_v4.md        # v4 implementation details
│   └── DESIGN_v4.md                # v4 design patterns
├── SLOMIX_PROJECT_BRIEF.md         # Project vision document
└── README.md                       # This file
```

---

## Website Integration

The proximity data is visualized in the website's **Proximity Intelligence** view (`/proximity`):

| Card | Data Source | Description |
|------|-------------|-------------|
| Engagement Timeline | `combat_engagement` | Fights over time, scoped by session/map/round |
| Hotzone Heatmap | `map_kill_heatmap` | Spatial kill density per map |
| Distance Leaders | `player_track` | Most distance traveled |
| Sprint Leaders | `player_track` | Highest sprint percentage |
| Fastest Reaction | `player_track` | Lowest avg `time_to_first_move_ms` |
| Survival Leaders | `player_track` | Longest avg alive duration |
| Crossfire Leaders | `player_teamplay_stats` | Most coordinated kills |
| Trade Analysis | `proximity_trade_event` | Trade success rates |
| Support Uptime | `proximity_support_summary` | Team proximity percentage |

API endpoints: `GET /api/proximity/{summary,engagements,hotzones,movers,teamplay,duos}`

---

## Documentation

Full documentation is in the [docs/](docs/) folder:

- [TRACKER_REFERENCE.md](docs/TRACKER_REFERENCE.md) - What the tracker captures
- [OUTPUT_FORMAT.md](docs/OUTPUT_FORMAT.md) - File format specification
- [INTEGRATION_STATUS.md](docs/INTEGRATION_STATUS.md) - System integration status
- [GAPS_AND_ROADMAP.md](docs/GAPS_AND_ROADMAP.md) - Known gaps and roadmap

See also: [SLOMIX_PROJECT_BRIEF.md](SLOMIX_PROJECT_BRIEF.md) for the full project vision.
