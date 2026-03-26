# Website Upgrade Foundation

This document locks the first implementation slice for the website tech-stack upgrade.

## Preserved behavior

- `website/index.html` remains the only top-level HTML entry.
- `website/js/app.js` remains the top-level hash router and route dispatcher.
- Existing public hash routes stay unchanged, especially:
  - `#/greatshot/{section}`
  - `#/greatshot/demo/{demoId}`
  - `#/uploads/{uploadId}`
  - `#/session-detail/{sessionId}`
  - `#/session-detail/date/{sessionDate}`
- FastAPI remains the same-origin contract source for `/api/*`, `/auth/*`, `/share/{id}`, `/greatshot*`, and static assets.

## Exact improvement

- Add a dedicated React/TypeScript/Vite workspace under `website/frontend/`.
- Introduce an explicit route registry with `mode: legacy | modern`.
- Keep all routes on `legacy` for now.
- Add a same-origin modern asset target at `website/static/modern/`.
- Block `/frontend/*` from public serving so source files are not exposed by the existing `StaticFiles` mount.

## What could break

- Changing route mode before the modern bundle exists will render the fallback panel instead of the legacy surface.
- A future modern route that does not fully replace its legacy loader can double-render into the same view container.
- Any change that lets React own top-level routing will conflict with the current hash parser and rollback model.

## Parity verification

- Hash parsing and hash generation still resolve to the same route shapes.
- Nav highlighting still maps the same surfaces to the same nav items.
- `greatshot` special entry routes and `/share/{upload_id}` remain untouched.
- Rollback stays route-local: switch a route definition back to `legacy`.

## Route matrix

| View | Current hash shape | Current mode | Wave | Surface type | Current owner |
|---|---|---|---|---|---|
| `home` | `#/` or empty hash | `legacy` | A | read-heavy | boot widgets in `js/app.js` |
| `sessions` | `#/sessions` | `legacy` | A | read-heavy | `js/sessions.js` |
| `leaderboards` | `#/leaderboards` | `legacy` | A | read-heavy | `js/leaderboard.js` |
| `maps` | `#/maps` | `legacy` | A | read-heavy | `js/matches.js` |
| `records` | `#/records` | `legacy` | A | read-heavy | `js/records.js` |
| `awards` | `#/awards` | `legacy` | A | read-heavy | `js/awards.js` |
| `profile` | `#/profile` | `legacy` | A | read-heavy | `js/player-profile.js` |
| `weapons` | `#/weapons` | `legacy` | B | read-heavy | `js/matches.js` |
| `proximity` | `#/proximity` | `legacy` | B | read-heavy | `js/proximity.js` |
| `hall-of-fame` | `#/hall-of-fame` | `legacy` | B | read-heavy | `js/hall-of-fame.js` |
| `retro-viz` | `#/retro-viz` | `legacy` | B | read-heavy | `js/retro-viz.js` |
| `sessions2` | `#/sessions2` | `legacy` | B | read-heavy | `js/sessions2.js` |
| `session-detail` | `#/session-detail/{id}` or `#/session-detail/date/{date}` | `legacy` | B | read-heavy | `js/session-detail.js` |
| `greatshot` | `#/greatshot/{section}` | `legacy` | C | mixed | `js/greatshot.js` |
| `greatshot-demo` | `#/greatshot/demo/{demoId}` | `legacy` | C | write/auth-heavy | `js/greatshot.js` |
| `uploads` | `#/uploads` | `legacy` | C | write/auth-heavy | `js/uploads.js` |
| `upload-detail` | `#/uploads/{uploadId}` | `legacy` | C | mixed | `js/uploads.js` |
| `availability` | `#/availability` | `legacy` | C | write/auth-heavy | `js/availability.js` |
| `admin` | `#/admin` | `legacy` | C | write/auth-heavy | `js/admin-panel.js` |

## Notes for later migrations

- The current product uses `#/session-detail/...`, not `#/sessions2/{id}`. Preserve that unless a compatibility alias is added intentionally.
- `profile` is not currently deep-linked to a player in the hash. The selected player lives in module state today.
- `home` should not be treated as a single route loader; it is a composition of boot-time widgets and deferred loads.
