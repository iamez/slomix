# M4 — website/venv drift: recommended upgrade order (2026-07-29)

Task M4 from `docs/TASKS_FOR_SONNET_2026-07-29.md`. This is analysis only —
**no packages are installed by this document**. The actual `pip install` on
the running `website/venv` is owner-gated (installing all pins at once on a
running service is not obviously safe, `fastapi` especially).

## Measured (2026-07-29)

```bash
website/venv/bin/python scripts/check_env.py --no-env --requirements website/requirements.txt
```

```
BLOCKING:
  ✗ prometheus-client: pinned 0.24.1, not installed
  ✗ prometheus-fastapi-instrumentator: pinned 7.1.0, not installed
  ✗ redis: pinned 7.2.1, not installed
advisory:
  · asyncpg: installed 0.29.0, pins 0.31.0
  · fastapi: installed 0.110.3, pins 0.133.1
  · httpx: installed 0.27.2, pins 0.28.1
  · python-dotenv: installed 1.0.1, pins 1.2.2
  · python-multipart: installed 0.0.22, pins 0.0.31
  · starlette: installed 0.37.2, pins 0.52.1
  · uvicorn: installed 0.29.0, pins 0.41.0
```

`website/backend/metrics.py` and the Redis caching path both
`try: import ... except ImportError:` and fall back to no-ops — metrics and
Redis caching are silently off on the running web service right now, not
crashing. Same silent-degradation shape as other issues this project has hit
before (a missing feature with no error, not a missing feature with a loud
one).

## Recommended order, package by package

### 1. `prometheus-client` + `prometheus-fastapi-instrumentator` — lowest risk
Currently **not installed at all** (not a version bump — pure addition). The
no-op fallback in `metrics.py` already proves the code path degrades safely
without them; installing just turns metrics from silently-off to on. No
known breaking-change surface for this project's usage (counters/gauges are
a stable, narrow API). Install first, verify `/metrics` (or wherever
`prometheus-fastapi-instrumentator` mounts it) returns real values instead
of the no-op zeros.

### 2. `redis` — low risk, but verify the caching path actually engages
Also not installed at all. `http_cache_middleware.py`'s cache backend
degrades to in-memory or no-op without it (exact fallback depends on
`create_cache_backend_from_env` — check that path specifically once
installed). Installing turns on Redis-backed caching, which changes
*behavior* under load (cache hit/miss patterns, TTL expiry) even though it
shouldn't change any response *shape*. Verify with `redis-cli monitor` (or
`INFO stats`) that keys actually get written after a proximity page load —
"the package imports" is not the same as "the cache backend selected it."

### 3. `python-dotenv`, `httpx` — low risk, minor version gaps
1.0.1→1.2.2 and 0.27.2→0.28.1 respectively — both well inside their stable
minor-version ranges, narrow usage in this codebase (env loading, outbound
HTTP calls). No specific breaking changes found for either at this gap.
Bundle with step 2 or run standalone; low enough risk either way.

### 4. `python-multipart` — check upload paths specifically
0.0.22→0.0.31. This library backs FastAPI's file upload parsing — directly
exercises `uploads.py` (community file upload library) and Greatshot's
upload validators (`upload_validators.py`, magic-byte/extension checks).
Low general risk, but this project has hardened upload security work
recently (see `website/backend/CLAUDE.md` security section) — re-run the
upload security tests specifically after this one, not just the full suite
passing.

### 5. `asyncpg` — moderate risk, DB is the shared dependency with the bot
0.29.0→0.31.0. Every query in `website/backend` goes through this. Check
asyncpg's own changelog for the 0.29→0.31 range before bumping — this
document does not certify it clean, only flags it as worth a dedicated look
given it touches every endpoint. The bot (`venv/`) pins its own asyncpg
version independently (separate venv), so this bump is website-only and
doesn't force a matching bot-side change, but worth confirming they don't
drift into two behaviorally-different asyncpg majors long-term.

### 6. `uvicorn` — moderate risk, changes the actual running server
0.29.0→0.41.0 (12 minor versions). Runs the process itself — worth doing in
a maintenance window with an easy rollback (keep the old venv or a pinned
wheel cache), not blind on a live service.

### 7. `starlette` — bundled with FastAPI, don't bump independently
0.37.2→0.52.1. FastAPI pins a compatible Starlette range internally;
bumping `starlette` on its own risks a combination FastAPI 0.110 doesn't
support. Let the FastAPI bump (step 8) pull the correct Starlette version
rather than pinning this one by hand.

### 8. `fastapi` 0.110.3 → 0.133.1 — highest risk, last, own test cycle
23 minor versions. Checked FastAPI's own release notes for breaking changes
in this range specifically (not just "big gap = scary"):

- **0.132.0 — `strict_content_type` for JSON requests, on by default.**
  Requests without a valid `Content-Type` header now get rejected unless
  `strict_content_type=False` is set. **Checked this project's webhook
  caller** (`vps_scripts/stats_discord_webhook.lua:394`) — it already sends
  `Content-Type: application/json` explicitly via curl, so the webhook path
  is fine. Still worth grepping for any *other* POST caller (internal
  scripts, greatshot tooling, health checks) that might not set it before
  flipping this on.
- **0.128.0 — drops `pydantic.v1` support entirely** (min Pydantic now
  `>=2.7.0`). Grepped this repo: no `pydantic.v1` compat imports found — not
  a blocker here.
- **0.131.0 — deprecates `ORJSONResponse`/`UJSONResponse`.** Not used in
  this codebase — not a blocker.
- **0.129.0 — drops Python 3.8.** Irrelevant; this project runs 3.10/3.11.

No fatal blocker found for this specific codebase, but 23 minor versions is
still enough surface that "no known blocker" isn't the same as "safe" —
treat this as its own staging-tested change, last in the sequence, after
everything below it in the dependency graph (starlette, asyncpg, uvicorn,
python-multipart) is already current.

## Verify (after the owner executes any step)

```bash
website/venv/bin/python scripts/check_env.py --no-env --requirements website/requirements.txt
# metrics endpoint returns real values, not the no-op zeros
# redis-cli monitor shows writes after a page load
# full pytest suite + upload-security tests specifically after step 4
```
