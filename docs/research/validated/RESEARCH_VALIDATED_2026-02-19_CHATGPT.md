# ChatGPT Research Validation Report (2026-02-19)

Source reviewed:

- `chatgptresearch.md` (copied to `docs/research/inbox/RESEARCH_INBOX_2026-02-19_chatgpt.md`)

Validation method:

- Local repo evidence (code/config/docs) first.
- External standards claims validated against primary sources where needed.
- Status values: `verified`, `partially-verified`, `false`, `not-verified-yet`.

## Executive Verdict

- Overall quality: `mixed`
- Main issue: significant baseline drift (repo has evolved beyond several claims in the report).
- Safe to merge: recommendations on dependency/security scanning and runtime hardening.
- Unsafe to merge as facts: statements claiming no CI, no Docker, no linting, no build system.

## Claim Matrix

| Claim ID | Claim (from ChatGPT report) | Status | Evidence | Notes |
| --- | --- | --- | --- | --- |
| C-001 | Slomix is Python 3.11+ with Discord bot + FastAPI + JS frontend | verified | `requirements.txt:2`, `requirements.txt:8`, `website/backend/main.py:1`, `website/index.html:16` | Core stack description is correct. |
| C-002 | Dependencies are pinned in both bot and website requirements | false | `requirements.txt:2`, `website/requirements.txt:2` | Root requirements are pinned (`==`), website requirements use ranges (`>=`). |
| C-003 | CI/CD is partial and only tests run | false | `.github/workflows/tests.yml:14`, `.github/workflows/tests.yml:57`, `.github/workflows/tests.yml:90`, `.github/workflows/tests.yml:100` | CI includes Python lint+tests, JS lint, Docker build, Codecov upload. |
| C-004 | No automated security scanning exists | partially-verified | `.github/workflows/codeql.yml:1`, `.github/workflows/codeql.yml:50`, `.pre-commit-config.yaml:14` | `bandit/pip-audit` absent, but automated CodeQL and detect-secrets are present. |
| C-005 | No container/Docker definitions exist | false | `docker-compose.yml:1`, `docker/Dockerfile.api:1`, `docker/Dockerfile.website:1` | Docker/Compose setup exists and is active in CI build checks. |
| C-006 | No standard lint/format tooling exists | false | `pyproject.toml:49`, `requirements-dev.txt:7`, `.github/workflows/tests.yml:57`, `package.json:11` | Ruff + JS lint exist and run in CI. |
| C-007 | Security baseline includes read-only DB role, CORS, sessions | partially-verified | `website/README.md:16`, `website/.env.example:13`, `website/backend/main.py:85`, `website/backend/main.py:100` | Documented and configurable; runtime enforcement depends on deployed env values. |
| C-008 | Testing uses pytest + pytest-cov and coverage is bot-focused | verified | `requirements.txt:25`, `pytest.ini:22`, `pytest.ini:46`, `.github/workflows/tests.yml:69` | Accurate. |
| C-009 | No formal build system / no Makefile | false | `Makefile:1`, `Makefile:10`, `Makefile:28` | Makefile exists for dev/test/lint workflows. |
| C-010 | No Node/npm tooling | false | `package.json:7`, `package.json:11`, `.github/workflows/tests.yml:84` | Node/npm is used for frontend linting in CI. |
| C-011 | No migrations tool/system exists | partially-verified | `website/migrations/005_date_based_availability.sql:2` | No Alembic/Flyway framework found, but SQL migration scripts do exist. |
| C-012 | Hardcoded CI test DB password concern is real | verified | `.github/workflows/tests.yml:21`, `.github/workflows/tests.yml:65` | Valid finding; should move to secrets/ephemeral creds policy. |
| C-013 | Recommendation to add Bandit + pip-audit is aligned with industry practice | verified | Bandit docs: https://bandit.readthedocs.io/en/latest/ ; pip-audit docs: https://pypa.github.io/pip-audit/ | Recommendation is valid even though current scans already include CodeQL. |
| C-014 | FastAPI production guidance about workers is valid | verified | FastAPI deployment docs: https://fastapi.tiangolo.com/deployment/server-workers/ | Keep context-aware (single worker can still be acceptable per deployment model). |
| C-015 | Tailwind production optimization concern is relevant | verified | `website/index.html:16`; Tailwind docs: https://tailwindcss.com/docs/installation/play-cdn ; https://tailwindcss.com/docs/optimizing-for-production | Current frontend uses Play CDN script; production optimization guidance is valid. |

## High-Confidence Corrections To Apply In Future Mega Prompts

1. Do not assume missing CI/security/containerization; verify current workflows and Docker assets first.
2. Keep recommendation to add dependency audit tooling (`pip-audit`) and Python security lint (`bandit`) as additive controls, not replacements for CodeQL.
3. Keep recommendation to expand coverage beyond `bot` scope.
4. Keep recommendation to tighten CI secrets handling (remove hardcoded test DB password patterns).
5. Treat external AI reports as untrusted until claim matrix validation is complete.

## Suggested Merge Inputs For Next Mega Prompt Version

Use these as validated carry-forward items:

1. Add explicit "baseline drift check" task at start of every audit.
2. Keep dual security-scan model:
   - code scanning (`CodeQL`)
   - dependency/security lint (`pip-audit` + `bandit`) if adopted.
3. Add CI hardening task:
   - replace static CI DB password literals with secrets or generated ephemeral credentials.
4. Add container hardening tasks:
   - non-root runtime user in API image
   - digest pinning policy for base images
   - optional multi-stage build when build complexity grows.

