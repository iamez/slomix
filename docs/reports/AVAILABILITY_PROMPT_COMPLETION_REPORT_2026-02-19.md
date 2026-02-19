# Availability Prompt Completion Report (2026-02-19)

Primary requirement source: `docs/workfile.md`

Context sources reviewed:
- `docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md`
- `docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md`
- `docs/workfile.md`

## Executive status
- Availability + linking + promotions + planning are implemented and covered by targeted tests.
- Prompt-specified docs now exist: `docs/AVAILABILITY_UI.md`, `docs/LINKING_ACCOUNTS.md`, `docs/PROMOTE_CAMPAIGNS.md`.
- Live outage root cause from logs (`permission denied`, `planning_sessions does not exist`) was remediated by re-running migrations/grants and verifying privileges as `website_app`.
- Remaining gap is operational verification outside this sandbox (true runtime E2E with live Discord-connected scheduler), not missing core feature implementation.

## Completion matrix

| Prompt area (`docs/workfile.md`) | Status | Evidence |
| --- | --- | --- |
| Stage 0: Linux run + runbook + health endpoint | Partial (sandbox-limited health probe) | `docs/RUNBOOK_LOCAL_LINUX.md`, `docs/RUNBOOK.md`, `scripts/dev_up.sh`, `Makefile`, `website/backend/main.py` |
| Stage 1: Availability UX revamp | Complete | `website/index.html`, `website/js/availability.js`, `docs/AVAILABILITY_UI.md` |
| Stage 2: Discord + Telegram/Signal linking | Complete | `website/backend/routers/auth.py`, `website/backend/routers/availability.py`, `website/js/auth.js`, `website/index.html`, `docs/LINKING_ACCOUNTS.md` |
| Stage 3: Promote campaign + idempotency + follow-up | Complete (implemented route is `/api/availability/promotions/campaigns`) | `website/backend/routers/availability.py`, `bot/cogs/availability_poll_cog.py`, `bot/services/availability_notifier_service.py`, `docs/PROMOTE_CAMPAIGNS.md` |
| Stage 4: Planning room MVP | Complete | `website/backend/routers/planning.py`, `website/backend/services/planning_discord_bridge.py`, `website/js/availability.js`, `website/index.html`, `website/migrations/007_planning_room_mvp.sql`, `docs/PLANNING_ROOM.md` |
| Stage 5: Tests/security/docs | Complete for coded requirements; live runtime signoff pending | tests listed below, CSRF + OAuth PKCE/state + rate limiting + token hashing present in router/middleware code |

## Live outage remediation performed (2026-02-19)

Applied on localhost PostgreSQL as `etlegacy_user`:
- `website/migrations/006_discord_linking_and_promotions.sql`
- `website/migrations/007_planning_room_mvp.sql`
- `website/migrations/008_website_app_availability_grants.sql`

Verification as `website_app`:
- `player_links` privileges: `true`
- `availability_entries` privileges: `true`
- `availability_promotion_campaigns` privileges: `true`
- `planning_sessions` privileges: `true`
- `planning_sessions` exists: `true`

This directly addresses the reported errors:
- `permission denied for table player_links`
- `permission denied for table availability_entries`
- `permission denied for table availability_promotion_campaigns`
- `relation "planning_sessions" does not exist`

## Verification runs (this pass)

Command:
```bash
pytest -q tests/unit/test_availability_router.py tests/unit/test_auth_linking_flow.py tests/unit/test_availability_promotions_router.py tests/unit/test_availability_poll_promotion_runtime.py tests/unit/test_availability_notifier_promotion_idempotency.py tests/unit/test_planning_router.py tests/unit/test_env_parsing.py
```
Result:
- `33 passed`

## Remaining items / caveats

1. Sandbox networking here cannot reliably prove `curl http://127.0.0.1:7000/health` during local boot smoke, so Stage 0 runtime health must be validated on your host session.
2. Prompt wording mentions `POST /api/promote`; implementation provides equivalent functionality at `POST /api/availability/promotions/campaigns`.
3. Final live signoff still requires non-sandbox runtime observation for scheduled promotion jobs and follow-up sends with real Discord connectivity.

## Post-restart live verification (2026-02-19 17:54 CET)

After `systemctl restart etlegacy-bot.service etlegacy-web.service`:
- `etlegacy-web.service` active/running
- `etlegacy-bot.service` active/running
- `GET /health` -> `200` (`{\"status\":\"ok\",\"database\":\"ok\"}`)
- `GET /api/availability` -> `200`
- `GET /api/planning/today` -> `200`
- `GET /api/availability/promotions/campaign` -> `401` anonymous (expected)
- No new `permission denied`, `relation does not exist`, or `500` lines observed in recent web journal tail.
