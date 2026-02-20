# Notifications Linking

## Scope
This document covers channel linking for Availability notifications:
- Discord account + player profile linking (website session identity + player mapping)
- Telegram/Signal subscription linking (one-time token flow)

## Discord + Player Linking
Entry points:
- Availability aggregate banner (`Link Discord`)
- Profile `Discord Link Status` card
- Availability nav badge when authenticated but not linked

Flow:
1. User starts `/auth/login` (Discord OAuth2 Authorization Code with PKCE).
2. Callback validates single-use `state` with TTL, exchanges code, stores minimal Discord identity.
3. User picks player profile in profile linking UI (`POST /auth/link`).
4. Link state is available via `GET /auth/link/status`.
5. User can unlink player (`DELETE /auth/link`) or unlink Discord (`POST /auth/discord/unlink`).

Constraints:
- one Discord account -> one website user (`discord_accounts.discord_user_id` unique)
- one website user -> max one Discord account (`discord_accounts.user_id` unique)
- one website user -> max one player (`user_player_links.user_id` PK)
- one player -> max one user (`user_player_links.player_guid` unique)

## Telegram/Signal Linking
Endpoints:
- `POST /api/availability/link-token`
- `POST /api/availability/link-confirm`

Token behavior:
- token stored hashed (`verification_token_hash`)
- default TTL: 30 minutes (configurable per request, bounded)
- one-time use only (`verified_at` must be null)
- replay fails with `Invalid or expired token`
- generation throttled per user+channel by `AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS` (default `30`)

Typical flow:
1. User generates token in website.
2. User sends token to Telegram bot/Signal bridge (`/link <token>`).
3. Bridge calls `link-confirm` with channel address.
4. Subscription row is upserted and enabled.

## Security Notes
- State-changing website session routes require `X-Requested-With: XMLHttpRequest`.
- OAuth endpoints have rate-limit guards.
- No OAuth tokens are persisted in app DB.
- Promotion contact handles are encrypted at rest (`CONTACT_DATA_ENCRYPTION_KEY`).
- Account link/unlink actions are audit logged (`account_link_audit_log`).

## Troubleshooting
- `403 Missing required CSRF header`: include `X-Requested-With: XMLHttpRequest`.
- `403 Linked Discord account required`: complete profile player mapping first.
- `404 Invalid or expired token`: token expired, already used, or wrong channel type.
- `429 Link token was generated recently`: wait and retry after throttle window.
