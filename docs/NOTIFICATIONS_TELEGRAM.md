# Availability Notifications - Telegram

## Connector
Implementation:
- `bot/services/telegram_connector.py`
- `bot/cogs/availability_poll_cog.py` (Telegram command polling)

The connector applies pacing and retries, including explicit `429 retry_after` handling.

## Feature Flags
- `AVAILABILITY_TELEGRAM_ENABLED`
- `AVAILABILITY_TELEGRAM_BOT_TOKEN`
- `AVAILABILITY_TELEGRAM_API_BASE_URL`
- `AVAILABILITY_TELEGRAM_MIN_INTERVAL_SECONDS`
- `AVAILABILITY_TELEGRAM_MAX_RETRIES`
- `AVAILABILITY_TELEGRAM_REQUEST_TIMEOUT_SECONDS`

## Subscription Flow
1. Linked Discord user runs: `!avail_link telegram`
2. Bot issues one-time token (stored hashed in `availability_channel_links`).
3. In Telegram, user sends: `/link <token>`
4. Bot verifies token and enables `availability_subscriptions` row for `channel_type='telegram'`.
5. User can disable with `/unlink` in Telegram or `!avail_unsubscribe telegram` in Discord.

This flow maps Telegram chat identity to authenticated Slomix/Discord-linked user via token handoff.

## Rate Limit Behavior
- Global pacing lock inside connector
- Retry on transient failures
- Retry-after handling for HTTP 429

## Verification
1. Enable Telegram flags and restart bot.
2. Generate token with `!avail_link telegram`.
3. Link via Telegram `/link` command.
4. Trigger reminder/ready event and confirm Telegram delivery.
5. Confirm ledger row for `channel_type='telegram'`.
