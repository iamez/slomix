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
| [FREEZE_RUNBOOK_2026-02-19.md](FREEZE_RUNBOOK_2026-02-19.md) | Resume/debug checklist after context break |

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

- **Player Movement** - Position, velocity, stance, sprint, class, and spawn reaction (default sample interval: 200ms)
- **Combat Engagements** - Every damage event from first hit to death/escape/round end
- **Crossfire Detection** - When 2+ players damage the same target within the configured window
- **Escape Detection** - When players survive focus pressure after no-hit timeout + distance threshold
- **Objective Focus (optional)** - Nearest objective distance and time within radius
- **Reaction Metrics** - Return fire, dodge turn, and teammate support reaction timing
- **Heatmaps** - Kill and movement density per map

### Data Flow

```python
ET:Legacy Game Server
        |
        v
proximity/lua/proximity_tracker.lua
        |
        v (writes at round end)
proximity/{timestamp}-{map}-round-{N}_engagements.txt
        |
        v (parsed by proximity/parser/parser.py)
PostgreSQL Database
        |
        +---> Website proximity API + UI
        +---> Bot commands/tasks
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
- Objective focus export (map config dependent)
- Reaction telemetry export + import (`REACTION_METRICS`)
- Heatmap generation

**Not Yet Implemented:**

- Round/match outcomes (who won)
- "Team" identity (currently only tracks Axis/Allies per round)

See [GAPS_AND_ROADMAP.md](GAPS_AND_ROADMAP.md) for the full list.
