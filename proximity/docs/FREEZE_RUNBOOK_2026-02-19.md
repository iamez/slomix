# Proximity Freeze Runbook (2026-02-19)

Purpose: park the project safely and make restart/debug deterministic after a context break.

## Snapshot

Date: 2026-02-19

State delivered:

- v4.2 reaction telemetry wired end-to-end (Lua -> parser -> DB -> API -> UI).
- Class tracking visible in proximity UI and API.
- Metric glossary + formula/capture-source notes live in UI.
- Sample-size confidence tags live in leaderboards.

## Files Changed In This Phase

Core pipeline:

- `proximity/lua/proximity_tracker.lua`
- `proximity/parser/parser.py`
- `proximity/schema/schema.sql`
- `proximity/schema/migrations/2026-02-19_reaction_metrics.sql`
- `proximity/docs/OUTPUT_FORMAT.md`

Web/API:

- `website/backend/routers/api.py`
- `website/js/proximity.js`
- `website/index.html`

Docs + tests:

- `docs/PROXIMITY_ETL_LUA_CAPABILITIES_2026-02-19.md`
- `docs/PROXIMITY_IMPROVEMENT_DIRECTION_2026-02-19.md`
- `docs/PROXIMITY_WEB_BENCHMARK_IDEAS_2026-02-19.md`
- `tests/unit/test_proximity_reaction_metrics_parser.py`
- `.gitignore` (allow `proximity/schema/migrations/*.sql`)

## DB Migration + Import Notes

Migration file:

- `proximity/schema/migrations/2026-02-19_reaction_metrics.sql`

Observed status on 2026-02-19:

- Local DB: migration applied (`CREATE TABLE` + indexes).
- ETL DB: table already existed; indexes confirmed present.
- Parser imports succeeded on latest local file in both DB targets.
- Reaction rows remain `0` until new v4.2-generated files appear with `# REACTION_METRICS`.

## Resume Checklist

1. Deploy latest Lua tracker to game server.
2. Confirm server config loads `proximity_tracker.lua`.
3. Wait for one fresh round file.
4. Confirm new file contains `# REACTION_METRICS`.
5. Import file with parser.
6. Verify `proximity_reaction_metric` row count > 0.
7. Verify API responses for `/api/proximity/reactions` and `/api/proximity/classes`.

## Commands (Copy/Paste)

### 1) Verify file has reaction section

```bash
rg -n "^# REACTION_METRICS" local_proximity/*_engagements.txt
```

### 2) Apply reaction migration

```bash
psql -d etlegacy -f proximity/schema/migrations/2026-02-19_reaction_metrics.sql
```

### 3) Import one file

```bash
python3 - <<'PY'
import asyncio
from proximity.parser.parser import ProximityParserV4
from bot.core.database_adapter import PostgreSQLAdapter

FILE_PATH = "local_proximity/REPLACE_FILE.txt"
SESSION_DATE = "2026-02-19"

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
        print("PARSED_REACTION_ROWS", parser.get_stats().get("reaction_metrics"))
    finally:
        await db.close()

asyncio.run(main())
PY
```

### 4) Verify DB counts

```bash
psql -d etlegacy -Atc "SELECT 'combat', COUNT(*)::text FROM combat_engagement
UNION ALL SELECT 'track', COUNT(*)::text FROM player_track
UNION ALL SELECT 'reaction', COUNT(*)::text FROM proximity_reaction_metric
ORDER BY 1;"
```

### 5) Verify indexes

```bash
psql -d etlegacy -Atc "SELECT indexname FROM pg_indexes WHERE tablename='proximity_reaction_metric' ORDER BY indexname;"
```

### 6) Verify API payloads

```bash
curl -s "http://localhost:8000/api/proximity/reactions?range_days=30&limit=6"
curl -s "http://localhost:8000/api/proximity/classes?range_days=30"
```

## Failure Triage

### Symptom: `permission denied for table proximity_reaction_metric`

Check:

- run import as DB role with rights (`etlegacy_user` in this repo flow).

Fix (as table owner/admin):

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE proximity_reaction_metric TO etlegacy_user;
GRANT USAGE, SELECT ON SEQUENCE proximity_reaction_metric_id_seq TO etlegacy_user;
```

### Symptom: migration fails with `must be owner of table proximity_reaction_metric`

Meaning:

- table exists under another owner; re-creation is blocked.

Check:

```sql
SELECT tableowner FROM pg_tables WHERE tablename='proximity_reaction_metric';
SELECT indexname FROM pg_indexes WHERE tablename='proximity_reaction_metric';
```

Action:

- if required indexes exist, proceed.
- if missing, run index DDL as table owner/admin.

### Symptom: import succeeds but reaction rows stay zero

Check:

- input file lacks `# REACTION_METRICS` section.

Action:

- deploy updated Lua tracker and ingest fresh files only.

### Symptom: `/api/proximity/reactions` returns prototype message

Check:

- table missing or no data in selected scope.

Action:

- run migration, confirm scope filters, and verify table count directly.

## Operational Notes

- Source of truth Lua file is `proximity/lua/proximity_tracker.lua`.
- Old docs referencing `proximity_tracker_v3.lua` are deprecated.
- `.env` files may contain CRLF; avoid `source .env` unless normalized.
