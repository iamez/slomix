# Proximity Tracker

ET:Legacy Lua module for tracking player movement, combat engagements, and team coordination.

**Part of the SLOMIX Team Chemistry Analytics Platform.**

---

## Documentation

Full documentation is in the [docs/](docs/) folder:

- [docs/README.md](docs/README.md) - Documentation index
- [docs/TRACKER_REFERENCE.md](docs/TRACKER_REFERENCE.md) - What the tracker captures
- [docs/OUTPUT_FORMAT.md](docs/OUTPUT_FORMAT.md) - File format specification
- [docs/INTEGRATION_STATUS.md](docs/INTEGRATION_STATUS.md) - System integration
- [docs/GAPS_AND_ROADMAP.md](docs/GAPS_AND_ROADMAP.md) - Known gaps and roadmap

---

## Project Vision

See [SLOMIX_PROJECT_BRIEF.md](SLOMIX_PROJECT_BRIEF.md) for the full vision.

---

## Quick Start

```bash
# 1. Copy Lua module to game server
cp lua/proximity_tracker.lua /path/to/etlegacy/lua_modules/

# 2. Add to server config
# lua_modules "c0rnp0rn.lua proximity_tracker.lua"

# 3. Run database schema
psql -d your_db -f schema/schema.sql
```

---

## Project Structure

```
proximity/
├── lua/
│   └── proximity_tracker.lua    # Game server module (v4)
├── parser/
│   └── parser.py                # Parse output files → database
├── schema/
│   └── schema.sql               # PostgreSQL table definitions
├── docs/                        # Full documentation
│   ├── README.md
│   ├── TRACKER_REFERENCE.md
│   ├── OUTPUT_FORMAT.md
│   ├── INTEGRATION_STATUS.md
│   ├── GAPS_AND_ROADMAP.md
│   └── session-notes/
├── SLOMIX_PROJECT_BRIEF.md      # Project vision
└── README.md                    # This file
```
