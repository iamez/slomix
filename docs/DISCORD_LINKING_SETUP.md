# Discord Linking Setup

## Purpose
Enable website login with Discord OAuth2 and map a website user to one player profile.

## Discord App Setup
1. Open Discord Developer Portal.
2. Create/select application.
3. OAuth2 settings:
   - add redirect URI(s), for example:
     - `http://localhost:8000/auth/callback`
     - `https://your-domain/auth/callback`
4. Copy:
   - Client ID
   - Client Secret

## Required Environment Variables
Website/API env:
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DISCORD_REDIRECT_URI`
- `DISCORD_REDIRECT_URI_ALLOWLIST` (comma-separated, must include redirect URI)
- `SESSION_SECRET`

Recommended security env:
- `DISCORD_OAUTH_STATE_TTL_SECONDS` (default `600`)
- `DISCORD_OAUTH_RATE_LIMIT_WINDOW_SECONDS` (default `60`)
- `DISCORD_OAUTH_RATE_LIMIT_MAX_REQUESTS` (default `40`)
- `FRONTEND_ORIGIN` (for stable post-auth redirects)

## Backend Security Controls
Implemented in `website/backend/routers/auth.py`:
- Authorization Code flow (server-side)
- state validation with TTL
- PKCE challenge/verifier (`S256`)
- redirect URI allowlist checks
- rate limiting on OAuth endpoints
- CSRF-style `X-Requested-With` requirement on state-changing routes
- account-link audit log table (`account_link_audit_log`)

## Linking Flow
1. User logs in via `/auth/login`.
2. Callback `/auth/callback` stores website identity + Discord metadata.
3. User opens link picker in profile and selects a player (`POST /auth/link`).
4. Link status is read from `/auth/link/status`.
5. User can unlink player (`DELETE /auth/link`) or unlink Discord (`POST /auth/discord/unlink`).

## Data Mapping Rules
- one Discord account ↔ one website user (`discord_accounts`)
- one website user ↔ max one player (`user_player_links`)
- one player_guid ↔ max one website user (unique constraint)

## Quick Verification
1. Log in with Discord.
2. Call `/auth/me` and `/auth/link/status`.
3. Link a player from profile UI.
4. Confirm rows in:
   - `website_users`
   - `discord_accounts`
   - `user_player_links`
5. Confirm audit events in `account_link_audit_log`.
