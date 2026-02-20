# Proximity Integration Status (2026-02-19)

Operational snapshot of how proximity is wired across Lua, parser, database, and website.

## Source Of Truth

- Tracker: `proximity/lua/proximity_tracker.lua` (v4.2)
- Parser: `proximity/parser/parser.py` (`ProximityParserV4`)
- Schema: `proximity/schema/schema.sql`
- Migrations: `proximity/schema/migrations/*.sql`
- Web API: `website/backend/routers/api.py`
- Web UI: `website/js/proximity.js` + `website/index.html`

## Data Flow

```text
ET:Legacy server
  -> proximity_tracker.lua
  -> proximity/*.txt output per round
  -> ProximityParserV4 import
  -> PostgreSQL proximity tables
  -> /api/proximity/* endpoints
  -> Proximity page visualizations
```

## Output Sections Parsed

- `ENGAGEMENTS`
- `PLAYER_TRACKS`
- `KILL_HEATMAP`
- `MOVEMENT_HEATMAP`
- `OBJECTIVE_FOCUS` (optional)
- `REACTION_METRICS` (optional, new in v4.2)

## Database Tables Used

Direct import + derived tables:

- `combat_engagement`
- `player_track`
- `map_kill_heatmap`
- `map_movement_heatmap`
- `proximity_objective_focus`
- `proximity_reaction_metric`
- `proximity_trade_event`
- `proximity_support_summary`
- `player_teamplay_stats` (derived upsert)
- `crossfire_pairs` (derived upsert)

## Website API Surface

Proximity endpoints currently implemented:

- `/proximity/scopes`
- `/proximity/summary`
- `/proximity/engagements`
- `/proximity/hotzones`
- `/proximity/duos`
- `/proximity/movers`
- `/proximity/classes`
- `/proximity/reactions`
- `/proximity/teamplay`
- `/proximity/trades/summary`
- `/proximity/trades/events`
- `/proximity/events`
- `/proximity/event/{event_id}`

## UI Surface

Current UI includes:

- scoped session/map/round filters
- glossary + formula/capture notes
- confidence tags by sample size
- movement/teamplay/trade/support cards
- class composition panel
- reaction leaders panel (return fire / dodge / support)
- class reaction baseline panel

## Migration Status Notes

Relevant migrations:

- `2026-02-04_round_start_unix.sql`
- `2026-02-12_ws1c_constraint_cleanup.sql`
- `2026-02-19_reaction_metrics.sql`

2026-02-19 run notes:

- Local DB migration applied successfully.
- ETL DB already had `proximity_reaction_metric`; index creation was owner-limited in one run, but required indexes are present.

## Known Operational Gotchas

- If parser user lacks rights on new table, imports fail with `permission denied for table proximity_reaction_metric`.
- If files were produced before v4.2 deploy, they will not contain `# REACTION_METRICS`; reaction row import will remain zero.
- `.env` files in this repo may have CRLF line endings; sourcing them directly in bash can produce `$'\\r'` errors.

## Validation Commands

```bash
# Verify new section exists in latest files:
rg -n "^# REACTION_METRICS" local_proximity/*_engagements.txt

# Verify table/indexes:
psql -d etlegacy -Atc "SELECT COUNT(*) FROM proximity_reaction_metric;"
psql -d etlegacy -Atc "SELECT indexname FROM pg_indexes WHERE tablename='proximity_reaction_metric' ORDER BY indexname;"

# Verify API:
curl -s "http://localhost:8000/api/proximity/reactions?range_days=30&limit=6"
curl -s "http://localhost:8000/api/proximity/classes?range_days=30"
```

## Resume Pointer

If coming back after a break, use:

- `proximity/docs/FREEZE_RUNBOOK_2026-02-19.md`
