# Proximity Context Note (Updated 2026-02-19)

This file previously documented older v2/v3 proximity variants and is now retained as a pointer only.

Use these as source-of-truth:

- `proximity/README.md`
- `proximity/docs/README.md`
- `proximity/docs/TRACKER_REFERENCE.md`
- `proximity/docs/OUTPUT_FORMAT.md`
- `proximity/docs/INTEGRATION_STATUS.md`
- `proximity/docs/FREEZE_RUNBOOK_2026-02-19.md`

Current active stack:

- Lua tracker: `proximity/lua/proximity_tracker.lua` (v4.2)
- Parser: `proximity/parser/parser.py` (`ProximityParserV4`)
- Reaction table migration: `proximity/schema/migrations/2026-02-19_reaction_metrics.sql`
- Website APIs: `/api/proximity/*` in `website/backend/routers/api.py`

If you are resuming work after a break, start with:

- `proximity/docs/FREEZE_RUNBOOK_2026-02-19.md`
