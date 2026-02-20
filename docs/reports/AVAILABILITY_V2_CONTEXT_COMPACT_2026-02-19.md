# Availability v2 Context Compact (2026-02-19)

## Why this file
This is the compact source-of-truth so implementation can continue without losing decisions from:
- this repo state,
- your in-thread requirements,
- shared ChatGPT conversation: `https://chatgpt.com/share/69968161-6d58-8007-89c4-ffea01615b9b`.

Related restart handover:
- `docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md`

## Progress log
- 2026-02-19 (current): live outage fix for Availability/Promotions/Planning endpoints:
  - Symptom observed in live logs:
    - `GET /api/availability` -> `500` (`permission denied for table availability_entries`)
    - `GET /api/availability/promotions/campaign` -> `500` (`permission denied for table availability_promotion_campaigns`)
    - `GET /api/planning/today` -> `500` (`relation "planning_sessions" does not exist` for website role visibility)
  - Root cause:
    - DB grant drift for role `website_app` after Availability/Planning schema additions.
  - Immediate runtime remediation applied:
    - Re-ran idempotent migrations:
      - `website/migrations/005_date_based_availability.sql`
      - `website/migrations/006_discord_linking_and_promotions.sql`
      - `website/migrations/007_planning_room_mvp.sql`
    - Applied grants/default privileges for `website_app` on availability/promotions/planning tables and sequences.
    - Verified as `website_app`:
      - table visibility restored (`availability_entries`, `availability_promotion_campaigns`, `planning_sessions`)
      - `SELECT` + `INSERT` + `UPDATE` privileges restored on impacted tables.
  - Preventive hardening:
    - Added migration:
      - `website/migrations/008_website_app_availability_grants.sql`
      - `website/migrations/008_website_app_availability_grants_down.sql`
    - Updated system doc:
      - `docs/AVAILABILITY_SYSTEM.md` now includes migration `008` and explicit live PostgreSQL note for `007/008`.
- 2026-02-19 (current): startup/env hardening + Stage 4 verification evidence refresh:
  - Added robust inline-comment env parsing for integer settings:
    - `bot/config.py`: `_get_config` now sanitizes `.env` values like `27960  # comment`.
    - `website/backend/env_utils.py`: new `getenv_int()` + `strip_inline_comment()` helper.
    - Wired helper into:
      - `website/backend/main.py`
      - `website/backend/routers/api.py`
      - `website/backend/middleware/http_cache_middleware.py`
      - `website/backend/middleware/rate_limit_middleware.py`
  - Added startup/env regression tests:
    - `tests/unit/test_env_parsing.py`
  - Hardened local startup behavior:
    - `scripts/dev_up.sh` now preserves explicit CLI/session overrides for:
      - `BOT_STARTUP_VALIDATE_ONLY`
      - `DISCORD_BOT_TOKEN`
    - This prevents `.env` from unintentionally forcing a full Discord bot start when validate-only was explicitly requested.
  - Added live verification helper script:
    - `docs/reports/stage4_live_verification.sh` for campaign/job/send-log evidence queries on non-sandbox host.
  - Verification:
    - `pytest -q tests/unit/test_env_parsing.py tests/unit/test_availability_poll_promotion_runtime.py tests/unit/test_availability_promotions_router.py` -> `12 passed`
    - `pytest -q tests/unit/test_availability_poll_promotion_runtime.py tests/unit/test_availability_promotions_router.py tests/unit/test_availability_notifier_promotion_idempotency.py tests/unit/test_availability_poll_external_commands.py tests/unit/test_env_parsing.py` -> `17 passed`
  - Runtime/sandbox findings:
    - `uvicorn` startup reaches ready state in logs, but localhost TCP probes (`curl http://127.0.0.1:7000/health`) fail in this sandbox with `curl: (7) Couldn't connect to server`.
    - For sandbox startup smoke, `SKIP_HEALTHCHECK=1` is required; log evidence confirms backend startup/shutdown lifecycle.
    - Stage 4 true live runtime send path remains dependent on a real Discord-connected bot runtime (scheduler starts only after `wait_until_ready()`), so final end-to-end follow-up validation must be executed in non-sandbox/live credentials environment.
- 2026-02-19 (current): continuation hardening + test coverage pass:
  - Added dedicated promotions router test suite:
    - `tests/unit/test_availability_promotions_router.py`
  - New coverage validates:
    - Promote preview auth/link/permission gating
    - Recipient filtering by statuses + explicit opt-in
    - Campaign creation schedule job fan-out (`send_reminder_2045`, `send_start_2100`, `voice_check_2100`)
    - Per-promoter once-per-day campaign guard
    - Promotion preference validation (opt-in + quiet-hours)
    - Access payload includes `can_promote` for eligible linked promoter
  - Fixed server-side validation bug in quiet-hours parser:
    - `website/backend/routers/availability.py` now converts invalid `quiet_hours` formats into HTTP `400` (instead of uncaught `ValueError` -> `500`).
  - Focused regression suite result after patch:
    - `24 passed` (`promotions + availability router + auth linking + notifier idempotency + external avail commands`).
- 2026-02-19 (current): Stage 4 runtime behavior test pass (bot scheduler/follow-up):
  - Added `tests/unit/test_availability_poll_promotion_runtime.py`.
  - New runtime coverage validates:
    - `_process_promotion_jobs` status transitions for start job + campaign status propagation (`partial` when mixed send/fail).
    - retry behavior on dispatch exceptions (pending retry until max attempts, then terminal `failed`).
    - `_dispatch_voice_check_followup` targeting logic:
      - only missing users are pinged,
      - quiet-hours recipients are skipped,
      - summary channel post includes missing + direct-send count,
      - optional game-server cross-check note (`in server but not in voice`) appears when applicable.
  - Focused runtime suite result:
    - `13 passed` (`availability_poll_promotion_runtime + promotions_router + notifier_idempotency + external_commands`).
  - Operational note:
    - sub-agent spawning remained blocked in this session by thread cap (`max 6`), so this slice was completed directly in-thread.
- 2026-02-19 (current): context compacted + linked from `docs/workfile.md`.
- 2026-02-19 (current): Stage 0 bootstrap patches started:
  - Added top-level `GET /health` with DB check in `website/backend/main.py`.
  - Added startup controls for Greatshot boot (`GREATSHOT_STARTUP_ENABLED`).
  - Added local/prod startup scripts: `scripts/dev_up.sh`, `scripts/prod_up.sh`.
  - Added `make prod` and `make dev-local`.
  - Added runbook: `docs/RUNBOOK.md`.
  - Added stricter bot startup exit codes and validate-only mode.
- 2026-02-19 (current): Stage 0 stabilization pass:
  - `BOT_STARTUP_VALIDATE_ONLY` now validates config without full bot initialization.
  - Local env parsing in startup scripts now tolerates CRLF and inline comments.
  - `dev_up.sh` now uses deterministic local defaults (`sqlite`, `memory`, port `7000`) via `DEV_*` overrides.
  - Startup script cleanup improved to terminate child processes on exit.
  - `/health` DB check guarded with timeout to avoid hangs.
  - `docs/RUNBOOK_LOCAL_LINUX.md` added as pointer to `docs/RUNBOOK.md`.
  - Verified unit tests still pass (`13 passed` for auth/availability router tests).
- 2026-02-19 (current): Stage 1-3 implementation audit + hardening pass:
  - Confirmed Availability default UX is now Today/Tomorrow first + Current Queue + Upcoming(3) with collapsible calendar.
  - Confirmed Link Discord CTA entry points on Availability message + Profile card + nav badge.
  - Added CSRF hardening for state-changing availability endpoints (`X-Requested-With` required).
  - Added link-token API throttle (`AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS`).
  - Redacted campaign API recipient payloads to avoid exposing encrypted contact internals.
  - Added promotion quiet-hours enforcement at send time in bot campaign dispatch.
  - Extended availability unit tests for CSRF enforcement, link-token replay fail, and token throttle.
  - Added operator-facing linking guide: `docs/NOTIFICATIONS_LINKING.md`.
  - Added notifier-level idempotent channel send wrappers for campaign jobs (`notifications_ledger` backed).
  - Promotion dispatch now uses explicit ledger keys:
    - `PROMOTE:T-15:<date>`
    - `PROMOTE:T0:<date>`
    - `PROMOTE:FOLLOWUP:<date>`
  - Added unit tests proving duplicate promotion DM/channel sends are skipped via ledger.
  - Added auth-linking flow tests covering:
    - CSRF header enforcement on `/auth/link`
    - conflict when player is already linked to another user
    - link status persistence and unlink behavior
  - Campaign status payload privacy tightened: no recipient snapshot returned from campaign status endpoint.
- 2026-02-19 (current): Stage 5 Planning Room MVP implementation pass:
  - Added migration pair:
    - `website/migrations/007_planning_room_mvp.sql`
    - `website/migrations/007_planning_room_mvp_down.sql`
  - Added planning API router:
    - `GET /api/planning/today`
    - `POST /api/planning/today/create`
    - `POST /api/planning/today/join`
    - `POST /api/planning/today/suggestions`
    - `POST /api/planning/today/vote`
    - `POST /api/planning/today/teams`
  - Added optional best-effort Discord thread bridge on planning-room creation (`website/backend/services/planning_discord_bridge.py`) behind env flags.
  - Added Availability UI Planning Room section: create/open/join, suggestion voting, chip-based draft, auto-draft, team save.
  - Added new tests: `tests/unit/test_planning_router.py`.
  - Verified focused suite (`planning + availability + auth`): `17 passed`.
- 2026-02-19 (current): Shared chat context recovery note:
  - Conversation payload from shared ChatGPT URL was only partially recoverable in tooling due Cloudflare/challenge gating and intermittent extraction failures.
  - One successful extraction snapshot confirmed the root ask verbatim (Availability declutter + Current Queue + Discord linking CTA/profile + linking implementation).
  - The mega-prompt in this repo thread remains the authoritative detailed requirement source for Stage sequencing and acceptance criteria.
  - Recovered requirements reaffirmed:
    - Stage 0->6 delivery sequence
    - Availability + linking + promote/ready-check hard requirements
    - broader “community hub” ideas should remain phased backlog, not block core delivery.
  - Backlog themes explicitly preserved for later phases:
    - thread-based planning rooms/community hub layers
    - team rosters/clubs and event scheduling
    - clips/config sharing and strategy library
    - real-time tracker/analytics and post-session recaps
    - retro/lore/onboarding themed UX tracks

## Mission order (do in sequence)
1. Stage 0: Green startup first (web + bot + DB, no startup errors/warnings, runbook)
2. Stage 1: Availability UX declutter (Today/Tomorrow hero + Current Queue + Upcoming(3) + collapsible calendar)
3. Stage 2: Discord linking + Player mapping + gating + profile entry points
4. Stage 3: Promote campaigns (idempotent scheduling at 20:45 CET and 21:00 CET)
5. Stage 4: Ready-check follow-up (voice presence; optional game-server cross-check)
6. Stage 5: Planning room MVP (post-availability coordination room/thread)
7. Stage 6: Security hardening + tests + docs

## Non-negotiables
- Opt-in only: no unsolicited pings.
- Idempotency: no double-send on retries/restarts.
- Security first: OAuth state + PKCE, redirect allowlist, no token leaks/logging.
- Privacy: do not expose raw contact handles publicly.
- Timezone for game-night workflows: `Europe/Ljubljana` (CET/CEST), with exact reminders at 20:45 and 21:00 CET.
- Incremental, safe diffs; avoid broad refactors.

## Confirmed required product behavior
### Availability UI
- Keep Today/Tomorrow as primary hero panels.
- Add `Current queue` from TODAY `LOOKING` pool.
- Default view should not be full calendar.
- Show compact `Upcoming days` digest for next 3 days.
- Add `Open calendar` toggle to reveal full calendar.

### Access gating
- Unauthenticated/unlinked users: aggregate read-only view.
- Linked users: can submit availability + configure subscription preferences.
- CTA text must be actionable: Link Discord.

### Linking model
- Website user <-> Discord account: 1:1
- Website user <-> Player profile: max 1
- Discord account <-> website user: 1:1
- Flow: Link Discord -> resolve/select Player -> success -> unlink/change allowed.

### Promote workflow
- Permission-restricted `Promote` action.
- Campaign snapshot + schedule two sends for the date:
  - T-15: 20:45 CET
  - T0: 21:00 CET
- Recipients only if explicitly opted in.
- Channel preference order and privacy-aware handling.
- Anti-spam: cooldown/rate limit/idempotency key.
- Audit records for campaign creation/sends.

### Ready-check at 21:00
- Compare expected participants vs voice presence.
- Neutral follow-up for missing players.
- Optional note for in-server-not-in-voice when telemetry exists.

### Multi-channel extension (captured in shared chat)
- Telegram/Signal/Discord availability entry/update/remove flows should be supported.
- Token-based link confirm already planned for Telegram/Signal.

### Planning room (MVP)
- Unlock when session readiness threshold is met.
- Team-name suggestions + voting + lightweight drafting.
- Optional auto-created Discord thread/channel.

## Current repo status snapshot (from latest local audit)
### Already in-progress/implemented in codebase
- Availability UI base work present in `website/js/availability.js` + `website/index.html`.
- Discord OAuth + link state + player suggestion endpoints present in `website/backend/routers/auth.py`.
- Promotion campaign scaffolding present in `website/backend/routers/availability.py` and bot availability services/cog.
- Migration sets present:
  - `website/migrations/006_discord_linking_and_promotions.sql`
  - `website/migrations/006_discord_linking_and_promotions_down.sql`
  - `website/migrations/007_planning_room_mvp.sql`
  - `website/migrations/007_planning_room_mvp_down.sql`
  - `website/migrations/008_website_app_availability_grants.sql`
  - `website/migrations/008_website_app_availability_grants_down.sql`
- Planning room router/UI now present:
  - `website/backend/routers/planning.py`
  - `website/js/availability.js` (planning section logic)
  - `website/index.html` (planning panel markup)
- Tests exist for auth/availability routers and are currently async HTTPX-based.

### Stage 0 gaps found
- No code-level startup parser blockers currently open in local snapshot.
- Remaining risks:
  - environment drift across local/prod secrets and runtime flags,
  - sandbox localhost TCP limitation (requires `SKIP_HEALTHCHECK=1` in this environment),
  - true Stage 4 end-to-end follow-up still requires Discord-connected runtime outside this sandbox.

## Execution contract going forward
- Work stage-by-stage; do not jump ahead until current stage is green.
- Keep this file updated after each stage with:
  - done items,
  - outstanding risks,
  - verification commands,
  - known limitations.

## Stage checklist template (reuse each stage)
- Scope confirmed
- Code changes merged locally
- Tests/verification passed
- Docs updated
- Risks recorded
- Ready for next stage

## Stage 4 live verification checklist (non-sandbox host)
Goal: prove production-like runtime behavior for promotions end-to-end on **2026-02-19** or later with real Discord connectivity.

Preflight (required):
- host must allow loopback/network TCP checks (unlike this sandbox)
- valid `DISCORD_BOT_TOKEN`, linked promoter user, and opted-in test recipients
- promotion flags enabled (`AVAILABILITY_PROMOTION_ENABLED=true`, voice/server checks as needed)
- database access for evidence queries

Evidence table:

| Step | Command / action | Evidence to capture | Status |
| --- | --- | --- | --- |
| 1. Boot stack | `SKIP_INSTALL=1 make dev-local` (or prod-equivalent) and keep bot connected to Discord | `logs/web.log` startup-ready lines + `logs/bot.log` `wait_until_ready`/logged-in lines | Pending (blocked in sandbox) |
| 2. Verify health | `curl -fsS http://127.0.0.1:7000/health` | command output + timestamp | Pending (blocked in sandbox) |
| 3. Preview recipients | `GET /api/availability/promotions/preview?include_available=true&include_maybe=false` as linked promoter | response snapshot: recipient count + channel summary | Pending |
| 4. Create campaign | `POST /api/availability/promotions/campaigns` (`dry_run=false` for true E2E) | API response with `campaign_id` + scheduled times | Pending |
| 5. Verify job fan-out | SQL on `availability_promotion_jobs` by `campaign_id` | rows for `send_reminder_2045`, `send_start_2100`, `voice_check_2100` | Pending |
| 6. Verify T-15 dispatch | wait for / trigger due processing window | `availability_promotion_send_logs` + ledger evidence (`PROMOTE:T-15:<date>`) | Pending |
| 7. Verify T0 dispatch | wait for / trigger start window | send logs + ledger evidence (`PROMOTE:T0:<date>`) | Pending |
| 8. Verify voice follow-up | confirm expected-vs-voice delta at 21:00 | targeted missing-user sends only, quiet-hour skips, summary post evidence | Pending |
| 9. Verify optional server note | enable server check and create in-server-not-in-voice case | follow-up summary includes neutral note when telemetry applies | Pending |
| 10. Verify idempotency | rerun scheduler window/restart bot once | no duplicate sends; ledger blocks re-delivery (`PROMOTE:FOLLOWUP:<date>` etc.) | Pending |

Suggested SQL evidence queries:

```sql
-- Campaign and high-level status
SELECT id, campaign_date, status, recipient_count, created_at, updated_at
FROM availability_promotion_campaigns
ORDER BY id DESC
LIMIT 5;

-- Job lifecycle for one campaign
SELECT campaign_id, job_type, status, attempts, max_attempts, run_at, sent_at, last_error
FROM availability_promotion_jobs
WHERE campaign_id = <campaign_id>
ORDER BY job_type;

-- Delivery outcomes
SELECT campaign_id, job_id, user_id, channel_type, status, message_id, error, created_at
FROM availability_promotion_send_logs
WHERE campaign_id = <campaign_id>
ORDER BY created_at ASC;
```

## Next immediate action
Complete Stage 4 end-to-end runtime verification in non-sandbox/live-like env:
- run web + bot + DB with real Discord connectivity and promotion flags enabled,
- create campaign and verify 20:45 CET / 21:00 CET jobs fire once,
- verify 21:00 voice follow-up path + optional game-server note handling,
- then close remaining Stage 6 hardening/docs gaps and package final PR notes.
