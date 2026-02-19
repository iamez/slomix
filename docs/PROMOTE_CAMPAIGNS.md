# Promote Campaigns

## Scope
Current promote flow across:
- API: `website/backend/routers/availability.py`
- Runtime scheduler: `bot/cogs/availability_poll_cog.py`
- Delivery/idempotency: `bot/services/availability_notifier_service.py`

## Eligibility and recipient rules
Promote actions require:
- authenticated session
- linked Discord/player mapping
- promoter/admin permission (`PROMOTER_DISCORD_IDS`, admin IDs, or admin/root tier)

Recipient selection (snapshot at campaign creation):
- Status must be `LOOKING` (always), plus optional `AVAILABLE` and/or `MAYBE`.
- `subscription_preferences.allow_promotions` must be `true`.
- Channel target is chosen from preference + fallback:
  - `telegram`: telegram -> signal -> discord
  - `signal`: signal -> telegram -> discord
  - `discord`: discord -> telegram -> signal
  - `any`: telegram -> signal -> discord

## API flow
1. Preview:
   - `GET /api/availability/promotions/preview?include_available=...&include_maybe=...`
   - Returns counts + sanitized `recipients_preview` (`display_name`, `status`, `selected_channel`).
2. Create campaign:
   - `POST /api/availability/promotions/campaigns`
   - Creates one campaign with three jobs:
     - `send_reminder_2045`
     - `send_start_2100`
     - `voice_check_2100`
3. Read campaign status:
   - `GET /api/availability/promotions/campaign[?date=YYYY-MM-DD]`
   - Returns aggregate campaign/job state (no recipient snapshot payload).

Scheduling defaults in API:
- reminder `20:45` CET
- start `21:00` CET
- voice-check `+30s` after start

If scheduled time is already in the past at creation time, jobs are shifted forward to near-now (`+10s`/`+20s`).

`dry_run=true` behavior:
- Recipient list is replaced with the campaign initiator only (Discord channel).

## Runtime dispatch
Scheduler loop processes due pending jobs and updates job/campaign status:
- retries until `max_attempts` then marks job `failed`
- `send_start_2100` sets campaign to `sent`, `partial`, or `failed`
- `voice_check_2100` sends targeted follow-ups to missing voice participants and posts a summary to follow-up channel, then marks campaign `followup_sent`

Quiet-hours enforcement:
- Recipients in local quiet window are skipped and logged.

## Anti-spam and idempotency
- One campaign per promoter per day (always).
- Optional global one-campaign-per-day guard (`AVAILABILITY_PROMOTION_GLOBAL_COOLDOWN=true`).
- Delivery idempotency uses `notifications_ledger` keys:
  - `PROMOTE:T-15:<YYYY-MM-DD>`
  - `PROMOTE:T0:<YYYY-MM-DD>`
  - `PROMOTE:FOLLOWUP:<YYYY-MM-DD>`
- Per-send audit rows are written to `availability_promotion_send_logs`.

## QA
Automated:
```bash
pytest -q tests/unit/test_availability_promotions_router.py tests/unit/test_availability_poll_promotion_runtime.py tests/unit/test_availability_notifier_promotion_idempotency.py
```

Manual smoke (dry run recommended first):
1. Ensure promoter user is linked and has promote permission.
2. Save promotion preferences with `allow_promotions=true`.
3. Open Availability Promote modal, inspect preview, and schedule campaign.
4. Confirm one campaign row and three job rows exist.
5. Confirm send logs populate and duplicate dispatch is skipped (idempotent) on rerun/restart.
