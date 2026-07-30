# M4 — website/venv drift: recommended upgrade order (2026-07-29)

Task M4 from `docs/TASKS_FOR_SONNET_2026-07-29.md`. This is analysis only —
**no packages are installed by this document**. The actual `pip install` on
the running `website/venv` is owner-gated (installing all pins at once on a
running service is not obviously safe, `fastapi` especially).

## Measured (2026-07-29)

`scripts/check_env.py` is a local helper that isn't tracked in this
repository (not part of this commit tree), so the command that produced the
output below isn't reproducible from a fresh checkout:

```bash
website/venv/bin/python scripts/check_env.py --no-env --requirements website/requirements.txt
```

Reproduce it without that helper with the snippet below. `pip list
--outdated` is **not** a substitute — it never reads the manifest, so it
omits a pinned-but-missing package entirely (all three BLOCKING rows here)
and reports a correctly-pinned package as "outdated" whenever PyPI has
something newer (Codex review on #583). `pip install --dry-run` isn't an
option either: this venv's pip predates that flag, which is itself part of
the drift being measured.

```bash
website/venv/bin/python - <<'PY' website/requirements.txt
import re, sys
from importlib.metadata import version, PackageNotFoundError
missing, mismatch = [], []
for line in open(sys.argv[1]):
    # `[extras]` must be tolerated: website/requirements.txt pins
    # `uvicorn[standard]==0.41.0`, and a name-then-`==` pattern skips it
    # silently — the earlier version of this snippet missed the uvicorn drift
    # entirely while claiming to reproduce it (Codex review on #583).
    m = re.match(r'^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==([^\s;]+)', line.split('#')[0].strip())
    if not m:
        continue
    name, pinned = m.groups()
    try:
        got = version(name)
    except PackageNotFoundError:
        missing.append(f"{name} (pinned {pinned})")
    else:
        if got != pinned:
            mismatch.append(f"{name}: installed {got}, pinned {pinned}")
print("MISSING:  ", missing or "none")
print("MISMATCH: ", mismatch or "none")
PY
```

Verified to reproduce exactly the drift recorded below — all three missing
packages plus all **seven** version mismatches. (An earlier version of this
snippet reported only six: its regex required the name to be followed
immediately by `==`, so it silently skipped `uvicorn[standard]==0.41.0` while
this text claimed a complete match — Codex review on #583.)

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

## Before any step: stop the service, don't just restart after

Every step below mutates `site-packages` in a venv a live process is running
out of. `pip` removes and replaces package directories in place, so a request
or a lazy import landing mid-install can load a half-swapped module set and
fail — and it fails *before* the restart that was supposed to make the change
safe. This project's own deploy already does it the right way round:
`scripts/deploy_release.sh:519-541` stops `slomix-web slomix-bot` first, then
pips, with a comment naming "inconsistent imports" as the reason (Codex review
on #583).

So each step is: **stop → pip → start**, not pip → restart. The unit name, the
venv it runs from, and the port it serves are a matched set — mixing a
production unit name with this dev box's venv path (as an earlier version of
this section did, substituting only the stop target) points pip at an
environment the restarted service never loads (Codex review on #583). Pick one
column and stay in it:

| | dev box (this machine) | canonical VM |
|---|---|---|
| unit | `etlegacy-web` | `slomix-web` |
| venv | `website/venv` | `/opt/slomix/venv-web` |
| port | 8000 | 7000 |

```bash
# dev box
sudo systemctl stop etlegacy-web
website/venv/bin/pip install ...        # the step's install
sudo systemctl start etlegacy-web && sudo systemctl status etlegacy-web

# canonical VM (paths/ownership per docs/DEPLOYMENT_RUNBOOK.md:17-20,97-99)
sudo systemctl stop slomix-web
sudo -u slomix_web /opt/slomix/venv-web/bin/pip install ...
sudo systemctl start slomix-web && sudo systemctl status slomix-web
```

Note the VM installs run **as `slomix_web`**: `slomix_vm_setup.sh` chowns that
venv to the service account with no group write, so a plain `sudo pip` fails
the moment a pin actually changes — the same reason
`scripts/deploy_release.sh` uses `sudo_run_as`.

The restart is also what makes steps 1-2 take effect at all (see their notes) —
stopping first just means nothing is served from a half-installed tree in
between. Every `curl` example below uses the dev-box port 8000; use 7000 on the
VM.

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

Verify with an **unauthenticated** request, not by loading the page in your
logged-in browser. `HTTPCacheMiddleware.dispatch()`
(`http_cache_middleware.py:87-91`) sets `Cache-Control: private, no-store`
and skips the cache entirely whenever a `cookie` or `authorization` header is
present — so a normal logged-in page load produces no Redis writes at all and
would make a correctly-working backend look dead (Codex review on #583). Hit a
cacheable endpoint twice with a cookie-less client and watch the `X-Cache`
header go `MISS` → `HIT`:

```bash
curl -sS -D- -o /dev/null http://127.0.0.1:8000/api/stats/overview | grep -i x-cache   # MISS
curl -sS -D- -o /dev/null http://127.0.0.1:8000/api/stats/overview | grep -i x-cache   # HIT
redis-cli --scan --pattern 'slomix:*' | head              # keys actually present
```

`/api/stats/overview` specifically, **not** a proximity endpoint: whenever any
source query fails, the proximity scoring endpoints answer
`{"status": "degraded", ...}`, and `_is_uncacheable_status_body()`
(`http_cache_middleware.py:309`) deliberately turns every `status: error` /
`status: degraded` payload into `X-Cache: BYPASS-ERROR` without writing it to
Redis — so a correctly-connected backend could never show a HIT there, and the
check would blame Redis for an unrelated data problem (Codex review on #583).
Confirmed on this box: `/api/stats/overview` goes `MISS` → `HIT` reliably.

`X-Cache: BYPASS` on either call means the request carried a cookie (or the
path isn't cacheable), not that Redis is broken. "The package imports" is not
the same as "the cache backend selected it."

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
that lands them separately; treat it as one change, last in the sequence,
after asyncpg/uvicorn/python-multipart above are already current.

Install the **exact** analysed versions, not `-U`. `pip install -U fastapi
starlette` resolves to "newest available at run time", so if a newer release
lands between this analysis and the owner actually executing this
owner-gated step, it would install a version nobody reviewed — the
breaking-change review below would then describe a different upgrade than the
one performed (Codex review on #583):

```bash
website/venv/bin/pip install 'fastapi==0.133.1' 'starlette==0.52.1'
```

(Those are the pins already in `website/requirements.txt`, so
`pip install -r website/requirements.txt` is equivalent and stays in sync if
the pins are bumped deliberately later.)

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

Re-run the manifest comparison from the "Measured" section above (not
`pip list --outdated` — it can't see a missing package or the pinned version
at all). Start the service again after each step before checking; the checks
below all need a running process.

```bash
# 1. Manifest drift: rerun the heredoc from "Measured" — expect the row for
#    the package(s) just handled to disappear from MISSING/MISMATCH.

# 2. Dependency consistency (no broken transitive requirements):
website/venv/bin/pip check

# 3. after step 1 + restart: /metrics must be PRESENT and actually carry the
#    series. A status-only check can't tell a real metrics endpoint from an
#    empty-but-200 one, so grep the body rather than discarding it with
#    -o /dev/null (Codex review on #583):
curl -sS http://127.0.0.1:8000/metrics | grep -c '^slomix_'   # expect > 0

# 4. after step 2 + restart: X-Cache goes MISS -> HIT on a cookie-less request
#    against /api/stats/overview (see step 2 — a logged-in page load proves
#    nothing, and a proximity endpoint can answer `degraded` and never cache)

# 5. Tests do NOT run from website/venv — it has no pytest (requirements-dev.txt
#    carries pytest/pytest-asyncio/pytest-cov, and only the bot venv installs
#    that file). Verified: `website/venv/bin/python -c "import pytest"` fails
#    with ModuleNotFoundError. Run them from the root venv, which imports the
#    website package directly from the checkout, so it exercises the same source
#    the upgraded web service runs — but NOT the upgraded dependencies. Anything
#    that could plausibly be affected by the new pins needs a real request
#    against the restarted service (steps 3-4), not just a green suite:
venv/bin/python -m pytest tests/                              # after any step
venv/bin/python -m pytest tests/ -k "upload"                  # after step 4
```
