# Line-By-Line Audit Closed/Open Matrix (Strict)
Date: 2026-02-19
Execution Lock ID: SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19
Mode: full-restart line-by-line + patch pass (security + performance)

Status legend:
- `closed`: issue fixed with code-level evidence
- `mitigated`: risk materially reduced, but residual hardening remains
- `open`: not fixed yet

## Findings Matrix
| ID | Severity | Status | Evidence | Finding | Patch / Current State | Residual Risk / Next Action |
|---|---|---|---|---|---|---|
| RL-001 | Medium | closed | `website/backend/middleware/rate_limit_middleware.py:40`, `website/backend/middleware/rate_limit_middleware.py:62`, `website/backend/middleware/rate_limit_middleware.py:106`, `tests/unit/test_api_middleware.py:79` | In-memory rate-limit buckets could grow unbounded with high-cardinality clients. | Added periodic stale-bucket cleanup, hard cap (`RATE_LIMIT_MAX_TRACKED_KEYS`), and explicit guarded rejection path; added direct unit test coverage for limiter-cap branch. | None in current in-process limiter path. |
| HC-001 | Medium | closed | `website/backend/middleware/http_cache_middleware.py:26`, `website/backend/middleware/http_cache_middleware.py:133`, `website/backend/middleware/http_cache_middleware.py:206`, `tests/unit/test_api_middleware.py:16` | Cache middleware could buffer large JSON bodies without a size guard and skipped cache cycle for streamed FastAPI responses. | Added body-size guardrails plus bounded streamed-body materialization path so ETag MISS/HIT cycle works while preserving BYPASS for unknown-size streams. | None in current middleware path. |
| SSH-001 | High | closed | `bot/services/automation/ssh_monitor.py:484`, `bot/services/automation/ssh_monitor.py:506`, `bot/services/automation/ssh_monitor.py:533` | SSH filename handling allowed traversal/overwrite risk from untrusted filename input. | Added strict filename sanitization allowlist + basename normalization + local path boundary enforcement before SCP download. | None in this path after patch. |
| MET-001 | Medium | closed | `bot/services/automation/metrics_logger.py:73`, `bot/services/automation/metrics_logger.py:151`, `bot/services/automation/metrics_logger.py:157` | Metrics logger created/closed SQLite connection per event causing churn/locks. | Introduced shared persistent connection guarded by async lock and centralized write helper. | Ensure shutdown path calls `close()` where lifecycle teardown exists. |
| VPS-001 | Medium | closed | `vps_scripts/stats_webhook_notify.py:89`, `vps_scripts/stats_webhook_notify.py:136`, `vps_scripts/stats_webhook_notify.py:499` | State file was fsync+replace on every event in watcher path. | Added batched/time-based state flush and forced final flush on shutdown. | Small in-memory window exists before flush by design; acceptable tradeoff for throughput. |
| CSP-001 | High | closed | `website/index.html:7`, `docker/nginx/default.conf:12`, `website/js/inline-actions.js:1`, `website/js/tailwind-config.js:1`, `website/js/lucide-init.js:1` | Missing CSP defense-in-depth for web UI/CDN script sources. | Removed inline handlers/scripts, migrated behavior to external JS modules, and tightened CSP by removing script `'unsafe-inline'`/`'unsafe-eval'` in both document and nginx policy. | No script inline/eval allowances remain in CSP `script-src`. |
| APP-PERF-001 | Medium | closed | `website/js/app.js:663`, `website/js/app.js:720`, `website/js/app.js:743` | Startup fired broad parallel data fan-out before first interaction. | Split critical loads vs deferred loads (`requestIdleCallback` fallback), reducing first-paint pressure. | Monitor slow-client telemetry; move more view-specific fetches to route activation if needed. |
| ADMIN-PERF-001 | Medium | closed | `website/js/admin-panel.js:23`, `website/js/admin-panel.js:2966`, `website/js/admin-panel.js:3036`, `website/js/admin-panel.js:5559` | Admin status refresh repeatedly queried/mutated full DOM tree on each poll. | Added element cache + state diffing and no-op write skips for unchanged status/mode values. | Rebuild cache when future dynamic node insertion behavior changes. |
| REQ-001 | Medium | closed | `requirements.txt:1` | Runtime dependency set included test-only tooling. | Removed pytest/tooling from runtime requirements file. | Keep CI flows on `requirements-dev.txt`; monitor drift between runtime/dev pins. |
| DOCKER-BASE-001 | Medium | closed | `docker/Dockerfile.api:1` | API base image used floating major/minor tag. | Pinned API base image to immutable digest (`python:3.11.10-slim-bookworm@sha256:840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e`). | None in current Docker base-image pinning path. |
| CSRF-001 | High | closed | `website/backend/routers/auth.py:15`, `website/backend/routers/auth.py:167`, `website/backend/routers/api.py:3005`, `website/backend/routers/api.py:3040`, `website/js/auth.js:96` | State-changing auth/player-link routes lacked non-simple request guard. | Added required `X-Requested-With` check server-side and header emission client-side. | Consider full synchronizer token model if browser-only threat model expands. |
| LOG-IP-001 | Medium | closed | `website/backend/middleware/logging_middleware.py:147`, `website/backend/middleware/logging_middleware.py:152`, `website/backend/middleware/logging_middleware.py:205` | Logging middleware previously trusted spoofable forwarded headers. | Trusted-proxy parsing now gates use of `X-Forwarded-For`/`X-Real-IP`. | Keep `RATE_LIMIT_TRUSTED_PROXIES`/proxy list aligned with deploy topology. |
| SESSION-XSS-001 | High | closed | `website/js/sessions.js:120`, `website/js/sessions.js:126`, `website/js/sessions.js:1224`, `website/js/sessions.js:1400` | Session view used unsafe inline interpolation for IDs/handlers. | Added DOM key sanitization, round ID coercion, and JS-string escaping across session toggle/graph handlers. | Continue reducing inline handlers over time toward delegated listeners + strict CSP. |
| SSH-HOSTKEY-001 | High | closed | `bot/automation/ssh_handler.py:39`, `bot/automation/ssh_handler.py:60`, `tools/sync_stats.py:38`, `tools/ssh_sync_and_import.py:42`, `tools/database_backup_system.py:109` | Several SSH paths previously allowed permissive host-key behavior. | Enforced RejectPolicy/system host keys in helpers; bot SSH handler now always enforces strict known_hosts validation and ignores insecure fallback flags. | None in current code path. |

## Totals (High/Medium)
- Closed: 14
- Mitigated: 0
- Open: 0

## Validation Evidence
- `python3 -m py_compile website/backend/middleware/rate_limit_middleware.py website/backend/middleware/http_cache_middleware.py bot/services/automation/ssh_monitor.py bot/services/automation/metrics_logger.py vps_scripts/stats_webhook_notify.py` -> pass.
- `npm run lint:js` -> pass (`JS syntax lint passed (27 files)`).
- `pytest --no-cov tests/unit/test_api_middleware.py tests/unit/auth_router_security_test.py -q` -> `10 passed`.

## Remaining Work (strict)
None in this strict matrix scope.
