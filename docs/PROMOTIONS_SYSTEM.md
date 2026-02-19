# Promotions System

## Goal
Create auditable, rate-limited outreach campaigns from Availability to help start sessions without spam.

## Schedule (CET)
Default per campaign:
- reminder: **20:45 CET**
- start ping: **21:00 CET**
- follow-up voice check: shortly after 21:00

## Permissions
Promote is allowed only for:
- authenticated users
- linked Discord + linked player users
- promoter/admin users (`PROMOTER_DISCORD_IDS` or admin permissions)

## Recipient Eligibility
Recipients are snapshot at campaign creation and filtered by:
- availability status set (always `LOOKING`, optional `AVAILABLE`/`MAYBE`)
- `allow_promotions = true` in `subscription_preferences`
- available channel target
- recipient quiet-hours + timezone are enforced at send time (quiet recipients are skipped + logged)

Channel selection priority uses preference + fallback:
- `telegram`
- `signal`
- `discord`

## Campaign Lifecycle
Tables:
- `availability_promotion_campaigns`
- `availability_promotion_jobs`
- `availability_promotion_send_logs`

Flow:
1. UI preview (`GET /api/availability/promotions/preview`)
2. create campaign (`POST /api/availability/promotions/campaigns`)
3. scheduler claims due jobs
4. notifier sends channel messages
5. follow-up voice/server checks
6. status/log updates
7. targeted follow-up delivery to missing recipients + optional neutral channel summary

Campaign status payloads are aggregate-only (counts/channels/jobs). Recipient preview is returned only by `GET /api/availability/promotions/preview` for eligible promoters.

## Anti-Spam and Reliability
- one campaign per promoter per day
- optional global one-per-day cooldown
- idempotency key per campaign payload
- per-send ledger idempotency keys:
  - `PROMOTE:T-15:<YYYY-MM-DD>`
  - `PROMOTE:T0:<YYYY-MM-DD>`
  - `PROMOTE:FOLLOWUP:<YYYY-MM-DD>`
- retries with max attempts (`AVAILABILITY_PROMOTION_JOB_MAX_ATTEMPTS`)
- send logs per recipient/channel/job

## Privacy and Contact Storage
Promotion handles are stored encrypted:
- `telegram_handle_encrypted`
- `signal_handle_encrypted`

Configure:
- `CONTACT_DATA_ENCRYPTION_KEY` (Fernet)

## Environment Variables
Website/API:
- `PROMOTER_DISCORD_IDS`
- `AVAILABILITY_PROMOTION_TIMEZONE`
- `AVAILABILITY_PROMOTION_DRY_RUN_DEFAULT`
- `AVAILABILITY_PROMOTION_GLOBAL_COOLDOWN`
- `AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS`
- `CONTACT_DATA_ENCRYPTION_KEY`

Bot scheduler:
- `AVAILABILITY_PROMOTION_ENABLED`
- `AVAILABILITY_PROMOTION_TIMEZONE`
- `AVAILABILITY_PROMOTION_REMINDER_TIME`
- `AVAILABILITY_PROMOTION_START_TIME`
- `AVAILABILITY_PROMOTION_FOLLOWUP_CHANNEL_ID`
- `AVAILABILITY_PROMOTION_VOICE_CHECK_ENABLED`
- `AVAILABILITY_PROMOTION_SERVER_CHECK_ENABLED`
- `AVAILABILITY_PROMOTION_JOB_MAX_ATTEMPTS`

## Dev Dry-Run Test
1. Set `AVAILABILITY_PROMOTION_DRY_RUN_DEFAULT=true` (or use modal checkbox).
2. Create campaign from Availability modal.
3. Confirm scheduled jobs and timestamps.
4. Verify send logs are created and only promoter receives dry-run delivery.
