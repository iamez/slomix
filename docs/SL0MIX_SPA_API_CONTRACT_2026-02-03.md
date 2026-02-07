# Slomix SPA API Contract & Feature Map (2026-02-03)

**Context**
This document captures a lightweight API contract and feature map for the Slomix web SPA. The website and proximity system are prototypes, so endpoints marked as prototype or planned are optional and expected to evolve.

**Goals**
- Keep the SPA read-only and safe by default.
- Make the API stable enough for front-end iteration.
- Support proximity analytics without blocking core stats flows.

**Architecture Snapshot**
- ET:Legacy server emits stats files and Lua webhook timing data.
- Bot parses stats, stores in PostgreSQL, posts to Discord.
- Website API provides read-only stats and aggregates.
- SPA consumes API and renders views with lightweight client routing.
- Proximity pipeline is a separate prototype that will feed additional analytics.

**API Conventions**
- Base path: `/api`
- Response format: JSON objects, consistent keys, predictable pagination.
- Time: ISO 8601 UTC strings for timestamps, seconds for durations.
- Pagination: `limit`, `offset`, `next_offset` fields.
- Errors: `{ "error": "message", "code": "ERROR_CODE" }`

**Common Response Envelope (Recommended)**
```json
{
  "data": {},
  "meta": {
    "generated_at": "2026-02-03T12:00:00Z"
  }
}
```

**Core Entities**
| Entity | Key Fields | Notes |
| --- | --- | --- |
| Session | `id`, `session_date`, `map_name`, `round_number`, `time_limit`, `actual_time` | Stopwatch: two rounds make one match |
| Round | `id`, `round_date`, `round_time`, `map_name`, `round_number`, `winner_team` | Source of match timeline |
| Player | `guid`, `player_name`, `kills`, `deaths`, `dpm`, `kd` | Aggregated per player |
| Match | `id`, `map_name`, `rounds[]`, `winner_team` | Derived from two rounds |
| ProximityEvent | `timestamp`, `player_guid`, `nearby_guid`, `distance_m` | Prototype |
| ProximityHotzone | `map_name`, `x`, `y`, `count` | Prototype |

**Endpoints In Use**
| Endpoint | Purpose |
| --- | --- |
| `GET /api/status` | Health check |
| `GET /api/seasons/current` | Current season metadata |
| `GET /api/stats/overview` | Home page summary counts |
| `GET /api/stats/last-session` | Latest session summary |
| `GET /api/stats/session-leaderboard` | Session leaders |
| `GET /api/stats/matches` | Recent matches list |
| `GET /api/stats/matches/{id}` | Match details with player breakdown |
| `GET /api/stats/leaderboard` | Global leaderboards |
| `GET /api/stats/player/{name}` | Player profile summary |
| `GET /api/player/{name}/matches` | Player recent matches |
| `GET /api/stats/weapons` | Weapon stats |
| `GET /api/stats/maps` | Map stats |
| `GET /api/stats/records` | Records |
| `GET /api/player/search` | Player autocomplete |
| `POST /api/player/link` | Link Discord to player alias |

**Proximity Endpoints (Prototype)**
| Endpoint | Purpose | Proposed Fields |
| --- | --- | --- |
| `GET /api/proximity/summary` | Top-level proximity summary | `status`, `ready`, `message`, `total_engagements`, `avg_distance_m`, `crossfire_events`, `hotzones`, `sample_rounds`, `top_duos[]` |
| `GET /api/proximity/engagements` | Engagement timeline | `status`, `ready`, `message`, `buckets[]` |
| `GET /api/proximity/hotzones` | Map heatmap bins | `status`, `ready`, `message`, `map_name`, `hotzones[]` |
| `GET /api/proximity/duos` | Duo synergy list | `status`, `ready`, `message`, `duos[]` |
| `GET /api/proximity/events` | Raw event export | `status`, `ready`, `message`, `events[]` |

**Prototype Query Params (Current Stubs)**
- `range_days`: integer window (default: 30)
- `map_name`: filter hotzones by map (optional)
- `limit`: cap event/duo lists (optional)

**SPA Feature Map**
| View | Primary Endpoints | Secondary Endpoints | Status |
| --- | --- | --- | --- |
| Home | `/api/stats/overview`, `/api/stats/last-session` | `/api/stats/session-leaderboard`, `/api/stats/matches` | Live |
| Sessions | `/api/stats/matches` | `/api/stats/matches/{id}` | Live |
| Leaderboards | `/api/stats/leaderboard` | `/api/player/search` | Live |
| Maps | `/api/stats/maps` | None | Live |
| Weapons | `/api/stats/weapons` | None | Live |
| Records | `/api/stats/records` | None | Live |
| Awards | `/api/stats/awards` | `/api/stats/awards/player` | Partial |
| Profile | `/api/stats/player/{name}` | `/api/player/{name}/matches` | Live |
| Proximity | `/api/proximity/summary` | `/api/proximity/duos`, `/api/proximity/hotzones` | Prototype |

**Proximity UI Plan**
- Engagement timeline (per-minute buckets).
- Hot zone heatmap per map.
- Duo synergy list (top pairs by overlap).
- Crossfire events per session.

**Notes**
- Website and proximity features remain prototypes and should be labeled as such in UI.
- Proximity endpoints can return empty data without failing the SPA.
- When proximity pipeline is offline, UI should show “prototype mode” messaging.
- Prototype banners can be enabled per view by adding `data-prototype="true"` and a `data-prototype-slot` container.
