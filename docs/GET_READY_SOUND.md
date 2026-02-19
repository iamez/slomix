# Get Ready Sound (Web)

## Behavior
Frontend module: `website/js/availability.js`

The sound plays only when all conditions are true:
- User is authenticated
- User is linked with Discord (`can_submit` access state)
- Availability view is active and browser tab is visible
- User enabled `get_ready_sound` in settings
- `session_ready.ready` from `/api/availability` is true
- Cooldown has elapsed

## Trigger Definition
Current trigger is `SESSION_READY` for today's date:
- looking count (`LOOKING`) >= configured threshold
- threshold is included in API session metadata and bot scheduler config

## Cooldown
- Stored in user settings (`sound_cooldown_seconds`, default 480s)
- Local browser state tracks last played event key and timestamp
- Prevents repeated playback for same event and rapid replay across refreshes

## Settings Integration
Settings endpoint:
- `GET /api/availability/settings`
- `POST /api/availability/settings`

Relevant fields:
- `get_ready_sound` / `sound_enabled`
- `sound_cooldown_seconds`

## Verification
1. Enable sound toggle on `#/availability`.
2. Mark enough users as `LOOKING` to satisfy threshold.
3. Keep page open and visible.
4. Confirm single sound trigger.
5. Refresh/reopen within cooldown and verify sound does not replay.
