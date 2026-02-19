# Line-By-Line Audit + Patch Report
Date: 2026-02-19  
Mode: Full-restart line-by-line audit (security + performance hardening)

## Scope audited
- `bot/`
- `website/backend/`
- `website/js/`
- `proximity/`
- `tools/`, `vps_scripts/`
- CI/infra surfaces (`.github/workflows/`, `docker/`, compose/env templates)

## Fixed (this pass)
### High / security
- Blocked path traversal and unsafe filenames in SSH download path:
  - `bot/automation/ssh_handler.py`
  - `bot/services/automation/ws_client.py`
- Added secure-by-default WebSocket scheme (`wss`) config path:
  - `bot/config.py`
- Fixed cross-user Greatshot artifact access in crossref endpoint:
  - `website/backend/routers/greatshot.py`
- Removed GET logout CSRF vector by moving logout to POST:
  - `website/backend/routers/auth.py`
  - `website/js/auth.js`
  - `tests/unit/auth_router_security_test.py`
- Escaped unsafe crossref rendering fields and removed inline event-injection vector:
  - `website/js/greatshot.js`
  - `website/js/player-profile.js`
- Enforced SSH host-key verification defaults in sync/backup scripts:
  - `tools/ssh_sync_and_import.py`
  - `tools/database_backup_system.py`
- Hardened Docker/edge exposure defaults and metrics route:
  - `docker-compose.yml`
  - `docker/nginx/default.conf`
  - `.dockerignore`

### Medium / performance + reliability
- Fixed temp file cleanup leak in map upload flow:
  - `bot/cogs/server_control.py`
- Reduced redundant DB work in player listing pagination:
  - `bot/cogs/link_cog.py`
- Capped expensive topshots scan patterns:
  - `website/backend/routers/greatshot_topshots.py`
- Added lifecycle-aware polling stop/start to prevent background timer waste:
  - `website/js/admin-panel.js`
  - `website/js/live-status.js`
- Tightened diagnostic endpoint limits:
  - `website/backend/routers/api.py`
- Bounded support-uptime sampling cost for long tracks:
  - `proximity/parser/parser.py`
- Made VPS webhook state writes atomic:
  - `vps_scripts/stats_webhook_notify.py`
- Rebuilt broken sync script into a working, guarded implementation:
  - `tools/sync_stats.py`

### CI / supply-chain hardening
- Removed dependency-install error swallowing in CodeQL job:
  - `.github/workflows/codeql.yml`
- Made Codecov upload failures fail CI:
  - `.github/workflows/tests.yml`
- Updated API base image pinning strategy to latest patch line:
  - `docker/Dockerfile.api`
- Switched env template cache default to Redis for production posture:
  - `.env.example`
  - `website/.env.example`

## Validation run
- Python syntax compile for modified Python files:
  - `python3 -m py_compile ...` (passed)
- JS lint:
  - `npm run lint:js` (passed)
- Targeted tests:
  - `pytest tests/unit/test_api_middleware.py tests/unit/test_greatshot_crossref.py -q`
  - Result: `4 passed, 2 skipped` (skip reason: missing FastAPI TestClient deps)
- Auth router security test:
  - `pytest tests/unit/auth_router_security_test.py -q`
  - Skipped in this environment due missing `httpx`

## Remaining gaps (not fully closed yet)
- Some hardening findings exist in previously untracked/new infra and ops files that are outside tracked baseline.
- Full repo-wide dependency CVE scan remains incomplete in this environment due network/DNS restrictions during advisory fetch.
- Additional deep pass can still be run for low-severity/perf micro-optimizations and broader regression coverage.
