# Shop-Close Handover (Availability/Linking/Promotions/Planning)
Date: 2026-02-19
Scope: Availability feature track requested in `docs/workfile.md`

## 1) Read This First (when you return)
Load in this exact order:
1. `docs/reports/SHOP_CLOSE_HANDOVER_AVAILABILITY_2026-02-19.md` (this file)
2. `docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md`
3. `docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md`
4. `docs/reports/AVAILABILITY_PROMPT_COMPLETION_REPORT_2026-02-19.md`
5. `docs/workfile.md`

Supporting docs created for this effort:
- `docs/AVAILABILITY_UI.md`
- `docs/LINKING_ACCOUNTS.md`
- `docs/PROMOTE_CAMPAIGNS.md`
- `docs/PLANNING_ROOM.md`

## 2) Current State Snapshot (as of 2026-02-19)
- Web service: `etlegacy-web.service` running (Uvicorn on `0.0.0.0:8000`).
- Bot service: `etlegacy-bot.service` running.
- Health check confirmed: `GET /health` returned `200` with `{"status":"ok","database":"ok"}`.
- Availability endpoints confirmed after restart:
  - `GET /api/availability` -> `200`
  - `GET /api/planning/today` -> `200`
  - `GET /api/availability/promotions/campaign` -> `401` when anonymous (expected)

## 3) What Was Broken and What Was Fixed

### Reported runtime failures
From logs before fix:
- `permission denied for table availability_entries`
- `permission denied for table availability_promotion_campaigns`
- `permission denied for table player_links`
- `relation "planning_sessions" does not exist`

### Root cause
- DB grant/schema drift for `website_app` role after availability/linking/planning additions.

### Fix applied
Executed locally on 2026-02-19:
- `website/migrations/006_discord_linking_and_promotions.sql`
- `website/migrations/007_planning_room_mvp.sql`
- `website/migrations/008_website_app_availability_grants.sql`

Then verified as `website_app`:
- `player_links` privileges: true
- `availability_entries` privileges: true
- `availability_promotion_campaigns` privileges: true
- `planning_sessions` privileges: true
- `planning_sessions` exists: true

## 4) Feature Completion Summary

Prompt source: `docs/workfile.md`

- Stage 1 (Availability UI): complete
- Stage 2 (Discord + Telegram/Signal linking UX): complete
- Stage 3 (Promote campaigns + idempotency): complete (implemented route: `/api/availability/promotions/campaigns`)
- Stage 4 (Planning Room MVP): complete
- Stage 5 (tests/docs/security hardening): strong coverage and docs added
- Stage 0 (local startup verification): implemented; sandbox loopback limits were the only blocker there

Canonical completion report:
- `docs/reports/AVAILABILITY_PROMPT_COMPLETION_REPORT_2026-02-19.md`

## 5) Tests and Latest Results
Command used:
```bash
pytest -q \
  tests/unit/test_availability_router.py \
  tests/unit/test_auth_linking_flow.py \
  tests/unit/test_availability_promotions_router.py \
  tests/unit/test_availability_poll_promotion_runtime.py \
  tests/unit/test_availability_notifier_promotion_idempotency.py \
  tests/unit/test_planning_router.py \
  tests/unit/test_env_parsing.py
```
Result:
- `33 passed` (2026-02-19)

## 6) Operational Quick Check (run when coming back)

### Service health
```bash
systemctl status etlegacy-web.service --no-pager
systemctl status etlegacy-bot.service --no-pager
```

### Endpoint sanity
```bash
curl -sS http://127.0.0.1:8000/health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/availability
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/planning/today
```
Expected:
- `/health` returns JSON with `status=ok`
- availability/planning return `200`

### Error watch
```bash
journalctl -f -u etlegacy-web.service -u etlegacy-bot.service -o cat | grep -iE "warn|error|exception|traceback|critical|permission denied|does not exist| 500 "
```

## 7) If the Old DB Errors Reappear
Re-apply migrations/grants in this order:
```bash
# run as DB owner role (example role in this repo: etlegacy_user)
psql -v ON_ERROR_STOP=1 -h localhost -p 5432 -U etlegacy_user -d etlegacy -f website/migrations/006_discord_linking_and_promotions.sql
psql -v ON_ERROR_STOP=1 -h localhost -p 5432 -U etlegacy_user -d etlegacy -f website/migrations/007_planning_room_mvp.sql
psql -v ON_ERROR_STOP=1 -h localhost -p 5432 -U etlegacy_user -d etlegacy -f website/migrations/008_website_app_availability_grants.sql
```

Then verify as `website_app`:
```sql
SELECT has_table_privilege('website_app','player_links','SELECT,INSERT,UPDATE,DELETE');
SELECT has_table_privilege('website_app','availability_entries','SELECT,INSERT,UPDATE,DELETE');
SELECT has_table_privilege('website_app','availability_promotion_campaigns','SELECT,INSERT,UPDATE,DELETE');
SELECT has_table_privilege('website_app','planning_sessions','SELECT,INSERT,UPDATE,DELETE');
SELECT to_regclass('public.planning_sessions') IS NOT NULL;
```

## 8) Known Caveats (Do Not Forget)
1. Anonymous `GET /api/availability/promotions/campaign` returning `401` is expected behavior.
2. Worktree is heavily dirty and includes many unrelated changes; avoid blanket commits/reset.
3. Prompt mentions `POST /api/promote`; actual implemented endpoint is `POST /api/availability/promotions/campaigns`.
4. Live E2E campaign scheduling confirmation (real Discord delivery timing) still requires runtime verification with real credentials and active bot connectivity.

## 9) Exact User-Facing Areas to Re-test First
1. Availability page buttons (status updates, calendar toggle, promote modal open).
2. Discord link + player GUID link flow in Profile.
3. Telegram/Signal token generation + unlink actions in Profile.
4. Planning Room panel load on Availability page.

## 10) Resume Prompt (copy/paste)
Use this when resuming work:

```text
Load and follow:
1) docs/reports/SHOP_CLOSE_HANDOVER_AVAILABILITY_2026-02-19.md
2) docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md
3) docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md
4) docs/reports/AVAILABILITY_PROMPT_COMPLETION_REPORT_2026-02-19.md
5) docs/workfile.md

Then run service + endpoint sanity checks and continue from any failing UI flow first.
```
