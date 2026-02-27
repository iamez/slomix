# Proximity Context Note (Updated 2026-02-24)

This file previously documented older v2/v3 proximity variants and is now retained as a pointer only.

Use these as source-of-truth:

- `proximity/README.md`
- `proximity/docs/README.md`
- `proximity/docs/TRACKER_REFERENCE.md`
- `proximity/docs/OUTPUT_FORMAT.md`
- `proximity/docs/INTEGRATION_STATUS.md`
- `proximity/docs/FREEZE_RUNBOOK_2026-02-19.md`

Current active stack:

- Lua tracker: `proximity/lua/proximity_tracker_v5.lua` (v5, 2265 lines)
- Parser: `proximity/parser/parser.py` (`ProximityParserV4` — handles both v4 and v5 output)
- Migration: `migrations/013_add_proximity_v5_teamplay.sql` (5 new tables)
- Website APIs: `/api/proximity/*` in `website/backend/routers/api.py`
- Bot commands: `bot/cogs/proximity_cog.py` (5 new v5 commands)

## v5 Teamplay Tables (added 2026-02-23)

| Table | Purpose | ~Volume |
|-------|---------|---------|
| `proximity_spawn_timing` | Per-kill spawn wave efficiency | ~kills/round |
| `proximity_team_cohesion` | Periodic team shape snapshots | ~720/round |
| `proximity_crossfire_opportunity` | LOS-verified crossfire angle events | varies |
| `proximity_team_push` | Coordinated team movement events | varies |
| `proximity_lua_trade_kill` | Server-side trade kill detection | ~trades/round |

## v5 Bot Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `!proximity_spawn_efficiency` | `!pse` | Top 10 by spawn timing score |
| `!proximity_cohesion` | `!pco` | Axis vs Allies dispersion summary |
| `!proximity_crossfire_angles` | `!pxa` | Crossfire utilization + top duos |
| `!proximity_trades_lua` | `!ptl` | Trade kill leaderboard |
| `!proximity_pushes` | `!ppu` | Team push quality comparison |

## v5 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /proximity/spawn-timing` | Spawn timing leaderboard + team averages |
| `GET /proximity/cohesion` | Dispersion summary + timeline + buddy pairs |
| `GET /proximity/crossfire-angles` | Utilization rate + angle buckets + top duos |
| `GET /proximity/pushes` | Per-team push summary + quality distribution |
| `GET /proximity/lua-trades` | Trader leaderboard + recent trades + speed tiers |

## Parser Backward Compatibility

- v4 files parse normally; v5 lists remain empty
- v5 files detected by `# PROXIMITY_TRACKER_V5` header
- New sections: `SPAWN_TIMING`, `TEAM_COHESION`, `CROSSFIRE_OPPORTUNITIES`, `TEAM_PUSHES`, `TRADE_KILLS`
- `FOCUS_FIRE` section intentionally skipped (website-only, later phase)

If you are resuming work after a break, start with:

- `proximity/docs/FREEZE_RUNBOOK_2026-02-19.md`
