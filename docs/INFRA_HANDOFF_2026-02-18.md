# Infra Handoff - 2026-02-18

## Scope Completed in This Lane

This lane implemented production-foundation infrastructure and middleware work:

- Local reproducible stack:
  - `docker-compose.yml`
  - `docker/Dockerfile.api`
  - `docker/Dockerfile.website`
  - `docker/nginx/default.conf`
  - `.dockerignore`
  - `Makefile`
  - `monitoring/prometheus.yml`
- CI/release foundation:
  - `.github/workflows/tests.yml`
  - `.github/workflows/release.yml`
  - `.github/workflows/publish-images.yml`
  - `.release-please-config.json`
  - `.release-please-manifest.json`
  - `CHANGELOG.md`
- Repo governance/security:
  - `LICENSE`
  - `SECURITY.md`
  - `CODE_OF_CONDUCT.md`
  - `CONTRIBUTING.md`
  - `.github/ISSUE_TEMPLATE/*`
  - `.github/pull_request_template.md`
- Backend performance/observability middleware:
  - `website/backend/services/http_cache_backend.py`
  - `website/backend/middleware/http_cache_middleware.py`
  - `website/backend/middleware/rate_limit_middleware.py`
  - `website/backend/metrics.py`
  - `website/backend/main.py` wiring
  - `website/backend/middleware/__init__.py`
- Frontend fetch/poll behavior:
  - `website/js/utils.js` (SWR-style cache + request dedupe)
  - `website/js/live-status.js` (visibility-aware polling)
  - `website/js/app.js`
- Config/docs updates:
  - `.env.example`
  - `website/.env.example`
  - `pyproject.toml`
  - `requirements-dev.txt`
  - `.nvmrc`
  - `README.md`
- New tests:
  - `tests/unit/test_api_middleware.py`

## Known Environment Constraints During Validation

- `ruff` not installed locally (`ruff: command not found`).
- `docker` not installed locally (`docker: command not found`), so compose rendering/build was not locally verified.
- `tests/unit/test_api_middleware.py` uses `TestClient`; when `httpx` is missing, tests are skipped by design.

## Observed Multi-Agent Churn Risk

Repo had concurrent edits from multiple Codex processes during this lane.  
Before merging infra work, re-check final content of:

- `requirements.txt`
- `.github/workflows/tests.yml`
- `website/backend/main.py`
- `README.md`

## Required Follow-Ups for Next Agent

1. Dependency finalization
- Decide final policy for `requirements.txt` vs `requirements-dev.txt`.
- Keep runtime-only deps in `requirements.txt` and test/lint deps in `requirements-dev.txt`.
- Ensure CI installs dev deps consistently.

2. CI hardening
- Pin all third-party GitHub Actions to commit SHAs.
- Add minimal `permissions` in every workflow job.
- Ensure release workflow updates the canonical changelog path (decide root `CHANGELOG.md` vs `docs/CHANGELOG.md` and keep one source of truth).

3. Docker/runtime verification
- Run:
  - `docker compose config`
  - `docker compose build api website`
  - `docker compose up --build`
- Verify:
  - Website at `http://localhost:8000`
  - API at `http://localhost:8001/api/status`
  - Metrics at `/metrics` (when enabled)

### Container Digest Pinning Policy (Added 2026-02-19)

- Local/dev compose may keep human-readable tags for ergonomics.
- CI and production release manifests must resolve and deploy immutable image digests (`image@sha256:...`).
- Base image updates must be explicit:
  - refresh digest pins on a scheduled cadence (at least monthly),
  - include CVE/security note in the PR description,
  - re-run CI build/tests before promotion.
- Do not merge production deployment changes that switch from digest pinning back to mutable tags.

4. Cache and rate-limit policy review
- Confirm cacheable endpoint allowlist in `website/backend/middleware/http_cache_middleware.py`.
- Confirm TTL defaults:
  - live endpoints: `15s`
  - leaderboard/aggregates: `300s`
  - default: `120s`
- Confirm rate limits in `website/backend/middleware/rate_limit_middleware.py` are acceptable for production traffic.

5. Security completion (still open from original objective)
- CSRF protection for state-changing endpoints.
- Production CORS allowlist validation.
- Explicit TLS reverse-proxy guidance in deployment docs.

6. Observability completion (still open from original objective)
- Add dashboard provisioning for Grafana (JSON dashboards + datasource provisioning).
- Add alert rules and Discord alert route for threshold breaches.

## Acceptance Checklist for Infra Merge

- [ ] `pytest tests/ -v --tb=short` passes in CI.
- [ ] JS lint step passes in CI.
- [ ] Docker build job passes in CI.
- [ ] `make dev` brings up healthy stack with docs-accurate ports.
- [ ] Release workflow creates semver PR/tag flow from Conventional Commits.
- [ ] No duplicate/conflicting changelog files remain unresolved.

## End-of-Day Closeout (2026-02-18)

Final stabilization work focused on PR `#37` (`fix/codebase-review-findings` -> `main`):

1. Triaged failing checks in parallel (lint, tests, CodeQL) with sub-agents and run-log verification.
2. Confirmed/validated landed fixes for:
   - Ruff lint violations in bot modules.
   - PostgreSQL adapter and schema/test compatibility regressions.
   - Greatshot crossref test-double compatibility.
3. Applied the final blocker fix:
   - `.github/workflows/codeql.yml`
   - `github/codeql-action/init@v3` -> `@v4`
   - `github/codeql-action/analyze@v3` -> `@v4`
4. Pushed commit `7ab90da` (`fix(ci): migrate CodeQL action to v4`).
5. Re-verified checks and reached green/mergeable state.

Result: PR `#37` was merged to `main` successfully.
