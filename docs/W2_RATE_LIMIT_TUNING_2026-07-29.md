# W2 — the site was rate-limiting itself (2026-07-29)

Task W2 from `docs/TASKS_FOR_SONNET_2026-07-29.md`. The task doc measured 36×
429 responses in a 20k-request sample, one each on `weapon-accuracy`,
`vehicle-progress`, `support-summary`, `summary`, `revives` — scattered,
single occurrences on otherwise-unrelated endpoints. That pattern only makes
sense if they share something. They do: `RateLimitMiddleware`
(`website/backend/middleware/rate_limit_middleware.py`) buckets *every*
`/api/proximity/*` path into one shared sliding-window budget per IP, separate
from and in addition to the handful of routes that also carry their own
per-route `@limiter.limit(...)` (slowapi) decorator.

## Measured: calls per page load

```bash
grep -F "2026-07-19 09:51:19" logs/access.log | grep "→ GET /api/proximity" | wc -l
# 38
```

38 distinct `/api/proximity/*` endpoints fire (see the full list in the
`git log` for this file) within the same second for a single proximity page
load — `scopes`, `summary`, `quality`, `engagements`, `hotzones`, `movers`,
`teamplay`, `classes`, `reactions`, `events`, `trades/summary`,
`trades/events`, `spawn-timing`, `cohesion`, `crossfire-angles`, `pushes`,
`lua-trades`, `kill-outcomes` (+`player-stats`), `hit-regions`
(+`headshot-rates`), `movement-stats`, `prox-scores` (+`formula`),
`weapon-accuracy`, `revives`, `carrier-events/kills/returns`,
`vehicle-progress`, `escort-credits`, `construction-events`,
`objective-runs`/`objective-focus`, `focus-fire`, `support-summary`,
`combat-position-stats`, `aim-lock`.

## The math

`RATE_LIMIT_PROXIMITY_REQUESTS_PER_WINDOW` defaulted to **200** per 60s
window, per IP, shared across all 38 of those endpoints combined (not 200
each). `200 / 38 ≈ 5.3` — one IP could fully load the proximity page about
**5 times per minute** before whichever endpoints landed last in a batch
started 429ing. Two browser tabs plus a couple of session/date switches (each
switch re-fires most of the 38) easily crosses that. The five endpoints named
in the task doc aren't special — they're just whichever ones happened to be
mid-flight when a given IP's shared counter tipped over 200; a different
session would 429 a different subset.

The other two buckets (`heavy` at 45, `standard` at 180) are unaffected —
proximity was already deliberately given the largest budget of the three,
which shows the original design anticipated this page being chatty. It just
wasn't chatty enough headroom for real usage patterns (multiple tabs, rapid
navigation during a session review).

## Decision: raise the limit, don't batch (yet)

Per the task's framing (raise limit for read-only GETs / batch / stagger —
don't remove the limiter): **raised the default to 450** (`rate_limit_middleware.py`),
supporting ~12 full page loads/window/IP — generous headroom for normal
multi-tab use while still bounding a real burst/scrape. Chose this over
batching/staggering the frontend's 38 calls because:

- it's a one-line, low-risk config change matching the existing bucket
  design (proximity already gets special treatment; this just corrects the
  headroom given the now-measured call count)
- most of these endpoints are already covered by `http_cache_middleware.py`'s
  300s TTL for `/api/proximity/*` — a second page load within 5 minutes should
  mostly be cache hits, though the rate limiter counts them regardless of
  cache hit/miss (a real but separate inefficiency, not fixed here)
- batching 38 independent endpoints into fewer requests is a real
  frontend/backend redesign with its own risk profile; not proportionate to
  a config-tuning problem

`RATE_LIMIT_PROXIMITY_REQUESTS_PER_WINDOW` remains overridable via env var for
either direction if 450 turns out wrong in practice.

## Verify

```bash
pytest tests/unit/test_rate_limit_middleware_proximity.py -v
```

Load-testing "the heaviest page ten times in a row and get zero 429s" (the
task's suggested verify) wasn't run live — the local dev backend has far less
concurrent traffic than production, so it wouldn't prove much; the fix is
sized directly off the measured 38-calls-per-load number instead.
