"""Prometheus metric helpers for middleware instrumentation."""

try:
    from prometheus_client import Counter, Gauge, Histogram
except ImportError:  # pragma: no cover - optional dependency fallback
    class _NoopMetric:
        def __init__(self, *args, **kwargs):
            pass

        def inc(self, amount: float = 1.0) -> None:
            return None

        def observe(self, amount: float) -> None:
            return None

        def set(self, value: float) -> None:
            return None

        def labels(self, *args, **kwargs):
            return self

    Counter = _NoopMetric
    Gauge = _NoopMetric
    Histogram = _NoopMetric


API_CACHE_HITS = Counter(
    "slomix_api_cache_hits_total",
    "Total number of API cache hits",
)

API_CACHE_MISSES = Counter(
    "slomix_api_cache_misses_total",
    "Total number of API cache misses",
)

API_CACHE_INVALIDATIONS = Counter(
    "slomix_api_cache_invalidations_total",
    "Total number of cache namespace invalidations",
)

API_RATE_LIMIT_REJECTIONS = Counter(
    "slomix_api_rate_limit_rejections_total",
    "Total number of API requests rejected by rate limiting",
)

# Prox-scoring source-query health (audit AUD-008). Low-cardinality labels
# only — {source, outcome}; NEVER player/GUID labels (Prometheus naming
# practices). `outcome` ∈ {success, error}.
PROX_SOURCE_QUERIES = Counter(
    "slomix_prox_source_queries_total",
    "Proximity scoring source-query results",
    ["source", "outcome"],
)

PROX_SOURCE_QUERY_DURATION = Histogram(
    "slomix_prox_source_query_duration_seconds",
    "Per-source wall-clock duration of each proximity scoring query",
    ["source"],
)

# 1 while the LAST prox-scores compute for that scope was degraded (any source
# failed → ranking withheld), 0 once it recovers. `scope` is low-cardinality:
# leaderboard | player | round. Per-scope so a degraded one-off round request
# can't mask (or fake) leaderboard health — alerting keys on
# scope="leaderboard" (IMP-005).
PROX_DEGRADED = Gauge(
    "slomix_prox_scoring_degraded",
    "Whether the last proximity scoring compute for this scope was degraded",
    ["scope"],
)
