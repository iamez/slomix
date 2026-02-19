# Availability Notifications - Signal

## Connector
Implementation:
- `bot/services/signal_connector.py`
- `bot/services/availability_notifier_service.py`

Supported modes:
- `cli` (default): `signal-cli` subprocess send
- `daemon`: HTTP daemon endpoint

## Feature Flags
- `AVAILABILITY_SIGNAL_ENABLED`
- `AVAILABILITY_SIGNAL_MODE` (`cli` or `daemon`)
- `AVAILABILITY_SIGNAL_CLI_PATH`
- `AVAILABILITY_SIGNAL_SENDER`
- `AVAILABILITY_SIGNAL_DAEMON_URL`
- `AVAILABILITY_SIGNAL_MIN_INTERVAL_SECONDS`
- `AVAILABILITY_SIGNAL_MAX_RETRIES`
- `AVAILABILITY_SIGNAL_REQUEST_TIMEOUT_SECONDS`

## Subscription Flow
1. Linked Discord user runs: `!avail_link signal`
2. Bot creates one-time token in `availability_channel_links`.
3. Token is consumed by Signal gateway flow and confirmed to `availability_subscriptions`.
4. User can disable from Discord via `!avail_unsubscribe signal`.

## Operator Setup (signal-cli)
1. Install and register `signal-cli` sender account.
2. Set `AVAILABILITY_SIGNAL_SENDER` to registered number.
3. If daemon mode:
   - run signal-cli daemon
   - set `AVAILABILITY_SIGNAL_DAEMON_URL`
4. Restart bot and validate with test event.

## Verification
1. Enable signal feature flags.
2. Link Signal subscription using token flow.
3. Trigger reminder/ready event.
4. Confirm Signal message delivery and ledger entry (`channel_type='signal'`).
