# Availability UI

## Scope
Current `#/availability` behavior from:
- `website/index.html`
- `website/js/availability.js`
- `website/backend/routers/availability.py`

## What the UI shows today
1. Today/Tomorrow action cards with four statuses: `LOOKING`, `AVAILABLE`, `MAYBE`, `NOT_PLAYING`.
2. Current Queue section from today's `users_by_status.LOOKING`; empty state is `Queue is empty`.
3. Upcoming quick view for 3 days (starting at today + 2).
4. Collapsible calendar (default collapsed). Toggle text: `Open calendar` / `Close calendar`.
5. Selected-day panel with totals, per-status counts, optional user chips, and write controls.
6. Optional campaign status panel when a campaign exists (`/api/availability/promotions/campaign`).

## Access and output gating
- Anonymous:
  - Aggregate read-only.
  - Banner: `Aggregate view only. Link your Discord account to a player profile to submit or subscribe.`
  - Preferences section hidden.
- Authenticated but not linked:
  - Aggregate read-only.
  - Same link CTA and settings hint: `Link your Discord profile to manage settings.`
  - Promote button disabled (`Link Discord to promote.` tooltip).
- Authenticated and linked:
  - Can submit availability (`POST /api/availability`).
  - Can save settings/subscription toggles (`POST /api/availability/settings`).
  - Ready sound can play when session-ready is true and cooldown allows.
- Promoter/admin (linked):
  - Promote button enabled; modal can preview recipients and schedule a campaign.

## API inputs used by the UI
- `GET /api/availability/access` -> `authenticated`, `linked_discord`, `can_submit`, `can_promote`.
- `GET /api/availability?from=...&to=...&include_users=...` -> day aggregates + `session_ready`.
- `GET /api/availability/settings` (linked users only).
- State-changing endpoints require header `X-Requested-With: XMLHttpRequest`:
  - `POST /api/availability`
  - `POST /api/availability/settings`
  - `POST /api/availability/promotions/campaigns`

## QA
Automated:
```bash
pytest -q tests/unit/test_availability_router.py
```

Manual smoke:
1. Open `#/availability` logged out; confirm read-only banner and hidden preferences.
2. Log in without a player link; confirm Link CTA and disabled promote.
3. Link player profile; set Today/Tomorrow statuses and refresh; confirm persistence.
4. Toggle calendar open/close; confirm button label changes.
5. If promoter/admin, open Promote modal and confirm preview loads.
