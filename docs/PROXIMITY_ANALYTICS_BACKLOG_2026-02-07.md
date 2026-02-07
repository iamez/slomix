# Proximity Analytics Backlog (2026-02-07)

## Current status
- Proximity UI has new **Trade & Support Signals** panels wired to API.
- API now exposes:
  - `/api/proximity/trades/summary`
  - `/api/proximity/trades/events`
- Parser now computes **trade events** from engagements + player tracks and writes to DB.

## Must-do (to activate trade data)
1. Apply migration:
   - `migrations/009_add_proximity_trade_events.sql`
   - `migrations/010_add_proximity_support_summary.sql`
2. Ensure web DB role can read the table:
   - `GRANT SELECT ON TABLE proximity_trade_event TO website_readonly;`
   - `GRANT SELECT ON TABLE proximity_support_summary TO website_readonly;`
3. Re-run proximity import on recent files (or wait for next round).
4. Restart `etlegacy-web` to expose new endpoints.

## Validation steps
- `curl -s http://localhost:8000/api/proximity/trades/summary | python3 -m json.tool`
- `curl -s http://localhost:8000/api/proximity/trades/events?limit=10 | python3 -m json.tool`
- Verify new panel on Proximity tab populates.

## Next steps (v1 completeness)
- Add **support uptime** and **isolation death** metrics using player_track.
- Add **trade confidence tiers** + candidate tagging (no penalties yet).
- Add objective context hooks (from Lua or server logs) to suppress false positives.

## v2/v3 roadmap (from spec)
- Objective-role exceptions + rotation timing.
- Buddy graph / pairing analysis.
- Pack vs split clustering.
- Engagement geometry (viewangles/LOS heuristics).

## Related docs
- Spec: `docs/et_stopwatch_proximity_analytics_spec.md`
- Map overlay plan: `docs/PROXIMITY_MAP_OVERLAY_PLAN_2026-02-07.md`
