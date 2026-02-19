# Restart Handover Report (Availability / Linking / Promote)

Date: 2026-02-19  
Repo: `iamez/slomix`  
Branch: `feat/availability-multichannel-notifications`

## Why restart is needed
- Sub-agent spawning is blocked in this session by tool thread cap:
  - error: `agent thread limit reached (max 6)`
- This appears to be stale/bugged agent-slot state, not a code issue.
- We should restart/reset session, then continue from this exact handover.

## Canonical context to load first after restart
1. `docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md`
2. `docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md` (this file)
3. `docs/workfile.md`

## Current implementation state

### Stage 0 (boot/runbook)
- In place:
  - `Makefile` with `dev`, `dev-local`, `prod`
  - `scripts/dev_up.sh`, `scripts/prod_up.sh`
  - `/health` endpoint with DB check
  - `docs/RUNBOOK.md`
- Additional hardening in this continuation:
  - env integer parsing now tolerates inline comments (`PORT=7000  # note`) in bot + web startup paths.
  - `scripts/dev_up.sh` now preserves explicit CLI/session overrides for `BOT_STARTUP_VALIDATE_ONLY` and `DISCORD_BOT_TOKEN` instead of letting `.env` overwrite them.
- Live DB outage remediation completed:
  - Re-applied migrations `005/006/007` idempotently on local PostgreSQL.
  - Restored grants for role `website_app` on Availability/Promotions/Planning tables and sequences.
  - Added default privileges so future tables/sequences created by `etlegacy_user` remain readable/writable by `website_app`.
  - Added migration pair to codify grant policy:
    - `website/migrations/008_website_app_availability_grants.sql`
    - `website/migrations/008_website_app_availability_grants_down.sql`

### Stage 1 (Availability UX)
- In place:
  - Today/Tomorrow hero
  - Current queue from today LOOKING
  - Upcoming(3) digest
  - calendar collapsed by default with Open/Close toggle
  - Link Discord CTA in aggregate-only message

### Stage 2 (Discord/Player linking + gating)
- In place:
  - OAuth + PKCE + state validation and redirect allowlist patterns
  - profile/link status and link/unlink routes
  - submission gating on linked state

### Stage 3 (Promote campaigns)
- In place:
  - preview + create campaign endpoints
  - scheduled jobs (`send_reminder_2045`, `send_start_2100`, `voice_check_2100`)
  - idempotent delivery via `notifications_ledger`
  - opt-in preferences and channel selection flow

### Stage 4 (ready-check runtime behavior)
- Newly added strong unit coverage (this continuation):
  - `tests/unit/test_availability_poll_promotion_runtime.py`
  - covers:
    - promotion job processing status transitions
    - retry then fail behavior at max attempts
    - voice follow-up targeting + summary post + game-server note + quiet-hours skip
- Remaining gap:
  - true live-like end-to-end runtime verification in running stack with real Discord connectivity (scheduler/follow-up).
  - In this sandbox, localhost TCP health probes fail (`curl: (7)`), so startup readiness must be validated via logs + `SKIP_HEALTHCHECK=1`.

### Stage 5
- Planning Room MVP scaffolding already present from prior continuation.

### Stage 6 (hardening/docs/tests)
- In progress:
  - test coverage significantly expanded
  - docs compacted
- Remaining:
  - final docs consolidation + final PR-style packaging and commit slicing.

## Changes made in this continuation

### New files
- `tests/unit/test_availability_promotions_router.py`
- `tests/unit/test_availability_poll_promotion_runtime.py`
- `tests/unit/test_env_parsing.py`
- `website/backend/env_utils.py`
- `website/migrations/008_website_app_availability_grants.sql`
- `website/migrations/008_website_app_availability_grants_down.sql`
- `docs/reports/stage4_live_verification.sh`
- `docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md`

### Updated files
- `website/backend/routers/availability.py`
  - fixed quiet-hours validation to return HTTP 400 on invalid HH:MM instead of uncaught 500.
- `bot/config.py`
  - `_get_config` now sanitizes inline-comment env values before downstream numeric parsing.
- `website/backend/main.py`
- `website/backend/routers/api.py`
- `website/backend/middleware/http_cache_middleware.py`
- `website/backend/middleware/rate_limit_middleware.py`
  - switched startup/runtime integer env parsing to shared robust helper.
- `scripts/dev_up.sh`
  - preserve explicit runtime overrides for `BOT_STARTUP_VALIDATE_ONLY`/`DISCORD_BOT_TOKEN` so validate-only mode can be forced safely.
- `docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md`
  - appended progress + test outcomes + startup/sandbox/runtime notes.
- `docs/AVAILABILITY_SYSTEM.md`
  - migration list updated to include `008` and live PostgreSQL note for `007/008`.

## Test evidence (latest)

### Promotions + availability + linking + notifier + external command suite
Command:
```bash
pytest -q \
  tests/unit/test_availability_promotions_router.py \
  tests/unit/test_availability_router.py \
  tests/unit/test_auth_linking_flow.py \
  tests/unit/test_availability_notifier_promotion_idempotency.py \
  tests/unit/test_availability_poll_external_commands.py
```
Result:
- `24 passed`

### Stage 4 runtime-focused suite
Command:
```bash
pytest -q \
  tests/unit/test_availability_poll_promotion_runtime.py \
  tests/unit/test_availability_promotions_router.py \
  tests/unit/test_availability_notifier_promotion_idempotency.py \
  tests/unit/test_availability_poll_external_commands.py
```
Result:
- `13 passed`

### Stage 4 + env hardening suite
Command:
```bash
pytest -q \
  tests/unit/test_availability_poll_promotion_runtime.py \
  tests/unit/test_availability_promotions_router.py \
  tests/unit/test_availability_notifier_promotion_idempotency.py \
  tests/unit/test_availability_poll_external_commands.py \
  tests/unit/test_env_parsing.py
```
Result:
- `17 passed`

### Startup smoke evidence (sandbox)
Commands:
```bash
SKIP_INSTALL=1 SKIP_HEALTHCHECK=1 BOT_STARTUP_VALIDATE_ONLY=true make dev-local
```
Observed:
- bot config-validation path is now explicitly enforceable via override (no forced full bot startup from `.env`).
- web startup reaches ready state in `logs/web.log`.
- localhost TCP probes are sandbox-limited (`curl: (7)`), so `/health` can’t be validated via loopback in this environment.

Notes:
- `ruff` unavailable in this environment (`ruff: command not found`).

### DB outage fix evidence (live/local postgres role)
Checks executed as `website_app` after grant remediation:
- visibility:
  - `availability_entries`
  - `availability_promotion_campaigns`
  - `planning_sessions`
- privileges:
  - `SELECT`/`INSERT`/`UPDATE` on `availability_entries`, `availability_promotion_campaigns`, `planning_sessions` => all `true`.

## Working tree checkpoint (target files)
- `M website/backend/routers/availability.py`
- `M bot/config.py`
- `!! scripts/dev_up.sh` (ignored file; local startup helper change)
- `M website/backend/main.py`
- `M website/backend/routers/api.py`
- `M website/backend/middleware/http_cache_middleware.py`
- `M website/backend/middleware/rate_limit_middleware.py`
- `M docs/AVAILABILITY_SYSTEM.md`
- `?? tests/unit/test_availability_promotions_router.py`
- `?? tests/unit/test_availability_poll_promotion_runtime.py`
- `?? tests/unit/test_env_parsing.py`
- `?? website/backend/env_utils.py`
- `?? website/migrations/008_website_app_availability_grants.sql`
- `?? website/migrations/008_website_app_availability_grants_down.sql`
- `?? docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md`
- `?? docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md`
- `?? docs/reports/stage4_live_verification.sh`

## Commit slicing plan (Stage 6 packaging)

| Slice | Scope | Files | Verification | Notes |
| --- | --- | --- | --- | --- |
| A | Startup/env parsing hardening + live evidence helper | `bot/config.py`, `website/backend/env_utils.py`, `website/backend/main.py`, `website/backend/routers/api.py`, `website/backend/middleware/http_cache_middleware.py`, `website/backend/middleware/rate_limit_middleware.py`, `docs/reports/stage4_live_verification.sh` | `pytest -q tests/unit/test_env_parsing.py` + targeted promotion runtime suite | `scripts/dev_up.sh` is ignored in this worktree; keep as local helper unless `.gitignore` policy changes |
| B | Promote/ready-check runtime validation tests | `tests/unit/test_availability_promotions_router.py`, `tests/unit/test_availability_poll_promotion_runtime.py`, `tests/unit/test_availability_notifier_promotion_idempotency.py`, `tests/unit/test_availability_poll_external_commands.py`, `tests/unit/test_env_parsing.py`, `website/backend/routers/availability.py` | `pytest -q tests/unit/test_availability_poll_promotion_runtime.py tests/unit/test_availability_promotions_router.py tests/unit/test_availability_notifier_promotion_idempotency.py tests/unit/test_availability_poll_external_commands.py tests/unit/test_env_parsing.py` | Keep API behavior/security/idempotency assertions grouped in this slice |
| C | Context + handover docs finalization | `docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md`, `docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md` | markdown review + command references validated | Includes live-host Stage 4 checklist and sandbox limitation notes |

Recommended PR narrative order:
1. Env/startup hardening
2. Stage 4 runtime + promotions regression coverage
3. Final docs/handover packaging

Suggested commit commands:

```bash
# Slice A
git add \
  bot/config.py \
  website/backend/env_utils.py \
  website/backend/main.py \
  website/backend/routers/api.py \
  website/backend/middleware/http_cache_middleware.py \
  website/backend/middleware/rate_limit_middleware.py \
  docs/reports/stage4_live_verification.sh
git commit -m "fix(config): tolerate inline-comment env ints for bot/web startup"

# Slice B
git add \
  website/backend/routers/availability.py \
  tests/unit/test_availability_promotions_router.py \
  tests/unit/test_availability_poll_promotion_runtime.py \
  tests/unit/test_availability_notifier_promotion_idempotency.py \
  tests/unit/test_availability_poll_external_commands.py \
  tests/unit/test_env_parsing.py
git commit -m "test(availability): expand promotion runtime, idempotency, and env parsing coverage"

# Slice C
git add \
  docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md \
  docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md
git commit -m "docs(availability): add live Stage 4 verification checklist and handover slicing plan"
```

## Stage 4 live host command bundle

```bash
# 0) Repo + branch
cd /home/samba/share/slomix_discord
git checkout feat/availability-multichannel-notifications

# 1) Preflight regression gate
pytest -q \
  tests/unit/test_availability_poll_promotion_runtime.py \
  tests/unit/test_availability_promotions_router.py \
  tests/unit/test_availability_notifier_promotion_idempotency.py \
  tests/unit/test_availability_poll_external_commands.py \
  tests/unit/test_env_parsing.py

# 2) Start live-like runtime (non-sandbox host)
SKIP_INSTALL=1 make dev-local

# 3) Verify health (from same host)
curl -fsS http://127.0.0.1:7000/health

# 4) Trigger campaign in UI as linked promoter/admin
#    Open Availability page, run Promote modal with desired status filters and dry_run=false.
#    Capture returned campaign_id from browser network response:
#    POST /api/availability/promotions/campaigns

# 5) DB evidence using helper script
docs/reports/stage4_live_verification.sh latest
docs/reports/stage4_live_verification.sh campaign <campaign_id>
```

Expected Stage 4 signoff evidence:
- exactly one job each for `send_reminder_2045`, `send_start_2100`, `voice_check_2100`
- no duplicate delivery rows for same user/channel/event on rerun/restart
- voice follow-up targets missing players only, respects quiet-hours, and posts summary
- optional game-server note appears only when telemetry indicates in-server-but-not-voice mismatch

## Resume plan after restart (with sub-agents)
1. Spawn explorer agent:
   - verify non-sandbox/live Discord runtime prerequisites for final Stage 4 E2E.
2. Spawn worker agent:
   - execute live-like promote campaign verification checklist on host with real Discord connectivity.
3. Spawn docs worker:
   - finalize docs for Promote + linking + sandbox-vs-live verification split.
4. Run final verification:
   - targeted tests above (including env parsing)
   - startup smoke (`SKIP_HEALTHCHECK=1 make dev-local` in sandbox)
   - full live `/health` + scheduler verification in non-sandbox host env
5. Prepare commit slicing and PR summary.

## Immediate first commands after restart
```bash
cd /home/samba/share/slomix_discord
git checkout feat/availability-multichannel-notifications
git status --short
pytest -q tests/unit/test_availability_poll_promotion_runtime.py tests/unit/test_availability_promotions_router.py
```

## Continuation instruction
Continue exactly where we left off:
- keep current branch,
- keep current modifications,
- use sub-agents once session is reset,
- prioritize Stage 4 live-like verification and final docs/PR packaging.
