# Whole-Codebase Audit — 2026-06-15

**Method:** Mandelbrot RCA v2 (classify C/H/M/L → 5 Whys → fault-tree → Ishikawa →
remediate) + automated scanners (bandit, pip-audit, detect-secrets, mypy, ruff
full-repo, semgrep) in a throwaway `.audit-venv`. **Hard rule honoured:
"prove it / no false positives"** — every HIGH/CRITICAL was verified against the live
code/DB before reporting; unprovable scanner hits are listed under *False positives*.

**Scope:** whole project from inception → S7 (bot, website backend+frontend, proximity,
greatshot, Lua, DB, tests, docs, CI). Ground truth: `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md`,
`docs/SAFETY_VALIDATION_SYSTEMS.md`, `tools/schema_postgresql.sql`, the code/DB.

> Note: a planned 5-agent parallel fan-out hit a session usage limit mid-run, so
> Phase-1 verification was completed directly (grep/psql/read) against the Phase-0
> scanner signal. Findings below are individually proven.

---

## Phase-0 scanner baseline (raw signal)

| Scanner | Result |
|---------|--------|
| **pip-audit** | **6 dependencies with CVEs** (see H1) — concrete, actionable |
| bandit | 338 results: 5 HIGH (B507 paramiko AutoAddPolicy in `tools/`), 291 MEDIUM (268 = B608 f-string SQL → **FP class**), 42 LOW |
| detect-secrets | 64 flags / 35 files — almost all docs / `.secrets.baseline` / documented dev placeholders (see FP) |
| ruff (full repo) | 1158 issues **outside CI scope** (CI lints only `bot/`+`website/backend/`): 927 SLF001 (tests/scripts), ~175 DTZ (naive datetime), small real F401/I001 |
| mypy | not runnable as-is (package-base error: missing `__init__` / `--explicit-package-bases`) — not enforced |
| RCA greps | 42 `except…: pass`, 27 `create_task(`, **0** `shell=True`, **0** `eval/exec` |

---

## CRITICAL — none found

No data-loss, RCE, auth-bypass, or money-conservation class defect proven. (The
parimutuel atomicity/payout class was already fixed in S4 review.)

## HIGH (verified)

### H1 — Dependency CVEs (pip-audit, confirmed real)
`requirements.txt` pins vulnerable versions:

| Package | Pinned | CVE | Fix | Remediation risk |
|---------|--------|-----|-----|------------------|
| Pillow | 12.1.1 | 5× (CVE-2026-40192/42309/42310/42311, PYSEC-2026-165) | **12.2.0** | low — safe bump |
| python-dotenv | 1.2.1 | CVE-2026-28684 | **1.2.2** | low — safe patch |
| pytest (dev) | 9.0.2 | CVE-2025-71176 | **9.0.3** | low — dev only |
| python-multipart | 0.0.22 | CVE-2026-40347, CVE-2026-42561 | 0.0.27 | **med** — FastAPI 0.133.1 dep graph; test before bump |
| starlette | 0.52.1 | PYSEC-2026-161 | 1.0.1 | **high** — MAJOR; pinned transitively by fastapi==0.133.1; needs FastAPI upgrade |
| paramiko | 4.0.0 | CVE-2026-44405 | (no fix yet) | monitor |

**5 Whys:** no `pip-audit`/dependabot in CI → CVEs land silently. **Ishikawa: Process/Dependencies.**
**Fix (this PR):** bump the 3 low-risk (Pillow, python-dotenv, pytest). **Backlog:** multipart/starlette via a FastAPI-version bump (compat test); track paramiko.

### H2 — Upload + delete endpoints lack CSRF protection
`website/backend/routers/uploads.py`: `upload_file` (POST `/uploads`, L80) and
`delete_upload` (DELETE `/uploads/{id}`, L476) authenticate via `_require_user(request)`
but do **NOT** call `require_ajax_csrf_header` — unlike every S2+ write endpoint. The
frontend (`website/js/uploads.js`) sends them via raw `XMLHttpRequest` POST (L266) and
`fetch` DELETE (L796) **without** `X-Requested-With`, so a cross-site request could
upload or delete on behalf of a logged-in user.
**Ishikawa: Code (pre-S2 endpoint not retrofitted).**
**Fix (this PR, 2-part — must ship together or uploads break):** add
`X-Requested-With: XMLHttpRequest` to the xhr POST + the DELETE fetch in `uploads.js`,
AND add `require_ajax_csrf_header(request)` to both backend handlers.

## MEDIUM (verified)

- **M1 — CI security/quality gaps.** CI has no `pip-audit` (→ H1 went uncaught), no
  `bandit`, no `mypy`; ruff lints only `bot/`+`website/backend/` (1158 issues in
  `scripts/`,`tools/`,`proximity/`,`greatshot/` unchecked). *Fix: add a `pip-audit`
  (or dependabot) CI step; optionally widen ruff. Backlog.*
- **M2 — paramiko `AutoAddPolicy`** in 4 dev/ops tools (`tools/migrate_from_samba.py:53,60`,
  `verify_db_sync.py:27`, `vm_ssh.py:24`, `sync_from_samba.py:95`) — trusts unknown host
  keys (MITM on first connect). Lower exploitability: internal ops tools to known hosts,
  not in the prod bot/web path; several sibling tools already use `RejectPolicy`. *Fix:
  switch to `RejectPolicy` + known_hosts, or document as accepted ops risk. Backlog.*
- **M3 — Docs drift vs ground truth.** `docs/CLAUDE.md` (and root `CLAUDE.md`) still say
  "90 tables" (real **101**), Lua webhook "v1.7.0" (real **v1.7.1**), "2,989 tests"
  (real ~3,260+). `docs/KNOWN_ISSUES.md` lists items resolved since. *Fix: refresh
  (mirror the README #393 pass). Backlog.*
- **M4 — GitHub Actions pinning / container hardening** — verify actions are SHA-pinned
  vs mutable `@vN` tags; Dockerfile base/user hardening. *Backlog (see
  `docs/AUDIT_IMPLEMENTATION_PLAN_2026-02-19.md` IMP items).*

## LOW (verified, backlog)

- **L1** — 1158 ruff issues outside CI scope (mostly SLF001 in tests/scripts = style;
  ~175 DTZ naive-datetime, many intentional wall-clock). Low risk; widen CI gradually.
- **L2** — 42 `except…: pass` + 27 `create_task` — sampled; most are best-effort
  enrichment (digest, optional cards) with logging. A deeper per-site RCA pass is backlog;
  no proven data-loss instance found in the sample.
- **L3** — mypy not enforceable without `--explicit-package-bases` + `__init__` fixes.

---

## False positives / non-issues ruled out (prove-or-drop)

- **f-string SQL (bandit B608 ×268)** — **FP class.** Verified sites use
  `IN ({placeholders})` with `?`-bound `tuple(...)` params (e.g.
  `player_formatter.py:151`) or the `ProximityQueryBuilder` (literal `where_sql` + bound
  `params`, `proximity_helpers.py`). No user input is concatenated into SQL. Matches the
  documented B2-audit stance.
- **detect-secrets ×64** — almost all in `docs/`, `.secrets.baseline`, or documented dev
  placeholders (`etlegacy_secure_2025` is the published dev password in `.env.example`/
  CLAUDE.md). No real production secret proven leaked; `.env` is gitignored.
- **availability `/preferences` "missing CSRF"** — **FP.** It's a compatibility alias that
  delegates to `upsert_settings`, which **does** call `require_ajax_csrf_header`.
- **`shell=True` / `eval` / `exec`** — **0** in source (no shell-injection / dynamic-exec surface).

---

## Quantitative baseline (before)

- Python ~270k LOC (incl. tooling); JS (legacy, production) ~25k; React/TS ~42k; Lua ~45k.
- God files: `proximity/parser/parser.py` (~4042), `postgresql_database_manager.py` (~3198),
  `bot/ultimate_bot.py` (~2124), `sessions_router.py` (~1929), `availability.py` (~1600).
- Tests: ~3,260 collected. CI: ruff(8 sets)/pytest/JS-lint/docker/CodeQL/Codacy green.
- DB: 101 tables; schema file matches live (verified during S6 audit).

## Remediation plan

**This PR (audit/2026-06-remediation) — verified HIGH + safe wins, bundled:**
1. H2 — uploads CSRF (frontend header + backend check).
2. H1 (safe subset) — bump Pillow→12.2.0, python-dotenv→1.2.2, pytest→9.0.3.

**Owner-gated backlog (needs decisions / risk):** H1 multipart+starlette (FastAPI upgrade +
compat test), paramiko (await fix), M1 CI pip-audit step, M2 AutoAddPolicy policy, M3 docs
refresh, M4 action pinning, L1–L3.
