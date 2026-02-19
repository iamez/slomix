# Availability System

## Overview
Availability is date-based with website API as the source of truth. Primary UX is Today/Tomorrow first, then compact upcoming days, with the full calendar behind an explicit toggle.

Statuses:
- `LOOKING`
- `AVAILABLE`
- `MAYBE`
- `NOT_PLAYING`

## Current Queue Definition
`Current queue` is derived from **today's** pool:
- include entries with status `LOOKING`
- render names from `users_by_status.LOOKING`
- if empty, show `Queue is empty`

## Access Rules and Gating
- Anonymous: aggregate read-only view.
- Authenticated but not linked to a player: aggregate read-only view, no submit/subscribe/promote; UI shows actionable `Link Discord` CTA.
- Authenticated + linked: can submit availability and manage subscription settings.
- Promote action: requires authenticated + linked + promoter/admin permission.
- State-changing website session routes require `X-Requested-With: XMLHttpRequest` for CSRF hardening.

## Data Model
Migrations:
- `website/migrations/005_date_based_availability.sql`
- `website/migrations/006_discord_linking_and_promotions.sql`
- `website/migrations/007_planning_room_mvp.sql`
- `website/migrations/008_website_app_availability_grants.sql`

Core availability:
- `availability_entries`
- `availability_user_settings`
- `availability_subscriptions`
- `availability_channel_links`
- `notifications_ledger`

Identity/linking:
- `website_users`
- `discord_accounts`
- `user_player_links`
- `account_link_audit_log`

Promotion preferences and campaigns:
- `subscription_preferences`
- `availability_promotion_campaigns`
- `availability_promotion_jobs`
- `availability_promotion_send_logs`

Planning room:
- `planning_sessions`
- `planning_team_names`
- `planning_votes`
- `planning_teams`
- `planning_team_members`

## API Surface
Router: `website/backend/routers/availability.py`

Read/write availability:
- `GET /api/availability?from=YYYY-MM-DD&to=YYYY-MM-DD[&include_users=true]`
- `POST /api/availability`
- `GET /api/availability/me`
- `GET /api/availability/access`

Settings/subscriptions:
- `GET /api/availability/settings`
- `POST /api/availability/settings`
- `GET /api/availability/subscriptions`
- `POST /api/availability/subscriptions`
- `GET /api/availability/preferences` (compat alias)
- `POST /api/availability/preferences` (compat alias)
- `POST /api/availability/link-token`
- `POST /api/availability/link-confirm`

Promotion preferences and campaigns:
- `GET /api/availability/promotion-preferences`
- `POST /api/availability/promotion-preferences`
- `GET /api/availability/promotions/preview`
- `POST /api/availability/promotions/campaigns`
- `GET /api/availability/promotions/campaign`

Planning room:
- `GET /api/planning/today`
- `POST /api/planning/today/create`
- `POST /api/planning/today/join`
- `POST /api/planning/today/suggestions`
- `POST /api/planning/today/vote`
- `POST /api/planning/today/teams`

## Promotion Schedule (CET)
Default campaign schedule is:
- **20:45 CET** reminder job (`send_reminder_2045`)
- **21:00 CET** start job (`send_start_2100`)
- voice follow-up shortly after 21:00 (`voice_check_2100`)

Campaign behavior:
- recipients are snapshot at campaign creation
- recipient eligibility requires `allow_promotions = true`
- channel chosen by preference and available handle (`discord` / `telegram` / `signal`)
- quiet hours are enforced at send time using recipient `quiet_hours` + `timezone`
- anti-spam: one campaign per promoter per day (optional global cooldown)
- notification ledger idempotency keys:
  - `PROMOTE:T-15:<YYYY-MM-DD>`
  - `PROMOTE:T0:<YYYY-MM-DD>`
  - `PROMOTE:FOLLOWUP:<YYYY-MM-DD>`
- all sends are logged in `availability_promotion_send_logs`
- campaign status API returns aggregate-only campaign metadata (no recipient snapshot payload)

## Planning Room MVP
- Unlock: today `LOOKING` count reaches `AVAILABILITY_SESSION_READY_THRESHOLD`.
- Create: linked user can create one planning session for today.
- Join: linked user can join; if needed, join action upserts their today status to `LOOKING`.
- Suggestions/votes: one vote per user per session (`planning_votes` upsert).
- Team draft: two sides (`A`/`B`) with persisted membership in `planning_team_members`.
- Team-save permissions: session creator or promoter/admin.
- Optional Discord thread auto-create is best-effort (session creation still succeeds when Discord API call fails).
- Detailed flow doc: `docs/PLANNING_ROOM.md`.

## Bot and Notifier Integration
- Scheduler: `bot/cogs/availability_poll_cog.py`
- Channel adapters: `bot/services/availability_notifier_service.py`
- Telegram/Signal are adapter-driven; Discord is fully integrated.
- Voice and optional game-server cross-checks use `live_status` data.

## Environment Variables
Website/API:
- `DISCORD_REDIRECT_URI_ALLOWLIST`
- `DISCORD_OAUTH_STATE_TTL_SECONDS`
- `DISCORD_OAUTH_RATE_LIMIT_WINDOW_SECONDS`
- `DISCORD_OAUTH_RATE_LIMIT_MAX_REQUESTS`
- `PROMOTER_DISCORD_IDS`
- `AVAILABILITY_PROMOTION_TIMEZONE`
- `AVAILABILITY_PROMOTION_DRY_RUN_DEFAULT`
- `AVAILABILITY_PROMOTION_GLOBAL_COOLDOWN`
- `AVAILABILITY_PLANNING_DISCORD_CREATE_THREAD`
- `AVAILABILITY_PLANNING_THREAD_PARENT_CHANNEL_ID`
- `AVAILABILITY_PLANNING_DISCORD_BOT_TOKEN`
- `AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS`
- `CONTACT_DATA_ENCRYPTION_KEY`

Bot scheduler:
- `AVAILABILITY_LINK_TOKEN_TTL_MINUTES`
- `AVAILABILITY_PROMOTION_ENABLED`
- `AVAILABILITY_PROMOTION_TIMEZONE`
- `AVAILABILITY_PROMOTION_REMINDER_TIME`
- `AVAILABILITY_PROMOTION_START_TIME`
- `AVAILABILITY_PROMOTION_FOLLOWUP_CHANNEL_ID`
- `AVAILABILITY_PROMOTION_VOICE_CHECK_ENABLED`
- `AVAILABILITY_PROMOTION_SERVER_CHECK_ENABLED`
- `AVAILABILITY_PROMOTION_JOB_MAX_ATTEMPTS`

## Dev Validation (Dry Run)
1. Configure `CONTACT_DATA_ENCRYPTION_KEY` and OAuth env vars.
2. Apply migrations `005` and `006`.
   - for live/local PostgreSQL deployments, include `007` and `008` so planning tables exist and `website_app` table/sequence grants are present.
3. Log in and link to a player profile.
4. Open `#/availability`; verify default view = Today + Tomorrow + Upcoming(3) + `Open calendar`.
5. Save promotion preferences.
6. Open Promote modal, enable `Dry run`, confirm campaign.
7. Verify campaign/job rows:
   - `availability_promotion_campaigns`
   - `availability_promotion_jobs`
   - `availability_promotion_send_logs`
8. Verify scheduled times correspond to **20:45 CET** and **21:00 CET**.
9. Verify planning room flow:
   - `GET /api/planning/today` unlock state
   - create/join/suggest/vote/save teams
   - optional thread id in `planning_sessions.discord_thread_id` when thread auto-create is enabled.
