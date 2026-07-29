# M4 — website/venv drift: recommended upgrade order (2026-07-29)

Task M4 from `docs/TASKS_FOR_SONNET_2026-07-29.md`. This is analysis only —
**no packages are installed by this document**. The actual `pip install` on
the running `website/venv` is owner-gated (installing all pins at once on a
running service is not obviously safe, `fastapi` especially).

## Measured (2026-07-29)

`scripts/check_env.py` is a local helper that isn't tracked in this
repository (not part of this commit tree) — the command below isn't
reproducible from a fresh checkout as written. Its output is reproduced
verbatim here as the source of the drift numbers this plan is built on;
treat it as a description of what was run, not a command you can currently
re-run yourself. `pip list --outdated` against `website/requirements.txt`
in the same venv is the nearest equivalent already in the repo.

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

`website/backend/main.py` guards the Prometheus instrumentator with
`try: import ... except ImportError: Instrumentator = None`, and only
mounts `/metrics` `if PROMETHEUS_ENABLED and Instrumentator is not None`
(main.py:312) — with the package missing, `/metrics` isn't a "zero" or
degraded endpoint, it simply doesn't exist (404). Redis is a step short of
"off": `create_cache_backend_from_env()` (`http_cache_backend.py:175`)
already defaults to `MemoryCacheBackend()` unless `CACHE_BACKEND=redis` is
explicitly set — with the `redis` package missing, `RedisCacheBackend`'s
import fails, and if the running config *does* have `CACHE_BACKEND=redis`,
`ResilientCacheBackend.connect()` catches that, `logger.warning`s
"Primary cache backend unavailable, using memory fallback", and drops to
memory. So caching itself keeps working either way (in-memory instead of
Redis) — what's actually silent is that nothing tells you it downgraded
except that one warning line in `web.log`, easy to miss unless you're
looking for it.

## Recommended order, package by package

### 1. `prometheus-client` + `prometheus-fastapi-instrumentator` — lowest risk
Currently **not installed at all** (not a version bump — pure addition). No
known breaking-change surface for this project's usage (counters/gauges are
a stable, narrow API). **Requires a service restart to take effect** —
`Instrumentator = None` and the `if ... Instrumentator is not None` mount
check (`main.py:312`) both run once at import time, so installing the
package into the running venv doesn't retroactively mount `/metrics` on
the process that's already up. After install + restart, verify `/metrics`
is present at all (it's a 404 today, not a degraded/zero response) and
that the expected `slomix_*` series show up in it.

### 2. `redis` — low risk, but verify the caching path actually engages
Also not installed at all. Same restart caveat as step 1: the active cache
backend is selected once in `create_cache_backend_from_env()` at import
time, so the running process keeps using `MemoryCacheBackend` until
restarted even after `redis` is installed and `CACHE_BACKEND=redis` is set.
After install + restart, verify with `redis-cli monitor` (or `INFO stats`)
that keys actually get written after a proximity page load — "the package
imports" is not the same as "the cache backend selected it."

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
drift into two behaviorally-different asyncpg releases long-term (both
0.29.0 and 0.31.0 are 0.x — not a major-version jump, just worth watching
so a future gap doesn't become one).

### 6. `uvicorn` — moderate risk, changes the actual running server
0.29.0→0.41.0 (12 minor versions). Runs the process itself — worth doing in
a maintenance window with an easy rollback (keep the old venv or a pinned
wheel cache), not blind on a live service.

### 7. `fastapi` 0.110.3 → 0.133.1 **and** `starlette` 0.37.2 → 0.52.1 — highest risk, last, upgrade together
Do these two in the same step, not sequentially. FastAPI pins a compatible
Starlette range internally, so bumping `starlette` on its own first risks a
combination FastAPI 0.110 doesn't support — but letting `fastapi` pull
Starlette in transitively also means it isn't independently at "already
current" before this step starts. There's no atomicity-preserving order
that lands them separately; treat `pip install -U fastapi starlette` (or
the equivalent pinned-version bump in `requirements.txt`) as one change,
last in the sequence, after asyncpg/uvicorn/python-multipart above are
already current.

23 minor versions of FastAPI is a lot of surface — checked its release
notes for breaking changes in this specific range (not just "big gap =
scary"):

- **0.132.0 — `strict_content_type` for JSON requests, on by default.**
  Requests without a valid `Content-Type` header now get rejected unless
  `strict_content_type=False` is set. This only matters for callers that
  POST JSON *into this FastAPI app* — `vps_scripts/stats_discord_webhook.lua`
  and `vps_scripts/stats_webhook_notify.py` both POST to Discord's own
  webhook API (`configuration.discord_webhook_url` /
  `DISCORD_WEBHOOK_URL`), not to this service, so they say nothing about
  compatibility here. Grepped for any non-browser server-side caller that
  POSTs into `website/backend` directly: there isn't one — every JSON POST
  endpoint in `website/backend/routers/` is only ever called from browser
  `fetch()` in `website/frontend/src` or `website/js`, which sets
  `Content-Type: application/json` (or lets `FormData` set its own
  multipart boundary) by default. No known blocker, but worth a
  `grep -rn "method: 'POST'" website/frontend/src website/js` spot-check in
  staging rather than trusting that reasoning alone.
- **0.128.0 — drops `pydantic.v1` support entirely** (min Pydantic now
  `>=2.7.0`). Grepped this repo: no `pydantic.v1` compat imports found — not
  a blocker here.
- **0.131.0 — deprecates `ORJSONResponse`/`UJSONResponse`.** Not used in
  this codebase — not a blocker.
- **0.129.0 — drops Python 3.8.** Irrelevant; this project runs 3.10/3.11.

No fatal blocker found for this specific codebase, but "no known blocker"
isn't the same as "safe" — treat this as its own staging-tested change.

## Verify (after the owner executes any step)

`scripts/check_env.py` isn't in this repository (see the note under
"Measured" above) — the nearest in-repo equivalent is `pip list --outdated`
against `website/requirements.txt` in the same venv. Restart the service
after each step before checking (see the restart note on steps 1-2 above).

```bash
website/venv/bin/pip list --outdated
# after step 1 + restart: /metrics is present (not 404) and shows slomix_* series
# after step 2 + restart: redis-cli monitor shows writes after a page load
# full pytest suite + upload-security tests specifically after step 4
```
