# React pages — routing status (strangler-fig)

The site uses a **strangler-fig** migration: `website/js/route-registry.js` routes
each view to either legacy JS (`VIEW_MODE.LEGACY`) or this React app
(`VIEW_MODE.MODERN`). A route can be flipped to MODERN by changing its `mode` in
the route registry **provided its `viewId` has a React page wired in
`src/route-host.tsx`'s `routeComponents` map**. Most legacy views do (the staged
set below); a few legacy-only viewIds do **not** yet have a React page (e.g.
`record-book`, `tonight`) and would need one added first. **Nothing here is dead
code** — the not-yet-routed pages are the staged, ready-to-activate side of the
migration.

## Currently served by React (MODERN routes)
- `ProximityPlayer.tsx`  → route `proximity-player`
- `ProximityReplay.tsx`  → route `proximity-replay`
- `ProximityTeams.tsx`   → route `proximity-teams`
- `SkillRating.tsx`      → route `skill-rating`

These depend on the Vite build in `website/static/modern/` (built by the deploy —
see `scripts/deploy_release.sh` step 3c). If that build is missing the routes show
"Modern Route Offline".

## Staged for migration (implemented in React, still served by legacy JS today)
All other pages (Home, Records, Leaderboards, Maps, HallOfFame, Awards, Sessions2,
Profile, Weapons, RetroViz, SessionDetail, Uploads, UploadDetail, Greatshot,
GreatshotDemo, Availability, Admin, Proximity, Rivalries, Story, …). Their live
production rendering is the legacy `website/js/*.js`. To activate one, flip its
route `mode` to `VIEW_MODE.MODERN` in `route-registry.js` and verify parity.

## Build / deploy
- Build: `cd website/frontend && npm run build` → `website/static/modern/`
  (gitignored; produced on deploy, not committed).
- Cache-bust: deploy sets `modern-route-host.js` `BUILD_VERSION` to the git SHA.
- Full rationale + plan: `docs/research/DUAL_FRONTEND_DEPLOY_PLAN_2026-06-29.md`.

## Known dead path in this tree (2026-09-08)

`Availability.tsx` calls `/api/availability/planning/today`. That endpoint has never
existed: `website/backend/main.py` mounts the planning router at `/api/planning`, so
the old React planning panel (20 fields) always rendered its 404 branch. The new
app (`src/app`) does not carry the panel; the `planning_*` tables hold 0 rows
(measured 2026-09-08). Left as a note rather than fixed: this tree is the one
being replaced, and the fix would be to a page nobody routes to.
