# W3 — triage of slow responses (2026-07-29)

Task W3 from a session working-doc (`docs/TASKS_FOR_SONNET_2026-07-29.md` — not tracked in
this repo, not a citable source; every finding below is independently reproducible from
`logs/access.log` and this repo's tracked code). Method: sort every `← ... → status (Xms)`
line in `logs/access.log` by duration, then read the code and surrounding log context for
the worst offenders. Two distinct root causes found — neither is the "missing index" pattern
the task doc used as its reference case (the re-linker UNION→UNION ALL fix). Full sorted list
is reproducible with:

```bash
grep -oE "← .* → [0-9]+ \([0-9]+\.[0-9]ms\)" logs/access.log | sort -t'(' -k2 -rn | head -20
```

## 1. `/api/storytelling/lurker-profile` — 5 occurrences, 10.4s–13.3s: already mitigated, not a bug

```
2026-06-07 20:59:00  200  13274.2ms
2026-06-07 21:05:05  200  13186.6ms
2026-06-07 21:02:14  200  12270.8ms
2026-04-21 03:56:36  200  11278.6ms
2026-05-09 13:30:13  304  10449.7ms   <- 304 still cost the full 10.4s, see below
```

`compute_lurker_profile()` (`website/backend/services/storytelling/advanced_metrics.py:544`)
is a documented-as-heavy pure-Python triple loop over `player_track.path` point
clouds (200ms samples downsampled to 1s). The code already carries three
mitigations, visible directly in the comments at lines 579-584:

- offloaded to `asyncio.to_thread` so it can't block the event loop (the comment
  literally says "~13s freeze" — this was already measured and addressed)
- a per-`gaming_session_id` lock (`_compute_locks`) so concurrent cold requests
  for the same session don't thrash the CPU redundantly
- `@limiter.limit("5/minute")` on the route

On top of that, `http_cache_middleware.py` caches `/api/storytelling/*` at the
same 300s TTL as leaderboards specifically *because* of this cost — see the
comment at `_ttl_for_path` line 285-288 ("Recompute cost per request includes 11
parallel moment detectors + KIS lookups, so a 5-minute cache dominates the
latency profile"). The 5 slow entries above are cache-miss/cold-cache
computations; every subsequent identical request within 5 minutes is a cache hit
(near-instant, verified by reading the middleware's HIT path — no `call_next()`
call at all) — **for anonymous requests only**. `HTTPCacheMiddleware.dispatch()`
(`http_cache_middleware.py:87-91`) explicitly sends `Cache-Control: private,
no-store` and skips the cache entirely whenever a `cookie` or `authorization`
header is present, so a *logged-in* user pays the full 10-13s on every load —
the "already cached, leave as-is" framing below only ever held for anonymous
traffic (Codex review on #574).

**Fixed, not just a minor inefficiency**: the `304 (10449.7ms)` line pointed at a
real bug, not a rare cosmetic cost. `http_cache_middleware.py`'s MISS path used
to compute the ETag *after* calling the expensive endpoint, then return 304
**before** calling `cache_backend.set()` if it matched the client's
`If-None-Match`. That's not "a 304 still pays the compute cost once" — a client
that keeps presenting the same ETag (normal browser behavior when the
underlying data genuinely hasn't changed) would get a 304 on *every* request
forever, and the cache would *never* populate, because the only code path that
writes to it was skipped every single time. Fixed by moving `cache_backend.set()`
before the 304 check, so the cache warms regardless of which response the
current client gets. Regression test:
`tests/unit/test_http_cache_middleware_304_warms_cache.py` (constructs a client
that presents a matching ETag on a cache MISS, asserts the cache backend is
non-empty afterward; verified it fails against the pre-fix code).

**Also not real request coalescing**: the per-`gaming_session_id` lock
(`advanced_metrics.py:584-587`) only serializes concurrent cold requests for the
same session — it has no cached-result check inside the critical section, so a
waiter that acquires the lock after the first request already ran still executes
the full ~13s computation itself, just one at a time instead of in parallel. It
prevents CPU thrashing from N simultaneous computations; it does not prevent N
redundant computations, and a request arriving just after another can wait for
multiples of 13s. Real coalescing (check-cache-again after acquiring the lock,
before recomputing) is a fix candidate, not implemented here — out of scope for
a triage doc, flagged for a follow-up.

**Recommendation**: with the 304 fix landed, this is close to as well-mitigated
as reasonably possible without a background pre-warm job or real lock
coalescing — both of which are legitimate follow-ups, not "leave as-is."

## 2. Homepage fan-out — root cause identified: a blocking UDP call freezes the whole event loop

```
2026-07-07 22:05:21-29  → /, /api/status, /api/availability, /api/sessions,
                          /api/skill/movers, /api/stats/overview,
                          /api/stats/live-session, /api/stats/quick-leaders,
                          /api/stats/matches, /auth/me, /api/challenges/current,
                          /api/seasons/current(+/leaders), /api/stats/tonight,
                          /auth/link/status, /api/live-status, /api/stats/trends,
                          /api/stats/last-session, /api/predictions/recent,
                          /api/stats/activity-calendar
← responses in the same window: 6.6s-7.6s each, unrelated endpoints
```

**Corrected from the original version of this doc**: this is *not* a single
19-way concurrent burst. `initApp()` (`website/js/app.js:722-785`) `await`s
`/api/status`, then `await`s a `Promise.allSettled` batch of ~6 critical calls,
and only after that resolves does `scheduleDeferredLoads()` fire the remaining
~8 as a second (still-concurrent-within-itself) batch via
`requestIdleCallback`/`setTimeout`. `loadHomePulseCards()`
(`website/js/home.js:95-123`) has the same two-batch shape. This pattern
predates the July 7 log entry by months (introduced 2026-02-19, commit
`fbd5ce0f`), so it isn't stale code needing to "catch up" — the 8-second spread
in the log is consistent with two sequential batches of ~6-8 concurrent calls
each, not one simultaneous 19-way burst.

**Real root cause, found by reading the code, not guessed**: `/api/live-status`
is one of the endpoints in that fan-out, and its handler
(`diagnostics_router.py:1153`) calls `query_game_server()`
(`website/backend/services/game_server_query.py:60`) as a **plain synchronous
function call inside an `async def` route** — no `await`, no
`asyncio.to_thread()`. That function opens a raw blocking `socket.socket()`,
calls `sock.sendto()` (which performs blocking DNS resolution if `host` isn't
already an IP — a step `sock.settimeout()` does not reliably bound), then
blocking `sock.recvfrom()` with a 3-second timeout. **A blocking call on the
event loop thread stalls the entire worker process, not just that one
request** — every other concurrently-in-flight request in the same batch stops
making progress until it returns. That is a direct, code-level explanation for
"every unrelated endpoint in the batch got equally slow at once": they weren't
independently slow, they were all waiting for the event loop to come back from
one blocking call. It also directly explains the standalone
`/api/live-status → 200 (18998.8ms)` outlier — 19s is far beyond the stated 3s
socket timeout, consistent with a slow/hanging DNS resolution step that
`settimeout()` doesn't cover.

(The originally-suspected "cold start" explanation for that 03-11 01:20:01
outlier doesn't hold either: Uvicorn doesn't serve *any* request until
FastAPI's startup hook — which already awaits `init_db_pool()` and cache init,
`main.py:386-394` — completes, so a served request can't itself be paying
import/connection-handshake cost merely because startup log lines precede it.)

Secondary, corroborating evidence: the website's DB pool is configured smaller
than the bot's — `POSTGRES_MIN_POOL=2` / `POSTGRES_MAX_POOL=10`
(`website/.env.example:17-18`, `slomix_vm_setup.sh:877-878`, wired through
`website/backend/dependencies.py`) vs. the bot's 10/30
(`slomix_vm_setup.sh:810-811`). A ceiling of 10 is real headroom to keep in
mind if DB-bound queries ever stack up during a batch, but it's not needed to
explain this specific cluster — the blocking UDP call is sufficient on its own
and matches the evidence directly.

**Recommendation**: fix `query_game_server()`'s call site to not block the
event loop — wrap it in `await asyncio.to_thread(query_game_server, ...)` (a
one-line change at the `diagnostics_router.py:1153` call site; the function
itself doesn't need to change). This is a more targeted, better-evidenced fix
than the original "batch/stagger the homepage calls" recommendation, and it's
independent of W2 — W2's rate-limit-headroom fix doesn't touch this code path
at all.

## Verify

```bash
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8000/api/live-status'
# 200 - confirms the asyncio.to_thread() fix doesn't break the endpoint
```

The `session_date=2026-07-20` used in the original version of this doc has no
matching session (same mistake as W1 — it 404s before reaching the slow path,
proves nothing). A cold-cache re-test needs a real session and, if using Redis,
should **not** use `redis-cli FLUSHDB` — that wipes the entire selected Redis
DB, which can destroy unrelated non-HTTP-cache keys if Redis is shared for
anything else. The cache backend already has a dedicated invalidation path for
exactly this (`RedisCacheBackend.invalidate_all()` →
`client.incr(self.namespace_key)`,
`website/backend/services/http_cache_backend.py:128-130`) — use that instead:

```bash
redis-cli INCR slomix:api_cache:namespace   # forces a cold cache without flushing unrelated keys
```

This doc's conclusions otherwise rest on reading `advanced_metrics.py:544-614`,
`http_cache_middleware.py`, `game_server_query.py`, and `app.js`/`home.js`
directly (the mitigation/bug evidence is explicit in each and matches the
observed log durations), not on a fresh live repro of the 10-13s cold-cache
path itself.
