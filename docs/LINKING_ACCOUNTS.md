# Linking Accounts

## Scope
Current account-linking flows for:
- Discord auth + player profile linking (`/auth/*`)
- Telegram/Signal channel linking for availability subscriptions (`/api/availability/link-*`)

## Discord + player profile linking
Primary endpoints:
- `GET /auth/login`
- `GET /auth/callback`
- `GET /auth/link/start` (redirect helper used by Availability/Profile CTA buttons)
- `GET /auth/link/status`
- `POST /auth/link`
- `DELETE /auth/link`
- `POST /auth/discord/unlink`

Behavior:
1. Login uses Discord OAuth2 Authorization Code + PKCE.
2. Callback validates OAuth `state` + TTL and creates/refreshes identity rows.
3. Player linking is explicit via `POST /auth/link` (profile UI).
4. Unlink player keeps session; unlink Discord clears session and returns `redirect_url`.

Data constraints:
- `discord_accounts.discord_user_id` is unique.
- `discord_accounts.user_id` is unique.
- `user_player_links.user_id` is primary key (one player link per user).
- `user_player_links.player_guid` is unique (one owner per player).
- Link actions are audit logged in `account_link_audit_log`.

## Telegram/Signal linking (availability channels)
Endpoints:
- `POST /api/availability/link-token`
- `POST /api/availability/link-confirm`
- `DELETE /api/availability/subscriptions/{channel_type}` (`telegram` or `signal`)

Behavior:
1. Linked user requests token for `telegram` or `signal`.
2. Token is stored hashed (`verification_token_hash`) with expiry.
3. Bridge/client confirms token with `channel_address`.
4. Link row is marked verified and `availability_subscriptions` is enabled/upserted.
5. User can unlink from profile with `DELETE /api/availability/subscriptions/{channel_type}`.

Profile UI controls:
- `Generate Link Token` (Telegram/Signal)
- `Unlink Telegram` / `Unlink Signal`
- Status output in `profile-channel-link-status`

Rules:
- Token TTL is bounded to `5..120` minutes (default request value `30`).
- One-time use only (`verified_at` must still be null).
- Replay returns `404 Invalid or expired token`.
- Token creation is throttled per user+channel by `AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS` (default `30`).

## CSRF hardening
State-changing session routes require:
- Header: `X-Requested-With: XMLHttpRequest`

This applies to auth write routes (`/auth/link`, `/auth/logout`, `/auth/discord/unlink`) and availability write routes (for example `/api/availability`, `/api/availability/settings`, `/api/availability/link-token`, `/api/availability/subscriptions/{channel_type}`).

## QA
Automated:
```bash
pytest -q tests/unit/test_auth_linking_flow.py tests/unit/test_availability_router.py
```

Manual smoke:
1. Use Availability `Link Discord` CTA while logged out; confirm redirect to `/auth/login`.
2. Log in and open `#/profile`; link a player; confirm `/auth/link/status` shows `player_linked=true`.
3. Unlink player; confirm `player_linked=false`.
4. Generate Telegram/Signal link token; confirm first `link-confirm` succeeds and replay fails with 404.
5. Click Unlink Telegram/Signal and verify subscription/link rows are removed.
