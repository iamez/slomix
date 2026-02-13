# Codebase Findings and Restart Runbook (2026-02-12)

## Scope
This report consolidates a parallel multi-agent review of the full repository with focus on:
- bot runtime and parser pipeline
- website auth/API and Greatshot job flow
- database manager and migration safety
- CI/testing confidence

Review date: 2026-02-12.

## Executive Summary
- High severity findings: 10
- Medium severity findings: 3
- Restart readiness: service restart is safe operationally, but restart alone does not mitigate these defects.
- Recommended before next production cycle: fix items F-01, F-02, F-03, F-04 first.

## Findings

## High Severity

### F-01: PostgreSQL import path can be skipped due to config string mismatch
- Evidence: `bot/ultimate_bot.py:1052` checks `self.config.database_type == "postgres"`, while `bot/config.py:52` default is `"postgresql"`.
- Risk: live imports can bypass intended PostgreSQL path and follow fallback behavior unexpectedly.
- Recommendation: normalize value once and compare with `in {"postgres", "postgresql"}`.

### F-02: Webhook-triggered file is marked processed before success
- Evidence: `bot/ultimate_bot.py:3330` adds filename to `processed_files` before download/import completes; `bot/automation/file_tracker.py:137` blocks reprocessing if present.
- Risk: transient failure can permanently skip a file until process restart/manual intervention.
- Recommendation: mark processed only after successful import/publish; remove marker on failure paths.

### F-03: OAuth callback lacks CSRF state validation and trusts Host header for redirect
- Evidence: `website/backend/routers/auth.py:24` login has no `state`; `website/backend/routers/auth.py:110` builds redirect from request `host`.
- Risk: CSRF/replay risk and host-header-driven open redirect behavior.
- Recommendation: generate/store/verify OAuth `state`; redirect only to canonical configured frontend origin.

### F-04: Greatshot render worker can crash when clip already exists
- Evidence: `website/backend/services/greatshot_jobs.py:406` sets `clip_demo_path` only in `if clip_missing`; later used unconditionally at `website/backend/services/greatshot_jobs.py:439`.
- Risk: `UnboundLocalError` for existing clips, render job marked failed.
- Recommendation: initialize `clip_demo_path` from existing locked path in the `else` branch.

### F-05: `FOR UPDATE` lock is ineffective without transaction scope
- Evidence: lock query at `website/backend/services/greatshot_jobs.py:399`; `bot/core/database_adapter.py:209` uses one-shot `fetch_one` connection context without surrounding transaction.
- Risk: concurrent workers can still race to cut/update same highlight.
- Recommendation: run lock/read/write in one explicit DB transaction and keep lock until update completes.

### F-06: Greatshot analysis timeout does not stop underlying thread work
- Evidence: `website/backend/services/greatshot_jobs.py:187` wraps `asyncio.to_thread(...)` in `wait_for`.
- Risk: timed-out tasks can continue running in background, causing resource leaks and duplicate work.
- Recommendation: move job execution to cancellable subprocess/process pool or implement cooperative cancellation signal.

### F-07: Backup subprocess environment can break `pg_dump` resolution
- Evidence: `postgresql_database_manager.py:310` passes `env={'PGPASSWORD': ...}`.
- Risk: missing `PATH` in child process can cause `pg_dump` lookup failures.
- Recommendation: inherit `os.environ.copy()` and inject `PGPASSWORD`.

### F-08: Full-table wipe is not transactional
- Evidence: `postgresql_database_manager.py:1231` iterates table deletes without `conn.transaction()`.
- Risk: partial wipe if one delete fails, leaving inconsistent state.
- Recommendation: wrap wipe in one transaction or use transactional `TRUNCATE ... CASCADE` strategy.

### F-09: CI runs a narrow subset of tests while reporting a broad total
- Evidence: workflow only runs three targets at `/.github/workflows/tests.yml:72`, `/.github/workflows/tests.yml:76`, `/.github/workflows/tests.yml:86`; summary claims total coverage at `/.github/workflows/tests.yml:100`.
- Risk: most unit modules are un-gated in CI and regressions can merge undetected.
- Recommendation: run `pytest tests/unit` (or full `pytest tests`) in CI and keep summary derived from actual run output.

### F-10: Security test file mostly validates synthetic constants, not production validators
- Evidence: `tests/security/test_security_validation.py:21` onward uses local regex/lists without importing runtime validation paths.
- Risk: test pass does not prove actual webhook/filename/rate-limit logic is safe.
- Recommendation: replace with tests that import and execute production validation functions/endpoints.

## Medium Severity

### F-11: Session cookie middleware uses default security flags
- Evidence: `website/backend/main.py:87` uses `SessionMiddleware` with only `secret_key`.
- Risk: weaker cookie guarantees in production deployments.
- Recommendation: explicitly set `https_only=True`, `same_site` policy, and cookie naming/domain settings for production.

### F-12: Migration strategy is split between hardcoded Python migrations and standalone SQL scripts
- Evidence: hardcoded migration chain starts at `postgresql_database_manager.py:984`; separate SQL files exist under `migrations/`.
- Risk: drift and uncertain single source of truth for schema evolution.
- Recommendation: enforce one migration runner with version table and apply-once semantics.

### F-13: Integration/E2E/performance suites are placeholders
- Evidence: `tests/integration/__init__.py`, `tests/e2e/__init__.py`, `tests/performance/__init__.py` are empty files.
- Risk: cross-component regressions and performance issues are not automatically detected.
- Recommendation: add at least one critical-path test per layer (ingest -> DB -> API -> render).

## Restart Runbook (Documented For This Host)

## Context
- Current detected systemd units on this host:
- `etlegacy-bot.service`
- `etlegacy-web.service`
- Note: other docs also mention `etlegacy-website.service`; verify actual unit names before restart.

## Pre-Restart Checks
1. Verify current unit names:
```bash
systemctl list-unit-files | rg 'etlegacy-(bot|web|website)'
```
2. Confirm services are currently healthy enough to restart:
```bash
sudo systemctl status etlegacy-bot --no-pager -l
sudo systemctl status etlegacy-web --no-pager -l
```
3. Record recent logs for comparison after restart:
```bash
sudo journalctl -u etlegacy-bot -n 80 --no-pager
sudo journalctl -u etlegacy-web -n 80 --no-pager
```

## Restart Steps
1. Restart website backend first:
```bash
sudo systemctl restart etlegacy-web
```
2. Restart Discord bot second:
```bash
sudo systemctl restart etlegacy-bot
```

If your host uses `etlegacy-website` instead of `etlegacy-web`, replace the website unit name accordingly.

## Post-Restart Validation
1. Check unit state:
```bash
sudo systemctl is-active etlegacy-web
sudo systemctl is-active etlegacy-bot
```
2. Check startup logs for errors:
```bash
sudo journalctl -u etlegacy-web -n 120 --no-pager
sudo journalctl -u etlegacy-bot -n 120 --no-pager
```
3. Basic HTTP smoke check:
```bash
curl -I http://127.0.0.1:8000/
```
4. Confirm bot process is present:
```bash
ps aux | rg 'bot/ultimate_bot.py' | rg -v rg
```

## Prioritized Remediation Plan
1. Patch F-01 and F-02 (data ingestion correctness and retry safety).
2. Patch F-03 and F-11 (auth/session security baseline).
3. Patch F-04, F-05, F-06 (Greatshot render/worker correctness and concurrency).
4. Patch F-07 and F-08 (backup/wipe safety in DB manager).
5. Expand CI/test coverage to close F-09, F-10, F-13.

## Patch Status Update (2026-02-12)
- F-01 patched in `bot/ultimate_bot.py` by normalizing `database_type` and accepting both `postgres`/`postgresql`.
- F-02 patched in `bot/ultimate_bot.py` for both webhook stats paths by rolling back in-memory processed markers on failure/exception so retries remain possible.
- F-03 patched in `website/backend/routers/auth.py` by adding OAuth `state` generation/validation and replacing host-header-based redirects with canonical configured frontend origin resolution.
- F-04 patched in `website/backend/services/greatshot_jobs.py` by guaranteeing `clip_demo_path` is initialized for both clip-existing and clip-missing branches before render execution.
- Runtime verification pending: service restart + live traffic checks (WS1 gate evidence still required for closeout).
