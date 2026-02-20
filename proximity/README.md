# Proximity Tracker

ET:Legacy Lua telemetry module + Python parser + PostgreSQL analytics pipeline for scoped combat/movement/teamplay insights.

Source-of-truth module: `proximity/lua/proximity_tracker.lua` (v4.2).

## What It Captures

- `ENGAGEMENTS`: per-fight target pressure, attackers, crossfire, path, outcome.
- `PLAYER_TRACKS`: spawn-to-death/round-end path with speed, stance, sprint, first-move timing, class.
- `KILL_HEATMAP` and `MOVEMENT_HEATMAP`: spatial bins for map visualization.
- `OBJECTIVE_FOCUS`: optional nearest-objective proximity summaries.
- `REACTION_METRICS`: return-fire / dodge-turn / teammate-support reaction windows after first incoming hit.

## Core Metrics Exposed to UI

- Spawn reaction (`time_to_first_move_ms`) from `PLAYER_TRACKS`.
- Movement distance/sprint/survival leaders from `player_track`.
- Crossfire/sync/focus teamplay from scoped combat data.
- Trade rates + support uptime from derived parser tables.
- Class composition and class reaction baselines.
- Combat reaction leaders (`return_fire_ms`, `dodge_reaction_ms`, `support_reaction_ms`).

## Architecture

```text
ET:Legacy server
  -> proximity/lua/proximity_tracker.lua
  -> *_engagements.txt files
  -> proximity/parser/parser.py (ProximityParserV4)
  -> PostgreSQL proximity tables
  -> website/backend/routers/api.py (/api/proximity/*)
  -> website/js/proximity.js + website/index.html
```

## Quick Start (Fresh Setup / Resume)

```bash
# 1) DB schema + migrations
psql -d etlegacy -f proximity/schema/schema.sql
psql -d etlegacy -f proximity/schema/migrations/2026-02-04_round_start_unix.sql
psql -d etlegacy -f proximity/schema/migrations/2026-02-12_ws1c_constraint_cleanup.sql
psql -d etlegacy -f proximity/schema/migrations/2026-02-19_reaction_metrics.sql

# 2) Deploy tracker to game server lua path
cp proximity/lua/proximity_tracker.lua /path/to/etlegacy/legacy/luascripts/proximity_tracker.lua

# 3) Ensure server config includes proximity module
# lua_modules "luascripts/team-lock c0rnp0rn7.lua endstats.lua proximity_tracker.lua"
```

Import one local file (example command used in this repo):

```bash
python3 - <<'PY'
import asyncio
from proximity.parser.parser import ProximityParserV4
from bot.core.database_adapter import PostgreSQLAdapter

FILE_PATH = "local_proximity/2026-02-18-235002-etl_frostbite-round-1_engagements.txt"
SESSION_DATE = "2026-02-18"

async def main():
    db = PostgreSQLAdapter(
        host="localhost",
        port=5432,
        database="etlegacy",
        user="etlegacy_user",
        password="etlegacy_secure_2025",
        min_pool_size=1,
        max_pool_size=2,
    )
    await db.connect()
    try:
        parser = ProximityParserV4(db_adapter=db, output_dir="local_proximity", gametimes_dir="local_gametimes")
        ok = await parser.import_file(FILE_PATH, SESSION_DATE)
        print("IMPORT_OK", ok)
    finally:
        await db.close()

asyncio.run(main())
PY
```

## Schema Surface

Main tables populated/used:

- `combat_engagement`
- `player_track`
- `player_teamplay_stats`
- `crossfire_pairs`
- `map_kill_heatmap`
- `map_movement_heatmap`
- `proximity_objective_focus`
- `proximity_trade_event`
- `proximity_support_summary`
- `proximity_reaction_metric`

## Website API Surface

Proximity endpoints:

- `/api/proximity/scopes`
- `/api/proximity/summary`
- `/api/proximity/engagements`
- `/api/proximity/hotzones`
- `/api/proximity/duos`
- `/api/proximity/movers`
- `/api/proximity/classes`
- `/api/proximity/reactions`
- `/api/proximity/teamplay`
- `/api/proximity/trades/summary`
- `/api/proximity/trades/events`
- `/api/proximity/events`
- `/api/proximity/event/{event_id}`

## Key Debug Checks

```bash
# New section exists in fresh files:
rg -n "^# REACTION_METRICS" local_proximity/*_engagements.txt

# Parser imported reaction rows:
psql -d etlegacy -Atc "SELECT COUNT(*) FROM proximity_reaction_metric;"

# UI data path live:
curl -s "http://localhost:8000/api/proximity/reactions?range_days=30&limit=5"
```

## Documentation

- `proximity/docs/README.md`
- `proximity/docs/TRACKER_REFERENCE.md`
- `proximity/docs/OUTPUT_FORMAT.md`
- `proximity/docs/INTEGRATION_STATUS.md`
- `proximity/docs/GAPS_AND_ROADMAP.md`
- `proximity/docs/FREEZE_RUNBOOK_2026-02-19.md`
