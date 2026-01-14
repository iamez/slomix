# Proximity Tracker Documentation

The Proximity Tracker is a Lua module for ET:Legacy that captures detailed player movement, combat engagements, and team coordination data. This data feeds into the SLOMIX team chemistry analytics platform.

**Vision:** See [SLOMIX_PROJECT_BRIEF.md](../SLOMIX_PROJECT_BRIEF.md) for the full project vision.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [TRACKER_REFERENCE.md](TRACKER_REFERENCE.md) | Comprehensive list of everything the Lua tracker captures |
| [OUTPUT_FORMAT.md](OUTPUT_FORMAT.md) | File format specification and parsing guide |
| [INTEGRATION_STATUS.md](INTEGRATION_STATUS.md) | How proximity connects to the bot, database, and website |
| [GAPS_AND_ROADMAP.md](GAPS_AND_ROADMAP.md) | Known limitations and planned improvements |

### Historical Design Docs

| Document | Description |
|----------|-------------|
| [DESIGN_v4.md](DESIGN_v4.md) | Original v4 design document |
| [IMPLEMENTATION_v4.md](IMPLEMENTATION_v4.md) | v4 implementation details |
| [GAP_ANALYSIS.md](GAP_ANALYSIS.md) | Earlier gap analysis (superseded by GAPS_AND_ROADMAP.md) |

---

## Quick Overview

### What It Does

The proximity tracker runs as a Lua module inside the ET:Legacy game server. It captures:

- **Player Movement** - Position, velocity, stance, sprint state sampled every 500ms
- **Combat Engagements** - Every damage event from first hit to death/escape
- **Crossfire Detection** - When 2+ players damage the same target within 1 second
- **Escape Detection** - When players survive combat (5s no damage + 300 units moved)
- **Heatmaps** - Kill locations and movement density per map

### Data Flow

```
ET:Legacy Game Server
        |
        v
proximity_tracker.lua (samples every 500ms)
        |
        v (writes at round end)
proximity/{timestamp}-{map}-round-{N}_engagements.txt
        |
        v (parsed by parser.py)
PostgreSQL Database
        |
        +---> Discord Bot (stats commands)
        +---> Web Dashboard (visualizations)
```

### Key Files

| File | Purpose |
|------|---------|
| `lua/proximity_tracker.lua` | The Lua module that runs in-game |
| `parser/parser.py` | Parses output files into database |
| `schema/schema.sql` | Database table definitions |

---

## Session Notes

Historical development session notes are in [session-notes/](session-notes/).

---

## Current Status

**Working:**
- Full player movement tracking
- Combat engagement detection with attacker details
- Crossfire detection (2+ attackers)
- Heatmap generation

**Not Yet Implemented:**
- Round/match outcomes (who won)
- Objective tracking (dynamite, constructions)
- "Team" identity (currently only tracks Axis/Allies per round)

See [GAPS_AND_ROADMAP.md](GAPS_AND_ROADMAP.md) for the full list.
