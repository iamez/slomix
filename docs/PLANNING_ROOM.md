# Planning Room MVP

## Purpose
Planning Room is unlocked after the session-ready threshold is met and provides lightweight pre-game coordination:
- committed players list
- team-name suggestions + one-vote-per-user
- simple two-side draft save

## Unlock Rule
Source: `GET /api/planning/today`
- `session_ready.ready` is true when today's `LOOKING` count reaches `AVAILABILITY_SESSION_READY_THRESHOLD`.
- `POST /api/planning/today/create` is blocked until unlock.

## API Endpoints
Router: `website/backend/routers/planning.py`

- `GET /api/planning/today`
- `POST /api/planning/today/create`
- `POST /api/planning/today/join`
- `POST /api/planning/today/suggestions`
- `POST /api/planning/today/vote`
- `POST /api/planning/today/teams`

Security and gating:
- All write endpoints require session auth + linked Discord/player mapping.
- All write endpoints require `X-Requested-With: XMLHttpRequest`.
- Team save is restricted to session creator or promoter/admin.

## Data Model
Migration:
- `website/migrations/007_planning_room_mvp.sql`
- `website/migrations/007_planning_room_mvp_down.sql`

Tables:
- `planning_sessions`
- `planning_team_names`
- `planning_votes`
- `planning_teams`
- `planning_team_members`

## Discord Thread Integration (Best-Effort)
Service: `website/backend/services/planning_discord_bridge.py`

Optional env flags:
- `AVAILABILITY_PLANNING_DISCORD_CREATE_THREAD=false`
- `AVAILABILITY_PLANNING_THREAD_PARENT_CHANNEL_ID=`
- `AVAILABILITY_PLANNING_DISCORD_BOT_TOKEN=`

Behavior:
- If enabled and configured, session creation attempts private-thread creation.
- Failure to create Discord thread does not fail Planning Room creation.

## Frontend
Availability view includes a Planning Room panel:
- open/create button with unlock status
- join action (marks user `LOOKING` if needed)
- name suggestion input + vote actions
- chip-based draft (Unassigned -> A -> B), auto-draft helper, save teams

Files:
- `website/index.html`
- `website/js/availability.js`

## Quick Validation
1. Link Discord/player and set enough `LOOKING` entries for today to meet threshold.
2. Open `#/availability` and create planning room.
3. Add two suggestions, vote one.
4. Draft and save Team A/B.
5. Refresh view and confirm state persists.
6. Optionally enable Discord thread env vars and verify `discord_thread_id` is populated.
