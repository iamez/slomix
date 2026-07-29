# W3 — triage of slow responses (2026-07-29)

Task W3 from `docs/TASKS_FOR_SONNET_2026-07-29.md`. Method: sort every `← ... →
status (Xms)` line in `logs/access.log` by duration, then read the code and
surrounding log context for the worst offenders. Two distinct root causes found —
neither is the "missing index" pattern the task doc used as its reference case
(the re-linker UNION→UNION ALL fix). Full sorted list is reproducible with:

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
call at all).

**One real finding**: the `304 (10449.7ms)` line. A `304 Not Modified` should be
cheap — but `http_cache_middleware.py`'s MISS path (lines 124-198) only computes
an ETag *after* calling the full expensive endpoint and building the response
body, then compares it against the client's `If-None-Match`. So a 304 on a cache
miss still pays the full compute cost; it only saves the response body's bandwidth,
not the 10+ seconds of CPU time. This is a real but minor inefficiency (304s are
presumably rare on a cold cache — the client needs a stale ETag from a *previous*
render to send one) and not worth a code change on its own.

**Recommendation**: leave as-is. This is already about as well-mitigated as
reasonably possible without a background pre-warm job. Not a fix candidate.

## 2. Homepage fan-out — 18-19 endpoints in the same 1-8 second window, each 6.5-19s

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

This is the same request-shape W2 already flags for the 429 self-rate-limiting
problem: a single homepage load fans out to ~19 concurrent API calls. Here the
symptom is different — every one of those unrelated endpoints (proximity,
predictions, stats, availability — nothing in common code-wise) landed at
**nearly the same ~7s duration simultaneously**. That pattern doesn't look like
19 independently slow queries; it looks like shared contention — the DB
connection pool or the event loop getting saturated by the burst, so each request
queues rather than actually taking 7s of query time on its own. This repo's
`website/backend` does not define its own asyncpg pool size in the files
searched (`local_database_adapter.py`, `main.py`) — it likely inherits pool
sizing from the shared bot-side adapter, which is worth checking directly if this
recurs, rather than assumed here.

The single `/api/live-status → 200 (18998.8ms)` outlier (2026-03-11 01:20:01)
lines up exactly with a service **startup** in the same log window (`BotConfig`
init, `SeasonManager initialized` immediately above it) — first-request-after-cold-start
cost (connection handshake, import warmup), not a recurring pattern.

**Recommendation**: this doesn't need a separate fix from W2. If W2's
batching/staggering of the homepage's API calls lands, it directly reduces the
concurrent burst that's the likely cause of this cluster too — implement once,
verify both. Don't chase this as an independent "slow query" with `EXPLAIN
ANALYZE`; none of the individual endpoints in the cluster are slow in isolation
(each returns well under 1s per their own code paths elsewhere in the log).

## Verify

Tried against the local dev backend with `session_date=2026-07-20` (a date with
known session data) — got a 404 both times, too fast to exercise the slow path,
so cache-hit-vs-miss timing wasn't directly re-confirmed live. This doc's
conclusions rest on reading `advanced_metrics.py:544-614` and
`http_cache_middleware.py` directly (the mitigation comments are explicit and
match the observed log durations exactly), not on a fresh repro. If this is
worth re-verifying live, it needs a `session_date`/scope with real
`player_track` rows and a cold cache (`redis-cli FLUSHDB` or wait out the 300s
TTL) — first call should land near the 10-13s range seen in the log, the
immediate repeat should be near-instant.
