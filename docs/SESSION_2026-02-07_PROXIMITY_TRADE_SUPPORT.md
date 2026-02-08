# Session Report — Proximity Trade + Support (2026-02-07)

## Scope
Implement proximity trade analytics (opportunity/attempt/success), add support uptime + isolation deaths, wire UI panels, and expose new API endpoints.

## Delivered

### Database
- Migration: `migrations/009_add_proximity_trade_events.sql`
  - New table: `proximity_trade_event`
- Migration: `migrations/010_add_proximity_support_summary.sql`
  - Adds columns to `proximity_trade_event`: `nearest_teammate_dist`, `is_isolation_death`
  - New table: `proximity_support_summary`
- Grants applied (for website read-only):
  - `GRANT SELECT ON TABLE proximity_trade_event TO website_readonly;`
  - `GRANT SELECT ON TABLE proximity_support_summary TO website_readonly;`

### Parser (proximity)
File: `proximity/parser/parser.py`
- Computes trade events from `combat_engagement` + `player_track`.
- Stores:
  - opportunities, attempts, successes, missed candidates
  - nearest teammate distance
  - isolation death flag
- Computes **support uptime** (% time within support radius of a teammate in combat).
- Imports support summary per round.
- Fix: avoid failing on re-import due to `proximity_objective_focus` unique conflicts.

Config parameters (env):
- `PROXIMITY_TRADE_WINDOW_MS` (default 3000)
- `PROXIMITY_TRADE_DIST` (default 800)
- `PROXIMITY_TRADE_POS_DELTA_MS` (default 1500)
- `PROXIMITY_ISOLATION_DIST` (default 1200)
- `PROXIMITY_SUPPORT_DIST` (default 600)
- `PROXIMITY_COMBAT_RECENT_MS` (default 1500)
- `PROXIMITY_SUPPORT_POS_DELTA_MS` (default 1500)

### API
File: `website/backend/routers/api.py`
- New endpoints:
  - `GET /api/proximity/trades/summary`
  - `GET /api/proximity/trades/events`
- Summary now returns:
  - `support_uptime_pct`
  - `isolation_deaths`

### UI
Files: `website/index.html`, `website/js/proximity.js`
- New panels:
  - Trade & Support Signals (summary)
  - Trade Events (latest list)
- New fields wired:
  - support uptime
  - isolation deaths
- Safe fallback for missing API fields
- Engagement inspector improvements:
  - Thicker path line + larger markers
  - Legend for start/path/hit/death/strafe/end
  - Strafe summary (turn count + timestamps)
  - Attacker path overlay (dashed) alongside target path
  - Killer name shown in engagement stats

### Data verification (live)
- `GET /api/proximity/trades/summary`
  - trade_opportunities, attempts, success, missed candidates
  - support_uptime_pct, isolation_deaths
  - trade events now include round metadata for deep linking

### Objective coords
- Added concrete objectives for `etl_supply` (crane controls, truck escape)
  to unlock objective focus tracking on that map.

## Known limitations
- Trade logic is v1 (no objective exceptions yet).
- Support uptime is derived from track sampling and can be heavy on large samples.
- Isolation death logic uses nearest teammate distance only.
- Strafe metrics are computed from target/attacker track slices (approximate; no LOS).

## Crash hardening (proximity lua)
- Added client index validation in `proximity/lua/proximity_tracker.lua`.
- Prevents `SV_GetUserinfo: bad index 1022` crashes when world damage is the killer
  (fall damage, trigger_hurt, crush, etc.).
- Guarded all killer lookups in `closeEngagement` and `getPlayerGUID` to avoid
  invalid entity access.
- Fixed Lua 5.4 startup error by making bit library loading optional (pcall require)
  and falling back to arithmetic flag checks if no bitlib is available.

## Next steps
- Add confidence tiers + objective exceptions (per spec).
- Add trade event detail drill‑down with opp/attempt/success lists.
- Extend support uptime with team/role breakdowns.
