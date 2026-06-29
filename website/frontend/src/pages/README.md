# React pages — routing status (strangler-fig)

The site uses a **strangler-fig** migration: `website/js/route-registry.js` routes
each view to either legacy JS (`VIEW_MODE.LEGACY`) or this React app
(`VIEW_MODE.MODERN`). `src/route-host.tsx` lazy-imports **all** pages here so any
route can be flipped to MODERN by changing only its `mode` in the route registry —
no code move required. **Nothing here is dead code**; the not-yet-routed pages are
the staged, ready-to-activate side of the migration.

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
