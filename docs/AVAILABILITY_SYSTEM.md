# Availability System

## Overview
The availability system is now date-based and uses the website API as the source of truth. Users set one status per date:

- `LOOKING`
- `AVAILABLE`
- `MAYBE`
- `NOT_PLAYING`

Anonymous users can read aggregated availability, but only authenticated users with a linked Discord account can submit entries or manage notification subscriptions.

## Data Model
Migration: `website/migrations/005_date_based_availability.sql`

Core tables:
- `availability_entries`
  - `id`, `user_id`, `user_name`, `entry_date`, `status`, `created_at`, `updated_at`
  - unique `(user_id, entry_date)`
- `availability_subscriptions`
  - `id`, `user_id`, `channel_type`, `channel_address`, `enabled`, `verified_at`, `preferences`, timestamps
  - `channel_type in ('discord','telegram','signal')`
  - unique `(user_id, channel_type)`
- `notifications_ledger`
  - `id`, `user_id`, `event_key`, `channel_type`, `sent_at`, `message_id`, `error`, `retries`, `payload`, `updated_at`
  - unique `(user_id, event_key, channel_type)`

Supporting tables:
- `availability_user_settings` (get-ready sound + reminder preferences)
- `availability_channel_links` (one-time token verification for Telegram/Signal linking)

## API
Router: `website/backend/routers/availability.py`

Primary endpoints:
- `GET /api/availability?from=YYYY-MM-DD&to=YYYY-MM-DD[&include_users=true]`
- `POST /api/availability`
- `GET /api/availability/me`

Settings/subscriptions:
- `GET /api/availability/access`
- `GET /api/availability/settings`
- `POST /api/availability/settings`
- `GET /api/availability/subscriptions`
- `POST /api/availability/subscriptions`

Compatibility aliases:
- `GET /api/availability/preferences`
- `POST /api/availability/preferences`

Link verification flow:
- `POST /api/availability/link-token`
- `POST /api/availability/link-confirm`

## Rules
- Past dates are read-only.
- Submission horizon is capped at 90 days ahead.
- Date-range reads are capped to prevent unbounded queries.
- `include_users=true` only exposes per-user lists to authenticated users.

## Scheduler + Events
Bot-side scheduler runs in `bot/cogs/availability_poll_cog.py` and uses advisory locking where available.

Events:
- `DAILY_REMINDER`
- `SESSION_READY`
- `FRIENDS_LOOKING` (reserved)

Stable event keys are generated in `bot/services/availability_notifier_service.py`:
- `DAILY_REMINDER:YYYY-MM-DD`
- `SESSION_READY:YYYY-MM-DD:threshold=N`

## Bot Integration
- Command: `!avail <today|tomorrow|YYYY-MM-DD> <LOOKING|AVAILABLE|MAYBE|NOT_PLAYING>`
- Token command: `!avail_link <telegram|signal>`
- Unsubscribe command: `!avail_unsubscribe <discord|telegram|signal>`

Notifier service:
- `bot/services/availability_notifier_service.py`
- Enforces idempotency with `notifications_ledger`
- Routes delivery to Discord DM, Telegram, Signal by subscription and feature flags

## How To Test
1. Apply migration `website/migrations/005_date_based_availability.sql`.
2. Log in to website, link Discord, open `#/availability`.
3. Set statuses for today, tomorrow, and a future date (>7 days).
4. Verify anonymous session can read aggregates but cannot submit.
5. Toggle notification settings and get-ready sound in website settings block.
6. Run `!avail today LOOKING` in Discord and verify website reflects the change.
7. Trigger `SESSION_READY` threshold and confirm:
   - no duplicate sends per user/channel/event_key
   - `notifications_ledger` rows track `message_id` or `error/retries`
8. Telegram link test:
   - run `!avail_link telegram`
   - in Telegram send `/link <token>`
   - verify `availability_subscriptions` updated
9. Signal link test:
   - run `!avail_link signal`
   - consume token through signal gateway flow
   - verify subscription row and delivery behavior

### Local Dev Checklist
1. Set env flags for Discord bot + website + optional Telegram/Signal.
2. Apply migration in local Postgres.
3. Run website and bot.
4. Verify `GET /api/availability` returns `days[]` and `session_ready`.
5. Verify `POST /api/availability` enforces linked Discord and 90-day horizon.
6. Verify `notifications_ledger` updates after reminder/ready sends.

### Staging Checklist
1. Enable feature flags incrementally:
   - Discord first
   - Telegram second
   - Signal third
2. Run a forced `SESSION_READY` dry run with low threshold in staging.
3. Confirm idempotency by re-running same event key (no duplicates).
4. Verify channel unlink flows disable future deliveries.
5. Restore production thresholds and reminder time before promoting.
